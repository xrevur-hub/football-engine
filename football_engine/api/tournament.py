"""
Tournament sessions — the user's drafted team enters the UCL competition.

Integration path, exactly as specified:

    user draft -> Effective XI -> User Team representation -> UCL Tournament
    -> match simulation adapter -> existing MatchOrchestrator -> real result

Concretely:

    adapter.build_user_team(placements)   # unchanged, existing function
        -> EffectiveXiPlayer list + Formation   (the user's real XI + shape)
    ExternalRoster(formation, players)          (typed DTO, this module)
    UCLRunner.register_external_roster(id, ExternalRoster)   (ucl.py, new hook)
    UCLRunner.run_full_season([...36 ids including the user's...])  (unchanged)

No football math lives here. This module's only job is: take what
`build_user_team` already computed, wrap it in the typed boundary
`ucl.ExternalRoster` expects, and hand a plain list of team_id strings to
`UCLRunner` — the same shape it always consumed.

DATA LIMITATION, stated rather than hidden: the catalog has exactly 36 team
slots, so the user's team is exchanged for the weakest currently-present
participant (the synthetic template block, never a real historical team) to
keep the field at 36. If a real 37th+ club is added to the dataset later,
this drop step should become unnecessary and can be removed.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from football_engine.api import adapter
from football_engine.api.adapter import AdapterError

USER_TEAM_ID = "your_xi"
_tournaments: dict[str, "TournamentSession"] = {}
_lock = threading.Lock()
MAX_TOURNAMENTS = 16


@dataclass
class TournamentSession:
    session_id: str
    seed: int
    result: dict
    user_team_id: str
    dropped_team_id: Optional[str]
    placements: list[dict]


def _pick_dropped_team(h) -> str:
    """
    The catalog participant removed to make room for the user.

    Always a synthetic template club (id ending `_2015_16`), never one of
    the two real historical teams (Barcelona 2010/11, Chelsea 2011/12).
    Picking the lexicographically last synthetic id keeps this
    deterministic given a fixed dataset, independent of dict ordering.
    """
    synthetic = sorted(
        t.id for t in h.repos.teams.all(include_placeholder=False)
        if adapter._is_synthetic_team(t.id)
    )
    if not synthetic:
        raise AdapterError(
            "no synthetic template club available to drop — the catalog has "
            "no spare slot for the user's team without removing a real "
            "historical club, which this adapter refuses to do silently"
        )
    return synthetic[-1]


def start_tournament(placements: list[dict], seed: Optional[int] = None) -> dict:
    """
    Build the user's Effective XI, register it as a UCL participant in place
    of one synthetic club, and run the full competition.

    Returns the same dict `UCLRunner.run_full_season` returns, plus a
    `session` block identifying this run and what was substituted.
    """
    import random as _random

    from football_engine.competition.ucl import ExternalRoster, UCLRunner

    h = adapter.handles()

    # This IS the existing pipeline: build_user_team already runs
    # normalize_placements -> build_formation -> build_effective_xi (with the
    # real role-fit table) -> TeamModelBuilder.build. We reuse its engine
    # objects directly rather than recomputing anything.
    built = adapter.build_user_team(placements)
    formation = built["engine"]["formation"]
    effective_xi = built["engine"]["effective_xi"]

    dropped_id = _pick_dropped_team(h)
    team_ids = [
        t.id for t in h.repos.teams.all(include_placeholder=False)
        if t.id != dropped_id
    ]
    team_ids.append(USER_TEAM_ID)
    if len(team_ids) != 36:
        raise AdapterError(
            f"expected exactly 36 tournament participants after substitution, got {len(team_ids)}"
        )

    actual_seed = int(seed) if seed is not None else _random.randrange(1, 2**31)
    runner = UCLRunner(data_dir=adapter.DATA_DIR, seed=actual_seed)
    runner.register_external_roster(
        USER_TEAM_ID,
        ExternalRoster(formation=formation, players=effective_xi, historical_prior=None),
    )

    result = runner.run_full_season(team_ids)
    result["session"] = {
        "session_id": uuid.uuid4().hex[:12],
        "seed": actual_seed,
        "user_team_id": USER_TEAM_ID,
        "dropped_team_id": dropped_id,
        "user_shape": built["dto"]["shape"],
    }
    result["user_result"] = _extract_user_journey(result)

    session = TournamentSession(
        session_id=result["session"]["session_id"],
        seed=actual_seed,
        result=result,
        user_team_id=USER_TEAM_ID,
        dropped_team_id=dropped_id,
        placements=placements,
    )
    with _lock:
        if len(_tournaments) >= MAX_TOURNAMENTS:
            for key in list(_tournaments)[: len(_tournaments) - MAX_TOURNAMENTS + 1]:
                _tournaments.pop(key, None)
        _tournaments[session.session_id] = session

    return result


def _extract_user_journey(result: dict) -> dict:
    """Where the user's team actually finished, read off the real result —
    not inferred or re-simulated."""
    standing = next(
        (s for s in result["standings"] if s["team"] == USER_TEAM_ID), None
    )
    stage_reached = "league_phase"
    eliminated_in = None

    if USER_TEAM_ID in result.get("r16_direct", []) or USER_TEAM_ID in result.get("playoff_winners", []):
        stage_reached = "round_of_16"
    if USER_TEAM_ID in result.get("quarter_finalists", []):
        stage_reached = "quarter_final"
    if USER_TEAM_ID in result.get("semi_finalists", []):
        stage_reached = "semi_final"
    if result["final"]["home"] == USER_TEAM_ID or result["final"]["away"] == USER_TEAM_ID:
        stage_reached = "final"
    if result["champion"] == USER_TEAM_ID:
        stage_reached = "champion"

    for stage_key in ("playoff_ties", "r16_ties", "qf_ties", "sf_ties"):
        for tie in result.get(stage_key, []):
            if USER_TEAM_ID in (tie["home"], tie["away"]) and tie["winner"] != USER_TEAM_ID:
                eliminated_in = stage_key.replace("_ties", "")

    return {
        "league_standing": standing,
        "stage_reached": stage_reached,
        "eliminated_in": eliminated_in,
        "champion": result["champion"] == USER_TEAM_ID,
    }


def get_tournament(session_id: str) -> dict:
    with _lock:
        session = _tournaments.get(session_id)
    if session is None:
        raise AdapterError("this tournament session has expired — start a new tournament")
    return session.result
