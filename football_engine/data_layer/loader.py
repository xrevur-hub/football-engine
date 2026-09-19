"""
Layer 1 — Dataset Loader.

Pipeline (L1.6, extended per explicit user requirement to a 4-stage
provenance pipeline):

    RAW SOURCE  ->  INGESTION/CURATION  ->  NORMALIZED (engine-ready JSON)
        ->  VALIDATION (this module)  ->  in-memory repository

This loader reads from the NORMALIZED stage only (data/<kind>/*.json —
see load_all()'s docstring for the exact layout). It never reads
data/raw/ directly: raw source dumps are ingestion's input, not this
loader's — keeping "ingestion" and "the data the engine actually
consumes" as two separate, independently-editable stages (explicit user
requirement: raw -> normalized -> validated -> engine-ready must not be
conflated).

Load order matters for referential integrity (L1.5) and is fixed here:

    1. players            (no references out)
    2. formations         (no references out)
    3. teams              (references PlayerSeason ids, optionally a
                            Formation name)
    4. historical_priors  (references TeamSeason ids — validated once
                            teams are known)

Because HistoricalPriorRecord references team_season_id and
TeamSeasonRecord references PlayerSeason ids, there's a mutual-looking
dependency; we resolve it by loading+validating players and formations
first (no dependencies), then teams (validated against the already-loaded
player repository), then historical priors (validated against the
already-loaded team repository), and finally re-attaching each team's
HistoricalPrior onto its core TeamSeason object. This keeps every
reference check a simple "does this id exist in an already-built
repository" lookup — no forward references, no two-pass team loading.

PLACEHOLDER handling: the loader itself loads *everything*, placeholder
or not — filtering placeholders out is a read-time concern for
repository consumers (see repository.py), not a load-time concern. A
loader that silently dropped placeholders would make it impossible to
even test that placeholder records validate correctly.

This module intentionally does not import anything from Layer 2+ (Team
Model, Matchup, lambda, simulation) — Layer 1 non-goals, Section 26.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from football_engine.core.formation import Formation, PositionSlot
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_season import (
    DimensionAdjustment,
    HistoricalPrior,
    IdentityPriors,
    TeamSeason,
)
from football_engine.data_layer.exceptions import (
    DatasetFileError,
    DuplicateIdError,
    InvalidFormationAssignmentError,
    SchemaValidationError,
    UnknownReferenceError,
)
from football_engine.data_layer.repository import (
    DataRepositories,
    FormationRepository,
    HistoricalPriorRepository,
    PlayerRepository,
    TeamSeasonRepository,
)
from football_engine.data_layer.schemas import (
    FormationDataset,
    HistoricalPriorDataset,
    PlayerSeasonDataset,
    TeamSeasonDataset,
)

_SUPPORTED_SCHEMA_VERSIONS = {"1.0"}


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        raise DatasetFileError(f'Dataset file not found: "{path}"')
    if not path.is_file():
        raise DatasetFileError(f'Dataset path is not a file: "{path}"')
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise DatasetFileError(f'Could not read dataset file "{path}": {e}') from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise DatasetFileError(f'Dataset file "{path}" is not valid JSON: {e}') from e


def _check_schema_version(dataset_version: str, schema_version: str, path: Path) -> None:
    """
    L1.10 — versioning check.

    We don't hard-fail on an *unrecognized* dataset_version (that's free
    text, meant to move independently of code), but schema_version must
    match a version this loader actually knows how to read, since it
    determines the record shape we're about to validate against.
    """
    if schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        raise SchemaValidationError(
            f'Dataset file "{path}": unsupported schema_version="{schema_version}" '
            f"(loader supports: {sorted(_SUPPORTED_SCHEMA_VERSIONS)}). "
            f"dataset_version was \"{dataset_version}\"."
        )


def load_player_dataset(path: Path) -> tuple[PlayerSeasonDataset, PlayerRepository]:
    """Load and validate a player_seasons.json file into a PlayerRepository."""
    raw = _read_json_file(path)
    try:
        dataset = PlayerSeasonDataset.model_validate(raw)
    except ValidationError as e:
        raise SchemaValidationError(f'Invalid PlayerSeason data in "{path}":\n{e}') from e

    _check_schema_version(dataset.metadata.dataset_version, dataset.metadata.schema_version, path)

    repo = PlayerRepository()
    for record in dataset.players:
        player = PlayerSeason(
            id=record.id,
            name=record.name,
            season=record.season,
            role=record.role,
            attack_ability=record.attack_ability,
            creation_ability=record.creation_ability,
            defense_ability=record.defense_ability,
            gk_ability=record.gk_ability,
            shot_tendency=record.shot_tendency,
            press_tendency=record.press_tendency,
            transition_tendency=record.transition_tendency,
            pace=record.pace,
            discipline_score=record.discipline_score,
            impact_score=record.impact_score,
        )
        try:
            repo.add(player, status=record.metadata.status)
        except DuplicateIdError as e:
            raise DuplicateIdError(f'In "{path}": {e}') from e
    return dataset, repo


def load_formation_dataset(path: Path) -> tuple[FormationDataset, FormationRepository]:
    """Load and validate a formations.json file into a FormationRepository."""
    raw = _read_json_file(path)
    try:
        dataset = FormationDataset.model_validate(raw)
    except ValidationError as e:
        raise SchemaValidationError(f'Invalid Formation data in "{path}":\n{e}') from e

    _check_schema_version(dataset.metadata.dataset_version, dataset.metadata.schema_version, path)

    repo = FormationRepository()
    for record in dataset.formations:
        formation = Formation(
            name=record.name,
            position_pool=[
                PositionSlot(slot_id=slot.slot_id, role=slot.role, side=slot.side, depth=slot.depth)
                for slot in record.position_pool
            ],
        )
        try:
            repo.add(formation)
        except DuplicateIdError as e:
            raise DuplicateIdError(f'In "{path}": {e}') from e
    return dataset, repo


def load_team_dataset(
    path: Path,
    player_repo: PlayerRepository,
    formation_repo: FormationRepository | None = None,
) -> tuple[TeamSeasonDataset, TeamSeasonRepository]:
    """
    Load and validate a team_seasons.json file into a TeamSeasonRepository.

    Referential integrity enforced here (L1.5):
      - every roster entry must resolve against player_repo (checked
        against ALL players including placeholders — a roster reference
        to a placeholder player is a valid reference, just not a
        production-ready one; see DataRepositories.production_ready_team_ids)
      - default_formation, if set, must resolve against formation_repo
        (when a formation_repo is supplied; team datasets can be loaded
        standalone for tests that don't care about formations)

    historical_prior is intentionally NOT attached here — it is attached
    afterward by load_all() once historical_priors.json has also been
    loaded, since HistoricalPriorRecord references team_season_id (see
    module docstring for the load-order rationale).
    """
    raw = _read_json_file(path)
    try:
        dataset = TeamSeasonDataset.model_validate(raw)
    except ValidationError as e:
        raise SchemaValidationError(f'Invalid TeamSeason data in "{path}":\n{e}') from e

    _check_schema_version(dataset.metadata.dataset_version, dataset.metadata.schema_version, path)

    known_player_ids = player_repo.ids(include_placeholder=True)

    repo = TeamSeasonRepository()
    for record in dataset.teams:
        missing_players = [pid for pid in record.roster if pid not in known_player_ids]
        if missing_players:
            raise UnknownReferenceError(
                f'TeamSeasonRecord "{record.id}" in "{path}" references unknown PlayerSeason '
                f"id(s): {missing_players}"
            )
        if record.default_formation is not None and formation_repo is not None:
            if record.default_formation not in formation_repo:
                raise InvalidFormationAssignmentError(
                    f'TeamSeasonRecord "{record.id}" in "{path}" references unknown Formation '
                    f'"{record.default_formation}"'
                )

        team = TeamSeason(
            id=record.id,
            club=record.club,
            season=record.season,
            roster=list(record.roster),
            historical_prior=None,  # attached later, see load_all()
        )
        try:
            repo.add(team, status=record.metadata.status, default_formation=record.default_formation)
        except DuplicateIdError as e:
            raise DuplicateIdError(f'In "{path}": {e}') from e
    return dataset, repo


def load_historical_prior_dataset(
    path: Path,
    team_repo: TeamSeasonRepository,
) -> tuple[HistoricalPriorDataset, HistoricalPriorRepository]:
    """Load and validate a historical_priors.json file into a HistoricalPriorRepository."""
    raw = _read_json_file(path)
    try:
        dataset = HistoricalPriorDataset.model_validate(raw)
    except ValidationError as e:
        raise SchemaValidationError(f'Invalid HistoricalPrior data in "{path}":\n{e}') from e

    _check_schema_version(dataset.metadata.dataset_version, dataset.metadata.schema_version, path)

    known_team_ids = team_repo.ids(include_placeholder=True)

    repo = HistoricalPriorRepository()
    for record in dataset.priors:
        if record.team_season_id not in known_team_ids:
            raise UnknownReferenceError(
                f'HistoricalPriorRecord in "{path}" references unknown TeamSeason '
                f'id "{record.team_season_id}"'
            )
        prior = HistoricalPrior(
            tier=record.tier,
            alpha=record.alpha,
            identity_priors=IdentityPriors(**record.identity_priors.model_dump()),
            dimension_adjustment=DimensionAdjustment(**record.dimension_adjustment.model_dump()),
        )
        try:
            repo.add(record.team_season_id, prior, status=record.metadata.status)
        except DuplicateIdError as e:
            raise DuplicateIdError(f'In "{path}": {e}') from e
    return dataset, repo


def load_all(data_dir: Path) -> DataRepositories:
    """
    Load the full Layer 1 dataset from a directory laid out as:

        data_dir/
            players/player_seasons.json
            formations/formations.json
            teams/team_seasons.json
            historical_priors/historical_priors.json

    This is the NORMALIZED, engine-ready stage (explicit user
    requirement to keep raw -> normalized -> validated -> engine-ready
    distinct): data_dir here is expected to be e.g. `data/normalized/`,
    not `data/raw/`. Ingestion code (not part of Layer 1) is responsible
    for producing files in this shape from whatever raw source it reads.

    Returns a DataRepositories bundle with every cross-reference already
    validated (L1.5) and every TeamSeason's historical_prior attached
    where one exists. PLACEHOLDER records are loaded like any other
    record — use DataRepositories/repository filtering at read time to
    exclude them from production/calibration use.

    Raises DataLayerError subclasses (see exceptions.py) with a message
    identifying the offending file/record on any validation failure.
    """
    data_dir = Path(data_dir)

    _, player_repo = load_player_dataset(data_dir / "players" / "player_seasons.json")
    _, formation_repo = load_formation_dataset(data_dir / "formations" / "formations.json")
    _, team_repo = load_team_dataset(
        data_dir / "teams" / "team_seasons.json", player_repo, formation_repo
    )
    _, prior_repo = load_historical_prior_dataset(
        data_dir / "historical_priors" / "historical_priors.json", team_repo
    )

    # Re-attach historical priors onto their TeamSeason objects. TeamSeason
    # is frozen (immutable), so we rebuild it via model_copy(update=...)
    # rather than mutating in place — this preserves the "TeamSeason is
    # immutable catalog data" contract (team_season.py docstring) while
    # still letting Layer 1 assemble the fully-populated object.
    #
    # include_placeholder=True here is required: this loop must carry
    # EVERY loaded team forward (placeholder or not) into the final
    # repository. Filtering happens at read time via
    # TeamSeasonRepository.all(include_placeholder=False), not here —
    # dropping placeholders at load time would make it impossible to
    # even validate that they load correctly.
    final_team_repo = TeamSeasonRepository()
    for team in team_repo.all(include_placeholder=True):
        prior = prior_repo.get(team.id)
        final_team = team.model_copy(update={"historical_prior": prior}) if prior is not None else team
        final_team_repo.add(
            final_team,
            status=team_repo.status_of(team.id),
            default_formation=team_repo.default_formation_name(team.id),
        )

    return DataRepositories(
        players=player_repo,
        teams=final_team_repo,
        formations=formation_repo,
        historical_priors=prior_repo,
    )
