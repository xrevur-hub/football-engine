"""
TacticalProfile — Module 5 output.

Architecture reference: Section 7, Section O.2 (Module 5 contract).

Contract:
    INPUT:              TeamIdentity + TeamRuntimeState.state
    OUTPUT:             TacticalProfile
    IMMUTABLE?          NO (per-segment)
    RUNTIME?            YES
    CAN_CHANGE_λ?       YES
    CAN_CHANGE_STATE?   NO
    RANDOMNESS?         NO

TacticalProfile is the runtime version of a team's tactics for the
current sub-segment: TeamIdentity (static) + State Adjustment (from
MatchState) = TacticalProfile. It is recomputed every sub-segment
(Section N.4: RUNTIME state list includes "tactical_a, tactical_b (بعد
از State Adjustment)").
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TacticalProfile(BaseModel):
    """
    Per-segment runtime tactical state feeding the Matchup Engine
    (Section 7's named variables, used directly in Matchup formulas —
    e.g. I_press uses press_final, T uses line_final/defensive_cover_feature).
    """

    model_config = ConfigDict(frozen=True)

    press_final: float = Field(..., ge=0, le=1)
    line_final: float = Field(..., ge=0, le=1)
    width_final: float = Field(..., ge=0, le=1)
    build_up_control_score: float = Field(..., ge=0, le=1)
    defensive_cover_feature: float = Field(..., ge=0, le=1)
    attack_pace_factor: float = Field(..., ge=0, le=1)

    # Used by T (Transition Threat) formula (Section 14) and I_tempo
    # (Section 12.3); tracked explicitly since State Adjustment can move
    # this away from the static TeamIdentity value.
    transition_tendency_final: float = Field(..., ge=0, le=1)
    tempo_final: float = Field(..., ge=0, le=1)

    # Possession tendency after state adjustment, feeding PossessionShare
    # (Section 10). Kept distinct from the static TeamIdentity value for
    # the same reason as transition_tendency_final above.
    possession_tendency_final: float = Field(..., ge=0, le=1)
