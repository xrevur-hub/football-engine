"""
PlayerSeason — Module 0.

Architecture reference: Section 3.1, Section O.2 (Module 0 contract).

Contract (Section O.2):
    INPUT:              raw player data (از DB)
    OUTPUT:             PlayerSeason
    IMMUTABLE?          YES
    RUNTIME?            NO
    CAN_CHANGE_λ?       INDIRECT
    CAN_CHANGE_STATE?   NO
    RANDOMNESS?         NO

A player is a season-specific snapshot: `messi_2010_11` and `messi_2018_19`
are different PlayerSeason records with different attributes, even though
they represent the same human (Section 3.1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from football_engine.core.enums import PlayerRole


class PlayerSeason(BaseModel):
    """
    Immutable, season-specific player snapshot.

    All *_ability / *_tendency fields are expected on a normalized 0-100
    scale unless noted otherwise, consistent with the worked example in
    Section 15 (Attack=85, Creation=95, ... on the same scale as the
    78/78/78/78 global averages).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description='e.g. "messi_2010_11"')
    name: str
    season: str = Field(..., description='e.g. "2010/11"')
    role: PlayerRole

    # --- Core dimension-feeding abilities (Section 4) -----------------------
    attack_ability: float = Field(..., ge=0, le=100)
    creation_ability: float = Field(..., ge=0, le=100)
    defense_ability: float = Field(..., ge=0, le=100)
    gk_ability: float = Field(0.0, ge=0, le=100, description="Nonzero only for GK role")

    # --- Identity/tendency inputs (Section 3, Section 33 identity_priors) --
    shot_tendency: float = Field(0.5, ge=0, le=1)
    press_tendency: float = Field(0.5, ge=0, le=1)
    transition_tendency: float = Field(0.5, ge=0, le=1)
    pace: float = Field(0.5, ge=0, le=1)

    # --- Discipline / attribution inputs (Section Q.5, R.7) -----------------
    discipline_score: float = Field(
        0.5, ge=0, le=1, description="Higher = more disciplined; Q.5 selects with inverse weight"
    )
    impact_score: float = Field(
        0.5, ge=0, le=1, description="Used for substitution sub_out weighting (Section Q.6)"
    )
