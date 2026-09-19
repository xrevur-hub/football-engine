"""
Layer 0 — Core Models and Infrastructure.

This package contains the fundamental data models and infrastructure
used throughout the engine.
"""

from __future__ import annotations

from football_engine.core.constants import (
    DEFAULT_A_AWAY,
    DEFAULT_BASELINE,
    DEFAULT_CONVERSION_PRIOR,
    DEFAULT_H_HOME,
    DEFAULT_K_FORM,
    DEFAULT_K_GK,
    DEFAULT_K_P,
    DEFAULT_K_POSS_CALC,
    DEFAULT_K_RC,
    DEFAULT_K_T,
    DEFAULT_K_T2,
    DEFAULT_K_TE,
    DEFAULT_K_W,
    DEFAULT_K_YC,
    DEFAULT_P_ASSIST_EXISTS,
    DEFAULT_P_OFF_TARGET,
    DEFAULT_R_CARD,
    DEFAULT_RHO,
    DEFAULT_TRANSITION_WEIGHT,
    DC_MAX_GOALS_GRID,
    DC_MIN_DURATION_MINUTES,
    GLOBAL_AVG_ATTACK,
    GLOBAL_AVG_CREATION,
    GLOBAL_AVG_DEFENSE,
    GLOBAL_AVG_GK,
    MAX_PLAYER_COUNT,
    MAX_SUBSTITUTIONS_PER_TEAM,
    MIN_PLAYER_COUNT,
    PARAMETER_BOUNDS,
    ROLE_ATTACK_WEIGHT,
    ROLE_CREATION_WEIGHT,
    SEGMENT_SCHEDULE,
)
from football_engine.team_model.formation_engine import V1_LINE_HEIGHT_BASELINE_PRIOR
from football_engine.core.enums import (
    HistoricalTier,
    MatchState,
    NonSplittingEventType,
    PlayerRole,
    SegmentId,
    SplittingEventType,
)
from football_engine.core.formation import SlotDepth, SlotSide
from football_engine.core.events import (
    AttributedGoalEvent,
    CardEvent,
    GoalEvent,
    MatchEvents,
    SaveEvent,
    ShotEvent,
    SubstitutionEvent,
)
from football_engine.core.formation import Formation, PositionSlot
from football_engine.core.match_result import MatchResult
from football_engine.core.match_runtime import MatchRuntime
from football_engine.core.matchup import LambdaPair, MatchupResult
from football_engine.core.parameters import DEFAULT_PARAMETER_SET, ParameterSet
from football_engine.core.player_season import PlayerSeason
from football_engine.core.segment_outcome import SegmentOutcome
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.core.team_identity import TeamIdentity
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.core.team_season import (
    DimensionAdjustment,
    HistoricalPrior,
    IdentityPriors,
    TeamSeason,
    apply_historical_prior_to_dimensions,
    apply_historical_prior_to_identity,
)
from football_engine.core.tactical_profile import TacticalProfile

__all__ = [
    # constants
    "DEFAULT_A_AWAY",
    "DEFAULT_BASELINE",
    "DEFAULT_CONVERSION_PRIOR",
    "DEFAULT_H_HOME",
    "DEFAULT_K_FORM",
    "DEFAULT_K_GK",
    "DEFAULT_K_P",
    "DEFAULT_K_POSS_CALC",
    "DEFAULT_K_RC",
    "DEFAULT_K_T",
    "DEFAULT_K_T2",
    "DEFAULT_K_TE",
    "DEFAULT_K_W",
    "DEFAULT_K_YC",
    "DEFAULT_P_ASSIST_EXISTS",
    "DEFAULT_P_OFF_TARGET",
    "DEFAULT_R_CARD",
    "DEFAULT_RHO",
    "DEFAULT_TRANSITION_WEIGHT",
    "DC_MAX_GOALS_GRID",
    "DC_MIN_DURATION_MINUTES",
    "GLOBAL_AVG_ATTACK",
    "GLOBAL_AVG_CREATION",
    "GLOBAL_AVG_DEFENSE",
    "GLOBAL_AVG_GK",
    "MAX_PLAYER_COUNT",
    "MAX_SUBSTITUTIONS_PER_TEAM",
    "MIN_PLAYER_COUNT",
    "PARAMETER_BOUNDS",
    "ROLE_ATTACK_WEIGHT",
    "ROLE_CREATION_WEIGHT",
    "SEGMENT_SCHEDULE",
    "V1_LINE_HEIGHT_BASELINE_PRIOR",
    # enums
    "HistoricalTier",
    "MatchState",
    "NonSplittingEventType",
    "PlayerRole",
    "SegmentId",
    "SlotDepth",
    "SlotSide",
    "SplittingEventType",
    # events
    "AttributedGoalEvent",
    "CardEvent",
    "GoalEvent",
    "MatchEvents",
    "SaveEvent",
    "ShotEvent",
    "SubstitutionEvent",
    # models
    "Formation",
    "PositionSlot",
    "MatchResult",
    "MatchRuntime",
    "LambdaPair",
    "MatchupResult",
    "DEFAULT_PARAMETER_SET",
    "ParameterSet",
    "PlayerSeason",
    "SegmentOutcome",
    "StructuralFeatures",
    "TeamDimensions",
    "TeamIdentity",
    "TeamRuntimeState",
    "DimensionAdjustment",
    "HistoricalPrior",
    "IdentityPriors",
    "TeamSeason",
    "apply_historical_prior_to_dimensions",
    "apply_historical_prior_to_identity",
    "TacticalProfile",
]