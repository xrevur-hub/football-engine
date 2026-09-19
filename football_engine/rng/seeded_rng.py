"""
SeededRNG — the engine's single source of randomness.

Architecture reference: Section N.5 (Reproducibility + Random Seed),
Section S.8 (RNG Order — Locked), Section P.5 (field ownership table:
"rng — هیچ‌کس — فقط .next() — call-only").

Hard rules encoded here:

  1. Every random draw anywhere in the engine MUST come from a single
     SeededRNG instance per match. No module may call `random.random()`,
     `numpy.random`, etc. directly — that would silently break replay.

  2. The *order* in which modules consume randomness is part of the
     reproducibility contract (S.8): "Same seed + Same module order +
     Same algorithm = Same simulation." This class does not enforce
     ordering itself (that's the orchestrator's job, Section S) — it
     only guarantees that a given sequence of calls against a given
     seed is always reproducible.

  3. `rng` is call-only for the rest of the engine per P.5: nobody but
     this class mutates its internal state.
"""

from __future__ import annotations

import random
from typing import Sequence, TypeVar

T = TypeVar("T")


class SeededRNG:
    """
    Thin, explicit wrapper around a PRNG instance.

    We deliberately wrap Python's `random.Random` rather than exposing it
    directly, so that:
      - call sites read as intent ("uniform", "poisson-ish draw", "choice")
        rather than raw `random.Random` API,
      - we have one place to swap the underlying generator later (e.g. for
        a numpy Generator) without touching call sites,
      - accidental use of the global `random` module elsewhere in the
        codebase is easy to grep for and flag in review.
    """

    __slots__ = ("_seed", "_generator")

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._generator = random.Random(seed)

    @property
    def seed(self) -> int:
        return self._seed

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        """Uniform(low, high) draw. Used for CDF sampling (Section 26.3)."""
        return self._generator.uniform(low, high)

    def bernoulli(self, p: float) -> bool:
        """Single Bernoulli(p) trial. Used throughout Q and R."""
        if not (0.0 <= p <= 1.0):
            raise ValueError(f"Bernoulli probability out of range: {p}")
        return self._generator.random() < p

    def poisson(self, lam: float) -> int:
        """
        Poisson(lam) draw via Knuth's algorithm.

        Used for e.g. Q.2 missed-shot generation. Kept dependency-free
        (no numpy requirement) since Layer 0 should not force a numpy
        dependency just for this.
        """
        if lam < 0:
            raise ValueError(f"Poisson lambda must be >= 0, got {lam}")
        if lam == 0:
            return 0
        import math

        l_threshold = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= self._generator.random()
            if p <= l_threshold:
                return k - 1

    def exponential(self, rate: float) -> float:
        """
        Exponential(rate) draw — natural complement to Poisson, used for
        first-goal-timing sampling (N.3 implementation note).
        """
        if rate <= 0:
            raise ValueError(f"Exponential rate must be > 0, got {rate}")
        return self._generator.expovariate(rate)

    def choice(self, population: Sequence[T]) -> T:
        """Uniform choice over a non-empty sequence."""
        if not population:
            raise ValueError("Cannot choose from an empty population")
        return self._generator.choice(list(population))

    def weighted_choice(self, population: Sequence[T], weights: Sequence[float]) -> T:
        """
        Weighted random choice (Section R.3/R.4 scorer/assist sampling,
        R.7 fallback = uniform random when all weights are zero).
        """
        if len(population) != len(weights):
            raise ValueError("population and weights must be the same length")
        if not population:
            raise ValueError("Cannot choose from an empty population")
        total = sum(weights)
        if total <= 0:
            # R.7 edge case: "All weights = 0 → fallback = uniform random"
            return self.choice(population)
        return self._generator.choices(list(population), weights=list(weights), k=1)[0]

    @staticmethod
    def derive_match_seed(
        home_team_id: str,
        away_team_id: str,
        match_date: str,
        match_id: str,
    ) -> int:
        """
        Deterministic seed derivation (N.5):
            seed = hash(team_a_id, team_b_id, match_date, match_id)

        Uses a stable hash (not Python's salted `hash()`, which varies
        across process runs) so that replay works across processes/machines.
        """
        import hashlib

        key = f"{home_team_id}|{away_team_id}|{match_date}|{match_id}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        # Truncate to a value that comfortably fits a 63-bit signed int.
        return int(digest[:16], 16)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"SeededRNG(seed={self._seed})"
