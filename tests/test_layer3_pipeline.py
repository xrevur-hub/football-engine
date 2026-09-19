"""Module 5 -> 6 -> 7 integration using manual fixtures ONLY.

This is a Layer 3 composition test, never a claim that Layer 2 works.
Tactical policies return explicit final-profile fixtures and do not invent
state-adjustment equations. Helpers are explicit per-direction fixture values.
"""

import math

import pytest

from football_engine.core.parameters import ParameterSet
from football_engine.matchup import (
    DirectionalMatchupHelpers,
    LambdaCalculator,
    MatchupEngine,
    TacticalProfileGenerator,
)
from tests.layer3_helpers import make_runtime, make_structure, make_tactical


def fixture_chain(*, is_tournament=False, home_form=1.0, away_form=1.0, parameters=None):
    parameters = parameters or ParameterSet()
    home = make_runtime(True, form_factor=home_form)
    away = make_runtime(False, form_factor=away_form)
    home_structure = make_structure()
    away_structure = make_structure()
    home_final_fixture = make_tactical()
    away_final_fixture = make_tactical()
    home_tactics = TacticalProfileGenerator(lambda **inputs: home_final_fixture).generate(
        home.identity, home_structure, home.state
    )
    away_tactics = TacticalProfileGenerator(lambda **inputs: away_final_fixture).generate(
        away.identity, away_structure, away.state
    )
    # Explicit values in each direction; no shared default/neutral fallback.
    home_helpers = DirectionalMatchupHelpers(press_disruption_m=0.36, width_mismatch=0.20, press_transition_opportunity_t=0.25)
    away_helpers = DirectionalMatchupHelpers(press_disruption_m=0.36, width_mismatch=0.20, press_transition_opportunity_t=0.25)
    matchup = MatchupEngine(parameters).calculate(
        home.dims, away.dims, home_tactics, away_tactics,
        home_to_away_helpers=home_helpers,
        away_to_home_helpers=away_helpers,
    )
    lambdas = LambdaCalculator(parameters).calculate(matchup, home, away, is_tournament=is_tournament)
    return matchup, lambdas


class TestLayer3ManualFixturePipeline:
    def test_full_layer3_chain_matches_independent_arithmetic(self):
        matchup, lambdas = fixture_chain()
        keeper = 1.0 - 0.10 * (81.0 - 78.0) / 78.0
        base = (84.0 / 78.0) / (76.0 / 78.0) * keeper
        possession = 1.0 / (1.0 + math.exp(-1.5 * (0.65 - 0.65 + 0.70 - 0.30)))
        creation = (0.7 + 0.3 * 90.0 / 78.0) * (0.6 + 0.4 * possession)
        m = base * creation * (1.0 - 0.40 * 0.36) * (1.0 + 0.20 * 0.20) * (1.0 + 0.15 * 0.50)
        t = 0.60 * 0.80 * 0.40 * (1.0 - 0.40) + 0.25 * 0.60 * 0.50
        assert matchup.m_home_to_away == pytest.approx(m)
        assert matchup.m_away_to_home == pytest.approx(m)
        assert matchup.t_home_to_away == pytest.approx(t)
        assert matchup.t_away_to_home == pytest.approx(t)
        assert lambdas.lambda_home_90 == pytest.approx((1.35 * m + 0.55 * t) * 1.10)
        assert lambdas.lambda_away_90 == pytest.approx((1.35 * m + 0.55 * t) * 0.95)

    def test_form_changes_only_final_lambda_not_matchup(self):
        base_matchup, base_rates = fixture_chain()
        form_matchup, form_rates = fixture_chain(is_tournament=True, home_form=1.10, away_form=0.90)
        assert base_matchup == form_matchup
        assert form_rates.lambda_home_90 == pytest.approx(base_rates.lambda_home_90 * 1.10)
        assert form_rates.lambda_away_90 == pytest.approx(base_rates.lambda_away_90 * 0.90)

    def test_home_advantage_changes_only_final_lambda(self):
        baseline_matchup, baseline_rates = fixture_chain()
        changed_matchup, changed_rates = fixture_chain(parameters=ParameterSet(h_home=1.20, a_away=0.85))
        assert baseline_matchup == changed_matchup
        assert changed_rates.lambda_home_90 == pytest.approx(baseline_rates.lambda_home_90 * 1.20 / 1.10)
        assert changed_rates.lambda_away_90 == pytest.approx(baseline_rates.lambda_away_90 * 0.85 / 0.95)

    def test_repeated_fixture_chain_has_identical_serialization(self):
        first = tuple(value.model_dump_json() for value in fixture_chain())
        for _ in range(10):
            assert tuple(value.model_dump_json() for value in fixture_chain()) == first
