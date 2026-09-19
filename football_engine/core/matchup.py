"""
MatchupResult (Module 6) and LambdaPair (Module 7).

Architecture reference: Section 8 (Matchup Engine I/O), Section 19
(Final λ), Section O.2 (Module 6/7 contracts).

Module 6 contract:
    INPUT:              TeamDimensions(A,B) + TacticalProfile(A,B) + GlobalAnchors
    OUTPUT:             MatchupResult{M_a_to_b, M_b_to_a, T_a_to_b, T_b_to_a}
    IMMUTABLE?          NO (per-segment)
    CAN_CHANGE_λ?       YES
    RANDOMNESS?         NO

Module 7 contract:
    INPUT:              MatchupResult + TeamRuntimeState(home_flag, form_factor,
                        red_card_modifier) + Constants
    OUTPUT:             LambdaPair{lambda_home_90, lambda_away_90}
    IMMUTABLE?          NO (per-segment)
    CAN_CHANGE_λ?       YES
    RANDOMNESS?         NO

Key structural rule preserved here (Section 8.2 principle):
    "Matchup Engine نباید یک Generic Team Strength Score جدید بسازد."
MatchupResult only ever carries the two independent M/T paths — never a
single collapsed strength score.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MatchupResult(BaseModel):
    """
    Module 6 output. Both directions (A→B and B→A) are computed and
    stored together since a single segment's λ_home/λ_away both derive
    from the same matchup context.
    """

    model_config = ConfigDict(frozen=True)

    m_home_to_away: float = Field(..., ge=0, description="M_A→B — organized attack threat, home perspective")
    m_away_to_home: float = Field(..., ge=0, description="M_B→A — organized attack threat, away perspective")
    t_home_to_away: float = Field(..., ge=0, description="T_A→B — transition threat, home perspective")
    t_away_to_home: float = Field(..., ge=0, description="T_B→A — transition threat, away perspective")


class LambdaPair(BaseModel):
    """
    Module 7 output — final 90-minute-equivalent goal rates for the
    current sub-segment's tactical context, BEFORE duration scaling
    (Section 26.1 applies duration scaling downstream, in the sampler).

    Section 20 (Randomness): "Randomness اینجا ضریب جداگانه ندارد." — no
    noise field belongs here in V1; V2's optional noise layer (lambda_noisy)
    is applied at the sampling call site, not stored on this object.
    """

    model_config = ConfigDict(frozen=True)

    lambda_home_90: float = Field(..., ge=0)
    lambda_away_90: float = Field(..., ge=0)
