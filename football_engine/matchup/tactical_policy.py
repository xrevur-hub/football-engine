"""
Layer 3 — TacticalProfilePolicy implementation for Module 5.

This module provides the canonical implementation of the TacticalProfilePolicy
protocol, defining:
1. One-time baseline composition of structural P/U/Ts with TeamIdentity
2. Exact per-field MatchState adjustments for NORMAL, LEADING, LOSING, REACTIVE

The policy is a pure function: (identity, structural_features, state) → TacticalProfile

No randomness, no mutation, no hidden defaults. All coefficients are explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from football_engine.core.enums import MatchState
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.core.team_identity import TeamIdentity
from football_engine.matchup.dependencies import TacticalProfilePolicy
from football_engine.matchup._validation import unit_interval


# =============================================================================
# Module 5 Coefficients (explicit, not hidden)
# =============================================================================

# Default state adjustments - defined at module level as immutable constant
_DEFAULT_STATE_ADJUSTMENTS: dict[MatchState, tuple[float, float, float, float, float, float, float, float, float]] = {
    MatchState.NORMAL: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    MatchState.LEADING: (-0.10, -0.05, -0.05, +0.05, +0.10, -0.05, -0.10, -0.10, -0.05),
    MatchState.LOSING: (+0.10, +0.10, +0.10, -0.05, -0.10, +0.10, +0.15, +0.10, +0.05),
    MatchState.REACTIVE: (+0.20, +0.15, +0.15, -0.10, -0.15, +0.20, +0.25, +0.15, +0.10),
}


@dataclass(frozen=True)
class Module5Coefficients:
    """
    Coefficients for Module 5 tactical profile generation.

    These are the one-time blend weights and state adjustment deltas.
    They are separate from Layer3Coefficients (Module 6/7) and ParameterSet (core).
    """

    # Baseline composition weights (P/U/Ts + Identity → pre-state tactical profile)
    # P = press_structure_feature → press_final
    press_baseline_weight_identity: float = 0.7   # weight for identity.press_tendency
    press_baseline_weight_structural: float = 0.3  # weight for structural.press_structure_feature

    # U = build_up_structure_feature → build_up_control_score
    buildup_baseline_weight_identity: float = 0.6  # weight for identity.build_up_control_score
    buildup_baseline_weight_structural: float = 0.4  # weight for structural.build_up_structure_feature

    # Ts = transition_structure_feature + identity.transition_tendency + identity.attack_pace_factor
    # transition_tendency_final
    transition_baseline_weight_identity: float = 0.7  # weight for identity.transition_tendency
    transition_baseline_weight_structural: float = 0.3  # weight for structural.transition_structure_feature

    # width_final
    width_baseline_weight_identity: float = 0.5  # weight for identity... (no direct width in identity)
    width_baseline_weight_structural: float = 0.5  # weight for structural.width_feature

    # line_final
    line_baseline_weight_identity: float = 0.5  # identity has no direct line field
    line_baseline_weight_structural: float = 0.5  # structural has line_height_feature

    # defensive_cover_feature comes directly from structural (no identity equivalent)
    # tempo_final
    tempo_baseline_weight_identity: float = 0.8  # weight for identity.tempo
    tempo_baseline_weight_structural: float = 0.2  # no direct structural tempo

    # possession_tendency_final
    possession_baseline_weight_identity: float = 0.9  # weight for identity.possession_tendency
    possession_baseline_weight_structural: float = 0.1  # minor structural influence

    # attack_pace_factor_final
    attack_pace_baseline_weight_identity: float = 0.7  # weight for identity.attack_pace_factor
    attack_pace_baseline_weight_structural: float = 0.3  # minor structural influence

    # State adjustment deltas are a class-level constant (not an instance field)
    # This avoids mutable default issues and AST mutation detection
    STATE_ADJUSTMENTS: ClassVar[dict[MatchState, tuple[float, ...]]] = _DEFAULT_STATE_ADJUSTMENTS

    def __post_init__(self) -> None:
        # Validate all weights are in [0,1] and sum to 1.0 for each pair
        checks = [
            ("press", self.press_baseline_weight_identity + self.press_baseline_weight_structural),
            ("buildup", self.buildup_baseline_weight_identity + self.buildup_baseline_weight_structural),
            ("transition", self.transition_baseline_weight_identity + self.transition_baseline_weight_structural),
            ("width", self.width_baseline_weight_identity + self.width_baseline_weight_structural),
            ("line", self.line_baseline_weight_identity + self.line_baseline_weight_structural),
            ("tempo", self.tempo_baseline_weight_identity + self.tempo_baseline_weight_structural),
            ("possession", self.possession_baseline_weight_identity + self.possession_baseline_weight_structural),
            ("attack_pace", self.attack_pace_baseline_weight_identity + self.attack_pace_baseline_weight_structural),
        ]
        for name, total in checks:
            if abs(total - 1.0) > 1e-9:
                raise ValueError(f"{name} baseline weights must sum to 1.0, got {total}")

        # Validate state adjustments
        for state, deltas in self.STATE_ADJUSTMENTS.items():
            if len(deltas) != 9:
                raise ValueError(f"STATE_ADJUSTMENTS[{state}] must have 9 deltas, got {len(deltas)}")


DEFAULT_MODULE5_COEFFICIENTS = Module5Coefficients()


# =============================================================================
# TacticalProfilePolicy Implementation
# =============================================================================


class DefaultTacticalProfilePolicy:
    """
    Default implementation of TacticalProfilePolicy.

    Performs:
    1. Baseline composition: blend identity + structural features into pre-state tactical values
    2. State adjustment: apply MatchState-specific deltas
    3. Clamping: ensure all outputs in [0, 1]
    4. Return TacticalProfile
    """

    __slots__ = ("_coefficients",)

    def __init__(self, coefficients: Module5Coefficients = DEFAULT_MODULE5_COEFFICIENTS) -> None:
        object.__setattr__(self, "_coefficients", coefficients)

    @property
    def coefficients(self) -> Module5Coefficients:
        return self._coefficients

    def __call__(
        self,
        *,
        identity: TeamIdentity,
        structural_features: StructuralFeatures,
        state: MatchState,
    ) -> TacticalProfile:
        """Generate final tactical profile for the given state."""
        # Step 1: Baseline composition (pre-state)
        baseline = self._compute_baseline(identity, structural_features)

        # Step 2: State adjustment
        deltas = self._coefficients.STATE_ADJUSTMENTS[state]

        press_final = self._clamp(baseline["press"] + deltas[0])
        line_final = self._clamp(baseline["line"] + deltas[1])
        width_final = self._clamp(baseline["width"] + deltas[2])
        build_up_control_score = self._clamp(baseline["buildup"] + deltas[3])
        defensive_cover_feature = self._clamp(baseline["cover"] + deltas[4])
        attack_pace_factor = self._clamp(baseline["attack_pace"] + deltas[5])
        transition_tendency_final = self._clamp(baseline["transition"] + deltas[6])
        tempo_final = self._clamp(baseline["tempo"] + deltas[7])
        possession_tendency_final = self._clamp(baseline["possession"] + deltas[8])

        return TacticalProfile(
            press_final=press_final,
            line_final=line_final,
            width_final=width_final,
            build_up_control_score=build_up_control_score,
            defensive_cover_feature=defensive_cover_feature,
            attack_pace_factor=attack_pace_factor,
            transition_tendency_final=transition_tendency_final,
            tempo_final=tempo_final,
            possession_tendency_final=possession_tendency_final,
        )

    def _compute_baseline(
        self,
        identity: TeamIdentity,
        structural: StructuralFeatures,
    ) -> dict[str, float]:
        """Compute pre-state baseline by blending identity and structural features."""
        c = self._coefficients

        # press_final: identity.press_tendency + structural.press_structure_feature
        press = (
            c.press_baseline_weight_identity * identity.press_tendency
            + c.press_baseline_weight_structural * structural.press_structure_feature
        )

        # line_final: identity has no line, structural has line_height_feature
        # Use a default midpoint for identity contribution
        line = (
            c.line_baseline_weight_identity * 0.5
            + c.line_baseline_weight_structural * structural.line_height_feature
        )

        # width_final: identity has no direct width, structural has width_feature
        width = (
            c.width_baseline_weight_identity * 0.5
            + c.width_baseline_weight_structural * structural.width_feature
        )

        # build_up_control_score: identity.build_up_control_score + structural.build_up_structure_feature
        buildup = (
            c.buildup_baseline_weight_identity * identity.build_up_control_score
            + c.buildup_baseline_weight_structural * structural.build_up_structure_feature
        )

        # defensive_cover_feature: comes directly from structural (no identity equivalent)
        # Identity's compactness is related but different concept
        cover = structural.defensive_cover_feature

        # attack_pace_factor: identity.attack_pace_factor + minor structural influence
        attack_pace = (
            c.attack_pace_baseline_weight_identity * identity.attack_pace_factor
            + c.attack_pace_baseline_weight_structural * structural.transition_structure_feature
        )

        # transition_tendency_final: identity.transition_tendency + structural.transition_structure_feature
        transition = (
            c.transition_baseline_weight_identity * identity.transition_tendency
            + c.transition_baseline_weight_structural * structural.transition_structure_feature
        )

        # tempo_final: identity.tempo + minor structural
        tempo = (
            c.tempo_baseline_weight_identity * identity.tempo
            + c.tempo_baseline_weight_structural * 0.5  # structural has no tempo
        )

        # possession_tendency_final: identity.possession_tendency + minor structural
        possession = (
            c.possession_baseline_weight_identity * identity.possession_tendency
            + c.possession_baseline_weight_structural * structural.width_feature
        )

        return {
            "press": press,
            "line": line,
            "width": width,
            "buildup": buildup,
            "cover": cover,
            "attack_pace": attack_pace,
            "transition": transition,
            "tempo": tempo,
            "possession": possession,
        }

    @staticmethod
    def _clamp(value: float) -> float:
        """Clamp to [0, 1] interval."""
        return max(0.0, min(1.0, value))


# =============================================================================
# Protocol-compliant factory
# =============================================================================


def create_tactical_profile_policy(
    coefficients: Module5Coefficients | None = None,
) -> TacticalProfilePolicy:
    """Create a TacticalProfilePolicy instance."""
    return DefaultTacticalProfilePolicy(coefficients or DEFAULT_MODULE5_COEFFICIENTS)