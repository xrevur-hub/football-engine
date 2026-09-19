"""Step A checks: explicit schema separation, without FormationEngine math."""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from football_engine.core import enums
from football_engine.core.enums import HistoricalTier
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.core.team_identity import TeamIdentity
from football_engine.data_layer.snapshot_quality import HistoricalSnapshotQuality, SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS


class TestE12ContractMigration:
    def test_misnamed_enum_is_removed_not_aliased(self):
        assert not hasattr(enums, "FormationStructuralType")
        assert not hasattr(enums, "HistoricalSnapshotQuality")

    def test_structural_features_construct_without_any_quality(self):
        features = StructuralFeatures(formation_name="explicit_geometry_only")
        assert "formation_type" not in features.model_dump()
        assert "snapshot_quality" not in features.model_dump()
        assert "formation_type" not in StructuralFeatures.model_fields

    def test_legacy_field_is_rejected_for_every_label(self):
        for label in ("TYPE_A", "TYPE_B", "TYPE_C", None):
            with pytest.raises(ValidationError, match="formation_type"):
                StructuralFeatures(formation_name="test", formation_type=label)

    def test_unknown_or_quality_fields_cannot_be_silently_ignored(self):
        for field in ("snapshot_quality", "historical_snapshot_quality", "quality", "unknown"):
            with pytest.raises(ValidationError):
                StructuralFeatures(formation_name="test", **{field: "TYPE_A"})

    def test_serialized_schema_forbids_extra_fields(self):
        schema = StructuralFeatures.model_json_schema()
        assert schema["additionalProperties"] is False
        assert "formation_type" not in schema["properties"]
        assert schema["required"] == ["formation_name"]

    def test_v1_fields_and_inactive_v3_fields_are_preserved(self):
        assert set(StructuralFeatures.model_fields) == {
            "formation_name", "width_feature", "line_height_feature",
            "defensive_cover_feature", "press_structure_feature",
            "build_up_structure_feature", "transition_structure_feature",
            "cb_pairing_quality", "fullback_exposure",
        }
        features = StructuralFeatures(formation_name="test")
        assert features.cb_pairing_quality == 0.5
        assert features.fullback_exposure == 0.5

    def test_structural_features_remain_frozen_and_bounded(self):
        features = StructuralFeatures(formation_name="test")
        with pytest.raises(ValidationError):
            features.width_feature = 0.9
        with pytest.raises(ValidationError):
            StructuralFeatures(formation_name="test", width_feature=1.1)

    def test_historical_quality_is_owned_by_layer1(self):
        assert HistoricalSnapshotQuality.__module__ == "football_engine.data_layer.snapshot_quality"
        assert {item.value for item in HistoricalSnapshotQuality} == {"TYPE_A", "TYPE_B", "TYPE_C"}

    def test_calibration_weight_mapping_is_exact_and_read_only(self):
        assert SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS[HistoricalSnapshotQuality.TYPE_A] == 1.0
        assert SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS[HistoricalSnapshotQuality.TYPE_B] == 0.5
        assert SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS[HistoricalSnapshotQuality.TYPE_C] == 0.2
        with pytest.raises(TypeError):
            SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS[HistoricalSnapshotQuality.TYPE_A] = 0.2

    def test_no_quality_default_or_unknown_quality_is_invented(self):
        with pytest.raises(TypeError):
            HistoricalSnapshotQuality()
        for value in ("UNKNOWN", "4-3-3", 1, None):
            with pytest.raises(ValueError):
                HistoricalSnapshotQuality(value)

    def test_historical_tier_remains_independent_and_unchanged(self):
        assert [(tier.name, tier.value) for tier in HistoricalTier] == [("TIER_1", 1), ("TIER_2", 2), ("TIER_3", 3)]
        assert HistoricalTier.TIER_1 != HistoricalSnapshotQuality.TYPE_A
        assert "snapshot_quality" not in TeamIdentity.model_fields
        assert "snapshot_quality" not in TeamDimensions.model_fields

    def test_core_and_runtime_engines_do_not_import_quality_metadata(self):
        root = Path(__file__).resolve().parents[1]
        for folder in ("core", "team_model", "matchup"):
            for path in (root / "football_engine" / folder).glob("*.py"):
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        assert node.module != "football_engine.data_layer.snapshot_quality", path.name
                    if isinstance(node, ast.Name):
                        assert node.id not in {"HistoricalSnapshotQuality", "SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS"}, path.name
