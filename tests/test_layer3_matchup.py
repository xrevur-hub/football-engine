"""Isolated Module 6 exact-formula tests; no upstream derive() calls."""

from dataclasses import FrozenInstanceError, asdict
import math

import pytest

from football_engine.core.matchup import MatchupResult
from football_engine.core.parameters import ParameterSet
from football_engine.matchup.configuration import Layer3Coefficients
from football_engine.matchup.dependencies import DirectionalMatchupHelpers
from football_engine.matchup.errors import Layer3InputError, SpecificationGapError
from football_engine.matchup.matchup_engine import (
    MatchupEngine,
    adjusted_base,
    base_relative_strength,
    creation_factor,
    creation_realization,
    gk_factor,
    organized_attack,
    possession_share,
    press_interaction,
    sigmoid,
    space_behind_defense,
    tempo_interaction,
    transition_threat,
    width_interaction,
)
from tests.layer3_helpers import make_dimensions, make_helpers, make_tactical


class TestLayer3SpecifiedFormulae:
    def test_exact_gk_factor(self):
        defender = make_dimensions(goalkeeping=85.0)
        assert gk_factor(defender, ParameterSet()) == pytest.approx(1.0 - 0.10 * (85.0 - 78.0) / 78.0)

    def test_keeper_at_anchor_has_factor_one(self):
        assert gk_factor(make_dimensions(goalkeeping=78.0), ParameterSet()) == 1.0

    def test_weaker_keeper_increases_relative_factor(self):
        assert gk_factor(make_dimensions(goalkeeping=60.0), ParameterSet()) > 1.0

    def test_exact_base_relative_strength(self):
        attacker = make_dimensions(attack=84.0)
        defender = make_dimensions(defense=70.0, goalkeeping=85.0)
        expected = (84.0 / 78.0) / (70.0 / 78.0) * (1.0 - 0.10 * (85.0 - 78.0) / 78.0)
        assert base_relative_strength(attacker, defender, ParameterSet()) == pytest.approx(expected)

    def test_distinct_attack_defense_anchors_are_not_cancelled(self):
        params = ParameterSet(global_avg_attack=80.0, global_avg_defense=70.0, global_avg_gk=90.0)
        expected = (84.0 / 80.0) / (76.0 / 70.0) * (1.0 - 0.10 * (81.0 - 90.0) / 90.0)
        assert base_relative_strength(make_dimensions(), make_dimensions(), params) == pytest.approx(expected)

    def test_zero_attack_gives_zero_base(self):
        assert base_relative_strength(make_dimensions(attack=0.0), make_dimensions(), ParameterSet()) == 0.0

    def test_zero_defense_fails_without_epsilon(self):
        with pytest.raises(Layer3InputError, match="Defense_B.*strictly positive"):
            base_relative_strength(make_dimensions(), make_dimensions(defense=0.0), ParameterSet())

    def test_zero_or_negative_global_anchors_rejected(self):
        for name in ("global_avg_attack", "global_avg_defense", "global_avg_gk"):
            for value in (0.0, -1.0):
                with pytest.raises(Layer3InputError):
                    base_relative_strength(make_dimensions(), make_dimensions(), ParameterSet(**{name: value}))
        with pytest.raises(Layer3InputError, match="GlobalAvgCreation"):
            creation_factor(make_dimensions(), 0.5, ParameterSet(global_avg_creation=0.0))

    def test_nonfinite_anchor_rejected(self):
        with pytest.raises(Layer3InputError, match="finite"):
            gk_factor(make_dimensions(), ParameterSet(global_avg_gk=float("nan")))

    def test_negative_gk_result_not_clamped(self):
        with pytest.raises(Layer3InputError, match="GK_Factor"):
            gk_factor(make_dimensions(goalkeeping=100.0), ParameterSet(global_avg_gk=1.0))

    def test_exact_sigmoid(self):
        assert sigmoid(0.0) == 0.5
        for value in (-2.0, -0.7, 0.7, 2.0):
            assert sigmoid(value) == pytest.approx(1.0 / (1.0 + math.exp(-value)))

    def test_sigmoid_extremes_do_not_overflow(self):
        assert sigmoid(-1000.0) == 0.0
        assert sigmoid(1000.0) == 1.0

    def test_sigmoid_nonfinite_or_non_numeric_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "0.5"):
            with pytest.raises(Layer3InputError):
                sigmoid(value)

    def test_exact_possession_share_uses_final_fields(self):
        attacker = make_tactical(possession_tendency_final=0.60, build_up_control_score=0.70)
        defender = make_tactical(possession_tendency_final=0.40, press_final=0.80)
        expected = 1.0 / (1.0 + math.exp(-1.5 * (0.60 - 0.40 + 0.70 - 0.80)))
        assert possession_share(attacker, defender, ParameterSet()) == pytest.approx(expected)

    def test_possession_directions_are_not_forced_complements(self):
        a = make_tactical(possession_tendency_final=0.60, build_up_control_score=0.90, press_final=0.20)
        b = make_tactical(possession_tendency_final=0.40, build_up_control_score=0.70, press_final=0.30)
        params = ParameterSet()
        forward = possession_share(a, b, params)
        reverse = possession_share(b, a, params)
        assert forward == pytest.approx(sigmoid(1.5 * (0.60 - 0.40 + 0.90 - 0.30)))
        assert reverse == pytest.approx(sigmoid(1.5 * (0.40 - 0.60 + 0.70 - 0.20)))
        assert abs(forward + reverse - 1.0) > 0.1

    def test_exact_creation_realization(self):
        assert creation_realization(0.25) == pytest.approx(0.70)
        assert creation_realization(0.0) == 0.6
        assert creation_realization(1.0) == 1.0

    def test_creation_realization_rejects_invalid_share(self):
        for value in (-0.1, 1.1, float("nan")):
            with pytest.raises(Layer3InputError):
                creation_realization(value)

    def test_exact_creation_factor(self):
        assert creation_factor(make_dimensions(creation=90.0), 0.25, ParameterSet()) == pytest.approx(
            (0.7 + 0.3 * 90.0 / 78.0) * (0.6 + 0.4 * 0.25)
        )

    def test_exact_adjusted_base(self):
        assert adjusted_base(1.20, 0.75) == pytest.approx(0.90)

    def test_exact_press_interaction(self):
        assert press_interaction(0.36, ParameterSet()) == pytest.approx(0.856)

    def test_exact_width_interaction(self):
        assert width_interaction(0.20, ParameterSet()) == pytest.approx(1.04)
        assert width_interaction(-0.20, ParameterSet()) == pytest.approx(0.96)

    def test_negative_interaction_rejected_without_clamp(self):
        with pytest.raises(Layer3InputError, match="I_press"):
            press_interaction(3.0, ParameterSet())
        with pytest.raises(Layer3InputError, match="I_width"):
            width_interaction(-6.0, ParameterSet())

    def test_exact_tempo_interaction(self):
        assert tempo_interaction(make_tactical(tempo_final=0.55), ParameterSet()) == pytest.approx(1.0825)

    def test_exact_organized_attack_product(self):
        assert organized_attack(0.9, 0.856, 1.04, 1.0825) == pytest.approx(0.9 * 0.856 * 1.04 * 1.0825)

    def test_exact_space_behind_defense(self):
        assert space_behind_defense(make_tactical(line_final=0.85, defensive_cover_feature=0.40)) == pytest.approx(0.51)

    def test_space_zero_at_zero_line_or_full_cover(self):
        assert space_behind_defense(make_tactical(line_final=0.0)) == 0.0
        assert space_behind_defense(make_tactical(defensive_cover_feature=1.0)) == 0.0

    def test_exact_transition_threat(self):
        attacker = make_tactical(transition_tendency_final=0.80, attack_pace_factor=0.90)
        defender = make_tactical(line_final=0.85, defensive_cover_feature=0.40)
        assert transition_threat(attacker, defender, 0.25, ParameterSet()) == pytest.approx(
            0.80 * 0.90 * 0.85 * (1.0 - 0.40) + 0.25 * 0.80 * 0.50
        )

    def test_transition_second_term_is_independent_of_space(self):
        attacker = make_tactical(transition_tendency_final=0.80)
        defender = make_tactical(line_final=0.0)
        assert transition_threat(attacker, defender, 0.25, ParameterSet()) == pytest.approx(0.25 * 0.80 * 0.50)

    def test_zero_transition_tendency_zeroes_both_terms(self):
        assert transition_threat(make_tactical(transition_tendency_final=0.0), make_tactical(), 0.25, ParameterSet()) == 0.0

    def test_zero_pace_zeroes_space_term_only(self):
        assert transition_threat(make_tactical(attack_pace_factor=0.0), make_tactical(), 0.25, ParameterSet()) == pytest.approx(0.25 * 0.60 * 0.50)

    def test_negative_transition_result_rejected(self):
        with pytest.raises(Layer3InputError, match="T"):
            transition_threat(make_tactical(), make_tactical(line_final=0.0), -1.0, ParameterSet())

    def test_coefficients_are_explicit_configuration_not_literals(self):
        config = Layer3Coefficients(
            creation_realization_offset=0.50,
            creation_realization_possession_weight=0.30,
            creation_factor_offset=0.80,
            creation_factor_creation_weight=0.10,
        )
        assert creation_realization(0.5, config) == pytest.approx(0.65)
        assert creation_factor(make_dimensions(creation=78.0), 0.5, ParameterSet(), config) == pytest.approx(0.9 * 0.65)

    def test_parameter_set_knobs_are_actually_consumed(self):
        params = ParameterSet(k_p=0.2, k_w=0.4, k_te=0.3, k_t2=0.7, k_gk=0.2, k_poss_calc=2.0)
        a, b = make_tactical(), make_tactical()
        assert press_interaction(0.3, params) == pytest.approx(0.94)
        assert width_interaction(0.3, params) == pytest.approx(1.12)
        assert tempo_interaction(a, params) == pytest.approx(1.15)
        assert gk_factor(make_dimensions(goalkeeping=85.0), params) == pytest.approx(1 - 0.2 * 7.0 / 78.0)
        assert possession_share(a, b, params) == pytest.approx(sigmoid(2.0 * (0.70 - 0.30)))
        assert transition_threat(a, b, 0.25, params) == pytest.approx(0.6 * 0.8 * 0.4 * 0.6 + 0.25 * 0.6 * 0.7)


class TestLayer3MatchupComposition:
    def test_full_direction_matches_independent_hand_calculation(self):
        a = make_dimensions(attack=84.0, creation=90.0)
        b = make_dimensions(defense=70.0, goalkeeping=85.0)
        ta = make_tactical(possession_tendency_final=0.60, build_up_control_score=0.70, tempo_final=0.55)
        tb = make_tactical(possession_tendency_final=0.40, press_final=0.80, line_final=0.85, defensive_cover_feature=0.40)
        result = MatchupEngine(ParameterSet()).evaluate_direction(a, b, ta, tb, helpers=make_helpers())
        keeper = 1 - 0.1 * (85.0 - 78.0) / 78.0
        base = (84.0 / 78.0) / (70.0 / 78.0) * keeper
        share = 1 / (1 + math.exp(-1.5 * (0.60 - 0.40 + 0.70 - 0.80)))
        realized = 0.6 + 0.4 * share
        creation = (0.7 + 0.3 * 90.0 / 78.0) * realized
        expected = dict(
            gk_factor=keeper,
            base_relative_strength=base,
            possession_share=share,
            creation_realization=realized,
            creation_factor=creation,
            adjusted_base=base * creation,
            i_press=1 - 0.4 * 0.36,
            i_width=1 + 0.2 * 0.20,
            i_tempo=1 + 0.15 * 0.55,
            space_behind_defense=0.85 * (1 - 0.40),
            m=base * creation * (1 - 0.4 * 0.36) * (1 + 0.2 * 0.20) * (1 + 0.15 * 0.55),
            t=0.60 * 0.80 * 0.85 * (1 - 0.40) + 0.25 * 0.60 * 0.50,
        )
        for name, value in expected.items():
            assert getattr(result, name) == pytest.approx(value), name

    def test_two_directions_use_distinct_inputs_and_helpers(self):
        engine = MatchupEngine(ParameterSet())
        a, b = make_dimensions(), make_dimensions(attack=65.0, defense=85.0)
        ta, tb = make_tactical(), make_tactical(tempo_final=0.75, line_final=0.80)
        h_ab = make_helpers()
        h_ba = DirectionalMatchupHelpers(press_disruption_m=0.10, width_mismatch=-0.10, press_transition_opportunity_t=0.05)
        ab = engine.evaluate_direction(a, b, ta, tb, helpers=h_ab)
        ba = engine.evaluate_direction(b, a, tb, ta, helpers=h_ba)
        pair = engine.calculate(a, b, ta, tb, home_to_away_helpers=h_ab, away_to_home_helpers=h_ba)
        assert isinstance(pair, MatchupResult)
        assert pair.m_home_to_away == ab.m
        assert pair.t_home_to_away == ab.t
        assert pair.m_away_to_home == ba.m
        assert pair.t_away_to_home == ba.t
        assert ab.m != ba.m
        assert ab.t != ba.t

    def test_swapping_sides_swaps_outputs_without_home_advantage(self):
        engine = MatchupEngine(ParameterSet())
        a, b = make_dimensions(), make_dimensions(attack=65.0)
        ta, tb = make_tactical(), make_tactical(transition_tendency_final=0.20)
        hab = make_helpers()
        hba = DirectionalMatchupHelpers(press_disruption_m=0.1, width_mismatch=-0.2, press_transition_opportunity_t=0.3)
        original = engine.calculate(a, b, ta, tb, home_to_away_helpers=hab, away_to_home_helpers=hba)
        reversed_pair = engine.calculate(b, a, tb, ta, home_to_away_helpers=hba, away_to_home_helpers=hab)
        assert original.m_home_to_away == reversed_pair.m_away_to_home
        assert original.t_home_to_away == reversed_pair.t_away_to_home
        assert original.m_away_to_home == reversed_pair.m_home_to_away
        assert original.t_away_to_home == reversed_pair.t_home_to_away

    def test_deterministic_repeated_execution(self):
        engine = MatchupEngine(ParameterSet())
        inputs = (make_dimensions(), make_dimensions(attack=72.0), make_tactical(), make_tactical())
        expected = engine.evaluate_direction(*inputs, helpers=make_helpers())
        for _ in range(20):
            assert engine.evaluate_direction(*inputs, helpers=make_helpers()) == expected

    def test_upstream_inputs_and_configuration_are_not_mutated(self):
        params = ParameterSet()
        inputs = (make_dimensions(), make_dimensions(), make_tactical(), make_tactical())
        before = [obj.model_dump() for obj in (*inputs, params)]
        helpers = make_helpers()
        before_helpers = asdict(helpers)
        MatchupEngine(params).calculate(*inputs, home_to_away_helpers=helpers, away_to_home_helpers=helpers)
        assert [obj.model_dump() for obj in (*inputs, params)] == before
        assert asdict(helpers) == before_helpers

    def test_missing_helpers_are_explicit_specification_gap(self):
        with pytest.raises(SpecificationGapError, match="PressDisruption_M.*WidthMismatch.*PressTransitionOpportunity_T"):
            MatchupEngine(ParameterSet()).evaluate_direction(make_dimensions(), make_dimensions(), make_tactical(), make_tactical())

    def test_missing_reverse_helpers_are_not_copied_from_forward(self):
        with pytest.raises(SpecificationGapError):
            MatchupEngine(ParameterSet()).calculate(
                make_dimensions(), make_dimensions(), make_tactical(), make_tactical(),
                home_to_away_helpers=make_helpers(),
            )

    def test_helper_fields_have_no_defaults(self):
        with pytest.raises(TypeError):
            DirectionalMatchupHelpers()
        with pytest.raises(TypeError):
            DirectionalMatchupHelpers(press_disruption_m=0.36, width_mismatch=0.20)

    def test_nonfinite_helper_values_rejected(self):
        for field in ("press_disruption_m", "width_mismatch", "press_transition_opportunity_t"):
            for value in (float("nan"), float("inf"), True):
                values = asdict(make_helpers())
                values[field] = value
                with pytest.raises(Layer3InputError):
                    DirectionalMatchupHelpers(**values)

    def test_helper_and_engine_configuration_are_frozen(self):
        helpers = make_helpers()
        with pytest.raises(FrozenInstanceError):
            helpers.width_mismatch = 0.0
        engine = MatchupEngine(ParameterSet())
        with pytest.raises(FrozenInstanceError):
            engine.parameters = ParameterSet()
