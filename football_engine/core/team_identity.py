"""
TeamIdentity — Module 3 output.

Architecture reference: Section 3 (identity vars in TacticalProfile
context), Section 33 (identity_priors in TeamSeason schema), Section O.2
(Module 3 contract).

Contract:
    INPUT:              PlayerSeasons + StructuralFeatures + HistoricalPrior
    OUTPUT:             TeamIdentity
    IMMUTABLE?          YES
    RUNTIME?            NO
    CAN_CHANGE_λ?       INDIRECT
    CAN_CHANGE_STATE?   NO
    RANDOMNESS?         NO

Anti-double-counting note (Section 46, rule 6):
    "Form با Team Identity یکی نشود." — TeamIdentity is the *static*
    per-match identity; Form (Section 18) is a separate, runtime,
    tournament-only signal layered on top of λ, not stored here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TeamIdentity(BaseModel):
    """
    Static tactical identity for one TeamSeason in one match context.

    These feed TacticalProfile generation (Module 5) as the pre-state
    baseline; TacticalProfile then applies State Adjustment on top of them
    at runtime (Section 7).
    """

    model_config = ConfigDict(frozen=True)

    possession_tendency: float = Field(..., ge=0, le=1)
    press_tendency: float = Field(..., ge=0, le=1)
    transition_tendency: float = Field(..., ge=0, le=1)
    tempo: float = Field(..., ge=0, le=1)
    risk_tolerance: float = Field(..., ge=0, le=1)
    compactness: float = Field(..., ge=0, le=1)

    # Feed directly into TacticalProfile.*_final fields (Section 7) absent
    # any state adjustment.
    build_up_control_score: float = Field(..., ge=0, le=1)
    attack_pace_factor: float = Field(..., ge=0, le=1)
