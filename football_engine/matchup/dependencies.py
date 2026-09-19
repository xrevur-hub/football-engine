"""Explicit typed boundaries for the canonical equations that are still absent.

There are no production guesses or neutral-value fallbacks here. Callers must
supply independently derived helper values for BOTH matchup directions, or an
approved tactical policy. Tests may supply clearly labeled hand-built values.
The future approved helper implementations plug into these same boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from football_engine.core.enums import MatchState
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.core.team_identity import TeamIdentity
from football_engine.matchup._validation import finite_number


@dataclass(frozen=True)
class DirectionalMatchupHelpers:
    """Already-evaluated dependencies for ONE attacker -> defender direction.

    press_disruption_m = PressDisruption_M(defender -> attacker)
    width_mismatch = WidthMismatch(attacker, defender)
    press_transition_opportunity_t = PressTransitionOpportunity_T(defender -> attacker)

    All three are required; none is derived from either of the others. No
    [0,1] or [-1,1] helper range is invented: only finiteness is required here.
    The consuming equations separately reject invalid negative interaction
    factors/rates. Supplying 0.0 is an explicit caller choice, never a default.

    These values contain no provenance or quality label and are not a generic
    tactical multiplier. Approved helper code must preserve the M/T input
    ownership rules; this value boundary cannot certify arbitrary caller code.
    """

    press_disruption_m: float
    width_mismatch: float
    press_transition_opportunity_t: float

    def __post_init__(self) -> None:
        finite_number("PressDisruption_M", self.press_disruption_m)
        finite_number("WidthMismatch", self.width_mismatch)
        finite_number("PressTransitionOpportunity_T", self.press_transition_opportunity_t)


from typing import runtime_checkable


@runtime_checkable
class TacticalProfilePolicy(Protocol):
    """Missing Module 5 mathematical dependency, including baseline composition.

    A policy must define the one-time composition of P/U/Ts with identity and
    exact per-field adjustments for NORMAL, LEADING, LOSING, and REACTIVE.
    Until supplied, even NORMAL is not silently assumed to be an identity map.
    Implementations must be deterministic, side-effect free, and must neither
    inspect formation_name/formation_type nor re-derive formation geometry.
    This protocol adds no fields to the existing Layer 0 models.
    """

    def __call__(
        self,
        *,
        identity: TeamIdentity,
        structural_features: StructuralFeatures,
        state: MatchState,
    ) -> TacticalProfile:
        ...
