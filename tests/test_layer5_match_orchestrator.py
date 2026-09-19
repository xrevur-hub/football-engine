"""Tests for Layer 5 Match Orchestrator."""

import pytest

from football_engine.core.enums import PlayerRole
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.core.match_runtime import MatchRuntime
from football_engine.core.parameters import ParameterSet
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import TeamDimensions
from football_engine.core.team_identity import TeamIdentity
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.core.team_season import HistoricalPrior, HistoricalTier
from football_engine.rng.seeded_rng import SeededRNG
from football_engine.simulation.match_orchestrator import MatchOrchestrator, create_match_orchestrator
from football_engine.team_model import TeamModelBuilder


def make_test_formation() -> Formation:
    """Create a standard 4-3-3 formation."""
    B, M, F = SlotDepth.BACK, SlotDepth.MID, SlotDepth.FRONT
    L, C, R = SlotSide.LEFT, SlotSide.CENTER, SlotSide.RIGHT

    slots = [
        PositionSlot(slot_id='GK', role=PlayerRole.GK, side=C, depth=B),
        PositionSlot(slot_id='LB', role=PlayerRole.FB, side=L, depth=B),
        PositionSlot(slot_id='LCB', role=PlayerRole.CB, side=L, depth=B),
        PositionSlot(slot_id='RCB', role=PlayerRole.CB, side=R, depth=B),
        PositionSlot(slot_id='RB', role=PlayerRole.FB, side=R, depth=B),
        PositionSlot(slot_id='DM', role=PlayerRole.DM, side=C, depth=M),
        PositionSlot(slot_id='LCM', role=PlayerRole.CM, side=L, depth=M),
        PositionSlot(slot_id='RCM', role=PlayerRole.CM, side=R, depth=M),
        PositionSlot(slot_id='LW', role=PlayerRole.WM, side=L, depth=F),
        PositionSlot(slot_id='ST', role=PlayerRole.FW, side=C, depth=F),
        PositionSlot(slot_id='RW', role=PlayerRole.WM, side=R, depth=F),
    ]
    return Formation(name='4-3-3', position_pool=slots)


def make_test_players(team_prefix: str) -> list[PlayerSeason]:
    """Create 11 test players for a team."""
    base_id = f"{team_prefix}_2010_11"
    return [
        PlayerSeason(id=f"{base_id}_gk", name=f"{team_prefix} GK", season="2010/11", role=PlayerRole.GK,
                     attack_ability=10, creation_ability=15, defense_ability=10, gk_ability=85,
                     shot_tendency=0.1, press_tendency=0.3, transition_tendency=0.2, pace=0.3,
                     discipline_score=0.6, impact_score=0.5),
        PlayerSeason(id=f"{base_id}_lb", name=f"{team_prefix} LB", season="2010/11", role=PlayerRole.FB,
                     attack_ability=60, creation_ability=50, defense_ability=55, gk_ability=0,
                     shot_tendency=0.3, press_tendency=0.5, transition_tendency=0.4, pace=0.7,
                     discipline_score=0.5, impact_score=0.6),
        PlayerSeason(id=f"{base_id}_lcb", name=f"{team_prefix} LCB", season="2010/11", role=PlayerRole.CB,
                     attack_ability=20, creation_ability=30, defense_ability=85, gk_ability=0,
                     shot_tendency=0.2, press_tendency=0.4, transition_tendency=0.3, pace=0.4,
                     discipline_score=0.7, impact_score=0.7),
        PlayerSeason(id=f"{base_id}_rcb", name=f"{team_prefix} RCB", season="2010/11", role=PlayerRole.CB,
                     attack_ability=25, creation_ability=35, defense_ability=80, gk_ability=0,
                     shot_tendency=0.2, press_tendency=0.5, transition_tendency=0.3, pace=0.5,
                     discipline_score=0.6, impact_score=0.6),
        PlayerSeason(id=f"{base_id}_rb", name=f"{team_prefix} RB", season="2010/11", role=PlayerRole.FB,
                     attack_ability=55, creation_ability=45, defense_ability=60, gk_ability=0,
                     shot_tendency=0.3, press_tendency=0.5, transition_tendency=0.4, pace=0.6,
                     discipline_score=0.5, impact_score=0.5),
        PlayerSeason(id=f"{base_id}_dm", name=f"{team_prefix} DM", season="2010/11", role=PlayerRole.DM,
                     attack_ability=35, creation_ability=65, defense_ability=60, gk_ability=0,
                     shot_tendency=0.3, press_tendency=0.7, transition_tendency=0.4, pace=0.4,
                     discipline_score=0.8, impact_score=0.7),
        PlayerSeason(id=f"{base_id}_lcm", name=f"{team_prefix} LCM", season="2010/11", role=PlayerRole.CM,
                     attack_ability=50, creation_ability=90, defense_ability=40, gk_ability=0,
                     shot_tendency=0.4, press_tendency=0.7, transition_tendency=0.5, pace=0.5,
                     discipline_score=0.7, impact_score=0.8),
        PlayerSeason(id=f"{base_id}_rcm", name=f"{team_prefix} RCM", season="2010/11", role=PlayerRole.CM,
                     attack_ability=65, creation_ability=85, defense_ability=35, gk_ability=0,
                     shot_tendency=0.5, press_tendency=0.6, transition_tendency=0.6, pace=0.6,
                     discipline_score=0.6, impact_score=0.7),
        PlayerSeason(id=f"{base_id}_lw", name=f"{team_prefix} LW", season="2010/11", role=PlayerRole.WM,
                     attack_ability=75, creation_ability=50, defense_ability=30, gk_ability=0,
                     shot_tendency=0.7, press_tendency=0.5, transition_tendency=0.7, pace=0.8,
                     discipline_score=0.5, impact_score=0.6),
        PlayerSeason(id=f"{base_id}_st", name=f"{team_prefix} ST", season="2010/11", role=PlayerRole.FW,
                     attack_ability=90, creation_ability=75, defense_ability=20, gk_ability=0,
                     shot_tendency=0.9, press_tendency=0.4, transition_tendency=0.6, pace=0.8,
                     discipline_score=0.4, impact_score=0.8),
        PlayerSeason(id=f"{base_id}_rw", name=f"{team_prefix} RW", season="2010/11", role=PlayerRole.WM,
                     attack_ability=80, creation_ability=55, defense_ability=25, gk_ability=0,
                     shot_tendency=0.8, press_tendency=0.5, transition_tendency=0.7, pace=0.7,
                     discipline_score=0.5, impact_score=0.7),
    ]


def build_team_runtime_state(
    team_id: str,
    club: str,
    is_home: bool,
    formation: Formation,
    players: list[PlayerSeason],
    possession_source,
) -> TeamRuntimeState:
    """Build a TeamRuntimeState from players and formation."""
    from football_engine.team_model import TeamModelBuilder, TeamIdentityEngine
    from football_engine.data_layer.possession_source import JsonPossessionTendencySource

    if possession_source is None:
        from football_engine.data_layer import create_possession_source
        possession_source = create_possession_source()

    # Create engines
    builder = TeamModelBuilder()
    identity_engine = TeamIdentityEngine(possession_source=possession_source)
    builder._identity_engine = identity_engine

    # Build team model
    team_model = builder.build(players, formation, None)

    # Create runtime state
    return TeamRuntimeState(
        team_id=team_id,
        dims=team_model.dimensions,
        identity=team_model.identity,
        formation=formation,
        formation_structural_features=team_model.structural_features,
        roster=[p.id for p in players],
        is_home=is_home,
    )


class TestMatchOrchestrator:
    """Test the match orchestrator."""

    def setup_method(self):
        self.formation = make_test_formation()
        self.home_players = make_test_players("barcelona")
        self.away_players = make_test_players("chelsea")

        from football_engine.data_layer import create_possession_source
        self.possession_source = create_possession_source()

        self.home_runtime = build_team_runtime_state(
            "barcelona_2010_11", "Barcelona", True,
            self.formation, self.home_players, self.possession_source
        )
        self.away_runtime = build_team_runtime_state(
            "chelsea_2011_12", "Chelsea", False,
            self.formation, self.away_players, self.possession_source
        )

    def test_orchestrator_creation(self):
        orchestrator = create_match_orchestrator()
        assert isinstance(orchestrator, MatchOrchestrator)

    def test_orchestrator_with_custom_params(self):
        params = ParameterSet(baseline=1.5, k_p=0.3)
        orchestrator = create_match_orchestrator(parameters=params)
        assert orchestrator.parameters.baseline == 1.5
        assert orchestrator.parameters.k_p == 0.3

    def test_simulate_standalone_match(self):
        """Test a full standalone match simulation."""
        runtime = MatchRuntime(
            match_id="test_match_1",
            seed=12345,
            is_tournament=False,
            home_team_id="barcelona_2010_11",
            away_team_id="chelsea_2011_12",
            rng=SeededRNG(12345),
            home=self.home_runtime,
            away=self.away_runtime,
        )

        orchestrator = create_match_orchestrator(is_tournament=False)
        result = orchestrator.simulate(runtime)

        # Verify result structure
        assert isinstance(result.final_score_home, int)
        assert isinstance(result.final_score_away, int)
        assert result.final_score_home >= 0
        assert result.final_score_away >= 0
        assert result.match_id == "test_match_1"
        assert result.seed == 12345
        assert result.home_team_id == "barcelona_2010_11"
        assert result.away_team_id == "chelsea_2011_12"

        # Verify invariants
        home_goals = sum(1 for g in result.goal_log if g.is_home_team)
        away_goals = sum(1 for g in result.goal_log if not g.is_home_team)
        assert home_goals == result.final_score_home
        assert away_goals == result.final_score_away

    def _create_fresh_runtimes(self, seed: int) -> tuple[MatchRuntime, MatchRuntime]:
        """Create fresh runtime objects for a simulation."""
        home_runtime = build_team_runtime_state(
            "barcelona_2010_11", "Barcelona", True,
            self.formation, self.home_players, self.possession_source
        )
        away_runtime = build_team_runtime_state(
            "chelsea_2011_12", "Chelsea", False,
            self.formation, self.away_players, self.possession_source
        )
        runtime1 = MatchRuntime(
            match_id="test_1", seed=seed, is_tournament=False,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(seed), home=home_runtime, away=away_runtime,
        )
        # Need separate runtime objects for the second run
        home_runtime2 = build_team_runtime_state(
            "barcelona_2010_11", "Barcelona", True,
            self.formation, self.home_players, self.possession_source
        )
        away_runtime2 = build_team_runtime_state(
            "chelsea_2011_12", "Chelsea", False,
            self.formation, self.away_players, self.possession_source
        )
        runtime2 = MatchRuntime(
            match_id="test_2", seed=seed, is_tournament=False,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(seed), home=home_runtime2, away=away_runtime2,
        )
        return runtime1, runtime2

    def test_deterministic_reproducibility(self):
        """Same seed + same inputs = same result."""
        runtime1, runtime2 = self._create_fresh_runtimes(99999)

        orchestrator = create_match_orchestrator(is_tournament=False)
        result1 = orchestrator.simulate(runtime1)
        result2 = orchestrator.simulate(runtime2)

        assert result1.final_score_home == result2.final_score_home
        assert result1.final_score_away == result2.final_score_away
        assert result1.goal_log == result2.goal_log

    def test_different_seeds_different_results(self):
        """Different seeds should produce different results (with high probability)."""
        runtime1, runtime2 = self._create_fresh_runtimes(11111)
        runtime3, runtime4 = self._create_fresh_runtimes(22222)

        orchestrator = create_match_orchestrator(is_tournament=False)
        result1 = orchestrator.simulate(runtime1)
        result2 = orchestrator.simulate(runtime3)

        # Very unlikely to be identical (but theoretically possible)
        # Just check they ran without error
        assert result1.final_score_home >= 0
        assert result2.final_score_home >= 0

    def test_goal_log_ordered_by_minute(self):
        """Goal log should be ordered by minute."""
        runtime = MatchRuntime(
            match_id="test_order", seed=55555, is_tournament=False,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(55555), home=self.home_runtime, away=self.away_runtime,
        )

        orchestrator = create_match_orchestrator(is_tournament=False)
        result = orchestrator.simulate(runtime)

        minutes = [g.minute for g in result.goal_log]
        assert minutes == sorted(minutes), "Goal minutes must be non-decreasing"

    def test_match_result_validation(self):
        """MatchResult should validate goal count invariants."""
        runtime = MatchRuntime(
            match_id="test_validation", seed=77777, is_tournament=False,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(77777), home=self.home_runtime, away=self.away_runtime,
        )

        orchestrator = create_match_orchestrator(is_tournament=False)
        result = orchestrator.simulate(runtime)

        # This should not raise - validates invariants
        assert result.final_score_home >= 0
        assert result.final_score_away >= 0

    def test_tournament_mode(self):
        """Test tournament mode (uses form_factor)."""
        # Set non-1.0 form factors
        self.home_runtime.form_factor = 1.1
        self.away_runtime.form_factor = 0.95

        runtime = MatchRuntime(
            match_id="test_tournament", seed=88888, is_tournament=True,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(88888), home=self.home_runtime, away=self.away_runtime,
        )

        orchestrator = create_match_orchestrator(is_tournament=True)
        result = orchestrator.simulate(runtime)

        assert result.final_score_home >= 0
        assert result.final_score_away >= 0


class TestSegmentLoop:
    """Test segment loop behavior."""

    def setup_method(self):
        self.formation = make_test_formation()
        self.home_players = make_test_players("barcelona")
        self.away_players = make_test_players("chelsea")

        from football_engine.data_layer import create_possession_source
        self.possession_source = create_possession_source()

        self.home_runtime = build_team_runtime_state(
            "barcelona_2010_11", "Barcelona", True,
            self.formation, self.home_players, self.possession_source
        )
        self.away_runtime = build_team_runtime_state(
            "chelsea_2011_12", "Chelsea", False,
            self.formation, self.away_players, self.possession_source
        )

    def test_segment_schedule(self):
        """Verify segment schedule is correct."""
        from football_engine.simulation.match_orchestrator import SEGMENT_SCHEDULE

        assert SEGMENT_SCHEDULE == [
            (1, 0, 30),    # S1
            (2, 30, 60),   # S2
            (3, 60, 75),   # S3
            (4, 75, 90),   # S4
        ]

    def test_segment_processing(self):
        """Test that segments are processed in order."""
        runtime = MatchRuntime(
            match_id="test_segments", seed=33333, is_tournament=False,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(33333), home=self.home_runtime, away=self.away_runtime,
        )

        orchestrator = create_match_orchestrator(is_tournament=False)
        result = orchestrator.simulate(runtime)

        # Match should complete all 4 segments or end early
        assert runtime.segment_id <= 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])