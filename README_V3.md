# v3 — Squad UX, Tournament UI, Match Playback

## Install

From `football_project/`:

```powershell
copy /Y football-engine-v3\football_engine\competition\ucl.py football_engine\competition\ucl.py
copy /Y football-engine-v3\web\index.html web\index.html
python -m uvicorn football_engine.api.app:app --reload
```

Only these two files changed. Everything else from earlier deliveries (role
fit, lottery draft, tournament session adapter, API routes) is untouched.

---

## Part 1 — Squad builder UX

Already delivered in a previous turn (persistent tray, drag-to-pitch, role
zones, empty-state cue). Not touched this session except for the GK rule
below.

## Part 2 — Exactly one goalkeeper

Row 0 is seven cells but one role slot. `placePlayer` now evicts whoever
else is in row 0 the moment a different cell in that row is taken — swapped
into the incoming player's old spot if they had one, benched otherwise. The
state can never contain two goalkeepers by construction, not by rejecting a
drop after the fact. A client-side check also blocks "Choose an opponent"
with a specific message if all 11 are placed but none are in the goal band
(the one legal-but-incomplete case the eviction rule can't itself prevent).

**Verified:** extracted `placePlayer` from the real file and ran it in
Node — 21 assertions covering placement, eviction, 3-way swap, and that
6-3-1/2-3-5 remain unaffected. All passed.

## Part 3 — Tournament UI

Replaced the old single-scroll dump with four tabs: **Overview / Table /
Matches / Bracket**.

- **Table**: full `Pld/W/D/L/GF/GA/GD/Pts` (the backend already tracked
  these on `UCLStanding`; they just weren't in the output dict — exposed,
  not calculated). Three legible bands (qualified / playoff / eliminated)
  with a legend, and a "YOUR TEAM" tag.
- **Matches**: every knockout tie as an explicit `Leg 1 / Leg 2 / Aggregate`
  card — no more bare `2-0 / 5-1` strings.
- **Bracket**: a real connected bracket for **Round of 16 → QF → SF → Final
  → Champion**, drawn with CSS connector lines between paired matches. The
  Playoff round is shown separately, above it, as leg cards — its 8 winners
  join the Round of 16 by league rank, not by a 1:1 tie pairing, so drawing
  a connector from a playoff box into a specific R16 box would assert a
  link the actual draw doesn't have. I chose accuracy over a fully-uniform
  bracket graphic.

**Contrast bug — measured and fixed, not guessed.** Computed real WCAG
ratios: `--dim` was failing at 3.35–3.92:1 everywhere it's used (losing
team names, rank numbers — needs 4.5:1), `--red` as text failed at
4.01–4.38:1, `--gold-dim` used as text on badges failed at 3.48–4.07:1.
Replaced with values clearing 4.5:1 with real margin (5.25–8.18:1). Full
sweep afterward found zero remaining failures.

**Verified:** extracted all four tab-render functions from the real file
and ran them in Node against a realistic mock payload shaped exactly like
`/api/tournament/start`'s output — 23 assertions: correct 8/16/12 table
banding, all 10 columns present, 5-column bracket, playoff kept separate,
and the R16 aggregate hand-verified against the mock leg scores (`Your XI
2–1 t8` from legs of 2-1 and 0-0 — matches).

## Part 8 — League-phase progressive reveal

`run_league_phase` now records every individual match
(`self.last_league_matches`) instead of discarding them after folding into
standings, exposed as `league_matches` in the season result. **One real
subtlety I checked rather than assumed:** the fixture generator doesn't
produce true round-robin rounds — it's grouped by host team, not by
matchday — and `assign_match_dates` already uses a naive chunk-by-18 grouping
internally for date assignment (pre-existing, not something I introduced).
I verified my new `matchday` field is byte-for-byte identical to that
existing internal grouping rather than computing a "corrected" one, because
a correction would change match dates and therefore match seeds — forbidden
by the task. The Matches tab reveals matchdays in a fast stagger (a few
seconds for all 144 games), with the user's own matches shown first and
held slightly longer, and a "show all now" skip.

**Verified:** ran the reveal against 145 mock league matches (144 + 1
user match) with fake timers — every match produced exactly one card, the
user's match was flagged, exactly 8 matchday sections appeared.

## Parts 4-6 — Match playback

New `startMatchPlayback()` replaces the instant score-dump. A scoreboard
(names, live score, clock, ticker) plays the real `result.timeline` — same
minute-stamped goals/cards/shots/subs the engine already produced — across
90 scheduled ticks. Base pacing is ~10.4s plus a half-time pause, landing
inside the requested 10-15s window without slowing the backend or adding
per-goal pauses that could push a high-scoring match past it. A skip button
cancels every pending timer and snaps straight to the real final score.

**No randomness added anywhere in playback** — verified by regex-scanning
the extracted playback code for `Math.random` (none) and `setInterval`
(none; only `setTimeout` for display scheduling, exactly as the task
requires).

**Verified:** extracted the real `startMatchPlayback` and ran it with fake
timers against a 7-event mock match (matching `adapter._timeline`'s exact
field shapes) — 14 assertions: correct final score (3-1) reached purely by
counting real goal events, every timeline event produced exactly one row
(none fabricated, none dropped), ascending minute order preserved, and the
skip button correctly cancels all pending timers and reveals every event
immediately.

---

## Tests actually run

All of the above (68 total JS assertions across four separate extraction
harnesses) executed for real in this session — not planned, not assumed.
Every extraction pulled the literal function body out of the real
`index.html` by regex, so what ran is what ships, not a rewritten stand-in.

**Not run:** anything requiring pydantic/fastapi. This sandbox still has no
network and no cached wheels (`pip download` fails identically to every
prior session). No match has been simulated by the real engine this
session, no tournament has actually executed end-to-end, and the browser
UI has never been loaded. The `ucl.py` change (exposing
`played/won/drawn/lost` and `league_matches`) only compiles — it has not
been exercised against real data.

**Run `python selftest.py` first** (from an earlier delivery) to check the
whole stack end-to-end on a machine with real dependencies, then load
`web/index.html` in a browser and actually watch a match play out and a
tournament bracket render — that's the one thing I categorically cannot
verify from here.
