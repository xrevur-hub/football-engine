"""Layer 3 — Matchup + lambda Engine.

Only explicit formulas are implemented. Module 5 policy and the three
Module 6 helper equations are now implemented in helpers.py.
No FormationEngine, probability model, or sampling implementation lives here.
"""

from football_engine.matchup.configuration import Layer3Coefficients
from football_engine.matchup.dependencies import DirectionalMatchupHelpers, TacticalProfilePolicy
from football_engine.matchup.errors import Layer3InputError, SpecificationGapError
from football_engine.matchup.helpers import (
    compute_directional_helpers,
    press_disruption_m,
    press_transition_opportunity_t,
    width_mismatch,
)
from football_engine.matchup.lambda_calculator import LambdaCalculator
from football_engine.matchup.matchup_engine import DirectionalMatchupBreakdown, MatchupEngine
from football_engine.matchup.tactical_policy import (
    DEFAULT_MODULE5_COEFFICIENTS,
    DefaultTacticalProfilePolicy,
    Module5Coefficients,
    create_tactical_profile_policy,
)
from football_engine.matchup.tactical_profile import TacticalProfileGenerator

__all__ = [
    "DirectionalMatchupBreakdown",
    "DirectionalMatchupHelpers",
    "LambdaCalculator",
    "Layer3Coefficients",
    "Layer3InputError",
    "MatchupEngine",
    "SpecificationGapError",
    "TacticalProfileGenerator",
    "TacticalProfilePolicy",
    # helpers
    "press_disruption_m",
    "width_mismatch",
    "press_transition_opportunity_t",
    "compute_directional_helpers",
    # tactical policy
    "Module5Coefficients",
    "DEFAULT_MODULE5_COEFFICIENTS",
    "DefaultTacticalProfilePolicy",
    "create_tactical_profile_policy",
]
