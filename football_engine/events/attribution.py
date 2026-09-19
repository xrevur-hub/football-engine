"""
Layer 6 — Player Events & Attribution (Modules 9/10).

This module generates coherent player events that emerge probabilistically
from the existing match model, NOT as independent random numbers.

Architecture (Section J/K/Q/R):
    Goal Count (from Dixon-Coles) → Shot Count → Player Attribution
    → Shots/Saves/Cards/Subs consistent with goals/tactics/players

Golden rules:
- R "فقط گل‌های موجود را به بازیکنان نسبت می‌دهد؛ هرگز گل جدید نمی‌سازد"
  → AttributedGoalEvent count must match SegmentOutcome goal counts
- Q "نمی‌تواند goal جدید بسازد"
  → ShotEvent/SaveEvent/CardEvent/SubstitutionEvent never increment score
- All events derived from: team λ, tactics, player abilities/roles, match state
- Single SeededRNG source for all randomness
- Reproducible given same seed + same match context
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from football_engine.core.enums import NonSplittingEventType, PlayerRole
from football_engine.core.events import (
    AttributedGoalEvent,
    CardEvent,
    MatchEvents,
    SaveEvent,
    ShotEvent,
    SubstitutionEvent,
)
from football_engine.core.matchup import LambdaPair, MatchupResult
from football_engine.core.parameters import ParameterSet, DEFAULT_PARAMETER_SET
from football_engine.core.player_season import PlayerSeason
from football_engine.core.segment_outcome import SegmentOutcome
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import TeamDimensions
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.matchup.helpers import compute_directional_helpers
from football_engine.rng.seeded_rng import SeededRNG


# =============================================================================
# Configuration / Coefficients (explicit, not hidden)
# =============================================================================

@dataclass(frozen=True)
class EventGenerationCoefficients:
    """
    Coefficients for event generation. These are separate from Layer 3/4 coefficients.
    All are calibration-adjacent priors; real calibration should optimize these.
    """

    # Shot generation (Section Q.2)
    shots_per_lambda: float = 1.8          # Expected shots per unit λ (real match: ~11-15 shots/team)
    min_shots_per_goal: float = 1.0        # At least 1 shot per goal
    on_target_rate_base: float = 0.35      # Base on-target rate
    on_target_rate_creation_bonus: float = 0.15  # Bonus per creation dimension

    # Shot xG allocation (Section Q.3)
    goal_xg_share: float = 0.75            # Goals get this share of team xG
    miss_xg_total: float = 0.25            # Misses share remaining xG

    # Save generation (Section Q.4)
    save_probability_base: float = 0.70    # Base save prob for on-target non-goals
    save_gk_ability_weight: float = 0.30   # Weight of GK ability

    # Card generation (Section Q.5/Q.7)
    yellow_card_base_rate: float = 0.02    # Per-minute base rate
    yellow_card_press_weight: float = 0.01  # Press intensity multiplier
    yellow_card_discipline_weight: float = 0.015  # Inverse discipline multiplier
    red_card_base_rate: float = 0.0008     # Per-minute base rate
    red_card_press_weight: float = 0.0005   # Press intensity multiplier

    # Substitution (Section Q.6)
    sub_probability_per_minute_late: float = 0.005  # Base prob in S3/S4
    sub_impact_weight: float = 0.003        # Impact score weight
    sub_trailing_bonus: float = 0.002       # Bonus when losing
    sub_leading_penalty: float = 0.001      # Penalty when leading

    # Goal attribution (Section R.3/R.4)
    scorer_attack_weight: float = 1.0      # Attack ability weight for scorer
    scorer_creation_weight: float = 0.5    # Creation ability weight for scorer
    scorer_role_weights: dict = None       # Role-based scorer weights

    assist_creation_weight: float = 1.0    # Creation ability weight for assist
    assist_vision_weight: float = 0.5      # Vision-like weight (using creation)
    assist_role_weights: dict = None       # Role-based assist weights

    def __post_init__(self):
        if self.scorer_role_weights is None:
            object.__setattr__(self, 'scorer_role_weights', {
                PlayerRole.FW: 1.00,
                PlayerRole.AM: 0.80,
                PlayerRole.WM: 0.70,
                PlayerRole.CM: 0.40,
                PlayerRole.DM: 0.20,
                PlayerRole.FB: 0.15,
                PlayerRole.CB: 0.05,
                PlayerRole.GK: 0.01,
            })
        if self.assist_role_weights is None:
            object.__setattr__(self, 'assist_role_weights', {
                PlayerRole.AM: 1.00,
                PlayerRole.WM: 0.85,
                PlayerRole.CM: 0.75,
                PlayerRole.FW: 0.60,
                PlayerRole.FB: 0.40,
                PlayerRole.DM: 0.30,
                PlayerRole.CB: 0.10,
                PlayerRole.GK: 0.02,
            })


DEFAULT_EVENT_COEFFICIENTS = EventGenerationCoefficients()


# =============================================================================
# Helper: Weighted player selection
# =============================================================================

def weighted_player_choice(
    rng: SeededRNG,
    players: list[PlayerSeason],
    weight_fn,
    exclude: Optional[set[str]] = None,
) -> Optional[PlayerSeason]:
    """Select a player weighted by weight_fn, excluding certain players."""
    exclude = exclude or set()
    candidates = [p for p in players if p.id not in exclude]
    if not candidates:
        return None

    weights = []
    for p in candidates:
        w = weight_fn(p)
        weights.append(max(0.0, w))

    total = sum(weights)
    if total <= 0:
        return rng.choice(candidates)

    return rng.weighted_choice(candidates, weights)


def compute_scorer_weight(player: PlayerSeason, coeffs: EventGenerationCoefficients) -> float:
    """Compute scorer weight for a player based on attack/creation abilities and role."""
    role_weight = coeffs.scorer_role_weights.get(player.role, 0.1)
    return (
        coeffs.scorer_attack_weight * player.attack_ability / 100.0
        + coeffs.scorer_creation_weight * player.creation_ability / 100.0
    ) * role_weight


def compute_assist_weight(player: PlayerSeason, coeffs: EventGenerationCoefficients) -> float:
    """Compute assist weight for a player based on creation ability and role."""
    role_weight = coeffs.assist_role_weights.get(player.role, 0.1)
    return (
        coeffs.assist_creation_weight * player.creation_ability / 100.0
        + coeffs.assist_vision_weight * player.creation_ability / 100.0  # using creation as proxy
    ) * role_weight


# =============================================================================
# Goal Attribution (Module 9 / Section J/R)
# =============================================================================

def attribute_goals(
    rng: SeededRNG,
    outcome: SegmentOutcome,
    runtime: TeamRuntimeState,
    opponent_runtime: TeamRuntimeState,
    lambda_pair: LambdaPair,
    coeffs: EventGenerationCoefficients = DEFAULT_EVENT_COEFFICIENTS,
) -> list[AttributedGoalEvent]:
    """
    Attribute goals to specific players.

    For each team's goals, select scorer and (optionally) assist provider
    weighted by attack/creation abilities, role, and tactical context.
    """
    goals = []
    minute = outcome.goal_minute or runtime.segment_start

    # Home team goals
    if outcome.goals_home > 0:
        home_players = [p for p in runtime.roster if p in runtime.roster]  # placeholder
        # We need actual PlayerSeason objects - passed via roster reference
        # This will be populated by the caller with actual player objects

    return goals


def attribute_goals_for_team(
    rng: SeededRNG,
    team_runtime: TeamRuntimeState,
    opponent_runtime: TeamRuntimeState,
    num_goals: int,
    base_minute: int,
    team_players: list[PlayerSeason],
    is_home: bool,
    lambda_team: float,
    coeffs: EventGenerationCoefficients = DEFAULT_EVENT_COEFFICIENTS,
) -> list[AttributedGoalEvent]:
    """
    Attribute N goals for one team to specific players.

    Returns list of AttributedGoalEvent.
    """
    if num_goals <= 0:
        return []

    events = []
    used_scorers = set()  # Track to vary attribution slightly

    for i in range(num_goals):
        # Select scorer
        scorer = weighted_player_choice(
            rng, team_players,
            lambda p: compute_scorer_weight(p, coeffs),
            exclude=used_scorers,
        )
        if scorer is None:
            scorer = team_players[0]  # fallback

        used_scorers.add(scorer.id)

        # Select assist (optional, ~75% chance per Section R.4)
        assist = None
        assist_player = None
        if rng.bernoulli(0.75):
            assist_candidates = [p for p in team_players if p.id != scorer.id]
            if assist_candidates:
                assist_player = weighted_player_choice(
                    rng, assist_candidates,
                    lambda p: compute_assist_weight(p, coeffs),
                )

        # xG credit: split team λ across goals, with some variation
        base_xg = lambda_team / max(1, num_goals)
        # Add small random variation
        xg_variation = rng.uniform(0.8, 1.2)
        xg_credit = max(0.01, base_xg * xg_variation)

        # Minute: stagger if multiple goals in same segment
        goal_minute = base_minute + i if num_goals > 1 else base_minute

        events.append(AttributedGoalEvent(
            minute=goal_minute,
            team_id=team_runtime.team_id,
            is_home_team=is_home,
            scorer_player_id=scorer.id,
            assist_player_id=assist_player.id if assist_player else None,
            xg_credit=xg_credit,
        ))

    return events


# =============================================================================
# Shot Generation (Module 10 / Section Q.2/Q.3)
# =============================================================================

def generate_shots(
    rng: SeededRNG,
    outcome: SegmentOutcome,
    home_runtime: TeamRuntimeState,
    away_runtime: TeamRuntimeState,
    lambda_pair: LambdaPair,
    home_players: list[PlayerSeason],
    away_players: list[PlayerSeason],
    coeffs: EventGenerationCoefficients = DEFAULT_EVENT_COEFFICIENTS,
) -> list[ShotEvent]:
    """
    Generate shot events consistent with goals and team λ.

    Architecture: Goal Count → Shot Count → Player Attribution
    - Total shots = goals + Poisson misses
    - On-target rate depends on creation ability and tactics
    - Goals are subset of on-target shots
    """
    shots = []
    minute_base = outcome.goal_minute or 0

    for team_runtime, team_players, num_goals, lambda_val, is_home in [
        (home_runtime, home_players, outcome.goals_home, lambda_pair.lambda_home_90, True),
        (away_runtime, away_players, outcome.goals_away, lambda_pair.lambda_away_90, False),
    ]:
        # Expected total shots
        expected_shots = max(num_goals, lambda_val * coeffs.shots_per_lambda)
        # Add Poisson variation for misses
        total_shots = max(num_goals, int(rng.poisson(expected_shots)))

        # On-target probability
        creation_avg = sum(p.creation_ability for p in team_players) / len(team_players)
        on_target_prob = min(0.7, coeffs.on_target_rate_base + coeffs.on_target_rate_creation_bonus * creation_avg / 100.0)

        goals_assigned = 0
        for shot_idx in range(total_shots):
            is_goal = goals_assigned < num_goals
            on_target = is_goal or rng.bernoulli(on_target_prob)

            # xG: goals get higher share, misses get lower
            if is_goal:
                xg = lambda_val / max(1, num_goals) * coeffs.goal_xg_share
                goals_assigned += 1
            else:
                # Distribute remaining xG across misses
                remaining_xg = max(0.0, lambda_val - sum(s.xg for s in shots if s.is_goal and s.is_home_team == is_home))
                xg = remaining_xg / max(1, total_shots - num_goals) if total_shots > num_goals else 0.0
                xg *= coeffs.miss_xg_total

            # Minute: distribute across segment
            shot_minute = minute_base + int(rng.uniform(0, 1) * 15)  # spread within ~15 min window

            # Select shooter weighted by attack/creation
            shooter = weighted_player_choice(
                rng, team_players,
                lambda p: (p.attack_ability + p.creation_ability) / 200.0,
            )
            shooter_id = shooter.id if shooter else team_players[0].id

            shots.append(ShotEvent(
                minute=shot_minute,
                team_id=team_runtime.team_id,
                is_home_team=is_home,
                is_goal=is_goal,
                on_target=on_target,
                xg=xg,
            ))

    # Sort by minute
    shots.sort(key=lambda s: s.minute)
    return shots


# =============================================================================
# Save Generation (Module 10 / Section Q.4)
# =============================================================================

def generate_saves(
    rng: SeededRNG,
    shots: list[ShotEvent],
    home_runtime: TeamRuntimeState,
    away_runtime: TeamRuntimeState,
    home_players: list[PlayerSeason],
    away_players: list[PlayerSeason],
    coeffs: EventGenerationCoefficients = DEFAULT_EVENT_COEFFICIENTS,
) -> list[SaveEvent]:
    """
    Generate goalkeeper saves for on-target non-goal shots.

    Save probability depends on GK ability and shot quality.
    """
    saves = []

    # Find GK for each team
    home_gk = next((p for p in home_players if p.role == PlayerRole.GK), None)
    away_gk = next((p for p in away_players if p.role == PlayerRole.GK), None)

    for shot in shots:
        if not shot.on_target or shot.is_goal:
            continue

        if shot.is_home_team:
            gk = home_gk
            team_id = home_runtime.team_id
        else:
            gk = away_gk
            team_id = away_runtime.team_id

        if gk is None:
            continue

        # Save probability based on GK ability
        gk_ability_norm = gk.gk_ability / 100.0
        save_prob = coeffs.save_probability_base + coeffs.save_gk_ability_weight * gk_ability_norm
        save_prob = min(0.95, max(0.1, save_prob))

        if rng.bernoulli(save_prob):
            saves.append(SaveEvent(
                minute=shot.minute,
                team_id=team_id,
                is_home_team=shot.is_home_team,
                gk_player_id=gk.id,
            ))

    return saves


# =============================================================================
# Card Generation (Module 10 / Section Q.5/Q.7)
# =============================================================================

def generate_cards(
    rng: SeededRNG,
    runtime: MatchRuntime,
    home_runtime: TeamRuntimeState,
    away_runtime: TeamRuntimeState,
    home_players: list[PlayerSeason],
    away_players: list[PlayerSeason],
    segment: int,
    coeffs: EventGenerationCoefficients = DEFAULT_EVENT_COEFFICIENTS,
) -> list[CardEvent]:
    """
    Generate yellow/red cards.

    Rate depends on: base rate, match state, press intensity, player discipline.
    Only in segments where cards make sense (not S1 usually).
    """
    cards = []

    if segment == 1:  # Few cards in first 30 min
        return cards

    for team_runtime, team_players, is_home in [
        (home_runtime, home_players, True),
        (away_runtime, away_players, False),
    ]:
        # Match state influence
        state_multiplier = 1.0
        if team_runtime.state.name == "LOSING":
            state_multiplier = 1.5
        elif team_runtime.state.name == "REACTIVE":
            state_multiplier = 2.0
        elif team_runtime.state.name == "LEADING":
            state_multiplier = 0.7

        # Tactical press influence
        press = team_runtime.tactical_profile.press_final if hasattr(team_runtime, 'tactical_profile') and team_runtime.tactical_profile else 0.5

        for player in team_players:
            if player.role == PlayerRole.GK:
                continue  # GKs rarely get cards

            discipline = player.discipline_score  # 0-1, higher = more disciplined
            # Yellow card probability
            yc_prob = (
                coeffs.yellow_card_base_rate
                + coeffs.yellow_card_press_weight * press
                + coeffs.yellow_card_discipline_weight * (1.0 - discipline)
            ) * state_multiplier

            # Per-minute rate over segment duration
            segment_durations = {1: 30, 2: 30, 3: 15, 4: 15}
            duration = segment_durations.get(segment, 15)
            yc_prob_total = 1.0 - (1.0 - yc_prob) ** duration

            if rng.bernoulli(yc_prob_total):
                minute = runtime.segment_start + int(rng.uniform(0, duration))
                cards.append(CardEvent(
                    minute=minute,
                    team_id=team_runtime.team_id,
                    is_home_team=is_home,
                    player_id=player.id,
                    is_red=False,
                ))

                # Red card chance (small, usually from second yellow or direct)
                rc_prob = (
                    coeffs.red_card_base_rate
                    + coeffs.red_card_press_weight * press
                ) * state_multiplier
                rc_prob_total = 1.0 - (1.0 - rc_prob) ** duration
                if rng.bernoulli(rc_prob_total):
                    cards.append(CardEvent(
                        minute=minute + 1,
                        team_id=team_runtime.team_id,
                        is_home_team=is_home,
                        player_id=player.id,
                        is_red=True,
                    ))

    cards.sort(key=lambda c: c.minute)
    return cards


# =============================================================================
# Substitution Generation (Module 10 / Section Q.6)
# =============================================================================

def generate_substitutions(
    rng: SeededRNG,
    runtime: MatchRuntime,
    home_runtime: TeamRuntimeState,
    away_runtime: TeamRuntimeState,
    home_players: list[PlayerSeason],
    away_players: list[PlayerSeason],
    segment: int,
    coeffs: EventGenerationCoefficients = DEFAULT_EVENT_COEFFICIENTS,
) -> list[SubstitutionEvent]:
    """
    Generate substitutions.

    Only in S3/S4, max 3 per team. Probability depends on:
    - Impact score of players on bench
    - Match state (trailing teams sub more)
    - Player fatigue (simplified via minute)
    """
    subs = []

    if segment not in (3, 4):  # Only S3 (60-75) and S4 (75-90+)
        return subs

    for team_runtime, team_players, is_home in [
        (home_runtime, home_players, True),
        (away_runtime, away_players, False),
    ]:
        # Check subs already made
        subs_made = team_runtime.substitutions_made
        if subs_made >= 3:
            continue

        # Determine on-pitch vs bench
        on_pitch = set(team_runtime.players_on_pitch) if team_runtime.players_on_pitch else set(p.id for p in team_players[:11])
        bench = [p for p in team_players if p.id not in on_pitch]

        if not bench:
            continue

        # State influence
        state_mult = 1.0
        if team_runtime.state.name == "LOSING":
            state_mult = 1.5
        elif team_runtime.state.name == "REACTIVE":
            state_mult = 2.0
        elif team_runtime.state.name == "LEADING":
            state_mult = 0.5

        # Available sub slots
        slots = 3 - subs_made
        segment_durations = {3: 15, 4: 15}
        duration = segment_durations.get(segment, 15)

        for _ in range(slots):
            sub_prob = (
                coeffs.sub_probability_per_minute_late
                + coeffs.sub_impact_weight * sum(p.impact_score for p in bench) / len(bench)
            ) * state_mult

            if not rng.bernoulli(sub_prob * duration / 15.0):
                break

            # Player out: weighted by low impact (tired/ineffective)
            player_out = weighted_player_choice(
                rng, [p for p in team_players if p.id in on_pitch],
                lambda p: 1.0 - p.impact_score,
            )
            if not player_out:
                break

            # Player in: weighted by high impact (fresh/impactful)
            player_in = weighted_player_choice(
                rng, bench,
                lambda p: p.impact_score,
            )
            if not player_in:
                break

            minute = runtime.segment_start + int(rng.uniform(0, duration))
            subs.append(SubstitutionEvent(
                minute=minute,
                team_id=team_runtime.team_id,
                is_home_team=is_home,
                player_out_id=player_out.id,
                player_in_id=player_in.id,
            ))

            # Update tracking
            on_pitch.discard(player_out.id)
            on_pitch.add(player_in.id)
            bench.remove(player_in)
            team_runtime.substitutions_made += 1

    subs.sort(key=lambda s: s.minute)
    return subs


# =============================================================================
# MatchRuntime import (avoid circular)
# =============================================================================
from football_engine.core.match_runtime import MatchRuntime


# =============================================================================
# Main Event Generation Orchestrator (Module 10)
# =============================================================================

@dataclass
class EventGenerator:
    """
    Generates all non-splitting events for a segment.

    Uses single SeededRNG. Events are statistically coherent with:
    - Team λ (from Layer 3/4)
    - Tactical profile (press, tempo, etc.)
    - Player attributes (abilities, discipline, impact)
    - Match state (leading/losing/reactive)
    """
    parameters: ParameterSet = DEFAULT_PARAMETER_SET
    coeffs: EventGenerationCoefficients = DEFAULT_EVENT_COEFFICIENTS

    def generate_segment_events(
        self,
        rng: SeededRNG,
        outcome: SegmentOutcome,
        runtime: MatchRuntime,
        home_players: list[PlayerSeason],
        away_players: list[PlayerSeason],
        lambda_pair: LambdaPair,
        segment: int,
    ) -> MatchEvents:
        """
        Generate all events for a segment given the outcome.

        Called by MatchOrchestrator after segment outcome is sampled.
        """
        # 1. Attribute goals
        home_goals = attribute_goals_for_team(
            rng, runtime.home, runtime.away, outcome.goals_home,
            outcome.goal_minute or runtime.segment_start,
            home_players, True, lambda_pair.lambda_home_90, self.coeffs
        )
        away_goals = attribute_goals_for_team(
            rng, runtime.away, runtime.home, outcome.goals_away,
            outcome.goal_minute or runtime.segment_start,
            away_players, False, lambda_pair.lambda_away_90, self.coeffs
        )

        # Add to runtime goal log (for MatchResult validation)
        runtime.goals.extend(home_goals)
        runtime.goals.extend(away_goals)

        # 2. Generate shots
        shots = generate_shots(
            rng, outcome, runtime.home, runtime.away,
            lambda_pair, home_players, away_players, self.coeffs
        )

        # 3. Generate saves
        saves = generate_saves(
            rng, shots, runtime.home, runtime.away,
            home_players, away_players, self.coeffs
        )

        # 4. Generate cards
        cards = generate_cards(
            rng, runtime, runtime.home, runtime.away,
            home_players, away_players, segment, self.coeffs
        )

        # Add red cards to runtime for segment splitting
        for card in cards:
            if card.is_red:
                runtime.cards.append(card)

        # 5. Generate substitutions
        subs = generate_substitutions(
            rng, runtime, runtime.home, runtime.away,
            home_players, away_players, segment, self.coeffs
        )

        # Add subs to runtime
        for sub in subs:
            runtime.substitutions.append(sub)

        return MatchEvents(
            shots=shots,
            saves=saves,
            yellow_cards=[c for c in cards if not c.is_red],
            red_cards=[c for c in cards if c.is_red],
            substitutions=subs,
        )


def create_event_generator(
    parameters: ParameterSet | None = None,
    coeffs: EventGenerationCoefficients | None = None,
) -> EventGenerator:
    """Factory function."""
    return EventGenerator(
        parameters=parameters or DEFAULT_PARAMETER_SET,
        coeffs=coeffs or DEFAULT_EVENT_COEFFICIENTS,
    )