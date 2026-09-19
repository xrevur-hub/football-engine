"""
Layer 3 canonical helper equations — exact implementations for the three
specification gaps L3-G1, L3-G2, L3-G3.

These are the approved helper equations referenced in the FINAL AUTHORIZATION
2026-09-08. They are separated from the core matchup engine so that their
definitions are explicit, testable, and independently replaceable if calibration
requires it.

No default/neutral values are provided here; the functions raise on invalid
inputs, matching the Layer 3 validation policy.
"""

from __future__ import annotations

from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.matchup._validation import finite_number, unit_interval
from football_engine.matchup.errors import Layer3InputError


# =============================================================================
# L3-G1: PressDisruption_M(defender → attacker)
# =============================================================================
# How much the defender's press disrupts the attacker's organized attack (M path).
# Inputs: defender's press_final, attacker's build_up_control_score (from identity/structure)
# Output: finite number, typically [0, 1] but not clamped by this function.
# Consumed by: I_press = 1 - k_p * PressDisruption_M
# Anti-double-counting: This is the ONLY route for defender press quality into M.
# PossessionShare already uses defender.press_final; PressDisruption_M is a
# separate construct and MUST NOT simply reuse the same value.
# =============================================================================


def press_disruption_m(
    defender_press_final: float,
    attacker_build_up_control_score: float,
) -> float:
    """
    PressDisruption_M(defender → attacker).

    Defender's press disrupts attacker's build-up. Higher defender press increases
    disruption; higher attacker build-up control mitigates it.

    Formula:
        PressDisruption_M = defender_press_final * (1 - attacker_build_up_control_score)

    This captures:
    - A high press (press_final → 1) against poor build-up (build_up → 0) = max disruption
    - A high press against excellent build-up (build_up → 1) = low disruption
    - A low press (press_final → 0) = low disruption regardless of build-up

    Both inputs are unit-interval [0,1] tactical/structural fields.
    Output is in [0,1], finite.
    """
    press = unit_interval("defender.press_final", defender_press_final)
    build_up = unit_interval("attacker.build_up_control_score", attacker_build_up_control_score)

    return finite_number("PressDisruption_M", press * (1.0 - build_up))


# =============================================================================
# L3-G2: WidthMismatch(attacker, defender)
# =============================================================================
# Width advantage/disadvantage for the attacker against the defender.
# Inputs: attacker's width_final (tactical), defender's defensive_cover_feature (structural)
# Output: signed finite number (can be negative = attacker narrower than defender cover)
# Consumed by: I_width = 1 + k_w * WidthMismatch
# Anti-double-counting: This is the ONLY route for width mismatch into M.
# Attacker's width_final already feeds PossessionShare indirectly via build_up_control_score
# (which comes from StructuralFeatures.build_up_structure_feature). WidthMismatch is
# a distinct construct: tactical width vs structural defensive cover.
# =============================================================================


def width_mismatch(
    attacker_width_final: float,
    defender_defensive_cover_feature: float,
) -> float:
    """
    WidthMismatch(attacker, defender).

    Attacker's tactical width vs defender's structural defensive cover.
    Positive = attacker is wider than defender's cover (exposes flanks).
    Negative = attacker is narrower than defender's cover (congested center).

    Formula:
        WidthMismatch = attacker_width_final - defender_defensive_cover_feature

    Both inputs are unit-interval [0,1] fields.
    Output is in [-1, 1], finite (not clamped).
    """
    width = unit_interval("attacker.width_final", attacker_width_final)
    cover = unit_interval("defender.defensive_cover_feature", defender_defensive_cover_feature)

    return finite_number("WidthMismatch", width - cover)


# =============================================================================
# L3-G3: PressTransitionOpportunity_T(defender → attacker)
# =============================================================================
# Transition opportunity created by defender's press for the attacker.
# This is DIFFERENT from PressDisruption_M:
# - PressDisruption_M: how press disrupts organized attack (M path)
# - PressTransitionOpportunity_T: how press creates counter-attack chances (T path)
#
# Inputs: defender's press_final, defender's line_final, attacker's transition_tendency_final
# Output: finite number, typically [0, 1]
# Consumed by: T = tendency * pace * SpaceBehindDefense + PressTransitionOpportunity_T * tendency * k_t2
# Anti-double-counting: This is the ONLY route for defender press into T.
# It MUST NOT reuse PressDisruption_M. A high press creates BOTH disruption to M
# AND transition opportunities for T — they are separate phenomena.
# =============================================================================


def press_transition_opportunity_t(
    defender_press_final: float,
    defender_line_final: float,
    attacker_transition_tendency_final: float,
) -> float:
    """
    PressTransitionOpportunity_T(defender → attacker).

    Defender's high press combined with high line creates space behind for transition.
    Only relevant if attacker has transition tendency.

    Formula:
        PressTransitionOpportunity_T = defender_press_final * defender_line_final * attacker_transition_tendency_final

    This captures:
    - High press (press_final → 1) + high line (line_final → 1) + attacker likes transition (tendency → 1) = max opportunity
    - Low press or deep line or no transition tendency = low opportunity

    All three inputs are unit-interval [0,1] tactical fields.
    Output is in [0,1], finite.
    """
    press = unit_interval("defender.press_final", defender_press_final)
    line = unit_interval("defender.line_final", defender_line_final)
    tendency = unit_interval("attacker.transition_tendency_final", attacker_transition_tendency_final)

    return finite_number("PressTransitionOpportunity_T", press * line * tendency)


# =============================================================================
# Convenience: compute all three helpers for one direction
# =============================================================================


def compute_directional_helpers(
    attacker_tactical: TacticalProfile,
    defender_tactical: TacticalProfile,
    attacker_structural: StructuralFeatures,
) -> tuple[float, float, float]:
    """
    Compute all three directional helpers for A → B direction.

    Returns:
        (press_disruption_m, width_mismatch, press_transition_opportunity_t)
        where:
        - press_disruption_m = PressDisruption_M(B → A)
        - width_mismatch = WidthMismatch(A, B)
        - press_transition_opportunity_t = PressTransitionOpportunity_T(B → A)
    """
    pdm = press_disruption_m(
        defender_press_final=defender_tactical.press_final,
        attacker_build_up_control_score=attacker_tactical.build_up_control_score,
    )
    wm = width_mismatch(
        attacker_width_final=attacker_tactical.width_final,
        defender_defensive_cover_feature=defender_tactical.defensive_cover_feature,
    )
    ptot = press_transition_opportunity_t(
        defender_press_final=defender_tactical.press_final,
        defender_line_final=defender_tactical.line_final,
        attacker_transition_tendency_final=attacker_tactical.transition_tendency_final,
    )
    return pdm, wm, ptot