"""Module 5 — Tactical Profile Generator (Layer 3 boundary, not invented math).

F-1(b): Layer 5 passes TeamModel.identity and TeamModel.structural_features
explicitly, together with MatchState. Nothing is added to TeamIdentity or to
TeamRuntimeState. The original numbered state-adjustment equations and the
one-time P/U/Ts composition are absent from the supplied repository. A typed
policy is therefore required; missing policy is an explicit specification gap.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_engine.core.enums import MatchState
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.core.team_identity import TeamIdentity
from football_engine.matchup.dependencies import TacticalProfilePolicy
from football_engine.matchup.errors import Layer3InputError, SpecificationGapError


@dataclass(frozen=True)
class TacticalProfileGenerator:
    policy: TacticalProfilePolicy | None = None

    def generate(
        self,
        identity: TeamIdentity,
        structural_features: StructuralFeatures,
        state: MatchState,
    ) -> TacticalProfile:
        """Return the supplied approved policy's result, never a fabricated one."""
        if not isinstance(identity, TeamIdentity):
            raise Layer3InputError("identity must be a TeamIdentity")
        if not isinstance(structural_features, StructuralFeatures):
            raise Layer3InputError("structural_features must be StructuralFeatures")
        if not isinstance(state, MatchState):
            raise Layer3InputError("state must be a MatchState")
        if self.policy is None:
            raise SpecificationGapError(
                "Module 5 specification gap: exact TeamIdentity + StructuralFeatures "
                "baseline composition (including P/U/Ts ownership) and field-by-field "
                "MatchState -> TacticalProfile adjustments for NORMAL, LEADING, "
                "LOSING, REACTIVE are not supplied. Provide an explicit "
                "TacticalProfilePolicy; no default adjustments are assumed."
            )
        result = self.policy(
            identity=identity,
            structural_features=structural_features,
            state=state,
        )
        if not isinstance(result, TacticalProfile):
            raise Layer3InputError("TacticalProfilePolicy must return a TacticalProfile")
        # Validate the final values even if a caller used model_construct/copy.
        return TacticalProfile.model_validate(result.model_dump())
