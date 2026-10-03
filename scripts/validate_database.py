import json
from pathlib import Path
r=Path(__file__).resolve().parents[1]/"data/normalized"
p=json.loads((r/"players/player_seasons.json").read_text(encoding="utf-8"))["players"]
t=json.loads((r/"teams/team_seasons.json").read_text(encoding="utf-8"))["teams"]
pos=json.loads((r/"possession/possession_tendencies.json").read_text(encoding="utf-8"))["possession_tendencies"]
ids=[x["id"] for x in p]
assert len(ids)==len(set(ids))
assert all(x.get("metadata",{}).get("source") != "synthetic_template" for x in p)
assert all(set(x["roster"]).issubset(set(ids)) for x in t)
assert set(pos)=={x["id"] for x in t}
assert all(0<=x["attack_ability"]<=100 and 0<=x["creation_ability"]<=100 and 0<=x["defense_ability"]<=100 and 0<=x["gk_ability"]<=100 for x in p)
assert all(0<=x[k]<=1 for x in p for k in ("shot_tendency","press_tendency","transition_tendency","pace","discipline_score","impact_score"))
print(f"PASS: {len(t)} teams, {len(p)} players, {len(pos)} possession records")
