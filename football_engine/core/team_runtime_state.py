"""
TeamRuntimeState — Module 4, Section P.3.

Architecture reference: Section O.2 (Module 4 contract), Section P.3
(field-level immutable/mutable split), Section P.5 (field ownership).

Contract (O.2):
    IMMUTABLE FIELDS:   team_id, dims, identity, formation, roster, is_home
    MUTABLE FIELDS:     score, player_count, state, form_factor,
                        red_card_modifier
    RUNTIME?            YES
    CAN_CHANGE_λ?       YES (via state → TacticalProfile)
    CAN_CHANGE_STATE?   YES
    RANDOMNESS?         NO

Note on mutability: this Pydantic model uses `validate_assignment=True`
and is NOT frozen, since it genuinely needs field-level mutation — but
Section P.5 restricts *who* may perform that mutation (State Updater
only, for the mutable fields). Layer 0 only defines the shape; enforcing
"only the State Updater writes this" is a Layer 5 (Full Simulation)
orchestration discipline, not something the type system alone can
guarantee without a heavier access-control wrapper. We call this out
explicitly rather than pretending the dataclass enforces it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from football_engine.core.enums import MatchState
from football_engine.core.formation import Formation
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.core.team_identity import TeamIdentity


class TeamRuntimeState(BaseModel):
    """Per-match, per-team mutable runtime container."""

    model_config = ConfigDict(validate_assignment=True)

    # --- IMMUTABLE for the duration of the match (Section P.3) -------------
    team_id: str
    dims: TeamDimensions
    identity: TeamIdentity
    formation: Formation
    formation_structural_features: StructuralFeatures
    roster: list[str] = Field(..., description="PlayerSeason id references, on-pitch + bench")
    is_home: bool

    # --- MUTABLE — State Updater only (Section P.5) -------------------------
    score: int = Field(0, ge=0)
    player_count: int = Field(11, ge=7, le=11)
    state: MatchState = MatchState.NORMAL
    form_factor: float = Field(1.0, description="1.0 in standalone historical matches (Section 18)")
    red_card_modifier: float = Field(1.0, description="1.0 default; 0.75 prior in V2 (Section Q.7)")

    # --- Bookkeeping needed by Q.6 (max 3 subs per team) --------------------
    substitutions_made: int = Field(0, ge=0)
    players_on_pitch: list[str] = Field(
        default_factory=list,
        description="Subset of roster currently on the pitch; used for R.7 red-card on_pitch filter",
    )


# Resolve forward reference to StructuralFeatures
TeamRuntimeState.model_rebuild()
