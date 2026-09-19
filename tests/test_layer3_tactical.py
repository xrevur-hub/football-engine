"""Module 5 contract tests using explicit final-profile fixtures, not policies
claimed to be canonical. E-12 migration rejects the removed legacy field explicitly.
"""

import pytest
from pydantic import ValidationError

from football_engine.core.enums import MatchState
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.matchup.errors import Layer3InputError, SpecificationGapError
from football_engine.matchup.tactical_profile import TacticalProfileGenerator
from tests.layer3_helpers import make_identity, make_structure, make_tactical


class TestLayer3TacticalBoundary:
    def test_no_default_state_equation_for_any_match_state(self):
        generator = TacticalProfileGenerator()
        for state in MatchState:
            with pytest.raises(SpecificationGapError, match="MatchState -> TacticalProfile"):
                generator.generate(make_identity(), make_structure(), state)

    def test_missing_baseline_composition_is_explicit(self):
        with pytest.raises(SpecificationGapError, match="P/U/Ts ownership"):
            TacticalProfileGenerator().generate(make_identity(), make_structure(), MatchState.NORMAL)

    def test_policy_receives_identity_structure_and_state_separately(self):
        identity = make_identity()
        structure = make_structure()
        expected = make_tactical()
        received = []  # test-only call recorder, never a production mutation

        def explicit_fixture_policy(*, identity, structural_features, state):
            received.append((identity, structural_features, state))
            return expected

        actual = TacticalProfileGenerator(explicit_fixture_policy).generate(identity, structure, MatchState.LEADING)
        assert isinstance(actual, TacticalProfile)
        assert actual == expected
        assert received == [(identity, structure, MatchState.LEADING)]
        assert received[0][0] is identity
        assert received[0][1] is structure

    def test_all_nine_profile_fields_are_retained(self):
        explicit = make_tactical()
        generator = TacticalProfileGenerator(lambda **inputs: explicit)
        actual = generator.generate(make_identity(), make_structure(), MatchState.NORMAL)
        assert actual.model_dump() == explicit.model_dump()
        assert set(actual.model_dump()) == {
            "press_final", "line_final", "width_final", "build_up_control_score",
            "defensive_cover_feature", "attack_pace_factor", "transition_tendency_final",
            "tempo_final", "possession_tendency_final",
        }

    def test_explicit_fixture_profiles_support_each_state_without_inferred_adjustments(self):
        # These arbitrary profiles test dispatch only. NOT architecture equations.
        fixtures = {
            MatchState.NORMAL: make_tactical(tempo_final=0.11),
            MatchState.LEADING: make_tactical(tempo_final=0.22),
            MatchState.LOSING: make_tactical(tempo_final=0.33),
            MatchState.REACTIVE: make_tactical(tempo_final=0.44),
        }
        generator = TacticalProfileGenerator(lambda **inputs: fixtures[inputs["state"]])
        for state, expected in fixtures.items():
            assert generator.generate(make_identity(), make_structure(), state) == expected

    def test_wrong_policy_return_type_rejected(self):
        generator = TacticalProfileGenerator(lambda **inputs: {})
        with pytest.raises(Layer3InputError, match="must return a TacticalProfile"):
            generator.generate(make_identity(), make_structure(), MatchState.NORMAL)

    def test_policy_output_is_validated_even_after_model_construct(self):
        invalid = TacticalProfile.model_construct(**{**make_tactical().model_dump(), "line_final": 9.0})
        with pytest.raises(ValidationError):
            TacticalProfileGenerator(lambda **inputs: invalid).generate(make_identity(), make_structure(), MatchState.NORMAL)

    def test_invalid_boundary_input_types_rejected(self):
        identity = make_identity()
        structure = make_structure()
        generator = TacticalProfileGenerator(lambda **inputs: make_tactical())
        for args in (({}, structure, MatchState.NORMAL), (identity, {}, MatchState.NORMAL), (identity, structure, "NORMAL")):
            with pytest.raises(Layer3InputError):
                generator.generate(*args)

    def test_input_immutability_and_deterministic_repetition(self):
        identity = make_identity()
        structure = make_structure()
        original = [identity.model_dump(), structure.model_dump()]
        explicit = make_tactical()
        generator = TacticalProfileGenerator(lambda **inputs: explicit)
        for _ in range(20):
            assert generator.generate(identity, structure, MatchState.NORMAL) == explicit
        assert [identity.model_dump(), structure.model_dump()] == original

    def test_legacy_type_rejected_and_name_is_only_metadata(self):
        # Explicit breaking-contract migration, not silently ignored metadata.
        with pytest.raises(ValidationError, match="formation_type"):
            make_structure(formation_type="TYPE_A")
        explicit = make_tactical()
        generator = TacticalProfileGenerator(lambda **inputs: explicit)
        for name in ("changed_arbitrary_name", "another_descriptive_name"):
            structure = make_structure(formation_name=name)
            assert generator.generate(make_identity(), structure, MatchState.NORMAL) == explicit

    def test_identity_schema_is_not_overloaded_with_structural_fields(self):
        assert set(make_identity().model_dump()) == {
            "possession_tendency", "press_tendency", "transition_tendency", "tempo",
            "risk_tolerance", "compactness", "build_up_control_score", "attack_pace_factor",
        }
