"""Numerical domain checks, not additional football modeling."""

from __future__ import annotations

import math

from football_engine.matchup.errors import Layer3InputError


def finite_number(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Layer3InputError(f"{name} must be a finite real number")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise Layer3InputError(f"{name} must be finite; got {value!r}")
    return float(value)


def nonnegative(name: str, value: float) -> float:
    value = finite_number(name, value)
    if value < 0.0:
        raise Layer3InputError(f"{name} must be nonnegative; got {value}")
    return value


def positive(name: str, value: float) -> float:
    value = finite_number(name, value)
    if value <= 0.0:
        raise Layer3InputError(
            f"{name} must be strictly positive; no epsilon fallback is specified"
        )
    return value


def unit_interval(name: str, value: float) -> float:
    value = finite_number(name, value)
    if not 0.0 <= value <= 1.0:
        raise Layer3InputError(f"{name} must be in [0, 1]; got {value}")
    return value
