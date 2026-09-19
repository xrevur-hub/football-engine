"""Historical snapshot-quality metadata — Layer 1 ownership (E-12 Step A).

Full / Partial / Minimal Snapshot is not formation structure or HistoricalTier.
These weights are the user-supplied canonical calibration metadata, not runtime
strength/identity/lambda modifiers. This module does not classify records,
convert legacy formation_type values, or assign a quality default.

The exact historical record granularity and completeness predicates have not
been supplied. Do not add a guessed quality field to player/team records or
infer quality from fixture labels, confidence, alpha, or HistoricalTier.
"""

from enum import Enum
from types import MappingProxyType
from typing import Mapping


class HistoricalSnapshotQuality(str, Enum):
    TYPE_A = "TYPE_A"  # Full Snapshot
    TYPE_B = "TYPE_B"  # Partial Snapshot
    TYPE_C = "TYPE_C"  # Minimal Snapshot


# Read-only canonical metadata for future calibration consumers, never λ.
SNAPSHOT_QUALITY_CALIBRATION_WEIGHTS: Mapping[HistoricalSnapshotQuality, float] = MappingProxyType({
    HistoricalSnapshotQuality.TYPE_A: 1.0,
    HistoricalSnapshotQuality.TYPE_B: 0.5,
    HistoricalSnapshotQuality.TYPE_C: 0.2,
})
