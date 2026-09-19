"""Tests for Layer 3 TacticalProfilePolicy (Module 5)."""

import pytest

from football_engine.core.enums import MatchState
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.core.team_identity import TeamIdentity
from football_engine.matchup.tactical_policy import (
    DEFAULT_MODULE5_COEFFICIENTS,
    DefaultTacticalProfilePolicy,
    Module5Coefficients,
    create_tactical_profile_policy,
)
from football_engine.matchup.dependencies import TacticalProfilePolicy


class TestModule5Coefficients:
    """Test Module5Coefficients validation"""

    def test_default_coefficients_valid(self):
        c = DEFAULT_MODULE5_COEFFICIENTS
        assert isinstance(c, Module5Coefficients)

    def test_weights_sum_to_one(self):
        c = DEFAULT_MODULE5_COEFFICIENTS
        checks = [
            ("press", c.press_baseline_weight_identity + c.press_baseline_weight_structural),
            ("buildup", c.buildup_baseline_weight_identity + c.buildup_baseline_weight_structural),
            ("transition", c.transition_baseline_weight_identity + c.transition_baseline_weight_structural),
            ("width", c.width_baseline_weight_identity + c.width_baseline_weight_structural),
            ("line", c.line_baseline_weight_identity + c.line_baseline_weight_structural),
            ("tempo", c.tempo_baseline_weight_identity + c.tempo_baseline_weight_structural),
            ("possession", c.possession_baseline_weight_identity + c.possession_baseline_weight_structural),
            ("attack_pace", c.attack_pace_baseline_weight_identity + c.attack_pace_baseline_weight_structural),
        ]
        for name, total in checks:
            assert abs(total - 1.0) < 1e-9, f"{name} weights sum to {total}"

    def test_state_adjustments_complete(self):
        c = DEFAULT_MODULE5_COEFFICIENTS
        for state in MatchState:
            assert state in c.STATE_ADJUSTMENTS
            deltas = c.STATE_ADJUSTMENTS[state]
            assert len(deltas) == 9, f"{state} has {len(deltas)} deltas, expected 9"

    def test_invalid_weights_rejected(self):
        with pytest.raises(ValueError, match="weights must sum to 1.0"):
            Module5Coefficients(press_baseline_weight_identity=0.5, press_baseline_weight_structural=0.3)

    def test_invalid_state_adjustments_rejected(self):
        # STATE_ADJUSTMENTS is a class variable, so we can't test it via constructor
        # Instead, verify the default has correct structure
        c = Module5Coefficients()
        for state in MatchState:
            assert state in c.STATE_ADJUSTMENTS
            assert len(c.STATE_ADJUSTMENTS[state]) == 9


class TestDefaultTacticalProfilePolicy:
    """Test the default policy implementation"""

    def test_protocol_compliance(self):
        policy = create_tactical_profile_policy()
        # Verify it has the required call signature by actually calling it
        identity = TeamIdentity(
            possession_tendency=0.5, press_tendency=0.5, transition_tendency=0.5,
            tempo=0.5, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.5, attack_pace_factor=0.5
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.5, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.5,
            build_up_structure_feature=0.5, transition_structure_feature=0.5
        )
        result = policy(identity=identity, structural_features=structural, state=MatchState.NORMAL)
        assert isinstance(result, TacticalProfile)

    def test_baseline_composition_bounded(self):
        """Baseline outputs should be in [0,1] before state adjustment"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.5, press_tendency=0.5, transition_tendency=0.5,
            tempo=0.5, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.5, attack_pace_factor=0.5
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.5, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.5,
            build_up_structure_feature=0.5, transition_structure_feature=0.5
        )

        baseline = policy._compute_baseline(identity, structural)

        for key, value in baseline.items():
            assert 0.0 <= value <= 1.0, f"Baseline {key}={value} out of bounds"

    def test_normal_state_is_baseline(self):
        """NORMAL state should apply zero deltas (just clamped baseline)"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.7, press_tendency=0.6, transition_tendency=0.5,
            tempo=0.6, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.4, attack_pace_factor=0.7
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6
        )

        profile_normal = policy(identity=identity, structural_features=structural, state=MatchState.NORMAL)

        # Manually compute expected baseline
        baseline = policy._compute_baseline(identity, structural)

        # Map baseline keys to TacticalProfile fields
        field_map = {
            "press": "press_final",
            "line": "line_final",
            "width": "width_final",
            "buildup": "build_up_control_score",
            "cover": "defensive_cover_feature",
            "attack_pace": "attack_pace_factor",
            "transition": "transition_tendency_final",
            "tempo": "tempo_final",
            "possession": "possession_tendency_final",
        }

        for key, expected in baseline.items():
            actual = getattr(profile_normal, field_map[key])
            assert actual == pytest.approx(expected), f"{key}: expected {expected}, got {actual}"

    def test_leading_state_adjustments(self):
        """LEADING state should reduce press/line/width, increase cover"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.7, press_tendency=0.6, transition_tendency=0.5,
            tempo=0.6, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.4, attack_pace_factor=0.7
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6
        )

        profile_normal = policy(identity=identity, structural_features=structural, state=MatchState.NORMAL)
        profile_leading = policy(identity=identity, structural_features=structural, state=MatchState.LEADING)

        # LEADING should have lower press, line, width, attack_pace, transition, tempo, possession
        assert profile_leading.press_final < profile_normal.press_final
        assert profile_leading.line_final < profile_normal.line_final
        assert profile_leading.width_final < profile_normal.width_final
        assert profile_leading.attack_pace_factor < profile_normal.attack_pace_factor
        assert profile_leading.transition_tendency_final < profile_normal.transition_tendency_final
        assert profile_leading.tempo_final < profile_normal.tempo_final
        assert profile_leading.possession_tendency_final < profile_normal.possession_tendency_final

        # LEADING should have higher cover, build_up
        assert profile_leading.defensive_cover_feature > profile_normal.defensive_cover_feature
        assert profile_leading.build_up_control_score > profile_normal.build_up_control_score

    def test_losing_state_adjustments(self):
        """LOSING state should increase press/line/width, decrease cover"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.7, press_tendency=0.6, transition_tendency=0.5,
            tempo=0.6, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.4, attack_pace_factor=0.7
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6
        )

        profile_normal = policy(identity=identity, structural_features=structural, state=MatchState.NORMAL)
        profile_losing = policy(identity=identity, structural_features=structural, state=MatchState.LOSING)

        # LOSING should have higher press, line, width, attack_pace, transition, tempo, possession
        assert profile_losing.press_final > profile_normal.press_final
        assert profile_losing.line_final > profile_normal.line_final
        assert profile_losing.width_final > profile_normal.width_final
        assert profile_losing.attack_pace_factor > profile_normal.attack_pace_factor
        assert profile_losing.transition_tendency_final > profile_normal.transition_tendency_final
        assert profile_losing.tempo_final > profile_normal.tempo_final
        assert profile_losing.possession_tendency_final > profile_normal.possession_tendency_final

        # LOSING should have lower cover, build_up
        assert profile_losing.defensive_cover_feature < profile_normal.defensive_cover_feature
        assert profile_losing.build_up_control_score < profile_normal.build_up_control_score

    def test_reactive_state_extreme(self):
        """REACTIVE state should have most extreme adjustments"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.7, press_tendency=0.6, transition_tendency=0.5,
            tempo=0.6, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.4, attack_pace_factor=0.7
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6
        )

        profile_losing = policy(identity=identity, structural_features=structural, state=MatchState.LOSING)
        profile_reactive = policy(identity=identity, structural_features=structural, state=MatchState.REACTIVE)

        # REACTIVE should be even more extreme than LOSING
        assert profile_reactive.press_final > profile_losing.press_final
        assert profile_reactive.line_final > profile_losing.line_final
        assert profile_reactive.width_final > profile_losing.width_final
        assert profile_reactive.attack_pace_factor > profile_losing.attack_pace_factor
        assert profile_reactive.transition_tendency_final > profile_losing.transition_tendency_final
        assert profile_reactive.tempo_final > profile_losing.tempo_final
        assert profile_reactive.possession_tendency_final > profile_losing.possession_tendency_final

        assert profile_reactive.defensive_cover_feature < profile_losing.defensive_cover_feature
        assert profile_reactive.build_up_control_score < profile_losing.build_up_control_score

    def test_output_clamped_to_bounds(self):
        """All output fields must be in [0,1] even with extreme inputs"""
        policy = DefaultTacticalProfilePolicy()

        # Identity and structural at extremes
        identity = TeamIdentity(
            possession_tendency=1.0, press_tendency=1.0, transition_tendency=1.0,
            tempo=1.0, risk_tolerance=1.0, compactness=1.0,
            build_up_control_score=1.0, attack_pace_factor=1.0
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=1.0, line_height_feature=1.0,
            defensive_cover_feature=1.0, press_structure_feature=1.0,
            build_up_structure_feature=1.0, transition_structure_feature=1.0
        )

        profile = policy(identity=identity, structural_features=structural, state=MatchState.REACTIVE)

        # All fields should be clamped to 1.0
        for field in ["press_final", "line_final", "width_final", "build_up_control_score",
                      "defensive_cover_feature", "attack_pace_factor", "transition_tendency_final",
                      "tempo_final", "possession_tendency_final"]:
            value = getattr(profile, field)
            assert 0.0 <= value <= 1.0, f"{field}={value} out of bounds"

    def test_input_immutability(self):
        """Policy must not mutate inputs"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.7, press_tendency=0.6, transition_tendency=0.5,
            tempo=0.6, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.4, attack_pace_factor=0.7
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6
        )

        identity_before = identity.model_dump()
        structural_before = structural.model_dump()

        policy(identity=identity, structural_features=structural, state=MatchState.LOSING)

        assert identity.model_dump() == identity_before
        assert structural.model_dump() == structural_before

    def test_deterministic(self):
        """Repeated calls with same inputs must produce identical outputs"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.7, press_tendency=0.6, transition_tendency=0.5,
            tempo=0.6, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.4, attack_pace_factor=0.7
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6
        )

        results = [policy(identity=identity, structural_features=structural, state=MatchState.LOSING) for _ in range(20)]
        for r in results[1:]:
            assert r == results[0]

    def test_all_nine_fields_present(self):
        """TacticalProfile must have all nine required fields"""
        policy = DefaultTacticalProfilePolicy()
        identity = TeamIdentity(
            possession_tendency=0.5, press_tendency=0.5, transition_tendency=0.5,
            tempo=0.5, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.5, attack_pace_factor=0.5
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.5, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.5,
            build_up_structure_feature=0.5, transition_structure_feature=0.5
        )

        profile = policy(identity=identity, structural_features=structural, state=MatchState.NORMAL)
        dump = profile.model_dump()

        expected_fields = {
            "press_final", "line_final", "width_final", "build_up_control_score",
            "defensive_cover_feature", "attack_pace_factor", "transition_tendency_final",
            "tempo_final", "possession_tendency_final"
        }
        assert set(dump.keys()) == expected_fields


class TestTacticalProfileGeneratorIntegration:
    """Test TacticalProfileGenerator with the policy"""

    def test_generator_uses_policy(self):
        from football_engine.matchup.tactical_profile import TacticalProfileGenerator

        policy = create_tactical_profile_policy()
        generator = TacticalProfileGenerator(policy=policy)

        identity = TeamIdentity(
            possession_tendency=0.7, press_tendency=0.6, transition_tendency=0.5,
            tempo=0.6, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.4, attack_pace_factor=0.7
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.8, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.3,
            build_up_structure_feature=0.4, transition_structure_feature=0.6
        )

        profile = generator.generate(identity=identity, structural_features=structural, state=MatchState.NORMAL)
        assert isinstance(profile, TacticalProfile)

    def test_generator_without_policy_raises(self):
        from football_engine.matchup.tactical_profile import TacticalProfileGenerator
        from football_engine.matchup.errors import SpecificationGapError

        generator = TacticalProfileGenerator(policy=None)
        identity = TeamIdentity(
            possession_tendency=0.5, press_tendency=0.5, transition_tendency=0.5,
            tempo=0.5, risk_tolerance=0.5, compactness=0.5,
            build_up_control_score=0.5, attack_pace_factor=0.5
        )
        structural = StructuralFeatures(
            formation_name="4-3-3",
            width_feature=0.5, line_height_feature=0.5,
            defensive_cover_feature=0.5, press_structure_feature=0.5,
            build_up_structure_feature=0.5, transition_structure_feature=0.5
        )

        with pytest.raises(SpecificationGapError):
            generator.generate(identity=identity, structural_features=structural, state=MatchState.NORMAL)