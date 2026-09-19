"""Shared fixtures for Layer 1 (data_layer) tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DATA_DIR = REPO_ROOT / "data" / "normalized"


@pytest.fixture
def seed_data_dir() -> Path:
    """The real, checked-in seed dataset directory (data/normalized/)."""
    return SEED_DATA_DIR


@pytest.fixture
def tmp_dataset_dir(tmp_path: Path) -> Path:
    """
    A scratch directory laid out like data/normalized/, for tests that
    need to write deliberately-broken JSON (duplicate ids, bad
    references, invalid attributes, etc.) without touching the real
    seed dataset.
    """
    for sub in ("players", "teams", "formations", "historical_priors"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def minimal_dataset_metadata() -> dict:
    return {"dataset_version": "test.0", "schema_version": "1.0"}


def placeholder_metadata() -> dict:
    return {
        "status": "PLACEHOLDER",
        "source": None,
        "confidence": 0.0,
        "manual_override": False,
    }


def curated_metadata(source: str = "manual_curation", confidence: float = 0.9) -> dict:
    return {
        "status": "CURATED",
        "source": source,
        "confidence": confidence,
        "manual_override": False,
    }


def make_player(player_id: str, role: str = "CM", **overrides) -> dict:
    base = {
        "id": player_id,
        "name": player_id,
        "season": "2020/21",
        "role": role,
        "attack_ability": 50.0,
        "creation_ability": 50.0,
        "defense_ability": 50.0,
        "gk_ability": 50.0 if role == "GK" else 0.0,
        "metadata": placeholder_metadata(),
    }
    base.update(overrides)
    return base


def make_formation(name: str = "4-3-3") -> dict:
    roles = ["GK", "FB", "CB", "CB", "FB", "DM", "CM", "CM", "WM", "WM", "FW"]
    # side/depth are additive Layer 0/core contract fields (conversation
    # record — Option 3 decision, 2026-09-08): required, explicit per slot.
    geometry = [
        ("center", "back"),  # GK
        ("right", "back"),  # FB
        ("left", "back"),  # CB
        ("right", "back"),  # CB
        ("left", "back"),  # FB
        ("center", "mid"),  # DM
        ("left", "mid"),  # CM
        ("right", "mid"),  # CM
        ("left", "front"),  # WM
        ("right", "front"),  # WM
        ("center", "front"),  # FW
    ]
    return {
        "name": name,
        "position_pool": [
            {"slot_id": f"slot_{i}", "role": r, "side": side, "depth": depth}
            for i, (r, (side, depth)) in enumerate(zip(roles, geometry))
        ],
    }


def make_team(team_id: str, roster: list[str], **overrides) -> dict:
    base = {
        "id": team_id,
        "club": team_id,
        "season": "2020/21",
        "roster": roster,
        "metadata": placeholder_metadata(),
    }
    base.update(overrides)
    return base
