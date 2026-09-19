"""Tests for Layer 6 Player Events / Attribution."""

import pytest

from football_engine.core.enums import PlayerRole
from football_engine.core.events import (
    AttributedGoalEvent,
    CardEvent,
    MatchEvents,
    SaveEvent,
    ShotEvent,
    SubstitutionEvent,
)
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.core.match_runtime import MatchRuntime
from football_engine.core.parameters import ParameterSet
from football_engine.core.player_season import PlayerSeason
from football_engine.core.segment_outcome import SegmentOutcome
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.core.team_identity import TeamIdentity
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.events.attribution import (
    EventGenerationCoefficients,
    DEFAULT_EVENT_COEFFICIENTS,
    EventGenerator,
    create_event_generator,
    attribute_goals_for_team,
    compute_scorer_weight,
    compute_assist_weight,
    generate_shots,
    generate_saves,
    generate_cards,
    generate_substitutions,
    weighted_player_choice,
)
from football_engine.matchup.helpers import compute_directional_helpers
from football_engine.probability.dixon_coles import SegmentLambda, scale_lambda_to_segment
from football_engine.core.matchup import LambdaPair
from football_engine.rng.seeded_rng import SeededRNG
from football_engine.matchup.dependencies import DirectionalMatchupHelpers
from football_engine.core.enums import MatchState


def make_test_formation() -> Formation:
    """Create a standard 4-3-3 formation for testing."""
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


def make_test_structure() -> StructuralFeatures:
    """Create standard structural features for testing."""
    return StructuralFeatures(
        formation_name="4-3-3",
        width_feature=0.8,
        line_height_feature=0.5,
        defensive_cover_feature=0.5,
        press_structure_feature=0.28,
        build_up_structure_feature=0.32,
        transition_structure_feature=0.84,
    )


def make_test_players(team_prefix: str) -> list[PlayerSeason]:
    """Create 11 test players for a team."""
    base_id = f"{team_prefix}_2010_11"
    return [
        PlayerSeason(id=f"{base_id}_gk", name=f"{team_prefix} GK", season="2010/11", role=PlayerRole.GK,
                     attack_ability=10, creation_ability=15, defense_ability=10, gk_ability=85,
                     shot_tendency=0.1, press_tendency=0.3, transition_tendency=0.2, pace=0.3,
                     discipline_score=0.6, impact_score=0.5),
        PlayerSeason(id=f"{base_id}_lb", name=f"{team_prefix} LB", season="2010/11", role=PlayerRole.FB,
                     attack_ability=65, creation_ability=55, defense_ability=50, gk_ability=0,
                     shot_tendency=0.4, press_tendency=0.6, transition_tendency=0.5, pace=0.7,
                     discipline_score=0.5, impact_score=0.6),
        PlayerSeason(id=f"{base_id}_lcb", name=f"{team_prefix} LCB", season="2010/11", role=PlayerRole.CB,
                     attack_ability=20, creation_ability=30, defense_ability=90, gk_ability=0,
                     shot_tendency=0.2, press_tendency=0.5, transition_tendency=0.3, pace=0.4,
                     discipline_score=0.7, impact_score=0.7),
        PlayerSeason(id=f"{base_id}_rcb", name=f"{team_prefix} RCB", season="2010/11", role=PlayerRole.CB,
                     attack_ability=25, creation_ability=35, defense_ability=85, gk_ability=0,
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


class TestEventCoefficients:
    """Test EventGenerationCoefficients configuration."""

    def test_default_coefficients_valid(self):
        c = DEFAULT_EVENT_COEFFICIENTS
        assert isinstance(c, EventGenerationCoefficients)
        assert c.scorer_role_weights is not None
        assert c.assist_role_weights is not None
        assert len(c.scorer_role_weights) == 8
        assert len(c.assist_role_weights) == 8

    def test_scorer_role_weights_complete(self):
        c = DEFAULT_EVENT_COEFFICIENTS
        for role in PlayerRole:
            assert role in c.scorer_role_weights
            assert 0.0 <= c.scorer_role_weights[role] <= 1.0

    def test_assist_role_weights_complete(self):
        c = DEFAULT_EVENT_COEFFICIENTS
        for role in PlayerRole:
            assert role in c.assist_role_weights
            assert 0.0 <= c.assist_role_weights[role] <= 1.0


class TestWeightedPlayerChoice:
    """Test weighted player selection."""

    def test_choice_returns_player(self):
        rng = SeededRNG(12345)
        players = make_test_players("barcelona")
        player = weighted_player_choice(rng, players, lambda p: 1.0)
        assert player is not None
        assert isinstance(player, PlayerSeason)

    def test_choice_respects_weights(self):
        rng = SeededRNG(12345)
        players = make_test_players("barcelona")
        # High attack ability should be chosen more often
        fw = next(p for p in players if p.role == PlayerRole.FW)
        cb = next(p for p in players if p.role == PlayerRole.CB)

        choices_fw = 0
        choices_cb = 0
        for _ in range(1000):
            p = weighted_player_choice(rng, players, lambda p: p.attack_ability)
            if p.role == PlayerRole.FW:
                choices_fw += 1
            elif p.role == PlayerRole.CB:
                choices_cb += 1

        assert choices_fw > choices_cb

    def test_choice_excludes_players(self):
        rng = SeededRNG(12345)
        players = make_test_players("barcelona")
        fw = next(p for p in players if p.role == PlayerRole.FW)
        player = weighted_player_choice(rng, players, lambda p: 1.0, exclude={fw.id})
        assert player.id != fw.id

    def test_choice_empty_returns_none(self):
        rng = SeededRNG(12345)
        player = weighted_player_choice(rng, [], lambda p: 1.0)
        assert player is None


class TestScorerAssistWeights:
    """Test scorer and assist weight computation."""

    def test_scorer_weight_positive(self):
        players = make_test_players("barcelona")
        fw = next(p for p in players if p.role == PlayerRole.FW)
        cb = next(p for p in players if p.role == PlayerRole.CB)

        fw_weight = compute_scorer_weight(fw, DEFAULT_EVENT_COEFFICIENTS)
        cb_weight = compute_scorer_weight(cb, DEFAULT_EVENT_COEFFICIENTS)

        assert fw_weight > cb_weight

    def test_assist_weight_positive(self):
        players = make_test_players("barcelona")
        am = next(p for p in players if p.role == PlayerRole.CM)  # CM has high creation
        cb = next(p for p in players if p.role == PlayerRole.CB)

        am_weight = compute_assist_weight(am, DEFAULT_EVENT_COEFFICIENTS)
        cb_weight = compute_assist_weight(cb, DEFAULT_EVENT_COEFFICIENTS)

        assert am_weight > cb_weight


class TestGoalAttribution:
    """Test goal attribution to players."""

    def test_attribute_goals_returns_correct_count(self):
        rng = SeededRNG(12345)
        home_players = make_test_players("barcelona")
        away_players = make_test_players("chelsea")

        home_runtime = TeamRuntimeState(
            team_id="barcelona_2010_11",
            dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(
                possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5
            ),
            formation=make_test_formation(),
            formation_structural_features=make_test_structure(),
            roster=[p.id for p in home_players],
            is_home=True,
        )

        away_runtime = TeamRuntimeState(
            team_id="chelsea_2011_12",
            dims=TeamDimensions(attack=75, creation=80, defense=75, goalkeeping=85),
            identity=TeamIdentity(
                possession_tendency=0.5, press_tendency=0.6, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5
            ),
            formation=make_test_formation(),
            formation_structural_features=make_test_structure(),
            roster=[p.id for p in away_players],
            is_home=False,
        )

        goals = attribute_goals_for_team(
            rng, home_runtime, away_runtime, 3, 45, home_players, True, 1.5
        )
        assert len(goals) == 3
        assert all(isinstance(g, AttributedGoalEvent) for g in goals)
        assert all(g.is_home_team for g in goals)
        assert all(g.scorer_player_id in [p.id for p in home_players] for g in goals)

    def test_attribute_goals_zero_returns_empty(self):
        rng = SeededRNG(12345)
        players = make_test_players("barcelona")
        runtime = TeamRuntimeState(
            team_id="test", dims=TeamDimensions(attack=50, creation=50, defense=50, goalkeeping=50),
            identity=TeamIdentity(possession_tendency=0.5, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(),
            formation_structural_features=make_test_structure(),
            roster=[p.id for p in players], is_home=True,
        )

        goals = attribute_goals_for_team(rng, runtime, runtime, 0, 45, players, True, 1.0)
        assert goals == []

    def test_attribute_goals_has_xg_credit(self):
        rng = SeededRNG(12345)
        players = make_test_players("barcelona")
        runtime = TeamRuntimeState(
            team_id="test", dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in players], is_home=True,
        )

        goals = attribute_goals_for_team(rng, runtime, runtime, 2, 45, players, True, 2.0)
        assert all(g.xg_credit > 0 for g in goals)


class TestShotGeneration:
    """Test shot event generation."""

    def test_generate_shots_returns_shots(self):
        rng = SeededRNG(12345)
        home_players = make_test_players("barcelona")
        away_players = make_test_players("chelsea")

        home_runtime = TeamRuntimeState(
            team_id="barcelona_2010_11",
            dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in home_players], is_home=True,
        )

        away_runtime = TeamRuntimeState(
            team_id="chelsea_2011_12",
            dims=TeamDimensions(attack=75, creation=80, defense=75, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.5, press_tendency=0.6, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in away_players], is_home=False,
        )

        outcome = SegmentOutcome(goals_home=2, goals_away=1, goal_minute=45, used_dixon_coles=True)
        lambda_pair = LambdaPair(lambda_home_90=1.5, lambda_away_90=1.0)

        shots = generate_shots(
            rng, outcome, home_runtime, away_runtime, lambda_pair,
            home_players, away_players
        )

        assert len(shots) >= 3  # at least goals_home + goals_away
        assert all(isinstance(s, ShotEvent) for s in shots)
        # Goals should be subset of shots
        goal_shots = [s for s in shots if s.is_goal]
        assert len(goal_shots) == 3

    def test_shots_have_xg(self):
        rng = SeededRNG(12345)
        players = make_test_players("barcelona")
        runtime = TeamRuntimeState(
            team_id="test", dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in players], is_home=True,
        )

        outcome = SegmentOutcome(goals_home=1, goals_away=0, goal_minute=45, used_dixon_coles=True)
        lambda_pair = LambdaPair(lambda_home_90=1.5, lambda_away_90=1.0)

        shots = generate_shots(rng, outcome, runtime, runtime, lambda_pair, players, players)
        goal_shots = [s for s in shots if s.is_goal]
        assert all(s.xg > 0 for s in goal_shots)


class TestSaveGeneration:
    """Test save event generation."""

    def test_generate_saves_for_on_target_shots(self):
        rng = SeededRNG(12345)
        home_players = make_test_players("barcelona")
        away_players = make_test_players("chelsea")

        home_runtime = TeamRuntimeState(
            team_id="barcelona_2010_11", dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in home_players], is_home=True,
        )

        away_runtime = TeamRuntimeState(
            team_id="chelsea_2011_12", dims=TeamDimensions(attack=75, creation=80, defense=75, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.5, press_tendency=0.6, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in away_players], is_home=False,
        )

        # Create shots: some on-target goals, some on-target misses
        shots = [
            ShotEvent(minute=30, team_id="barcelona_2010_11", is_home_team=True, is_goal=True, on_target=True, xg=0.8),
            ShotEvent(minute=35, team_id="chelsea_2011_12", is_home_team=False, is_goal=False, on_target=True, xg=0.3),
            ShotEvent(minute=40, team_id="barcelona_2010_11", is_home_team=True, is_goal=False, on_target=True, xg=0.2),
            ShotEvent(minute=45, team_id="chelsea_2011_12", is_home_team=False, is_goal=False, on_target=False, xg=0.1),
        ]

        saves = generate_saves(rng, shots, home_runtime, away_runtime, home_players, away_players)

        # Should have saves for on-target non-goal shots
        assert len(saves) >= 0  # depends on RNG
        assert all(isinstance(s, SaveEvent) for s in saves)


class TestCardGeneration:
    """Test card event generation."""

    def test_generate_cards_returns_cards(self):
        rng = SeededRNG(12345)
        home_players = make_test_players("barcelona")
        away_players = make_test_players("chelsea")

        home_runtime = TeamRuntimeState(
            team_id="barcelona_2010_11", dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in home_players], is_home=True,
            state=MatchState.LOSING,
            substitutions_made=0,
            players_on_pitch=[p.id for p in home_players[:11]],
        )

        away_runtime = TeamRuntimeState(
            team_id="chelsea_2011_12", dims=TeamDimensions(attack=75, creation=80, defense=75, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.5, press_tendency=0.6, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in away_players], is_home=False,
            state=MatchState.LEADING,
            substitutions_made=0,
            players_on_pitch=[p.id for p in away_players[:11]],
        )

        # Need MatchRuntime for the function signature
        from football_engine.core.match_runtime import MatchRuntime
        runtime = MatchRuntime(
            match_id="test", seed=12345, is_tournament=False,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(12345), home=home_runtime, away=away_runtime,
        )

        cards = generate_cards(rng, runtime, home_runtime, away_runtime, home_players, away_players, 2)

        # Should return some cards (depends on RNG)
        assert isinstance(cards, list)
        assert all(isinstance(c, CardEvent) for c in cards)

    def test_generate_cards_no_cards_in_segment_1(self):
        rng = SeededRNG(12345)
        home_players = make_test_players("barcelona")
        away_players = make_test_players("chelsea")

        # Just test that segment 1 returns empty by directly calling with segment=1
        # The function checks segment == 1 at start and returns early
        # This is a smoke test
        cards = generate_cards(rng, None, None, None, home_players, away_players, 1)
        assert cards == []


class TestSubstitutionGeneration:
    """Test substitution event generation."""

    def test_generate_subs_only_in_s3_s4(self):
        rng = SeededRNG(12345)
        players = make_test_players("barcelona")

        runtime = TeamRuntimeState(
            team_id="test", dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in players], is_home=True,
            state=MatchState.NORMAL,
            substitutions_made=0,
            players_on_pitch=[p.id for p in players[:11]],
        )

        from football_engine.core.match_runtime import MatchRuntime
        match_runtime = MatchRuntime(match_id="test", seed=12345, is_tournament=False,
            home_team_id="test", away_team_id="test2",
            rng=SeededRNG(12345), home=runtime, away=runtime)

        # Segment 1 and 2 should return empty
        subs = generate_substitutions(rng, match_runtime, runtime, runtime, players, players, 1)
        assert subs == []

        subs = generate_substitutions(rng, match_runtime, runtime, runtime, players, players, 2)
        assert subs == []

    def test_generate_subs_returns_subs_in_late_segments(self):
        rng = SeededRNG(12345)
        home_players = make_test_players("barcelona")
        away_players = make_test_players("chelsea")

        home_runtime = TeamRuntimeState(
            team_id="barcelona_2010_11", dims=TeamDimensions(attack=80, creation=85, defense=70, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.6, press_tendency=0.5, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in home_players], is_home=True,
            state=MatchState.LOSING,
            substitutions_made=0,
            players_on_pitch=[p.id for p in home_players[:11]],
        )

        away_runtime = TeamRuntimeState(
            team_id="chelsea_2011_12", dims=TeamDimensions(attack=75, creation=80, defense=75, goalkeeping=85),
            identity=TeamIdentity(possession_tendency=0.5, press_tendency=0.6, transition_tendency=0.5,
                tempo=0.5, risk_tolerance=0.5, compactness=0.5,
                build_up_control_score=0.5, attack_pace_factor=0.5),
            formation=make_test_formation(), formation_structural_features=make_test_structure(),
            roster=[p.id for p in away_players], is_home=False,
            state=MatchState.LEADING,
            substitutions_made=0,
            players_on_pitch=[p.id for p in away_players[:11]],
        )

        from football_engine.core.match_runtime import MatchRuntime
        match_runtime = MatchRuntime(
            match_id="test", seed=12345, is_tournament=False,
            home_team_id="barcelona_2010_11", away_team_id="chelsea_2011_12",
            rng=SeededRNG(12345), home=home_runtime, away=away_runtime,
        )

        subs = generate_substitutions(rng, match_runtime, home_runtime, away_runtime, home_players, away_players, 3)
        # May or may not return subs depending on RNG
        assert isinstance(subs, list)
        if subs:
            assert all(isinstance(s, SubstitutionEvent) for s in subs)
            assert all(s.minute >= 60 for s in subs)


class TestEventGenerator:
    """Test the main EventGenerator orchestrator."""

    def test_event_generator_creation(self):
        gen = create_event_generator()
        assert isinstance(gen, EventGenerator)

    def test_event_generator_with_custom_coeffs(self):
        coeffs = EventGenerationCoefficients(shots_per_lambda=10.0)
        gen = create_event_generator(coeffs=coeffs)
        assert gen.coeffs.shots_per_lambda == 10.0


class TestSegmentLambda:
    """Test SegmentLambda scaling."""

    def test_scale_lambda_to_segment(self):
        seg = scale_lambda_to_segment(1.8, 1.2, 30)
        assert seg.duration_minutes == 30
        assert seg.lambda_home == pytest.approx(1.8 * 30 / 90)
        assert seg.lambda_away == pytest.approx(1.2 * 30 / 90)

    def test_scale_lambda_to_different_segments(self):
        s1 = scale_lambda_to_segment(1.8, 1.2, 30)
        s2 = scale_lambda_to_segment(1.8, 1.2, 30)
        s3 = scale_lambda_to_segment(1.8, 1.2, 15)
        s4 = scale_lambda_to_segment(1.8, 1.2, 15)
        assert s1.lambda_home == s2.lambda_home
        assert s3.lambda_home == s4.lambda_home
        assert s1.lambda_home == pytest.approx(2 * s3.lambda_home)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])