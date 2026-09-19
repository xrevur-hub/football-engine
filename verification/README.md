# Verification checkpoints

## Current delivery — Design Memo V3 / D1 and conditional identity

Current evidence lives in **layer2_memo_v3/**:

- Repository-wide: **280 passed, 6 failed, 286 total**, exit 1.
- New tests, isolated: **57/57**, exit 0 (21 dimensions, 25 identity, 11 pipeline/audit).
- Layer 3-specific health, isolated: **112/112**, exit 0; no production or test edits to Layer 3.
- All six failures are the unchanged missing normalized seed-data tests. No synthetic historical data, skip, or xfail concealed them.
- Actual D1 and seven identity components work. A full identity/model requires a supplied possession source; no automatic estimator or default was invented.
- source_audit.json lists exact source changes and unchanged protected files. implementation.patch, documentation.patch and memo_v2_to_v3.patch separate the work for review.
- numerical_reference_builder.py reproduces the synthetic 11-player reference independently using Fraction arithmetic. Pass an output directory argument to avoid writing into this folder.

## Earlier historical checkpoints

**layer2/** records the prior E-12/Formation delivery (223/229 repository-wide). Root combined_tests/layer3_only/file_audit and architecture/documentation-review records describe the earlier Layer 3 delivery (172/178 repository-wide; 112/112 Layer 3) and documentation-only approvals. Their old unchanged-source and OPEN/missing-spec statements refer to those checkpoints, not today's source tree.

Current original/revised documents and the detailed V3 report are linked from PROJECT_OVERVIEW.md. Source_manifest.sha256 covers every current packaged file except itself. No Git commits are claimed. The local runner is the existing limited pytest-compatible harness, not the full pytest distribution.
