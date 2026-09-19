"""Regenerate data/normalized/players/player_positions.json from the dataset."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from football_engine.role_fit import build_positions_file  # noqa: E402

SRC = ROOT / "data" / "normalized" / "players" / "player_seasons.json"
OUT = ROOT / "data" / "normalized" / "players" / "player_positions.json"

players = json.loads(SRC.read_text(encoding="utf-8"))["players"]
existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
payload = build_positions_file(players, overrides=existing.get("overrides"))
OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
multi = sum(1 for v in payload["positions"].values() if len(v) > 1)
print(f"wrote {len(payload['positions'])} players ({multi} multi-position) -> {OUT}")
print("Hand-curated entries in 'overrides' are preserved and always win.")
