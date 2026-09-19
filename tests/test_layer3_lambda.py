"""Module 7 formula, context, and no-extra-modifier tests."""

import pytest

from football_engine.core.matchup import LambdaPair, MatchupResult
from football_engine.core.parameters import ParameterSet
from football_engine.matchup.configuration import Layer3Coefficients
from football_engine.matchup.errors import Layer3InputError
from football_engine.matchup.lambda_calculator import (
    LambdaCalculator,
    form_factor_for_match,
    form_factor_from_recent_performance_index,
    home_multiplier,
    lambda_base,
)
from tests.layer3_helpers import make_runtime


def manual_matchup() -> MatchupResult:
    return MatchupResult(m_home_to_away=0.80, m_away_to_home=0.60, t_home_to_away=0.40, t_away_to_home=0.20)


class TestLayer3LambdaFormulae:
    def test_exact_lambda_base(self):
        assert lambda_base(0.80, 0.40, ParameterSet()) == pytest.approx(1.35 * 0.80 + 0.55 * 0.40)

    def test_transition_is_not_scaled_by_baseline(self):
        assert lambda_base(0.0, 1.0, ParameterSet()) == 0.55

    def test_base_uses_parameter_set_not_hardcoded_priors(self):
        params = ParameterSet(baseline=1.70, transition_weight=0.80)
        assert lambda_base(0.80, 0.40, params) == pytest.approx(1.70 * 0.80 + 0.80 * 0.40)

    def test_zero_m_and_t_gives_zero_lambda(self):
        assert lambda_base(0.0, 0.0, ParameterSet()) == 0.0

    def test_negative_or_nonfinite_rates_rejected(self):
        for m, t in ((-0.1, 0.2), (0.1, -0.2), (float("inf"), 0.1), (0.1, float("nan"))):
            with pytest.raises(Layer3InputError):
                lambda_base(m, t, ParameterSet())

    def test_exact_home_and_away_multipliers(self):
        assert home_multiplier(True, ParameterSet()) == 1.10
        assert home_multiplier(False, ParameterSet()) == 0.95

    def test_home_and_away_multipliers_are_configurable(self):
        params = ParameterSet(h_home=1.20, a_away=0.85)
        assert home_multiplier(True, params) == 1.20
        assert home_multiplier(False, params) == 0.85

    def test_home_context_requires_bool(self):
        with pytest.raises(Layer3InputError):
            home_multiplier(1, ParameterSet())

    def test_exact_form_factor_linear_region(self):
        params = ParameterSet()
        assert form_factor_from_recent_performance_index(0.0, params) == 1.0
        assert form_factor_from_recent_performance_index(0.50, params) == pytest.approx(1.075)
        assert form_factor_from_recent_performance_index(-0.50, params) == pytest.approx(0.925)

    def test_exact_form_factor_clamp_boundaries(self):
        params = ParameterSet()
        for recent in (1.0, 2.0, 100.0):
            assert form_factor_from_recent_performance_index(recent, params) == 1.15
        for recent in (-1.0, -2.0, -100.0):
            assert form_factor_from_recent_performance_index(recent, params) == 0.85

    def test_form_uses_existing_k_form_parameter(self):
        assert form_factor_from_recent_performance_index(0.5, ParameterSet(k_form=0.10)) == pytest.approx(1.05)

    def test_form_bounds_are_explicit_layer3_configuration(self):
        coefficients = Layer3Coefficients(form_min=0.90, form_max=1.10)
        assert form_factor_from_recent_performance_index(2.0, ParameterSet(), coefficients) == 1.10
        assert form_factor_from_recent_performance_index(-2.0, ParameterSet(), coefficients) == 0.90

    def test_nonfinite_recent_performance_index_rejected(self):
        for value in (float("inf"), float("nan")):
            with pytest.raises(Layer3InputError):
                form_factor_from_recent_performance_index(value, ParameterSet())

    def test_standalone_form_is_exactly_one_regardless_of_stored_value(self):
        for stored in (0.85, 1.15, 99.0, float("nan")):
            team = make_runtime(True, form_factor=stored)
            assert form_factor_for_match(team, is_tournament=False) == 1.0

    def test_tournament_reads_precomputed_form_without_reapplying_formula(self):
        team = make_runtime(True, form_factor=1.075)
        assert form_factor_for_match(team, is_tournament=True) == 1.075
        assert team.form_factor == 1.075

    def test_invalid_tournament_form_not_repaired(self):
        for value in (0.0, 0.84, 1.16, float("inf"), float("nan")):
            with pytest.raises(Layer3InputError):
                form_factor_for_match(make_runtime(True, form_factor=value), is_tournament=True)

    def test_tournament_context_requires_explicit_bool(self):
        with pytest.raises(Layer3InputError):
            form_factor_for_match(make_runtime(True), is_tournament="false")

    def test_layer3_coefficient_validation(self):
        for changes in (
            {"form_min": 1.2, "form_max": 1.1},
            {"form_min": 0.0},
            {"creation_factor_creation_weight": -0.1},
            {"creation_realization_offset": float("nan")},
        ):
            with pytest.raises(Layer3InputError):
                Layer3Coefficients(**changes)


class TestLayer3LambdaContext:
    def test_exact_standalone_final_rates(self):
        home, away = make_runtime(True, form_factor=1.15), make_runtime(False, form_factor=0.85)
        rates = LambdaCalculator(ParameterSet()).calculate(manual_matchup(), home, away, is_tournament=False)
        assert isinstance(rates, LambdaPair)
        assert rates.lambda_home_90 == pytest.approx((1.35 * 0.80 + 0.55 * 0.40) * 1.10)
        assert rates.lambda_away_90 == pytest.approx((1.35 * 0.60 + 0.55 * 0.20) * 0.95)

    def test_exact_tournament_final_rates(self):
        home, away = make_runtime(True, form_factor=1.075), make_runtime(False, form_factor=0.925)
        rates = LambdaCalculator(ParameterSet()).calculate(manual_matchup(), home, away, is_tournament=True)
        assert rates.lambda_home_90 == pytest.approx((1.35 * 0.80 + 0.55 * 0.40) * 1.10 * 1.075)
        assert rates.lambda_away_90 == pytest.approx((1.35 * 0.60 + 0.55 * 0.20) * 0.95 * 0.925)

    def test_runtime_and_matchup_inputs_are_not_mutated(self):
        matchup, home, away = manual_matchup(), make_runtime(True), make_runtime(False)
        before = [x.model_dump() for x in (matchup, home, away)]
        LambdaCalculator(ParameterSet()).calculate(matchup, home, away, is_tournament=True)
        assert [x.model_dump() for x in (matchup, home, away)] == before

    def test_repeated_execution_is_deterministic(self):
        calc = LambdaCalculator(ParameterSet())
        args = manual_matchup(), make_runtime(True), make_runtime(False)
        expected = calc.calculate(*args, is_tournament=False)
        for _ in range(20):
            assert calc.calculate(*args, is_tournament=False) == expected

    def test_inconsistent_home_away_flags_are_rejected(self):
        with pytest.raises(Layer3InputError, match="is_home"):
            LambdaCalculator(ParameterSet()).calculate(manual_matchup(), make_runtime(False), make_runtime(True), is_tournament=False)

    def test_no_v2_red_card_modifier_or_player_count_factor(self):
        calc = LambdaCalculator(ParameterSet(r_card=0.01))
        normal_home, normal_away = make_runtime(True), make_runtime(False)
        altered_home = make_runtime(True, red_card_modifier=0.01, player_count=7, score=4)
        altered_away = make_runtime(False, red_card_modifier=0.50, player_count=8, score=1)
        expected = calc.calculate(manual_matchup(), normal_home, normal_away, is_tournament=False)
        assert calc.calculate(manual_matchup(), altered_home, altered_away, is_tournament=False) == expected

    def test_varying_k_form_does_not_recompute_precomputed_tournament_form(self):
        args = manual_matchup(), make_runtime(True, form_factor=1.10), make_runtime(False, form_factor=0.90)
        original = LambdaCalculator(ParameterSet()).calculate(*args, is_tournament=True)
        changed = LambdaCalculator(ParameterSet(k_form=0.90)).calculate(*args, is_tournament=True)
        assert original == changed

    def test_no_probability_or_duration_scaling_in_output(self):
        rates = LambdaCalculator(ParameterSet()).calculate(manual_matchup(), make_runtime(True), make_runtime(False), is_tournament=False)
        assert set(rates.model_dump()) == {"lambda_home_90", "lambda_away_90"}
        assert rates.lambda_home_90 > 1.0  # a rate, not a probability
