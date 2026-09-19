# Design Memo V2: Team Dimension Engine (Module 2) & Team Identity Engine (Module 3)

**Status:** Revised proposal, incorporating reviewer corrections + a Matchup Engine
audit that surfaced one unresolved architecture-level issue. **Still not V1-locked.**
See §0 for a full changelog against V1, and §10.5 for the one open decision blocking
final lock.

---

## 0. Changelog Against V1

| Field | V1 memo | V2 memo | Reason |
|---|---|---|---|
| `possession_tendency` | `0.5·creation_ability + 0.5·(1−press_tendency)` | **OPEN SPECIFICATION ITEM — no formula proposed** | `creation_ability` already has a locked, single path to M via `TeamDimensions.Creation → CreationFactor`; reusing it here opens a second path. `1−press_tendency` is also a weak proxy — press and possession are not mutually exclusive. |
| `tempo` | `0.5·pace + 0.5·creation_ability` | `WeightedMean(pace)`, team-wide role weights | Same `creation_ability` double-path problem as above. `pace` alone has no competing path into TeamDimensions, so it is single-path-safe. |
| `compactness` | `0.5·C + 0.5·(1−mean_pace)` | `Compactness = C` (direct) | The pace-based term was already flagged in V1 as a weak heuristic kept only for formula "completeness". A weak, unfalsifiable term does not belong in a V1 meant to be simple-to-calibrate. |
| `risk_tolerance` | `0.6·WeightedMean(shot_tendency) + 0.4·(1−C)` | `WeightedMean(shot_tendency)` only | `C` already has one locked downstream path (`SpaceBehindDefense`, `PressDisruption`). Whether `risk_tolerance`'s consumer (the not-yet-specified State Adjustment layer) creates a second path back to the same place cannot be proven safe or unsafe today — see §10.4. Removing `C` here is the conservative choice until State Adjustment is specified. |
| Attribution language | "DIRECTLY IMPLIED" (for `TacticalProfile.defensive_cover_feature` ← `StructuralFeatures.C`) | **"APPROVED PROJECT DECISION"** | This came from a separate architectural decision made during this project's design conversation, not from the originally-quoted locked architecture text. Mislabeling it as "directly implied" blurred the line between the source document and later project decisions. |
| Toy example | 4-player (GK+CB+CM+FW) | Explicitly flagged as **illustrative arithmetic only, not a valid engine input** | Module 2's contract requires exactly 11 PlayerSeasons; a 4-player example must never be read as a validation case. |
| `build_up_control_score` | Treated as settled (`= U`, single path via `PressDisruption`) | **Flagged as an unresolved overlap inside the already-locked Matchup Engine itself** (§10.5) | A causal audit (§10) found `build_up_control_score` feeds BOTH `PressDisruption` and `PossessionShare`, both of which multiply into `M`. This is not a TeamIdentity design choice — it exists in the Matchup Engine formulas as already specified. Flagged, not resolved, per explicit instruction. |
| `pace` (tempo vs attack_pace_factor) | Not audited | Audited (§10.3) — found **structurally safe** (diverges to M vs T via different role-weight scopes), with a calibration-time caveat | New finding from this revision's causal audit. |

---

## 1. Executive Diagnosis

Unchanged from V1: the core risk remains double-counting between TeamIdentity fields
and the already-locked Matchup Engine. What V2 adds is a systematic **attribute-level**
audit (not just a structural-feature-level one) that traces every raw PlayerSeason
attribute through to λ. This audit surfaced two findings of different severity:

1. A genuine, structural double-use of `build_up_control_score` **inside the
   already-locked Matchup Engine formulas** (not something this memo introduced) —
   this is the more serious finding and is left explicitly unresolved (§10.5).
2. A correlated-but-structurally-distinct reuse of `pace` (via `tempo` and
   `attack_pace_factor`) that resolves to SAFE under a causal audit, provided the two
   fields' role-weight scopes remain genuinely different — with a calibration-time
   caveat, not a design-time blocker.

The distinction between these two matters: finding 1 requires an architecture
decision from the project owner (this memo cannot resolve it); finding 2 requires a
calibration-time sanity check, not a redesign.

---

## 2. What Is Truly Locked vs Missing

Unchanged from V1 §2, with one addition to the MISSING list:

### MISSING (additional item found in V2's audit)
- Whether `build_up_control_score`'s dual appearance in `PossessionShare` and
  `PressDisruption` is an intentional dual-manifestation of one latent capability, or
  an unintentional duplicate that should be resolved by removing it from one formula.
  **This is a decision about the Matchup Engine, not about Module 2/3** — it is listed
  here because it directly affects whether `build_up_control_score`'s TeamIdentity
  formula (`= U`, unchanged from V1) can be considered final, or whether it is
  provisional pending that decision.

---

## 3. Candidate TeamDimension Formulations

**Unchanged from V1 §3.** No reviewer objection was raised against D1/D2/D3 or their
comparison table. Reproduced here for completeness of this standalone document.

### Candidate D1 — Pure Role-Weighted Mean (no structural adjustment)

```
Dimension_d(team) = Σ_i [ w_d(role_i) · ability_d(player_i) ] / Σ_i w_d(role_i)
```

StructuralFeatures unused; formation affects TeamDimensions only via role occupancy.

### Candidate D2 — Role-Weighted Mean + Additive Structural Adjustment

```
Dimension_d(team) = clamp( RoleWeightedMean_d + Σ_f β_{d,f}·(StructuralFeature_f − 0.5), 0, 100 )
```

Real double-counting risk unless every β is individually audited against the
Matchup Engine's own StructuralFeatures usage.

### Candidate D3 — Role-Weighted Power-Mean

```
Dimension_d(team) = ( Σ_i [ w_d(role_i)·ability_d(player_i)^p_d ] / Σ_i w_d(role_i) )^(1/p_d)
```

Hardest to calibrate (`p_d` weakly identifiable from outcome data); no double-counting
risk, but only expresses individual-star effects, not formation effects.

### Comparison Table

| Criterion | D1 | D2 | D3 |
|---|---|---|---|
| Interpretability | High | Moderate | Low |
| Calibration difficulty | Low | Moderate | High |
| Double-counting risk | Lowest | Real, manageable with discipline | Low |
| Stability | High | Moderate | Lower |
| Sensitivity to formation | Low (occupancy only) | Direct | Low (occupancy only) |
| Historical-reconstruction fit | Good | Good, if disciplined | Mixed |

---

## 4. Recommended TeamDimension V1

**Unchanged from V1 §4: Candidate D1**, StructuralFeatures excluded entirely from
TeamDimensions, formation sensitivity mediated purely through role occupancy.
Answers Question A.5 as **(B) indirectly through role occupancy**.

---

## 5. Candidate TeamIdentity Formulations

**Unchanged from V1 §5** (I1/I2/I3 strategy definitions and comparison table). What
changes in V2 is *which strategy is assigned to which field* — see §6.

---

## 6. Recommended TeamIdentity V1 (Revised)

The field-by-field assignment changes from V1 as follows, driven directly by the
attribute-level audit in §10:

| Field | V1 assignment | V2 assignment | Why it changed |
|---|---|---|---|
| `possession_tendency` | I1 (creation_ability + press proxy) | **UNRESOLVED — open spec item** | Both proposed proxies had single-path or strength problems (§10.6) |
| `press_tendency` | I1 (press_tendency attribute) | I1, unchanged | Audited SAFE (§10.1) |
| `transition_tendency` | I1 (transition_tendency attribute) | I1, unchanged | Audited SAFE (§10.2) |
| `tempo` | I2-like (pace + creation_ability) | **I1, pace only** | `creation_ability` reuse was a genuine single-path violation |
| `risk_tolerance` | I2 (shot_tendency + C) | **I1, shot_tendency only** | `C`'s downstream safety cannot be proven until State Adjustment is specified (§10.4) |
| `compactness` | I2 (C + pace proxy) | **Direct pass-through, `= C`** | The pace term was an admittedly-weak heuristic; removed rather than defended |
| `build_up_control_score` | Direct pass-through, `= U` | Direct pass-through, `= U`, **but flagged provisional** | The formula itself is unchanged; what changed is the confidence that its sole downstream consumer (`PressDisruption`) is really the *only* consumer — audit found a second one (§10.5) |
| `attack_pace_factor` | I1 (attacking-role pace) | I1, unchanged | Audited SAFE, with a calibration caveat (§10.3) |

I3 (sigmoid) remains not recommended anywhere in V2, for the same reason as V1 §6.

---

## 7. Complete Mathematical Equations (V2 Recommendation)

### 7.1 TeamDimensions (Candidate D1) — unchanged from V1

```
Attack(team)      = Σ_i [ w_A(role_i) · attack_ability_i ]    / Σ_i w_A(role_i)
Creation(team)    = Σ_i [ w_C(role_i) · creation_ability_i ]  / Σ_i w_C(role_i)
Defense(team)     = Σ_i [ w_D(role_i) · defense_ability_i ]   / Σ_i w_D(role_i)
Goalkeeping(team) = gk_ability_of_the_selected_GK
```

### 7.2 TeamIdentity (Revised)

```
possession_tendency          = ⚠ OPEN SPECIFICATION ITEM — no V2 formula proposed.
    See §10.6 for why both V1 candidates were rejected and no safe replacement
    attribute was identified in this pass.

press_tendency                = Σ_i [ w_PRESS(role_i) · press_tendency_i ] / Σ_i w_PRESS(role_i)
    [unchanged from V1]

transition_tendency           = Σ_i [ w_TRANS(role_i) · transition_tendency_i ] / Σ_i w_TRANS(role_i)
    [unchanged from V1; Ts remains excluded, per V1 §10's conservative reading]

tempo                          = Σ_i [ w_TEMPO(role_i) · pace_i ] / Σ_i w_TEMPO(role_i)
    [REVISED — creation_ability term removed; pace only, team-wide role weights]

risk_tolerance                 = Σ_i [ w_RISK(role_i) · shot_tendency_i ] / Σ_i w_RISK(role_i)
    [REVISED — C term removed; shot_tendency only]

compactness                    = C
    [REVISED — direct pass-through, pace-proxy term removed]

build_up_control_score         = U
    [unchanged from V1, but see §10.5 — provisional pending Matchup Engine decision]

attack_pace_factor             = Σ_i [ w_ATT_PACE(role_i) · pace_i ] / Σ_i w_ATT_PACE(role_i)
    [unchanged from V1, restricted to attacking-role weights]
```

All outputs `clamp(·, 0, 1)` where not already guaranteed by construction.

---

## 8. Role-Weight Tables

**Unchanged from V1 §8** (both tables). No reviewer objection was raised against the
role-weight values themselves — only against which *attributes* feed which field, and
how they're combined. Reproduced for completeness:

### 8.1 TeamDimensions role weights

| Role | w_Attack | w_Creation | w_Defense | w_GK |
|---|---|---|---|---|
| GK | 0.00 | 0.00 | 0.00 | 1.00 |
| CB | 0.05 | 0.10 | 1.00 | 0.00 |
| FB | 0.15 | 0.35 | 0.65 | 0.00 |
| DM | 0.10 | 0.45 | 0.55 | 0.00 |
| CM | 0.25 | 0.70 | 0.35 | 0.00 |
| WM | 0.65 | 0.55 | 0.15 | 0.00 |
| AM | 0.55 | 0.85 | 0.10 | 0.00 |
| FW | 1.00 | 0.30 | 0.05 | 0.00 |

(Explicit note, unchanged from V1: this is a new proposal for Module 2, not a reuse of
the existing `ROLE_ATTACK_WEIGHT`/`ROLE_CREATION_WEIGHT` tables from Player
Attribution/Section R, which answer a different question.)

### 8.2 TeamIdentity role weights

| Role | w_PRESS | w_TRANS | w_TEMPO | w_RISK | w_ATT_PACE |
|---|---|---|---|---|---|
| GK | 0.00 | 0.00 | 0.05 | 0.00 | 0.00 |
| CB | 0.30 | 0.10 | 0.20 | 0.05 | 0.00 |
| FB | 0.50 | 0.40 | 0.30 | 0.15 | 0.20 |
| DM | 0.60 | 0.20 | 0.30 | 0.10 | 0.00 |
| CM | 0.55 | 0.30 | 0.35 | 0.25 | 0.10 |
| WM | 0.45 | 0.60 | 0.30 | 0.45 | 0.60 |
| AM | 0.35 | 0.45 | 0.35 | 0.55 | 0.50 |
| FW | 0.25 | 0.55 | 0.25 | 0.75 | 1.00 |

Note: `w_POSS` and `w_COMPACT` columns from V1's table are dropped here —
`possession_tendency` has no formula to weight (§7.2), and `compactness` is now a
direct pass-through of `C` with no role-weighted attribute term at all, so no
role-weight column is needed for it.

---

## 9. Structural-Feature Mapping Table (Revised)

| StructuralFeature | Used in TeamDimensions? | Used in TeamIdentity? | Already used downstream (Matchup/TacticalProfile)? |
|---|---|---|---|
| W (width_feature) | No | No | Feeds `width_final` → `I_width` |
| H (line_height_feature) | No | No | Feeds `line_final` → `SpaceBehindDefense` |
| C (defensive_cover_feature) | No | **Yes — `compactness = C` directly** (risk_tolerance's use of C was REMOVED in V2) | Feeds `defensive_cover_feature` → `SpaceBehindDefense`, `PressDisruption` (APPROVED PROJECT DECISION — see §2/V1's original note) |
| P (press_structure_feature) | No | No | Feeds `press_final` → `PressDisruption` |
| U (build_up_structure_feature) | No | **Yes — `build_up_control_score = U`** (provisional, §10.5) | Feeds `build_up_control_score` → `PressDisruption` **and** `PossessionShare` (audit finding, §10.5) |
| Ts (transition_structure_feature) | No | No (conservative exclusion, unresolved open item) | No confirmed consumer in the quoted locked Matchup formulas |

---

## 10. Attribute-Level Causal Audit (New in V2)

This section is the substantive addition over V1. Methodology: for every raw
PlayerSeason attribute used anywhere in this memo's recommendation, trace every path
from that attribute to λ, and classify the result as **SAFE** (exactly one meaningful
path), **OVERLAP** (the same signal reaches λ via two paths that both feed the same
term), or **OPEN SPEC** (a downstream consumer is not yet specified, so safety cannot
be determined).

### 10.1 `press_tendency`

```
press_tendency(player) → press_tendency(Identity) → press_final → PressDisruption(B→A)
    → I_press(A→B) → M_A→B → λ
```

No other formula in this memo's V2 recommendation reads `press_tendency` (the V1
`possession_tendency` formula that read `1−press_tendency` has been removed).
**Verdict: SAFE.**

### 10.2 `transition_tendency`

```
transition_tendency(player) → transition_tendency(Identity) → transition_tendency_final
    → T_A→B → λ
```

No competing path. **Verdict: SAFE.**

### 10.3 `pace`

```
pace(player) → tempo(Identity, team-wide role weights) → tempo_final
    → I_tempo(A→B) → M_A→B → λ

pace(player) → attack_pace_factor(Identity, attacking-role-only weights) → attack_pace_factor
    → T_A→B → λ
```

These are two separate role-weighted aggregations of the same raw attribute, feeding
two structurally distinct downstream terms (M vs T), which per the locked λ_base
formula (`1.35·M + 0.55·T`) are designed to be additive, independent contributions.
A thought experiment (a team with fast defenders but slow forwards) shows the two
outputs can genuinely diverge — `tempo` would rise, `attack_pace_factor` would not —
confirming this is not a disguised copy of the same number.

**Verdict: SAFE (structurally)**, with an explicit **calibration-time caveat**: if
real historical rosters tend to have correlated pace across all outfield positions
(fast teams tend to be fast everywhere), `tempo` and `attack_pace_factor` may move
together often enough in practice that their combined effect on λ should be checked
during calibration for over-amplification of "pace" as a hidden meta-factor — this is
a data-behavior concern, not a formula defect.

### 10.4 `shot_tendency`

```
shot_tendency(player) → risk_tolerance(Identity) → [State Adjustment — NOT YET SPECIFIED]
    → TacticalProfile fields (which ones, exactly, is unknown)
    → possibly Matchup Engine (unknown which term, if any)
```

`risk_tolerance` does not appear by name in any of the locked M/T/λ formulas quoted for
this task. Its only stated consumer is `detect_state()` (the State Machine), whose
State Adjustment formula — how `risk_tolerance` translates into changes to
`press_final`, `line_final`, etc. — has not been specified in the material available to
this memo. **Verdict: OPEN SPEC.** Cannot be marked SAFE (no proof of a single path)
or OVERLAP (no proof of two). This is exactly why `C` was removed from
`risk_tolerance`'s formula in V2 — adding a second attribute-adjacent input
(`defensive_cover_feature`) to an already-unauditable field would only compound the
uncertainty.

### 10.5 `build_up_control_score` (sourced from `U`, not a player attribute — audited for completeness since it behaves like one causally)

```
U (StructuralFeature) → build_up_control_score(Identity) 
    ┌──────────────────────────────┬──────────────────────────────┐
    ↓                                ↓
PressDisruption(B→A)              PossessionShare(A)
= B.press_final×(1−A.build_up...)  = sigmoid(k×[...+ A.build_up_control_score − B.press_final])
    ↓                                ↓
I_press(A→B)                      CreationRealization(A) → CreationFactor(A)
    ↓                                ↓
    └──────────────► M_A→B ◄────────┘
                        ↓
                        λ
```

Both paths terminate in `M_A→B`, multiplying into the same term. This is a genuine
structural duplicate-use, found **inside the already-locked Matchup Engine formulas**,
not introduced by this memo. Two interpretations were considered:

- **Interpretation A (intentional):** build-up control is one latent capability with
  two correlated behavioral manifestations (possession retention, press resistance) —
  defensible football reasoning, but it makes M's sensitivity to
  `build_up_control_score` effectively quadratic rather than linear (both `CreationFactor`
  and `I_press` rise together when `build_up_control_score` rises, and both multiply
  into M), which risks a single TeamIdentity field having disproportionate,
  hard-to-calibrate leverage over λ.
- **Interpretation B (unintentional):** `PossessionShare` should not have read
  `build_up_control_score` at all; it should rely on `possession_tendency` alone
  (which is already one of its inputs).

**This memo does not choose between A and B** — per explicit instruction, both are
recorded as an **OPEN ARCHITECTURE DECISION**, to be resolved by the project owner
(most defensibly, by testing both variants' λ-sensitivity during calibration rather
than by a priori reasoning alone). The `build_up_control_score = U` formula itself is
left unchanged pending that decision, but is marked **provisional**.

### 10.6 `possession_tendency` — why no V2 formula is proposed

Both V1 candidate proxies failed the audit:
- `creation_ability`: already SAFE-classified as single-path in §10 of V1 (via
  `TeamDimensions.Creation`) — reusing it here would create the exact kind of second
  path this whole audit exists to catch.
- `1 − press_tendency`: not a double-counting problem (press_tendency's one path is
  already accounted for), but a **weak proxy** problem — press and possession are
  empirically and theoretically not mutually exclusive, so this term would encode a
  false constraint into the model (a high-press, high-possession team, which
  genuinely exists in football, would be mismodeled as having suppressed
  possession_tendency).

No other PlayerSeason attribute in the provided list (`attack_ability`,
`defense_ability`, `gk_ability`, `transition_tendency`, `shot_tendency`,
`discipline_score`, `impact_score`) has an obvious, single-path-safe, theoretically
sound relationship to "tendency to retain possession". **Verdict: genuine
specification gap.** Closing it likely requires either (a) a new PlayerSeason
attribute not in the current schema (e.g. a dedicated `possession_tendency` field,
mirroring how `press_tendency` and `transition_tendency` already exist as direct
attributes), or (b) accepting a StructuralFeature-based proxy (none of W/H/C/P/Ts are
obviously safe either — U is already flagged provisional in §10.5, and using it here
would add a *third* path for U). This memo recommends (a) as the more defensible fix,
but flags it explicitly as a recommendation requiring schema change, not a
same-scope fix.

### Summary Table

| Raw Attribute | Derived Field(s) | Downstream Path(s) | Overlap? | Verdict |
|---|---|---|---|---|
| `press_tendency` | `press_tendency` | M via `PressDisruption`→`I_press` | No | **SAFE** |
| `transition_tendency` | `transition_tendency` | T directly | No | **SAFE** |
| `pace` | `tempo`, `attack_pace_factor` | M via `I_tempo`; T via `T_A→B` | Structural, not duplicate | **SAFE** (calibration caveat) |
| `shot_tendency` | `risk_tolerance` | State Machine (unspecified) | Unknown | **OPEN SPEC** |
| `creation_ability` | `Creation` (TeamDimensions only) | M via `CreationFactor` | No (if excluded from Identity) | **SAFE** |
| — (`U`, not a player attribute) | `build_up_control_score` | M via `PressDisruption` AND `PossessionShare`→`CreationRealization` | **Yes** | **OVERLAP — in the locked Matchup Engine itself, unresolved (§10.5)** |
| — (no attribute found) | `possession_tendency` | N/A | N/A | **OPEN SPEC — no formula proposed (§10.6)** |

---

## 11. Parameter Count and Calibration Burden

Revised from V1: removing the `f_poss` mix coefficient, `f_tempo` mix coefficient, and
`risk_tolerance`/`compactness` blend weights (all of which were the exact terms
removed in this revision) reduces the free-parameter count:

| Component | V1 count | V2 count |
|---|---|---|
| TeamDimensions role weights (4×8) | 32 | 32 (unchanged) |
| TeamIdentity role weights | 56 (7 fields × 8 roles) | 40 (5 fields × 8 roles — `possession_tendency` has no formula, `compactness` has no role-weighted term) |
| Blend/mix coefficients | 4 | 0 |
| **Total** | ~92 | **~72** |

V2 is simpler by construction, which is a direct benefit of removing the
double-counting-risk terms rather than defending them — fewer parameters to
calibrate, and each remaining one has a cleaner, single-path justification.

---

## 12. Numerical Toy Example

**Unchanged illustrative purpose from V1, explicitly re-flagged per reviewer
instruction:**

> ⚠️ **This example uses 4 players (GK, CB, CM, FW) for arithmetic clarity only. It
> is NOT a valid Module 2/3 engine input** — the locked contract requires exactly 11
> PlayerSeasons. Do not use this example as, or in place of, an engine validation
> test. A full 11-player worked example should be constructed separately once the
> open items in this memo (§10.4, §10.5, §10.6) are resolved.

Using the same 4 toy players as V1 §12, with `C = 0.60`, `U = 0.55`:

**TeamDimensions (unchanged from V1 — this part of the formula did not change):**
```
Attack   ≈ 80.6
Creation ≈ 64.5
Defense  ≈ 72.5
Goalkeeping = 80
```

**TeamIdentity (recomputed under V2's revised formulas):**
```
press_tendency = (same as V1) ≈ 0.489

tempo = weighted_mean(pace) over {CB:0.40, CM:0.60, FW:0.85} with w_TEMPO{CB:0.20, CM:0.35, FW:0.25}
      = (0.20×0.40 + 0.35×0.60 + 0.25×0.85) / (0.20+0.35+0.25)
      = (0.08+0.21+0.2125)/0.80 ≈ 0.629
      [V1's value mixed in creation_ability and would have differed]

risk_tolerance = weighted_mean(shot_tendency) over {CB:0.10, CM:0.45, FW:0.85} with w_RISK{CB:0.05, CM:0.25, FW:0.75}
               = (0.05×0.10 + 0.25×0.45 + 0.75×0.85)/(0.05+0.25+0.75)
               = (0.005+0.1125+0.6375)/1.05 ≈ 0.719
               [V1's value was ≈0.591, pulled down by the now-removed (1−C) term]

compactness = C = 0.60   [direct; V1's value was 0.60×0.5 + pace-term×0.5]

build_up_control_score = U = 0.55   [unchanged]

possession_tendency = ⚠ not computed — no V2 formula exists
```

---

## 13. Edge Cases

**Unchanged from V1 §13** for all TeamDimensions-related cases (D1's formula did not
change). For TeamIdentity, the removal of blended terms simplifies edge-case behavior:
`compactness` under a 5-at-the-back formation now moves in lockstep with `C`'s own
locked formula (`C = (n_B + n_DM)/N`) with no secondary pace-based damping or
amplification — a more predictable, easier-to-explain edge-case profile than V1's
blended version.

---

## 14. Failure Modes

Retained from V1 where still applicable (role-weight table drift, `Ts` ambiguity,
`Goalkeeping`'s single-player shortcut, D1's inability to capture pure system effects
beyond individual quality). V1 failure mode #3 (the weak pace-based `compactness`
proxy) is **resolved by removal**, not retained as a live risk. Two new failure modes
from this revision:

5. **`possession_tendency` remaining unspecified blocks anything downstream that
   assumes it exists.** `PossessionShare`, `CreationRealization`, and therefore
   `CreationFactor` and `M` all read `possession_tendency` in the already-locked
   formulas. Until §10.6 is resolved, TeamIdentity cannot actually be implemented
   end-to-end — this is the single largest remaining blocker in this memo, larger
   than the `build_up_control_score` question, because that one at least has a
   working (if provisional) formula; this one has none.

6. **Resolving `build_up_control_score` (§10.5) by removing it from `PossessionShare`
   changes `PossessionShare`'s own calibrated behavior**, since that formula is
   already locked and presumably was reasoned about (even if not yet calibrated) with
   both terms present. Any resolution here should be treated as touching the Matchup
   Engine's specification, not merely Module 2/3's — the project owner should decide
   this with that scope in mind, not as a "just fix Module 3" change.

---

## 15. What Must NOT Be Implemented Yet

Retained from V1 (D2's β-coefficients, I3/sigmoid formulas, gradient-based calibration
of the full parameter set, multi-GK/red-card interaction). V2 adds:

- **`possession_tendency` must not be implemented with a placeholder proxy** just to
  unblock coding — per this memo's own audit, no safe candidate was found; shipping a
  weak or double-counting placeholder to "make progress" would reintroduce exactly the
  problem this revision exists to remove.
- **Neither Interpretation A nor B for `build_up_control_score` (§10.5) should be
  implemented until the project owner explicitly picks one** — implementing either
  silently would make a real architecture decision by default rather than by choice.

---

## 16. Final Recommendation

**TeamDimensions:** Unchanged — Candidate D1, role-weighted linear mean,
StructuralFeatures excluded, formation sensitivity via occupancy only.

**TeamIdentity:** `press_tendency`, `transition_tendency`, `tempo`,
`attack_pace_factor` are audited SAFE and ready to lock as specified in §7.2.
`compactness` and `build_up_control_score` are simple, direct pass-throughs
(`= C`, `= U` respectively) — `compactness` is safe to lock; `build_up_control_score`
is usable as-is but **provisional** pending §10.5. `risk_tolerance` has a working
formula but is **OPEN SPEC**, not lockable, until State Adjustment is specified
(§10.4). `possession_tendency` has **no formula** and is the single largest blocker
(§10.6, failure mode 5).

**Two items require an explicit decision from the project owner before this memo can
be considered V1-locked:**

1. **§10.5** — is `build_up_control_score`'s dual role in `PossessionShare` and
   `PressDisruption` intentional (keep both, accept the quadratic-sensitivity
   tradeoff) or unintentional (remove it from `PossessionShare`, rely on
   `possession_tendency` alone there)?
2. **§10.6** — how should `possession_tendency` be derived, given that its two most
   obvious candidate proxies both fail the audit? (Proposed direction: add a
   dedicated `possession_tendency` PlayerSeason attribute, mirroring the existing
   `press_tendency`/`transition_tendency` fields — but this is a schema change, not a
   same-scope formula fix, and needs explicit sign-off.)

```
PlayerSeason
    ↓
Formation / Structure  (W, H, C, P, U, Ts — geometry only, locked V1 formulas)
    ↓
TeamDimensions          (D1: role-weighted mean, occupancy-only — READY)
    ↓
Pre-Prior TeamIdentity   (press/transition/tempo/attack_pace — READY
                          compactness = C — READY
                          build_up_control_score = U — PROVISIONAL (§10.5)
                          risk_tolerance — OPEN SPEC (§10.4)
                          possession_tendency — UNSPECIFIED (§10.6, BLOCKER)
    ↓
HistoricalPrior          (locked blend — unaffected by this memo)
    ↓
Final TeamIdentity
    ↓
TacticalProfile           (+ State Adjustment — not designed here, blocks §10.4)
    ↓
Matchup                   (locked, except §10.5's open question)
    ↓
M + T                     (locked)
    ↓
λ                         (locked)
```
