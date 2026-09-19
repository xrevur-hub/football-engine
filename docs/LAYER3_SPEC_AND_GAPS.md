# Layer 3 — Matchup + λ Engine

**V3 Layer 2 update:** production Layer 3 is unchanged and separately passes 112/112. Original source availability statements below reflect the earlier delivery; the checkpoint is now preserved under docs/references/. The corrected V3 memo distinguishes its build-up/press verbal-rule tension from the still-undefined helper equations. No speculative press formula or term deletion was applied.

Implementation source: the user's **FINAL AUTHORIZATION — IMPLEMENT LAYER 3 NOW**, dated 2026-09-08. The formulas in that authorization are the source of truth for this layer. The original numbered architecture document was not supplied as a repository file.

**Status:** the explicitly specified M/T/λ formulas are implemented and executable with explicit helper inputs. Module 5 has an executable, typed delegation/validation boundary but no invented tactical composition or state equations. End-to-end Layer 2 → Layer 3 execution remains pending. This is not a complete match simulator.

## Review status — current implementation APPROVED

On 2026-09-08 the user approved the current Layer 3 implementation, with documentation corrections only. **112/112 is the Layer 3-specific test-health result; 172/178 is the repository-wide result, not the Layer 3 pass rate.** Those are the last verified run's results, not a new execution claim.

No additional Layer 3 equations may be guessed. Remaining gaps require formal definitions/approval. The next priority is to close Layer 2 using approved historical inputs before claiming real integrated validation. No Layer 0, implementation, or test change is authorized by this documentation review.

## 1. Scope and unchanged boundaries

- Module 5: `TacticalProfileGenerator` consumes `TeamIdentity`, `StructuralFeatures`, and `MatchState` separately.
- Module 6: `MatchupEngine` consumes existing `TeamDimensions` and final `TacticalProfile` objects, independently in both directions.
- Module 7: `LambdaCalculator` consumes existing `MatchupResult`, home/away `TeamRuntimeState` objects, and explicit tournament context; returns existing `LambdaPair`.
- FormationEngine belongs to Layer 2. Layer 3 neither imports nor calls it or any other Layer 2 derivation.
- Layer 0 models and Layer 2 code are unchanged. No structural fields were added to `TeamIdentity` or `TeamRuntimeState`.
- F-1(b): the future Layer 5 caller passes `TeamModel.identity` and `TeamModel.structural_features` explicitly to Module 5; Layer 3 never needs to import the Layer 2 builder.
- No probability model, Dixon-Coles, Poisson, RNG, event generator, attribution, historical-quality weighting, or runtime state updater is implemented here.
- E-12 is now migrated and CLOSED; see the formal decision and current Layer 2 report. StructuralFeatures has no formation_type field and rejects legacy extras. Layer 3 production formulas/interfaces are unchanged; affected fixtures were explicitly migrated without mapping old labels into quality evidence. Layer 3 still passes 112/112. Snapshot-quality metadata remains independently owned by Layer 1 and is not consumed by Layer 3.

## 2. Public interfaces

Production package: `football_engine/matchup/`.

| Component | Inputs | Output / missing-dependency behavior |
|---|---|---|
| `TacticalProfileGenerator(policy).generate` | `identity`, `structural_features`, `state` | Existing `TacticalProfile`; missing policy raises `SpecificationGapError` |
| `TacticalProfilePolicy` | Keyword-only `identity`, `structural_features`, `state` | All nine final TacticalProfile values, under a future approved policy |
| `DirectionalMatchupHelpers` | Required `press_disruption_m`, `width_mismatch`, `press_transition_opportunity_t` | Frozen per-direction value object; no default or guessed equation |
| `MatchupEngine(parameters, coefficients).evaluate_direction` | Attacker/defender dimensions and tactics; explicit `helpers` | Frozen `DirectionalMatchupBreakdown` diagnostic values |
| `MatchupEngine(...).calculate` | Home/away dimensions and tactics; explicit `home_to_away_helpers`, `away_to_home_helpers` | Existing four-field `MatchupResult` |
| `LambdaCalculator(parameters, coefficients).calculate` | `matchup`, `home`, `away`; keyword-only `is_tournament` | Existing `LambdaPair` with 90-minute-equivalent rates |
| `form_factor_from_recent_performance_index` | Explicit RPI, ParameterSet, coefficients | Exact clamped scalar; does not derive RPI or write runtime state |

`ParameterSet` is explicitly supplied to each numeric engine. `coefficients` defaults to the immutable canonical `Layer3Coefficients`. Standalone scalar functions expose each named equation for isolated tests.

For the direction **A → B**, helper fields mean:

- `press_disruption_m`: **PressDisruption_M(B → A)**.
- `width_mismatch`: **WidthMismatch(A, B)**.
- `press_transition_opportunity_t`: **PressTransitionOpportunity_T(B → A)**.

For the reverse direction, supply a second explicit helper object with reversed participants. The implementation never copies helpers across directions or reuses the M helper as the T helper.

## 3. Implemented canonical equations

Notation: `dims_A` / `dims_B` are existing TeamDimensions; `tactics_A` / `tactics_B` are existing final TacticalProfiles. A/B denote teams here, never snapshot-quality categories.

1. `GK_Factor(B) = 1 - k_gk * (GK_B - GlobalAvgGK) / GlobalAvgGK`.
2. `BaseRelativeStrength(A→B) = (Attack_A / GlobalAvgAttack) / (Defense_B / GlobalAvgDefense) * GK_Factor(B)`.
3. `PossessionShare(A) = sigmoid(k_poss_calc * (A.possession_tendency_final - B.possession_tendency_final + A.build_up_control_score - B.press_final))`.
4. `sigmoid(x) = 1 / (1 + exp(-x))`, evaluated with a numerically stable sign branch.
5. `CreationRealization(A) = 0.6 + 0.4 * PossessionShare(A)`.
6. `CreationFactor(A) = (0.7 + 0.3 * Creation_A / GlobalAvgCreation) * CreationRealization(A)`.
7. `AdjustedBase(A→B) = BaseRelativeStrength(A→B) * CreationFactor(A)`.
8. `I_press(A→B) = 1 - k_p * PressDisruption_M(B→A)`.
9. `I_width(A→B) = 1 + k_w * WidthMismatch(A,B)`.
10. `I_tempo(A→B) = 1 + k_te * A.tempo_final`.
11. `M(A→B) = AdjustedBase(A→B) * I_press(A→B) * I_width(A→B) * I_tempo(A→B)`.
12. `SpaceBehindDefense(B) = B.line_final * (1 - B.defensive_cover_feature)`.
13. `T(A→B) = A.transition_tendency_final * A.attack_pace_factor * SpaceBehindDefense(B) + PressTransitionOpportunity_T(B→A) * A.transition_tendency_final * k_t2`.
14. `lambda_base(A→B) = baseline * M(A→B) + transition_weight * T(A→B)`.
15. `FormFactor = clamp(1 + k_form * RecentPerformanceIndex, form_min, form_max)`.
16. `lambda_final = lambda_base * venue_multiplier * FormFactor`.

### Literal-formula decisions that must not be silently changed

- The current core tactical field is `possession_tendency_final`; that is the state-adjusted value used for the authorization's tactical `possession_tendency` symbol.
- Both possession expressions are evaluated independently. The supplied logit expression is not antisymmetric, so their sum is not guaranteed to equal one. There is **no** undocumented `share_B = 1 - share_A`, renormalization, or extra possession λ multiplier. Any future complementary-share revision requires an explicit mathematical decision.
- The transition term is **not** multiplied by baseline: this is `baseline*M + transition_weight*T`, not `baseline*(M + transition_weight*T)`.
- Existing `ParameterSet.k_t` is intentionally unused because the supplied T formula contains no such multiplier.
- Home advantage and Form are applied only in Module 7, exactly once, after lambda_base.
- Standalone mode returns FormFactor exactly 1.0 and does not read the stored form factor, even if that stored value differs.
- Tournament mode reads the already-computed `TeamRuntimeState.form_factor`; it does not reapply `1+k_form*x` to that factor, infer an RPI, or mutate state.
- `red_card_modifier`, `r_card`, player-count penalties, generic tactical factors, independent randomness factors, and duration scaling are not part of this V1 λ equation.

## 4. Configuration provenance, without Layer 0 changes

Existing `ParameterSet` supplies:

| Parameter | Canonical default |
|---|---:|
| `k_gk` | 0.10 |
| `k_poss_calc` | 1.5 |
| `k_p` | 0.40 |
| `k_w` | 0.20 |
| `k_te` | 0.15 |
| `k_t2` | 0.50 |
| `baseline` | 1.35 |
| `transition_weight` | 0.55 |
| `h_home` | 1.10 |
| `a_away` | 0.95 |
| `k_form` | 0.15 |
| Global attack/creation/defense/GK anchors | Existing defaults: 78.0 each |

The following explicitly supplied constants are absent from the existing ParameterSet. They are exposed in a frozen **Layer-3-local** `Layer3Coefficients`, not hidden in function bodies and not added to Layer 0:

| Configuration field | Canonical default |
|---|---:|
| `creation_realization_offset` | 0.6 |
| `creation_realization_possession_weight` | 0.4 |
| `creation_factor_offset` | 0.7 |
| `creation_factor_creation_weight` | 0.3 |
| `form_min` | 0.85 |
| `form_max` | 1.15 |

There are no additional fitted priors, guessed helper ranges, state deltas, normalization constants, or multipliers. Alternative coefficient values must be explicit configuration, not claimed to reproduce the canonical defaults. The literal 1 in the supplied identity terms and the standalone form factor are part of the authorized equations.

## 5. Exact unresolved specification gaps

| ID | Missing definition | Implemented boundary | Current behavior |
|---|---|---|---|
| L3-G1 | `PressDisruption_M(defender→attacker)`: exact formula, dependency ownership, and domain | Required `DirectionalMatchupHelpers.press_disruption_m` | No production derivation or default |
| L3-G2 | `WidthMismatch(attacker,defender)`: exact signed/unsigned formula and domain | Required `DirectionalMatchupHelpers.width_mismatch` | No width-name/geometry inference or default |
| L3-G3 | `PressTransitionOpportunity_T(defender→attacker)`: independent equation and permitted inputs | Required `DirectionalMatchupHelpers.press_transition_opportunity_t` | Never derived from the M disruption signal |
| L3-G4 | Exact per-field MatchState adjustments for NORMAL/LEADING/LOSING/REACTIVE | `TacticalProfilePolicy` | Generator raises without a supplied policy, including in NORMAL |
| L3-G5 | One-time baseline composition of structural P/U/Ts with identity into final tactical values | Same explicit policy boundary | No invented multiply/mean/blend or overloaded identity field |
| L3-G6 | Definition of RecentPerformanceIndex from historical/tournament results | Explicit scalar argument to the implemented FormFactor equation | No RPI derivation; runtime factor is read for tournaments |

L3-G1/2/3 block automatic Matchup derivation from tactical objects alone. L3-G4/5 block automatic final tactics from identity/structure/state alone. L3-G6 does not block λ when the state owner already supplies a valid form factor. Real Layer 2 outputs can plug into the existing interfaces later; missing helper equations still need separately approved implementations.

### Validation policy (numerical, not invented football math)

- Non-finite numeric inputs are rejected.
- Global anchors and the defender's defense denominator must be strictly positive. A zero defense value is allowed by the core shape but makes the supplied relative-strength equation undefined; Layer 3 raises rather than adding epsilon or capping strength.
- Helper values must be finite; no unsupported `[0,1]`/`[-1,1]` domain is imposed. Negative width mismatch is supported. Resulting negative interaction factors or negative/non-finite M/T/λ fail explicitly, rather than being clipped.
- Tactical/possession values respect the existing `[0,1]` core fields.
- Tournament form must already lie in the approved clamp interval; invalid stored values are rejected, not recomputed or repaired. This check does not apply to a stored value ignored in standalone mode.
- Home/away input positions must agree with the runtime `is_home` flags.

## 6. Anti-double-counting and dependency ownership

| Signal | Implemented route |
|---|---|
| Dimensions attack / defender defense and GK | BaseRelativeStrength → AdjustedBase → M |
| Creation | CreationFactor → AdjustedBase → M |
| Possession tendency / attacker build-up / defender press_final | PossessionShare → CreationRealization → CreationFactor → M only |
| Supplied PressDisruption_M | I_press → M only |
| Supplied WidthMismatch | I_width → M only |
| Attacker tempo | I_tempo → M only |
| Defender line and cover | SpaceBehindDefense → T only |
| Attacker transition tendency / pace | T only |
| Supplied PressTransitionOpportunity_T | Separate T term only |
| Venue / Form | After lambda_base only |
| Snapshot quality / RNG / event outcomes | No Layer 3 formula path |

The canonical M formula explicitly contains both the possession-related opponent press input and a separate disruption helper. This implementation does not redesign those supplied equations. The missing helper definition must specify how its construct differs and what inputs it may consume; no claim is made that an arbitrary caller-supplied helper policy has already been audited for double-counting. Perturbation tests hold helper outputs fixed while verifying built-in routing; static guards independently check allowed field access.

## 7. Architecture-example regression: partial, not fabricated

The authorization supplies these rounded outputs for B→A, but no complete raw example input block: BRS 1.089; possession 0.231; realization 0.692; creation factor 0.671; adjusted base 0.731; I_press 0.856; I_tempo 1.0825; M 0.677; space 0.51; T 0.598; lambda_base 1.243.

They are preserved verbatim as numeric reference values in `tests/fixtures/layer3_architecture_reference.json`, with explicit provenance and `full_regression_reproduced: false`.

Verified links whose inputs were actually supplied:

- `PossessionShare(B) = 0.231`; therefore `CreationRealization(B) = 0.6 + 0.4*0.231 = 0.6924`, approximately 0.692. The value 0.231 is possession share, **not** creation realization.
- `1.089*0.671 = 0.730719`, approximately 0.731.
- `1.35*0.677 + 0.55*0.598 = 1.24285`, approximately 1.243.

Tolerance is half of the 0.001 reporting unit (0.0005), a test rounding tolerance, not a model coefficient.

A full replay is blocked by PressDisruption_M(A→B), WidthMismatch(B,A), PressTransitionOpportunity_T(A→B), and the absent original TeamDimensions/final TacticalProfile values. Starting before final tactics additionally requires the Module 5 policy equations. Unit tests independently demonstrate e.g. I_press 0.856, I_tempo 1.0825, and space 0.51 using labeled synthetic inputs; those are **not** passed off as recovered original inputs. No inverse-fitting of raw inputs or helper outputs was done.

## 8. Testing and delivery

- New Layer 3 tests hand-build TeamDimensions, TeamIdentity, StructuralFeatures, TeamRuntimeState, and final TacticalProfile fixtures. These are test-only fictional numbers.
- Both independent formula tests and a Module 5→6→7 manual-fixture chain are exercised.
- Existing tests and all Layers 0/1/2 source/data schema files are preserved; before/after SHA-256 verification is reported separately.
- Run from the repository root: `python3 run_tests_shim.py --json test-results.json`.
- The runner uses the existing minimal pytest-compatible shim, now bundled for portability. It is **not** the full pytest distribution. The baseline shim's missing `.value` attribute was repaired without changing tests; this was an actual baseline harness defect.
- Test collection failures are counted and failed runs exit nonzero. Nothing is skipped or marked xfail to obtain green.
- See `docs/LAYER3_IMPLEMENTATION_REPORT.md` and `verification/` for the actual measured totals, unchanged-file audit, and known missing-data failures.
