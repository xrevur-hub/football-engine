"""Print the structure of possession_tendencies.json. Read-only; changes nothing.

Run from football_project/:   python inspect_possession.py
"""
import collections
import json
from pathlib import Path

path = Path("data/normalized/possession/possession_tendencies.json")
data = json.loads(path.read_text(encoding="utf-8"))

print("top-level keys:", list(data.keys()))
table = data.get("possession_tendencies", {})
print("entries under 'possession_tendencies':", len(table))
print("value types:", dict(collections.Counter(type(v).__name__ for v in table.values())))

numeric = [k for k, v in table.items() if isinstance(v, (int, float))]
dicts = [k for k, v in table.items() if isinstance(v, dict)]
print("numeric (per-player) keys:", len(numeric), numeric[:5])
print("dict (team-level) keys   :", len(dicts), dicts[:5])

if dicts:
    sample = table[dicts[0]]
    print("\nfirst dict entry, fields:", list(sample.keys()))
    print("possession_tendency value:", sample.get("possession_tendency"))

other = {k: type(v).__name__ for k, v in data.items() if k != "possession_tendencies"}
print("\nother top-level sections:", other)
