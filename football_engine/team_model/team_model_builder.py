"""
Team Model Builder — Layer 2 orchestration (wires Modules 1, 2, 3 in the
locked dependency order; NOT a new module of its own).

Architecture reference: Section 33/34 ("computed_dimensions /
computed_identity در runtime محاسبه می‌شوند؛ چون formation انتخابی
می‌تواند آن‌ها را تغییر دهد" — Section 34, "Runtime Pipeline").

Locked dependency graph enforced here (this is plumbing/wiring, not a
new derivation — no TODO(SPEC-NEEDED) applies to this file):

    PlayerSeason[11] + Formation
        --(Module 1: FormationEngine)-->        StructuralFeatures
    PlayerSeason[11] + StructuralFeatures
        --(Module 2: TeamDimensionEngine)-->    TeamDimensions (pre-prior)
    TeamDimensions (pre-prior) + HistoricalPrior
        --(apply_historical_prior_to_dimensions, already locked)-->
                                                  TeamDimensions (final)
    PlayerSeason[11] + StructuralFeatures + HistoricalPrior
        --(Module 3: TeamIdentityEngine, blend wired internally)-->
                                                  TeamIdentity (final)

This file does not decide *when* a match rebuilds these values (that is
a Layer 5 orchestration concern, since formation is fixed for the
duration of one match per N.4) — it only provides the single, correct
call order so Layer 5 doesn't have to re-derive this dependency graph
itself.

FormationEngine and D1 dimensions are implemented. Identity assembly uses
seven specified components plus an explicitly configured possession source.
Configure TeamIdentityEngine(possession_source=...) and inject that engine
here; the builder itself adds no source fallback or numerical logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from football_engine.core.formation import Formation
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.core.team_identity import TeamIdentity
from football_engine.core.team_season import HistoricalPrior, apply_historical_prior_to_dimensions
from football_engine.team_model.formation_engine import FormationEngine
from football_engine.team_model.team_dimension_engine import TeamDimensionEngine
from football_engine.team_model.team_identity_engine import TeamIdentityEngine


@dataclass(frozen=True)
class TeamModel:
    """
    Bundle of everything Modules 1-3 produce for one TeamSeason under one
    chosen Formation: the three objects a Layer 5 match build needs to
    construct a TeamRuntimeState (team_runtime_state.py's immutable
    fields: dims, identity, formation).
    """

    structural_features: StructuralFeatures
    dimensions: TeamDimensions
    identity: TeamIdentity


class TeamModelBuilder:
    """
    Orchestrates Modules 1-3 in the locked dependency order for one
    (roster, formation, historical_prior) triple.

    This class stores configured engines, not mutable per-match values,
    and performs no derivation. Layer 5 (or tests) has one call site instead of
    needing to know the correct Module 1 -> 2/3 -> historical-prior-blend
    ordering itself.
    """

    def __init__(
        self,
        formation_engine: FormationEngine | None = None,
        dimension_engine: TeamDimensionEngine | None = None,
        identity_engine: TeamIdentityEngine | None = None,
    ) -> None:
        self._formation_engine = formation_engine or FormationEngine()
        self._dimension_engine = dimension_engine or TeamDimensionEngine()
        self._identity_engine = identity_engine or TeamIdentityEngine()

    def build(
        self,
        players: list[PlayerSeason],
        formation: Formation,
        historical_prior: HistoricalPrior | None,
    ) -> TeamModel:
        """
        Run Modules 1-3 in the locked order and return the fully-blended
        TeamModel.

        Raises:
            FormationEngineError / TeamDimensionEngineError /
                TeamIdentityEngineError: on invalid input shape (wrong
                squad size, duplicate ids, role-count mismatch).
            TeamIdentitySpecificationGapError (NotImplementedError): an
                explicit possession source has not been configured. Modules
                1/2 succeed; no fake identity or fallback model is built.
        """
        structural_features = self._formation_engine.derive(players, formation)

        pre_prior_dimensions = self._dimension_engine.derive(players, structural_features)
        final_dimensions = apply_historical_prior_to_dimensions(pre_prior_dimensions, historical_prior)

        # TeamIdentityEngine.derive() applies the historical-prior blend
        # internally (see team_identity_engine.py) — no separate call
        # needed here, unlike dimensions above.
        final_identity = self._identity_engine.derive(players, structural_features, historical_prior)

        return TeamModel(
            structural_features=structural_features,
            dimensions=final_dimensions,
            identity=final_identity,
        )
