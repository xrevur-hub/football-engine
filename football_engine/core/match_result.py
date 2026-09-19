"""
MatchResult — Section S.10 (final schema, supersedes the draft in P.6).

Architecture reference: Section S.9 (termination invariants that a valid
MatchResult must satisfy), Section S.10.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from football_engine.core.events import AttributedGoalEvent, CardEvent, SaveEvent, ShotEvent, SubstitutionEvent
from football_engine.core.team_dimensions import TeamDimensions


class MatchResult(BaseModel):
    """
    Final, immutable output of a completed simulation (Section S.10).

    `event_log` intentionally keeps shots/cards/subs as separate typed
    lists rather than one polymorphic list — this matches MatchRuntime's
    own event-log shape (Section P.2) and avoids a discriminated-union
    tag just to satisfy a single generic "event_log" field name.
    """

    model_config = ConfigDict(frozen=True)

    match_id: str
    final_score_home: int = Field(..., ge=0)
    final_score_away: int = Field(..., ge=0)

    goal_log: list[AttributedGoalEvent] = Field(default_factory=list)
    card_log: list[CardEvent] = Field(default_factory=list)
    shot_log: list[ShotEvent] = Field(default_factory=list)
    save_log: list[SaveEvent] = Field(default_factory=list)
    substitution_log: list[SubstitutionEvent] = Field(default_factory=list)

    seed: int

    home_team_id: str
    away_team_id: str

    dims_home: TeamDimensions
    dims_away: TeamDimensions

    reproducible: bool = Field(
        True, description="False only if a non-deterministic code path was hit (should never happen)"
    )

    @model_validator(mode="after")
    def _check_goal_count_invariants(self) -> "MatchResult":
        """
        Section S.9, Invariants 3/4/17/18:
            len(goal_log_home) == final_score_home
            len(goal_log_away) == final_score_away
            "no goal may exist in goal_log without changing score, and no
             score increment may exist without a corresponding goal_log entry"
        """
        home_goals = sum(1 for g in self.goal_log if g.is_home_team)
        away_goals = sum(1 for g in self.goal_log if not g.is_home_team)
        if home_goals != self.final_score_home:
            raise ValueError(
                f"Invariant violation: home goal_log count ({home_goals}) != "
                f"final_score_home ({self.final_score_home})"
            )
        if away_goals != self.final_score_away:
            raise ValueError(
                f"Invariant violation: away goal_log count ({away_goals}) != "
                f"final_score_away ({self.final_score_away})"
            )
        return self

    @model_validator(mode="after")
    def _check_goal_minutes_non_decreasing(self) -> "MatchResult":
        """Section S.9, Invariant 7: goal minutes are non-decreasing."""
        minutes = [g.minute for g in self.goal_log]
        if minutes != sorted(minutes):
            raise ValueError("Invariant violation: goal_log minutes are not non-decreasing")
        return self
