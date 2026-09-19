"""Step B: approved geometry/role-only FormationEngine mathematics.

Layouts are explicit synthetic test geometry, not historical reconstructions.
No snapshot-quality labels or inferred football coefficients are test inputs.
"""

import ast
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from football_engine.core.enums import PlayerRole
from football_engine.core.formation import Formation, PositionSlot, SlotDepth, SlotSide
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.team_model.formation_engine import FormationEngine, FormationEngineError, V1_LINE_HEIGHT_BASELINE_PRIOR
from tests.team_model_helpers import make_standard_formation, make_standard_squad, make_test_player


B, M, F = SlotDepth.BACK, SlotDepth.MID, SlotDepth.FRONT
L, C, R = SlotSide.LEFT, SlotSide.CENTER, SlotSide.RIGHT
FEATURES = (
    "width_feature", "line_height_feature", "defensive_cover_feature",
    "press_structure_feature", "build_up_structure_feature", "transition_structure_feature",
)


def explicit_layout(depths, sides=None, roles=None):
    assert len(depths) == 10
    sides = [C] * 10 if sides is None else sides
    roles = [PlayerRole.CM] * 10 if roles is None else roles
    assert len(sides) == len(roles) == 10
    slots = [PositionSlot(slot_id="opaque_keeper", role=PlayerRole.GK, side=C, depth=B)]
    slots += [PositionSlot(slot_id=f"opaque_{i}", role=role, side=side, depth=depth)
              for i, (depth, side, role) in enumerate(zip(depths, sides, roles))]
    formation = Formation(name="explicit_synthetic_geometry", position_pool=slots)
    players = [make_test_player(f"id_{i}", slot.role) for i, slot in enumerate(slots)]
    return players, formation


def calculate(depths, sides=None, roles=None):
    return FormationEngine().derive(*explicit_layout(depths, sides, roles))


class TestFormationV1SixRules:
    def test_standard_layout_all_six_exact_values(self):
        output = FormationEngine().derive(make_standard_squad(), make_standard_formation())
        expected = (0.8, 0.5, 0.5, 7 / 25, 8 / 25, 21 / 25)
        for field, value in zip(FEATURES, expected):
            assert getattr(output, field) == pytest.approx(value), field
        assert isinstance(output, StructuralFeatures)
        assert output.formation_name == "4-3-3"

    def test_width_zero_for_all_center_outfield(self):
        assert calculate([B] * 4 + [M] * 3 + [F] * 3).width_feature == 0.0

    def test_width_uses_ten_outfield_slots_not_eleven_players(self):
        assert calculate([M] * 10, [L] * 5 + [R] * 5).width_feature == 1.0

    def test_width_counts_both_sides_equally(self):
        left = calculate([M] * 10, [L] * 4 + [C] * 6)
        right = calculate([M] * 10, [R] * 4 + [C] * 6)
        assert left.width_feature == right.width_feature == 0.4

    def test_line_height_is_disclosed_half_prior_not_inferred(self):
        assert V1_LINE_HEIGHT_BASELINE_PRIOR == 0.5
        for depths in ([B] * 10, [M] * 10, [F] * 10):
            assert calculate(depths).line_height_feature == 0.5

    def test_defensive_cover_is_back_plus_mid_dm(self):
        roles = [PlayerRole.CM] * 10
        roles[4] = PlayerRole.DM
        result = calculate([B] * 4 + [M] * 3 + [F] * 3, roles=roles)
        assert result.defensive_cover_feature == 0.5

    def test_dm_already_in_back_is_not_counted_twice(self):
        roles = [PlayerRole.CM] * 10
        roles[0] = PlayerRole.DM
        result = calculate([B] * 4 + [M] * 3 + [F] * 3, roles=roles)
        assert result.defensive_cover_feature == 0.4

    def test_front_dm_does_not_add_cover(self):
        roles = [PlayerRole.CM] * 10
        roles[9] = PlayerRole.DM
        result = calculate([B] * 4 + [M] * 3 + [F] * 3, roles=roles)
        assert result.defensive_cover_feature == 0.4

    def test_back_band_counts_occupancy_not_a_role_quality_weight(self):
        assert calculate([B] + [F] * 9, roles=[PlayerRole.FW] * 10).defensive_cover_feature == 0.1

    def test_role_dm_changes_cover_only(self):
        depths = [B] * 4 + [M] * 3 + [F] * 3
        baseline = calculate(depths)
        roles = [PlayerRole.CM] * 10
        roles[4] = PlayerRole.DM
        changed = calculate(depths, roles=roles)
        assert changed.defensive_cover_feature == pytest.approx(baseline.defensive_cover_feature + 0.1)
        for field in FEATURES:
            if field != "defensive_cover_feature":
                assert getattr(changed, field) == getattr(baseline, field)

    def test_full_back_occupancy_has_cover_one(self):
        assert calculate([B] * 10).defensive_cover_feature == 1.0

    def test_press_connectivity_attains_one_for_five_plus_five(self):
        assert calculate([M] * 5 + [F] * 5).press_structure_feature == 1.0

    def test_press_excludes_opposite_left_right_pairs(self):
        assert calculate([M] * 5 + [F] * 5, [L] * 5 + [R] * 5).press_structure_feature == 0.0

    def test_press_center_connects_to_either_side(self):
        for side in (L, C, R):
            result = calculate([M] * 5 + [F] * 5, [side] * 5 + [C] * 5)
            assert result.press_structure_feature == 1.0

    def test_press_same_side_is_connected(self):
        assert calculate([M] * 5 + [F] * 5, [L] * 10).press_structure_feature == 1.0

    def test_press_mixed_side_edge_count(self):
        result = calculate([B] * 3 + [M] * 3 + [F] * 4, [C] * 3 + [L, C, R] + [L, L, C, R])
        assert result.press_structure_feature == pytest.approx(9 / 25)

    def test_press_uses_global_combinatorial_normalizer_not_local_density(self):
        assert calculate([M] * 2 + [F] * 8).press_structure_feature == pytest.approx(16 / 25)

    def test_build_up_attains_one_for_five_plus_five(self):
        assert calculate([B] * 5 + [M] * 5).build_up_structure_feature == 1.0

    def test_build_up_excludes_opposite_sides(self):
        assert calculate([B] * 5 + [M] * 5, [L] * 5 + [R] * 5).build_up_structure_feature == 0.0

    def test_build_up_exact_mixed_edge_count(self):
        result = calculate([B] * 2 + [M] * 3 + [F] * 5, [L, R] + [L, C, R] + [C] * 5)
        assert result.build_up_structure_feature == pytest.approx(4 / 25)

    def test_build_up_normalizer_is_twenty_five(self):
        assert calculate([B] * 4 + [M] * 6).build_up_structure_feature == pytest.approx(24 / 25)

    def test_empty_middle_has_zero_press_and_build_up(self):
        result = calculate([B] * 5 + [F] * 5)
        assert result.press_structure_feature == 0.0
        assert result.build_up_structure_feature == 0.0

    def test_transition_exact_front_complement_product(self):
        for front_count in range(11):
            result = calculate([M] * (10 - front_count) + [F] * front_count)
            assert result.transition_structure_feature == pytest.approx(front_count * (10 - front_count) / 25)

    def test_transition_ignores_lateral_connectivity(self):
        center = calculate([M] * 5 + [F] * 5)
        opposed = calculate([M] * 5 + [F] * 5, [L] * 5 + [R] * 5)
        assert center.transition_structure_feature == opposed.transition_structure_feature == 1.0
        assert center.press_structure_feature != opposed.press_structure_feature

    def test_all_features_bounded_across_all_depth_count_partitions(self):
        # 66 integer depth partitions, each exercised under three lateral layouts.
        for back_count in range(11):
            for mid_count in range(11 - back_count):
                front_count = 10 - back_count - mid_count
                depths = [B] * back_count + [M] * mid_count + [F] * front_count
                for sides in ([C] * 10, [L, R] * 5, [L, C, R, C, L, C, R, C, L, R]):
                    result = calculate(depths, sides)
                    for field in FEATURES:
                        value = getattr(result, field)
                        assert math.isfinite(value) and 0.0 <= value <= 1.0


class TestFormationV1PurityAndValidation:
    def test_player_order_does_not_assign_players_to_slots(self):
        players, formation = make_standard_squad(), make_standard_formation()
        engine = FormationEngine()
        assert engine.derive(players, formation) == engine.derive(list(reversed(players)), formation)

    def test_template_order_does_not_change_features(self):
        players, formation = make_standard_squad(), make_standard_formation()
        reversed_template = Formation(name=formation.name, position_pool=list(reversed(formation.position_pool)))
        assert FormationEngine().derive(players, formation) == FormationEngine().derive(players, reversed_template)

    def test_arbitrary_identifier_renaming_preserves_complete_output(self):
        players, formation = make_standard_squad(), make_standard_formation()
        slots = [PositionSlot(slot_id=f"not_a_position_{i}", role=s.role, side=s.side, depth=s.depth) for i, s in enumerate(formation.position_pool)]
        renamed = Formation(name=formation.name, position_pool=slots)
        assert FormationEngine().derive(players, formation) == FormationEngine().derive(players, renamed)

    def test_formation_name_is_descriptive_only(self):
        players, formation = make_standard_squad(), make_standard_formation()
        renamed = Formation(name="not_a_football_shape", position_pool=formation.position_pool)
        a = FormationEngine().derive(players, formation)
        b = FormationEngine().derive(players, renamed)
        assert a.model_dump(exclude={"formation_name"}) == b.model_dump(exclude={"formation_name"})
        assert b.formation_name == "not_a_football_shape"

    def test_gk_geometry_is_excluded_from_every_feature(self):
        players, formation = make_standard_squad(), make_standard_formation()
        slots = list(formation.position_pool)
        slots[0] = PositionSlot(slot_id=slots[0].slot_id, role=PlayerRole.GK, side=R, depth=F)
        changed = Formation(name=formation.name, position_pool=slots)
        assert FormationEngine().derive(players, formation) == FormationEngine().derive(players, changed)

    def test_all_player_abilities_tendencies_pace_and_quality_are_irrelevant(self):
        players, formation = make_standard_squad(), make_standard_formation()
        changed = [player.model_copy(update={
            "name": "different_name", "season": "1990/91", "attack_ability": 100.0,
            "creation_ability": 0.0, "defense_ability": 100.0, "gk_ability": 100.0,
            "shot_tendency": 0.0, "press_tendency": 1.0, "transition_tendency": 0.0,
            "pace": 1.0, "discipline_score": 0.0, "impact_score": 1.0,
        }) for player in players]
        assert FormationEngine().derive(players, formation) == FormationEngine().derive(changed, formation)

    def test_player_nonvalidation_attributes_are_not_even_read(self):
        players, formation = make_standard_squad(), make_standard_formation()
        forbidden = set(PlayerSeason.model_fields) - {"id", "role"}
        original = PlayerSeason.__getattribute__
        def guarded(player, name):
            assert name not in forbidden, f"FormationEngine read forbidden PlayerSeason.{name}"
            return original(player, name)
        with patch.object(PlayerSeason, "__getattribute__", guarded):
            assert isinstance(FormationEngine().derive(players, formation), StructuralFeatures)

    def test_input_immutability_and_repeated_determinism(self):
        players, formation = make_standard_squad(), make_standard_formation()
        before = ([p.model_dump() for p in players], formation.model_dump())
        engine = FormationEngine()
        expected = engine.derive(players, formation)
        for _ in range(20):
            assert engine.derive(players, formation) == expected
        assert ([p.model_dump() for p in players], formation.model_dump()) == before
        assert vars(engine) == {}

    def test_duplicate_slot_ids_are_rejected_at_engine_boundary(self):
        players, formation = make_standard_squad(), make_standard_formation()
        slots = list(formation.position_pool)
        slots[1] = slots[1].model_copy(update={"slot_id": slots[0].slot_id})
        with pytest.raises(FormationEngineError, match="duplicate slot_id"):
            FormationEngine().derive(players, Formation(name="duplicate", position_pool=slots))

    def test_exactly_one_gk_is_required_even_with_matching_roles(self):
        for keeper_count in (0, 2):
            players, formation = explicit_layout([M] * 10)
            slots = list(formation.position_pool)
            if keeper_count == 0:
                slots[0] = slots[0].model_copy(update={"role": PlayerRole.CM})
            else:
                slots[1] = slots[1].model_copy(update={"role": PlayerRole.GK})
            players = [make_test_player(f"id_{i}", slot.role) for i, slot in enumerate(slots)]
            with pytest.raises(FormationEngineError, match="exactly one GK"):
                FormationEngine().derive(players, Formation(name="invalid_keeper_count", position_pool=slots))

    def test_non_player_input_is_rejected(self):
        players = make_standard_squad()
        players[1] = object()
        with pytest.raises(FormationEngineError, match="PlayerSeason"):
            FormationEngine().derive(players, make_standard_formation())

    def test_bypassed_invalid_geometry_is_rejected_without_inference(self):
        players, formation = make_standard_squad(), make_standard_formation()
        slots = list(formation.position_pool)
        slots[1] = slots[1].model_copy(update={"side": "north"})
        invalid = Formation.model_construct(name="invalid", position_pool=slots)
        with pytest.raises(FormationEngineError, match="geometry"):
            FormationEngine().derive(players, invalid)

    def test_no_quality_classification_and_v3_remains_inert(self):
        result = FormationEngine().derive(make_standard_squad(), make_standard_formation())
        assert set(result.model_dump()) == set(FEATURES) | {"formation_name", "cb_pairing_quality", "fullback_exposure"}
        assert result.cb_pairing_quality == result.fullback_exposure == 0.5

    def test_no_rng_runtime_matchup_probability_or_io_dependency(self):
        source = Path(__file__).resolve().parents[1] / 'football_engine/team_model/formation_engine.py'
        tree = ast.parse(source.read_text())
        forbidden_prefixes = ('random', 'secrets', 'football_engine.rng', 'football_engine.matchup', 'football_engine.probability', 'football_engine.data_layer', 'football_engine.core.team_runtime_state', 'football_engine.core.match_runtime')
        for node in ast.walk(tree):
            imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
            for module in imports:
                assert not any(module == p or module.startswith(p + '.') for p in forbidden_prefixes)
            if isinstance(node, (ast.Attribute, ast.Subscript)):
                assert not isinstance(node.ctx, (ast.Store, ast.Del))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {'open', 'print', 'input', 'eval', 'exec'}
