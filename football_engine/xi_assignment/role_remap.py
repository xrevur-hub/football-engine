"""General role-count remapping utility (data-driven roster → formation).

Used by the simulation/UCL/calibration runners to make a roster whose draft-role
counts differ from a chosen formation's slot-role counts playable WITHOUT the
full Effective-XI assignment path (which requires an explicit player→slot map).

This is a convenience for running seeded historical squads in an arbitrary
formation. It preserves the player's identity and abilities; it only relabels
the coarse PlayerRole to satisfy Formation Engine's role-count gate so the
engine can run. This is NOT a substitute for Effective XI when precision
matters — it is a diagnostic/runner convenience.
"""

from __future__ import annotations

from collections import Counter

from football_engine.core.enums import PlayerRole
from football_engine.core.formation import Formation
from football_engine.core.player_season import PlayerSeason

# Domain-knowledge versatility priority (low number = preferred conversion).
# Each edge converts surplus role -> deficit role.
CONVERSION_PRIORITY = {
    (PlayerRole.WM, PlayerRole.AM): 1,
    (PlayerRole.AM, PlayerRole.WM): 1,
    (PlayerRole.CM, PlayerRole.DM): 2,
    (PlayerRole.DM, PlayerRole.CM): 2,
    (PlayerRole.CM, PlayerRole.AM): 3,
    (PlayerRole.AM, PlayerRole.CM): 3,
    (PlayerRole.FW, PlayerRole.AM): 4,
    (PlayerRole.AM, PlayerRole.FW): 4,
    (PlayerRole.FW, PlayerRole.WM): 5,
    (PlayerRole.WM, PlayerRole.FW): 5,
    (PlayerRole.CB, PlayerRole.DM): 6,
    (PlayerRole.DM, PlayerRole.CB): 6,
    (PlayerRole.FB, PlayerRole.CM): 7,
    (PlayerRole.CM, PlayerRole.FB): 7,
}


def remap_roster_to_formation(
    players: list[PlayerSeason],
    formation: Formation,
) -> list[PlayerSeason] | None:
    """
    Return a copy of `players` whose role counts match the formation's slot roles.

    Converts surplus roles to deficit roles greedily by CONVERSION_PRIORITY.
    Returns None if no remap can satisfy the formation's role counts.
    The returned players are `PlayerSeason.model_copy(update={'role': ...})`
    — identity and abilities are otherwise unchanged.
    """
    if not formation or not formation.position_pool:
        return None
    need = Counter(s.role for s in formation.position_pool)
    if len(need) == 0 or len(formation.position_pool) != 11:
        return None
    if len(players) != 11:
        return None

    # Already matches?
    have = Counter(p.role for p in players)
    if have == need:
        return list(players)

    out = list(players)

    while True:
        have = Counter(p.role for p in out)
        if have == need:
            return out

        # Find a deficit
        deficit = None
        for role, count in need.items():
            if have.get(role, 0) < count:
                deficit = role
                break
        if deficit is None:
            return None  # satisfied all needs but still wrong? shouldn't happen

        # Find the best surplus to convert
        best_surplus = None
        best_prio = 999
        for role, count in have.items():
            if count > need.get(role, 0):
                prio = CONVERSION_PRIORITY.get((role, deficit), 999)
                if prio < best_prio:
                    best_prio = prio
                    best_surplus = role
        if best_surplus is None:
            return None  # cannot satisfy

        # Convert the first player with the surplus role
        converted = False
        for i, p in enumerate(out):
            if p.role == best_surplus:
                out[i] = p.model_copy(update={"role": deficit})
                converted = True
                break
        if not converted:
            return None


def remap_players(players: list[PlayerSeason], formation: Formation) -> list[PlayerSeason]:
    """
    Remap players to match formation, raising a clear error if impossible.

    Convenience wrapper that guarantees an 11-player playable roster.
    """
    result = remap_roster_to_formation(players, formation)
    if result is None:
        want = Counter(s.role for s in formation.position_pool)
        got = Counter(p.role for p in players)
        raise ValueError(
            f"Cannot remap roster (roles {dict(got)}) to formation "
            f"{getattr(formation, 'name', '?')} (roles {dict(want)})."
        )
    return result