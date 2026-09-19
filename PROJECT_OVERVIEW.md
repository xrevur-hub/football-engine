# Football Match Simulation Engine — Project Overview

**Status snapshot:** E-12 CLOSED and FormationEngine V1 implemented · **D1 dimensions and seven identity components implemented** · Complete TeamModel assembly requires an explicit possession source · Layer 3 approved formulas unchanged · No automatic historical reconstruction or full match simulation claimed.

This document is a complete, honest snapshot of the project: what it's
for, how it's structured, what's been built, what actually works today
versus what's a placeholder, and what's left. It's meant to be readable
on its own, without needing to re-read the whole conversation history.

---

## 1. What this project is

A **Football Match Simulation Engine** that simulates historical
football teams — including matchups that never actually happened (e.g.
Barcelona 2010/11 vs. Bayern 2012/13) — in a way that is:

- **Probabilistic, not black-box.** Every match outcome comes from an
  explicit probability distribution, sampled with a seeded RNG — not a
  hidden neural net or a hardcoded outcome table.
- **Historically aware.** Teams are modeled as season-specific snapshots
  (`barcelona_2010_11` is a different entity from `barcelona_2014_15`),
  optionally blended with curated historical priors for iconic teams.
- **Reproducible.** Same seed + same code path = bit-for-bit same
  simulated match, forever.
- **Calibratable, not yet calibrated.** Existing anchors use immutable ParameterSet; Layer 3 has its separately disclosed coefficients. Layer 2 now has immutable, uncalibrated role-weight priors supplied by the design memo, separate from attribution weights. No optimizer ran and no new Core schema or hidden possession default was introduced.
- **Extensible without touching engine code.** Adding team #41, #101, or
  #501 should require editing JSON data files only — never Python.
- **Anti-double-counting is a design invariant to audit, not a blanket empirical guarantee.** Explicit ownership rules guide the implementation. Known build-up/press verbal-rule tensions and unspecified tactical/helper dependencies are recorded in the corrected memo without silently changing approved Layer 3 equations.

### The core philosophy, in one line

```
Prediction → Probability → Simulation
```

Not: raw stats → magic score → fake randomness bolted on top. The engine
builds real team strength signals, turns them into goal-rate parameters
(λ), turns λ into a real probability distribution over scorelines, and
only *then* samples an outcome — so upsets emerge naturally from the
distribution's own variance, not from an artificial "upset chance" hack.

### The three conceptual layers (not to be confused with the 8
implementation "Layers" below — these are the *pipeline stages*, the
implementation Layers are the *build order*)

```
PREDICTION LAYER
  PlayerSeason → Formation → Team Dimensions/Identity → Tactical State
    → Matchup (M + T) → λ_base → Home Advantage → Form → λ_final

PROBABILITY LAYER
  λ_final → Dixon-Coles / Poisson → P(X=x, Y=y)

SIMULATION LAYER
  P(X=x, Y=y) → Random Sampling → Segment Outcome → Goal/Event
    → State Update → Next Segment
```

Two rules are locked and enforced throughout the whole codebase:

1. **Randomness → Sampling, never Randomness → λ.** Nothing upstream of
   the sampling step may be random; nothing downstream of it may write
   back into λ.
2. **Goal Outcome → Future State, never Goal Outcome → retroactively
   changes the λ that produced it.** Post-sample modules (event
   generation, player attribution) only *observe and describe* what the
   sampler already decided — they can never manufacture a new goal or
   rewrite a probability that already fired.

---

## 2. The 8-layer build plan and authorized isolation

The canonical Layer 3 name is **Matchup + λ Engine**. FormationEngine remains entirely in Layer 2. The 2026-09-08 final authorization permits isolated Layer 3 implementation using manually constructed upstream test fixtures while Layer 2 remains incomplete; this is not an end-to-end integration claim.

| Layer | Name | Current status |
|---|---|---|
| 0 | Project Skeleton + Base Types | Approved E-12 migration applied; unrelated contracts unchanged |
| 1 | Data Layer + JSON Schemas | Snapshot-quality type/weight metadata added; existing loader/schemas retained; normalized seed data absent |
| 2 | Team Model | FormationEngine, D1 dimensions and conditional identity assembly implemented; actual possession source still required |
| 3 | **Matchup + λ Engine** | **Specified M/T/λ formulas implemented; explicit Module 5 policy and Module 6 helper gaps remain** |
| 4 | Probability models (legacy roadmap label: λ + Probability) | Not implemented; λ is Module 7 in Layer 3 and must not be duplicated here |
| 5 | Full Simulation | Not implemented; future orchestrator only |
| 6 | Q/R Events + Attribution | Not implemented |
| 7 | Calibration Implementation | Not implemented |

See `docs/LAYER3_SPEC_AND_GAPS.md` for the implemented equations, interfaces, exact missing dependencies, and fixture provenance.

---

## 3. Locked architectural rules (apply across every layer)

These are non-negotiable constraints the whole project must keep
satisfying, no matter which layer is being worked on:

- **The Boundary (Module 8 — `SegmentOutcome`).** This is the *only*
  object in the entire pipeline where randomness enters. Everything
  computed after it (goal attribution, shot/save/card events) is
  "post-sample" and is contractually forbidden from writing back into λ.
- **M/T separation.** The Matchup Engine (Module 6) must never collapse
  organized-attack threat (`M`) and transition threat (`T`) into one
  generic "team strength" number. They stay as two independent paths
  all the way to λ.
- **Single shared RNG.** `SeededRNG` is the *only* permitted source of
  randomness anywhere in the engine. Seeds are derived deterministically
  from `(home_id, away_id, match_date, match_id)`, so any historical or
  hypothetical match can be replayed exactly.
- **Explicit configuration, not hidden constants.** Existing priors use `ParameterSet` with its existing bounds. The authorized creation coefficients (0.6/0.4 and 0.7/0.3) and form bounds (0.85/1.15) are named in immutable Layer-3-local `Layer3Coefficients`; this introduces no Layer 0 field changes.
- **Single-path dependency rules (anti-double-counting).** Each football
  phenomenon has exactly one route into λ — e.g. Press quality → M only,
  High line → T only, Possession → CreationRealization only, Home
  Advantage lives *outside* the Matchup Engine entirely, Form is
  separate from Team Identity. Breaking one of these rules (making the
  same signal influence λ twice through two different paths) is
  considered a serious architectural bug.
- **`MatchResult` invariants.** A completed match's final score must
  always exactly match the count of goals in its goal log, and goal
  minutes must be non-decreasing — enforced by Pydantic validators, not
  just convention.
- **Data-driven, not hardcoded.** The engine must never contain
  `if team == "Brazil"` logic or a fixed `TEAMS = [...]` list anywhere.
  Going from 40 teams to 500 teams must never require touching engine
  code — only adding/editing JSON.

---

## 4. Layer 0 — Project Skeleton + Base Types (✅ Done)

**Goal:** Define every data *shape* the engine will ever need, as
immutable Pydantic models, before any formula exists. "Contracts before
calculations."

### What's in it

```
football_engine/
├── __init__.py                 # public API surface — exports everything below
├── core/
│   ├── enums.py                 # MatchState, PlayerRole, HistoricalTier,
│   │                             # SegmentId,
│   │                             # SplittingEventType, NonSplittingEventType
│   ├── constants.py              # Section 44/T.12 default calibration priors
│   │                             # + T.12 parameter bounds + role weight tables
│   ├── parameters.py             # ParameterSet — the one object every
│   │                             # calibration-sensitive constant lives in
│   ├── player_season.py          # PlayerSeason — immutable, season-specific
│   │                             # player snapshot (messi_2010_11 ≠ messi_2018_19)
│   ├── formation.py               # Formation template (Position Pool + name)
│   ├── team_dimensions.py         # StructuralFeatures (Module 1 output shape),
│   │                             # TeamDimensions (Module 2 output shape:
│   │                             # attack/creation/defense/goalkeeping)
│   ├── team_identity.py           # TeamIdentity (Module 3 output shape:
│   │                             # possession/press/transition tendency, tempo,
│   │                             # risk tolerance, compactness, etc.)
│   ├── team_season.py             # HistoricalPrior + TeamSeason (catalog entity)
│   │                             # + the ALREADY-IMPLEMENTED Section 30 hybrid
│   │                             # blend functions (see box below)
│   ├── tactical_profile.py        # TacticalProfile (Module 5 output shape —
│   │                             # per-segment runtime tactics)
│   ├── matchup.py                 # MatchupResult (M/T, Module 6 output),
│   │                             # LambdaPair (Module 7 output)
│   ├── segment_outcome.py         # SegmentOutcome — THE BOUNDARY object
│   ├── events.py                  # GoalEvent, AttributedGoalEvent, CardEvent,
│   │                             # ShotEvent, SaveEvent, SubstitutionEvent,
│   │                             # MatchEvents — all post-sample, all forbidden
│   │                             # from writing back into λ
│   ├── team_runtime_state.py       # TeamRuntimeState — per-match mutable
│   │                             # container (score, state, form_factor, etc.)
│   ├── match_runtime.py           # MatchRuntime — full per-match state
│   │                             # container ("state container, not a
│   │                             # prediction engine")
│   └── match_result.py            # MatchResult — final immutable output +
│                                 # Pydantic validators enforcing Section S.9
│                                 # invariants (goal counts match score, goal
│                                 # minutes non-decreasing)
└── rng/
    └── seeded_rng.py               # SeededRNG — the single allowed randomness
                                    # source (uniform, bernoulli, poisson,
                                    # exponential, choice, weighted_choice) +
                                    # deterministic seed derivation
```

### Already-implemented, real, working logic (not just shapes)

Two pieces of actual math exist and work today, both from Section 30
("Historical Team Hybrid Model"), in `team_season.py`:

```python
final = clamp(alpha * derived + (1 - alpha) * historical_prior, 0, 1)
```

- `apply_historical_prior_to_dimensions(derived, prior)` — blends a
  derived `TeamDimensions` with a team's curated historical prior.
- `apply_historical_prior_to_identity(derived, prior)` — same blend for
  `TeamIdentity`.

Both handle the edge cases correctly: `prior=None` or `alpha=1.0` (Tier
3, fully generic team) is a no-op pass-through of the derived value,
exactly matching the spec's "teams without a historical prior just use
derived values" rule.

`SeededRNG` is also fully real and working: `uniform`, `bernoulli`,
`poisson` (Knuth's algorithm, no numpy dependency), `exponential`,
`choice`, `weighted_choice` (with the documented "all weights zero →
fallback to uniform" edge case), plus `derive_match_seed()` using a
stable SHA-256 hash (not Python's salted `hash()`, which would break
cross-process reproducibility).

### What's intentionally *not* in Layer 0

No formulas for M, T, λ, probability, sampling, or event generation.
Just the shapes those formulas will eventually produce and consume.

---

## 5. Layer 1 — Data Layer + JSON Schemas (✅ Done)

**Goal:** Get real-world data (players, teams, formations, historical
priors) from JSON files into validated, cross-referenced, in-memory
Python objects — with zero hardcoded team lists, full referential
integrity checking, and a provenance system that can never let fake
"placeholder" data accidentally reach a calibration or production
pipeline.

### Structure

```
football_engine/data_layer/
├── schemas.py       # On-disk JSON record shapes: PlayerSeasonRecord,
│                    # TeamSeasonRecord, FormationRecord, HistoricalPriorRecord
│                    # + SourceMetadata/RecordStatus/DatasetMetadata
│                    # (kept separate from core/* — see box below)
├── loader.py         # JSON → Pydantic-validated Record → referential
│                    # integrity checks → in-memory repository
├── repository.py     # PlayerRepository, TeamSeasonRepository,
│                    # FormationRepository, HistoricalPriorRepository —
│                    # PLACEHOLDER-aware, exclude fixtures by default
└── exceptions.py     # DataLayerError hierarchy with debuggable messages

data/
├── schemas/          # Hand-maintained JSON Schema mirrors (for external
│                    # tooling/editors) — Pydantic is the real authority
├── raw/              # Reserved for future ingestion; currently empty
└── normalized/       # The engine-ready JSON the loader actually reads
    ├── players/player_seasons.json
    ├── teams/team_seasons.json
    ├── formations/formations.json
    └── historical_priors/historical_priors.json
```

### Why provenance/metadata isn't on the core Layer 0 models

`SourceMetadata` (status, source, confidence, retrieved_at,
manual_override) lives only in the data layer's `*Record` schemas, never
on `PlayerSeason`/`TeamSeason` themselves. Two reasons: (1) it would be
a Layer 0 contract change, which is out of scope without a real
contradiction; (2) keeping it off the core models guarantees provenance
bookkeeping can never accidentally leak into a calculation path.

### The PLACEHOLDER safety system

Every data record carries a `status`: `PLACEHOLDER`, `IMPORTED`, or
`CURATED`. A Pydantic validator enforces that PLACEHOLDER records must
have `confidence == 0.0` and `source == null` — they literally cannot
be constructed any other way. Every repository's `.all()` method
**excludes PLACEHOLDER records by default**; callers must explicitly
pass `include_placeholder=True` to see them. On top of that,
`DataRepositories.production_ready_team_ids()` returns only teams whose
own record *and every player in their roster* are non-placeholder — so
fixture data can never silently slip into a calibration run.

### The pipeline

```
RAW SOURCE  →  INGESTION/CURATION  →  NORMALIZED (data/normalized/*.json)
    →  VALIDATION (loader.py)  →  in-memory repository
```

`data/raw/` and an ingestion stage are reserved for later — nothing
currently reads from `data/raw/`, and no ingestion code exists yet (see
"Known limitations" below for exactly why).

### Adding team #41 (or #101, or #501) — the actual test of extensibility

```
1. Add PlayerSeason entries to data/normalized/players/player_seasons.json
2. Add a TeamSeason entry to data/normalized/teams/team_seasons.json
   whose roster lists those PlayerSeason ids
3. (Optional) Add a HistoricalPrior entry, or omit for a Tier 3 team
4. Run pytest
```

No Python file changes. `load_all()` has no hardcoded team list anywhere
— it discovers everything from JSON at call time.

### Current seed dataset — availability disclosure

The earlier authoring overview described three team seasons, 33 player-season placeholders, and five standard formations covering historical-prior tiers. **Those `data/normalized/*.json` files were not supplied in this repository snapshot.** They must not be represented as a locally loaded or verified dataset.

The local repository contains JSON schemas and temporary test fixtures only. The six existing seed-integrity tests currently fail at the missing `data/normalized/players/player_seasons.json`. No fake seed files were created to make those tests pass. The required companion files are teams/team_seasons.json, formations/formations.json, and historical_priors/historical_priors.json.

Formation data authored before the explicit side/depth contract must be updated by its author with valid geometry for every slot. The existing provenance/PLACEHOLDER exclusion system remains unchanged.

---

## 6. Layer 2 — implemented mathematics with an explicit possession dependency

### Current status

| Component | Current state |
|---|---|
| E-12 | CLOSED; structure/quality/tier separation unchanged |
| FormationEngine | W/H/C/P/U/Ts implemented; geometry/roles only; unchanged in this delivery |
| TeamDimensionEngine | D1 weighted Attack/Creation/Defense; unique-GK Goalkeeping; four independent values |
| TeamIdentityEngine | Five weighted components + C/U proxies; eighth pre-prior field supplied by an explicit PossessionTendencySource |
| Historical-prior blends | Existing functions and exact-once wiring unchanged |
| TeamModelBuilder | Returns a complete model with an explicitly configured source; raises a named gap without one |

D1 validates but does not numerically use StructuralFeatures. For a fixed squad/role assignment it is geometry-invariant: an explicit V1 simplification, not a hidden formation bonus. Its role weights are the memo's new Layer 2 priors, never reused scorer/assist weights.

Identity formulas and limitations are fully specified in [the corrected V3 memo](docs/team_dimension_and_identity_design_memo_v3.md). Tempo/risk/compactness/build-up are labeled modeling proxies. No evidence of empirical validity or independent pace contributions is invented.

The optional-at-construction possession source is an explicit missing-data/model boundary. It receives sorted immutable player-season IDs and supplies independently established pre-prior tendency. There is no production default source, new schema field, neutral value, prior-only bypass or inferred possession formula. Missing/invalid source data raises, rather than returning a fake identity.

The unchanged FormationEngine produces (.8,.5,.5,.28,.32,.84) for the fully specified synthetic 11-player geometry. The new exact-reference fixture verifies real Module 1→2→3 execution, source injection and prior blending. It is not historical reconstruction.

F-1(b) remains: identity and raw structural features travel separately to future Module 5. That policy must define ownership once, especially for C/U also represented by identity proxies. It is not silently supplied by this implementation.

**Still open:** actual possession-data/estimator choice, proxy/weight calibration and real historical normalized data. Automatic Layer 2 is not declared complete solely because a caller can supply its missing input.

Current delivery: [implementation report](docs/LAYER2_MEMO_V3_IMPLEMENTATION_REPORT.md). Previous checkpoints: [E-12](docs/E12_ARCHITECTURE_DECISION.md), [FormationEngine spec](docs/FORMATION_ENGINE_V1_SPEC.md), [historical migration/formation report](docs/LAYER2_E12_FORMATION_REPORT.md).

---

## 7. Layer 3 — Matchup + λ Engine

**Implemented:** the specified M/T/λ formulas from the 2026-09-08 canonical authorization, plus explicit typed dependency boundaries. This is not a fully autonomous Layer 3 pipeline until its missing helpers are supplied.

```text
football_engine/matchup/
├── __init__.py
├── configuration.py       # named creation coefficients and FormFactor bounds
├── dependencies.py        # required directional helper values; tactical policy protocol
├── errors.py              # explicit specification-gap/input errors
├── _validation.py         # numerical domain checks, no epsilon or hidden clamp
├── tactical_profile.py    # Module 5: separate identity/structure/state policy boundary
├── matchup_engine.py      # Module 6: exact independent M/T equations in both directions
└── lambda_calculator.py   # Module 7: exact base λ, venue, standalone/tournament Form
```

- Module 5 delegates to an explicitly supplied TacticalProfilePolicy and validates its final TacticalProfile. Exact state adjustments and the one-time P/U/Ts composition were not supplied, so no default/neutral policy is invented—even for NORMAL.
- Module 6 implements GK factor, relative strength, stable sigmoid/possession, creation realization/factor, adjusted base, press/width/tempo interactions, M, space behind defense, and T. Three helper outputs are explicit, independently supplied dependencies per direction: PressDisruption_M, WidthMismatch, PressTransitionOpportunity_T.
- Module 7 implements `baseline*M + transition_weight*T`, then venue multiplier and Form exactly once. Standalone Form is exactly 1.0; tournament Form is read from TeamRuntimeState. The provided RPI-to-Form clamp is implemented as a scalar helper; RPI derivation itself remains external/unspecified.
- There is no RNG, probability model, event generation, FormationEngine duplication, generic tactical multiplier, V2 red-card multiplier, or duration scaling.
- Possession uses the existing `possession_tendency_final` field. The literal supplied formula is evaluated separately in both directions; no unapproved complementary-share normalization is added.
- Original Layer 3 tests still hand-build upstream fixtures. New V3 tests additionally transport real Layer 2 outputs through an explicitly test-only tactical policy and supplied helpers. Canonical policy/helper integration and real-data end-to-end validation remain pending.

### Remaining helper-spec gaps

1. PressDisruption_M: exact equation, domain, and permitted signal ownership.
2. WidthMismatch: exact equation and domain.
3. PressTransitionOpportunity_T: independent exact equation and permitted inputs.
4. Exact field-by-field MatchState→TacticalProfile adjustments.
5. Exact one-time structural P/U/Ts + identity baseline composition.
6. RecentPerformanceIndex derivation (not needed when a valid tournament form_factor is already supplied).

The original architecture checkpoint is now preserved under docs/references/; the original Layer 3 test fixture still records only the previously supplied rounded intermediates. No new full canonical-example regression was added in this Layer 2 task. **PossessionShare(B) = 0.231; CreationRealization(B) = 0.6 + 0.4 × 0.231 = 0.6924 ≈ 0.692, not 0.231.** Three downstream links are verified from the provided rounded intermediates: 0.6924 creation realization, 0.730719 adjusted base, and 1.24285 base λ. A full canonical-example replay is **not** claimed.

Detailed equations/interfaces and scope: `docs/LAYER3_SPEC_AND_GAPS.md`. Actual results, failed-test reasons, and file-change audit: `docs/LAYER3_IMPLEMENTATION_REPORT.md` and `verification/`.

---

## 8. Cross-cutting engineering practices used throughout

- **Pydantic everywhere for data**, frozen (`ConfigDict(frozen=True)`)
  wherever the architecture says "immutable," mutable
  (`validate_assignment=True`) only where the architecture explicitly
  calls for runtime state (`TeamRuntimeState`).
- **Validators enforce architecture invariants directly in the model**,
  not just in tests — e.g. `ParameterSet` rejects out-of-T.12-bounds
  values at construction time; `HistoricalPrior` rejects a Tier 3 record
  with `alpha != 1.0`; `SegmentOutcome` rejects a goal count/minute
  mismatch.
- **Custom exception hierarchies** per layer
  (`FormationEngineError`/`TeamDimensionEngineError`/
  `TeamIdentityEngineError` in Layer 2; `DataLayerError` and its
  subclasses in Layer 1) so failures are debuggable by type, not just by
  string-matching an error message.
- **Actual runtime verification.** Python/Pydantic imports and assertions now run under the existing local pytest-compatible harness. This is not the full pytest distribution. Its missing `pytest.raises(...).value` compatibility feature was repaired without changing existing tests; collection errors now count as failures and failed runs exit nonzero. Syntax/import checks supplement, rather than replace, runtime execution.

---

## 9. Test suites — current actual execution

| Scope | Passed | Failed | Total |
|---|---:|---:|---:|
| Previous E-12/Formation repository checkpoint | 223 | 6 | 229 |
| **Current repository-wide result** | **280** | **6** | **286** |
| New D1 numerical tests | 21 | 0 | 21 |
| New identity numerical/source tests | 25 | 0 | 25 |
| New real Layer 2 pipeline/memo-audit tests | 11 | 0 | 11 |
| **New tests, isolated rerun** | **57** | **0** | **57** |
| **Layer 3-specific health, isolated rerun** | **112** | **0** | **112** |

280/286 is repository-wide; 112/112 is Layer 3-specific. Earlier 172/178 and 223/229 totals describe earlier repository checkpoints. All six current failures are unchanged seed tests first raising DatasetFileError at missing data/normalized/players/player_seasons.json.

Only obsolete Module 2/default-builder stub expectations were migrated in existing tests. Nothing was skipped/xfail or weakened to hide a regression. The default identity-gap tests still pass because an explicit possession source is required, not because automatic possession estimation exists.

Run from the project root:

```bash
python3 run_tests_shim.py --json test-results.json
```

This is the existing limited pytest-compatible harness, not the full pytest distribution. Full repository runs correctly exit nonzero for the six known failures. New results, source audit and patches: verification/layer2_memo_v3/. Older logs retain their checkpoint-specific meaning.

---

## 10. Known limitations — stated plainly

- **Automatic Layer 2 remains incomplete.** Formation, D1 and the specified identity components work, but the actual possession source/estimator is not defined by the current data schema. Explicit dependency injection is not a fabricated estimator or closure of that gap.
- **Layer 3 missing helper equations remain explicit.** Module 5 needs its approved composition/state policy. Module 6 needs three independent named helper outputs per direction. Defaults, inferred formations, and fabricated tactical multipliers are not supplied.
- **The canonical-example regression remains partial.** The source checkpoint is now available, but the historical test fixture still checks only three rounded-intermediate links. Full reference verification and missing helper definitions remain separate work.
- **Normalized seed data is absent.** The six existing seed tests fail transparently; no synthetic production dataset was invented. Data-layer tests using temporary fixtures do execute.
- **No end-to-end game exists yet.** Conditional synthetic Layer 2→3 transport is tested, not complete canonical integration. Probability/sampling, the Layer 5 runtime loop, events/attribution and calibration remain pending.
- **State write ownership remains orchestration discipline.** The eventual Layer 5 state updater is not implemented; Layer 3 only reads its limited runtime inputs.
- **Global Layer 0 architecture tests are not a completed suite.** New Layer 3 tests cover its own purity/import/anti-double-counting boundaries, not every future whole-engine invariant.
- **No real historical ingestion or calibration has been performed.** Fixtures are labeled test inputs, not researched historical estimates.
- **Verification used a limited local pytest-compatible harness, not the full pytest distribution.** Its scope and actual results are documented; no unsupported runner features are used by the new tests.

---

## 11. What's next — real data and the remaining explicit dependencies

1. Decide and populate the actual pre-prior possession-tendency source or estimator. Any PlayerSeason/TeamSeason schema extension is a separate explicit migration; do not use a neutral fallback or reuse the same historical prior.
2. Validate the D1/identity weight priors and pace/shot/cover/connectivity proxies against real historical data, not only synthetic numerical tests.
3. Specify Module 5 composition/state rules and Layer 3 helper equations, reconciling build-up/press ownership without hidden changes to the approved math.
4. Verify the complete reference example and real-data integration, then implement probability/sampling and runtime orchestration.
5. Continue to events/attribution, tournament state, calibration and UI within their later approved scopes.
