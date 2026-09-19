"""
Engine adapter — the ONLY module the web layer is allowed to reach through.

Nothing here computes football. Every number returned by this module is read
straight out of an engine object. The adapter's whole job is:

    JSON in  ->  existing engine call order  ->  JSON out

The call order below is copied from the already-working runners
(`football_engine/calibration/runner.py`), so the web app walks exactly the
same path that the calibrated 3000-match run walks:

    PlayerSeason -> (free placement) Formation -> EffectiveXiPlayer
      -> TeamModelBuilder (FormationEngine -> D1 -> Identity + prior blend)
      -> TeamRuntimeState -> MatchRuntime
      -> MatchOrchestrator.simulate -> MatchResult

Deliberately NOT provided here (they do not exist in the engine yet, and a
fabricated version would be worse than nothing):

    overall rating, stamina/fatigue, decision quality, decision noise,
    player development, user-authored tactical overrides.

`engine_capabilities()` reports that list to the UI so the frontend can show
honest empty states instead of inventing values.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from football_engine.api.pitch_formation import (
    PitchGridError,
    assignment_from_placements,
    build_formation,
    formation_to_grid,
    normalize_placements,
    shape_label,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "normalized"
SQUAD_SIZE = 11


class AdapterError(ValueError):
    """A request the engine cannot accept. Carries a user-safe message."""


# --------------------------------------------------------------------------
# Lazily-built, process-wide engine handles
# --------------------------------------------------------------------------


@dataclass
class _EngineHandles:
    repos: Any
    builder: Any
    policy: Any


_handles: Optional[_EngineHandles] = None
_lock = threading.Lock()


def handles() -> _EngineHandles:
    """Load the dataset and configure the engines once per process."""
    global _handles
    if _handles is not None:
        return _handles
    with _lock:
        if _handles is not None:
            return _handles

        from football_engine.data_layer import create_possession_source
        from football_engine.data_layer.loader import load_all
        from football_engine.matchup.tactical_policy import create_tactical_profile_policy
        from football_engine.team_model import TeamIdentityEngine, TeamModelBuilder

        repos = load_all(DATA_DIR)
        possession = create_possession_source()
        builder = TeamModelBuilder(
            identity_engine=TeamIdentityEngine(possession_source=possession)
        )
        _handles = _EngineHandles(
            repos=repos,
            builder=builder,
            policy=create_tactical_profile_policy(),
        )
        return _handles


# --------------------------------------------------------------------------
# Capability reporting (drives the UI's honest empty states)
# --------------------------------------------------------------------------


def engine_capabilities() -> dict:
    return {
        "available": [
            "free_xi_placement",
            "formation_structural_features",
            "team_dimensions",
            "team_identity",
            "tactical_profile_derived",
            "multi_position_players",
            "role_fit_coefficients",
            "lottery_draft",
            "directional_matchup",
            "home_advantage",
            "dixon_coles",
            "seeded_reproducibility",
            "goal_events",
            "shot_events",
            "card_events",
            "substitution_events",
        ],
        "unavailable": [
            "overall_rating",
            "stamina",
            "fatigue",
            "decision_quality",
            "decision_noise",
            "player_development",
            "manual_tactical_overrides",
            "possession_percentage",
            "live_minute_by_minute_replay",
        ],
        "notes": {
            "role_fit_coefficients": (
                "Now supplied by football_engine.role_fit. The coefficients are stated "
                "PRIORS, not calibrated values - see /api/role-fit."
            ),
            "manual_tactical_overrides": (
                "TacticalProfile is derived from team identity, formation structure and "
                "in-match state. There is no user-facing tactics input in the engine yet."
            ),
            "line_height_feature": (
                "Fixed V1 baseline prior of 0.5; it is not derived from placement, so it "
                "is not presented as a placement-driven value."
            ),
        },
    }


# --------------------------------------------------------------------------
# Catalog reads
# --------------------------------------------------------------------------


def _player_dto(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "season": p.season,
        "role": p.role.value,
        "attack_ability": p.attack_ability,
        "creation_ability": p.creation_ability,
        "defense_ability": p.defense_ability,
        "gk_ability": p.gk_ability,
        "shot_tendency": p.shot_tendency,
        "press_tendency": p.press_tendency,
        "transition_tendency": p.transition_tendency,
        "pace": p.pace,
        "discipline_score": p.discipline_score,
        "impact_score": p.impact_score,
    }


def list_players() -> list[dict]:
    """
    Every non-placeholder PlayerSeason, annotated with the club/season it was
    curated from and with the provenance the dataset already records.

    `synthetic` marks the neutral-rated template players that
    `competition/synthetic_teams.py` generates to exercise the UCL engine. They
    are flagged, never silently mixed in as if they were researched history.
    """
    h = handles()
    club_of: dict[str, tuple[str, str]] = {}
    synthetic_ids: set[str] = set()
    for team in h.repos.teams.all(include_placeholder=False):
        synthetic = _is_synthetic_team(team.id)
        for pid in team.roster:
            club_of[pid] = (team.club, team.id)
            if synthetic:
                synthetic_ids.add(pid)

    out = []
    for p in h.repos.players.all(include_placeholder=False):
        club, team_id = club_of.get(p.id, ("", ""))
        dto = _player_dto(p)
        dto["club"] = club
        dto["team_id"] = team_id
        dto["synthetic"] = p.id in synthetic_ids
        out.append(dto)
    out.sort(key=lambda d: (d["synthetic"], d["club"], d["name"]))
    return out


def _is_synthetic_team(team_id: str) -> bool:
    """Synthetic template clubs are the 2015/16 scaffolding block."""
    return team_id.endswith("_2015_16")


def list_teams() -> list[dict]:
    h = handles()
    out = []
    for team in h.repos.teams.all(include_placeholder=False):
        out.append(
            {
                "id": team.id,
                "club": team.club,
                "season": team.season,
                "roster": list(team.roster),
                "default_formation": h.repos.teams.default_formation_name(team.id),
                "has_historical_prior": team.historical_prior is not None,
                "synthetic": _is_synthetic_team(team.id),
            }
        )
    out.sort(key=lambda d: (d["synthetic"], d["club"]))
    return out


def list_formation_presets() -> list[dict]:
    """Authored presets, expressed as grid cells so the builder can preload one."""
    h = handles()
    out = []
    for formation in h.repos.formations.all():
        try:
            cells = formation_to_grid(formation)
        except PitchGridError:
            continue
        out.append({"name": formation.name, "cells": cells})
    out.sort(key=lambda d: d["name"])
    return out


# --------------------------------------------------------------------------
# Team model construction
# --------------------------------------------------------------------------


def _structural_dto(sf) -> dict:
    return {
        "formation_name": sf.formation_name,
        "width": sf.width_feature,
        "defensive_cover": sf.defensive_cover_feature,
        "press_structure": sf.press_structure_feature,
        "build_up_structure": sf.build_up_structure_feature,
        "transition_structure": sf.transition_structure_feature,
        "line_height_fixed_prior": sf.line_height_feature,
    }


def _dimensions_dto(d) -> dict:
    return {
        "attack": d.attack,
        "creation": d.creation,
        "defense": d.defense,
        "goalkeeping": d.goalkeeping,
    }


def _identity_dto(i) -> dict:
    return {
        "possession_tendency": i.possession_tendency,
        "press_tendency": i.press_tendency,
        "transition_tendency": i.transition_tendency,
        "tempo": i.tempo,
        "risk_tolerance": i.risk_tolerance,
        "compactness": i.compactness,
        "build_up_control_score": i.build_up_control_score,
        "attack_pace_factor": i.attack_pace_factor,
    }


def _tactical_dto(t) -> dict:
    return {
        "press_final": t.press_final,
        "line_final": t.line_final,
        "width_final": t.width_final,
        "build_up_control_score": t.build_up_control_score,
        "defensive_cover_feature": t.defensive_cover_feature,
        "attack_pace_factor": t.attack_pace_factor,
        "transition_tendency_final": t.transition_tendency_final,
        "tempo_final": t.tempo_final,
        "possession_tendency_final": t.possession_tendency_final,
    }


def _resolve_players(player_ids: list[str]) -> list:
    h = handles()
    from football_engine.data_layer.exceptions import UnknownReferenceError

    players = []
    for pid in player_ids:
        try:
            players.append(h.repos.players.get(pid))
        except UnknownReferenceError as exc:
            raise AdapterError(f"unknown player id: {pid!r}") from exc
    return players


def build_user_team(placements: list[dict]) -> dict:
    """
    Free-XI path: raw placements -> Formation -> EffectiveXiPlayer -> TeamModel.

    Returns the engine objects plus their serializable projections. No
    historical prior is applied: a drafted XI is not a curated TeamSeason.
    """
    from football_engine.core.enums import MatchState
    from football_engine.xi_assignment.effective_xi import build_effective_xi

    h = handles()
    try:
        normalized = normalize_placements(placements)
        formation = build_formation(normalized)
        assignment = assignment_from_placements(normalized)
    except PitchGridError as exc:
        raise AdapterError(str(exc)) from exc

    draft_players = _resolve_players([p["player_id"] for p in normalized])

    # Role-fit table. Imported lazily: sessions.py imports this module, so a
    # top-level import here would be circular.
    from football_engine.api.sessions import fit_table_for_players

    try:
        effective = build_effective_xi(
            draft_players, formation, assignment,
            fit_table=fit_table_for_players(draft_players),
        )
        model = h.builder.build(effective, formation, None)
    except (ValueError, NotImplementedError) as exc:
        raise AdapterError(f"engine rejected this XI: {exc}") from exc

    tactical = h.policy(
        identity=model.identity,
        structural_features=model.structural_features,
        state=MatchState.NORMAL,
    )

    from football_engine.api.sessions import annotate_placements

    by_id = {p.id: p for p in draft_players}
    placement_dto = annotate_placements([
        {
            **p,
            "name": by_id[p["player_id"]].name,
            "season": by_id[p["player_id"]].season,
            "draft_role": by_id[p["player_id"]].role.value,
            "assigned_role": p["role"],
            "out_of_position": by_id[p["player_id"]].role.value != p["role"],
        }
        for p in normalized
    ])

    return {
        "engine": {
            "formation": formation,
            "effective_xi": effective,
            "model": model,
        },
        "dto": {
            "shape": shape_label(normalized),
            "placements": placement_dto,
            "structural_features": _structural_dto(model.structural_features),
            "dimensions": _dimensions_dto(model.dimensions),
            "identity": _identity_dto(model.identity),
            "tactical_profile_normal_state": _tactical_dto(tactical),
        },
    }


def build_catalog_team(team_id: str, formation_name: str | None = None) -> dict:
    """
    Opponent path: a curated TeamSeason in its own formation.

    Uses `remap_players` exactly as the existing runners do, so a roster whose
    draft roles do not match the template's slot roles stays playable.
    """
    from football_engine.core.enums import MatchState
    from football_engine.data_layer.exceptions import UnknownReferenceError
    from football_engine.xi_assignment.role_remap import remap_players

    h = handles()
    try:
        team = h.repos.teams.get(team_id)
    except UnknownReferenceError as exc:
        raise AdapterError(f"unknown team id: {team_id!r}") from exc

    name = formation_name or h.repos.teams.default_formation_name(team_id) or "4-3-3"
    try:
        formation = h.repos.formations.get(name)
    except UnknownReferenceError as exc:
        raise AdapterError(f"unknown formation: {name!r}") from exc

    players = _resolve_players(list(team.roster))
    try:
        players = remap_players(players, formation)
        model = h.builder.build(players, formation, h.repos.historical_priors.get(team_id))
    except (ValueError, NotImplementedError) as exc:
        raise AdapterError(f"engine rejected team {team_id}: {exc}") from exc

    tactical = h.policy(
        identity=model.identity,
        structural_features=model.structural_features,
        state=MatchState.NORMAL,
    )

    return {
        "engine": {"formation": formation, "players": players, "model": model},
        "dto": {
            "team_id": team.id,
            "club": team.club,
            "season": team.season,
            "formation_name": formation.name,
            "synthetic": _is_synthetic_team(team.id),
            "lineup": [
                {"id": p.id, "name": p.name, "role": p.role.value, "season": p.season}
                for p in players
            ],
            "structural_features": _structural_dto(model.structural_features),
            "dimensions": _dimensions_dto(model.dimensions),
            "identity": _identity_dto(model.identity),
            "tactical_profile_normal_state": _tactical_dto(tactical),
        },
    }


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------


def _runtime_state(team_id: str, model, formation, players, is_home: bool):
    from football_engine.core.team_runtime_state import TeamRuntimeState

    return TeamRuntimeState(
        team_id=team_id,
        dims=model.dimensions,
        identity=model.identity,
        formation=formation,
        formation_structural_features=model.structural_features,
        roster=[p.id for p in players],
        is_home=is_home,
    )


def simulate_match(
    placements: list[dict],
    opponent_team_id: str,
    *,
    user_is_home: bool = True,
    seed: int | None = None,
    match_id: str = "web_match",
) -> dict:
    """Run one match through the unmodified MatchOrchestrator."""
    from football_engine.core.match_runtime import MatchRuntime
    from football_engine.rng.seeded_rng import SeededRNG
    from football_engine.simulation.match_orchestrator import create_match_orchestrator

    user = build_user_team(placements)
    opponent = build_catalog_team(opponent_team_id)

    user_id = "your_xi"
    if seed is None:
        seed = SeededRNG.derive_match_seed(user_id, opponent_team_id, "", match_id)
    seed = int(seed) % (2**63 - 1)

    user_state = _runtime_state(
        user_id,
        user["engine"]["model"],
        user["engine"]["formation"],
        user["engine"]["effective_xi"],
        is_home=user_is_home,
    )
    opp_state = _runtime_state(
        opponent_team_id,
        opponent["engine"]["model"],
        opponent["engine"]["formation"],
        opponent["engine"]["players"],
        is_home=not user_is_home,
    )

    if user_is_home:
        home_state, away_state = user_state, opp_state
        home_players = user["engine"]["effective_xi"]
        away_players = opponent["engine"]["players"]
        home_id, away_id = user_id, opponent_team_id
    else:
        home_state, away_state = opp_state, user_state
        home_players = opponent["engine"]["players"]
        away_players = user["engine"]["effective_xi"]
        home_id, away_id = opponent_team_id, user_id

    runtime = MatchRuntime(
        match_id=match_id,
        seed=seed,
        is_tournament=False,
        home_team_id=home_id,
        away_team_id=away_id,
        rng=SeededRNG(seed),
        home=home_state,
        away=away_state,
    )

    orchestrator = create_match_orchestrator(is_tournament=False)
    try:
        result = orchestrator.simulate(
            runtime, home_players=home_players, away_players=away_players
        )
    except (ValueError, NotImplementedError) as exc:
        raise AdapterError(f"simulation failed: {exc}") from exc

    name_of = {p.id: p.name for p in list(home_players) + list(away_players)}
    return {
        "match_id": result.match_id,
        "seed": result.seed,
        "reproducible": result.reproducible,
        "user_is_home": user_is_home,
        "home": {"team_id": home_id, "score": result.final_score_home},
        "away": {"team_id": away_id, "score": result.final_score_away},
        "timeline": _timeline(result, name_of),
        "totals": {
            "shots_home": sum(1 for s in result.shot_log if s.is_home_team),
            "shots_away": sum(1 for s in result.shot_log if not s.is_home_team),
            "shots_on_target_home": sum(
                1 for s in result.shot_log if s.is_home_team and s.on_target
            ),
            "shots_on_target_away": sum(
                1 for s in result.shot_log if not s.is_home_team and s.on_target
            ),
            "saves_home": sum(1 for s in result.save_log if s.is_home_team),
            "saves_away": sum(1 for s in result.save_log if not s.is_home_team),
            "xg_home": round(sum(s.xg for s in result.shot_log if s.is_home_team), 2),
            "xg_away": round(sum(s.xg for s in result.shot_log if not s.is_home_team), 2),
        },
        "user_team": user["dto"],
        "opponent": opponent["dto"],
    }


def _timeline(result, name_of: dict[str, str]) -> list[dict]:
    """Flatten the engine's typed event logs into one minute-ordered list."""
    events: list[dict] = []
    for g in result.goal_log:
        events.append(
            {
                "minute": g.minute,
                "type": "GOAL",
                "is_home_team": g.is_home_team,
                "team_id": g.team_id,
                "player": name_of.get(g.scorer_player_id, g.scorer_player_id),
                "assist": name_of.get(g.assist_player_id) if g.assist_player_id else None,
                "xg": round(g.xg_credit, 2),
            }
        )
    for c in result.card_log:
        events.append(
            {
                "minute": c.minute,
                "type": "RED_CARD" if c.is_red else "YELLOW_CARD",
                "is_home_team": c.is_home_team,
                "team_id": c.team_id,
                "player": name_of.get(c.player_id, c.player_id),
            }
        )
    for s in result.substitution_log:
        events.append(
            {
                "minute": s.minute,
                "type": "SUBSTITUTION",
                "is_home_team": s.is_home_team,
                "team_id": s.team_id,
                "player": name_of.get(s.player_in_id, s.player_in_id),
                "player_out": name_of.get(s.player_out_id, s.player_out_id),
            }
        )
    for s in result.save_log:
        events.append(
            {
                "minute": s.minute,
                "type": "SAVE",
                "is_home_team": s.is_home_team,
                "team_id": s.team_id,
                "player": name_of.get(s.gk_player_id, s.gk_player_id),
            }
        )
    for s in result.shot_log:
        if s.is_goal:
            continue  # already represented by its GoalEvent
        events.append(
            {
                "minute": s.minute,
                "type": "SHOT_ON_TARGET" if s.on_target else "SHOT_OFF_TARGET",
                "is_home_team": s.is_home_team,
                "team_id": s.team_id,
                "player": None,
                "xg": round(s.xg, 2),
            }
        )
    order = {
        "GOAL": 0, "RED_CARD": 1, "YELLOW_CARD": 2, "SUBSTITUTION": 3,
        "SAVE": 4, "SHOT_ON_TARGET": 5, "SHOT_OFF_TARGET": 6,
    }
    events.sort(key=lambda e: (e["minute"], order.get(e["type"], 9)))
    return events
