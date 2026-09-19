# FormationEngine V1 — implemented definition of record

The six rules were explicitly approved by the user. Implementation followed a separate, verified E-12 schema/ownership migration. No new football equation was invented.

## Contract

- Exactly 11 distinct PlayerSeason objects and one Formation with 11 unique PositionSlot identifiers.
- Matching player/slot role multisets; exactly one GK on both sides.
- Explicit SlotSide/SlotDepth enums; identifiers and formation names are not parsed.
- PlayerSeason fields are read only for id/role validation, not abilities, tendencies, pace, quality, names, or seasons.
- Output: StructuralFeatures with descriptive formation_name and six numeric features in [0,1]. No formation_type or snapshot-quality dependency. Legacy/unknown output fields are explicitly rejected by the core model.
- No randomness, opponent data, I/O, runtime state, mutation, or λ.
- V3 cb_pairing_quality/fullback_exposure remain uncomputed and inert at their existing defaults.

## Notation

O = non-GK slots; N = 10. B/M/F are the BACK/MID/FRONT subsets of O. n_L/n_C/n_R count outfield sides. D consists of DM-role slots in M.

A pair is connected unless its sides are opposite LEFT/RIGHT. CENTER connects to every side; same-side pairs connect. E(X,Y) counts all connected pairs in X × Y.

K = floor(N²/4) = 25 is the maximum cross-partition pair count, not a calibrated coefficient or a layout-specific edge-density denominator.

## Approved formulas

| Rule | Formula | Output |
|---|---|---|
| W | (n_L + n_R) / N | width_feature |
| H | h0 = 0.5 | line_height_feature |
| C | (back-slot count + midfield-DM count) / N | defensive_cover_feature |
| P | E(M,F) / K | press_structure_feature |
| U | E(B,M) / K | build_up_structure_feature |
| Ts | front-slot count × (N - front-slot count) / K | transition_structure_feature |

H is the disclosed V1 baseline prior, not line height inferred from depth bands. Its only authorized V1 value is named V1_LINE_HEIGHT_BASELINE_PRIOR in the engine module; no unrelated Layer 0 ParameterSet field was added. A new value or tactical-height input requires separate approval.

A DM in BACK counts once, not twice; a DM in FRONT adds no midfield cover. Empty bands produce zero connected pairs. Ts is zero at both 0 and 10 front slots and maximal at 5, as the approved structural pair-count rule requires. No corrective clamp or feature-to-feature dependency was introduced.

## Verified manual-layout example

The standard test geometry has four back, three middle (including one DM), three front, eight wide outfield slots, seven middle/front connected pairs, and eight back/middle connected pairs.

- W = 8/10 = 0.8
- H = 0.5
- C = (4+1)/10 = 0.5
- P = 7/25 = 0.28
- U = 8/25 = 0.32
- Ts = 3×7/25 = 0.84

This is explicitly authored test geometry, not a verified historical reconstruction.

## Tests and remaining Layer 2 limits

39 dedicated tests verify exact rules, zero/max/edge cases, all 66 depth-count partitions under three lateral layouts, normalization, geometry/role dependence, identifier/name irrelevance, player-attribute non-access, determinism, immutability, and input/dependency guards.

Existing geometry tests now compare actual StructuralFeatures rather than placeholder errors. TeamModelBuilder passes Module 1 and reaches the genuine missing Module 2 derivation. TeamDimensionEngine and TeamIdentityEngine remain unimplemented because their approved numerical derivation equations were not supplied. The existing prior-blend functions were not redesigned.
