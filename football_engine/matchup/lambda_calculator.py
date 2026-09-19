"""Module 7 — authorized 90-minute lambda rates, before probability/sampling.

lambda_base = baseline*M + transition_weight*T
lambda_final = lambda_base * venue_multiplier * form_factor

No extra factor (including the V2 red_card_modifier) is read or applied.
Standalone matches explicitly ignore runtime form and use exactly 1.0.
Tournament matches read the precomputed TeamRuntimeState.form_factor; the
calculator never recomputes or writes it and never derives RecentPerformanceIndex.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_engine.core.matchup import LambdaPair, MatchupResult
from football_engine.core.parameters import ParameterSet
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.matchup._validation import finite_number, nonnegative, positive
from football_engine.matchup.configuration import (
    DEFAULT_LAYER3_COEFFICIENTS,
    Layer3Coefficients,
)
from football_engine.matchup.errors import Layer3InputError


def lambda_base(m: float, t: float, parameters: ParameterSet) -> float:
    """The transition term is NOT multiplied by baseline a second time."""
    m = nonnegative("M", m)
    t = nonnegative("T", t)
    baseline = nonnegative("baseline", parameters.baseline)
    transition_weight = nonnegative("transition_weight", parameters.transition_weight)
    return nonnegative("lambda_base", baseline * m + transition_weight * t)


def home_multiplier(is_home: bool, parameters: ParameterSet) -> float:
    if not isinstance(is_home, bool):
        raise Layer3InputError("is_home must be bool")
    return positive(
        "h_home" if is_home else "a_away",
        parameters.h_home if is_home else parameters.a_away,
    )


def form_factor_from_recent_performance_index(
    recent_performance_index: float,
    parameters: ParameterSet,
    coefficients: Layer3Coefficients = DEFAULT_LAYER3_COEFFICIENTS,
) -> float:
    """Exact supplied clamp formula; the RPI itself is an external input.

    Called by a future form/state owner, not again by LambdaCalculator.
    The source definition of RecentPerformanceIndex is not available here.
    """
    recent = finite_number("RecentPerformanceIndex", recent_performance_index)
    k_form = finite_number("k_form", parameters.k_form)
    unbounded = finite_number("unbounded FormFactor", 1.0 + k_form * recent)
    return min(coefficients.form_max, max(coefficients.form_min, unbounded))


def form_factor_for_match(
    team: TeamRuntimeState,
    *,
    is_tournament: bool,
    coefficients: Layer3Coefficients = DEFAULT_LAYER3_COEFFICIENTS,
) -> float:
    if not isinstance(is_tournament, bool):
        raise Layer3InputError("is_tournament must be bool")
    if not is_tournament:
        # Do not even consult the stored value for a standalone match.
        return 1.0
    factor = finite_number("TeamRuntimeState.form_factor", team.form_factor)
    if not coefficients.form_min <= factor <= coefficients.form_max:
        raise Layer3InputError(
            "Tournament form_factor must already satisfy the approved clamp bounds "
            f"[{coefficients.form_min}, {coefficients.form_max}]; got {factor}. "
            "It is read, not recomputed or silently repaired, in Module 7."
        )
    return factor


@dataclass(frozen=True)
class LambdaCalculator:
    parameters: ParameterSet
    coefficients: Layer3Coefficients = DEFAULT_LAYER3_COEFFICIENTS

    def calculate(
        self,
        matchup: MatchupResult,
        home: TeamRuntimeState,
        away: TeamRuntimeState,
        *,
        is_tournament: bool,
    ) -> LambdaPair:
        """Use explicit context; runtime inputs are observed, never mutated.

        The caller (future Layer 5) supplies is_tournament from its match
        context; there is no implicit global mode or MatchRuntime dependency.
        Positional home/away rates and is_home flags must agree.
        """
        if home.is_home is not True or away.is_home is not False:
            raise Layer3InputError("home/away TeamRuntimeState.is_home flags are inconsistent")
        home_base = lambda_base(matchup.m_home_to_away, matchup.t_home_to_away, self.parameters)
        away_base = lambda_base(matchup.m_away_to_home, matchup.t_away_to_home, self.parameters)
        home_form = form_factor_for_match(home, is_tournament=is_tournament, coefficients=self.coefficients)
        away_form = form_factor_for_match(away, is_tournament=is_tournament, coefficients=self.coefficients)
        home_final = home_base * home_multiplier(home.is_home, self.parameters) * home_form
        away_final = away_base * home_multiplier(away.is_home, self.parameters) * away_form
        return LambdaPair(
            lambda_home_90=nonnegative("lambda_home_90", home_final),
            lambda_away_90=nonnegative("lambda_away_90", away_final),
        )
