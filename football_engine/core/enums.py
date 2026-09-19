"""
Enumerations used across the engine.

These are pure closed-set types with no behaviour. Keeping them in one
module avoids circular imports between the entity modules that reference
them (TeamRuntimeState.state, PlayerSeason.role, etc.).

Architecture reference: Section P.3 (MatchState enum), Section R.3/R.4
(role tables). E-12 removes the misnamed formation enum; snapshot quality
is separately owned by football_engine.data_layer.snapshot_quality.
"""

from __future__ import annotations

from enum import Enum


class MatchState(str, Enum):
    """
    Runtime tactical state of a team, derived from score differential and
    match minute. Drives the Tactical Profile Generator (Module 5).

    Architecture reference: Section P.3.
    """

    NORMAL = "NORMAL"
    LEADING = "LEADING"
    LOSING = "LOSING"
    REACTIVE = "REACTIVE"  # late-game, urgent need for a goal


class PlayerRole(str, Enum):
    """
    Coarse positional role used for role-weight tables in Section R
    (scorer weight, assist weight) and Section 3 (team dimensions).
    """

    GK = "GK"
    CB = "CB"
    FB = "FB"
    DM = "DM"
    CM = "CM"
    WM = "WM"
    AM = "AM"
    FW = "FW"


class HistoricalTier(int, Enum):
    """
    Historical Team Hybrid Model tiering (Section 31).

    TIER_1 = Iconic teams, full historical prior, alpha ~0.5-0.6
    TIER_2 = Notable teams, partial historical prior, alpha ~0.75-0.85
    TIER_3 = Generic historical teams, no historical prior, alpha = 1.0
    """

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class SegmentId(int, Enum):
    """
    Canonical V1 segment schedule (Section 6, Section S.3).

    S1 = [0, 30)
    S2 = [30, 60)
    S3 = [60, 75)
    S4 = [75, 90+)
    """

    S1 = 1
    S2 = 2
    S3 = 3
    S4 = 4


class SplittingEventType(str, Enum):
    """
    Events that can break/split a segment (Section 6, Section N.10).

    Only GOAL and RED_CARD split; everything else is a non-splitting,
    "display" event handled by the Event Generator (Section Q).
    """

    GOAL = "GOAL"
    RED_CARD = "RED_CARD"


class NonSplittingEventType(str, Enum):
    """Display-only events that never split a segment (Section N.10, Q.10)."""

    YELLOW_CARD = "YELLOW_CARD"
    SUBSTITUTION = "SUBSTITUTION"
    SHOT = "SHOT"
    SAVE = "SAVE"
    MISSED_CHANCE = "MISSED_CHANCE"
