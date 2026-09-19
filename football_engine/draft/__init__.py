"""
Draft Engine — Snake, Auction, and Salary-Cap drafts.

Draftable entity is the PlayerSeason (season-specific). Uniqueness enforced:
a PlayerSeason can be drafted at most once. Pure data-driven, orchestration only.
"""

from __future__ import annotations

from football_engine.draft.engine import (
    DraftEngine,
    DraftFormat,
    DraftPick,
    DraftState,
    DraftTeam,
    create_draft_from_data,
    run_draft,
)

__all__ = [
    "DraftEngine",
    "DraftFormat",
    "DraftPick",
    "DraftState",
    "DraftTeam",
    "create_draft_from_data",
    "run_draft",
]
