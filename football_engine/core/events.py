"""
Event models — GoalEvent, AttributedGoalEvent, CardEvent, ShotEvent,
SaveEvent, SubstitutionEvent.

Architecture reference: Section J/K, Section O.2 (Modules 9/10), Section Q
(Event Generator), Section R (Player Attribution), Section N (Layer 0
required base types list).

Golden rules preserved here (Section J/K.1, Q.1, R.1):
    - These are all POST-SAMPLE objects. None of them can change λ.
    - R "فقط گل‌های موجود را به بازیکنان نسبت می‌دهد؛ هرگز گل جدید نمی‌سازد"
      → AttributedGoalEvent count must always match SegmentOutcome goal
      counts; that invariant is enforced by the orchestrator (Section S.9,
      Invariants 17/18), not by this module itself (this module only
      defines the shape).
    - Q "نمی‌تواند goal جدید بسازد" → ShotEvent/SaveEvent/CardEvent/
      SubstitutionEvent never themselves increment score.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from football_engine.core.enums import NonSplittingEventType


class GoalEvent(BaseModel):
    """
    A raw goal, before player attribution. Team-level only.

    Architecture reference: Section J/K.3 locked path:
        Goal Count → Shot Count → Player Attribution
    (never Shots → Goal Count → λ).
    """

    model_config = ConfigDict(frozen=True)

    minute: int = Field(..., ge=0)
    team_id: str
    is_home_team: bool


class AttributedGoalEvent(BaseModel):
    """
    Module 9 (Section J) output — a GoalEvent with scorer/assist/xG_credit
    attached. Section R.1 contract: CAN_CREATE_GOAL=NO, CAN_CHANGE_λ=NO.
    """

    model_config = ConfigDict(frozen=True)

    minute: int = Field(..., ge=0)
    team_id: str
    is_home_team: bool
    scorer_player_id: str
    assist_player_id: str | None = None
    xg_credit: float = Field(..., ge=0, description="Section R.5 — display-only, no effect on λ")


class CardEvent(BaseModel):
    """
    Yellow or red card. Red cards are also segment-splitting (tracked via
    SplittingEventType at the orchestrator level, Section 6/N.10) — this
    model just carries the observed fact.
    """

    model_config = ConfigDict(frozen=True)

    minute: int = Field(..., ge=0)
    team_id: str
    is_home_team: bool
    player_id: str
    is_red: bool = Field(..., description="False = yellow, True = red (Section Q.5/Q.7)")


class ShotEvent(BaseModel):
    """
    Section Q.2/Q.3 — derived from goal count, never the other way around.

    `is_goal=True` shots are the same shots already counted in the match's
    goal tally; `is_goal=False` shots are the Poisson-distributed misses.
    `on_target` distinguishes saved shots from off-target misses (Q.4).
    """

    model_config = ConfigDict(frozen=True)

    minute: int = Field(..., ge=0)
    team_id: str
    is_home_team: bool
    is_goal: bool
    on_target: bool
    xg: float = Field(..., ge=0, description="Section Q.3 — V1: uniform per-shot xG")


class SaveEvent(BaseModel):
    """Section Q.4 — goalkeeper save, derived count, never affects λ."""

    model_config = ConfigDict(frozen=True)

    minute: int = Field(..., ge=0)
    team_id: str = Field(..., description="Team of the goalkeeper making the save")
    is_home_team: bool
    gk_player_id: str


class SubstitutionEvent(BaseModel):
    """
    Section Q.6 — substitutions only occur in S3/S4, max 3 per team.
    Never affects TeamDimensions in V1/V2 (Section Q.6 explicit note).
    """

    model_config = ConfigDict(frozen=True)

    minute: int = Field(..., ge=0)
    team_id: str
    is_home_team: bool
    player_out_id: str
    player_in_id: str


class MatchEvents(BaseModel):
    """
    Module 10 (Section Q) output bundle for a single sub-segment.

    Kept as one bundle (rather than four separate return values) so the
    orchestrator (Section S.7) can trivially do:
        sort(all_events, by=minute)
    across every non-splitting event type produced in this pass.
    """

    model_config = ConfigDict(frozen=True)

    shots: list[ShotEvent] = Field(default_factory=list)
    saves: list[SaveEvent] = Field(default_factory=list)
    yellow_cards: list[CardEvent] = Field(default_factory=list)
    substitutions: list[SubstitutionEvent] = Field(default_factory=list)
    # Red cards ride along here as CardEvents with is_red=True, but are
    # ALSO surfaced to the orchestrator as a splitting-event candidate
    # (Section N.10) — see match_runtime.py for how S resolves ordering.
    red_cards: list[CardEvent] = Field(default_factory=list)

    def as_event_type(self) -> dict[NonSplittingEventType, list]:
        """Convenience grouping, useful for generic "commit non-splitting
        events" orchestrator code (Section S.5)."""
        return {
            NonSplittingEventType.SHOT: self.shots,
            NonSplittingEventType.SAVE: self.saves,
            NonSplittingEventType.YELLOW_CARD: self.yellow_cards,
            NonSplittingEventType.SUBSTITUTION: self.substitutions,
        }
