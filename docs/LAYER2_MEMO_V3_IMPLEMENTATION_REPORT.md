# Layer 2 — Design Memo V3 implementation report

Date: 2026-09-09. Scope: apply corrections to the user-supplied V2 memo and execute the specified next-step mathematics. Original source documents are preserved unchanged under docs/references/.

## Actual delivery status

- **FormationEngine and E-12:** unchanged, already implemented/closed.
- **TeamDimensionEngine:** D1 implemented using the exact V2 role weights, separate from Section R attribution tables. Four dimensions remain distinct. A unique GK supplies Goalkeeping directly.
- **TeamIdentityEngine:** five role-weighted components and the C/U structural proxies implemented. An explicit PossessionTendencySource supplies the eighth pre-prior field; no estimator, neutral constant, prior reuse, or rejected proxy was added.
- **Full TeamModel assembly works conditionally**, with a deliberately supplied source. The default builder still raises TeamIdentitySpecificationGapError because possession cannot be inferred from the current schema under the specified constraints.
- **Automatic Layer 2 reconstruction is NOT declared complete.** Its possession-data/estimator decision remains open. The statistical validity of proxies and weights is also unproven without real data/calibration.
- Layer 0/1 source and schemas, FormationEngine, existing prior blends, Layer 3 production/math tests, RNG, and the harness are unchanged. Builder execution order/signatures are unchanged; only its status docstrings changed.

## Memo corrections actually applied

The standalone corrected memo is `team_dimension_and_identity_design_memo_v3.md`.

1. Removed the false attribution of `PressDisruption=B.press_final*(1-A.build_up_control_score)` as an approved existing helper equation. Current code takes an explicit helper value; the source checkpoint does not supply that equation.
2. Distinguished the real verbal-rule/PossessionShare ownership tension from an unproven duplicate implementation. Both build-up and opponent press explicitly affect PossessionShare. Layer 3 is preserved, not silently repaired.
3. Replaced the inaccurate quadratic-sensitivity claim with the correct fixed-helper sigmoid sensitivity, verified numerically. No hypothetical helper was implemented.
4. Replaced unconditional SAFE/independence claims about pace with a conditional, testable audit. M/T additivity is not independence; FB and CM have nonzero attack-pace weights.
5. Labeled pace-based tempo, shooting-based risk, cover-based compactness and connectivity-based build-up as uncalibrated proxies, not empirical measurements.
6. Clarified D1 invariance: for a fixed PlayerSeason list/role assignment, geometry does not alter dimensions. This is a deliberate V1 simplification, not implemented structural bonuses.
7. Replaced missing V1 cross-references and the incomplete four-player toy example with complete definitions, edge cases, and a fully specified 11-player reference, including GK pace.
8. Corrected calibration accounting: 72 displayed entries are not 72 identifiable fit parameters. With zeros and GK lookup fixed, there are at most 47 scale-normalized positive-weight ratios. This delivery fits zero parameters.
9. Distinguished pre-prior compactness=C from final compactness after the existing historical blend. No double prior blending is introduced.
10. Defined missing-data, zero-denominator, malformed/nonfinite input, determinism and source-boundary behavior explicitly.

## Production changes

### New files

- `football_engine/team_model/role_weight_priors.py`: frozen row types and read-only dimension/identity weight mappings.
- `football_engine/team_model/_validation.py`: strict selection/role/GK validation and finite numerical guards.
- `football_engine/team_model/_weighted_mean.py`: deterministic positive-weight means with explicit denominator errors and a convex-interval floating-point guard.
- `football_engine/team_model/dependencies.py`: ID-only PossessionTendencySource protocol; no default implementation.

### Updated existing files

- `team_dimension_engine.py`: replaces the missing-formula stub with actual D1 computation.
- `team_identity_engine.py`: implements specified components, validates the explicit source result and prior inputs, preserves exact-once historical blending, and exposes the remaining gap precisely.
- `team_model_builder.py`: documentation only. Its existing injected-engine wiring now supports conditional complete assembly without changing execution/signatures.
- `team_model/__init__.py`: accurate status and exports of the new dependency/error.
- `tests/test_team_model.py`: only obsolete Module 2/default-builder stub expectations and associated comments updated. No unrelated tests were disabled or weakened.

### Possession dependency details

The new constructor parameter is keyword-only. Existing derive/build signatures stay the same:

```python
identity_engine = TeamIdentityEngine(possession_source=my_preloaded_source)
builder = TeamModelBuilder(identity_engine=identity_engine)
model = builder.build(players, formation, historical_prior)
```

The source receives only `player_season_ids=tuple(sorted_ids)` and must return separately established, finite pre-prior tendency data for that exact roster. Its purity/provenance are a caller contract, not something a Python Protocol can guarantee. Source errors propagate and invalid results are rejected. No source is an explicit NotImplementedError subtype, including when a curated prior exists or alpha=0. No new PlayerSeason/TeamSeason field or legacy data default was introduced.

The fixture value 0.62 exists only as labeled synthetic test data. It is not a production default or a newly calibrated prior. Rejected creation/press/geometry possession proxies are not hidden in production callbacks.

## Numerical reference and tests

An independent Fraction-based calculation generated all expected values before production aggregation was executed. The full inputs and rational reference are in `tests/fixtures/layer2_memo_v3_example.json`.

The 11-player example gives:

- Structure: W=.8, H=.5, C=.5, P=.28, U=.32, Ts=.84.
- Dimensions: Attack=77.35443037974683, Creation=74.11111111111111, Defense=73.93406593406593, Goalkeeping=85.
- With explicit pre-prior possession=.62, the eight-field identity is complete; its five weighted values and all post-prior results are specified in the corrected memo/fixture.
- Existing alpha=.55 and creation delta=.03 yield final Creation=75.46111111111111, not a new adjustment formula. Existing possession prior=.95 yields final possession=.7685.

### Executed results

| Scope | Passed | Failed | Total |
|---|---:|---:|---:|
| Pre-change repository baseline | 223 | 6 | 229 |
| Compatibility after replacing old stubs | 223 | 6 | 229 |
| **Current repository-wide** | **280** | **6** | **286** |
| New D1 tests | 21 | 0 | 21 |
| New identity tests | 25 | 0 | 25 |
| New real Layer 2 pipeline / memo-audit tests | 11 | 0 | 11 |
| **New tests, separate run** | **57** | **0** | **57** |
| **Layer 3, separate run** | **112** | **0** | **112** |

The runner is the existing limited local pytest-compatible harness, not the full pytest distribution. Repository runs correctly exit 1 because of the same six data-layer seed failures; both isolated scopes exit 0. The earlier 172/178 and 223/229 were historical repository-wide checkpoints, never Layer 3 pass rates.

The only six failures remain in tests/test_data_layer.py:

- test_seed_dataset_every_roster_resolves
- test_seed_dataset_has_zero_production_ready_teams
- test_seed_dataset_loads_completely
- test_seed_dataset_no_duplicate_team_ids
- test_seed_dataset_schema_versions_are_supported
- test_seed_dataset_tier_coverage

Each first raises DatasetFileError at missing `data/normalized/players/player_seasons.json`. No seed data, silent skip, xfail or fabricated historical model was used to hide them.

### Coverage and limits

Tests cover exact weight values, immutability, independent arithmetic, convexity/bounds, monotonicity, input-order invariance, selected-GK behavior, ability-vs-identity isolation, zero denominators, bad types/nonfinite values, role-dependent pace responses, ID-only source calls, no source/prior fallback, distinct roster lookups, and exact-once prior blending.

Real FormationEngine→DimensionEngine→IdentityEngine builder execution is tested with an explicit synthetic possession source. A separate transport test supplies a **test-only** tactical policy and helper values to unchanged Layer 3. This does not implement the missing Module 5/6 equations or a full match simulation. Contract tests expecting the default possession gap pass for that reason, not because the gap is closed.

## What stays open

1. Actual possession data/estimator and any separately approved schema migration.
2. Formal Module 5 structural/identity composition and state adjustments; C/U cannot be blindly applied twice.
3. Three Layer 3 helper equations and the verbal-vs-formula ownership issue for build-up/press. No A/B interpretation was silently chosen.
4. Historical-data validation and calibration of the proposed proxies/weights.
5. Probability/sampling, runtime orchestration and full end-to-end match simulation.

Current logs, exact source-change audit, diffs and original-reference hashes are under `verification/layer2_memo_v3/`. Earlier verification reports retain their historical checkpoint scope. No Git commits are claimed; changes are delivered as source and auditable patches.
