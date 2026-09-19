"""Explicit unresolved possession-data dependency; no estimator or default."""
from __future__ import annotations

from typing import Protocol


class PossessionTendencySource(Protocol):
    """Preloaded, deterministic source of a roster's PRE-PRIOR tendency index.

    Return a finite [0,1] value for the exact player-season IDs supplied.
    This is not the opponent-dependent PossessionShare and not a historical
    prior passed through again. No default value or production implementation
    is provided. Missing observations must raise, never fall back to 0.5.

    Callers must establish data provenance, avoid outcome leakage and rejected
    ability/press/geometry proxies, and perform all I/O before engine use.
    The ID-only immutable argument restricts this engine's data flow; a Protocol
    cannot certify arbitrary caller implementations as pure or causally safe.
    """

    def __call__(self, *, player_season_ids: tuple[str, ...]) -> float:
        ...
