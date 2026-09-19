"""Tests for Layer 4 Dixon-Coles Probability Model."""

import pytest
import math

from football_engine.core.parameters import ParameterSet
from football_engine.probability.dixon_coles import (
    poisson_pmf,
    poisson_cdf,
    dixon_coles_correction,
    joint_probability,
    build_scoreline_distribution,
    sample_scoreline,
    sample_goal_minute,
    scale_lambda_to_segment,
    SegmentLambda,
    DixonColesModel,
    create_dixon_coles_model,
)
from football_engine.rng.seeded_rng import SeededRNG


class TestPoissonPMF:
    """Test Poisson probability mass function."""

    def test_pmf_basic(self):
        # P(X=0 | λ=1) = e^(-1) ≈ 0.3679
        assert poisson_pmf(0, 1.0) == pytest.approx(math.exp(-1.0))

        # P(X=1 | λ=1) = e^(-1) ≈ 0.3679
        assert poisson_pmf(1, 1.0) == pytest.approx(math.exp(-1.0))

        # P(X=2 | λ=1) = e^(-1)/2 ≈ 0.1839
        assert poisson_pmf(2, 1.0) == pytest.approx(math.exp(-1.0) / 2.0)

    def test_pmf_zero_lambda(self):
        assert poisson_pmf(0, 0.0) == 1.0
        assert poisson_pmf(1, 0.0) == 0.0
        assert poisson_pmf(5, 0.0) == 0.0

    def test_pmf_negative_k(self):
        assert poisson_pmf(-1, 1.0) == 0.0
        assert poisson_pmf(-5, 1.0) == 0.0

    def test_pmf_sums_to_one(self):
        # Sum over all k should approach 1
        total = sum(poisson_pmf(k, 2.5) for k in range(0, 50))
        assert total == pytest.approx(1.0, abs=1e-10)

    def test_pmf_numerical_stability(self):
        # Large lambda should not overflow
        assert poisson_pmf(100, 100.0) > 0
        assert math.isfinite(poisson_pmf(100, 100.0))


class TestPoissonCDF:
    """Test Poisson cumulative distribution function."""

    def test_cdf_basic(self):
        # P(X <= 0 | λ=1) = P(X=0) = e^(-1)
        assert poisson_cdf(0, 1.0) == pytest.approx(math.exp(-1.0))

        # P(X <= 1 | λ=1) = P(X=0) + P(X=1) = 2*e^(-1)
        assert poisson_cdf(1, 1.0) == pytest.approx(2 * math.exp(-1.0))

    def test_cdf_monotonic(self):
        lam = 2.5
        prev = 0.0
        for k in range(0, 20):
            cdf = poisson_cdf(k, lam)
            assert cdf >= prev - 1e-10
            prev = cdf

    def test_cdf_approaches_one(self):
        assert poisson_cdf(50, 2.5) == pytest.approx(1.0, abs=1e-10)


class TestDixonColesCorrection:
    """Test Dixon-Coles low-score correction factor."""

    def test_correction_00(self):
        # τ(0,0) = 1 - λ*μ*ρ
        lam, mu, rho = 1.5, 1.2, -0.13
        expected = 1.0 - lam * mu * rho
        assert dixon_coles_correction(0, 0, lam, mu, rho) == pytest.approx(expected)

    def test_correction_10(self):
        # τ(1,0) = 1 + λ*ρ
        lam, mu, rho = 1.5, 1.2, -0.13
        expected = 1.0 + lam * rho
        assert dixon_coles_correction(1, 0, lam, mu, rho) == pytest.approx(expected)

    def test_correction_01(self):
        # τ(0,1) = 1 + μ*ρ
        lam, mu, rho = 1.5, 1.2, -0.13
        expected = 1.0 + mu * rho
        assert dixon_coles_correction(0, 1, lam, mu, rho) == pytest.approx(expected)

    def test_correction_11(self):
        # τ(1,1) = 1 - ρ
        lam, mu, rho = 1.5, 1.2, -0.13
        expected = 1.0 - rho
        assert dixon_coles_correction(1, 1, lam, mu, rho) == pytest.approx(expected)

    def test_correction_other_scores(self):
        # τ(x,y) = 1 for all other scores
        lam, mu, rho = 1.5, 1.2, -0.13
        assert dixon_coles_correction(2, 0, lam, mu, rho) == 1.0
        assert dixon_coles_correction(0, 2, lam, mu, rho) == 1.0
        assert dixon_coles_correction(2, 2, lam, mu, rho) == 1.0
        assert dixon_coles_correction(3, 1, lam, mu, rho) == 1.0

    def test_rho_zero_is_no_correction(self):
        # ρ=0 should give τ=1 everywhere (independent Poisson)
        lam, mu, rho = 1.5, 1.2, 0.0
        assert dixon_coles_correction(0, 0, lam, mu, rho) == 1.0
        assert dixon_coles_correction(1, 0, lam, mu, rho) == 1.0
        assert dixon_coles_correction(0, 1, lam, mu, rho) == 1.0
        assert dixon_coles_correction(1, 1, lam, mu, rho) == 1.0


class TestJointProbability:
    """Test joint probability P(X=x, Y=y)."""

    def test_probability_nonnegative(self):
        for h in range(5):
            for a in range(5):
                prob = joint_probability(h, a, 1.5, 1.2, -0.13)
                assert prob >= 0.0

    def test_probability_sums_to_one(self):
        # Sum over reasonable grid should approach 1
        # Note: truncation at max_goals=10 loses some probability mass
        total = 0.0
        for h in range(10):
            for a in range(10):
                total += joint_probability(h, a, 1.5, 1.2, -0.13)
        # With max_goals=10 and lambda~1.5, we capture ~99.9% of mass
        assert total == pytest.approx(1.0, abs=1e-3)

    def test_rho_zero_is_independent_poisson(self):
        lam, mu = 1.5, 1.2
        for h in range(5):
            for a in range(5):
                dc_prob = joint_probability(h, a, lam, mu, 0.0)
                poisson_prob = poisson_pmf(h, lam) * poisson_pmf(a, mu)
                assert dc_prob == pytest.approx(poisson_prob, rel=1e-10)

    def test_known_values(self):
        # With λ=1.3, μ=1.1, ρ=-0.13, the 0-0 probability should be > independent Poisson
        lam, mu, rho = 1.3, 1.1, -0.13
        p_00_dc = joint_probability(0, 0, lam, mu, rho)
        p_00_poisson = poisson_pmf(0, lam) * poisson_pmf(0, mu)
        # DC correction for 0-0 is 1 - λ*μ*ρ = 1 - 1.3*1.1*(-0.13) = 1 + 0.1859 = 1.1859
        # So DC probability should be ~18.6% higher than independent Poisson
        assert p_00_dc > p_00_poisson


class TestScorelineDistribution:
    """Test full scoreline distribution building."""

    def test_distribution_sums_to_one(self):
        dist = build_scoreline_distribution(1.5, 1.2, -0.13, max_goals=8)
        total = sum(s.probability for s in dist)
        # Normalization happens after truncation, so should sum to ~1
        assert total == pytest.approx(1.0, abs=1e-3)

    def test_distribution_sorted_descending(self):
        dist = build_scoreline_distribution(1.5, 1.2, -0.13, max_goals=8)
        probs = [s.probability for s in dist]
        assert probs == sorted(probs, reverse=True)

    def test_distribution_contains_most_likely(self):
        dist = build_scoreline_distribution(1.5, 1.2, -0.13, max_goals=8)
        # Most likely scores should be present
        scores = [(s.home_goals, s.away_goals) for s in dist]
        assert (1, 1) in scores or (1, 0) in scores or (0, 1) in scores

    def test_max_goals_parameter(self):
        dist8 = build_scoreline_distribution(3.0, 2.5, -0.13, max_goals=8)
        dist10 = build_scoreline_distribution(3.0, 2.5, -0.13, max_goals=10)
        # With higher max_goals, distribution should be more complete
        total8 = sum(s.probability for s in dist8)
        total10 = sum(s.probability for s in dist10)
        assert total10 >= total8


class TestSampling:
    """Test scoreline sampling."""

    def test_sample_returns_valid_scores(self):
        rng = SeededRNG(12345)
        for _ in range(100):
            h, a = sample_scoreline(rng, 1.5, 1.2, -0.13, max_goals=8)
            assert 0 <= h <= 8
            assert 0 <= a <= 8

    def test_sample_deterministic_with_same_seed(self):
        rng1 = SeededRNG(12345)
        rng2 = SeededRNG(12345)
        samples1 = [sample_scoreline(rng1, 1.5, 1.2, -0.13) for _ in range(20)]
        samples2 = [sample_scoreline(rng2, 1.5, 1.2, -0.13) for _ in range(20)]
        assert samples1 == samples2

    def test_different_seeds_different_sequences(self):
        rng1 = SeededRNG(12345)
        rng2 = SeededRNG(54321)
        samples1 = [sample_scoreline(rng1, 1.5, 1.2, -0.13) for _ in range(20)]
        samples2 = [sample_scoreline(rng2, 1.5, 1.2, -0.13) for _ in range(20)]
        # Very unlikely to be identical
        assert samples1 != samples2

    def test_sample_distribution_matches_theory(self):
        # Large sample should approximate theoretical distribution
        rng = SeededRNG(99999)
        N = 50000
        counts = {}
        for _ in range(N):
            h, a = sample_scoreline(rng, 1.5, 1.2, -0.13, max_goals=6)
            counts[(h, a)] = counts.get((h, a), 0) + 1

        dist = build_scoreline_distribution(1.5, 1.2, -0.13, max_goals=6)
        # Check a few common scores
        for s in dist[:5]:
            if s.probability > 0.01:
                empirical = counts.get((s.home_goals, s.away_goals), 0) / N
                assert empirical == pytest.approx(s.probability, abs=0.01)


class TestGoalMinuteSampling:
    """Test goal minute sampling within segments."""

    def test_no_goals_returns_none(self):
        rng = SeededRNG(12345)
        assert sample_goal_minute(rng, 0, 30, 0) is None
        assert sample_goal_minute(rng, 30, 60, 0) is None

    def test_goal_minute_in_segment(self):
        rng = SeededRNG(12345)
        for _ in range(100):
            minute = sample_goal_minute(rng, 0, 30, 1)
            assert 0 <= minute < 30

        for _ in range(100):
            minute = sample_goal_minute(rng, 30, 60, 1)
            assert 30 <= minute < 60

    def test_multiple_goals_returns_first(self):
        rng = SeededRNG(12345)
        for _ in range(100):
            minute = sample_goal_minute(rng, 0, 30, 3)
            assert 0 <= minute < 30


class TestLambdaScaling:
    """Test lambda scaling to segment duration."""

    def test_scale_to_segment(self):
        seg = scale_lambda_to_segment(1.8, 1.2, 30)
        assert seg.duration_minutes == 30
        assert seg.lambda_home == pytest.approx(1.8 * 30 / 90)
        assert seg.lambda_away == pytest.approx(1.2 * 30 / 90)

    def test_scale_to_different_segments(self):
        s1 = scale_lambda_to_segment(1.8, 1.2, 30)  # 0-30
        s2 = scale_lambda_to_segment(1.8, 1.2, 30)  # 30-60
        s3 = scale_lambda_to_segment(1.8, 1.2, 15)  # 60-75
        s4 = scale_lambda_to_segment(1.8, 1.2, 15)  # 75-90
        assert s1.lambda_home == s2.lambda_home
        assert s3.lambda_home == s4.lambda_home
        assert s1.lambda_home == pytest.approx(2 * s3.lambda_home)


class TestDixonColesModel:
    """Test DixonColesModel class interface."""

    def test_model_creation(self):
        model = create_dixon_coles_model()
        assert isinstance(model, DixonColesModel)
        assert model.max_goals == 10

    def test_model_with_custom_params(self):
        params = ParameterSet(rho=-0.20, max_goals=8)
        model = create_dixon_coles_model(params, max_goals=8)
        assert model.parameters.rho == -0.20
        assert model.max_goals == 8

    def test_model_joint_probability(self):
        model = create_dixon_coles_model(ParameterSet(rho=-0.13))
        prob = model.joint_probability(1, 0, 1.5, 1.2)
        expected = joint_probability(1, 0, 1.5, 1.2, -0.13)
        assert prob == pytest.approx(expected)

    def test_model_sample(self):
        rng = SeededRNG(12345)
        model = create_dixon_coles_model()
        h, a = model.sample(rng, 1.5, 1.2)
        assert 0 <= h <= 10
        assert 0 <= a <= 10

    def test_model_scoreline_distribution(self):
        model = create_dixon_coles_model()
        dist = model.scoreline_distribution(1.5, 1.2)
        total = sum(s.probability for s in dist)
        # Normalization happens after truncation
        assert total == pytest.approx(1.0, abs=1e-3)


class TestNumericalProperties:
    """Test numerical properties of the model."""

    def test_probability_conservation(self):
        """Total probability should be 1 for various lambda values."""
        # For higher lambdas, need more goals to capture full mass
        # The distribution is normalized after truncation, so it sums to 1.0 within
        # the truncated space. The test checks that normalization works correctly.
        test_cases = [
            (0.5, 0.5, 8, 1e-6),
            (1.0, 1.0, 10, 1e-6),
            (2.0, 1.5, 12, 1e-6),
            (3.0, 0.8, 15, 1e-6),  # Normalization should work regardless
            (0.1, 0.1, 6, 1e-6),
        ]
        for lam_h, lam_a, max_g, tol in test_cases:
            dist = build_scoreline_distribution(lam_h, lam_a, -0.13, max_goals=max_g)
            total = sum(s.probability for s in dist)
            # Normalization after truncation should produce exactly 1.0
            assert total == pytest.approx(1.0, abs=tol), f"Failed for λ=({lam_h},{lam_a})"

    def test_low_lambda_behavior(self):
        """With very low lambda, 0-0 should dominate."""
        dist = build_scoreline_distribution(0.1, 0.1, -0.13, max_goals=5)
        p_00 = next(s.probability for s in dist if s.home_goals == 0 and s.away_goals == 0)
        assert p_00 > 0.7  # Should be very high

    def test_high_lambda_behavior(self):
        """With high lambda, distribution spreads out."""
        dist = build_scoreline_distribution(3.0, 2.5, -0.13, max_goals=10)
        # Probability should be spread across many scores
        assert len(dist) > 20

    def test_negative_rho_increases_draws(self):
        """Negative rho should increase draw probability (especially 0-0, 1-1)."""
        lam, mu = 1.3, 1.1
        dist_neg = build_scoreline_distribution(lam, mu, -0.20, max_goals=8)
        dist_zero = build_scoreline_distribution(lam, mu, 0.0, max_goals=8)

        p_draw_neg = sum(s.probability for s in dist_neg if s.home_goals == s.away_goals)
        p_draw_zero = sum(s.probability for s in dist_zero if s.home_goals == s.away_goals)

        assert p_draw_neg > p_draw_zero