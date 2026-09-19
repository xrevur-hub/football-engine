"""
Layer 4 — Probability Models (Dixon-Coles).

This package implements the probability layer that converts lambda (expected goals)
into scoreline probabilities and samples match outcomes.
"""

from __future__ import annotations

from football_engine.probability.dixon_coles import (
    DixonColesModel,
    ScorelineProbability,
    SegmentLambda,
    build_scoreline_distribution,
    create_dixon_coles_model,
    dixon_coles_correction,
    joint_probability,
    poisson_cdf,
    poisson_pmf,
    sample_goal_minute,
    sample_scoreline,
    scale_lambda_to_segment,
)

__all__ = [
    "DixonColesModel",
    "ScorelineProbability",
    "SegmentLambda",
    "build_scoreline_distribution",
    "create_dixon_coles_model",
    "dixon_coles_correction",
    "joint_probability",
    "poisson_cdf",
    "poisson_pmf",
    "sample_goal_minute",
    "sample_scoreline",
    "scale_lambda_to_segment",
]