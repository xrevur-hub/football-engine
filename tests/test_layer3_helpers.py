"""Tests for Layer 3 helper equations (L3-G1, L3-G2, L3-G3)."""

import pytest

from football_engine.matchup.helpers import (
    press_disruption_m,
    width_mismatch,
    press_transition_opportunity_t,
    compute_directional_helpers,
)
from football_engine.matchup.errors import Layer3InputError
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures


class TestPressDisruptionM:
    """L3-G1: PressDisruption_M(defender → attacker)"""

    def test_exact_formula(self):
        # High press, low build-up → high disruption
        assert press_disruption_m(1.0, 0.0) == 1.0
        # High press, high build-up → low disruption
        assert press_disruption_m(1.0, 1.0) == 0.0
        # Low press, any build-up → low disruption
        assert press_disruption_m(0.0, 0.0) == 0.0
        assert press_disruption_m(0.0, 1.0) == 0.0
        # Mid values
        assert press_disruption_m(0.8, 0.3) == pytest.approx(0.8 * 0.7)

    def test_bounds(self):
        for press in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for build_up in [0.0, 0.25, 0.5, 0.75, 1.0]:
                result = press_disruption_m(press, build_up)
                assert 0.0 <= result <= 1.0

    def test_invalid_press_rejected(self):
        with pytest.raises(Layer3InputError):
            press_disruption_m(-0.1, 0.5)
        with pytest.raises(Layer3InputError):
            press_disruption_m(1.1, 0.5)
        with pytest.raises(Layer3InputError):
            press_disruption_m(float("nan"), 0.5)
        with pytest.raises(Layer3InputError):
            press_disruption_m(float("inf"), 0.5)

    def test_invalid_build_up_rejected(self):
        with pytest.raises(Layer3InputError):
            press_disruption_m(0.5, -0.1)
        with pytest.raises(Layer3InputError):
            press_disruption_m(0.5, 1.1)
        with pytest.raises(Layer3InputError):
            press_disruption_m(0.5, float("nan"))


class TestWidthMismatch:
    """L3-G2: WidthMismatch(attacker, defender)"""

    def test_exact_formula(self):
        # Attacker wider than defender cover → positive
        assert width_mismatch(1.0, 0.0) == 1.0
        # Attacker narrower than defender cover → negative
        assert width_mismatch(0.0, 1.0) == -1.0
        # Equal → zero
        assert width_mismatch(0.5, 0.5) == 0.0
        # Mid values
        assert width_mismatch(0.8, 0.3) == pytest.approx(0.5)
        assert width_mismatch(0.3, 0.8) == pytest.approx(-0.5)

    def test_bounds(self):
        for width in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for cover in [0.0, 0.25, 0.5, 0.75, 1.0]:
                result = width_mismatch(width, cover)
                assert -1.0 <= result <= 1.0

    def test_invalid_width_rejected(self):
        with pytest.raises(Layer3InputError):
            width_mismatch(-0.1, 0.5)
        with pytest.raises(Layer3InputError):
            width_mismatch(1.1, 0.5)

    def test_invalid_cover_rejected(self):
        with pytest.raises(Layer3InputError):
            width_mismatch(0.5, -0.1)
        with pytest.raises(Layer3InputError):
            width_mismatch(0.5, 1.1)


class TestPressTransitionOpportunityT:
    """L3-G3: PressTransitionOpportunity_T(defender → attacker)"""

    def test_exact_formula(self):
        # All high → max opportunity
        assert press_transition_opportunity_t(1.0, 1.0, 1.0) == 1.0
        # Any zero → zero
        assert press_transition_opportunity_t(0.0, 1.0, 1.0) == 0.0
        assert press_transition_opportunity_t(1.0, 0.0, 1.0) == 0.0
        assert press_transition_opportunity_t(1.0, 1.0, 0.0) == 0.0
        # Mid values
        assert press_transition_opportunity_t(0.8, 0.7, 0.6) == pytest.approx(0.8 * 0.7 * 0.6)

    def test_bounds(self):
        for press in [0.0, 0.25, 0.5, 0.75, 1.0]:
            for line in [0.0, 0.25, 0.5, 0.75, 1.0]:
                for tendency in [0.0, 0.25, 0.5, 0.75, 1.0]:
                    result = press_transition_opportunity_t(press, line, tendency)
                    assert 0.0 <= result <= 1.0

    def test_invalid_inputs_rejected(self):
        with pytest.raises(Layer3InputError):
            press_transition_opportunity_t(-0.1, 0.5, 0.5)
        with pytest.raises(Layer3InputError):
            press_transition_opportunity_t(0.5, 1.1, 0.5)
        with pytest.raises(Layer3InputError):
            press_transition_opportunity_t(0.5, 0.5, 1.1)


class TestComputeDirectionalHelpers:
    """Integration test: compute all three helpers from tactical/structural objects"""

    def test_full_computation(self):
        attacker_tactical = TacticalProfile(
            press_final=0.6,
            line_final=0.7,
            width_final=0.8,
            build_up_control_score=0.4,
            defensive_cover_feature=0.5,
            attack_pace_factor=0.7,
            transition_tendency_final=0.5,
            tempo_final=0.6,
            possession_tendency_final=0.55,
        )
        defender_tactical = TacticalProfile(
            press_final=0.8,
            line_final=0.75,
            width_final=0.6,
            build_up_control_score=0.3,
            defensive_cover_feature=0.5,
            attack_pace_factor=0.6,
            transition_tendency_final=0.4,
            tempo_final=0.55,
            possession_tendency_final=0.45,
        )
        attacker_structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8,
            line_height_feature=0.5,
            defensive_cover_feature=0.5,
            press_structure_feature=0.3,
            build_up_structure_feature=0.4,
            transition_structure_feature=0.6,
        )

        pdm, wm, ptot = compute_directional_helpers(
            attacker_tactical, defender_tactical, attacker_structural
        )

        # pdm = PressDisruption_M(B -> A) = defender.press_final * (1 - attacker.build_up_control_score)
        assert pdm == pytest.approx(0.8 * (1.0 - 0.4))
        # wm = WidthMismatch(A, B) = attacker.width_final - defender.defensive_cover_feature
        assert wm == pytest.approx(0.8 - 0.5)
        # ptot = PressTransitionOpportunity_T(B -> A) = defender.press_final * defender.line_final * attacker.transition_tendency_final
        assert ptot == pytest.approx(0.8 * 0.75 * 0.5)

    def test_immutability_of_inputs(self):
        attacker_tactical = TacticalProfile(
            press_final=0.6, line_final=0.7, width_final=0.8,
            build_up_control_score=0.4, defensive_cover_feature=0.5,
            attack_pace_factor=0.7, transition_tendency_final=0.5,
            tempo_final=0.6, possession_tendency_final=0.55,
        )
        defender_tactical = TacticalProfile(
            press_final=0.8, line_final=0.75, width_final=0.6,
            build_up_control_score=0.3, defensive_cover_feature=0.5,
            attack_pace_factor=0.6, transition_tendency_final=0.4,
            tempo_final=0.55, possession_tendency_final=0.45,
        )
        attacker_structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6,
        )

        before_attacker = attacker_tactical.model_dump()
        before_defender = defender_tactical.model_dump()
        before_structural = attacker_structural.model_dump()

        compute_directional_helpers(attacker_tactical, defender_tactical, attacker_structural)

        assert attacker_tactical.model_dump() == before_attacker
        assert defender_tactical.model_dump() == before_defender
        assert attacker_structural.model_dump() == before_structural


class TestAntiDoubleCounting:
    """Verify the helpers are distinct and don't overlap"""

    def test_press_disruption_vs_transition_opportunity(self):
        """PressDisruption_M and PressTransitionOpportunity_T must be different constructs"""
        # Same defender press, but different other inputs
        pdm = press_disruption_m(defender_press_final=0.8, attacker_build_up_control_score=0.2)
        ptot = press_transition_opportunity_t(
            defender_press_final=0.8,
            defender_line_final=0.7,
            attacker_transition_tendency_final=0.6
        )

        # They should NOT be equal (different formulas)
        assert pdm != ptot

    def test_width_mismatch_uses_structural_cover_not_tactical_press(self):
        """WidthMismatch uses defender's defensive_cover_feature, not press_final"""
        # If it used press_final, it would overlap with PressDisruption_M
        # This test documents the intentional separation
        wm = width_mismatch(attacker_width_final=0.8, defender_defensive_cover_feature=0.5)
        # This is width - cover, NOT width - press
        assert wm == pytest.approx(0.3)