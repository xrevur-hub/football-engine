"""
Session adapter — lottery-draft sessions and the role-fit projection.

Like `adapter.py`, this module computes no football. It holds in-memory draft
sessions and turns engine objects into JSON. Sessions live in a process-local
dict: fine for one person running the app locally, which is what this is for.
Anything multi-user would need real storage, and that is called out rather
than quietly assumed.
"""

from __future__ import annotations

import random
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from football_engine.api import adapter
from football_engine.api.adapter import AdapterError
from football_engine.draft.lottery import ClubReuse, DraftError, LotteryDraft, missing_roles
from football_engine.role_fit import (
    DEFAULT_ROLE_FIT_COEFFICIENTS,
    PositionStore,
    load_position_store,
)

_sessions: dict[str, "DraftSession"] = {}
_sessions_lock = threading.Lock()
_store: Optional[PositionStore] = None
_store_lock = threading.Lock()

MAX_SESSIONS = 64


def position_store() -> PositionStore:
    """Process-wide position/fit store, loaded once."""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = load_position_store(coeffs=DEFAULT_ROLE_FIT_COEFFICIENTS)
        return _store


def positions_for(player_id: str, role: str) -> list[str]:
    return position_store().for_player(player_id, role)


# ---------------------------------------------------------------------------
# Draft sessions
# ---------------------------------------------------------------------------


@dataclass
class DraftSession:
    session_id: str
    seed: int
    draft: LotteryDraft
    include_synthetic: bool = True
    history: list[dict] = field(default_factory=list)


def _clubs_for_draft(include_synthetic: bool) -> dict[str, tuple[str, list[str]]]:
    h = adapter.handles()
    clubs: dict[str, tuple[str, list[str]]] = {}
    for team in h.repos.teams.all(include_placeholder=False):
        if not include_synthetic and adapter._is_synthetic_team(team.id):
            continue
        roster = [pid for pid in team.roster]
        if roster:
            clubs[team.id] = (f"{team.club} {team.season}", roster)
    if not clubs:
        raise AdapterError("no clubs available for the draft with these settings")
    return clubs


def start_draft(
    seed: Optional[int] = None,
    reuse: str = "until_exhausted",
    include_synthetic: bool = True,
) -> dict:
    """Open a new lottery draft and draw the first club."""
    try:
        mode = ClubReuse(reuse)
    except ValueError as exc:
        raise AdapterError(f"unknown club reuse mode: {reuse!r}") from exc

    clubs = _clubs_for_draft(include_synthetic)
    if mode is ClubReuse.ONCE and len(clubs) < 11:
        raise AdapterError(
            f"one-player-per-club needs at least 11 clubs, only {len(clubs)} available"
        )

    actual_seed = int(seed) if seed is not None else random.randrange(1, 2**31)
    draft = LotteryDraft(clubs=clubs, rng=random.Random(actual_seed), reuse=mode)
    session = DraftSession(
        session_id=uuid.uuid4().hex[:12],
        seed=actual_seed,
        draft=draft,
        include_synthetic=include_synthetic,
    )

    with _sessions_lock:
        if len(_sessions) >= MAX_SESSIONS:
            for key in list(_sessions)[: len(_sessions) - MAX_SESSIONS + 1]:
                _sessions.pop(key, None)
        _sessions[session.session_id] = session

    draft.draw_club()
    return draft_state(session.session_id)


def _session(session_id: str) -> DraftSession:
    session = _sessions.get(session_id)
    if session is None:
        raise AdapterError("this draft session has expired - start a new draft")
    return session


def draft_state(session_id: str) -> dict:
    session = _session(session_id)
    draft = session.draft
    h = adapter.handles()

    state = draft.state()
    state["session_id"] = session.session_id
    state["seed"] = session.seed
    state["reuse"] = draft.reuse.value
    state["clubs_remaining"] = len(draft.available_clubs())

    if draft.current_club and not draft.complete:
        club_name, _ = draft.clubs[draft.current_club]
        state["drawn_club"] = {
            "id": draft.current_club,
            "name": club_name,
            "synthetic": adapter._is_synthetic_team(draft.current_club),
        }
        state["options"] = [_draft_player_dto(pid) for pid in draft.options()]
    else:
        state["drawn_club"] = None
        state["options"] = []

    squad_roles = []
    squad = []
    for pid in draft.squad():
        dto = _draft_player_dto(pid)
        squad.append(dto)
        squad_roles.append(dto["role"])
    state["squad_detail"] = squad
    state["missing_roles"] = missing_roles(squad_roles)

    for pick, dto in zip(state["picks"], squad):
        pick["player_name"] = dto["name"]
        pick["role"] = dto["role"]
    return state


def _draft_player_dto(player_id: str) -> dict:
    h = adapter.handles()
    from football_engine.data_layer.exceptions import UnknownReferenceError

    try:
        p = h.repos.players.get(player_id)
    except UnknownReferenceError as exc:
        raise AdapterError(f"unknown player id: {player_id!r}") from exc

    dto = adapter._player_dto(p)
    dto["positions"] = positions_for(p.id, p.role.value)
    return dto


def draw(session_id: str) -> dict:
    session = _session(session_id)
    try:
        session.draft.draw_club()
    except DraftError as exc:
        raise AdapterError(str(exc)) from exc
    return draft_state(session_id)


def pick(session_id: str, player_id: str) -> dict:
    session = _session(session_id)
    try:
        session.draft.pick(player_id)
        if not session.draft.complete:
            session.draft.draw_club()
    except DraftError as exc:
        raise AdapterError(str(exc)) from exc
    return draft_state(session_id)


def auto_pick(session_id: str) -> dict:
    """Skip the turn. Prefers whatever the squad is still missing."""
    session = _session(session_id)
    draft = session.draft
    h = adapter.handles()

    have = [h.repos.players.get(pid).role.value for pid in draft.squad()]
    gaps = missing_roles(have)
    prefer: list[str] = []
    for gap in gaps:
        prefer += {
            "GK": ["GK"],
            "defender": ["CB", "FB"],
            "midfielder": ["CM", "DM", "AM", "WM"],
            "forward": ["FW", "WM"],
        }[gap]

    roles_by_player = {}
    try:
        for pid in draft.options():
            roles_by_player[pid] = h.repos.players.get(pid).role.value
    except DraftError as exc:
        raise AdapterError(str(exc)) from exc

    try:
        draft.auto_pick(prefer_roles=prefer or None, roles_by_player=roles_by_player)
        if not draft.complete:
            draft.draw_club()
    except DraftError as exc:
        raise AdapterError(str(exc)) from exc
    return draft_state(session_id)


# ---------------------------------------------------------------------------
# Role fit projection
# ---------------------------------------------------------------------------


def annotate_placements(placements: list[dict]) -> list[dict]:
    """
    Add position set, natural/unnatural and the real fit factor to each
    placement in a squad-preview payload.
    """
    store = position_store()
    out = []
    for p in placements:
        info = store.explain(p["player_id"], p["draft_role"], p["assigned_role"])
        out.append({**p, **info, "role_fit_factor": info["fit_factor"]})
    return out


def fit_table_for_players(players) -> dict[tuple[str, str], float]:
    """The (draft_role, assigned_role) table handed to build_effective_xi."""
    return position_store().fit_table_for(players)


def role_fit_settings() -> dict:
    c = position_store().coeffs
    return {
        "k_distance": c.k_distance,
        "width_weight": c.width_weight,
        "floor": c.floor,
        "gk_penalty": c.gk_penalty,
        "calibrated": False,
        "note": (
            "Role-fit coefficients are stated priors, not calibrated values. "
            "They decide what playing out of position costs; changing them "
            "changes match outcomes."
        ),
    }
