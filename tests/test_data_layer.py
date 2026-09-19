"""
Layer 1 — Architecture/data-layer tests.

Covers the checklist from the Layer 1 requirements (README-equivalent
Section 27):
  1. valid PlayerSeason loads
  2. invalid player attribute rejected
  3. duplicate player ID rejected
  4. valid TeamSeason loads
  5. missing roster reference rejected
  6. valid formation loads
  7. invalid formation assignment rejected
  8. historical prior validation
  9. Tier 3 alpha == 1.0 (enforced by the core model; a Tier 3
     HistoricalPriorRecord with alpha != 1.0 is also rejected at the
     data layer)
  10. repository lookup works
  11. all seeded teams load
  12. no duplicate TeamSeason IDs
  13. every team roster resolves
  14. schema version is valid

Plus additional tests for the explicit PLACEHOLDER-safety requirement
(placeholder records must be excludable from production/calibration use)
and the "no duplicate slot_id in a formation" / "no duplicate roster
entry" checks added during implementation.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from football_engine.core.enums import HistoricalTier, PlayerRole
from football_engine.data_layer.exceptions import (
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
from football_engine.data_layer.repository import DataRepositories, FormationRepository
from football_engine.data_layer.schemas import PlayerSeasonRecord, RecordStatus, SourceMetadata

from tests.conftest import (
    curated_metadata,
    make_formation,
    make_player,
    make_team,
    minimal_dataset_metadata,
    placeholder_metadata,
    write_json,
)


# ============================================================================
# 1. Valid PlayerSeason loads
# ============================================================================


def test_valid_player_season_loads(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")
    assert "p1" in repo
    assert repo.get("p1").role == PlayerRole.CM


# ============================================================================
# 2. Invalid player attribute rejected
# ============================================================================


def test_invalid_player_attribute_rejected(tmp_dataset_dir):
    bad_player = make_player("p1", attack_ability=150.0)  # out of [0, 100]
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [bad_player]},
    )
    with pytest.raises(SchemaValidationError):
        load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")


def test_invalid_season_format_rejected(tmp_dataset_dir):
    bad_player = make_player("p1", season="not-a-season")
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [bad_player]},
    )
    with pytest.raises(SchemaValidationError):
        load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")


def test_gk_ability_role_mismatch_rejected(tmp_dataset_dir):
    bad_player = make_player("p1", role="CM", gk_ability=90.0)
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [bad_player]},
    )
    with pytest.raises(SchemaValidationError):
        load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")


# ============================================================================
# 3. Duplicate player ID rejected
# ============================================================================


def test_duplicate_player_id_rejected(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("dup"), make_player("dup")]},
    )
    with pytest.raises(DuplicateIdError):
        load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")


# ============================================================================
# 4. Valid TeamSeason loads
# ============================================================================


def test_valid_team_season_loads(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1"), make_player("p2")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {"metadata": minimal_dataset_metadata(), "teams": [make_team("team_a", ["p1", "p2"])]},
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)
    assert "team_a" in team_repo
    assert team_repo.get("team_a").roster == ["p1", "p2"]


# ============================================================================
# 5. Missing roster reference rejected
# ============================================================================


def test_missing_roster_reference_rejected(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {"metadata": minimal_dataset_metadata(), "teams": [make_team("team_a", ["p1", "nonexistent_player"])]},
    )
    with pytest.raises(UnknownReferenceError):
        load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)


def test_duplicate_roster_entry_rejected(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {"metadata": minimal_dataset_metadata(), "teams": [make_team("team_a", ["p1", "p1"])]},
    )
    with pytest.raises(SchemaValidationError):
        load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)


# ============================================================================
# 6. Valid formation loads
# ============================================================================


def test_valid_formation_loads(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "formations" / "formations.json",
        {"metadata": minimal_dataset_metadata(), "formations": [make_formation("4-3-3")]},
    )
    _, repo = load_formation_dataset(tmp_dataset_dir / "formations" / "formations.json")
    assert "4-3-3" in repo
    assert len(repo.get("4-3-3").position_pool) == 11


def test_formation_wrong_slot_count_rejected(tmp_dataset_dir):
    formation = make_formation("bad")
    formation["position_pool"] = formation["position_pool"][:10]  # only 10 slots
    write_json(
        tmp_dataset_dir / "formations" / "formations.json",
        {"metadata": minimal_dataset_metadata(), "formations": [formation]},
    )
    with pytest.raises(SchemaValidationError):
        load_formation_dataset(tmp_dataset_dir / "formations" / "formations.json")


def test_formation_duplicate_slot_id_rejected(tmp_dataset_dir):
    formation = make_formation("bad")
    formation["position_pool"][1]["slot_id"] = formation["position_pool"][0]["slot_id"]
    write_json(
        tmp_dataset_dir / "formations" / "formations.json",
        {"metadata": minimal_dataset_metadata(), "formations": [formation]},
    )
    with pytest.raises(SchemaValidationError):
        load_formation_dataset(tmp_dataset_dir / "formations" / "formations.json")


# ============================================================================
# 7. Invalid formation assignment rejected
# ============================================================================


def test_invalid_default_formation_reference_rejected(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    write_json(
        tmp_dataset_dir / "formations" / "formations.json",
        {"metadata": minimal_dataset_metadata(), "formations": [make_formation("4-3-3")]},
    )
    _, formation_repo = load_formation_dataset(tmp_dataset_dir / "formations" / "formations.json")

    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {
            "metadata": minimal_dataset_metadata(),
            "teams": [make_team("team_a", ["p1"], default_formation="9-9-9-nonexistent")],
        },
    )
    with pytest.raises(InvalidFormationAssignmentError):
        load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo, formation_repo)


# ============================================================================
# 8/9. Historical prior validation, Tier 3 alpha == 1.0
# ============================================================================


def test_historical_prior_valid_loads(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")
    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {"metadata": minimal_dataset_metadata(), "teams": [make_team("team_a", ["p1"])]},
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)

    write_json(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json",
        {
            "metadata": minimal_dataset_metadata(),
            "priors": [
                {
                    "team_season_id": "team_a",
                    "tier": 1,
                    "alpha": 0.55,
                    "metadata": placeholder_metadata(),
                }
            ],
        },
    )
    _, prior_repo = load_historical_prior_dataset(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json", team_repo
    )
    prior = prior_repo.get("team_a")
    assert prior is not None
    assert prior.tier == HistoricalTier.TIER_1
    assert prior.alpha == 0.55


def test_historical_prior_unknown_team_rejected(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")
    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {"metadata": minimal_dataset_metadata(), "teams": [make_team("team_a", ["p1"])]},
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)

    write_json(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json",
        {
            "metadata": minimal_dataset_metadata(),
            "priors": [
                {
                    "team_season_id": "nonexistent_team",
                    "tier": 3,
                    "alpha": 1.0,
                    "metadata": placeholder_metadata(),
                }
            ],
        },
    )
    with pytest.raises(UnknownReferenceError):
        load_historical_prior_dataset(
            tmp_dataset_dir / "historical_priors" / "historical_priors.json", team_repo
        )


def test_tier3_alpha_must_be_one(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")
    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {"metadata": minimal_dataset_metadata(), "teams": [make_team("team_a", ["p1"])]},
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)

    write_json(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json",
        {
            "metadata": minimal_dataset_metadata(),
            "priors": [
                {
                    "team_season_id": "team_a",
                    "tier": 3,
                    "alpha": 0.9,  # invalid: Tier 3 requires alpha == 1.0
                    "metadata": placeholder_metadata(),
                }
            ],
        },
    )
    with pytest.raises(SchemaValidationError):
        load_historical_prior_dataset(
            tmp_dataset_dir / "historical_priors" / "historical_priors.json", team_repo
        )


def test_tier3_alpha_one_is_accepted(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")
    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {"metadata": minimal_dataset_metadata(), "teams": [make_team("team_a", ["p1"])]},
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)

    write_json(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json",
        {
            "metadata": minimal_dataset_metadata(),
            "priors": [
                {
                    "team_season_id": "team_a",
                    "tier": 3,
                    "alpha": 1.0,
                    "metadata": placeholder_metadata(),
                }
            ],
        },
    )
    _, prior_repo = load_historical_prior_dataset(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json", team_repo
    )
    assert prior_repo.get("team_a").alpha == 1.0


# ============================================================================
# 10. Repository lookup works
# ============================================================================


def test_repository_lookup_works(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1")]},
    )
    _, repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")
    assert repo.get("p1").id == "p1"
    with pytest.raises(UnknownReferenceError):
        repo.get("does_not_exist")
    assert len(repo) == 1
    assert repo.ids(include_placeholder=True) == {"p1"}


# ============================================================================
# 11-13. Seed dataset: all teams load, no duplicate ids, every roster resolves
# ============================================================================


def test_seed_dataset_loads_completely(seed_data_dir):
    repos = load_all(seed_data_dir)
    assert isinstance(repos, DataRepositories)
    # Our dataset now has 36 teams (2 real + 34 synthetic), all CURATED/IMPORTED
    teams = repos.teams.all(include_placeholder=True)
    assert len(teams) == 36, f"Expected 36 teams, got {len(teams)}"
    # No placeholders remain in production-ready data
    for t in teams:
        assert repos.teams.status_of(t.id) != RecordStatus.PLACEHOLDER


def test_seed_dataset_no_duplicate_team_ids(seed_data_dir):
    repos = load_all(seed_data_dir)
    ids = [t.id for t in repos.teams.all(include_placeholder=True)]
    assert len(ids) == len(set(ids)), f"duplicate TeamSeason ids found: {ids}"


def test_seed_dataset_every_roster_resolves(seed_data_dir):
    repos = load_all(seed_data_dir)
    for team in repos.teams.all(include_placeholder=True):
        for player_id in team.roster:
            assert player_id in repos.players, (
                f'team "{team.id}" roster references unresolved player "{player_id}"'
            )


def test_seed_dataset_tier_coverage(seed_data_dir):
    """Sanity check that the seed data actually exercises all three tiers."""
    repos = load_all(seed_data_dir)
    # Tier 1: Barcelona 2010/11 (iconic)
    barcelona = repos.teams.get("barcelona_2010_11")
    assert barcelona is not None, "Barcelona 2010/11 should exist"
    assert barcelona.historical_prior is not None
    assert barcelona.historical_prior.tier == HistoricalTier.TIER_1

    # Tier 1: Chelsea 2011/12 (also iconic)
    chelsea = repos.teams.get("chelsea_2011_12")
    assert chelsea is not None, "Chelsea 2011/12 should exist"
    assert chelsea.historical_prior is not None
    assert chelsea.historical_prior.tier == HistoricalTier.TIER_1

    # Tier 3: one of the synthetic teams (generic, no prior)
    # All synthetic teams are Tier 3 (no curated prior)
    any_synthetic = next(t for t in repos.teams.all(include_placeholder=False)
                         if t.id.endswith("2015_16"))
    assert any_synthetic.historical_prior is None  # Tier 3 = no curated prior


# ============================================================================
# 14. Schema version is valid
# ============================================================================


def test_unsupported_schema_version_rejected(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {
            "metadata": {"dataset_version": "2026.09.0", "schema_version": "99.9"},
            "players": [make_player("p1")],
        },
    )
    with pytest.raises(SchemaValidationError):
        load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")


def test_seed_dataset_schema_versions_are_supported(seed_data_dir):
    # load_all() itself will raise if any file's schema_version is unsupported;
    # a clean load is the assertion.
    load_all(seed_data_dir)


# ============================================================================
# File-level error handling (L1.7 — debuggable error messages)
# ============================================================================


def test_missing_file_raises_dataset_file_error(tmp_dataset_dir):
    with pytest.raises(DatasetFileError):
        load_player_dataset(tmp_dataset_dir / "players" / "does_not_exist.json")


def test_malformed_json_raises_dataset_file_error(tmp_dataset_dir):
    path = tmp_dataset_dir / "players" / "player_seasons.json"
    path.write_text("{ this is not valid json", encoding="utf-8")
    with pytest.raises(DatasetFileError):
        load_player_dataset(path)


# ============================================================================
# PLACEHOLDER safety (explicit user requirement)
# ============================================================================


def test_placeholder_metadata_requires_confidence_zero_and_null_source():
    with pytest.raises(ValidationError):
        SourceMetadata(status=RecordStatus.PLACEHOLDER, source=None, confidence=0.3)
    with pytest.raises(ValidationError):
        SourceMetadata(status=RecordStatus.PLACEHOLDER, source="some_source", confidence=0.0)
    # valid placeholder:
    meta = SourceMetadata(status=RecordStatus.PLACEHOLDER, source=None, confidence=0.0)
    assert meta.status == RecordStatus.PLACEHOLDER


def test_non_placeholder_requires_source():
    with pytest.raises(ValidationError):
        SourceMetadata(status=RecordStatus.CURATED, source=None, confidence=0.8)
    meta = SourceMetadata(status=RecordStatus.CURATED, source="manual_curation", confidence=0.8)
    assert meta.source == "manual_curation"


def test_player_repository_excludes_placeholders_by_default(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {
            "metadata": minimal_dataset_metadata(),
            "players": [
                make_player("placeholder_p", metadata=placeholder_metadata()),
                make_player("curated_p", metadata=curated_metadata()),
            ],
        },
    )
    _, repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    # both loaded
    assert "placeholder_p" in repo
    assert "curated_p" in repo

    # default all() excludes placeholders
    default_ids = {p.id for p in repo.all()}
    assert default_ids == {"curated_p"}

    # explicit opt-in includes everything
    all_ids = {p.id for p in repo.all(include_placeholder=True)}
    assert all_ids == {"placeholder_p", "curated_p"}

    assert repo.is_placeholder("placeholder_p") is True
    assert repo.is_placeholder("curated_p") is False


def test_team_repository_excludes_placeholders_by_default(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {"metadata": minimal_dataset_metadata(), "players": [make_player("p1", metadata=curated_metadata())]},
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {
            "metadata": minimal_dataset_metadata(),
            "teams": [
                make_team("placeholder_team", ["p1"], metadata=placeholder_metadata()),
                make_team("curated_team", ["p1"], metadata=curated_metadata()),
            ],
        },
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)

    assert {t.id for t in team_repo.all()} == {"curated_team"}
    assert {t.id for t in team_repo.all(include_placeholder=True)} == {"placeholder_team", "curated_team"}


def test_seed_dataset_has_production_ready_teams(seed_data_dir):
    """
    Our dataset now has 36 production-ready teams (2 real + 34 synthetic).
    All teams are CURATED/IMPORTED, no placeholders remain.
    """
    repos = load_all(seed_data_dir)
    ready = repos.production_ready_team_ids()
    assert len(ready) == 36
    # Verify both real teams are included
    assert "barcelona_2010_11" in ready
    assert "chelsea_2011_12" in ready


def test_production_ready_requires_team_and_roster_both_non_placeholder(tmp_dataset_dir):
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {
            "metadata": minimal_dataset_metadata(),
            "players": [
                make_player("curated_p", metadata=curated_metadata()),
                make_player("placeholder_p", metadata=placeholder_metadata()),
            ],
        },
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {
            "metadata": minimal_dataset_metadata(),
            "teams": [
                # team record itself curated, but roster has a placeholder player -> not ready
                make_team("mixed_team", ["curated_p", "placeholder_p"], metadata=curated_metadata()),
                # fully curated team+roster -> ready
                make_team("ready_team", ["curated_p"], metadata=curated_metadata()),
                # placeholder team -> never ready regardless of roster
                make_team("placeholder_team", ["curated_p"], metadata=placeholder_metadata()),
            ],
        },
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)

    write_json(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json",
        {"metadata": minimal_dataset_metadata(), "priors": []},
    )
    _, prior_repo = load_historical_prior_dataset(
        tmp_dataset_dir / "historical_priors" / "historical_priors.json", team_repo
    )

    repos = DataRepositories(
        players=player_repo,
        teams=team_repo,
        formations=FormationRepository(),
        historical_priors=prior_repo,
    )
    assert repos.production_ready_team_ids() == {"ready_team"}


# ============================================================================
# Adding a new team requires only data, not code (structural demonstration)
# ============================================================================


def test_new_team_can_be_added_via_data_only(tmp_dataset_dir):
    """
    Demonstrates the extensibility requirement: adding
    "netherlands_1974" requires writing JSON only, touching zero engine
    Python code. This test constructs that JSON purely as data (dicts),
    proving the loader has no hardcoded team list anywhere.
    """
    write_json(
        tmp_dataset_dir / "players" / "player_seasons.json",
        {
            "metadata": minimal_dataset_metadata(),
            "players": [make_player(f"p{i}") for i in range(11)],
        },
    )
    _, player_repo = load_player_dataset(tmp_dataset_dir / "players" / "player_seasons.json")

    write_json(
        tmp_dataset_dir / "teams" / "team_seasons.json",
        {
            "metadata": minimal_dataset_metadata(),
            "teams": [make_team("netherlands_1974", [f"p{i}" for i in range(11)])],
        },
    )
    _, team_repo = load_team_dataset(tmp_dataset_dir / "teams" / "team_seasons.json", player_repo)
    assert "netherlands_1974" in team_repo
    assert len(team_repo.get("netherlands_1974").roster) == 11
