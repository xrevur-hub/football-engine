"""
Shared fixtures/builders for Layer 2 (football_engine.team_model) tests.

These build real Layer 0 core-model instances directly (PlayerSeason,
Formation, PositionSlot, StructuralFeatures, HistoricalPrior) rather than
going through the Layer 1 JSON pipeline — Layer 2 tests exercise the
Modules 1-3 contracts in isolation and should not depend on Layer 1
loader behavior.
"""

from __future__ import annotations

from football_engine.core.enums import HistoricalTier, PlayerRole
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.core.team_season import DimensionAdjustment, HistoricalPrior, IdentityPriors

# A standard 11-role layout usable as either a Formation's position pool
# or a matching list of PlayerSeason roles. Order matters only in that
# len(...) == 11 and the role *multiset* must match between the two.
STANDARD_ROLES: list[PlayerRole] = [
    PlayerRole.GK,
    PlayerRole.FB,
    PlayerRole.CB,
    PlayerRole.CB,
    PlayerRole.FB,
    PlayerRole.DM,
    PlayerRole.CM,
    PlayerRole.CM,
    PlayerRole.WM,
    PlayerRole.WM,
    PlayerRole.FW,
]


def make_test_player(player_id: str, role: PlayerRole, **overrides) -> PlayerSeason:
    base = dict(
        id=player_id,
        name=player_id,
        season="2020/21",
        role=role,
        attack_ability=50.0,
        creation_ability=50.0,
        defense_ability=50.0,
        gk_ability=50.0 if role == PlayerRole.GK else 0.0,
    )
    base.update(overrides)
    return PlayerSeason(**base)


def make_standard_squad(prefix: str = "p") -> list[PlayerSeason]:
    """11 PlayerSeasons whose role multiset exactly matches STANDARD_ROLES
    (and therefore matches make_standard_formation()'s position pool)."""
    return [make_test_player(f"{prefix}{i}", role) for i, role in enumerate(STANDARD_ROLES)]


# side/depth are additive Layer 0/core contract fields (conversation record
# — Option 3 decision, 2026-09-08): required, explicit per slot, aligned
# 1:1 with STANDARD_ROLES (GK, FB, CB, CB, FB, DM, CM, CM, WM, WM, FW).
STANDARD_GEOMETRY = [
    (SlotSide.CENTER, SlotDepth.BACK),  # GK
    (SlotSide.RIGHT, SlotDepth.BACK),  # FB
    (SlotSide.LEFT, SlotDepth.BACK),  # CB
    (SlotSide.RIGHT, SlotDepth.BACK),  # CB
    (SlotSide.LEFT, SlotDepth.BACK),  # FB
    (SlotSide.CENTER, SlotDepth.MID),  # DM
    (SlotSide.LEFT, SlotDepth.MID),  # CM
    (SlotSide.RIGHT, SlotDepth.MID),  # CM
    (SlotSide.LEFT, SlotDepth.FRONT),  # WM
    (SlotSide.RIGHT, SlotDepth.FRONT),  # WM
    (SlotSide.CENTER, SlotDepth.FRONT),  # FW
]


def make_standard_formation(name: str = "4-3-3") -> Formation:
    return Formation(
        name=name,
        position_pool=[
            PositionSlot(slot_id=f"slot_{i}", role=role, side=side, depth=depth)
            for i, (role, (side, depth)) in enumerate(zip(STANDARD_ROLES, STANDARD_GEOMETRY))
        ],
    )


def make_structural_features(**overrides) -> StructuralFeatures:
    base = dict(formation_name="4-3-3")
    base.update(overrides)
    return StructuralFeatures(**base)


def make_historical_prior(
    tier: HistoricalTier = HistoricalTier.TIER_1,
    alpha: float = 0.55,
    **overrides,
) -> HistoricalPrior:
    base = dict(
        tier=tier,
        alpha=alpha,
        identity_priors=IdentityPriors(),
        dimension_adjustment=DimensionAdjustment(),
    )
    base.update(overrides)
    return HistoricalPrior(**base)
