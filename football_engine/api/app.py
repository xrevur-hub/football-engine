"""
FastAPI application — the HTTP surface of the engine.

This module owns request/response shapes and error mapping only. Every call is
delegated to `football_engine.api.adapter`, which is the one place allowed to
touch engine internals. No football mathematics lives in this file or anywhere
in the web layer.

Run it with:

    pip install -r requirements-api.txt
    uvicorn football_engine.api.app:app --reload

then open http://127.0.0.1:8000/
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from football_engine.api import adapter, sessions, tournament
from football_engine.api.adapter import AdapterError

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(
    title="Football Engine API",
    version="0.1.0",
    description="Thin HTTP adapter over the existing simulation engine.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------


class Placement(BaseModel):
    player_id: str
    col: int = Field(..., ge=0, le=6)
    row: int = Field(..., ge=0, le=7)


class SquadPreviewRequest(BaseModel):
    placements: list[Placement] = Field(..., min_length=11, max_length=11)


class StartDraftRequest(BaseModel):
    seed: int | None = None
    reuse: str = "until_exhausted"
    include_synthetic: bool = True


class PickRequest(BaseModel):
    session_id: str
    player_id: str | None = None


class SimulateRequest(BaseModel):
    placements: list[Placement] = Field(..., min_length=11, max_length=11)
    opponent_team_id: str
    user_is_home: bool = True
    seed: int | None = None
    match_id: str = "web_match"


class StartTournamentRequest(BaseModel):
    placements: list[Placement] = Field(..., min_length=11, max_length=11)
    seed: int | None = None


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@app.exception_handler(AdapterError)
async def _adapter_error_handler(_request, exc: AdapterError):  # pragma: no cover
    raise HTTPException(status_code=422, detail=str(exc))


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AdapterError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    """Loads the dataset; a 200 here means the engine is importable and fed."""
    try:
        h = adapter.handles()
    except Exception as exc:  # noqa: BLE001 - surfaced verbatim for setup debugging
        raise HTTPException(status_code=503, detail=f"engine not ready: {exc}") from exc
    return {
        "status": "ok",
        "players": len(h.repos.players.all(include_placeholder=False)),
        "teams": len(h.repos.teams.all(include_placeholder=False)),
        "formations": len(h.repos.formations.all()),
    }


@app.get("/api/capabilities")
def capabilities() -> dict:
    return adapter.engine_capabilities()


@app.get("/api/players")
def players() -> list[dict]:
    return _guard(adapter.list_players)


@app.get("/api/teams")
def teams() -> list[dict]:
    return _guard(adapter.list_teams)


@app.get("/api/formations")
def formations() -> list[dict]:
    return _guard(adapter.list_formation_presets)


@app.get("/api/teams/{team_id}/model")
def team_model(team_id: str, formation: str | None = None) -> dict:
    """Build a curated TeamSeason's model so the preview can compare sides."""
    return _guard(adapter.build_catalog_team, team_id, formation)["dto"]


@app.get("/api/role-fit")
def role_fit() -> dict:
    """The role-fit coefficients, flagged as uncalibrated priors."""
    return _guard(sessions.role_fit_settings)


@app.post("/api/draft/start")
def draft_start(req: StartDraftRequest) -> dict:
    return _guard(sessions.start_draft, req.seed, req.reuse, req.include_synthetic)


@app.get("/api/draft/{session_id}")
def draft_get(session_id: str) -> dict:
    return _guard(sessions.draft_state, session_id)


@app.post("/api/draft/draw")
def draft_draw(req: PickRequest) -> dict:
    return _guard(sessions.draw, req.session_id)


@app.post("/api/draft/pick")
def draft_pick(req: PickRequest) -> dict:
    if not req.player_id:
        raise HTTPException(status_code=422, detail="player_id is required")
    return _guard(sessions.pick, req.session_id, req.player_id)


@app.post("/api/draft/auto")
def draft_auto(req: PickRequest) -> dict:
    return _guard(sessions.auto_pick, req.session_id)


@app.post("/api/squad/preview")
def squad_preview(req: SquadPreviewRequest) -> dict:
    result = _guard(adapter.build_user_team, [p.model_dump() for p in req.placements])
    return result["dto"]


@app.post("/api/match/simulate")
def simulate(req: SimulateRequest) -> dict:
    return _guard(
        adapter.simulate_match,
        [p.model_dump() for p in req.placements],
        req.opponent_team_id,
        user_is_home=req.user_is_home,
        seed=req.seed,
        match_id=req.match_id,
    )


@app.post("/api/tournament/start")
def tournament_start(req: StartTournamentRequest) -> dict:
    """
    Run a full 36-team UCL season with the user's drafted, freely placed XI
    as one of the participants. This can take several seconds (36 league
    matches + knockouts, each through the real MatchOrchestrator) — it is
    synchronous by design so the response is the complete, real result.
    """
    return _guard(
        tournament.start_tournament,
        [p.model_dump() for p in req.placements],
        req.seed,
    )


@app.get("/api/tournament/{session_id}")
def tournament_get(session_id: str) -> dict:
    return _guard(tournament.get_tournament, session_id)


# --------------------------------------------------------------------------
# Static frontend
# --------------------------------------------------------------------------

if WEB_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
