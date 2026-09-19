"""Immutable, uncalibrated Layer 2 role-weight priors from design memo V2/V3.

These are NOT Section R scorer/assist tables and are NOT fitted parameters.
The unique GK is selected directly, so no tunable GK weight vector exists.
The corrected memo documents common-scale invariance and calibration limits.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from football_engine.core.enums import PlayerRole


@dataclass(frozen=True)
class DimensionRoleWeights:
    attack: float
    creation: float
    defense: float


@dataclass(frozen=True)
class IdentityRoleWeights:
    press: float
    transition: float
    tempo: float
    risk: float
    attack_pace: float


DIMENSION_ROLE_WEIGHT_PRIORS: Final[Mapping[PlayerRole, DimensionRoleWeights]] = MappingProxyType({
    PlayerRole.GK: DimensionRoleWeights(0.00, 0.00, 0.00),
    PlayerRole.CB: DimensionRoleWeights(0.05, 0.10, 1.00),
    PlayerRole.FB: DimensionRoleWeights(0.15, 0.35, 0.65),
    PlayerRole.DM: DimensionRoleWeights(0.10, 0.45, 0.55),
    PlayerRole.CM: DimensionRoleWeights(0.25, 0.70, 0.35),
    PlayerRole.WM: DimensionRoleWeights(0.65, 0.55, 0.15),
    PlayerRole.AM: DimensionRoleWeights(0.55, 0.85, 0.10),
    PlayerRole.FW: DimensionRoleWeights(1.00, 0.30, 0.05),
})

IDENTITY_ROLE_WEIGHT_PRIORS: Final[Mapping[PlayerRole, IdentityRoleWeights]] = MappingProxyType({
    PlayerRole.GK: IdentityRoleWeights(0.00, 0.00, 0.05, 0.00, 0.00),
    PlayerRole.CB: IdentityRoleWeights(0.30, 0.10, 0.20, 0.05, 0.00),
    PlayerRole.FB: IdentityRoleWeights(0.50, 0.40, 0.30, 0.15, 0.20),
    PlayerRole.DM: IdentityRoleWeights(0.60, 0.20, 0.30, 0.10, 0.00),
    PlayerRole.CM: IdentityRoleWeights(0.55, 0.30, 0.35, 0.25, 0.10),
    PlayerRole.WM: IdentityRoleWeights(0.45, 0.60, 0.30, 0.45, 0.60),
    PlayerRole.AM: IdentityRoleWeights(0.35, 0.45, 0.35, 0.55, 0.50),
    PlayerRole.FW: IdentityRoleWeights(0.25, 0.55, 0.25, 0.75, 1.00),
})
