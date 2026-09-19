"""
selftest.py — run every layer in order and say exactly where it breaks.

    python selftest.py

This exists because the code in `football_engine/api/`, `football_engine/
role_fit/` and `football_engine/draft/lottery.py` was authored in an
environment with no pydantic, no fastapi and no network, so it could not be
executed end to end before delivery. Syntax, the pure grid logic, the lottery
mechanics and a static check of every engine attribute the adapter reads all
passed there. Everything that needs a live engine is checked HERE.

Each step prints PASS or FAIL with the real exception. Stop at the first FAIL
and fix that; later steps depend on earlier ones.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASSED = 0
FAILED = 0


def step(name):
    def deco(fn):
        global PASSED, FAILED
        if FAILED:
            print(f"  SKIP  {name}")
            return fn
        try:
            detail = fn()
            PASSED += 1
            print(f"  PASS  {name}" + (f"  -> {detail}" if detail else ""))
        except Exception as exc:  # noqa: BLE001 - diagnostics are the point
            FAILED += 1
            print(f"  FAIL  {name}")
            print(f"        {type(exc).__name__}: {exc}")
            traceback.print_exc()
        return fn

    return deco


print("\n=== 1. dependencies ===")


@step("pydantic importable")
def _():
    import pydantic
    return pydantic.VERSION


@step("fastapi importable")
def _():
    import fastapi
    return fastapi.__version__


print("\n=== 2. data ===")

DATA = ROOT / "data" / "normalized"


@step("dataset loads")
def _():
    from football_engine.data_layer.loader import load_all
    repos = load_all(DATA)
    globals()["REPOS"] = repos
    return (f"{len(repos.players.all(include_placeholder=False))} players, "
            f"{len(repos.teams.all(include_placeholder=False))} teams")


@step("player_positions.json present and complete")
def _():
    from football_engine.role_fit import load_position_store
    store = load_position_store()
    if not store.positions:
        raise RuntimeError(
            "data/normalized/players/player_positions.json is missing or empty. "
            "Regenerate it with tools/generate_positions.py"
        )
    missing = [p.id for p in REPOS.players.all(include_placeholder=False)
               if p.id not in store.positions]
    if missing:
        raise RuntimeError(f"{len(missing)} players have no position entry, e.g. {missing[:3]}")
    multi = sum(1 for v in store.positions.values() if len(v) > 1)
    return f"{len(store.positions)} players, {multi} with more than one position"


print("\n=== 3. role fit ===")


@step("fit factors behave")
def _():
    from football_engine.role_fit import fit_factor
    assert fit_factor("FB", "FB", ["FB"]) == 1.0, "same role must be neutral"
    assert fit_factor("FB", "WM", ["FB", "WM"]) == 1.0, "listed position must be neutral"
    assert fit_factor("FB", "WM", ["FB"]) < 1.0, "unlisted position must cost something"
    assert fit_factor("FW", "GK", ["FW"]) < fit_factor("FW", "CB", ["FW"]), "goal must cost most"
    assert fit_factor("FW", "CB", ["FW"]) >= 0.5, "penalty must stay bounded"
    return "monotonic and bounded"


print("\n=== 4. lottery draft ===")


@step("draft is reproducible and legal")
def _():
    import random
    from football_engine.draft.lottery import ClubReuse, LotteryDraft

    teams = REPOS.teams.all(include_placeholder=False)
    clubs = {t.id: (f"{t.club} {t.season}", list(t.roster)) for t in teams if t.roster}

    def run(seed):
        d = LotteryDraft(
            clubs={k: (v[0], list(v[1])) for k, v in clubs.items()},
            rng=random.Random(seed), reuse=ClubReuse.UNTIL_EXHAUSTED,
        )
        while not d.complete:
            d.draw_club()
            d.auto_pick()
        return d.squad()

    a, b = run(42), run(42)
    assert a == b, "same seed produced a different squad"
    assert len(set(a)) == 11, "draft produced duplicate players"
    return f"11 unique players, reproducible"


print("\n=== 5. team model from free placement ===")

XI = [(3, 0), (0, 2), (2, 1), (3, 1), (4, 1), (6, 2), (2, 4), (3, 4), (4, 4), (2, 7), (4, 7)]


@step("grid maps onto a Formation")
def _():
    from football_engine.api.pitch_formation import build_formation, shape_label, normalize_placements
    team = REPOS.teams.get(REPOS.teams.ids()[0]) if hasattr(REPOS.teams, "ids") else None
    roster = list(team.roster) if team else [p.id for p in REPOS.players.all(include_placeholder=False)[:11]]
    placements = [{"player_id": roster[i], "col": c, "row": r} for i, (c, r) in enumerate(XI)]
    globals()["PLACEMENTS"] = placements
    formation = build_formation(placements)
    assert len(formation.position_pool) == 11
    return shape_label(normalize_placements(placements))


@step("engine builds a team model from that placement")
def _():
    from football_engine.api import adapter
    built = adapter.build_user_team(PLACEMENTS)
    d = built["dto"]["dimensions"]
    globals()["USER_DTO"] = built["dto"]
    return (f"att {d['attack']:.0f} cre {d['creation']:.0f} "
            f"def {d['defense']:.0f} gk {d['goalkeeping']:.0f}")


@step("role fit reaches the effective XI")
def _():
    factors = {p["player_id"]: p["fit_factor"] for p in USER_DTO["placements"]}
    if not factors:
        raise RuntimeError("no placements returned")
    penalised = {k: v for k, v in factors.items() if v < 1.0}
    return (f"{len(penalised)}/11 players carry a fit penalty"
            if penalised else "all 11 in natural positions")


print("\n=== 6. simulation ===")


@step("a match simulates")
def _():
    from football_engine.api import adapter
    opponent = REPOS.teams.all(include_placeholder=False)[0].id
    result = adapter.simulate_match(PLACEMENTS, opponent, seed=42)
    globals()["RESULT"] = result
    return (f"{result['home']['score']}-{result['away']['score']} "
            f"vs {opponent}, {len(result['timeline'])} events")


@step("same seed replays identically")
def _():
    from football_engine.api import adapter
    opponent = REPOS.teams.all(include_placeholder=False)[0].id
    again = adapter.simulate_match(PLACEMENTS, opponent, seed=42)
    assert again["home"]["score"] == RESULT["home"]["score"], "score drifted between runs"
    assert again["away"]["score"] == RESULT["away"]["score"], "score drifted between runs"
    return "deterministic"


@step("formation actually changes the outcome distribution")
def _():
    """A 6-3-1 and a 2-3-5 built from the same eleven must not be identical."""
    from football_engine.api import adapter
    ids = [p["player_id"] for p in PLACEMENTS]
    defensive = [(3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (6, 1), (2, 4), (3, 4), (4, 4), (3, 7)]
    attacking = [(3, 0), (2, 1), (4, 1), (2, 4), (3, 4), (4, 4), (0, 6), (2, 7), (3, 7), (4, 7), (6, 6)]
    out = {}
    for label, cells in (("6-3-1", defensive), ("2-3-5", attacking)):
        pl = [{"player_id": ids[i], "col": c, "row": r} for i, (c, r) in enumerate(cells)]
        dto = adapter.build_user_team(pl)["dto"]
        out[label] = dto["structural_features"]["defensive_cover"]
    if out["6-3-1"] <= out["2-3-5"]:
        raise RuntimeError(
            f"defensive cover did not respond to shape: 6-3-1={out['6-3-1']:.3f} "
            f"2-3-5={out['2-3-5']:.3f}"
        )
    return f"defensive cover 6-3-1={out['6-3-1']:.2f} > 2-3-5={out['2-3-5']:.2f}"


print("\n=== 7. api surface ===")


@step("FastAPI app imports and routes are registered")
def _():
    from football_engine.api.app import app
    paths = sorted({r.path for r in app.routes if r.path.startswith("/api")})
    required = ["/api/health", "/api/players", "/api/draft/start", "/api/match/simulate", "/api/role-fit"]
    missing = [p for p in required if p not in paths]
    if missing:
        raise RuntimeError(f"missing routes: {missing}")
    return f"{len(paths)} api routes"


print("\n" + "=" * 52)
print(f"  {PASSED} passed, {FAILED} failed")
if FAILED:
    print("\n  Fix the first FAIL above; later steps depend on earlier ones.")
print("=" * 52 + "\n")
sys.exit(1 if FAILED else 0)
