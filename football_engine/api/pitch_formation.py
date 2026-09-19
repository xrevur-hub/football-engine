"""
Pitch grid -> Formation template construction (Free XI / free placement).

This module contains NO simulation mathematics. It is a *template authoring*
helper: it turns a user's free placement of 11 tokens on a discrete pitch grid
into the same kind of `Formation` object that `data/normalized/formations/
formations.json` already stores by hand.

Everything downstream is unchanged:

    grid placement -> Formation (here)
                   -> build_effective_xi (xi_assignment, unchanged)
                   -> FormationEngine    (team_model, unchanged)
                   -> StructuralFeatures -> TeamDimensions / TeamIdentity
                   -> TacticalProfile -> Matchup -> lambda -> Dixon-Coles

Grid contract
-------------
COLS = 7 (0..6, left -> right), ROWS = 8 (0 = own goal line, 7 = opponent box).

    side      : col < 3 -> LEFT, col == 3 -> CENTER, col > 3 -> RIGHT
    central   : 2 <= col <= 4          (the central third of the pitch width)
    depth/role: by row band, see ROW_BANDS below

The four hand-authored presets in formations.json (4-3-3, 4-4-2, 4-2-3-1,
3-5-2) are all exactly representable on this grid - see
`tests/test_api_pitch_formation.py`, which asserts that round-trip. That is the
evidence that this mapping is a faithful superset of the existing data format
and not a new, competing geometry model.

Exactly one cell in row 0 is the goalkeeper slot. Whoever the user places there
becomes `role=GK` for the match; if that is an outfielder, their low
`gk_ability` flows through TeamDimensionEngine as a genuine penalty. That is an
existing engine consequence, not a rule added here.
"""

from __future__ import annotations

from typing import Iterable

COLS = 7
ROWS = 8
GK_ROW = 0
SQUAD_SIZE = 11


class PitchGridError(ValueError):
    """Invalid grid placement (out of range, duplicate cell, wrong GK count)."""


# row -> (depth, central_role, wide_role). Depth strings match SlotDepth values.
ROW_BANDS: dict[int, tuple[str, str, str]] = {
    0: ("back", "GK", "GK"),
    1: ("back", "CB", "FB"),
    2: ("back", "CB", "FB"),
    3: ("mid", "DM", "FB"),
    4: ("mid", "CM", "WM"),
    5: ("mid", "AM", "WM"),
    6: ("front", "FW", "WM"),
    7: ("front", "FW", "WM"),
}


def side_for_col(col: int) -> str:
    """Lateral band. Matches SlotSide values ('left' / 'center' / 'right')."""
    if col < 3:
        return "left"
    if col == 3:
        return "center"
    return "right"


def is_central_col(col: int) -> bool:
    """Central third of the pitch width, used only for role selection."""
    return 2 <= col <= 4


def slot_spec_for_cell(col: int, row: int) -> tuple[str, str, str]:
    """Return (role, side, depth) for one grid cell. Pure, no engine imports."""
    if not (0 <= col < COLS):
        raise PitchGridError(f"col must be in [0, {COLS - 1}], got {col}")
    if not (0 <= row < ROWS):
        raise PitchGridError(f"row must be in [0, {ROWS - 1}], got {row}")
    depth, central_role, wide_role = ROW_BANDS[row]
    role = central_role if is_central_col(col) else wide_role
    return role, side_for_col(col), depth


def slot_id_for_cell(col: int, row: int) -> str:
    """Stable, identity-only slot id. Never parsed for meaning downstream."""
    return f"C{col}R{row}"


def normalize_placements(placements: Iterable[dict]) -> list[dict]:
    """
    Validate a list of {player_id, col, row} and return it enriched with
    role/side/depth/slot_id. Raises PitchGridError on anything unusable.

    Only *structurally impossible* things are rejected (duplicate cell, wrong
    count, not exactly one keeper). Unconventional shapes - 6 at the back,
    five forwards, nobody in midfield - are deliberately accepted: producing
    their consequences is the engine's job, not this validator's.
    """
    items = list(placements)
    if len(items) != SQUAD_SIZE:
        raise PitchGridError(f"exactly {SQUAD_SIZE} placements required, got {len(items)}")

    seen_cells: set[tuple[int, int]] = set()
    seen_players: set[str] = set()
    out: list[dict] = []
    gk_count = 0

    for item in items:
        try:
            player_id = str(item["player_id"])
            col = int(item["col"])
            row = int(item["row"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PitchGridError(f"placement must be {{player_id, col, row}}: {item!r}") from exc

        role, side, depth = slot_spec_for_cell(col, row)
        if (col, row) in seen_cells:
            raise PitchGridError(f"two players placed on the same cell ({col}, {row})")
        if player_id in seen_players:
            raise PitchGridError(f"player {player_id!r} placed twice")
        seen_cells.add((col, row))
        seen_players.add(player_id)
        if row == GK_ROW:
            gk_count += 1

        out.append(
            {
                "player_id": player_id,
                "col": col,
                "row": row,
                "slot_id": slot_id_for_cell(col, row),
                "role": role,
                "side": side,
                "depth": depth,
            }
        )

    if gk_count != 1:
        raise PitchGridError(f"exactly one player must occupy the goalkeeper row, got {gk_count}")
    return out


def shape_label(placements: Iterable[dict]) -> str:
    """Human label such as '4-3-3' or '2-3-5', derived from depth bands only."""
    back = mid = front = 0
    for p in placements:
        row = int(p["row"])
        if row == GK_ROW:
            continue
        depth = ROW_BANDS[row][0]
        if depth == "back":
            back += 1
        elif depth == "mid":
            mid += 1
        else:
            front += 1
    return f"{back}-{mid}-{front}"


def build_formation(placements: Iterable[dict], name: str | None = None):
    """
    Build a core `Formation` from normalized placements.

    Imported lazily so the pure grid helpers above stay importable (and
    testable) without pydantic installed.
    """
    from football_engine.core.enums import PlayerRole
    from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide

    normalized = normalize_placements(placements)
    slots = [
        PositionSlot(
            slot_id=p["slot_id"],
            role=PlayerRole(p["role"]),
            side=SlotSide(p["side"]),
            depth=SlotDepth(p["depth"]),
        )
        for p in normalized
    ]
    return Formation(name=name or shape_label(normalized), position_pool=slots)


def assignment_from_placements(placements: Iterable[dict]) -> dict[str, str]:
    """{player_id: slot_id} map consumed by build_effective_xi (unchanged API)."""
    return {p["player_id"]: p["slot_id"] for p in normalize_placements(placements)}


def formation_to_grid(formation) -> list[dict]:
    """
    Best-effort inverse: place an authored Formation onto the grid so a preset
    can be used as a starting point in the squad builder. Returns a list of
    {slot_id, role, col, row}. Used for UI convenience only.
    """
    depth_rows = {"back": [1, 2], "mid": [3, 4, 5], "front": [6, 7]}
    default_row_for_role = {
        "CB": 1, "FB": 2, "DM": 3, "CM": 4, "AM": 5, "WM": 6, "FW": 7,
    }
    side_cols = {"left": [2, 1, 0], "center": [3], "right": [4, 5, 6]}

    used: set[tuple[int, int]] = set()
    out: list[dict] = []
    for slot in formation.position_pool:
        role = slot.role.value
        side = slot.side.value
        depth = slot.depth.value
        if role == "GK":
            out.append({"slot_id": slot.slot_id, "role": role, "col": 3, "row": 0})
            used.add((3, 0))
            continue

        rows = depth_rows[depth]
        preferred = default_row_for_role.get(role, rows[0])
        row_order = sorted(rows, key=lambda r: (abs(r - preferred), r))
        placed = False
        for row in row_order:
            for col in side_cols[side]:
                if (col, row) in used:
                    continue
                # Only accept a cell that regenerates this slot's role/side/depth.
                if slot_spec_for_cell(col, row) != (role, side, depth):
                    continue
                used.add((col, row))
                out.append({"slot_id": slot.slot_id, "role": role, "col": col, "row": row})
                placed = True
                break
            if placed:
                break
        if not placed:
            raise PitchGridError(
                f"slot {slot.slot_id} ({role}/{side}/{depth}) has no matching grid cell"
            )
    return out
