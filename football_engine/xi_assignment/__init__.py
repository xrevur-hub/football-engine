"""
xi_assignment — Effective XI (Free XI, Route C).

Transforms a Draft XI + user slot assignment into an Effective XI whose roles
match the chosen formation, so the unmodified pipeline penalizes unbalanced
or misplaced lineups through its existing mathematics.
"""

from __future__ import annotations

from football_engine.xi_assignment.effective_xi import (
    EffectiveXiPlayer,
    NeutralFitTable,
    build_effective_xi,
    _role_fit_factor,
)

__all__ = [
    "EffectiveXiPlayer",
    "NeutralFitTable",
    "build_effective_xi",
    "_role_fit_factor",
]