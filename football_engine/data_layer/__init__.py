"""
football_engine.data_layer — Layer 1: Data Layer + JSON Schemas.

Pipeline: JSON files -> Pydantic-validated *Record schemas -> referential
integrity checks -> in-memory repositories of Layer 0 core-model objects
(PlayerSeason, TeamSeason, Formation, HistoricalPrior).

Non-goals (see loader.py / schemas.py module docstrings and README
Section 26): no Matchup Engine, no lambda/probability code, no
simulation, no calibration optimizer. This package only gets data from
disk into validated, cross-referenced, in-memory form.
"""

from __future__ import annotations

from football_engine.data_layer.exceptions import (
    DataLayerError,
    DatasetFileError,
    DuplicateIdError,
    InvalidFormationAssignmentError,
    SchemaValidationError,
    UnknownReferenceError,
)
from football_engine.data_layer.loader import (
    load_all,
    load_formation_dataset,
    load_historical_prior_dataset,
    load_player_dataset,
    load_team_dataset,
)
from football_engine.data_layer.repository import (
    DataRepositories,
    FormationRepository,
    HistoricalPriorRepository,
    PlayerRepository,
    TeamSeasonRepository,
)
from football_engine.data_layer.schemas import (
    DatasetMetadata,
    DimensionAdjustmentRecord,
    FormationDataset,
    FormationRecord,
    HistoricalPriorDataset,
    HistoricalPriorRecord,
    IdentityPriorsRecord,
    PlayerSeasonDataset,
    PlayerSeasonRecord,
    PositionSlotRecord,
    RecordStatus,
    SourceMetadata,
    TeamSeasonDataset,
    TeamSeasonRecord,
)

from football_engine.data_layer.snapshot_quality import HistoricalSnapshotQuality, SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS
from football_engine.data_layer.possession_source import JsonPossessionTendencySource, create_possession_source

__all__ = [
    "HistoricalSnapshotQuality",
    "SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS",
    # exceptions
    "DataLayerError",
    "DatasetFileError",
    "SchemaValidationError",
    "DuplicateIdError",
    "UnknownReferenceError",
    "InvalidFormationAssignmentError",
    # loader
    "load_all",
    "load_player_dataset",
    "load_formation_dataset",
    "load_team_dataset",
    "load_historical_prior_dataset",
    # repositories
    "DataRepositories",
    "PlayerRepository",
    "TeamSeasonRepository",
    "FormationRepository",
    "HistoricalPriorRepository",
    # schemas
    "RecordStatus",
    "SourceMetadata",
    "DatasetMetadata",
    "PlayerSeasonRecord",
    "PlayerSeasonDataset",
    "PositionSlotRecord",
    "FormationRecord",
    "FormationDataset",
    "IdentityPriorsRecord",
    "DimensionAdjustmentRecord",
    "HistoricalPriorRecord",
    "HistoricalPriorDataset",
    "TeamSeasonRecord",
    "TeamSeasonDataset",
    # possession
    "JsonPossessionTendencySource",
    "create_possession_source",
]
