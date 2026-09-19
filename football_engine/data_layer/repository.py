"""
Layer 1 — in-memory repositories.

Each repository holds *validated* Layer 0 core-model instances (not the
raw data-layer *Record objects — those are an intermediate JSON-shape
representation consumed by the loader and then discarded, per the
schemas.py module docstring). Repositories are the read API that Layer 2+
code is expected to depend on; they never expose the full metadata block
that recorded provenance for curation purposes only (L1.9) — except for
`status`, which is tracked alongside each entity specifically so callers
can filter out PLACEHOLDER records (see `all(include_placeholder=...)`
below and `DataRepositories.production_ready_team_ids`).

These are intentionally plain in-memory dict wrappers — no database, no
external API dependency (Layer 1 non-goal list, Section 26) — since the
Layer 1 requirement (L1.6) is exactly "JSON → Pydantic validation →
in-memory repository", nothing more.

PLACEHOLDER SAFETY (explicit user requirement): PLACEHOLDER records exist
only to exercise schema/referential-integrity plumbing before real
historical data is ingested. They must never silently reach a
calibration or production simulation pipeline. Every repository defaults
`all()` to EXCLUDING placeholders; callers that genuinely want
placeholders too (e.g. Layer 1's own tests) must opt in explicitly with
`include_placeholder=True`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from football_engine.core.formation import Formation
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_season import HistoricalPrior, TeamSeason
from football_engine.data_layer.exceptions import DuplicateIdError, UnknownReferenceError
from football_engine.data_layer.schemas import RecordStatus


@dataclass
class PlayerRepository:
    """Lookup of PlayerSeason by id, with PLACEHOLDER-status tracking."""

    _by_id: dict[str, PlayerSeason] = field(default_factory=dict)
    _status: dict[str, RecordStatus] = field(default_factory=dict)

    def add(self, player: PlayerSeason, status: RecordStatus) -> None:
        if player.id in self._by_id:
            raise DuplicateIdError(f'Duplicate PlayerSeason id: "{player.id}"')
        self._by_id[player.id] = player
        self._status[player.id] = status

    def get(self, player_id: str) -> PlayerSeason:
        try:
            return self._by_id[player_id]
        except KeyError:
            raise UnknownReferenceError(f'Unknown PlayerSeason reference: "{player_id}"') from None

    def status_of(self, player_id: str) -> RecordStatus:
        if player_id not in self._status:
            raise UnknownReferenceError(f'Unknown PlayerSeason reference: "{player_id}"')
        return self._status[player_id]

    def is_placeholder(self, player_id: str) -> bool:
        return self.status_of(player_id) == RecordStatus.PLACEHOLDER

    def __contains__(self, player_id: str) -> bool:
        return player_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)

    def all(self, include_placeholder: bool = False) -> list[PlayerSeason]:
        if include_placeholder:
            return list(self._by_id.values())
        return [p for p in self._by_id.values() if self._status[p.id] != RecordStatus.PLACEHOLDER]

    def ids(self, include_placeholder: bool = False) -> set[str]:
        return {p.id for p in self.all(include_placeholder=include_placeholder)}


@dataclass
class FormationRepository:
    """Lookup of Formation by name (e.g. "4-3-3"). Formations are structural
    templates, not provenance-tracked data (see schemas.py FormationRecord
    docstring), so no PLACEHOLDER concept applies here."""

    _by_name: dict[str, Formation] = field(default_factory=dict)

    def add(self, formation: Formation) -> None:
        if formation.name in self._by_name:
            raise DuplicateIdError(f'Duplicate Formation name: "{formation.name}"')
        self._by_name[formation.name] = formation

    def get(self, name: str) -> Formation:
        try:
            return self._by_name[name]
        except KeyError:
            raise UnknownReferenceError(f'Unknown Formation reference: "{name}"') from None

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def __len__(self) -> int:
        return len(self._by_name)

    def all(self) -> list[Formation]:
        return list(self._by_name.values())

    def names(self) -> set[str]:
        return set(self._by_name.keys())


@dataclass
class HistoricalPriorRepository:
    """Lookup of HistoricalPrior by the TeamSeason id it applies to."""

    _by_team_season_id: dict[str, HistoricalPrior] = field(default_factory=dict)
    _status: dict[str, RecordStatus] = field(default_factory=dict)

    def add(self, team_season_id: str, prior: HistoricalPrior, status: RecordStatus) -> None:
        if team_season_id in self._by_team_season_id:
            raise DuplicateIdError(f'Duplicate HistoricalPrior for team_season_id: "{team_season_id}"')
        self._by_team_season_id[team_season_id] = prior
        self._status[team_season_id] = status

    def get(self, team_season_id: str) -> HistoricalPrior | None:
        """Returns None (not an error) for teams with no curated prior —
        this mirrors TeamSeason.historical_prior's own Optional semantics
        (Section 33: fully generic derivation is a valid, non-error state)."""
        return self._by_team_season_id.get(team_season_id)

    def status_of(self, team_season_id: str) -> RecordStatus | None:
        return self._status.get(team_season_id)

    def is_placeholder(self, team_season_id: str) -> bool:
        return self._status.get(team_season_id) == RecordStatus.PLACEHOLDER

    def __contains__(self, team_season_id: str) -> bool:
        return team_season_id in self._by_team_season_id

    def __len__(self) -> int:
        return len(self._by_team_season_id)


@dataclass
class TeamSeasonRepository:
    """Lookup of TeamSeason by id, with PLACEHOLDER-status tracking."""

    _by_id: dict[str, TeamSeason] = field(default_factory=dict)
    _default_formation: dict[str, str | None] = field(default_factory=dict)
    _status: dict[str, RecordStatus] = field(default_factory=dict)

    def add(self, team: TeamSeason, status: RecordStatus, default_formation: str | None = None) -> None:
        if team.id in self._by_id:
            raise DuplicateIdError(f'Duplicate TeamSeason id: "{team.id}"')
        self._by_id[team.id] = team
        self._default_formation[team.id] = default_formation
        self._status[team.id] = status

    def get(self, team_id: str) -> TeamSeason:
        try:
            return self._by_id[team_id]
        except KeyError:
            raise UnknownReferenceError(f'Unknown TeamSeason reference: "{team_id}"') from None

    def status_of(self, team_id: str) -> RecordStatus:
        if team_id not in self._status:
            raise UnknownReferenceError(f'Unknown TeamSeason reference: "{team_id}"')
        return self._status[team_id]

    def is_placeholder(self, team_id: str) -> bool:
        return self.status_of(team_id) == RecordStatus.PLACEHOLDER

    def default_formation_name(self, team_id: str) -> str | None:
        """Data-layer convenience, not part of the core TeamSeason contract (see schemas.py)."""
        if team_id not in self._by_id:
            raise UnknownReferenceError(f'Unknown TeamSeason reference: "{team_id}"')
        return self._default_formation.get(team_id)

    def __contains__(self, team_id: str) -> bool:
        return team_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)

    def all(self, include_placeholder: bool = False) -> list[TeamSeason]:
        if include_placeholder:
            return list(self._by_id.values())
        return [t for t in self._by_id.values() if self._status[t.id] != RecordStatus.PLACEHOLDER]

    def ids(self, include_placeholder: bool = False) -> set[str]:
        return {t.id for t in self.all(include_placeholder=include_placeholder)}


@dataclass
class DataRepositories:
    """Convenience bundle of all four repositories, as returned by the loader."""

    players: PlayerRepository
    teams: TeamSeasonRepository
    formations: FormationRepository
    historical_priors: HistoricalPriorRepository

    def production_ready_team_ids(self) -> set[str]:
        """
        TeamSeason ids that are safe to feed into a calibration or
        production simulation pipeline right now: the team itself is not
        PLACEHOLDER, and every player in its roster is not PLACEHOLDER
        either (a team can't be "production ready" if its roster is
        still fixture data, even if the TeamSeason record itself has
        real club/season/roster-reference metadata).
        """
        ready = set()
        for team in self.teams.all(include_placeholder=False):
            if all(not self.players.is_placeholder(pid) for pid in team.roster if pid in self.players):
                ready.add(team.id)
        return ready
