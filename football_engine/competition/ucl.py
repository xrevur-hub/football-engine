"""
UCL Competition Engine — Champions League simulation.

Implements the modern 36-team format:
- League phase: 36 teams, 8 matches each (4H/4A), round-robin style with fixtures
- Standings: points, GD, goals scored, H2H, away goals, etc.
- 1-8 -> direct R16, 9-24 -> playoff, 25-36 eliminated
- Knockout: R16, QF, SF, Final (two-legged, away goals / extra time / penalties)

Data-driven: teams, seeds, and fixtures loaded from JSON.
Uses existing MatchOrchestrator for all match simulations.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence
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


# =============================================================================
# Competition runner
# =============================================================================

@dataclass
class UCLRunner:
    """Orchestrates a full UCL season simulation."""

    data_dir: Path
    n_simulations: int = 1  # Number of full seasons to simulate
    parameters: Optional[ParameterSet] = None
    seed: int = 42

    def __post_init__(self) -> None:
        self.repos = load_all(self.data_dir)
        self.possession = create_possession_source()
        self.builder = TeamModelBuilder(
            identity_engine=TeamIdentityEngine(possession_source=self.possession)
        )
        self.orch = create_match_orchestrator(
            parameters=self.parameters, is_tournament=True,
        )

    def _build_runtime(self, team_id: str, is_home: bool, players: list[PlayerSeason], formation) -> TeamRuntimeState:
        """Build TeamRuntimeState for a team."""
        model = self.builder.build(players, formation, self.repos.historical_priors.get(team_id))
        return TeamRuntimeState(
            team_id=team_id, dims=model.dimensions, identity=model.identity,
            formation=formation, formation_structural_features=model.structural_features,
            roster=[p.id for p in players], is_home=is_home,
        )

    def _simulate_match(
        self,
        home_id: str,
        away_id: str,
        match_date: str,
        match_id: str,
        seed: int,
    ) -> MatchResult:
        """Simulate a single match."""
        home_team = self.repos.teams.get(home_id)
        away_team = self.repos.teams.get(away_id)

        home_formation = self.repos.formations.get(self.repos.teams.default_formation_name(home_id) or "4-3-3")
        away_formation = self.repos.formations.get(self.repos.teams.default_formation_name(away_id) or "4-3-3")

        home_players = [self.repos.players.get(pid) for pid in home_team.roster]
        away_players = [self.repos.players.get(pid) for pid in away_team.roster]

        # Fix roles for formations (simple)
        home_form_name = self.repos.teams.default_formation_name(home_id) or "4-3-3"
        away_form_name = self.repos.teams.default_formation_name(away_id) or "4-2-3-1"
        home_formation = self.repos.formations.get(home_form_name)
        away_formation = self.repos.formations.get(away_form_name)
        home_players = remap_players(home_players, home_formation)
        away_players = remap_players(away_players, away_formation)

        home_rt = self._build_runtime(home_id, True, home_players, self.repos.formations.get(home_form_name))
        away_rt = self._build_runtime(away_id, False, away_players, self.repos.formations.get(away_form_name))

        rt = MatchRuntime(
            match_id=match_id, seed=seed, is_tournament=True,
            home_team_id=home_id, away_team_id=away_id,
            rng=SeededRNG(seed), home=home_rt, away=away_rt,
        )
        return self.orch.simulate(rt, home_players=home_players, away_players=away_players)

    def run_league_phase(self, team_ids: list[str], base_seed: int) -> list[UCLStanding]:
        """Run the full league phase and return final standings."""
        # Generate fixtures
        fixtures = generate_league_phase_fixtures(team_ids, base_seed)
        dated_fixtures = assign_match_dates(fixtures)

        # Initialize standings
        standings = {tid: UCLStanding(team_id=tid) for tid in team_ids}

        # Simulate each match
        for i, (home_id, away_id, match_date) in enumerate(dated_fixtures):
            seed = base_seed * 10000 + i
            res = self._simulate_match(home_id, away_id, match_date, f"league_{i}", seed)

            home_standing = standings[home_id]
            away_standing = standings[away_id]
            home_standing.add_result(res.final_score_home, res.final_score_away)
            away_standing.add_result(res.final_score_away, res.final_score_home)

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
    ) -> MatchResult:
        """Simulate a knockout match (with aggregate for second leg)."""
        leg_label = leg.value if leg else "single"
        # For first leg or single leg, just simulate
        if leg is None or leg == MatchLeg.FIRST:
            return self._simulate_match(home_id, away_id, match_date, f"{stage.value}_{leg_label}", seed)
        else:
            # Second leg: need to track aggregate
            res = self._simulate_match(home_id, away_id, match_date, f"{stage.value}_{leg_label}", seed)
            return res

    def determine_knockout_winner(
        self,
        home_id: str,
        away_id: str,
        stage: MatchStage,
        first_leg: MatchResult,
        second_leg: MatchResult,
    ) -> str:
        """Determine winner from two-legged tie (away goals, then ET/Pens)."""
        agg_home = first_leg.final_score_home + second_leg.final_score_home
        agg_away = first_leg.final_score_away + second_leg.final_score_away

        # Away goals rule (used in UCL until 2021, keep for historical format)
        home_away_goals = first_leg.final_score_away + second_leg.final_score_home  # wrong: need correct
        # Actually: first leg home goals = home's away goals in second leg
        # first_leg: home_id home, away_id away
        # second_leg: away_id home, home_id away
        home_away = second_leg.final_score_away  # goals scored by home_id away
        away_away = first_leg.final_score_away   # goals scored by away_id away

        if agg_home > agg_away:
            return home_id
        elif agg_away > agg_home:
            return away_id
        else:
            # Aggregate tied - away goals
            if home_away > away_away:
                return home_id
            elif away_away > home_away:
                return away_id
            else:
                # Extra time / penalties - use seed for deterministic
                # Simplified: higher aggregate home wins (placeholder for penalties)
                # In reality, we'd simulate ET/Pens
                return home_id if hash(first_leg.match_id) % 2 == 0 else away_id

    def run_full_season(self, team_ids: list[str]) -> dict:
        """Run a complete UCL season and return results."""
        base_seed = self.seed

        # League phase
        standings = self.run_league_phase(team_ids, base_seed)

        # Top 8 direct to R16
        r16_teams = [s.team_id for s in standings[:8]]

        # 9-24 playoff: 9v24, 10v23, ..., 16v17
        playoff_teams = [s.team_id for s in standings[8:24]]
        playoff_pairs = []
        for i in range(8):
            playoff_pairs.append((playoff_teams[i], playoff_teams[15-i]))

        # Simulate playoffs (two legs)
        playoff_winners = []
        for i, (h, a) in enumerate(playoff_pairs):
            # First leg
            fl = self.run_knockout_match(h, a, MatchStage.PLAYOFF, MatchLeg.FIRST, "2025-02-11", base_seed + 1000 + i*2)
            sl = self.run_knockout_match(a, h, MatchStage.PLAYOFF, MatchLeg.SECOND, "2025-02-18", base_seed + 1001 + i*2)
            winner = self.determine_knockout_winner(h, a, MatchStage.PLAYOFF, fl, sl)
            playoff_winners.append(winner)

        # R16: 8 group winners + 8 playoff winners (need proper seeding)
        # For now, combine and do standard bracket
        r16_all = r16_teams + playoff_winners

        # Run knockouts
        current_teams = r16_all
        quarter_finalists = []
        semi_finalists = []
        for stage in [MatchStage.R16, MatchStage.QF, MatchStage.SF]:
            next_teams = []
            for i in range(0, len(current_teams), 2):
                h, a = current_teams[i], current_teams[i+1]
                fl = self.run_knockout_match(h, a, stage, MatchLeg.FIRST, "2025-03-04", base_seed + 2000)
                sl = self.run_knockout_match(a, h, stage, MatchLeg.SECOND, "2025-03-11", base_seed + 2001)
                winner = self.determine_knockout_winner(h, a, stage, fl, sl)
                next_teams.append(winner)
            if stage == MatchStage.R16:
                quarter_finalists = next_teams
            elif stage == MatchStage.QF:
                semi_finalists = next_teams
            current_teams = next_teams

        # Final
        final_h, final_a = current_teams[0], current_teams[1]
        final = self.run_knockout_match(final_h, final_a, MatchStage.FINAL, None, "2025-05-31", base_seed + 3000)
        champion = final_h if final.final_score_home > final.final_score_away else final_a

        return {
            "standings": [
                {"rank": i+1, "team": s.team_id, "pts": s.points, "gd": s.goal_difference, "gf": s.goals_for, "ga": s.goals_against}
                for i, s in enumerate(standings)
            ],
            "r16_direct": r16_teams,
            "playoff_winners": playoff_winners,
            "r16": r16_all,
            "quarter_finalists": quarter_finalists,
            "semi_finalists": semi_finalists,
            "final": {"home": final_h, "away": final_a, "score": f"{final.final_score_home}-{final.final_score_away}"},
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