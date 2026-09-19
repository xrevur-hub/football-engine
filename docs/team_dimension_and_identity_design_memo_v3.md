# Design Memo V3 — Team Dimension Engine and Team Identity Engine

**Status: corrected, self-contained implementation baseline for the specified mathematics. NOT a claim of complete automatic Layer 2 reconstruction or historical calibration.**

This revision applies the user's request to correct V2 and execute the next step. V2 is preserved unchanged as a source. E-12, FormationEngine W/H/C/P/U/Ts, existing historical-prior blends, and approved Layer 3 production formulas are not reopened or modified.

## 0. Executive outcome and implementation boundary

- Implement **Module 2 D1** with the exact numerical role weights proposed in V2.
- Implement the **seven specified pre-prior identity components** with V2's exact weights/mappings, but label their modeling assumptions accurately.
- Do **not** invent a possession proxy or silently use 0.5, a prior value, player creation, press, transition, or geometry as possession.
- Add an explicit, optional-at-construction **PossessionTendencySource dependency**. It supplies the missing pre-prior tendency from separately established, preloaded data. Missing dependency or missing data prevents a complete TeamIdentity; there is no production default source.
- Preserve the public `derive(players, structural_features, historical_prior)` and builder `build(players, formation, historical_prior)` call shapes. The identity engine accepts the new dependency at construction; the existing builder already supports injection of that engine.
- A complete TeamModel can be returned **only with an explicit valid possession source**. This is conditional plumbing around a missing data/model specification, not an implemented possession estimator and not closure of the automatic Layer 2 gap.
- Keep Layer 3 unchanged. Its tactical policy and three helper equations remain explicit dependencies; this memo does not select a new press equation or remove a term from PossessionShare.

## 1. Corrections applied to V2

| V2 issue | V3 correction |
|---|---|
| Claimed to be standalone while referring to unavailable V1 sections for strategies, assumptions, examples, and edge cases | Reproduce the operative definitions, tables, input conditions, limits, and executable boundary here. Do not assume an unseen V1 memo supplies facts. |
| Called `PressDisruption = B.press_final * (1 - A.build_up_control_score)` already locked | Neither the supplied architecture checkpoint nor approved Layer 3 production code defines this helper equation. Remove its attribution as a fact. Treat it only as a hypothetical example, never production math. |
| Described build-up sensitivity as effectively quadratic | An affine factor times a sigmoid-derived factor is not a quadratic polynomial. Exact total sensitivity depends on the still-undefined helper/policy. Separate known partial derivatives from hypothetical total derivatives. |
| Audited build-up but called press single-path SAFE | `B.press_final` also explicitly enters PossessionShare. The verbal exclusive-path table and the actual expression need reconciliation for **both** signals. No unseen helper formula is assumed. |
| Called pace reuse SAFE because outputs feed additive M and T | Additivity does not imply statistical independence or prove absence of double-counting. Classify it as deliberate proposed signal reuse requiring semantic/sensitivity/calibration checks. |
| Said attacking-role pace would not move if defenders became faster | The table gives FB weight 0.20 and CM weight 0.10 in attack pace. Only changes restricted to zero-weight roles, such as CB, leave this component unchanged. |
| Treated `compactness=C` as a proven compactness measurement | It is an explicit **cover-based compactness proxy**. Cover occupancy is not geometric compactness or empirical defensive cohesion. Its downstream safety remains policy-dependent. |
| Treated an unspecified downstream consumer as making every upstream formula mathematically unimplementable | Separate local input-to-output mathematics from end-to-end causal validation. A proxy can be implemented and labeled provisional without inventing its consumer or claiming end-to-end safety. |
| Claimed D1 has formation sensitivity through occupancy | For a fixed list of PlayerSeasons, roles are fixed. D1 is invariant to all valid formation geometry changes. Changing role composition requires a different squad/role assignment; the current engine does not assign new roles. |
| Counted 72 table entries as 72 free calibration parameters | Correct the distinction between displayed constants, fixed zeros, scale-invariant ratios, and fitted parameters (§8). |
| Omitted GK from the tempo toy calculation despite positive GK tempo weight | Replace the unverifiable four-player example with a complete 11-player example, including GK pace (§9). |
| Used `n_DM` ambiguously in C | Preserve FormationEngine's approved **MID-depth DM count only**, not all DMs. No double counting of a BACK-depth DM. |
| Mixed pre-prior and final identity pass-through claims | `compactness=C` applies before prior blending. Existing compactness prior may change the final value. Build-up and attack pace have no fields in the existing IdentityPriors model and remain pass-through after the existing blend. |

The original architecture checkpoint is useful evidence, not a rollback instruction. Its old formation_type/Type A/B/C structural references are superseded by the explicit E-12 decision.

## 2. Contracts, units, and invariants

### Inputs

Exactly 11 distinct, valid PlayerSeason objects and a valid StructuralFeatures object. Exactly one selected player must have role GK. Role values must be actual PlayerRole members. Duplicate/non-string/empty IDs, wrong object types, wrong counts, malformed structures, invalid/nonfinite numerical fields, and out-of-range consumed attributes raise explicit errors. Inputs and structures are never mutated or re-derived.

- Player abilities: `[0,100]`.
- Player tendencies and pace: `[0,1]`.
- TeamDimensions: four distinct values in `[0,100]`.
- TeamIdentity: eight distinct values in `[0,1]`.
- Do not divide already-normalized tendencies by 100 or collapse dimensions to one team-strength score.

Role-count compatibility with Formation is checked by FormationEngine in the builder. Modules 2/3 do not import Formation, infer slot assignment, parse formation names, or inspect opponent/runtime state.

### Structural notation

W/H/C/P/U/Ts mean the already-implemented FormationEngine outputs. C is `(BACK outfield count + MID-role-DM count)/10`. U is the approved connected BACK/MID pair count divided by 25. This memo never recomputes either feature. H remains the previously disclosed 0.5 baseline prior; it is not reused as a possession fallback.

### Determinism and isolation

Read validated inputs, use fixed immutable role-weight tables, return frozen core models. Sort by player ID before numerical aggregation so input ordering does not affect rounding. No RNG, I/O, runtime state, opponent input, venue/form multiplier, λ calculation, snapshot-quality weight, or calibration optimization belongs in these engines.

Current PlayerSeason defaults are not evidence of measured historical attributes. This delivery adds no default player observations; historical input completeness/provenance remains a separate data-layer responsibility.

## 3. Candidate models and selected scope

### TeamDimensions

- **D1 — weighted arithmetic mean:** interpretable, convex and bounded; no structural bonus. Selected for this delivery.
- **D2 — mean plus structural offsets:** introduces new beta coefficients and possible repeated tactical effects. Not implemented.
- **D3 — weighted power mean:** introduces power/identifiability and zero-value questions. Not implemented.

Claims that any candidate fits real historical teams better are untested until data validation/calibration is performed.

### TeamIdentity strategies

- **I1:** direct role-weighted aggregation of an available player field.
- **I2:** a new composition of player and structural inputs with explicit mix coefficients.
- **I3:** nonlinear transformation such as a sigmoid, introducing scale/intercept choices.
- **Direct structural proxy:** use an existing structural output once, with its limitations disclosed.

This delivery uses I1 for five components, direct structural proxies for two, and an explicit unresolved-source boundary for possession. It adds no I2 mix coefficients or I3 transformations.

## 4. Module 2 — D1 mathematical definition

For dimension d in {Attack, Creation, Defense}:

```text
D_d = sum_i(w_d(role_i) * ability_d(i)) / sum_i(w_d(role_i))
Goalkeeping = gk_ability of the unique selected GK
```

The sum is over all 11 players; zero-weight contributions are excluded numerically. No bench average, global-anchor normalization, opponent factor, or tactical multiplier is applied. The caller applies the existing dimension prior adjustment afterward.

**D1 deliberately does not use StructuralFeatures numerically.** The object remains part of the accepted/validated interface for compatibility. The same valid squad produces the same four dimensions under different valid geometry. This is an explicit V1 simplification of the original architectural ambition that formation context may adjust dimensions—not proof that such context adjustment has been implemented.

## 5. Module 3 — pre-prior definition and possession boundary

For a weighted component f with available player attribute x:

```text
WM_f(x) = sum_i(w_f(role_i) * x_i) / sum_i(w_f(role_i))

press_tendency      = WM_PRESS(player.press_tendency)
transition_tendency = WM_TRANS(player.transition_tendency)
tempo               = WM_TEMPO(player.pace)
risk_tolerance      = WM_RISK(player.shot_tendency)
attack_pace_factor  = WM_ATT_PACE(player.pace)
compactness         = C
build_up_control_score = U
possession_tendency = explicit_possession_source(sorted_player_season_ids)
```

### Interpretation, not empirical certification

- `tempo` is a **pace-based tempo proxy**, not a direct measurement of ball-circulation speed or coaching intent.
- `risk_tolerance` is a **shooting-propensity proxy**. State detection and state adjustment are separate unresolved consumers; this memo does not design them.
- `compactness` is a **cover-based proxy**, not a new claim that all notions of compactness equal C.
- `build_up_control_score=U` is a **structural-connectivity proxy**, not a player-skill estimate. Its composition with raw U in future Module 5 must be specified once; do not add the same U a second time by default.
- `attack_pace_factor` uses attack-contribution weights, including nonzero FB and CM weights—not strictly forwards-only weights.
- No ability field is repurposed as possession, tempo, risk, compactness, or build-up in this specification. No reversal such as `1-press` or `1-transition` is invented.

### The missing possession model is NOT silently closed

`PossessionTendencySource` is a callable protocol:

```python
source(*, player_season_ids: tuple[str, ...]) -> float
```

The engine is configured explicitly:

```python
identity_engine = TeamIdentityEngine(possession_source=my_preloaded_source)
builder = TeamModelBuilder(identity_engine=identity_engine)
model = builder.build(players, formation, historical_prior)
```

No implementation of `my_preloaded_source` is provided as a production default. This is dependency injection, not a new possession equation or a schema migration.

Source requirements:

1. Return a finite real `[0,1]` **pre-prior intrinsic possession-tendency index** for exactly that roster. It is not the matchup's PossessionShare, predicted possession percentage, or a post-match observation.
2. Be deterministic, read-only, preloaded, and independent of current opponent, match state, runtime randomness, and target-match outcomes. Avoid look-ahead/data leakage.
3. Use separately established possession data or a separately approved estimator. Do not smuggle the rejected ability/press/geometry proxies or the same HistoricalPrior back in through a callback.
4. Resolve the requested player-season IDs exactly. Do not use a constant fallback for an unrecognized roster. Any missing-data/source error propagates; nothing substitutes 0.5 or a curated prior.
5. The engine passes only a sorted immutable tuple of IDs, not abilities, structures, or HistoricalPrior. This limits its own data flow; it does not certify arbitrary caller code as causally valid or pure.

No source: raise `TeamIdentitySpecificationGapError`, a NotImplementedError subtype. Invalid source result: raise `TeamIdentityEngineError`. The default builder therefore still cannot automatically create a complete TeamModel without this separately supplied dependency.

**Future decision still required:** choose the actual possession-data schema/estimator and collect its values. A dedicated player attribute, a curated team-level input, or another defensible estimator requires an explicit subsequent decision. No Layer 0/1 field migration is performed here.

### Historical-prior blending — unchanged

After a complete pre-prior TeamIdentity exists, call the existing blend exactly once:

```text
final_f = clamp(alpha * derived_f + (1-alpha) * prior_f, 0, 1)
```

If no prior exists for a field, keep derived_f. A prior is not a replacement for a missing pre-prior possession value, even when alpha is zero. Current IdentityPriors covers six fields; build-up and attack pace have no prior slots and pass through. Compactness may differ from C after blending.

The builder applies the existing dimension adjustment separately, without redesigning it:

```text
final_dimension = clamp(derived_dimension + (1-alpha)*100*delta, 0, 100)
```

For prior=None or alpha=1, dimensions pass through. Dimension delta is on the existing normalized adjustment scale. This statement records existing code, not a new formula in this revision.

## 6. Fixed role-weight priors

Values below are **uncalibrated modeling priors supplied in V2**, retained numerically. They are new Module 2/3 tables, not aliases of Section R scorer/assist weights. Store them as immutable Layer 2 configuration, separate from Layer 0 ParameterSet and Layer 3 coefficients.

### 6.1 Dimensions

| Role | Attack | Creation | Defense | GK lookup indicator |
|---|---:|---:|---:|---:|
| GK | 0.00 | 0.00 | 0.00 | 1 |
| CB | 0.05 | 0.10 | 1.00 | 0 |
| FB | 0.15 | 0.35 | 0.65 | 0 |
| DM | 0.10 | 0.45 | 0.55 | 0 |
| CM | 0.25 | 0.70 | 0.35 | 0 |
| WM | 0.65 | 0.55 | 0.15 | 0 |
| AM | 0.55 | 0.85 | 0.10 | 0 |
| FW | 1.00 | 0.30 | 0.05 | 0 |

The GK column describes a fixed unique-player lookup, not a fourth tunable weighted mean.

### 6.2 Identity

| Role | PRESS | TRANS | TEMPO | RISK | ATT_PACE |
|---|---:|---:|---:|---:|---:|
| GK | 0.00 | 0.00 | 0.05 | 0.00 | 0.00 |
| CB | 0.30 | 0.10 | 0.20 | 0.05 | 0.00 |
| FB | 0.50 | 0.40 | 0.30 | 0.15 | 0.20 |
| DM | 0.60 | 0.20 | 0.30 | 0.10 | 0.00 |
| CM | 0.55 | 0.30 | 0.35 | 0.25 | 0.10 |
| WM | 0.45 | 0.60 | 0.30 | 0.45 | 0.60 |
| AM | 0.35 | 0.45 | 0.35 | 0.55 | 0.50 |
| FW | 0.25 | 0.55 | 0.25 | 0.75 | 1.00 |

These weights do not establish causal safety merely by being numerically different.

## 7. Corrected dependency and sensitivity audit

### 7.1 Evidence levels

Distinguish (a) an equation actually present in approved code, (b) a mapping introduced by this memo, (c) a verbal intended dependency, and (d) a helper/policy with no specified equation. Reachability alone cannot prove causality, independence, or empirical double-counting.

The supplied architecture checkpoint establishes PossessionShare in lines 333–339 and I_press in lines 382–402. It does **not** define the arithmetic inside PressDisruption. Approved production code receives three independent directional helper values and does not derive them from tactical fields.

The checkpoint's exclusive-path table says build-up and press should use the press path, while its PossessionShare expression explicitly reads build-up and opponent press. That is a real **specification-ownership tension**. It is not proof that today's implementation contains the memo's assumed helper formula. Record it for the later Layer 3 policy/helper decision; do not repair it by deleting an approved input now.

### 7.2 Confirmed current expression

For one direction, write u=A.build_up_control_score, b=B.press_final, a=A.possession_tendency_final-B.possession_tendency_final. With all other values—including the supplied press helper—held fixed:

```text
s(u) = sigmoid(1.5*(a+u-b))
M(u) = K * (0.6+0.4*s(u))
```

K includes the fixed base/creation-strength and interaction factors. For K>0:

```text
partial log(M)/partial u = 0.6*s*(1-s)/(0.6+0.4*s)
partial log(M)/partial b = -0.6*s*(1-s)/(0.6+0.4*s)
```

This is a **partial derivative with helper values and other tactics fixed**, not the total derivative through an unspecified future tactical policy. If M=0, the log derivative is undefined; do not apply the expression there.

Only hypothetically, if a later approved helper were b*(1-u), an additional affine factor `(1-0.4*b*(1-u))` would appear. A sigmoid-derived factor times an affine factor is nonlinear, **not a quadratic polynomial**. This hypothetical is not implemented or selected.

### 7.3 Field-level status

| Signal | Local mapping in this revision | End-to-end status |
|---|---|---|
| ability fields | Each to its corresponding dimension; GK to selected GK lookup | Local ownership explicit; no ability-to-identity proxy |
| player press | PRESS weighted mean | Tactical composition and helper definition pending; opponent press also explicitly enters PossessionShare |
| player transition | TRANS weighted mean | Transition pathway intended; future Ts composition must be defined once |
| player pace | TEMPO and ATT_PACE weighted means | Deliberate proposed shared input with distinct weights/consumers; **not proven independent or globally SAFE** |
| shot tendency | RISK weighted mean | Proxy with unspecified state consumer; no state equation invented |
| C | Pre-prior compactness proxy; raw C separately reaches future tactics | May duplicate a signal if a future policy recombines both; require an explicit ownership rule |
| U | Build-up proxy; raw U also available separately to Module 5 | Composition/press-helper ownership pending; do not add U twice |
| possession | Explicit separate source | Automatic estimator/data contract still open; do not confuse tendency with outcome/share |

For fixed roster weights, the local derivative of a weighted field with respect to one participating player's input is `w(role)/sum(w)`. A CB-only pace perturbation moves tempo and leaves attack pace unchanged; an FB pace perturbation moves both. The role-level response is testable without claiming real-roster independence. Actual calibration must later assess covariance and combined λ sensitivity.

No numerical formula for WidthMismatch, PressDisruption_M, PressTransitionOpportunity_T, state detection/adjustment, or P/U/Ts tactical composition is introduced here. Formation Structure, Snapshot Quality and Historical Tier remain separate.

## 8. Parameter accounting and calibration limits

V2 displays 32 dimension-table entries (including the redundant GK column) plus 40 identity-table entries: 72 numbers. These are not 72 identifiable free parameters.

With the proposed zero pattern and unique-GK lookup fixed:

- Three dimension means have 7 positive weights each: 21 positive entries, 3 common-scale invariances → **18 relative degrees of freedom**.
- Five identity means have 7, 7, 8, 7 and 5 positive weights: 34 positive entries, 5 scale invariances → **29 relative degrees of freedom**.
- The GK indicator is fixed, not fitted.
- Thus there are at most **47 scale-normalized weight ratios**, not 72 independent fitted parameters, if a future calibration process chooses to tune every positive mean weight. Data may identify fewer. Changing zero topology would change this count.
- **This delivery fits zero parameters.** The fixed weights are defaults from the user's memo, not empirical estimates. No optimizer is implemented and no match likelihood claims are made.

Use fixed scales/regularization and held-out historical validation in future calibration; multiplying every weight in one mean by the same positive constant changes no output. Do not optimize an unidentifiable common scale.

## 9. Reproducible 11-player worked example

All values below are synthetic test inputs, not historical claims. IDs are memo_p00 through memo_p10 in row order. Season is synthetic-v3; discipline and impact are explicitly 0.5 and unused. GK ability is 85 for p00 and 0 for everyone else. The GK is CENTER/BACK; outfield geometry is explicit.

| ID suffix | Role | Attack | Creation | Defense | Shot | Press | Transition | Pace | Side / Depth |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 00 | GK | 10 | 30 | 35 | .02 | .10 | .15 | .30 | center/back |
| 01 | CB | 20 | 35 | 84 | .10 | .40 | .20 | .45 | left/back |
| 02 | CB | 25 | 40 | 82 | .12 | .45 | .25 | .50 | right/back |
| 03 | FB | 45 | 65 | 72 | .30 | .65 | .50 | .75 | left/back |
| 04 | FB | 50 | 60 | 70 | .35 | .60 | .55 | .80 | right/back |
| 05 | DM | 35 | 70 | 78 | .20 | .70 | .30 | .55 | center/mid |
| 06 | CM | 60 | 80 | 65 | .45 | .65 | .45 | .65 | left/mid |
| 07 | AM | 75 | 90 | 40 | .60 | .50 | .55 | .70 | right/mid |
| 08 | WM | 82 | 78 | 38 | .70 | .55 | .75 | .90 | left/front |
| 09 | FW | 90 | 68 | 25 | .90 | .40 | .70 | .85 | center/front |
| 10 | FW | 86 | 72 | 30 | .85 | .45 | .80 | .95 | right/front |

The unchanged FormationEngine yields `(W,H,C,P,U,Ts)=(.8,.5,.5,.28,.32,.84)`.

For this example only, a clearly labeled test source provides pre-prior possession tendency **0.62**. This is fixture data, not a production coefficient, neutral fallback, or invented estimator.

| Output | Pre-prior value |
|---|---:|
| Attack | 77.35443037974683 |
| Creation | 74.11111111111111 |
| Defense | 73.93406593406593 |
| Goalkeeping | 85.0 |
| possession_tendency | 0.62 (explicit external fixture value) |
| press_tendency | 0.5660493827160494 |
| transition_tendency | 0.5979452054794521 |
| tempo | 0.7114035087719298 |
| risk_tolerance | 0.6764615384615384 |
| compactness | 0.5 |
| build_up_control_score | 0.32 |
| attack_pace_factor | 0.8513888888888889 |

With alpha=.55, identity priors `(possession=.95, press=.90, transition=.25, tempo=.70, risk=.50, compactness=.75)`, and creation adjustment +.03, existing blend code gives:

```text
Creation_final = 75.46111111111111
possession_final = .7685
press_final_identity = .7163271604938272
transition_final_identity = .4413698630136986
tempo_final_identity = .7062719298245614
risk_final_identity = .5970538461538462
compactness_final_identity = .6125
```

Other dimensions, build-up .32 and attack pace .8513888888888889 pass through. These are final **TeamIdentity** values, not state-adjusted TacticalProfile fields despite the descriptive final labels above.

Exact fraction references and all inputs are in `tests/fixtures/layer2_memo_v3_example.json`, generated independently of production aggregation code. Do not reuse V2's four-player outputs: its full input data is absent and its tempo calculation omitted a nonzero GK contribution.

## 10. Edge cases and numerical rules

1. Wrong count, duplicate IDs, invalid member types/roles, zero or multiple GKs: explicit engine input error.
2. No positive denominator: explicit error naming the field. Do not normalize by 1 or supply a neutral mean. With these tables, GK plus ten CB/DM players can make attack-pace denominator zero, even though the structure contract can represent that squad.
3. Zero abilities/tendencies are legitimate, not missing-value sentinels. All-100 abilities/all-one tendencies return their respective bounds; all-zero contributors return zero.
4. Only positive-weight contributors determine a mean. Changing GK attack/creation/defense cannot change the corresponding team dimensions; changing a non-GK gk_ability cannot change team Goalkeeping.
5. Validate finite, bounded values **before** aggregation. Do not clamp invalid input to make it pass.
6. Use deterministic `math.fsum` aggregation. A positive weighted mean is mathematically in the min/max interval of its contributors. A final projection to that same interval may protect floating-point rounding only; it introduces no tactical bonus or calibrated epsilon.
7. Role weights are finite and nonnegative, immutable, and complete for all eight roles. Fixed zeros are explicit model exclusions, not missing table entries.
8. Structures are accepted and validated; no formation label or legacy type is parsed. Valid W/H/P/Ts/V3 changes do not affect the chosen identity formulas. Only C/U are used numerically, and D1 uses none.
9. Source absence/result errors cannot be hidden by a historical prior. The source is queried once for a valid derivation with immutable, sorted roster IDs; input objects and order are not changed.
10. No partial dict or nullable fake TeamIdentity is passed downstream. Either return a fully validated eight-field model or raise an explicit error.
11. A D1 Defense value of zero is valid at the Layer 2 model boundary, but it cannot be used as the denominator of Layer 3 BaseRelativeStrength. The existing Layer 3 error is preserved; no epsilon or strength floor is invented.

## 11. Verification and delivery requirements

Add tests for exact table values, immutability, independent fraction arithmetic, bounds/convexity, monotonicity, role/GK isolation, squad/geometry distinction, player-order invariance, no mutation, input corruption/nonfinite values, zero denominators, and absence of prohibited imports.

Identity tests must cover the seven defined components, missing/invalid possession sources, no fallback through priors, immutable ID-only source input, distinct rosters using distinct external values, pace-scope differences, C/U-only structural use, and exact-once prior blending.

A real Module 1→2→3 builder test is allowed with the explicit synthetic possession source. If extended to Layer 3, label the tactical policy/helpers as test-only supplied dependencies; do not claim the open policy/helper mathematics has been solved.

Preserve existing unrelated tests and production layers. Update only tests that previously asserted the now-implemented Module 2 stub or expected the builder to stop there. Existing default identity-gap tests remain meaningful. Run the repository suite and the separate Layer 3 regression scope, report failures honestly, and rerun the extracted downloadable archive.

The six existing missing-seed tests must not be skipped or satisfied with synthetic historical data. Passing contract/synthetic tests is not evidence of historical accuracy or a complete automatic end-to-end simulation.

## 12. Remaining decisions after this delivery

- Actual possession-data source/estimator and any required Layer 0/1 schema migration.
- Explicit Module 5 composition/adjustments, including ownership when both identity build-up/compactness and raw U/C are available.
- Layer 3 helper equations and reconciliation of its verbal single-path rules with the retained PossessionShare formula for build-up and press.
- Empirical validation of the pace/shot/cover/connectivity proxies and role-weight priors.
- Real normalized historical data, calibrated parameters, and full simulation validation.

None is closed by dependency injection or by relabeling a prior as a measurement. This revision makes the specified mathematics executable and its remaining assumptions auditable without silently extending Layer 0/1 or changing approved Layer 3 behavior.
