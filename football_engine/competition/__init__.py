"""
Competition engine — UCL league phase + knockout simulation.

Uses the existing match engine for every fixture (identical user-vs-AI and
AI-vs-AI logic). Data-driven: teams loaded from normalized JSON.
"""

from __future__ import annotations

from football_engine.competition.ucl import (
    MatchLeg,
    MatchStage,
    UCLMatch,
    UCLRunner,
    UCLStanding,
    UCLTeamEntry,
    generate_league_phase_fixtures,
    run_ucl_season,
)
from football_engine.competition.synthetic_teams import SYNTHETIC_CLUBS, extend_dataset

__all__ = [
    "MatchLeg",
    "MatchStage",
    "UCLMatch",
    "UCLRunner",
    "UCLStanding",
    "UCLTeamEntry",
    "generate_league_phase_fixtures",
    "run_ucl_season",
    "SYNTHETIC_CLUBS",
    "extend_dataset",
]
