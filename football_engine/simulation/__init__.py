"""
Layer 5 — Full Simulation Orchestration.

This package implements the match simulation loop that ties together
all previous layers into a complete match.
"""

from __future__ import annotations

from football_engine.simulation.match_orchestrator import MatchOrchestrator, create_match_orchestrator

__all__ = [
    "MatchOrchestrator",
    "create_match_orchestrator",
]