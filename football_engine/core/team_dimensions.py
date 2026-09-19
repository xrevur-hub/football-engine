"""
StructuralFeatures (Module 1) and TeamDimensions (Module 2).

Architecture reference: Section 4, Section 5, Section O.2.

Both are IMMUTABLE / non-runtime per their Section O.2 contracts, but note
the important caveat from Section 5:

    "در معماری فعلی، همان TeamSeason می‌تواند بسته به formation انتخابی،
    Team Dimensions متفاوتی پیدا کند."

i.e. "immutable" here means immutable *for the duration of one match*
once formation is fixed (formation does not change mid-match in V1,
per N.4) — not immutable across different formation choices.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StructuralFeatures(BaseModel):
    """
    Module 1 output — Formation Engine.

    V1's six active features are geometry/role-occupancy signals. E-12
    explicitly removes the legacy formation_type field: historical snapshot
    quality is Layer 1 metadata, never a structural classifier or input here.
    Unknown fields are rejected so old payloads cannot silently masquerade as
    migrated data. The two inactive V3 fields retain their existing contract.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    formation_name: str = Field(..., description='e.g. "4-3-3"')

    width_feature: float = Field(0.5, ge=0, le=1)
    line_height_feature: float = Field(0.5, ge=0, le=1)
    defensive_cover_feature: float = Field(0.5, ge=0, le=1)
    press_structure_feature: float = Field(0.5, ge=0, le=1)
    build_up_structure_feature: float = Field(0.5, ge=0, le=1)
    transition_structure_feature: float = Field(0.5, ge=0, le=1)

    # V3-scoped fields (Section N.8) — present for schema stability, unused
    # in V1/V2 calculation paths.
    cb_pairing_quality: float = Field(0.5, ge=0, le=1)
    fullback_exposure: float = Field(0.5, ge=0, le=1)


class TeamDimensions(BaseModel):
    """
    Module 2 output — Team Dimension Engine.

    Section 4 explicit principle:
        "Team strength نباید به یک score عمومی 0-100 تبدیل شود که مستقیم
        λ را تعیین کند." — these four dimensions feed the Matchup Engine
        separately; they are never collapsed into one scalar.
    """

    model_config = ConfigDict(frozen=True)

    attack: float = Field(..., ge=0, le=100)
    creation: float = Field(..., ge=0, le=100)
    defense: float = Field(..., ge=0, le=100)
    goalkeeping: float = Field(..., ge=0, le=100)
