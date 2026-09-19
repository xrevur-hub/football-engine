# Layer 2 delivery — E-12 migration and FormationEngine V1

**Historical checkpoint report.** D1 dimensions and conditional identity assembly were subsequently implemented; see [the current V3 report](LAYER2_MEMO_V3_IMPLEMENTATION_REPORT.md). The 223/229 count and missing-all-Module-2/3 statements below describe the earlier delivery, not today's state.

Date: 2026-09-08. The user's request to complete Layer 2 was used to execute the previously approved E-12 architecture migration and FormationEngine mathematics as separate checkpoints.

**Actual result: E-12 and FormationEngine are implemented. Layer 2 is NOT entirely complete: TeamDimensionEngine and TeamIdentityEngine still lack approved numerical derivation specifications.** Missing equations were not replaced with guesses or fixture defaults.

## Step A — explicit contract migration

- Removed FormationStructuralType from core/enums.py, without an alias.
- Removed StructuralFeatures.formation_type from core/team_dimensions.py; configured explicit extra-field rejection. Legacy payloads now fail validation instead of being silently accepted.
- Preserved formation_name, the six active bounded fields, immutability, and both inert V3 fields. TeamDimensions itself is unchanged.
- Corrected only the obsolete ownership docstring in core/formation.py; its behavior is unchanged.
- Added HistoricalSnapshotQuality and the immutable canonical calibration-weight registry in data_layer/snapshot_quality.py, exported by Layer 1: TYPE_A Full Snapshot → 1.0; TYPE_B Partial Snapshot → 0.5; TYPE_C Minimal Snapshot → 0.2.
- No legacy fixture type was converted into snapshot-quality evidence. No default quality, classifier, HistoricalTier mapping, or runtime/λ quality multiplier was created.
- Exact snapshot-record granularity and completeness predicates remain unspecified. No guessed quality field was attached to existing player/team records and no calibration optimizer was added.
- Migrated only affected fixture/import/contract assertions. Layer 3 production equations were not modified.

Step A alone: **184 passed, 6 failed, 190 total**, including **12/12 migration tests** and **112/112 Layer 3 tests**. The same six seed files/data-related tests failed before this work. FormationEngine was still a mathematical stub at this checkpoint.

A separate snapshot, hash record, and patch were recorded before Step B. These are auditable conceptual change sets, not claimed Git commits in a repository without Git history.

## Step B — six approved FormationEngine rules

For N=10 non-GK slots and K=floor(N²/4)=25:

- W = (left + right outfield slots)/N.
- H = 0.5, the explicitly named V1 baseline prior.
- C = (back slots + midfield DM slots)/N.
- P = connected middle/front pairs/K.
- U = connected back/middle pairs/K.
- Ts = front slots × non-front outfield slots/K.

Connectivity excludes only opposite LEFT/RIGHT pairs. The engine reads only explicit geometry/role occupancy for features, and player id/role for input validation. No ability/tendency/pace/quality, role-weight table, formation-name parsing, opponent/runtime/RNG/I/O/λ logic was introduced.

Exactly-one-GK and unique-slot checks are enforced at the engine boundary without unrelated loader changes. The public derive(players, formation) signature is retained. See FORMATION_ENGINE_V1_SPEC.md for the full definitions, normalization, boundaries, and dependency rules.

The existing manual test geometry now produces actual **W=.8, H=.5, C=.5, P=.28, U=.32, Ts=.84**, plus descriptive formation_name; no formation_type is required or returned. This is code execution, not a historical accuracy claim.

## What still prevents complete Layer 2 implementation

The repository explicitly marks the derivation specification as missing in:

- football_engine/team_model/team_dimension_engine.py: module specification and derive().
- football_engine/team_model/team_identity_engine.py: module specification and _derive_pre_prior_identity().

| Engine | Equations still required |
|---|---|
| TeamDimensionEngine | Player/role contributions, weights, normalization, and any structural dependence for attack, creation, defense, goalkeeping |
| TeamIdentityEngine | Pre-prior possession_tendency, press_tendency, transition_tendency, tempo, risk_tolerance, compactness, build_up_control_score, attack_pace_factor mappings |

ROLE_ATTACK_WEIGHT and ROLE_CREATION_WEIGHT are scorer/assist attribution tables, not approved dimension-aggregation weights; they were not reused. Some identity outputs lack a corresponding direct PlayerSeason input field, so a generic average would itself invent a new model.

The existing historical-prior blending is already implemented and unchanged. Both missing-engine source files are unchanged. The builder now passes Module 1 and reaches the explicit Module 2 gap; no default TeamDimensions/TeamIdentity or fake complete model is returned.

To finish these engines under the existing no-invented-equations constraint, supply the canonical derivations or explicitly approve a newly designed mathematical specification. Implementation is not blocked by E-12 anymore; it is blocked by these actual missing equations. Real historical normalized data is also absent, preventing real-data/end-to-end validation independently of the code gaps.

## Current executed test results

| Scope / checkpoint | Passed | Failed | Total |
|---|---:|---:|---:|
| Pre-task repository baseline | 172 | 6 | 178 |
| Step A checkpoint | 184 | 6 | 190 |
| Current repository-wide, after Step B | **223** | **6** | **229** |
| Dedicated E-12 migration tests | **12** | **0** | **12** |
| New FormationEngine V1 tests | **39** | **0** | **39** |
| Layer 3-specific health after migration | **112** | **0** | **112** |

The previous **172/178 was repository-wide**, never a Layer 3 rate. The current repository-wide result is **223/229**, and a separate Layer 3-only rerun also returned **112/112**, exit status 0. Existing tests expecting Module 2/3 specification errors pass as contract tests, not evidence of completed derivations.

The existing local pytest-compatible harness was used, not the full pytest distribution. No tests were skipped/xfail or unrelated assertions weakened. The full run correctly exits nonzero for these six unchanged tests in tests/test_data_layer.py:

- test_seed_dataset_every_roster_resolves
- test_seed_dataset_has_zero_production_ready_teams
- test_seed_dataset_loads_completely
- test_seed_dataset_no_duplicate_team_ids
- test_seed_dataset_schema_versions_are_supported
- test_seed_dataset_tier_coverage

Each raises DatasetFileError first at missing data/normalized/players/player_seasons.json. No normalized historical seed data was supplied or fabricated.

## Audit and delivery scope

- Layer 0 behavior changes are confined to removing the misplaced enum/field and rejecting unknown structural fields. core/formation.py has only a documentation correction. Other core models, historical-prior blends, ParameterSet, runtime contracts, and RNG remain unchanged.
- Layer 1 has the new quality type/weight registry and exports. Existing loader, repository, record models, and JSON schemas are unchanged.
- Layer 2 has the actual FormationEngine implementation and updated package/builder status documentation. Modules 2/3 remain genuine explicit gaps.
- Existing affected fixtures/contract tests were migrated and two dedicated test modules added. Layer 3 production code and mathematical tests are unchanged.
- E-12 is CLOSED on the new contracts and quality-free actual derivation, not merely on documentation approval. Unspecified snapshot classification/data-population/calibration details remain separate later work.
- PROJECT_OVERVIEW.md and the E-12 decision now distinguish completed migration/formation work from incomplete Layer 2. Earlier Layer 3 delivery records remain historical, with an explicit scope note.
- Current logs, separate Step A/B patches, checkpoint hashes, and source-change audit are in verification/layer2/. The packaged filename deliberately does not claim layer2_complete.
