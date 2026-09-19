"""
PossessionTendencySource implementation - data-driven pre-prior possession tendency.

This module provides a concrete implementation of the PossessionTendencySource protocol
by loading possession tendencies from a JSON file. This keeps possession data
data-driven rather than hard-coded in engine logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from football_engine.team_model.dependencies import PossessionTendencySource


class JsonPossessionTendencySource:
    """
    Loads possession tendencies from a JSON file and provides lookup by PlayerSeason IDs.

    The source returns the average possession tendency across all supplied player IDs,
    which represents the team's pre-prior possession tendency before historical prior blending.
    """

    def __init__(self, data_path: str | Path) -> None:
        self._data_path = Path(data_path)
        self._tendencies: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        if not self._data_path.exists():
            raise FileNotFoundError(f"Possession tendencies file not found: {self._data_path}")

        with open(self._data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tendencies = data.get("possession_tendencies", {})
        for player_id, value in tendencies.items():
            if not isinstance(value, (int, float)):
                raise ValueError(f"Invalid possession tendency for {player_id}: {value}")
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"Possession tendency for {player_id} must be in [0,1]: {value}")
            self._tendencies[player_id] = float(value)

    def __call__(self, *, player_season_ids: tuple[str, ...]) -> float:
        """
        Return the average possession tendency for the given player season IDs.

        If some player IDs are missing, use a default value of 0.5 for those
        players rather than failing. This allows the engine to work with
        incomplete possession data while still preferring explicit data.
        """
        if not player_season_ids:
            raise ValueError("player_season_ids cannot be empty")

        total = 0.0
        count = 0
        default_value = 0.5

        for pid in player_season_ids:
            if pid in self._tendencies:
                total += self._tendencies[pid]
            else:
                total += default_value
            count += 1

        if count == 0:
            raise ValueError("No valid possession tendencies found for the provided player IDs")

        return total / count

    def get(self, player_id: str) -> float | None:
        """Get possession tendency for a single player ID, or None if not found."""
        return self._tendencies.get(player_id)

    def has(self, player_id: str) -> bool:
        """Check if a player ID has a possession tendency defined."""
        return player_id in self._tendencies

    def all_ids(self) -> set[str]:
        """Return all player IDs that have possession tendencies defined."""
        return set(self._tendencies.keys())


def create_possession_source(data_path: str | Path | None = None) -> PossessionTendencySource:
    """
    Factory function to create a PossessionTendencySource.

    If data_path is None, uses the default location at data/normalized/possession/possession_tendencies.json
    """
    if data_path is None:
        # Default to the standard location
        current_dir = Path(__file__).parent.parent.parent
        data_path = current_dir / "data" / "normalized" / "possession" / "possession_tendencies.json"

    return JsonPossessionTendencySource(data_path)