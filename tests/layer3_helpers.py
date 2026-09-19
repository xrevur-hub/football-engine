"""MANUAL TEST-ONLY upstream objects; never outputs of Layer 2 derive().

These fictional numbers are unit-test inputs, NOT historical estimates or
canonical-example raw data. E-12 removes the misassigned quality field;
structural fixtures contain no historical snapshot-quality labels.
Nothing in production imports this file, and no fixture computes Layer 2 math.
"""

from __future__ import annotations

from football_engine.core.enums import MatchState, PlayerRole
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.core.team_identity import TeamIdentity
from football_engine.core.team_runtime_state import TeamRuntimeState
from football_engine.matchup.dependencies import DirectionalMatchupHelpers


def make_dimensions(**overrides) -> TeamDimensions:
    values = dict(attack=84.0, creation=90.0, defense=76.0, goalkeeping=81.0)
    values.update(overrides)
    return TeamDimensions(**values)


def make_identity(**overrides) -> TeamIdentity:
    values = dict(
        possession_tendency=0.65,
        press_tendency=0.30,
        transition_tendency=0.60,
        tempo=0.50,
        risk_tolerance=0.40,
        compactness=0.55,
        build_up_control_score=0.70,
        attack_pace_factor=0.80,
    )
    values.update(overrides)
    return TeamIdentity(**values)


def make_structure(**overrides) -> StructuralFeatures:
    values = dict(
        formation_name="MANUAL_TEST_STRUCTURE_NOT_A_CLASSIFICATION",
        width_feature=0.60,
        line_height_feature=0.50,
        defensive_cover_feature=0.40,
        press_structure_feature=0.28,
        build_up_structure_feature=0.32,
        transition_structure_feature=0.84,
        cb_pairing_quality=0.50,
        fullback_exposure=0.50,
    )
    values.update(overrides)
    return StructuralFeatures(**values)


def make_tactical(**overrides) -> TacticalProfile:
    """All nine final values are supplied, not calculated from identity/geometry."""
    values = dict(
        press_final=0.30,
        line_final=0.40,
        width_final=0.60,
        build_up_control_score=0.70,
        defensive_cover_feature=0.40,
        attack_pace_factor=0.80,
        transition_tendency_final=0.60,
        tempo_final=0.50,
        possession_tendency_final=0.65,
    )
    values.update(overrides)
    return TacticalProfile(**values)


def make_helpers() -> DirectionalMatchupHelpers:
    # Explicit synthetic inputs, not guessed implementations of the helpers.
    return DirectionalMatchupHelpers(
        press_disruption_m=0.36,
        width_mismatch=0.20,
        press_transition_opportunity_t=0.25,
    )


def make_runtime(is_home: bool, **overrides) -> TeamRuntimeState:
    # The core runtime requires a Formation even though Layer 3 never reads it.
    role_geometry = [
        (PlayerRole.GK, SlotSide.CENTER, SlotDepth.BACK),
        (PlayerRole.FB, SlotSide.LEFT, SlotDepth.BACK),
        (PlayerRole.CB, SlotSide.LEFT, SlotDepth.BACK),
        (PlayerRole.CB, SlotSide.RIGHT, SlotDepth.BACK),
        (PlayerRole.FB, SlotSide.RIGHT, SlotDepth.BACK),
        (PlayerRole.DM, SlotSide.CENTER, SlotDepth.MID),
        (PlayerRole.CM, SlotSide.LEFT, SlotDepth.MID),
        (PlayerRole.CM, SlotSide.RIGHT, SlotDepth.MID),
        (PlayerRole.WM, SlotSide.LEFT, SlotDepth.FRONT),
        (PlayerRole.WM, SlotSide.RIGHT, SlotDepth.FRONT),
        (PlayerRole.FW, SlotSide.CENTER, SlotDepth.FRONT),
    ]
    formation = Formation(
        name="MANUAL_TEST_TEMPLATE",
        position_pool=[
            PositionSlot(slot_id=f"opaque_{i}", role=role, side=side, depth=depth)
            for i, (role, side, depth) in enumerate(role_geometry)
        ],
    )
    values = dict(
        team_id="fixture_home" if is_home else "fixture_away",
        dims=make_dimensions(),
        identity=make_identity(),
        formation=formation,
        formation_structural_features=make_structure(),
        roster=[f"fixture_player_{i}" for i in range(11)],
        is_home=is_home,
        state=MatchState.NORMAL,
        form_factor=1.0,
    )
    values.update(overrides)
    return TeamRuntimeState(**values)
