"""Tests for the Draft Engine."""

from pathlib import Path

import pytest

from football_engine.draft.engine import (
    DraftEngine,
    DraftFormat,
    DraftTeam,
    create_draft_from_data,
    run_draft,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "normalized"


def make_draft_teams(n: int = 2) -> list[DraftTeam]:
    return [DraftTeam(team_id=f"team_{i}", name=f"Team {i+1}") for i in range(n)]


class TestDraftEngineBasics:
    """Basic draft state management."""

    def test_create_draft(self):
        available = {f"p_{i}" for i in range(50)}
        engine = DraftEngine(DraftFormat.SNAKE, make_draft_teams(2), available, seed=1)
        assert engine.state.is_complete is False
        assert engine.state.current_round == 1

    def test_pick_updates_state(self):
        available = {f"p_{i}" for i in range(50)}
        engine = DraftEngine(DraftFormat.SNAKE, make_draft_teams(2), available, seed=1)
        pick = engine.pick("team_0", "p_0")
        assert pick.pick_number == 1
        assert pick.round_number == 1
        assert "p_0" not in engine.state.available_players
        assert engine.state.teams[0].roster_size() == 1

    def test_duplicate_pick_rejected(self):
        available = {f"p_{i}" for i in range(50)}
        engine = DraftEngine(DraftFormat.SNAKE, make_draft_teams(2), available, seed=1)
        engine.pick("team_0", "p_0")
        with pytest.raises(ValueError, match="not available"):
            engine.pick("team_1", "p_0")  # already picked

    def test_snake_draft_completes(self):
        available = {f"p_{i}" for i in range(100)}
        teams = make_draft_teams(2)
        engine = DraftEngine(DraftFormat.SNAKE, teams, available, seed=42)
        history = engine.run_snake_draft()
        assert engine.state.is_complete is True
        assert len(history) == 22  # 2 teams x 11 players
        # Each team has exactly 11 unique players
        for team in teams:
            assert team.roster_size() == 11
            player_ids = [p.player_id for p in team.picks]
            assert len(set(player_ids)) == 11

    def test_snake_draft_all_players_unique(self):
        available = {f"p_{i}" for i in range(500)}
        teams = make_draft_teams(2)
        engine = DraftEngine(DraftFormat.SNAKE, teams, available, seed=1)
        engine.run_snake_draft()
        all_picked = [p.player_id for team in teams for p in team.picks]
        assert len(all_picked) == len(set(all_picked))


class TestDraftUniqueness:
    """PlayerSeason uniqueness rules."""

    def test_same_player_not_drafted_twice(self):
        available = {f"p_{i}" for i in range(50)}
        engine = DraftEngine(DraftFormat.SNAKE, make_draft_teams(2), available, seed=1)
        engine.pick("team_0", "p_0")
        with pytest.raises(ValueError):
            engine.pick("team_1", "p_0")

    def test_draft_requires_enough_pool(self):
        available = {f"p_{i}" for i in range(20)}  # only 20 for 2x11=22 need
        with pytest.raises(ValueError, match="pool has"):
            DraftEngine(DraftFormat.SNAKE, make_draft_teams(2), available, seed=1)


class TestAuctionDraft:
    """Auction/salary-cap drafts."""

    def test_auction_draft_budget(self):
        available = {f"p_{i}" for i in range(100)}
        teams = [
            DraftTeam(team_id="team_0", name="T0", budget=1000),
            DraftTeam(team_id="team_1", name="T1", budget=1000),
        ]
        engine = DraftEngine(DraftFormat.AUCTION, teams, available, seed=5)
        # Each pick costs 5 (placeholder), so 11 picks = 55 <= 1000
        engine.run_auction_draft()
        for team in teams:
            assert team.roster_size() == 11
            assert team.spent == 11 * 5

    def test_salary_cap_draft_completes(self):
        available = {f"p_{i}" for i in range(100)}
        teams = [
            DraftTeam(team_id="team_0", name="T0", budget=100),
            DraftTeam(team_id="team_1", name="T1", budget=100),
        ]
        engine = DraftEngine(DraftFormat.SALARY_CAP, teams, available, seed=5)
        engine.run_salary_cap_draft()
        for team in teams:
            assert team.roster_size() == 11


class TestDataDrivenDraft:
    """Draft from actual dataset (data-driven)."""

    def test_draft_from_data_runs(self):
        res = run_draft(DATA_DIR, DraftFormat.SNAKE, num_teams=2, seed=42)
        assert res["format"] == "snake"
        assert len(res["teams"]) == 2
        for team in res["teams"]:
            assert len(team["roster"]) == 11
            # Each roster player has expected fields
            for player in team["roster"]:
                assert "id" in player
                assert "name" in player
                assert "season" in player
                assert "role" in player
                assert "attack_ability" in player

    def test_draft_uniqueness_global(self):
        res = run_draft(DATA_DIR, DraftFormat.SNAKE, num_teams=2, seed=1)
        all_ids = []
        for team in res["teams"]:
            all_ids.extend(p["id"] for p in team["roster"])
        assert len(all_ids) == len(set(all_ids))

    def test_create_draft_from_data(self):
        engine = create_draft_from_data(DATA_DIR, DraftFormat.SNAKE, ["A", "B"], seed=1)
        assert len(engine.state.available_players) >= 22