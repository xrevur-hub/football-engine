"""
Tests for the pitch-grid -> Formation template mapping (football_engine.api).

These exercise only the pure grid helpers, so they run without pydantic and
without loading the engine. The key property under test is that the grid is a
faithful *superset* of the hand-authored formations.json geometry: every slot
of every existing preset is reproducible as some grid cell, and each preset can
be laid out with all 11 slots on distinct cells.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_engine.api.pitch_formation import (
    COLS,
    ROWS,
    PitchGridError,
    normalize_placements,
    shape_label,
    slot_spec_for_cell,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "normalized" / "formations" / "formations.json"


def _presets() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))["formations"]


def _cells_producing(role: str, side: str, depth: str) -> list[tuple[int, int]]:
    return [
        (c, r)
        for c in range(COLS)
        for r in range(ROWS)
        if slot_spec_for_cell(c, r) == (role, side, depth)
    ]


@pytest.mark.parametrize("preset", _presets(), ids=lambda p: p["name"])
def test_every_preset_slot_is_representable_on_the_grid(preset):
    for slot in preset["position_pool"]:
        cells = _cells_producing(slot["role"], slot["side"], slot["depth"])
        assert cells, (
            f"{preset['name']} slot {slot['slot_id']} "
            f"({slot['role']}/{slot['side']}/{slot['depth']}) has no grid cell"
        )


@pytest.mark.parametrize("preset", _presets(), ids=lambda p: p["name"])
def test_every_preset_fits_on_distinct_cells(preset):
    """Greedy layout: all 11 slots must land on distinct cells."""
    used: set[tuple[int, int]] = set()
    for slot in preset["position_pool"]:
        cells = [c for c in _cells_producing(slot["role"], slot["side"], slot["depth"]) if c not in used]
        assert cells, f"{preset['name']} slot {slot['slot_id']} could not be placed"
        used.add(cells[0])
    assert len(used) == 11


def test_goalkeeper_row_is_the_only_gk_source():
    for col in range(COLS):
        for row in range(ROWS):
            role, _, _ = slot_spec_for_cell(col, row)
            assert (role == "GK") == (row == 0)


def test_grid_cell_bounds_are_enforced():
    with pytest.raises(PitchGridError):
        slot_spec_for_cell(COLS, 0)
    with pytest.raises(PitchGridError):
        slot_spec_for_cell(0, ROWS)
    with pytest.raises(PitchGridError):
        slot_spec_for_cell(-1, 0)


def _placement(pid: str, col: int, row: int) -> dict:
    return {"player_id": pid, "col": col, "row": row}


def _valid_eleven() -> list[dict]:
    cells = [(3, 0), (0, 2), (2, 1), (3, 1), (4, 1), (6, 2), (2, 4), (3, 4), (4, 4), (2, 7), (4, 7)]
    return [_placement(f"p{i}", c, r) for i, (c, r) in enumerate(cells)]


def test_normalize_accepts_a_legal_eleven():
    out = normalize_placements(_valid_eleven())
    assert len(out) == 11
    assert sum(1 for p in out if p["role"] == "GK") == 1
    assert all(p["slot_id"] == f"C{p['col']}R{p['row']}" for p in out)


def test_normalize_rejects_duplicate_cell():
    bad = _valid_eleven()
    bad[1] = _placement("p1", 2, 1)  # same cell as p2
    with pytest.raises(PitchGridError, match="same cell"):
        normalize_placements(bad)


def test_normalize_rejects_wrong_keeper_count():
    two_keepers = _valid_eleven()
    two_keepers[1] = _placement("p1", 2, 0)
    with pytest.raises(PitchGridError, match="goalkeeper row"):
        normalize_placements(two_keepers)

    no_keeper = _valid_eleven()
    no_keeper[0] = _placement("p0", 0, 5)
    with pytest.raises(PitchGridError, match="goalkeeper row"):
        normalize_placements(no_keeper)


def test_normalize_rejects_wrong_squad_size():
    with pytest.raises(PitchGridError, match="11 placements"):
        normalize_placements(_valid_eleven()[:10])


def test_unconventional_shapes_are_accepted_not_blocked():
    """6-3-1 and 2-3-5 are legal inputs; the engine decides the consequences."""
    six_three_one = [(3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (6, 1),
                     (2, 4), (3, 4), (4, 4), (3, 7)]
    two_three_five = [(3, 0), (2, 1), (4, 1), (2, 4), (3, 4), (4, 4),
                      (0, 6), (2, 7), (3, 7), (4, 7), (6, 6)]
    for cells, expected in ((six_three_one, "6-3-1"), (two_three_five, "2-3-5")):
        placements = [_placement(f"p{i}", c, r) for i, (c, r) in enumerate(cells)]
        normalized = normalize_placements(placements)
        assert shape_label(normalized) == expected
