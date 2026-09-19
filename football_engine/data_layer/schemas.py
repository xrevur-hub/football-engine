"""
Layer 1 — Data Layer record schemas.

These models describe the *on-disk JSON record shape* for each dataset
(players, teams, formations, historical priors). They are deliberately
kept separate from the Layer 0 core models (PlayerSeason, TeamSeason,
Formation, HistoricalPrior in football_engine.core.*) rather than adding
fields onto those models directly, for two reasons:

  1. Non-goal discipline (Layer 1 requirement, README Section 26): Layer 1
     must not modify core model formulas or contracts. Adding
     provenance/versioning fields onto the frozen Layer 0 models would be
     a Layer 0 change, not a Layer 1 change.
  2. Separation of concerns: "source", "confidence", "retrieved_at",
     "dataset_version" etc. are catalog/provenance metadata about *how a
     record entered the system*, not attributes the simulation engine
     itself ever reads. Keeping them off the core models guarantees they
     can never accidentally leak into a calculation path (anti
     double-counting discipline, Section 9/46, extended here to mean
     "no non-model metadata reaches the model layer either").

Each *Record model here is a pure superset (JSON shape) that the loader
(loader.py) validates first, then narrows into the corresponding Layer 0
core model by stripping metadata before constructing the pydantic engine
object. This keeps referential validation and provenance bookkeeping in
Layer 1, and keeps the engine's frozen data contracts in Layer 0
untouched.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from football_engine.core.enums import HistoricalTier, PlayerRole
from football_engine.core.formation import SlotDepth, SlotSide


# ============================================================================
# Shared provenance metadata (L1.9)
# ============================================================================


class RecordStatus(str, Enum):
    """
    Lifecycle status of a data record's *values* (not its schema shape).

    PLACEHOLDER records exist only to exercise schema/referential-integrity
    plumbing (ids, roster references, formation slots, etc.) end-to-end
    before real historical data has been ingested. A PLACEHOLDER record's
    numeric attributes are not researched values — they must never be
    treated as historical ground truth, and must never be readable by a
    calibration or production simulation pipeline (see
    repository.py: filtering helpers exclude PLACEHOLDER by default).

    CURATED means a human has manually reviewed/entered the value.
    IMPORTED means it came from an ingestion pipeline from a named source
    but has not yet had a manual review pass.
    """

    PLACEHOLDER = "PLACEHOLDER"
    IMPORTED = "IMPORTED"
    CURATED = "CURATED"


class SourceMetadata(BaseModel):
    """
    Provenance metadata for a single data record (L1.9).

    `source` is intentionally a free-form string rather than an enum: the
    set of data providers is expected to grow as the dataset scales from
    ~40 to hundreds of TeamSeasons, and Layer 1 should not need a code
    change just to register a new provider name. `source` may be null
    only when `status` is PLACEHOLDER (there is, by definition, no real
    source for a placeholder value yet).

    `confidence` has no engine meaning (it is never read by the
    simulation core) — it exists purely so that future calibration or
    curation work (Layer 7) can prioritize which records to review first,
    per L1.9's stated purpose ("this is for future calibration and
    provenance"). PLACEHOLDER records must carry confidence == 0.0
    (enforced below) so a confidence-based sort can never accidentally
    surface fabricated values ahead of low-but-real-confidence imports.
    """

    model_config = ConfigDict(frozen=True)

    status: RecordStatus = Field(
        ..., description="PLACEHOLDER (fixture only), IMPORTED (from a named source), or CURATED (human-reviewed)"
    )
    source: str | None = Field(
        None, description='e.g. "manual_curation", "provider:fbref", "provider:transfermarkt"; null iff PLACEHOLDER'
    )
    retrieved_at: datetime | None = Field(None, description="When this record's values were captured")
    confidence: float = Field(
        0.0, ge=0.0, le=1.0, description="Curation confidence; PLACEHOLDER records must be 0.0"
    )
    manual_override: bool = Field(
        False, description="True if a human manually overrode a derived/imported value"
    )
    notes: str | None = Field(None, description="Free-text provenance note, e.g. why a value is placeholder")

    @model_validator(mode="after")
    def _placeholder_consistency(self) -> "SourceMetadata":
        """
        Structural guarantee that a PLACEHOLDER record cannot masquerade
        as real data: source must be absent and confidence must be
        exactly 0.0. This is what lets repository-level filtering
        (repository.py's `exclude_placeholder`) trust `status` alone
        without also having to re-check confidence/source everywhere.
        """
        if self.status == RecordStatus.PLACEHOLDER:
            if self.confidence != 0.0:
                raise ValueError(
                    f"SourceMetadata.status=PLACEHOLDER requires confidence == 0.0, got {self.confidence}"
                )
            if self.source is not None:
                raise ValueError("SourceMetadata.status=PLACEHOLDER requires source to be null")
        else:
            if self.source is None:
                raise ValueError(f"SourceMetadata.status={self.status} requires a non-null source")
        return self


class DatasetMetadata(BaseModel):
    """
    File-level versioning header (L1.10), expected at the top of every
    dataset JSON file (players.json, team_seasons.json, etc.) alongside
    the record list.
    """

    model_config = ConfigDict(frozen=True)

    dataset_version: str = Field(..., description='e.g. "2026.09.0"')
    schema_version: str = Field(..., description='e.g. "1.0" — matches this module\'s record schema shape')
    generated_at: datetime | None = None
    description: str | None = None


# ============================================================================
# L1.1 — PlayerSeason dataset record
# ============================================================================


class PlayerSeasonRecord(BaseModel):
    """
    On-disk shape for one PlayerSeason entry.

    Field set mirrors football_engine.core.player_season.PlayerSeason
    exactly (id, name, season, role, *_ability, *_tendency, pace,
    discipline_score, impact_score) plus a `metadata` block that never
    crosses into the core PlayerSeason object. Bounds here intentionally
    duplicate the core model's Field(ge=..., le=...) constraints so that
    malformed JSON is rejected at the data layer with a data-layer-shaped
    error, before ever reaching the core model constructor (L1.7).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1, description='e.g. "messi_2010_11"')
    name: str = Field(..., min_length=1)
    season: str = Field(..., min_length=1, description='e.g. "2010/11"')
    role: PlayerRole

    attack_ability: float = Field(..., ge=0, le=100)
    creation_ability: float = Field(..., ge=0, le=100)
    defense_ability: float = Field(..., ge=0, le=100)
    gk_ability: float = Field(0.0, ge=0, le=100)

    shot_tendency: float = Field(0.5, ge=0, le=1)
    press_tendency: float = Field(0.5, ge=0, le=1)
    transition_tendency: float = Field(0.5, ge=0, le=1)
    pace: float = Field(0.5, ge=0, le=1)

    discipline_score: float = Field(0.5, ge=0, le=1)
    impact_score: float = Field(0.5, ge=0, le=1)

    metadata: SourceMetadata

    @model_validator(mode="after")
    def _season_format(self) -> "PlayerSeasonRecord":
        """
        L1.5/L1.7 — season format validation.

        Expected shape: "YYYY/YY" (e.g. "2010/11"). This is a light
        structural check (not a calendar check), matching every example
        given in the architecture doc (Section 3.1, Section 33).
        """
        parts = self.season.split("/")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(
                f'PlayerSeasonRecord.season={self.season!r} is not in "YYYY/YY" format (e.g. "2010/11")'
            )
        if len(parts[0]) != 4 or len(parts[1]) != 2:
            raise ValueError(
                f'PlayerSeasonRecord.season={self.season!r} must be "YYYY/YY" '
                f"(4-digit year, 2-digit year), got parts {parts}"
            )
        return self

    @model_validator(mode="after")
    def _gk_ability_role_consistency(self) -> "PlayerSeasonRecord":
        """
        Section 4 / player_season.py docstring: "gk_ability nonzero only
        for GK role". We warn-via-error on the clear data-entry mistake
        (a non-GK with a large gk_ability looks like a copy-paste error)
        without being so strict that a GK-adjacent utility value of, say,
        1-2 on a sweeper-keeper-ish CB fails the whole dataset load. The
        threshold is deliberately generous; this is a sanity check, not a
        formula.
        """
        if self.role != PlayerRole.GK and self.gk_ability > 20.0:
            raise ValueError(
                f"PlayerSeasonRecord.id={self.id!r} has role={self.role} but "
                f"gk_ability={self.gk_ability} > 20; gk_ability should be ~0 for outfield players"
            )
        return self


class PlayerSeasonDataset(BaseModel):
    """Top-level shape of a player_seasons.json file."""

    model_config = ConfigDict(frozen=True)

    metadata: DatasetMetadata
    players: list[PlayerSeasonRecord] = Field(default_factory=list)


# ============================================================================
# L1.3 — Formation dataset record
# ============================================================================


class PositionSlotRecord(BaseModel):
    """
    On-disk mirror of football_engine.core.formation.PositionSlot.

    side/depth are additive Layer 0/core contract fields (see conversation
    record — "Option 3" decision on 2026-09-08): explicit structural
    geometry, required for every slot, never inferred from slot_id.
    """

    model_config = ConfigDict(frozen=True)

    slot_id: str = Field(..., min_length=1, description='e.g. "LCB", "RW", "DM" — identifier only')
    role: PlayerRole
    side: SlotSide
    depth: SlotDepth


class FormationRecord(BaseModel):
    """
    On-disk shape for one Formation template. Mirrors
    football_engine.core.formation.Formation (name + 11-slot position
    pool) exactly; no metadata needed beyond an optional note since
    formations are structural facts, not curated/sourced data the way
    player or team records are.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1, description='e.g. "4-3-3"')
    position_pool: list[PositionSlotRecord] = Field(..., min_length=11, max_length=11)
    notes: str | None = None

    @model_validator(mode="after")
    def _unique_slot_ids(self) -> "FormationRecord":
        ids = [slot.slot_id for slot in self.position_pool]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f'FormationRecord "{self.name}" has duplicate slot_id(s): {sorted(dupes)}')
        return self


class FormationDataset(BaseModel):
    """Top-level shape of a formations.json file."""

    model_config = ConfigDict(frozen=True)

    metadata: DatasetMetadata
    formations: list[FormationRecord] = Field(default_factory=list)


# ============================================================================
# L1.4 — Historical Prior dataset record
# ============================================================================


class IdentityPriorsRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    possession_tendency: float | None = Field(None, ge=0, le=1)
    press_tendency: float | None = Field(None, ge=0, le=1)
    transition_tendency: float | None = Field(None, ge=0, le=1)
    tempo: float | None = Field(None, ge=0, le=1)
    risk_tolerance: float | None = Field(None, ge=0, le=1)
    compactness: float | None = Field(None, ge=0, le=1)


class DimensionAdjustmentRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    attack: float = 0.0
    creation: float = 0.0
    defense: float = 0.0
    goalkeeping: float = 0.0


class HistoricalPriorRecord(BaseModel):
    """
    On-disk shape for one HistoricalPrior, keyed by team_season_id in the
    dataset file (see HistoricalPriorDataset below) rather than embedded
    inline in team_seasons.json. Kept as its own file/dataset (L1.4;
    matches the directory layout the user specified) so historical-prior
    curation can be reviewed/edited independently of roster data.
    """

    model_config = ConfigDict(frozen=True)

    team_season_id: str = Field(..., min_length=1, description="Must match a TeamSeasonRecord.id")
    tier: HistoricalTier
    alpha: float = Field(..., ge=0, le=1)
    identity_priors: IdentityPriorsRecord = Field(default_factory=IdentityPriorsRecord)
    dimension_adjustment: DimensionAdjustmentRecord = Field(default_factory=DimensionAdjustmentRecord)
    metadata: SourceMetadata

    @model_validator(mode="after")
    def _tier3_alpha_is_one(self) -> "HistoricalPriorRecord":
        """Section 31 — Tier 3 requires alpha == 1.0 (mirrors core HistoricalPrior check,
        enforced again here so a malformed data file fails at load time with a
        data-layer error rather than only at core-model construction time)."""
        if self.tier == HistoricalTier.TIER_3 and self.alpha != 1.0:
            raise ValueError(
                f"HistoricalPriorRecord for {self.team_season_id!r}: "
                f"tier=TIER_3 requires alpha == 1.0, got {self.alpha}"
            )
        return self


class HistoricalPriorDataset(BaseModel):
    """Top-level shape of a historical_priors.json file."""

    model_config = ConfigDict(frozen=True)

    metadata: DatasetMetadata
    priors: list[HistoricalPriorRecord] = Field(default_factory=list)


# ============================================================================
# L1.2 — TeamSeason dataset record
# ============================================================================


class TeamSeasonRecord(BaseModel):
    """
    On-disk shape for one TeamSeason entry.

    `roster` holds PlayerSeason id *references* only (L1.2: "avoid
    duplicate player objects in TeamSeason") — never inline player data.
    `historical_prior_ref` is an optional reference into
    historical_priors.json (by team_season_id); a team with no curated
    history simply omits it, matching HistoricalPrior=None semantics in
    the core TeamSeason model (Section 33: fully generic derivation).

    `default_formation` is optional data-layer convenience (which
    Formation.name a team is most associated with historically) — it is
    NOT part of the core TeamSeason contract and is not required for the
    core model construction; it exists only so a Layer 2+ consumer has a
    sensible default without hardcoding formation choices in code.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., min_length=1, description='e.g. "barcelona_2010_11"')
    club: str = Field(..., min_length=1)
    season: str = Field(..., min_length=1, description='e.g. "2010/11"')
    roster: list[str] = Field(..., min_length=1, description="PlayerSeason id references")
    default_formation: str | None = Field(None, description='Formation.name reference, e.g. "4-3-3"')
    metadata: SourceMetadata

    @model_validator(mode="after")
    def _season_format(self) -> "TeamSeasonRecord":
        parts = self.season.split("/")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit() or len(parts[0]) != 4 or len(parts[1]) != 2:
            raise ValueError(f'TeamSeasonRecord.season={self.season!r} is not in "YYYY/YY" format (e.g. "2010/11")')
        return self

    @model_validator(mode="after")
    def _no_duplicate_roster_refs(self) -> "TeamSeasonRecord":
        dupes = {p for p in self.roster if self.roster.count(p) > 1}
        if dupes:
            raise ValueError(f"TeamSeasonRecord.id={self.id!r} roster has duplicate player id(s): {sorted(dupes)}")
        return self


class TeamSeasonDataset(BaseModel):
    """Top-level shape of a team_seasons.json file."""

    model_config = ConfigDict(frozen=True)

    metadata: DatasetMetadata
    teams: list[TeamSeasonRecord] = Field(default_factory=list)
