"""Partial regression from quoted intermediate outputs, NOT a full replay.

No helper outputs or original raw team inputs are reverse-engineered to make
the reference pass. Independent synthetic tests cover all explicit equations.
This file verifies only the three links whose inputs were actually supplied.
"""

import json
from pathlib import Path

import pytest

from football_engine.core.parameters import ParameterSet
from football_engine.matchup.errors import SpecificationGapError
from football_engine.matchup.lambda_calculator import lambda_base
from football_engine.matchup.matchup_engine import MatchupEngine, adjusted_base, creation_realization
from tests.layer3_helpers import make_dimensions, make_tactical


REFERENCE = json.loads((Path(__file__).parent / "fixtures" / "layer3_architecture_reference.json").read_text())
VALUES = REFERENCE["reported_outputs"]


class TestLayer3ArchitectureReference:
    def test_reported_possession_to_creation_realization(self):
        # 0.6 + 0.4 * 0.231 = 0.6924, approximately the quoted 0.692.
        assert creation_realization(VALUES["possession_share"]) == pytest.approx(
            VALUES["creation_realization"], abs=REFERENCE["rounding_tolerance"]
        )

    def test_reported_base_and_creation_to_adjusted_base(self):
        # 1.089 * 0.671 = 0.730719, approximately the quoted 0.731.
        assert adjusted_base(VALUES["base_relative_strength"], VALUES["creation_factor"]) == pytest.approx(
            VALUES["adjusted_base"], abs=REFERENCE["rounding_tolerance"]
        )

    def test_reported_m_and_t_to_lambda_base(self):
        # 1.35 * 0.677 + 0.55 * 0.598 = 1.24285, approximately 1.243.
        assert lambda_base(VALUES["m"], VALUES["t"], ParameterSet()) == pytest.approx(
            VALUES["lambda_base"], abs=REFERENCE["rounding_tolerance"]
        )

    def test_reference_does_not_claim_full_reproduction(self):
        assert REFERENCE["raw_inputs_available"] is False
        assert REFERENCE["full_regression_reproduced"] is False
        assert len(REFERENCE["missing_canonical_equations"]) == 4
        assert set(VALUES) == {
            "base_relative_strength", "possession_share", "creation_realization",
            "creation_factor", "adjusted_base", "i_press", "i_tempo", "m",
            "space_behind_defense", "t", "lambda_base",
        }

    def test_missing_helpers_remain_a_real_error_not_a_reference_fallback(self):
        with pytest.raises(SpecificationGapError, match="PressTransitionOpportunity_T"):
            MatchupEngine(ParameterSet()).evaluate_direction(
                make_dimensions(), make_dimensions(), make_tactical(), make_tactical()
            )
