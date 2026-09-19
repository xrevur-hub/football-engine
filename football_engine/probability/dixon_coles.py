"""
Layer 4 — Dixon-Coles Probability Model.

This module implements the Dixon-Coles adjusted Poisson model for football
scoreline probabilities. It is the probability layer that sits between
lambda (expected goals) and match simulation.

Architecture:
    λ (from Layer 3) → Poisson PMF → Dixon-Coles correction → P(X=x, Y=y) → Sampling

Key properties:
- λ is generated BEFORE this layer (Layer 3)
- No randomness in probability computation (deterministic given λ)
- Randomness only enters at sampling step (via SeededRNG)
- Reproducible given same seed and λ
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from football_engine.rng.seeded_rng import SeededRNG
from football_engine.matchup._validation import finite_number, nonnegative
from football_engine.core.parameters import ParameterSet


# =============================================================================
# Core Probability Functions
# =============================================================================


def poisson_pmf(k: int, lam: float) -> float:
    """
    Poisson probability mass function: P(X=k) = (λ^k * e^(-λ)) / k!

    Uses log-space computation for numerical stability.
    """
    lam = nonnegative("lambda", lam)
    if k < 0:
        return 0.0
    if lam == 0.0:
        return 1.0 if k == 0 else 0.0

    # log P = k * log(λ) - λ - log(k!)
    log_p = k * math.log(lam) - lam - math.lgamma(k + 1)
    return math.exp(log_p)


def poisson_cdf(k: int, lam: float) -> float:
    """Poisson cumulative distribution function: P(X <= k)."""
    lam = nonnegative("lambda", lam)
    if k < 0:
        return 0.0
    total = 0.0
    for i in range(k + 1):
        total += poisson_pmf(i, lam)
    return min(1.0, total)


def dixon_coles_correction(
    home_goals: int,
    away_goals: int,
    lambda_home: float,
    lambda_away: float,
    rho: float,
) -> float:
    """
    Dixon-Coles low-score correction factor.

    The correction adjusts the independent Poisson probabilities for the
    low-score cells (0-0, 1-0, 0-1, 1-1) to account for the empirical
    excess of draws and low-scoring matches in football.

    Correction factor τ(x, y; λ, μ, ρ):
    - τ(0,0) = 1 - λ*μ*ρ
    - τ(1,0) = 1 + λ*ρ
    - τ(0,1) = 1 + μ*ρ
    - τ(1,1) = 1 - ρ
    - τ(x,y) = 1 for all other (x,y)

    Where λ = lambda_home, μ = lambda_away, ρ = rho parameter (typically negative).
    """
    lambda_home = nonnegative("lambda_home", lambda_home)
    lambda_away = nonnegative("lambda_away", lambda_away)
    rho = finite_number("rho", rho)

    if home_goals == 0 and away_goals == 0:
        return 1.0 - lambda_home * lambda_away * rho
    elif home_goals == 1 and away_goals == 0:
        return 1.0 + lambda_home * rho
    elif home_goals == 0 and away_goals == 1:
        return 1.0 + lambda_away * rho
    elif home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    else:
        return 1.0


def joint_probability(
    home_goals: int,
    away_goals: int,
    lambda_home: float,
    lambda_away: float,
    rho: float,
) -> float:
    """
    Joint probability P(X=x, Y=y) under Dixon-Coles model.

    P(x,y) = Poisson(x|λ) * Poisson(y|μ) * τ(x,y; λ,μ,ρ)
    """
    lambda_home = nonnegative("lambda_home", lambda_home)
    lambda_away = nonnegative("lambda_away", lambda_away)

    p_home = poisson_pmf(home_goals, lambda_home)
    p_away = poisson_pmf(away_goals, lambda_away)
    tau = dixon_coles_correction(home_goals, away_goals, lambda_home, lambda_away, rho)

    prob = p_home * p_away * tau
    return max(0.0, prob)  # Guard against numerical issues


# =============================================================================
# Scoreline Distribution
# =============================================================================


@dataclass(frozen=True)
class ScorelineProbability:
    """A single scoreline with its probability."""
    home_goals: int
    away_goals: int
    probability: float


def build_scoreline_distribution(
    lambda_home: float,
    lambda_away: float,
    rho: float,
    max_goals: int = 10,
) -> list[ScorelineProbability]:
    """
    Build the full discrete probability distribution over scorelines.

    Returns list of ScorelineProbability sorted by probability descending.
    Distribution is normalized to sum to 1.0.
    """
    lambda_home = nonnegative("lambda_home", lambda_home)
    lambda_away = nonnegative("lambda_away", lambda_away)
    rho = finite_number("rho", rho)
    if max_goals < 0:
        raise ValueError("max_goals must be >= 0")

    scorelines = []
    total_prob = 0.0

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob = joint_probability(h, a, lambda_home, lambda_away, rho)
            if prob > 0:
                scorelines.append(ScorelineProbability(h, a, prob))
                total_prob += prob

    # Normalize
    if total_prob > 0:
        scorelines = [
            ScorelineProbability(s.home_goals, s.away_goals, s.probability / total_prob)
            for s in scorelines
        ]

    # Sort by probability descending
    scorelines.sort(key=lambda s: s.probability, reverse=True)
    return scorelines


# =============================================================================
# Sampling
# =============================================================================


def sample_scoreline(
    rng: SeededRNG,
    lambda_home: float,
    lambda_away: float,
    rho: float,
    max_goals: int = 10,
) -> tuple[int, int]:
    """
    Sample a scoreline from the Dixon-Coles distribution.

    Returns (home_goals, away_goals).
    Uses inverse transform sampling on the CDF.
    """
    lambda_home = nonnegative("lambda_home", lambda_home)
    lambda_away = nonnegative("lambda_away", lambda_away)
    rho = finite_number("rho", rho)

    # Build CDF
    cdf = []
    cumsum = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob = joint_probability(h, a, lambda_home, lambda_away, rho)
            if prob > 0:
                cumsum += prob
                cdf.append(((h, a), cumsum))

    # Normalize CDF
    if cumsum > 0:
        cdf = [((h, a), p / cumsum) for (h, a), p in cdf]

    # Sample
    u = rng.uniform(0.0, 1.0)
    for (h, a), p in cdf:
        if u <= p:
            return h, a

    # Fallback (should never reach here with proper normalization)
    return cdf[-1][0]


def sample_goal_minute(
    rng: SeededRNG,
    segment_start: int,
    segment_end: int,
    total_goals: int,
) -> int | None:
    """
    Sample the minute of the first goal in a segment.

    Uses exponential distribution for inter-arrival times.
    Returns None if no goals in segment.
    """
    if total_goals <= 0:
        return None

    segment_duration = segment_end - segment_start
    if segment_duration <= 0:
        return segment_start

    # Rate = goals per minute
    rate = total_goals / segment_duration
    if rate <= 0:
        return segment_start + segment_duration // 2

    # Sample time of first goal using exponential distribution
    # Time until first event in Poisson process with rate
    time_to_first = rng.exponential(rate)
    minute = segment_start + int(time_to_first)

    # Clamp to segment
    if minute >= segment_end:
        minute = segment_end - 1
    if minute < segment_start:
        minute = segment_start

    return minute


# =============================================================================
# Segment-level probability (for discrete-time simulation)
# =============================================================================


@dataclass(frozen=True)
class SegmentLambda:
    """Lambda values for a single segment (duration-adjusted)."""
    lambda_home: float
    lambda_away: float
    duration_minutes: int


def scale_lambda_to_segment(
    lambda_home_90: float,
    lambda_away_90: float,
    segment_duration_minutes: int,
) -> SegmentLambda:
    """
    Scale 90-minute lambda to a segment duration.

    Assumes constant scoring rate (homogeneous Poisson process).
    """
    lambda_home_90 = nonnegative("lambda_home_90", lambda_home_90)
    lambda_away_90 = nonnegative("lambda_away_90", lambda_away_90)
    if segment_duration_minutes <= 0:
        raise ValueError("segment_duration_minutes must be > 0")

    scale = segment_duration_minutes / 90.0
    return SegmentLambda(
        lambda_home=lambda_home_90 * scale,
        lambda_away=lambda_away_90 * scale,
        duration_minutes=segment_duration_minutes,
    )


# =============================================================================
# DixonColesModel - main interface
# =============================================================================


@dataclass(frozen=True)
class DixonColesModel:
    """
    Main interface for Dixon-Coles probability model.

    Encapsulates parameters and provides methods for probability computation
    and sampling.
    """
    parameters: ParameterSet
    max_goals: int = 10

    def joint_probability(self, home_goals: int, away_goals: int,
                          lambda_home: float, lambda_away: float) -> float:
        """Joint probability for a specific scoreline."""
        return joint_probability(
            home_goals, away_goals,
            lambda_home, lambda_away,
            self.parameters.rho,
        )

    def scoreline_distribution(self, lambda_home: float, lambda_away: float) -> list[ScorelineProbability]:
        """Full scoreline distribution."""
        return build_scoreline_distribution(
            lambda_home, lambda_away, self.parameters.rho, self.max_goals
        )

    def sample(self, rng: SeededRNG, lambda_home: float, lambda_away: float) -> tuple[int, int]:
        """Sample a scoreline."""
        return sample_scoreline(
            rng, lambda_home, lambda_away, self.parameters.rho, self.max_goals
        )

    def expected_goals(self, lambda_home: float, lambda_away: float) -> tuple[float, float]:
        """Expected goals under Dixon-Coles (approximately equal to λ for small ρ)."""
        # For small |ρ|, E[X] ≈ λ, E[Y] ≈ μ
        # Exact computation would require summing over distribution
        return lambda_home, lambda_away

    def variance(self, lambda_home: float, lambda_away: float) -> tuple[float, float]:
        """Approximate variance (Poisson variance = λ, DC adds small correction)."""
        return lambda_home, lambda_away


def create_dixon_coles_model(parameters: ParameterSet | None = None, max_goals: int = 10) -> DixonColesModel:
    """Factory function to create a DixonColesModel."""
    from football_engine.core.parameters import DEFAULT_PARAMETER_SET
    return DixonColesModel(parameters or DEFAULT_PARAMETER_SET, max_goals)