"""Local validation shared by Modules 2/3; never re-derive formation geometry."""
from __future__ import annotations

import math
from typing import Final

from pydantic import ValidationError

from football_engine.core.enums import PlayerRole
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import StructuralFeatures

REQUIRED_SQUAD_SIZE: Final[int] = 11


def bounded_number(value: object, *, label: str, upper: float,
                   error_type: type[ValueError]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error_type(f"{label} must be a finite real number in [0, {upper}]")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= upper:
        raise error_type(f"{label} must be a finite real number in [0, {upper}]")
    return number


def validated_players(players: list[PlayerSeason], structural_features: StructuralFeatures,
                      *, error_type: type[ValueError], engine_name: str) -> tuple[PlayerSeason, ...]:
    if not isinstance(players, (list, tuple)) or len(players) != REQUIRED_SQUAD_SIZE:
        raise error_type(f"{engine_name} requires exactly 11 PlayerSeasons")
    if not isinstance(structural_features, StructuralFeatures):
        raise error_type("structural_features must be a StructuralFeatures object")
    try:
        StructuralFeatures.model_validate(structural_features.model_dump())
    except (ValidationError, TypeError, ValueError) as exc:
        raise error_type(f"Invalid StructuralFeatures: {exc}") from exc
    ids = []
    for player in players:
        if not isinstance(player, PlayerSeason):
            raise error_type("Every selected player must be a PlayerSeason")
        if not isinstance(player.role, PlayerRole):
            raise error_type("PlayerSeason role must be a PlayerRole member")
        if not isinstance(player.id, str) or not player.id:
            raise error_type("PlayerSeason id must be a non-empty string")
        try:
            PlayerSeason.model_validate(player.model_dump())
        except (ValidationError, TypeError, ValueError) as exc:
            raise error_type(f"Invalid PlayerSeason {player.id}: {exc}") from exc
        ids.append(player.id)
    if len(set(ids)) != REQUIRED_SQUAD_SIZE:
        raise error_type(f"{engine_name} received duplicate PlayerSeason id(s)")
    if sum(player.role == PlayerRole.GK for player in players) != 1:
        raise error_type(f"{engine_name} requires exactly one GK")
    # Do not sort/mutate the caller's roster or retain a per-team cache.
    return tuple(sorted(players, key=lambda player: player.id))
