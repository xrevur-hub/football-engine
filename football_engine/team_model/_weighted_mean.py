"""Deterministic convex weighted means, not tactical multipliers or priors."""
from __future__ import annotations

import math
from typing import Callable

from football_engine.core.enums import PlayerRole
from football_engine.core.player_season import PlayerSeason
from football_engine.team_model._validation import bounded_number


def role_weighted_mean(players: tuple[PlayerSeason, ...], *, attribute: str,
                       weight_for_role: Callable[[PlayerRole], float], field_name: str,
                       upper: float, error_type: type[ValueError]) -> float:
    weights = []
    values = []
    for player in players:
        weight = weight_for_role(player.role)
        if (isinstance(weight, bool) or not isinstance(weight, (int, float))
                or not math.isfinite(weight) or weight < 0):
            raise error_type(f"{field_name} has an invalid role weight")
        if weight > 0:
            value = bounded_number(getattr(player, attribute), label=f"{player.id}.{attribute}",
                                   upper=upper, error_type=error_type)
            weights.append(float(weight))
            values.append(value)
    denominator = math.fsum(weights)
    if denominator <= 0:
        raise error_type(f"{field_name} has a zero role-weight denominator for the selected roster")
    result = math.fsum(weight * value for weight, value in zip(weights, values)) / denominator
    if not math.isfinite(result):
        raise error_type(f"{field_name} produced a nonfinite weighted mean")
    # Positive weighted means are already in this interval mathematically.
    # This projection protects floating-point rounding, not invalid inputs:
    # every consumed value/weight was validated above before calculation.
    return min(max(result, min(values)), max(values))
