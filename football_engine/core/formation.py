"""
Formation — the template/input side of the Formation Engine (Module 1).

Architecture reference: Section 5; approved E-12 semantic correction.
Formation is an explicit Position Pool, not merely a name such as 4-3-3.
Context rules produce StructuralFeatures. Historical snapshot-quality classes
are not formation classes and are owned separately by Layer 1.

This module models the *template* (Position Pool + name) that is fed into
the Formation Engine along with 11 selected PlayerSeasons; the Formation
Engine's *output* is StructuralFeatures (team_dimensions.py). Keeping
these separate mirrors the Section O.2 Module 1 contract:
    INPUT:  List[PlayerSeason] (11 نفر) + FormationTemplate
    OUTPUT: StructuralFeatures
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from football_engine.core.enums import PlayerRole


class SlotSide(str, Enum):
    """
    Lateral placement of a PositionSlot within the Position Pool.

    Added as an ADDITIVE Layer 0/core contract refinement (see
    conversation record — "Option 3" decision on 2026-09-08): side is an
    explicit structural property of PositionSlot, never derived by
    parsing slot_id.
    """

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class SlotDepth(str, Enum):
    """
    Vertical (depth) placement of a PositionSlot within the Position Pool.

    See SlotSide docstring for the same "Option 3" contract-refinement
    rationale: depth is explicit structural metadata, never derived by
    parsing slot_id.
    """

    BACK = "back"
    MID = "mid"
    FRONT = "front"


class PositionSlot(BaseModel):
    """
    One slot in a formation's Position Pool (Section 5).

    slot_id is an identifier only (e.g. "LCB", "RW") — it must never be
    parsed for semantic meaning. side/depth are the explicit structural
    geometry fields that Formation Engine (and future context-rule
    derivations, e.g. Double Pivot / Back Three detection) must consume
    directly. This separation is an additive Layer 0/core contract
    refinement, not a derived football formula (no math added here).
    """

    model_config = ConfigDict(frozen=True)

    slot_id: str = Field(..., description='e.g. "LCB", "RW", "DM" — identifier only, never parsed for meaning')
    role: PlayerRole
    side: SlotSide = Field(..., description="Explicit lateral placement: LEFT / CENTER / RIGHT")
    depth: SlotDepth = Field(..., description="Explicit depth placement: BACK / MID / FRONT")


class Formation(BaseModel):
    """
    A named formation template: a Position Pool that PlayerSeasons are
    assigned into. This is DB/catalog data (like TeamSeason), not a
    per-match computed object.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description='e.g. "4-3-3"')
    position_pool: list[PositionSlot] = Field(..., min_length=11, max_length=11)
