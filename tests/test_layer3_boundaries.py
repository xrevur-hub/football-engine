"""Executable single-path and static Layer 3 dependency guards.

Supplied helper scalar values are held fixed during tactical-field perturbations.
These tests prove Layer 3's routing, not the correctness of still-absent helper
implementations. A future helper provider needs its own input-ownership tests.
"""

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from football_engine.core.parameters import ParameterSet
from football_engine.matchup.matchup_engine import MatchupEngine
from tests.layer3_helpers import make_dimensions, make_helpers, make_tactical


ROOT = Path(__file__).resolve().parents[1]
LAYER3 = ROOT / "football_engine" / "matchup"


def direction(*, a_tactical=None, b_tactical=None, helpers=None, parameters=None):
    return MatchupEngine(parameters or ParameterSet()).evaluate_direction(
        make_dimensions(), make_dimensions(attack=72.0, defense=80.0),
        a_tactical if a_tactical is not None else make_tactical(),
        b_tactical if b_tactical is not None else make_tactical(),
        helpers=helpers if helpers is not None else make_helpers(),
    )


class TestLayer3SinglePathRouting:
    def test_press_disruption_affects_m_only(self):
        before = direction()
        after = direction(helpers=replace(make_helpers(), press_disruption_m=0.70))
        assert after.m < before.m
        assert after.t == before.t
        assert after.possession_share == before.possession_share

    def test_press_transition_opportunity_affects_t_only(self):
        before = direction()
        after = direction(helpers=replace(make_helpers(), press_transition_opportunity_t=0.70))
        assert after.t > before.t
        assert after.m == before.m

    def test_two_press_helpers_are_not_aliased_or_reused(self):
        baseline = direction(helpers=replace(make_helpers(), press_disruption_m=0.0, press_transition_opportunity_t=0.0))
        only_m = direction(helpers=replace(make_helpers(), press_disruption_m=0.5, press_transition_opportunity_t=0.0))
        only_t = direction(helpers=replace(make_helpers(), press_disruption_m=0.0, press_transition_opportunity_t=0.5))
        assert only_m.m < baseline.m and only_m.t == baseline.t
        assert only_t.m == baseline.m and only_t.t > baseline.t

    def test_width_mismatch_affects_m_only(self):
        before = direction()
        after = direction(helpers=replace(make_helpers(), width_mismatch=0.70))
        assert after.m > before.m
        assert after.t == before.t

    def test_tempo_affects_m_only(self):
        before = direction()
        after = direction(a_tactical=make_tactical(tempo_final=0.90))
        assert after.m > before.m
        assert after.t == before.t

    def test_attacker_build_up_control_affects_m_only(self):
        before = direction()
        after = direction(a_tactical=make_tactical(build_up_control_score=0.90))
        assert after.m > before.m
        assert after.t == before.t

    def test_defender_press_quality_affects_m_only(self):
        before = direction()
        after = direction(b_tactical=make_tactical(press_final=0.90))
        assert after.m < before.m
        assert after.t == before.t

    def test_high_defender_line_affects_t_only(self):
        before = direction()
        after = direction(b_tactical=make_tactical(line_final=0.90))
        assert after.m == before.m
        assert after.t > before.t

    def test_defender_cover_affects_t_only(self):
        before = direction()
        after = direction(b_tactical=make_tactical(defensive_cover_feature=0.90))
        assert after.m == before.m
        assert after.t < before.t

    def test_transition_tendency_affects_t_only(self):
        before = direction()
        after = direction(a_tactical=make_tactical(transition_tendency_final=0.90))
        assert after.m == before.m
        assert after.t > before.t

    def test_attack_pace_affects_t_only(self):
        before = direction()
        after = direction(a_tactical=make_tactical(attack_pace_factor=0.95))
        assert after.m == before.m
        assert after.t > before.t

    def test_possession_has_only_creation_realization_path(self):
        before = direction()
        after = direction(a_tactical=make_tactical(possession_tendency_final=0.90))
        assert after.possession_share > before.possession_share
        assert after.m / before.m == pytest.approx(after.creation_realization / before.creation_realization)
        assert after.t == before.t
        assert after.base_relative_strength == before.base_relative_strength
        assert after.i_press == before.i_press
        assert after.i_width == before.i_width
        assert after.i_tempo == before.i_tempo

    def test_home_advantage_form_and_unused_kt_are_absent_from_matchup(self):
        before = direction()
        after = direction(parameters=ParameterSet(h_home=1.25, a_away=0.75, k_form=0.9, k_t=12345.0))
        assert after == before

    def test_no_direct_width_field_path_besides_supplied_mismatch(self):
        before = direction()
        assert direction(a_tactical=make_tactical(width_final=0.95), b_tactical=make_tactical(width_final=0.05)) == before

    def test_direction_ignores_other_direction_only_fields(self):
        before = direction()
        # These fields matter for the reversed direction, not the evaluated one.
        after = direction(
            a_tactical=make_tactical(line_final=0.95, defensive_cover_feature=0.95, press_final=0.99),
            b_tactical=make_tactical(tempo_final=0.99, transition_tendency_final=0.99, attack_pace_factor=0.99, build_up_control_score=0.99),
        )
        assert after == before


class TestLayer3ImportAndStateBoundaries:
    def test_no_forbidden_production_imports(self):
        forbidden_prefixes = (
            "random", "secrets", "numpy.random", "scipy", "football_engine.rng",
            "football_engine.probability", "football_engine.sampling",
            "football_engine.events", "football_engine.core.events",
            "football_engine.event_generator", "football_engine.attribution",
            "football_engine.team_model", "football_engine.core.formation",
            "football_engine.data_layer", "football_engine.core.match_runtime",
            "tests", "time", "datetime", "os", "pathlib", "requests",
        )
        for path in LAYER3.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    modules = [node.module or ""]
                for name in modules:
                    assert not any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden_prefixes), (path.name, name)

    def test_runtime_model_import_is_confined_to_lambda_calculator(self):
        for path in LAYER3.glob("*.py"):
            if path.name == "lambda_calculator.py":
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert node.module != "football_engine.core.team_runtime_state", path.name

    def test_no_formation_classification_or_quality_weight_reads(self):
        forbidden = {"formation_type", "formation_name", "slot_id", "TYPE_A", "TYPE_B", "TYPE_C", "FormationStructuralType"}
        for path in LAYER3.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    assert node.attr not in forbidden, path.name
                if isinstance(node, ast.Name):
                    assert node.id not in forbidden, path.name

    def test_no_rng_probability_event_calls_or_production_io(self):
        forbidden = {"open", "print", "input", "eval", "exec", "__import__", "random", "poisson", "bernoulli", "choice", "sample", "uniform", "system", "read_text", "write_text", "read_bytes", "write_bytes"}
        for path in LAYER3.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    function = node.func
                    name = function.id if isinstance(function, ast.Name) else function.attr if isinstance(function, ast.Attribute) else None
                    assert name not in forbidden, (path.name, name)

    def test_no_attribute_or_subscript_mutation_in_production(self):
        for path in LAYER3.glob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Attribute, ast.Subscript)):
                    assert not isinstance(node.ctx, (ast.Store, ast.Del)), path.name

    def test_transition_threat_reads_only_authorized_tactical_fields(self):
        tree = ast.parse((LAYER3 / "matchup_engine.py").read_text())
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        attrs = {node.attr for node in ast.walk(functions["transition_threat"]) if isinstance(node, ast.Attribute)}
        assert attrs == {"transition_tendency_final", "attack_pace_factor", "k_t2"}
        space_attrs = {node.attr for node in ast.walk(functions["space_behind_defense"]) if isinstance(node, ast.Attribute)}
        assert space_attrs == {"line_final", "defensive_cover_feature"}

    def test_lambda_reads_only_context_flags_and_form_from_runtime(self):
        tree = ast.parse((LAYER3 / "lambda_calculator.py").read_text())
        runtime_attributes = {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id in {"home", "away", "team"}
        }
        assert runtime_attributes == {"is_home", "form_factor"}

    def test_new_tests_never_call_layer2_derivations(self):
        for path in [*ROOT.glob("tests/test_layer3_*.py"), ROOT / "tests/layer3_helpers.py"]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert not (node.module or "").startswith("football_engine.team_model"), path.name
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    assert node.func.attr != "derive", path.name
