"""
HistoricalPrior and TeamSeason — Sections 29-34.

TeamSeason is the top-level, DB-persisted entity for a historical team in
a given season (e.g. "barcelona_2010_11"). It is deliberately *not* the
same object as the per-match runtime state (TeamRuntimeState, Module 4) —
TeamSeason is catalog data; TeamRuntimeState is what a match orchestration
builds from it plus a chosen Formation.

Architecture reference: Section 30 (Hybrid Team Model + clamp formula),
Section 31 (Historical Tiering), Section 33 (TeamSeason Entity schema),
Section 34 (Runtime Pipeline).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from football_engine.core.enums import HistoricalTier
from football_engine.core.team_dimensions import TeamDimensions
from football_engine.core.team_identity import TeamIdentity


class IdentityPriors(BaseModel):
    """
    Historical prior values for TeamIdentity fields (Section 33 example:
    Barcelona 2010/11 possession_tendency=0.95, etc.).

    All fields optional: "برای ویژگی‌هایی که historical prior ندارند،
    derived به‌تنهایی استفاده می‌شود" (Section 30).
    """

    model_config = ConfigDict(frozen=True)

    possession_tendency: float | None = Field(None, ge=0, le=1)
    press_tendency: float | None = Field(None, ge=0, le=1)
    transition_tendency: float | None = Field(None, ge=0, le=1)
    tempo: float | None = Field(None, ge=0, le=1)
    risk_tolerance: float | None = Field(None, ge=0, le=1)
    compactness: float | None = Field(None, ge=0, le=1)


class DimensionAdjustment(BaseModel):
    """
    Historical prior adjustment applied to derived TeamDimensions
    (Section 33 example: `dimension_adjustment: { creation: +0.03 }`).

    Values are additive deltas applied post-derivation, pre-clamp.
    """

    model_config = ConfigDict(frozen=True)

    attack: float = 0.0
    creation: float = 0.0
    defense: float = 0.0
    goalkeeping: float = 0.0


class HistoricalPrior(BaseModel):
    """
    Section 30/31/33 — Historical Team Hybrid Model prior.

    Blend formula (Section 30):
        final = clamp(alpha * derived + (1 - alpha) * historical_prior, 0, 1)

    `alpha` is the derived-vs-prior blend weight:
        Tier 1 (iconic):   alpha ~ 0.5-0.6
        Tier 2 (notable):  alpha ~ 0.75-0.85
        Tier 3 (generic):  alpha = 1.0 (fully derived, no prior needed)
    """

    model_config = ConfigDict(frozen=True)

    tier: HistoricalTier
    alpha: float = Field(..., ge=0, le=1)
    identity_priors: IdentityPriors = Field(default_factory=IdentityPriors)
    dimension_adjustment: DimensionAdjustment = Field(default_factory=DimensionAdjustment)

    @model_validator(mode="after")
    def _tier3_has_no_prior_content(self) -> "HistoricalPrior":
        """
        Section 31: Tier 3 teams have alpha=1.0 (fully derived). We don't
        hard-fail on a Tier 3 entry carrying prior content (data entry
        mistakes happen), but alpha itself must still be 1.0 for Tier 3
        per the locked tiering rule.
        """
        if self.tier == HistoricalTier.TIER_3 and self.alpha != 1.0:
            raise ValueError("HistoricalTier.TIER_3 requires alpha == 1.0 (Section 31).")
        return self


class TeamSeason(BaseModel):
    """
    Section 33 — TeamSeason Entity.

    Note: `computed_dimensions` / `computed_identity` are intentionally
    NOT stored fields here. Section 33 states they "در runtime محاسبه
    می‌شوند؛ چون formation انتخابی می‌تواند آن‌ها را تغییر دهد" — so this
    model only carries the catalog-level roster + prior; the Team
    Dimension/Identity Engines (Modules 2/3, Layer 2) compute the
    formation-specific values at match-build time and return them
    separately (see TeamRuntimeState in match_runtime.py).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description='e.g. "barcelona_2010_11"')
    club: str
    season: str = Field(..., description='e.g. "2010/11"')

    roster: list[str] = Field(..., description="PlayerSeason id references", min_length=1)

    historical_prior: HistoricalPrior | None = Field(
        None, description="None for teams with no curated historical data (fully generic derivation)"
    )


def apply_historical_prior_to_dimensions(
    derived: TeamDimensions,
    prior: HistoricalPrior | None,
) -> TeamDimensions:
    """
    Section 30 clamp formula applied to TeamDimensions, using
    `dimension_adjustment` as an additive delta on the derived value
    before the alpha blend collapses to a pure "derived" pass-through
    (since dimension_adjustment has no separate "prior value" concept —
    it is a correction, not a competing estimate).

    For Tier 3 / no-prior teams (alpha == 1.0 or prior is None), this is
    a no-op identity pass-through, matching:
        "برای ویژگی‌هایی که historical prior ندارند، derived به‌تنهایی
        استفاده می‌شود."
    """
    if prior is None or prior.alpha >= 1.0:
        return derived

    adj = prior.dimension_adjustment

    def _blend(value: float, delta: float) -> float:
        adjusted = value + delta
        blended = prior.alpha * value + (1 - prior.alpha) * adjusted
        return max(0.0, min(100.0, blended))

    return TeamDimensions(
        attack=_blend(derived.attack, adj.attack * 100),
        creation=_blend(derived.creation, adj.creation * 100),
        defense=_blend(derived.defense, adj.defense * 100),
        goalkeeping=_blend(derived.goalkeeping, adj.goalkeeping * 100),
    )


def apply_historical_prior_to_identity(
    derived: TeamIdentity,
    prior: HistoricalPrior | None,
) -> TeamIdentity:
    """
    Section 30 clamp formula applied to TeamIdentity fields, using
    `identity_priors` as the competing prior estimate (as opposed to
    dimensions, where the prior is expressed as a delta).

        final = clamp(alpha * derived + (1 - alpha) * historical_prior, 0, 1)

    Fields with no prior value fall back to derived-only, per Section 30.
    """
    if prior is None:
        return derived

    def _blend(derived_value: float, prior_value: float | None) -> float:
        if prior_value is None:
            return derived_value
        blended = prior.alpha * derived_value + (1 - prior.alpha) * prior_value
        return max(0.0, min(1.0, blended))

    ip = prior.identity_priors
    return TeamIdentity(
        possession_tendency=_blend(derived.possession_tendency, ip.possession_tendency),
        press_tendency=_blend(derived.press_tendency, ip.press_tendency),
        transition_tendency=_blend(derived.transition_tendency, ip.transition_tendency),
        tempo=_blend(derived.tempo, ip.tempo),
        risk_tolerance=_blend(derived.risk_tolerance, ip.risk_tolerance),
        compactness=_blend(derived.compactness, ip.compactness),
        # build_up_control_score / attack_pace_factor have no historical
        # prior concept in Section 33's schema — pass through derived.
        build_up_control_score=derived.build_up_control_score,
        attack_pace_factor=derived.attack_pace_factor,
    )
