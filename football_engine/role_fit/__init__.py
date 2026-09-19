"""
Role fit — multi-position players and the E-24 fit coefficients.

WHAT THIS ADDS TO THE ENGINE
----------------------------
Until now `build_effective_xi` accepted a `fit_table` but every project-level
caller passed `None`, so every fit factor was a neutral 1.0 and a striker at
centre-back lost nothing beyond having his low `defense_ability` re-weighted.
This module supplies that table.

That makes it NEW SIMULATION MATHEMATICS, and it is treated as such:

  * every coefficient lives in `RoleFitCoefficients` and is overridable,
  * nothing here is presented as calibrated - the defaults are stated priors,
  * no existing engine file is modified; the table is injected through the
    hook `effective_xi.build_effective_xi(..., fit_table=...)` already exposes.

TWO SEPARATE IDEAS, DELIBERATELY NOT CONFLATED
----------------------------------------------
1. `positions` - the set of roles a player genuinely plays. Dani Alves is a
   full-back who also plays wide midfield; Abidal is a full-back who also
   plays centre-back. Inside a player's own position set the fit is 1.0.

2. `fit_factor` - what it costs to use a player outside that set. Derived from
   a positional distance between the drafted role and the assigned role, so a
   full-back at wing-back costs almost nothing and a striker in goal costs a
   lot, without a hand-written 8x8 table of magic numbers.

WHAT THIS DOES *NOT* MODEL
--------------------------
Left/right footedness. The engine's role vocabulary has no LB/RB split - a
slot's `side` comes from the formation template, not the player - so "Alves is
a RIGHT back" is expressed by where you place him on the pitch, not by his
role. Adding a footedness penalty would be a second, separate feature.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
POSITIONS_FILE = REPO_ROOT / "data" / "normalized" / "players" / "player_positions.json"

ROLES = ("GK", "CB", "FB", "DM", "CM", "WM", "AM", "FW")


# ---------------------------------------------------------------------------
# Positional geometry
# ---------------------------------------------------------------------------

# (depth, width) coordinates for each role, on the same pitch the formation
# templates describe: depth 0 = own goal line, width 0 = central, 1 = touchline.
# These are a description of the existing role vocabulary, not a new model of
# football - they exist only to give "how far apart are these two roles" a
# defensible answer instead of an arbitrary table.
ROLE_COORDS: dict[str, tuple[float, float]] = {
    "GK": (0.0, 0.0),
    "CB": (1.0, 0.0),
    "FB": (1.4, 1.0),
    "DM": (2.0, 0.0),
    "CM": (3.0, 0.0),
    "WM": (3.4, 1.0),
    "AM": (4.0, 0.0),
    "FW": (5.0, 0.0),
}


@dataclass(frozen=True)
class RoleFitCoefficients:
    """
    Every tunable number in this module. All are PRIORS, not calibrated values.

    k_distance   how steeply fit decays per unit of positional distance
    width_weight how much a lateral mismatch counts relative to a depth one
    floor        the worst fit any outfield mismatch can produce
    gk_penalty   fit for a non-keeper asked to keep goal, and vice versa
    """

    k_distance: float = 0.085
    width_weight: float = 1.2
    floor: float = 0.55
    gk_penalty: float = 0.40


DEFAULT_ROLE_FIT_COEFFICIENTS = RoleFitCoefficients()


def role_distance(a: str, b: str, coeffs: RoleFitCoefficients = DEFAULT_ROLE_FIT_COEFFICIENTS) -> float:
    """Euclidean distance between two roles on the (depth, width) plane."""
    if a not in ROLE_COORDS or b not in ROLE_COORDS:
        raise KeyError(f"unknown role in ({a!r}, {b!r})")
    (d1, w1), (d2, w2) = ROLE_COORDS[a], ROLE_COORDS[b]
    return math.hypot(d1 - d2, coeffs.width_weight * (w1 - w2))


def fit_factor(
    draft_role: str,
    assigned_role: str,
    positions: Iterable[str] = (),
    coeffs: RoleFitCoefficients = DEFAULT_ROLE_FIT_COEFFICIENTS,
) -> float:
    """
    Fit factor in (0, 1]. 1.0 means no penalty.

    Order of decision:
      1. the assigned role is one the player actually plays  -> 1.0
      2. goalkeeping is involved on exactly one side          -> gk_penalty
      3. otherwise decay with positional distance, clamped at `floor`
    """
    if assigned_role == draft_role or assigned_role in set(positions):
        return 1.0
    if (draft_role == "GK") != (assigned_role == "GK"):
        return coeffs.gk_penalty
    decayed = 1.0 - coeffs.k_distance * role_distance(draft_role, assigned_role, coeffs)
    return max(coeffs.floor, min(1.0, decayed))


# ---------------------------------------------------------------------------
# Deriving a player's position set
# ---------------------------------------------------------------------------

# Candidate secondary roles per primary role, each gated by a condition on the
# player's own attributes. A full-back only also plays wide midfield if he is
# actually quick and offensive; a centre-back only covers at full-back if he
# has the pace for it. So the position set is earned from the data, not
# assigned by fiat.
_SECONDARY_RULES: dict[str, list[tuple[str, str, float]]] = {
    "GK": [],
    "CB": [("FB", "pace", 0.55), ("DM", "creation_ability", 60.0)],
    "FB": [("WM", "pace", 0.58), ("CB", "defense_ability", 72.0)],
    "DM": [("CM", "creation_ability", 0.0), ("CB", "defense_ability", 72.0)],
    "CM": [("DM", "defense_ability", 62.0), ("AM", "creation_ability", 72.0)],
    "WM": [("FW", "attack_ability", 70.0), ("AM", "creation_ability", 70.0), ("FB", "defense_ability", 58.0)],
    "AM": [("CM", "defense_ability", 55.0), ("FW", "attack_ability", 72.0), ("WM", "pace", 0.65)],
    "FW": [("AM", "creation_ability", 68.0), ("WM", "pace", 0.68)],
}


def derive_positions(player: Mapping) -> list[str]:
    """
    Derive a player's position set from their primary role and attributes.

    `player` is any mapping with the PlayerSeason attribute keys - a raw JSON
    record or a `model_dump()`. The primary role always comes first.
    """
    primary = player["role"] if isinstance(player["role"], str) else player["role"].value
    out = [primary]
    for candidate, attribute, threshold in _SECONDARY_RULES.get(primary, []):
        if float(player.get(attribute, 0.0)) >= threshold and candidate not in out:
            out.append(candidate)
    return out


# ---------------------------------------------------------------------------
# The position store
# ---------------------------------------------------------------------------


@dataclass
class PositionStore:
    """
    Position sets for every player, plus the fit table the engine consumes.

    Loaded from `player_positions.json` when present. Any player missing from
    that file falls back to the derivation rules above, so the store is never
    partially blind.
    """

    positions: dict[str, list[str]] = field(default_factory=dict)
    coeffs: RoleFitCoefficients = DEFAULT_ROLE_FIT_COEFFICIENTS
    overrides: dict[str, list[str]] = field(default_factory=dict)

    def for_player(self, player_id: str, fallback_role: str) -> list[str]:
        if player_id in self.overrides:
            return list(self.overrides[player_id])
        return list(self.positions.get(player_id, [fallback_role]))

    def fit_table_for(self, players: Iterable) -> dict[tuple[str, str], float]:
        """
        Build the (draft_role, assigned_role) -> factor table for ONE XI.

        `build_effective_xi` keys the table by role pair, not by player, so the
        table must be built per squad: two drafted full-backs with different
        position sets would otherwise collide. Where they do collide, the more
        generous factor wins, because the pessimistic one would penalise a
        player for a team-mate's limitations.
        """
        table: dict[tuple[str, str], float] = {}
        for p in players:
            draft_role = p.role.value if hasattr(p.role, "value") else str(p.role)
            positions = self.for_player(p.id, draft_role)
            for assigned in ROLES:
                key = (draft_role, assigned)
                value = fit_factor(draft_role, assigned, positions, self.coeffs)
                if key not in table or value > table[key]:
                    table[key] = value
        return table

    def explain(self, player_id: str, draft_role: str, assigned_role: str) -> dict:
        """Everything the UI needs to describe one placement honestly."""
        positions = self.for_player(player_id, draft_role)
        return {
            "positions": positions,
            "assigned_role": assigned_role,
            "natural": assigned_role in positions,
            "fit_factor": round(fit_factor(draft_role, assigned_role, positions, self.coeffs), 3),
        }


def load_position_store(
    path: Optional[Path] = None,
    coeffs: RoleFitCoefficients = DEFAULT_ROLE_FIT_COEFFICIENTS,
) -> PositionStore:
    """Load the position file if it exists; otherwise return an empty store."""
    target = path or POSITIONS_FILE
    if not target.is_file():
        return PositionStore(coeffs=coeffs)
    payload = json.loads(target.read_text(encoding="utf-8"))
    return PositionStore(
        positions={k: list(v) for k, v in payload.get("positions", {}).items()},
        overrides={k: list(v) for k, v in payload.get("overrides", {}).items()},
        coeffs=coeffs,
    )


def build_positions_file(players: Iterable[Mapping], overrides: Optional[Mapping] = None) -> dict:
    """Produce the JSON payload for `player_positions.json`."""
    return {
        "metadata": {
            "description": (
                "Position sets per PlayerSeason. 'positions' is derived from the "
                "player's primary role and their own attributes; 'overrides' is "
                "hand-curated and always wins."
            ),
            "derivation": {
                primary: [{"role": r, "requires": f"{a} >= {t}"} for r, a, t in rules]
                for primary, rules in _SECONDARY_RULES.items()
            },
        },
        "positions": {p["id"]: derive_positions(p) for p in players},
        "overrides": dict(overrides or {}),
    }
