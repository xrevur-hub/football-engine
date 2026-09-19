"""Layer 2 — FormationEngine, D1 dimensions and conditional identity assembly.

Seven pre-prior identity components are specified. A full identity/model also
requires an explicit external possession source; no estimator/default is
fabricated. Historical-prior blends and builder ordering remain unchanged.
"""
from __future__ import annotations

from football_engine.team_model.dependencies import PossessionTendencySource
from football_engine.team_model.formation_engine import FormationEngine, FormationEngineError
from football_engine.team_model.team_dimension_engine import TeamDimensionEngine, TeamDimensionEngineError
from football_engine.team_model.team_identity_engine import (
    TeamIdentityEngine, TeamIdentityEngineError, TeamIdentitySpecificationGapError,
)
from football_engine.team_model.team_model_builder import TeamModel, TeamModelBuilder

__all__ = [
    "FormationEngine", "FormationEngineError", "TeamDimensionEngine", "TeamDimensionEngineError",
    "TeamIdentityEngine", "TeamIdentityEngineError", "TeamIdentitySpecificationGapError",
    "PossessionTendencySource", "TeamModel", "TeamModelBuilder",
]
