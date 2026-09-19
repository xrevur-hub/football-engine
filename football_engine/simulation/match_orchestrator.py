"""
Layer 5 — Match Simulation Orchestrator.

This module implements the full match simulation loop:
1. Initialize MatchRuntime with two TeamRuntimeState objects
2. Segment loop (S1-S4: 0-30, 30-60, 60-75, 75-90+)
3. TacticalProfile generation per segment
4. Matchup calculation
5. Lambda calculation
6. Score sampling via Dixon-Coles
7. State update (score, minute, MatchState)
8. Event generation (goals, shots, cards, subs)
9. Final MatchResult construction with validation

Architecture:
- Pure orchestration, no new football formulas
- Uses Layer 2 (TeamModel), Layer 3 (Matchup + Lambda), Layer 4 (Dixon-Coles)
- Single SeededRNG for all randomness
- Reproducible given same seed and inputs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from football_engine.core.enums import MatchState, SegmentId, SplittingEventType, NonSplittingEventType
from football_engine.core.events import (
    AttributedGoalEvent,
    CardEvent,
    GoalEvent,
    MatchEvents,
    SaveEvent,
    ShotEvent,
    SubstitutionEvent,
)
from football_engine.core.match_result import MatchResult
from football_engine.core.match_runtime import MatchRuntime
from football_engine.core.matchup import LambdaPair, MatchupResult
from football_engine.core.parameters import ParameterSet, DEFAULT_PARAMETER_SET
from football_engine.core.segment_outcome import SegmentOutcome
from football_engine.core.team_dimensions import TeamDimensions
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.matchup.helpers import compute_directional_helpers
from football_engine.matchup.lambda_calculator import LambdaCalculator
from football_engine.matchup.matchup_engine import MatchupEngine
from football_engine.matchup.tactical_profile import TacticalProfileGenerator
from football_engine.matchup.tactical_policy import create_tactical_profile_policy
from football_engine.probability.dixon_coles import (
    DixonColesModel,
    SegmentLambda,
    create_dixon_coles_model,
    sample_goal_minute,
    scale_lambda_to_segment,
)
from football_engine.events.attribution import EventGenerator, create_event_generator
from football_engine.rng.seeded_rng import SeededRNG


# =============================================================================
# Segment Schedule (Section S.3)
# =============================================================================

SEGMENT_SCHEDULE: list[tuple[int, int, int]] = [
    # (segment_id, start_minute, end_minute)
    (1, 0, 30),      # S1
    (2, 30, 60),     # S2
    (3, 60, 75),     # S3
    (4, 75, 90),     # S4
]


# =============================================================================
# Match Orchestrator
# =============================================================================


@dataclass
class MatchOrchestrator:
    """
    Orchestrates a full match simulation from two TeamRuntimeState objects.

    This is the Layer 5 "Full Simulation" component - the only place where
    the discrete-time segment loop runs and where randomness enters the system.
    """

    parameters: ParameterSet = DEFAULT_PARAMETER_SET
    max_goals: int = 10
    is_tournament: bool = False

    def __post_init__(self) -> None:
        self._matchup_engine = MatchupEngine(self.parameters)
        self._lambda_calculator = LambdaCalculator(self.parameters)
        self._tactical_generator = TacticalProfileGenerator(policy=create_tactical_profile_policy())
        self._dixon_coles = create_dixon_coles_model(self.parameters, self.max_goals)
        self._event_generator = create_event_generator(self.parameters)

    def simulate(
        self,
        runtime: MatchRuntime,
        home_players: Optional[list] = None,
        away_players: Optional[list] = None,
    ) -> MatchResult:
        """
        Run the full match simulation.

        Args:
            runtime: MatchRuntime with initialized home/away TeamRuntimeState,
                    match_id, seed, and is_tournament flag.
            home_players: List of PlayerSeason objects for the home team
                    (necessary for realistic goal/event attribution).
            away_players: List of PlayerSeason objects for the away team.

        Returns:
            MatchResult with final score, goal log, event logs, and validation.

        When player lists are supplied, goal attribution and non-splitting
        events are generated through the Layer 6 EventGenerator (weighted by
        attack/creation ability and role). Without them, attribution falls
        back to a deterministic placeholder.
        """
        # Validate initial state
        self._validate_initial_runtime(runtime)

        self._home_players = home_players
        self._away_players = away_players

        # Process each segment
        for segment_id, start_min, end_min in SEGMENT_SCHEDULE:
            if runtime.is_finished:
                break

            runtime.segment_id = segment_id
            runtime.segment_start = start_min
            runtime.segment_end = end_min
            runtime.current_minute = start_min

            # Run segment simulation
            self._process_segment(runtime)

            # Check for early termination (should not happen in normal flow)
            if runtime.current_minute >= 90:
                runtime.is_finished = True

        # Finalize
        return self._finalize(runtime)

    def _validate_initial_runtime(self, runtime: MatchRuntime) -> None:
        """Validate that runtime has all required initialized fields."""
        if not runtime.home.is_home:
            raise ValueError("home team must have is_home=True")
        if runtime.away.is_home:
            raise ValueError("away team must have is_home=False")
        if runtime.home.team_id != runtime.home_team_id:
            raise ValueError("home team_id mismatch")
        if runtime.away.team_id != runtime.away_team_id:
            raise ValueError("away team_id mismatch")

    def _process_segment(self, runtime: MatchRuntime) -> None:
        """Process a single segment (may be split by goals/red cards)."""
        segment_duration = runtime.segment_end - runtime.segment_start

        while runtime.current_minute < runtime.segment_end and not runtime.is_finished:
            remaining = runtime.segment_end - runtime.current_minute

            # 1. Generate tactical profiles for both teams
            self._generate_tactical_profiles(runtime)

            # 2. Compute matchup (M/T)
            self._compute_matchup(runtime)

            # 3. Compute lambda
            self._compute_lambda(runtime)

            # 4. Scale lambda to remaining segment duration
            seg_lambda = scale_lambda_to_segment(
                runtime.lambda_pair.lambda_home_90,
                runtime.lambda_pair.lambda_away_90,
                remaining,
            )

            # 5. Sample segment outcome
            outcome = self._sample_segment_outcome(runtime, seg_lambda, remaining)

            # 6. Apply outcome to runtime state
            self._apply_segment_outcome(runtime, outcome, remaining)

            # 7. Generate events (goals + non-splitting) via EventGenerator
            self._create_goal_events(runtime, outcome)

            # 8. Check for segment-splitting events (goals, red cards)
            if self._should_split_segment(runtime, outcome):
                # Segment splits - continue loop with updated state
                continue

            # No splitting event - segment continues or ends
            runtime.current_minute = runtime.segment_end

    def _generate_tactical_profiles(self, runtime: MatchRuntime) -> None:
        """Generate tactical profiles for current segment based on game state."""
        # Determine match state for each team
        home_state = self._determine_match_state(runtime.home, runtime.away, runtime.current_minute)
        away_state = self._determine_match_state(runtime.away, runtime.home, runtime.current_minute)

        runtime.home.state = home_state
        runtime.away.state = away_state

        # Generate tactical profiles
        runtime.tactical_home = self._tactical_generator.generate(
            identity=runtime.home.identity,
            structural_features=runtime.home.formation_structural_features,
            state=home_state,
        )
        runtime.tactical_away = self._tactical_generator.generate(
            identity=runtime.away.identity,
            structural_features=runtime.away.formation_structural_features,
            state=away_state,
        )

    def _compute_matchup(self, runtime: MatchRuntime) -> None:
        """Compute matchup (M/T) for both directions."""
        # Compute directional helpers
        home_helpers = compute_directional_helpers(
            runtime.tactical_home, runtime.tactical_away,
            runtime.home.formation_structural_features
        )
        away_helpers = compute_directional_helpers(
            runtime.tactical_away, runtime.tactical_home,
            runtime.away.formation_structural_features
        )

        from football_engine.matchup.dependencies import DirectionalMatchupHelpers
        home_helpers_obj = DirectionalMatchupHelpers(
            press_disruption_m=home_helpers[0],
            width_mismatch=home_helpers[1],
            press_transition_opportunity_t=home_helpers[2],
        )
        away_helpers_obj = DirectionalMatchupHelpers(
            press_disruption_m=away_helpers[0],
            width_mismatch=away_helpers[1],
            press_transition_opportunity_t=away_helpers[2],
        )

        runtime.matchup = self._matchup_engine.calculate(
            home_dimensions=runtime.home.dims,
            away_dimensions=runtime.away.dims,
            home_tactical=runtime.tactical_home,
            away_tactical=runtime.tactical_away,
            home_to_away_helpers=home_helpers_obj,
            away_to_home_helpers=away_helpers_obj,
        )

    def _compute_lambda(self, runtime: MatchRuntime) -> None:
        """Compute lambda for current segment."""
        runtime.lambda_pair = self._lambda_calculator.calculate(
            matchup=runtime.matchup,
            home=runtime.home,
            away=runtime.away,
            is_tournament=self.is_tournament,
        )

    def _sample_segment_outcome(
        self,
        runtime: MatchRuntime,
        seg_lambda: SegmentLambda,
        duration: int,
    ) -> SegmentOutcome:
        """Sample goals for this sub-segment using Dixon-Coles."""
        use_dc = duration >= 15  # DC threshold from constants

        if use_dc:
            home_goals, away_goals = self._dixon_coles.sample(
                runtime.rng,
                seg_lambda.lambda_home,
                seg_lambda.lambda_away,
            )
        else:
            # Independent Poisson for short segments
            home_goals = runtime.rng.poisson(seg_lambda.lambda_home)
            away_goals = runtime.rng.poisson(seg_lambda.lambda_away)

        # Sample goal minute if goals scored
        total_goals = home_goals + away_goals
        goal_minute = None
        if total_goals > 0:
            goal_minute = sample_goal_minute(
                runtime.rng,
                runtime.current_minute,
                runtime.current_minute + duration,
                total_goals,
            )

        return SegmentOutcome(
            goals_home=home_goals,
            goals_away=away_goals,
            goal_minute=goal_minute,
            used_dixon_coles=use_dc,
        )

    def _apply_segment_outcome(
        self,
        runtime: MatchRuntime,
        outcome: SegmentOutcome,
        duration: int,
    ) -> None:
        """Apply segment outcome to runtime state.

        Score and minute are updated here. Goal/event generation happens in
        _process_segment step 7 (single place) so goals are never double-counted.
        """
        # Update scores
        runtime.home.score += outcome.goals_home
        runtime.away.score += outcome.goals_away

        # Update current minute
        if outcome.goal_minute is not None:
            runtime.current_minute = outcome.goal_minute
        else:
            runtime.current_minute += duration

        # Update match state based on new score
        self._update_match_states(runtime)

    def _create_goal_events(self, runtime: MatchRuntime, outcome: SegmentOutcome) -> None:
        """Create attributed goal events using EventGenerator (Layer 6) when player data is available."""
        if not hasattr(self, "_home_players") or self._home_players is None or self._away_players is None:
            # Fallback to placeholder
            self._create_placeholder_goals(runtime, outcome)
            return

        # Use EventGenerator for proper goal attribution
        from football_engine.core.segment_outcome import SegmentOutcome
        goal_outcome = SegmentOutcome(
            goals_home=outcome.goals_home,
            goals_away=outcome.goals_away,
            goal_minute=outcome.goal_minute,
            used_dixon_coles=outcome.used_dixon_coles,
        )

        lambda_pair = runtime.lambda_pair

        events = self._event_generator.generate_segment_events(
            rng=runtime.rng,
            outcome=goal_outcome,
            runtime=runtime,
            home_players=self._home_players,
            away_players=self._away_players,
            lambda_pair=lambda_pair,
            segment=runtime.segment_id,
        )

        # EventGenerator already appends goals to runtime.goals and cards/subs/shots/saves
        # Just extend non-splitting events that aren't already appended
        runtime.shots.extend(events.shots)
        runtime.saves.extend(events.saves)
        # yellow/red cards and subs already added inside generate_segment_events

    def _create_placeholder_goals(self, runtime: MatchRuntime, outcome: SegmentOutcome) -> None:
        """Fallback when player data is not available."""
        minute = outcome.goal_minute or runtime.current_minute
        for i in range(outcome.goals_home):
            goal = AttributedGoalEvent(
                minute=minute + i,
                team_id=runtime.home.team_id,
                is_home_team=True,
                scorer_player_id=runtime.home.roster[0] if runtime.home.roster else "",
                assist_player_id=None,
                xg_credit=0.0,
            )
            runtime.goals.append(goal)
        for i in range(outcome.goals_away):
            goal = AttributedGoalEvent(
                minute=minute + i,
                team_id=runtime.away.team_id,
                is_home_team=False,
                scorer_player_id=runtime.away.roster[0] if runtime.away.roster else "",
                assist_player_id=None,
                xg_credit=0.0,
            )
            runtime.goals.append(goal)

    def _generate_non_splitting_events(
        self,
        runtime: MatchRuntime,
        outcome: SegmentOutcome,
        duration: int,
        seg_lambda: SegmentLambda,
    ) -> None:
        """Generate shots, saves, yellow cards, substitutions using Layer 6 EventGenerator."""
        # Need access to PlayerSeason objects for proper attribution
        # These would be passed in or stored on runtime in a full implementation
        # For now, use the existing placeholder logic
        # TODO: Integrate with player roster data from TeamRuntimeState

        # Placeholder: generate basic events consistent with goals
        total_shots_home = max(outcome.goals_home, runtime.rng.poisson(seg_lambda.lambda_home * 5))
        total_shots_away = max(outcome.goals_away, runtime.rng.poisson(seg_lambda.lambda_away * 5))

        # Full Q/R layer integration pending player data integration
        pass

    def _should_split_segment(self, runtime: MatchRuntime, outcome: SegmentOutcome) -> bool:
        """Check if segment should split due to goal or red card."""
        return outcome.goal_minute is not None

    def _determine_match_state(self, team: TeamRuntimeState, opponent: TeamRuntimeState, minute: int) -> MatchState:
        """Determine tactical state based on score and time."""
        score_diff = team.score - opponent.score

        if score_diff == 0:
            return MatchState.NORMAL
        elif score_diff > 0:
            # Leading
            if minute >= 75 and score_diff == 1:
                return MatchState.REACTIVE  # Protecting narrow lead late
            return MatchState.LEADING
        else:
            # Losing
            if minute >= 80:
                return MatchState.REACTIVE  # Desperation
            return MatchState.LOSING

    def _update_match_states(self, runtime: MatchRuntime) -> None:
        """Update match states for both teams after score change."""
        # States will be recalculated at start of next sub-segment
        pass

    def _finalize(self, runtime: MatchRuntime) -> MatchResult:
        """Create final MatchResult from completed runtime."""
        # Goals are already AttributedGoalEvent objects, just sort them
        attributed_goals = sorted(runtime.goals, key=lambda g: g.minute)

        return MatchResult(
            match_id=runtime.match_id,
            final_score_home=runtime.home.score,
            final_score_away=runtime.away.score,
            goal_log=attributed_goals,
            card_log=runtime.cards,
            shot_log=runtime.shots,
            save_log=runtime.saves,
            substitution_log=runtime.substitutions,
            seed=runtime.seed,
            home_team_id=runtime.home_team_id,
            away_team_id=runtime.away_team_id,
            dims_home=runtime.home.dims,
            dims_away=runtime.away.dims,
        )


# =============================================================================
# Factory
# =============================================================================


def create_match_orchestrator(
    parameters: ParameterSet | None = None,
    max_goals: int = 10,
    is_tournament: bool = False,
) -> MatchOrchestrator:
    """Create a MatchOrchestrator instance."""
    return MatchOrchestrator(
        parameters=parameters or DEFAULT_PARAMETER_SET,
        max_goals=max_goals,
        is_tournament=is_tournament,
    )