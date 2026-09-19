"""
MatchRuntime — Section P.2.

Architecture reference: Section P.1 ("MatchRuntime = State Container,
not Prediction Engine"), Section P.2 (full schema), Section P.5 (field
ownership table).

This object holds no formulas. It is populated exclusively by external
modules (Formation Engine, Matchup Engine, λ Calculator, Sampler, J/K,
State Updater) — see match_runtime.py's sibling orchestration code in
Layer 5 for the code that actually writes into it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from football_engine.core.events import (
    CardEvent,
    AttributedGoalEvent,
    SaveEvent,
    ShotEvent,
    SubstitutionEvent,
)
from football_engine.core.matchup import LambdaPair, MatchupResult
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.rng.seeded_rng import SeededRNG


class MatchRuntime(BaseModel):
    """
    Full per-match mutable state container (Section P.2).

    Field ownership (Section P.5) — enforced by orchestration discipline
    in Layer 5, not by this schema alone:
        home/away.dims/identity/formation  -> init only, else read-only
        home/away.score                    -> State Updater only
        home/away.state                    -> State Updater only
        home/away.red_card_modifier        -> State Updater only
        tactical_home/away                 -> Tactical Profile Generator only
        matchup                            -> Matchup Engine only
        lambda                             -> λ Calculator only
        goals/cards/shots/subs             -> J and K only (append-only)
        current_minute                     -> State Updater only
        rng                                -> call-only (.next() style calls)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # --- MATCH META (immutable) ---------------------------------------------
    match_id: str
    seed: int
    is_tournament: bool
    home_team_id: str
    away_team_id: str

    # --- RNG -----------------------------------------------------------------
    rng: SeededRNG

    # --- TEAM RUNTIME STATES (mutable) ---------------------------------------
    home: TeamRuntimeState
    away: TeamRuntimeState

    # --- SEGMENT STATE (mutable, per-segment) --------------------------------
    current_minute: int = Field(0, ge=0)
    segment_id: int = Field(1, ge=1, le=4, description="1=S1, 2=S2, 3=S3, 4=S4")
    segment_start: int = Field(0, ge=0)
    segment_end: int = Field(30, ge=0)

    # --- COMPUTED CACHE (mutable, per-sub-segment) ---------------------------
    tactical_home: TacticalProfile | None = None
    tactical_away: TacticalProfile | None = None
    matchup: MatchupResult | None = None
    lambda_pair: LambdaPair | None = None

    # --- EVENT LOG (append-only) ---------------------------------------------
    goals: list[AttributedGoalEvent] = Field(default_factory=list)
    cards: list[CardEvent] = Field(default_factory=list)
    substitutions: list[SubstitutionEvent] = Field(default_factory=list)
    shots: list[ShotEvent] = Field(default_factory=list)
    saves: list[SaveEvent] = Field(default_factory=list)

    # --- FINAL OUTPUT ----------------------------------------------------------
    final_score_home: int | None = None
    final_score_away: int | None = None
    is_finished: bool = False

    @property
    def remaining(self) -> int:
        """`segment_end - current_minute` (Section P.2 `remaining` field).

        Computed rather than stored to guarantee it can never drift out of
        sync with `current_minute` / `segment_end`.
        """
        return max(0, self.segment_end - self.current_minute)
