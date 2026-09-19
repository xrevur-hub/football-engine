# E-12 — Type Semantic/Schema Mismatch

**Formal architecture decision record — 2026-09-08**

**Current issue status: CLOSED — implemented and verified. Architecture: APPROVED.**

Execution update: the subsequent user request to complete Layer 2 was used to execute the already-approved Step A/Step B scope. The original architecture approval alone did not trigger implementation; the stages were tested separately. See [the delivery report](LAYER2_E12_FORMATION_REPORT.md).

Authority: the user's architecture approval and subsequent request to complete Layer 2 in this project conversation on 2026-09-08. Implementation was limited to the approved E-12 migration and the already-approved FormationEngine mathematics; missing Module 2/3 formulas were not invented.

## 1. Decision register

| E-12 component | Status |
|---|---|
| Semantic diagnosis | APPROVED |
| Target ownership | APPROVED |
| Target separation | APPROVED |
| Migration principle | APPROVED |
| Implementation | Step A migration and Step B FormationEngine implemented and separately verified |
| Overall issue | CLOSED on code and test evidence; not merely on architecture approval |

## 2. Fundamental separation

**Formation Structure ≠ Snapshot Quality ≠ Historical Tier**

These are three distinct concepts, not alternate labels for one enum, score, or classification.

| Concept | Ownership and role | Must not be conflated with |
|---|---|---|
| Formation Structure | Layer 2 derives structural features from explicit geometry and role occupancy | Snapshot completeness, data quality, historical tier, player quality |
| Historical Snapshot Quality | Metadata owned by Layer 1; its documented weights are consumed by calibration (Layer 7) | Formation classes, TeamIdentity, runtime strength or λ modifiers |
| Historical Tier | The existing historical-team/prior-tier concept remains separate and unchanged | Snapshot quality or formation structure |

Snapshot quality is also not an alias for HistoricalPrior.alpha or provenance confidence. This decision introduces no conversion between any of these concepts.

## 3. Approved target: FormationEngine and StructuralFeatures

The semantic computation is:

**Formation → StructuralFeatures**

For V1, the active numeric output is:

**StructuralFeatures = (W, H, C, P, U, Ts)**

with `formation_name` retained as descriptive metadata only.

- The structural signals depend on explicit `side`/`depth` geometry and role occupancy.
- Player abilities, tendencies, pace, and quality do not enter the V1 mathematical derivation.
- No `formation_type`, TYPE_A/B/C label, or data-quality metric may influence that computation.
- `slot_id` and `formation_name` must not be parsed for structural/classification semantics.
- The approved six rules and disclosed H = 0.5 baseline are unchanged by E-12.
- Existing inactive V3 fields are outside the minimal migration and remain untouched unless separately authorized.
- This record specifies semantic ownership. Recording it does not change any current callable signature or validation behavior.

The target schema removes the misleading required `StructuralFeatures.formation_type` field rather than supplying a placeholder, making it silently optional, or replacing it with another invented formation classifier.

## 4. Approved target: HistoricalSnapshotQuality

**HistoricalSnapshotQuality → CalibrationWeight**

| Category | Canonical meaning supplied by the user | Weight |
|---|---|---:|
| TYPE_A | Full Snapshot | 1.0 |
| TYPE_B | Partial Snapshot | 0.5 |
| TYPE_C | Minimal Snapshot | 0.2 |

- Introduce the correctly named `HistoricalSnapshotQuality` concept in **Layer 1**, not in StructuralFeatures or TeamIdentity.
- Keep the metadata in Layer 1; calibration consumes its weights.
- Do not apply these weights to FormationEngine outputs, player/team abilities, TeamIdentity, Matchup signals, or runtime λ.
- The incorrectly named `FormationStructuralType` is to be removed in the explicitly authorized migration, not repurposed as a structural taxonomy.
- This record does not supply automatic Full/Partial/Minimal completeness predicates, snapshot-record granularity, or an exact weighted calibration objective. None may be invented during migration.

## 5. Migration integrity — no semantic fabrication

A legacy fixture's TYPE_A value is **not evidence** that the fixture describes a Full Snapshot. The same principle applies to legacy TYPE_B and TYPE_C values.

The following automatic mapping is forbidden:

**old formation_type TYPE_A → HistoricalSnapshotQuality.TYPE_A**

Equality of label strings is not evidence of equality of meaning. A quality assignment requires independent, approved snapshot evidence; an old structural field or fixture default is insufficient.

The migration must also not hide the incompatibility through:

- A TYPE_A/B/C default or an invented UNKNOWN structural class.
- A parser inferring quality from slot IDs, formation names, side, depth, or roles.
- Silent aliases that retain the wrong ownership or field meaning.
- Silently dropping legacy fields through `ignore unknown fields` behavior.
- Treating the change as fully backward-compatible when a required field/enum is removed.

Any legacy input/serialization handling, necessary fixture/import updates, and resulting contract break must be explicit and auditable after authorization. Historical Tier, historical-prior blending, and unrelated schemas are not redesign targets.

## 6. Two separately auditable implementation steps — executed separately

Use two distinct commits when version control is available, or two distinct conceptual change sets. Do not merge contract migration and football formulas into one unreviewable step.

### Step A — Minimal schema / ownership migration

After explicit implementation authorization:

1. Remove `FormationStructuralType` from its incorrect Layer 0 role.
2. Remove `StructuralFeatures.formation_type` explicitly.
3. Introduce `HistoricalSnapshotQuality` in Layer 1.
4. Update only the imports, fixtures, documentation, and contract tests required by that migration; do not relabel fixture values as historical quality evidence.
5. Run and report migration-focused and existing regression tests. Separate genuine contract-migration changes from unrelated existing failures.
6. Do not implement FormationEngine formulas in this step; do not alter Layer 3 math.

**Expected evidence:** the revised structural output contract can be constructed and transported without any snapshot-quality label; quality ownership is represented independently in Layer 1; legacy incompatibility is not silently hidden.

### Step B — FormationEngine implementation

After Step A is verified and the implementation scope is explicitly authorized:

1. Implement the already-approved W, H, C, P, U, Ts rules against the migrated structural contract.
2. Test the six numerical rules, geometry/role dependence, determinism, identifier irrelevance, and absence of snapshot-quality influence.
3. Do not introduce an A/B/C formation classifier or a new Layer 3 equation.
4. Report formula-test results separately from the preceding migration evidence.

The separation was preserved: Step A passed 184/190 repository tests before Step B math was added; Step B passed 223/229. Each checkpoint has a separate patch and hash snapshot. The only six failures at both stages are missing seed data. No actual Git commits are claimed; these are two auditable conceptual change sets.

## 7. Closure criterion

**StructuralFeatures must be produced without any dependency on Snapshot Quality, and the new Layer 0/1 contracts must be applied explicitly—not through silent compatibility.**

Closure requires evidence from the authorized migration and the relevant construction/derivation tests; architecture approval or this document alone is insufficient. Do not mark E-12 CLOSED merely because its semantic diagnosis is now understood.

## 8. Current closure evidence and remaining boundaries

- E-12 is **CLOSED for the approved semantic/schema mismatch**: the misnamed core enum/field are removed, the structural schema rejects legacy/unknown fields, and HistoricalSnapshotQuality is separately defined/exported in Layer 1.
- **12/12 migration tests** verify explicit separation, strict serialization, preserved structural fields, independent HistoricalTier, and the exact immutable quality-weight registry.
- **39/39 FormationEngine tests** verify actual structure generation from geometry/roles, including no player-quality reads or snapshot-quality dependency.
- Actual manual-layout output: W=.8, H=.5, C=.5, P=.28, U=.32, Ts=.84, plus descriptive formation_name; no formation_type is required or returned.
- Quality classification predicates, snapshot-record granularity, and calibration objective usage remain outside this migration. No automatic quality classification or runtime quality weighting was added.
- Layer 3 production equations are unchanged and its migrated fixture-based suite passes **112/112**.
- **Automatic Layer 2 is not entirely complete:** D1 and specified identity components are now implemented under the corrected V3 memo, but a complete identity requires an explicitly supplied possession source. Its actual data/estimator definition remains open; no fallback/fixture value is inserted into production.
- Real historical normalized data and full end-to-end validation remain pending.
