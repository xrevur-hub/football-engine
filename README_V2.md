# UCL Tournament + Squad Builder — v2

## Install

From `football_project/` (the folder containing `football_engine/`):

```powershell
xcopy /E /I /Y football-engine-v2\football_engine football_engine
xcopy /E /I /Y football-engine-v2\data data
xcopy /E /I /Y football-engine-v2\web web
xcopy /E /I /Y football-engine-v2\tests tests
xcopy /E /I /Y football-engine-v2\tools tools
copy /Y football-engine-v2\selftest.py .

python -m pip install -r requirements-api.txt
python selftest.py
python -m pytest tests/ -q
python -m uvicorn football_engine.api.app:app --reload
```

`football_engine/competition/ucl.py` is **modified in place** — it overwrites
the existing file. Everything else is additive.

---

## Part 1 — UCL integration

### Why the drafted team could not enter

`_simulate_match` called `self.repos.teams.get(home_id)` unconditionally. A
user XI has no `TeamSeason` record in the catalog, so the lookup raised
`UnknownReferenceError` before any match could start.

### The integration seam

```
user draft → build_user_team() → Effective XI + Formation   (existing, unchanged)
           → ExternalRoster(formation, players)             (new typed DTO)
           → UCLRunner.register_external_roster(id, roster)  (new hook)
           → run_full_season([...36 ids...])                 (unchanged)
           → _resolve_side() → MatchOrchestrator.simulate    (existing engine)
```

`_resolve_side()` checks `external_rosters` first, then falls back to the
original `repos.teams` + `remap_players` path. All 35 catalog teams take the
exact path they always did. No team-strength calculation is duplicated — the
user's `TeamModelBuilder.build()` call is the same one `adapter.build_user_team`
already makes.

The user's XI is used **as placed**, without `remap_players`, because the free
placement and its role-fit penalties are the user's actual choice.

### Bugs fixed

| # | Bug | Fix |
|---|-----|-----|
| 1 | `hash(match_id) % 2` decided tied knockouts. Python salts `hash()` per process, so replay broke across runs. | `SeededRNG.derive_match_seed` (sha256) → seeded ET + penalties draw |
| 2 | **Every** match in a knockout stage shared one seed (`base_seed + 2000` for all R16 pairs, etc.) | Per-tie seed via `_match_seed(home, away, date, pair-specific id)` |
| 3 | `MatchResult.match_id` was stage-generic (`"round_of_16_first"` for all four pairs) | Pair-specific ids (`round_of_16_first_{home}_vs_{away}`) |
| 4 | Dead variable `home_away_goals` with the author's own `# wrong` comment | Removed |
| 5 | Away-goals tiebreak, contradicting the module's stated "modern 36-team format" (UEFA abolished it in 2021) | Aggregate → extra time → penalties |
| 6 | R16 draw was `r16_teams + playoff_winners` concatenated; comment said "need proper seeding" | Rank-based seeding, group winners vs playoff winners |
| 7 | A drawn final silently gave the trophy to the away team | `_resolve_single_match_tie` (same ET/pens path) |

### API

| Method | Path |
|--------|------|
| POST | `/api/tournament/start` — `{placements, seed?}` → full season result |
| GET | `/api/tournament/{session_id}` — re-read a completed run |

No tournament logic runs in JavaScript. The frontend renders the finished
payload only.

### Data limitation (stated, not hidden)

The catalog has exactly 36 slots. The user's team replaces **one synthetic
template club** (id ending `_2015_16`) — never Barcelona 2010/11 or Chelsea
2011/12. The UI names the club that stepped aside. If a 37th real club is
added later, the drop step in `tournament._pick_dropped_team` becomes
unnecessary.

---

## Part 2 — Squad builder

The bench used to sit **below** the pitch, forcing the scroll-select-scroll
loop. It now lives in the sticky right rail beside the pitch.

- **Persistent tray** — sticky, independently scrollable, showing name,
  original role, club and season per card.
- **Drag straight onto the pitch**; drop feedback on the target cell.
- **Drag a placed token back onto the tray** to bench that player.
- **Role zones** (GK/CB/FB/DM/CM/WM/AM/FW) on every empty cell, brightening
  while a drag is in progress. Labels only — they restrict nothing. 6-3-1 and
  2-3-5 remain legal and were tested.
- **Assigned vs drafted role** shown on each token, with the real role-fit
  factor when `/api/squad/preview` has returned one. Never a fabricated 1.0.
- **Empty state** — a "drag players onto the pitch" cue over the pitch.
- Shape and structural meters moved under the pitch so the rail stays
  tray-first. All values still come from the engine.

Formation calculation stays server-side: the frontend sends `{player_id, col,
row}` and `pitch_formation.py` builds the `Formation`.

---

## Verification

### Actually executed here

| Check | Result |
|---|---|
| `compileall` across the whole package | pass |
| `node --check` on the full frontend script | pass |
| All 46 JS-referenced DOM ids exist in markup | pass |
| **30 placement-logic tests** on code extracted verbatim from `index.html` — place, move, swap, bench-the-sitter, no-op re-drop, 6-3-1, 2-3-5 | 30/30 |
| **Frontend `assignedRole()` vs backend `slot_spec_for_cell()` on all 56 cells** | identical |
| **9 tournament-render tests** against a faithful backend payload, incl. missing/empty blocks | 9/9 |
| Frontend aggregate convention vs `determine_knockout_winner` | identical |
| `derive_match_seed` identical across 3 separate OS processes | pass |
| No builtin `hash()` call in `ucl.py` (AST-verified, not text-matched) | pass |
| League phase: 144 fixtures, 4H/4A, 8 distinct opponents per team | pass |
| All 144 league seeds unique; all 16 R16 leg seeds unique | pass |
| Public API used by `test_ucl_engine.py` still present | pass |

### NOT executed — the honest gap

This environment has **no pydantic, no fastapi, no network** (`pip download`
fails; no cached wheels). So nothing that constructs a pydantic model ran:

- No match was ever simulated.
- No tournament was ever run end to end.
- `/api/tournament/start` has never returned a real response.
- `tests/test_ucl_tournament.py` has never been run by me.
- The browser UI has never been loaded.

The pure logic — seed derivation, bracket math, placement rules, render
functions — was extracted from the **real files** (by source-slicing, not
retyping) and genuinely executed. The pydantic-dependent layer is unverified
code review only.

**Run `python selftest.py` first.** It checks dependencies, then data, role
fit, draft, team model, simulation, tournament and API routes in order, and
names the first failure. Send me its output if anything fails.
