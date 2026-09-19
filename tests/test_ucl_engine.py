"""Tests for the UCL Competition Engine."""

import json
import math
from pathlib import Path

import pytest

from football_engine.competition.synthetic_teams import extend_dataset, SYNTHETIC_CLUBS
from football_engine.competition.ucl import (
    MatchLeg,
    MatchStage,
    UCLRunner,
    UCLStanding,
    generate_league_phase_fixtures,
    run_ucl_season,
)
from football_engine.data_layer.loader import load_all


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "normalized"


class TestUCLStanding:
    """Test standing aggregation."""

    def test_add_win(self):
        s = UCLStanding(team_id="t")
        s.add_result(2, 1)
        assert s.played == 1 and s.won == 1 and s.points == 3
        assert s.goal_difference == 1

    def test_add_draw(self):
        s = UCLStanding(team_id="t")
        s.add_result(1, 1)
        assert s.played == 1 and s.drawn == 1 and s.points == 1

    def test_add_loss(self):
        s = UCLStanding(team_id="t")
        s.add_result(0, 2)
        assert s.played == 1 and s.lost == 1 and s.points == 0
        assert s.goal_difference == -2


class TestLeaguePhaseFixtures:
    """Test the league-phase scheduler."""

    def test_every_team_has_8_fixtures_4home_4away(self):
        teams = [f"team_{i:02d}" for i in range(36)]
        fixtures = generate_league_phase_fixtures(teams, seed=1)

        home_counts = {t: 0 for t in teams}
        away_counts = {t: 0 for t in teams}
        opponents = {t: set() for t in teams}

        for h, a in fixtures:
            home_counts[h] += 1
            away_counts[a] += 1
            opponents[h].add(a)
            opponents[a].add(h)

        for t in teams:
            assert home_counts[t] == 4, f"{t} has {home_counts[t]} home fixtures"
            assert away_counts[t] == 4, f"{t} has {away_counts[t]} away fixtures"
            assert len(opponents[t]) == 8, f"{t} plays {len(opponents[t])} distinct opponents"

    def test_deterministic_with_seed(self):
        teams = [f"team_{i:02d}" for i in range(20)]
        f1 = generate_league_phase_fixtures(teams, seed=7)
        f2 = generate_league_phase_fixtures(teams, seed=7)
        assert f1 == f2

    def test_no_team_plays_itself(self):
        teams = [f"team_{i:02d}" for i in range(36)]
        fixtures = generate_league_phase_fixtures(teams, seed=2)
        for h, a in fixtures:
            assert h != a


class TestUCLRunnerWithSeed:
    """Test the UCL runner end-to-end using the seeded synthetic dataset."""

    @pytest.fixture
    def repos(self):
        return load_all(DATA_DIR)

    def test_league_phase_runs(self, repos):
        team_ids = [t.id for t in repos.teams.all(include_placeholder=False)]
        assert len(team_ids) == 36

        runner = UCLRunner(data_dir=DATA_DIR, seed=42)
        standings = runner.run_league_phase(team_ids, 42)
        assert len(standings) == 36
        # Sorted by points descending
        pts = [s.points for s in standings]
        assert pts == sorted(pts, reverse=True)
        # Every team played 8 matches
        for s in standings:
            assert s.played == 8

    def test_full_season_runs_and_champion_valid(self, repos):
        runner = UCLRunner(data_dir=DATA_DIR, seed=7)
        team_ids = [t.id for t in repos.teams.all(include_placeholder=False)]
        result = runner.run_full_season(team_ids)

        assert "standings" in result
        assert len(result["standings"]) == 36
        assert len(result["r16_direct"]) == 8
        assert len(result["playoff_winners"]) == 8
        assert len(result["r16"]) == 16
        assert "champion" in result
        assert "final" in result
        champion = result["champion"]
        assert champion in team_ids

    def test_synthetic_dataset_has_expected_shape(self, repos):
        teams = repos.teams.all(include_placeholder=False)
        assert len(teams) >= 36
        # Barcelona and Chelsea real teams present
        ids = {t.id for t in teams}
        assert "barcelona_2010_11" in ids
        assert "chelsea_2011_12" in ids


class TestSyntheticTeams:
    """Test the synthetic team generator (data-driven scaffolding)."""

    def test_generator_is_idempotent(self):
        """Running extend_dataset twice produces the same result (idempotent)."""
        summary1 = extend_dataset(DATA_DIR)
        summary2 = extend_dataset(DATA_DIR)
        assert summary2["added_teams"] == 0
        assert summary2["added_players"] == 0
        assert summary2["added_possession"] == 0

    def test_synthetic_teams_have_valid_rosters(self):
        repos = load_all(DATA_DIR)
        for team in repos.teams.all(include_placeholder=False):
            for pid in team.roster:
                assert repos.players.get(pid) is not None