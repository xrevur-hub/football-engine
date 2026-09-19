"""
SegmentOutcome — Module 8 output. THE BOUNDARY object.

Architecture reference: Section O.2 (Module 8 contract), Section J/K.1,
Section O.4.

Contract:
    INPUT:              LambdaPair + segment_duration + rng
    OUTPUT:             SegmentOutcome{goals_home, goals_away, goal_minute}
    CAN_CHANGE_λ?       NO   ← the boundary
    CAN_CHANGE_STATE?   YES (via goals)
    RANDOMNESS?         YES  ← the only primary randomness source

Everything downstream of this object (Modules 9-11 / Sections J, K, R,
State Updater) is post-sample and, per the golden rule in O.1, can never
write back into λ:

    "اگر CAN_CHANGE_λ = YES، ماژول نمی‌تواند post-sample باشد.
     اگر post-sample است، CAN_CHANGE_λ = NO."
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SegmentOutcome(BaseModel):
    """
    Result of sampling one (sub-)segment from the probability model.

    `goal_minute` is the minute of the *first* goal in this outcome, if
    any — required so the orchestrator (Section S) can split the segment
    at the correct point. When both `goals_home` and `goals_away` are 0,
    `goal_minute` must be None (no splitting event occurred).

    Architecture note (Section N.3 implementation note): determining the
    precise minute of a goal requires an auxiliary Exponential-distribution
    draw layered on top of the (x, y) scoreline sample — this model just
    carries the *result* of that process, not the process itself.
    """

    model_config = ConfigDict(frozen=True)

    goals_home: int = Field(..., ge=0)
    goals_away: int = Field(..., ge=0)
    goal_minute: int | None = Field(
        None, description="Minute of the first goal in this outcome, if any"
    )
    used_dixon_coles: bool = Field(
        ..., description="True if sampled via DC (duration >= 15min), False if independent Poisson"
    )

    @model_validator(mode="after")
    def _goal_minute_consistency(self) -> "SegmentOutcome":
        has_goal = (self.goals_home + self.goals_away) > 0
        if has_goal and self.goal_minute is None:
            raise ValueError("goal_minute must be set when goals were scored in this outcome")
        if not has_goal and self.goal_minute is not None:
            raise ValueError("goal_minute must be None when no goals were scored")
        return self
