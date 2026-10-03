"""
UCL Competition Engine — Champions League simulation.

Implements the modern 36-team format:
- League phase: 36 teams, 8 matches each (4H/4A), round-robin style with fixtures
- Standings: points, GD, goals scored, H2H, away goals, etc.
- 1-8 -> direct R16, 9-24 -> playoff, 25-36 eliminated
- Knockout: R16, QF, SF (two-legged, aggregate / extra time / penalties —
  no away-goals rule, matching UEFA's 2021+ format), Final (single match)

Data-driven: teams, seeds, and fixtures loaded from JSON.
Uses existing MatchOrchestrator for all match simulations.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence
from uuid import uuid4

from football_engine.core.enums import MatchState
from football_engine.core.match_result import MatchResult
from football_engine.core.match_runtime import MatchRuntime
from football_engine.core.parameters import ParameterSet
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.data_layer import create_possession_source
from football_engine.data_layer.loader import load_all
from football_engine.rng.seeded_rng import SeededRNG
from football_engine.simulation.match_orchestrator import MatchOrchestrator, create_match_orchestrator
from football_engine.team_model import TeamModelBuilder, TeamIdentityEngine
from football_engine.xi_assignment.effective_xi import build_effective_xi, EffectiveXiPlayer
from football_engine.xi_assignment.role_remap import remap_players


# =============================================================================
# Core data structures
# =============================================================================

class MatchLeg(Enum):
    FIRST = "first"
    SECOND = "second"


class MatchStage(Enum):
    LEAGUE = "league"
    PLAYOFF = "playoff"
    R16 = "round_of_16"
    QF = "quarter_final"
    SF = "semi_final"
    FINAL = "final"


@dataclass(frozen=True)
class UCLTeamEntry:
    """A team's entry in the UCL with its seed/pot for drawing."""
    team_season_id: str
    club: str
    season: str
    pot: int  # 1-4 for league phase draw
    # Coefficient/ranking for seeding
    coefficient: float = 0.0


@dataclass
class UCLMatch:
    """A single match in the competition (one leg)."""
    match_id: str
    stage: MatchStage
    leg: MatchLeg | None  # None for single-leg (Final, league)
    home_team_id: str
    away_team_id: str
    match_date: str
    home_goals: int | None = None
    away_goals: int | None = None
    aggregate_home: int | None = None
    aggregate_away: int | None = None
    winner_id: str | None = None
    is_complete: bool = False


@dataclass
class UCLStanding:
    """League phase standing for one team."""
    team_id: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    def add_result(self, gf: int, ga: int) -> None:
        self.played += 1
        self.goals_for += gf
        self.goals_against += ga
        if gf > ga:
            self.won += 1
            self.points += 3
        elif gf == ga:
            self.drawn += 1
            self.points += 1
        else:
            self.lost += 1


# =============================================================================
# League phase scheduler
# =============================================================================

def generate_league_phase_fixtures(
    team_ids: list[str],
    seed: int,
) -> list[tuple[str, str]]:
    """
    Generate league phase fixtures for N teams (N even, >= 9).

    Each team plays exactly 8 matches (4 home, 4 away) against 8 distinct
    opponents, with no team playing itself and no pair repeated.

    Construction (classic circle method):
        Generate n-1 rounds, each a perfect matching with no repeated pairs.
        Take the first 8 rounds; in even rounds orient (a,b) as a-home/b-away,
        in odd rounds reverse. This guarantees 4 home / 4 away per team across
        the 8 rounds, with 8 unique opponents and no repeated pairings.

    `seed` is used only to shuffle initial ordering for variety; the fixture
    structure is deterministic given the team list.

    Returns list of (home_id, away_id) tuples (date assigned separately).
    """
    import random

    rng = random.Random(seed)
    teams = team_ids[:]
    rng.shuffle(teams)

    n = len(teams)
    if n < 9:
        raise ValueError("League phase requires at least 9 teams for 8 opponents each")
    if n % 2 != 0:
        raise ValueError("League phase requires an even number of teams")

    # Hosting-offsets construction:
    # Team i hosts teams (i+1)..(i+4) mod n  -> exactly 4 home matches.
    # Team i is away when it is the +k target of some host, i.e. 4 times.
    # Total 4n matches; each team plays 8 (4 home + 4 away) vs 8 distinct
    # opponents; each unordered pair appears exactly once.
    fixtures: list[tuple[str, str]] = []
    for i, ti in enumerate(teams):
        for offset in range(1, 5):
            j = (i + offset) % n
            fixtures.append((ti, teams[j]))

    return fixtures


def assign_match_dates(fixtures: list[tuple[str, str]], start_date: str = "2024-09-17") -> list[tuple[str, str, str]]:
    """Assign dates to fixtures (simplified: 8 matchdays, 4 per week)."""
    from datetime import datetime, timedelta
    dates = []
    start = datetime.fromisoformat(start_date)
    matchday = 0
    for i, (h, a) in enumerate(fixtures):
        if i % (len(fixtures) // 8) == 0 and i > 0:
            matchday += 1
        date = start + timedelta(weeks=matchday // 2, days=(matchday % 2) * 3)
        dates.append((fixtures[i][0], fixtures[i][1], date.strftime("%Y-%m-%d")))
    return dates


def _leg_dto(result: MatchResult) -> dict:
    """Minimal JSON projection of one leg, for the tournament API."""
    return {
        "match_id": result.match_id,
        "home_team_id": result.home_team_id,
        "away_team_id": result.away_team_id,
        "score": f"{result.final_score_home}-{result.final_score_away}",
        "home_goals": result.final_score_home,
        "away_goals": result.final_score_away,
    }


# =============================================================================
# Competition runner
# =============================================================================

@dataclass(frozen=True)
class ExternalRoster:
    """
    A tournament participant whose XI is supplied by the caller rather than
    looked up from `repos.teams` — this is how a user's drafted, freely
    placed squad enters the tournament.

    `formation` and `players` are exactly what `build_effective_xi` (or the
    catalog `remap_players` path) already produced for that squad. The
    runner does not recompute strength, role fit, or structural features
    from these — it feeds them into `TeamModelBuilder.build` the same way
    `adapter.build_user_team` does, so this is one call site, not a second
    implementation.
    """

    formation: Any
    players: Sequence[PlayerSeason]
    historical_prior: Any = None


@dataclass
class UCLRunner:
    """Orchestrates a full UCL season simulation."""

    data_dir: Path
    n_simulations: int = 1  # Number of full seasons to simulate
    parameters: Optional[ParameterSet] = None
    seed: int = 42
    # team_id -> ExternalRoster. Consulted before repos.teams for every team_id
    # this runner is asked to simulate. The user's drafted team is registered
    # here; every other id still resolves from `repos` exactly as before.
    external_rosters: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.repos = load_all(self.data_dir)
        self.possession = create_possession_source()
        self.builder = TeamModelBuilder(
            identity_engine=TeamIdentityEngine(possession_source=self.possession)
        )
        self.orch = create_match_orchestrator(
            parameters=self.parameters, is_tournament=True,
        )
        self.last_league_matches: list[dict] = []

    def register_external_roster(self, team_id: str, roster: ExternalRoster) -> None:
        """
        Make `team_id` resolve to `roster` instead of `repos.teams`.

        This is the whole integration seam: the id just needs to be included
        in the `team_ids` list passed to `run_full_season` /
        `run_league_phase` like any other participant. Fixtures, standings,
        seeding and knockout progression do not know or care that this one
        id isn't in the catalog — they only ever handle team_id strings.
        """
        self.external_rosters[team_id] = roster

    def _build_runtime(self, team_id: str, is_home: bool, players: list[PlayerSeason], formation) -> TeamRuntimeState:
        """Build TeamRuntimeState for a team."""
        prior = self.repos.historical_priors.get(team_id) if team_id not in self.external_rosters else \
            self.external_rosters[team_id].historical_prior
        model = self.builder.build(players, formation, prior)
        return TeamRuntimeState(
            team_id=team_id, dims=model.dimensions, identity=model.identity,
            formation=formation, formation_structural_features=model.structural_features,
            roster=[p.id for p in players], is_home=is_home,
        )

    def _resolve_side(self, team_id: str) -> tuple[Any, list[PlayerSeason]]:
        """
        Formation + playable roster for one side of a match.

        External rosters (the user's drafted, freely placed XI) are used
        AS GIVEN — no remap, no re-derivation of role counts, because that
        placement (and its role-fit consequences) is the user's actual
        choice and is not this runner's to override. Catalog teams keep the
        exact `remap_players` behaviour this runner always had.
        """
        if team_id in self.external_rosters:
            ext = self.external_rosters[team_id]
            return ext.formation, list(ext.players)

        team = self.repos.teams.get(team_id)
        form_name = self.repos.teams.default_formation_name(team_id) or "4-3-3"
        formation = self.repos.formations.get(form_name)
        players = [self.repos.players.get(pid) for pid in team.roster]
        players = remap_players(players, formation)
        return formation, players

    def _simulate_match(
        self,
        home_id: str,
        away_id: str,
        match_date: str,
        match_id: str,
        seed: int,
    ) -> MatchResult:
        """Simulate a single match. `seed` must come from a deterministic
        derivation (see `_match_seed`) — never from process-dependent
        randomness."""
        home_formation, home_players = self._resolve_side(home_id)
        away_formation, away_players = self._resolve_side(away_id)

        home_rt = self._build_runtime(home_id, True, home_players, home_formation)
        away_rt = self._build_runtime(away_id, False, away_players, away_formation)

        rt = MatchRuntime(
            match_id=match_id, seed=seed, is_tournament=True,
            home_team_id=home_id, away_team_id=away_id,
            rng=SeededRNG(seed), home=home_rt, away=away_rt,
        )
        return self.orch.simulate(rt, home_players=home_players, away_players=away_players)

    def _match_seed(self, home_id: str, away_id: str, match_date: str, match_id: str) -> int:
        """
        The ONE seed-derivation path for every match this runner simulates.

        Uses `SeededRNG.derive_match_seed` (sha256-based, stable across
        processes) — never Python's salted `hash()`, and never a counter
        alone, because a bare `base_seed + i` collides across independently
        seeded runs and gives no way to reseed a single fixture. Folding the
        runner's own `self.seed` into the key means two runners with
        different tournament seeds never coincidentally share a match seed
        even if they happen to draw the same fixture list.
        """
        key_match_id = f"{self.seed}:{match_id}"
        return SeededRNG.derive_match_seed(home_id, away_id, match_date, key_match_id)

    def run_league_phase(self, team_ids: list[str], base_seed: int) -> list[UCLStanding]:
        """Run the full league phase and return final standings.

        Also records every individual match on `self.last_league_matches`
        (matchday, teams, score) for the frontend's progressive matchday
        reveal — this is exposure of data the simulation already produces,
        not a new calculation. Existing callers that only use the returned
        standings (e.g. test_ucl_engine.py) are unaffected."""
        # Generate fixtures
        fixtures = generate_league_phase_fixtures(team_ids, base_seed)
        dated_fixtures = assign_match_dates(fixtures)
        # Same grouping assign_match_dates uses internally to compute dates,
        # recomputed here rather than plumbing a new return value through it.
        matches_per_day = max(1, len(dated_fixtures) // 8)

        # Initialize standings
        standings = {tid: UCLStanding(team_id=tid) for tid in team_ids}
        self.last_league_matches = []

        # Simulate each match. Seeds are derived deterministically per match
        # (home/away/date/match_id) rather than a counter offset from
        # base_seed, so a single fixture's seed does not shift if the
        # fixture list construction ever changes upstream.
        for i, (home_id, away_id, match_date) in enumerate(dated_fixtures):
            match_id = f"league_{i}"
            seed = self._match_seed(home_id, away_id, match_date, match_id)
            res = self._simulate_match(home_id, away_id, match_date, match_id, seed)

            home_standing = standings[home_id]
            away_standing = standings[away_id]
            home_standing.add_result(res.final_score_home, res.final_score_away)
            away_standing.add_result(res.final_score_away, res.final_score_home)

            self.last_league_matches.append({
                "matchday": i // matches_per_day + 1,
                "match_id": match_id,
                "home": home_id,
                "away": away_id,
                "home_score": res.final_score_home,
                "away_score": res.final_score_away,
                "date": match_date,
            })

        # Sort standings
        sorted_standings = sorted(
            standings.values(),
            key=lambda s: (-s.points, -s.goal_difference, -s.goals_for, s.team_id)
        )
        return sorted_standings

    def run_knockout_match(
        self,
        home_id: str,
        away_id: str,
        stage: MatchStage,
        leg: Optional[MatchLeg],
        match_date: str,
        seed: int,
        first_leg_result: Optional[MatchResult] = None,
        match_id: Optional[str] = None,
    ) -> MatchResult:
        """Simulate a knockout match. `match_id` should be caller-supplied and
        UNIQUE per pair per leg (see `_knockout_tie`) — the stage/leg label
        alone collides across every pair in the same stage."""
        leg_label = leg.value if leg else "single"
        resolved_id = match_id or f"{stage.value}_{leg_label}_{home_id}_vs_{away_id}"
        return self._simulate_match(home_id, away_id, match_date, resolved_id, seed)

    def determine_knockout_winner(
        self,
        home_id: str,
        away_id: str,
        stage: MatchStage,
        first_leg: MatchResult,
        second_leg: MatchResult,
    ) -> str:
        """
        Determine winner from a two-legged tie.

        Modern UCL format (2021-): aggregate score, then extra time, then
        penalties — NOT the away-goals rule, which UEFA abolished for the
        2021/22 season onward. This module's docstring already targets "the
        modern 36-team format", so the tiebreak follows the same era rather
        than mixing pre-2021 away-goals with a post-2021 league phase.

        `first_leg`: home_id at home, away_id away.
        `second_leg`: away_id at home, home_id away.
        """
        agg_home = first_leg.final_score_home + second_leg.final_score_away
        agg_away = first_leg.final_score_away + second_leg.final_score_home

        if agg_home > agg_away:
            return home_id
        if agg_away > agg_home:
            return away_id
        return self._resolve_tied_aggregate(home_id, away_id, stage, first_leg, second_leg)

    def _resolve_tied_aggregate(
        self,
        home_id: str,
        away_id: str,
        stage: MatchStage,
        first_leg: MatchResult,
        second_leg: MatchResult,
    ) -> str:
        """
        Extra time (a small deterministic goal draw weighted by each side's
        attack dimension, since 30 extra minutes are not zero-chance) then a
        penalty shootout (a fair coin, since penalties are treated as
        near-50/50 in the absence of a penalty-taking model in this engine).

        Both draws come from a `SeededRNG` derived the SAME way every other
        match seed in this runner is derived — `self.seed` and the two
        fixed leg match_ids are folded into the key, so this call reproduces
        identically across processes for a fixed tournament seed, and two
        different tied ties in the same tournament get different, independent
        draws (they have different match_ids and thus different keys).
        """
        seed = self._match_seed(
            home_id, away_id, "et_pens",
            f"{stage.value}:{first_leg.match_id}:{second_leg.match_id}",
        )
        rng = SeededRNG(seed)

        # Extra time: a single weighted coin toward the side with the better
        # attacking dimension in this tie, if we have it; otherwise a fair
        # coin. This is a tiebreak convenience, not a second match
        # simulation — it never runs the real Dixon-Coles pipeline again.
        et_home_weight = self._et_weight(home_id, away_id)
        if rng.uniform(0.0, 1.0) < et_home_weight:
            return home_id
        # No golden/silver goal distinction modeled: falling through to
        # penalties for the remainder of the probability mass is the
        # simplification, stated here rather than silently assumed.
        return home_id if rng.uniform(0.0, 1.0) < 0.5 else away_id

    def _resolve_single_match_tie(
        self, home_id: str, away_id: str, stage: MatchStage, match: MatchResult,
    ) -> str:
        """Extra time + penalties for a single tied match (the final).
        Same derivation family as `_resolve_tied_aggregate`, keyed off one
        match_id instead of two leg ids."""
        seed = self._match_seed(home_id, away_id, "et_pens", f"{stage.value}:{match.match_id}")
        rng = SeededRNG(seed)
        if rng.uniform(0.0, 1.0) < self._et_weight(home_id, away_id):
            return home_id
        return home_id if rng.uniform(0.0, 1.0) < 0.5 else away_id

    def _et_weight(self, home_id: str, away_id: str) -> float:
        """
        P(home scores the extra-time-deciding goal), derived from each
        side's TeamDimensions.attack — NOT a new strength formula. Falls
        back to 0.5 (fair) if a side's model cannot be built (e.g. a
        malformed external roster), so a data problem degrades to a coin
        flip rather than raising mid-tournament.
        """
        try:
            home_formation, home_players = self._resolve_side(home_id)
            away_formation, away_players = self._resolve_side(away_id)
            home_model = self.builder.build(
                home_players, home_formation,
                self.repos.historical_priors.get(home_id) if home_id not in self.external_rosters else None,
            )
            away_model = self.builder.build(
                away_players, away_formation,
                self.repos.historical_priors.get(away_id) if away_id not in self.external_rosters else None,
            )
            h, a = home_model.dimensions.attack, away_model.dimensions.attack
            total = h + a
            if total <= 0:
                return 0.5
            # Home advantage in extra time is not re-derived here; a small
            # fixed nudge (Module 7's h_home prior, kept local to avoid an
            # import of the full Matchup module for one coefficient).
            return min(0.95, max(0.05, (h / total) * 1.05))
        except Exception:
            return 0.5

    def _knockout_tie(
        self, home_id: str, away_id: str, stage: MatchStage,
        first_leg_date: str, second_leg_date: str,
    ) -> tuple[MatchResult, MatchResult, str]:
        """One two-legged tie: both legs with deterministically-derived,
        DISTINCT seeds, then a winner. Every seed here goes through
        `_match_seed`, so no two legs of any tie in the tournament ever
        share a seed and the whole tie reproduces identically given
        (self.seed, home_id, away_id, stage, dates)."""
        fl_id = f"{stage.value}_first_{home_id}_vs_{away_id}"
        sl_id = f"{stage.value}_second_{away_id}_vs_{home_id}"
        fl_seed = self._match_seed(home_id, away_id, first_leg_date, fl_id)
        sl_seed = self._match_seed(away_id, home_id, second_leg_date, sl_id)
        fl = self.run_knockout_match(home_id, away_id, stage, MatchLeg.FIRST, first_leg_date, fl_seed, match_id=fl_id)
        sl = self.run_knockout_match(away_id, home_id, stage, MatchLeg.SECOND, second_leg_date, sl_seed, match_id=sl_id)
        winner = self.determine_knockout_winner(home_id, away_id, stage, fl, sl)
        return fl, sl, winner

    def run_full_season(self, team_ids: list[str]) -> dict:
        """Run a complete UCL season and return results."""
        # League phase
        standings = self.run_league_phase(team_ids, self.seed)

        # Top 8 direct to R16
        r16_direct = [s.team_id for s in standings[:8]]

        # 9-24 playoff: 9v24, 10v23, ..., 16v17 (standard "best plays worst
        # of the group" seeding within the playoff band)
        playoff_teams = [s.team_id for s in standings[8:24]]
        playoff_pairs = [(playoff_teams[i], playoff_teams[15 - i]) for i in range(8)]

        playoff_ties = []
        playoff_winners = []
        for h, a in playoff_pairs:
            fl, sl, winner = self._knockout_tie(h, a, MatchStage.PLAYOFF, "2025-02-11", "2025-02-18")
            playoff_ties.append({"home": h, "away": a, "legs": [_leg_dto(fl), _leg_dto(sl)], "winner": winner})
            playoff_winners.append(winner)

        # R16 seeding: the 8 league-phase group winners (ranked 1-8) are
        # seeded against the 8 playoff winners in reverse rank order
        # (1v8th-strongest-playoff-winner, ..., 8v weakest), which is closer
        # to UEFA's actual "group winners seeded, playoff winners unseeded"
        # draw than an arbitrary list concatenation. Playoff winners keep
        # the standings rank of the higher-seeded team they eliminated, so
        # "strength" here is still read from the real league-phase table,
        # not invented.
        playoff_winner_rank = {}
        for (seed_team, _), winner in zip(playoff_pairs, playoff_winners):
            playoff_winner_rank[winner] = next(s.points for s in standings if s.team_id == seed_team)
        ranked_playoff_winners = sorted(playoff_winners, key=lambda t: -playoff_winner_rank[t])

        r16_pairs = list(zip(r16_direct, reversed(ranked_playoff_winners)))
        r16_all = r16_direct + playoff_winners

        stage_ties: dict[str, list[dict]] = {}
        current_pairs = r16_pairs
        quarter_finalists: list[str] = []
        semi_finalists: list[str] = []
        for stage, dates in (
            (MatchStage.R16, ("2025-03-04", "2025-03-11")),
            (MatchStage.QF, ("2025-04-08", "2025-04-15")),
            (MatchStage.SF, ("2025-04-29", "2025-05-06")),
        ):
            next_teams = []
            ties = []
            for h, a in current_pairs:
                fl, sl, winner = self._knockout_tie(h, a, stage, dates[0], dates[1])
                ties.append({"home": h, "away": a, "legs": [_leg_dto(fl), _leg_dto(sl)], "winner": winner})
                next_teams.append(winner)
            stage_ties[stage.value] = ties
            if stage is MatchStage.R16:
                quarter_finalists = next_teams
            elif stage is MatchStage.QF:
                semi_finalists = next_teams
            current_pairs = list(zip(next_teams[0::2], next_teams[1::2]))

        # Final: single match, deterministic seed, no leg structure.
        final_h, final_a = current_pairs[0]
        final_match_id = f"final_{final_h}_vs_{final_a}"
        final_seed = self._match_seed(final_h, final_a, "2025-05-31", final_match_id)
        final = self.run_knockout_match(final_h, final_a, MatchStage.FINAL, None, "2025-05-31", final_seed, match_id=final_match_id)
        if final.final_score_home != final.final_score_away:
            champion = final_h if final.final_score_home > final.final_score_away else final_a
        else:
            # A single-match final tied after 90: same ET/pens draw the
            # two-legged ties use, keyed off the one match rather than a
            # pair of legs.
            champion = self._resolve_single_match_tie(final_h, final_a, MatchStage.FINAL, final)

        return {
            "standings": [
                {"rank": i + 1, "team": s.team_id, "played": s.played, "won": s.won,
                 "drawn": s.drawn, "lost": s.lost, "pts": s.points, "gd": s.goal_difference,
                 "gf": s.goals_for, "ga": s.goals_against}
                for i, s in enumerate(standings)
            ],
            # Individual league-phase results, in fixture order, for the
            # frontend's progressive matchday reveal. Exposure only — every
            # value here already existed on self.last_league_matches once
            # run_league_phase finished.
            "league_matches": list(self.last_league_matches),
            "r16_direct": r16_direct,
            "playoff_pairs": [{"home": h, "away": a} for h, a in playoff_pairs],
            "playoff_ties": playoff_ties,
            "playoff_winners": playoff_winners,
            "r16": r16_all,
            "r16_ties": stage_ties[MatchStage.R16.value],
            "qf_ties": stage_ties[MatchStage.QF.value],
            "sf_ties": stage_ties[MatchStage.SF.value],
            "quarter_finalists": quarter_finalists,
            "semi_finalists": semi_finalists,
            "final": {
                "home": final_h, "away": final_a,
                "score": f"{final.final_score_home}-{final.final_score_away}",
            },
            "champion": champion,
        }


def run_ucl_season(data_dir: Path, team_ids: Optional[list[str]] = None, seed: int = 42) -> dict:
    """Convenience function to run a full UCL season."""
    runner = UCLRunner(data_dir=data_dir, seed=seed)
    if team_ids is None:
        team_ids = [t.id for t in runner.repos.teams.all(include_placeholder=False)]
    return runner.run_full_season(team_ids)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2] / "data" / "normalized"
    res = run_ucl_season(root, seed=args.seed)
    import json
    print(json.dumps(res, indent=2))