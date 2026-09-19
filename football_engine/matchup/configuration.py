"""Explicit Layer 3 coefficients not represented in the existing ParameterSet.

Source: the user's FINAL AUTHORIZATION, 2026-09-08, canonical formulas 3/4
and FormFactor. These six defaults are quoted coefficients, not newly inferred
priors. Existing k_*, anchors, baseline, transition_weight, and home/away/form
parameters ALWAYS come from core.parameters.ParameterSet.

This small, immutable, Layer-3-local configuration avoids changing Layer 0 or
hiding the remaining numeric coefficients inside calculations. No automatic
normalization, implicit fitting, or extra football multiplier is introduced.
Changing these values is an explicit alternative calibration/configuration,
not the canonical-default regression. H=0.5 and snapshot-quality weights are
upstream/outside this configuration and are not read by Layer 3 formulas.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_engine.matchup._validation import nonnegative, positive
from football_engine.matchup.errors import Layer3InputError


@dataclass(frozen=True)
class Layer3Coefficients:
    creation_realization_offset: float = 0.6
    creation_realization_possession_weight: float = 0.4
    creation_factor_offset: float = 0.7
    creation_factor_creation_weight: float = 0.3
    form_min: float = 0.85
    form_max: float = 1.15

    def __post_init__(self) -> None:
        for name in (
            "creation_realization_offset",
            "creation_realization_possession_weight",
            "creation_factor_offset",
            "creation_factor_creation_weight",
        ):
            nonnegative(name, getattr(self, name))
        positive("form_min", self.form_min)
        positive("form_max", self.form_max)
        if self.form_min > self.form_max:
            raise Layer3InputError("form_min must not exceed form_max")


DEFAULT_LAYER3_COEFFICIENTS = Layer3Coefficients()
