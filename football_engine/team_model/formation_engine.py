"""Module 1 — FormationEngine V1 (Layer 2), approved W/H/C/P/U/Ts rules.

E-12: no formation classifier or snapshot-quality dependency. PlayerSeason
objects are consumed ONLY for squad/role validation, never ability, tendency,
pace, or quality. The calculation reads explicit template geometry and roles.

For ten outfield slots O, with B/M/F depth groups and side counts n_L/n_C/n_R:
    W  = (n_L + n_R) / N
    H  = h0 = 0.5 (disclosed V1 baseline prior, NOT inferred tactical height)
    C  = (|B| + number of DM slots in M) / N
    P  = E(M, F) / K
    U  = E(B, M) / K
    Ts = |F| * (N - |F|) / K
where K = floor(N*N/4) = 25, and E counts all cross-group slot pairs EXCEPT
opposite LEFT/RIGHT pairs. CENTER connects to every side. Pair normalisation
is combinatorial, not a calibrated coefficient. No feature-to-feature chain,
corrective clamp, opponent data, runtime state, mutation, I/O, or randomness.

The public two-input derive(players, formation) interface is preserved. The
formation name is descriptive output metadata; slot IDs are identity-only.
"""

from __future__ import annotations

from collections import Counter
from typing import Final

from football_engine.core.enums import PlayerRole
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import StructuralFeatures

REQUIRED_SQUAD_SIZE: Final[int] = 11
# The only numeric FormationEngine V1 calibration prior. Keeping its name and
# provenance here avoids a bare literal or an unrelated Layer 0 ParameterSet
# modification. A different tactical-height input/prior needs new approval.
V1_LINE_HEIGHT_BASELINE_PRIOR: Final[float] = 0.5


class FormationEngineError(ValueError):
    """Invalid squad/template shape, role occupancy, or explicit geometry."""


def _validate_input_shape(players: list[PlayerSeason], formation: Formation) -> None:
    if not isinstance(players, (list, tuple)) or len(players) != REQUIRED_SQUAD_SIZE:
        raise FormationEngineError("FormationEngine requires exactly 11 PlayerSeasons")
    if not all(isinstance(player, PlayerSeason) for player in players):
        raise FormationEngineError("Every squad entry must be a PlayerSeason")
    if not isinstance(formation, Formation):
        raise FormationEngineError("formation must be a Formation")
    if len(formation.position_pool) != REQUIRED_SQUAD_SIZE:
        raise FormationEngineError("Formation position_pool must contain exactly 11 slots")

    player_ids = [player.id for player in players]
    if len(set(player_ids)) != REQUIRED_SQUAD_SIZE:
        raise FormationEngineError("FormationEngine received duplicate PlayerSeason id(s)")

    for slot in formation.position_pool:
        if not isinstance(slot, PositionSlot):
            raise FormationEngineError("Every formation slot must be a PositionSlot")
        if not isinstance(slot.side, SlotSide) or not isinstance(slot.depth, SlotDepth):
            raise FormationEngineError("Every slot must have explicit valid SlotSide/SlotDepth geometry")
        if not isinstance(slot.role, PlayerRole):
            raise FormationEngineError("Every slot must have a valid PlayerRole")
    slot_ids = [slot.slot_id for slot in formation.position_pool]
    if len(set(slot_ids)) != REQUIRED_SQUAD_SIZE:
        raise FormationEngineError("Formation position_pool contains duplicate slot_id values")

    required_roles = Counter(slot.role for slot in formation.position_pool)
    available_roles = Counter(player.role for player in players)
    if required_roles != available_roles:
        raise FormationEngineError(
            f"Formation requires role counts {dict(required_roles)}, "
            f"but the supplied players have role counts {dict(available_roles)}"
        )
    if required_roles[PlayerRole.GK] != 1 or available_roles[PlayerRole.GK] != 1:
        raise FormationEngineError("FormationEngine requires exactly one GK in both squad and template")


def _connection_count(
    first_group: tuple[PositionSlot, ...],
    second_group: tuple[PositionSlot, ...],
) -> int:
    """Binary lateral adjacency only; no distance, ability, or role multipliers."""
    return sum(
        1
        for first in first_group
        for second in second_group
        if not (
            (first.side is SlotSide.LEFT and second.side is SlotSide.RIGHT)
            or (first.side is SlotSide.RIGHT and second.side is SlotSide.LEFT)
        )
    )


class FormationEngine:
    """Deterministic, stateless formation-structure derivation; no snapshot type."""

    def derive(self, players: list[PlayerSeason], formation: Formation) -> StructuralFeatures:
        _validate_input_shape(players, formation)
        outfield = tuple(slot for slot in formation.position_pool if slot.role is not PlayerRole.GK)
        n = len(outfield)  # Exactly 10 by the checked squad and GK preconditions.
        normalizer = (n * n) // 4
        back = tuple(slot for slot in outfield if slot.depth is SlotDepth.BACK)
        middle = tuple(slot for slot in outfield if slot.depth is SlotDepth.MID)
        front = tuple(slot for slot in outfield if slot.depth is SlotDepth.FRONT)
        wide_count = sum(slot.side is not SlotSide.CENTER for slot in outfield)
        middle_dm_count = sum(slot.role is PlayerRole.DM for slot in middle)
        front_count = len(front)

        return StructuralFeatures(
            formation_name=formation.name,
            width_feature=wide_count / n,
            line_height_feature=V1_LINE_HEIGHT_BASELINE_PRIOR,
            defensive_cover_feature=(len(back) + middle_dm_count) / n,
            press_structure_feature=_connection_count(middle, front) / normalizer,
            build_up_structure_feature=_connection_count(back, middle) / normalizer,
            transition_structure_feature=front_count * (n - front_count) / normalizer,
        )
