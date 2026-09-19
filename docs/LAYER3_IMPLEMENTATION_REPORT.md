# Layer 3 Implementation Report

**Historical Layer 3 delivery record.** Subsequent E-12/Formation and V3 Layer 2 work is documented in [the current report](LAYER2_MEMO_V3_IMPLEMENTATION_REPORT.md). Original 172/178 and unchanged-core assertions below describe the earlier delivery only. Current repository: 280/286; Layer 3 remains 112/112, with production math and its original tests unchanged in the V3 task.

Date: 2026-09-08. Scope: **Matchup + λ Engine**, Modules 5/6/7, under the user's final authorization.

## Review decision — APPROVED implementation, documentation-only correction

The user approved the **current Layer 3 implementation** on 2026-09-08, subject to the two documentation clarifications below. This approval does not mean the missing helper equations are implemented or that the whole pipeline works end-to-end.

- **Numeric label correction:** `PossessionShare(B) = 0.231`. The corresponding `CreationRealization(B) = 0.6 + 0.4 × 0.231 = 0.6924 ≈ 0.692`, **not 0.231**.
- **Result scope:** **172/178 is the repository-wide result** (172 passed, 6 failed). **112/112 is the Layer 3-specific test-health/acceptance result** (112 passed, 0 failed), within the current manual-fixture and explicit-helper-boundary scope.
- No new Layer 3 formula may be guessed. Remaining specification gaps require formal canonical definitions and approval.
- **Next priority: close Layer 2 first**, in delivery order FormationEngine → TeamDimensionEngine → TeamIdentityEngine, using approved historical inputs rather than mistaking manual fixtures for historical validation. E-12's target architecture is now formally approved, but the issue remains OPEN and implementation is not authorized. See [the E-12 architecture decision](E12_ARCHITECTURE_DECISION.md): Step A is the minimal Layer 0/1 contract/ownership migration; Step B is FormationEngine implementation, kept separately auditable. No current Layer 0, production-code, or test change is authorized by recording this decision.

This correction changes documentation only. The test totals below are the last verified execution results, not a newly claimed test run.

## Outcome

The explicitly defined M/T/λ equations are implemented and executable with explicit helper inputs. Missing equations remain typed, visible dependencies rather than invented football math. **The complete engine does not run end-to-end.** Layer 2 remains incomplete and unchanged.

### Implemented components

| Component | Actual status |
|---|---|
| Module 5 — Tactical Profile Generator | Implemented typed policy/delegation boundary with input/output validation. No production state-adjustment or structural/identity blending equations were invented. Missing policy raises SpecificationGapError, including for NORMAL. |
| Module 6 — Matchup Engine | Implemented all specified relative-strength, GK, sigmoid/possession, creation, interaction, M, space, and T equations. Both directions are evaluated independently. |
| Module 7 — λ Calculator | Implemented baseline*M + transition_weight*T, home/away factors, exact standalone form 1.0, precomputed tournament form, and scalar RPI-to-Form clamp. No RPI derivation or state mutation. |
| Layer 3 integration | Module 5→6→7 tested with explicit final-tactic/helper fixtures and manually built upstream core objects. Not Layer 2 integration. |

Production files added:

- football_engine/matchup/__init__.py
- football_engine/matchup/_validation.py
- football_engine/matchup/configuration.py
- football_engine/matchup/dependencies.py
- football_engine/matchup/errors.py
- football_engine/matchup/tactical_profile.py
- football_engine/matchup/matchup_engine.py
- football_engine/matchup/lambda_calculator.py

## What was NOT changed or implemented

Before/after SHA-256 comparison verified **all 36 protected original files unchanged**: Layer 0/core, Layer 1/source and JSON schemas, RNG source, Layer 2/source, and every original test/helper file. The only modified original repository files are PROJECT_OVERVIEW.md and run_tests_shim.py. New tests are separate files.

- No Layer 0 model, field, enum, constant, or parameter was modified.
- No Layer 2 formula/derive() was implemented or modified.
- No FormationEngine was copied into Layer 3.
- E-12 was not fixed. Snapshot-quality A/B/C labels are not classified, read for math, or used as runtime weights. Manual test objects pass explicit legacy enum literals only because the existing schema requires one.
- No structural values were added to or smuggled through TeamIdentity.
- No RNG, probability model, Poisson/Dixon-Coles sampler, event generator, attribution, generic tactical factor, hidden λ modifier, V2 red-card factor, or duration scaling was introduced.
- No seed data or canonical-example raw inputs were fabricated.

## Exact equations and configuration

Full equations, interfaces, helper directions, and coefficient provenance are in LAYER3_SPEC_AND_GAPS.md.

Every existing calibration knob and global anchor is read from the unchanged ParameterSet. The authorization's creation coefficients 0.6/0.4 and 0.7/0.3, plus FormFactor bounds 0.85/1.15, have no fields in that model. They are therefore exposed in a frozen Layer-3-local Layer3Coefficients object, not hidden in formulas and not added to Layer 0.

Literal canonical behavior worth noting:

- Possession uses TacticalProfile.possession_tendency_final. Each directed expression is evaluated as supplied; the two values are not forcibly made complementary because the supplied expression is not antisymmetric.
- λ is baseline*M + transition_weight*T, not baseline*(M + transition_weight*T).
- Existing k_t is unused because the authorized T equation does not contain it.
- Tournament form_factor is read and applied once, not treated as RPI or recomputed. Standalone mode ignores stored form and uses exactly 1.0.
- Undefined denominators and invalid/non-finite rates fail explicitly. There is no epsilon, strength cap, or corrective clamp outside the supplied FormFactor equation.

## Unresolved mathematical dependencies

1. **PressDisruption_M(defender→attacker):** exact equation, domain, and allowed inputs.
2. **WidthMismatch(attacker,defender):** exact equation/domain.
3. **PressTransitionOpportunity_T(defender→attacker):** separate equation/domain and permitted inputs. Never substituted with PressDisruption_M.
4. **MatchState→TacticalProfile:** exact field-by-field equations for NORMAL, LEADING, LOSING, REACTIVE.
5. **Structural/identity baseline composition:** one-time P/U/Ts composition and ownership before final tactical values. No mean/product/blend is guessed.
6. **RecentPerformanceIndex:** how to derive it from match history. The supplied scalar clamp is implemented; state already holding valid form suffices for tournament λ.

The three matchup helpers are required fields in DirectionalMatchupHelpers, independently supplied for each direction. There are no implicit zero/one helper defaults. Module 5 requires a TacticalProfilePolicy over separate identity/structure/state objects. Future approved equations can supply these dependencies without replacing the existing Layer 3 core-model interfaces.

Anti-double-counting tests validate built-in M/T routing while supplied helpers are held fixed. An arbitrary future helper policy still needs its own dependency audit; the tests do not claim to prove unknown helper mathematics.

## Architecture-example regression

The supplied rounded example outputs were saved as a provenance-labeled reference JSON. The original raw dimensions/tactical inputs and helper equations were not available.

Verified from supplied intermediates:

| Link | Actual result | Quoted approximation |
|---|---:|---:|
| CreationRealization(B) = 0.6 + 0.4 × PossessionShare(B), with PossessionShare(B) = 0.231 | 0.6924 | 0.692 |
| BaseRelativeStrength 1.089 × CreationFactor 0.671 | 0.730719 | 0.731 |
| 1.35 × M 0.677 + 0.55 × T 0.598 | 1.24285 | 1.243 |

**Full canonical-example reproduction is NOT claimed.** For B→A it requires PressDisruption_M(A→B), WidthMismatch(B,A), PressTransitionOpportunity_T(A→B), and original raw dimensions/final tactics. Starting from identity/structure additionally requires the Module 5 policy equations. Separate formula unit tests use explicitly synthetic inputs; they are not passed off as recovered original example values.

## Actual test results

Environment: Python 3.13.14, Pydantic 2.13.5. Execution used the existing local pytest-compatible harness, **not the real pytest distribution**.

| Scope | Passed | Failed | Total |
|---|---:|---:|---:|
| Original tests before harness repair | 59 | 7 | 66 |
| Original tests after shim .value compatibility repair | 60 | 6 | 66 |
| **Layer 3-specific health / acceptance — 112/112** | **112** | **0** | **112** |
| **Repository-wide result — 172/178** | **172** | **6** | **178** |

**Do not report 172/178 as the Layer 3 pass rate.** Its six failures belong to existing repository seed-data tests, not Layer 3. The Layer 3-specific result is **112/112**; it validates the implemented scope, not the still-missing helper formulas or real historical end-to-end integration.

New test-module counts:

| File | Tests |
|---|---:|
| tests/test_layer3_matchup.py | 43 |
| tests/test_layer3_lambda.py | 26 |
| tests/test_layer3_tactical.py | 11 |
| tests/test_layer3_boundaries.py | 23 |
| tests/test_layer3_architecture_reference.py | 5 |
| tests/test_layer3_pipeline.py | 4 |

Coverage includes every named main formula, both directions, parameter sensitivity, exact form/venue placement, stable sigmoid extremes, denominator/non-finite validation, repeated determinism, input immutability, required missing helpers, typed policy errors, source-level no-RNG/probability/events/FormationEngine/IO guards, per-signal M-only/T-only perturbations, and a manual-fixture Module 5→6→7 chain.

### Exact remaining failures

All six are pre-existing seed-data tests in tests/test_data_layer.py:

- test_seed_dataset_every_roster_resolves
- test_seed_dataset_has_zero_production_ready_teams
- test_seed_dataset_loads_completely
- test_seed_dataset_no_duplicate_team_ids
- test_seed_dataset_schema_versions_are_supported
- test_seed_dataset_tier_coverage

Each fails with **DatasetFileError: Dataset file not found**, first at `data/normalized/players/player_seasons.json`. The entire normalized dataset is absent from the supplied snapshot. Required companion paths are teams/team_seasons.json, formations/formations.json, and historical_priors/historical_priors.json. No tests were changed, skipped, disabled, or xfailed to hide these failures.

The initial seventh failure was `AttributeError: '_RaisesContext' object has no attribute 'value'` in an unchanged geometry test. The existing local shim lacked the standard raises-context property. Restoring that property fixed harness compatibility, not football logic; the test itself was left unchanged.

### Harness changes

- Preserved its actual import-and-call fixture execution model.
- Bundled the repaired shim at tools/pytest_shim/pytest.py for a portable download.
- Added discovery of all test_*.py modules, including the new tests.
- Added optional --module selection and --json result output.
- Counted collection/import errors as failures and made failed runs exit nonzero, rather than reporting an apparent successful process.
- No new tests rely on unsupported parametrization, skips, xfails, plugins, or fixtures.

Run from repository root:

```bash
python3 run_tests_shim.py --json test-results.json
```

A nonzero exit status is expected while the six seed-data tests remain blocked by missing normalized files. For Layer 3 only, repeat --module for the six tests.test_layer3_* module names listed above; this scope passes independently.

## Documentation and delivery

PROJECT_OVERVIEW.md now identifies Layer 3 as Matchup + λ Engine, distinguishes implemented formulas from helper gaps, records Layer 2 as incomplete, explains manual fixtures and pending real integration, corrects stale execution/seed-availability claims, and reports the actual test totals.

The project archive includes the implementation, unchanged upstream code, new tests and labeled fixtures, portable harness, specification-gap documentation, this report, and verification logs/manifests. It deliberately does not include fabricated normalized seed data or claim a runnable complete match simulation.
