"""
Effective XI — Route C transform (E-16.1 / E-16.8 approved).

Free XI means the player can place any of their 11 drafted players into any
slot with no legality gate. Unbalanced or misplaced arrangements are penalized
by the engine's EXISTING mathematics (role-weighted team dimensions, structural
features, defensive cover) — not by a new formula.

Mechanism (inserted BEFORE the unchanged Formation Engine / Layer 2):
    Draft XI  ->  User Assignment  ->  Effective XI  ->  existing pipeline

Three-identity separation (critical invariant):
    draft identity   !=  assigned role  !=  effective (role-fit-adjusted) ability
    - draft_player_id / draft_role : who the player really is (for attribution, E-16.7)
    - .role                          : where the user placed them this match
    - ability fields on this object  : draft ability * fit_factor

Role-fit COEFFICIENTS (E-24) are deliberately UNSPECIFIED project-wide. This
module therefore defaults all fits to a NEUTRAL 1.0 (no extra penalty) and
makes the fit table pluggable. The natural penalty for a misplaced striker at
CB already exists: their low defense_ability is weighted as if they were a CB.
E-22 (freeing H=0.5) is out of scope. No core/ file is modified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from pydantic import ConfigDict, Field

from football_engine.core.enums import PlayerRole
from football_engine.core.formation import Formation
from football_engine.core.player_season import PlayerSeason


class EffectiveXiPlayer(PlayerSeason):
    """
    Frozen subclass of PlayerSeason that is type-distinguishable (I-3).

    `.role` reflects the ASSIGNED slot role (what downstream Layer 2 weights).
    `draft_player_id` / `draft_role` preserve the immutable Draft identity so
    that event attribution (E-16.7) can attribute goals/assists by draft role
    and NEVER by assigned role (avoiding double-penalizing a misplaced player).

    Ability fields carry the effective (role-fit-adjusted) values. With the
    default neutral fit table these equal the draft abilities.
    """

    model_config = ConfigDict(frozen=True)

    draft_player_id: str = Field(..., description="Original PlayerSeason.id (draft identity)")
    draft_role: PlayerRole = Field(..., description="Original draft role (unused by Layer 2 math)")
    fit_factor: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Role-fit factor applied to abilities (E-24: coefficients unspecified -> 1.0 neutral)",
    )

    @property
    def is_effective(self) -> bool:
        return True


# A role-fit factor table: mapping from (draft_role, assigned_role) -> fit_factor.
# E-24 is deliberately UNSPECIFIED, so this starts as an all-1.0 neutral table.
# Callers may override specific cells; values remain calibration-aware priors.
NeutralFitTable = {
    (r1.value, r2.value): 1.0
    for r1 in PlayerRole
    for r2 in PlayerRole
}


def _role_fit_factor(
    draft_role: PlayerRole,
    assigned_role: PlayerRole,
    fit_table: Optional[dict] = None,
) -> float:
    """Return fit factor from (draft_role, assigned_role); default neutral 1.0.

    fit_table keys are string pairs, e.g. ("FW", "CB"). A missing cell defaults
    to 1.0 (no penalty) to keep the engine unbiased until E-24 provides values.
    """
    table = fit_table or NeutralFitTable
    return float(table.get((draft_role.value, assigned_role.value), 1.0))


def build_effective_xi(
    draft_players: Sequence[PlayerSeason],
    formation: Formation,
    assignment: dict[str, str],
    fit_table: Optional[dict] = None,
) -> list[EffectiveXiPlayer]:
    """
    Transform a Draft XI + user assignment into an Effective XI (Route C).

    Args:
        draft_players: 11 PlayerSeason objects (draft identity preserved).
        formation:      any Formation (11 slots) the user wants to play.
        assignment:     dict {player_id: slot_id} placing each player in a slot.
        fit_table:      optional (draft_role, assigned_role) -> fit_factor table.

    The assigned slot's ROLE becomes the player's effective `.role`, and the
    player's abilities are scaled by fit_factor. The resulting Effective XI
    matches the formation's slot count exactly, so the unchanged Formation
    Engine accepts it (its role-count gate trivially passes).

    Raises ValueError on: wrong player count, wrong assignment coverage, a
    player assigned to an unknown slot, or no slot with role GK.
    """
    if len(draft_players) != 11:
        raise ValueError(f"Effective XI requires exactly 11 drafted players, got {len(draft_players)}")
    if len(formation.position_pool) != 11:
        raise ValueError(f"Formation must have exactly 11 slots, got {len(formation.position_pool)}")

    draft_by_id = {p.id: p for p in draft_players}
    if len(draft_by_id) != len(draft_players):
        raise ValueError("Draft XI contains duplicate player ids")

    slots_by_id = {s.slot_id: s for s in formation.position_pool}
    if len(slots_by_id) != len(formation.position_pool):
        raise ValueError("Formation contains duplicate slot ids")

    if set(assignment.keys()) != set(draft_by_id.keys()):
        missing = set(draft_by_id) - set(assignment)
        extra = set(assignment) - set(draft_by_id)
        raise ValueError(f"Assignment must cover exactly the 11 draft players; missing={missing}, extra={extra}")

    unknown_slots = set(assignment.values()) - set(slots_by_id)
    if unknown_slots:
        raise ValueError(f"Assignment references unknown slot ids: {sorted(unknown_slots)}")

    if not any(s.role == PlayerRole.GK for s in formation.position_pool):
        raise ValueError("Formation must contain exactly one GK; the engine guarantees a legal XI")

    effective: list[EffectiveXiPlayer] = []
    for player in draft_players:
        slot = slots_by_id[assignment[player.id]]
        assigned_role = slot.role
        fit = _role_fit_factor(player.role, assigned_role, fit_table)
        effective.append(
            EffectiveXiPlayer(
                id=player.id,
                name=player.name,
                season=player.season,
                role=assigned_role,               # ASSIGNED role drives Layer 2 math
                attack_ability=player.attack_ability * fit,
                creation_ability=player.creation_ability * fit,
                defense_ability=player.defense_ability * fit,
                gk_ability=player.gk_ability * fit,
                shot_tendency=player.shot_tendency,
                press_tendency=player.press_tendency,
                transition_tendency=player.transition_tendency,
                pace=player.pace,
                discipline_score=player.discipline_score,
                impact_score=player.impact_score,
                draft_player_id=player.id,        # draft identity (E-16.7)
                draft_role=player.role,
                fit_factor=fit,
            )
        )

    return effective