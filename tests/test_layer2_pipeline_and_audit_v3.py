"""Real Layer 2 assembly with explicit synthetic data; downstream gaps stay open."""
from __future__ import annotations

import ast
from dataclasses import fields, FrozenInstanceError
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from football_engine.core.enums import MatchState
from football_engine.core.parameters import DEFAULT_PARAMETER_SET
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_season import apply_historical_prior_to_dimensions, apply_historical_prior_to_identity
from football_engine.team_model import TeamIdentityEngine, TeamModelBuilder, TeamIdentitySpecificationGapError, FormationEngineError
from football_engine.team_model.role_weight_priors import DIMENSION_ROLE_WEIGHT_PRIORS as DW, IDENTITY_ROLE_WEIGHT_PRIORS as IW
from football_engine.matchup import MatchupEngine
from football_engine.matchup.dependencies import DirectionalMatchupHelpers
from football_engine.matchup.tactical_profile import TacticalProfileGenerator
from football_engine.matchup.errors import SpecificationGapError
from tests.layer2_memo_v3_helpers import example_players, example_structure, example_formation, example_prior, example_source, reference


def build(prior=None):
    players=example_players()
    builder=TeamModelBuilder(identity_engine=TeamIdentityEngine(possession_source=example_source(players)))
    return builder.build(players,example_formation(),prior)


def test_real_formation_dimension_identity_pipeline_without_prior():
    model=build();expected=reference()
    for key,value in expected['expected_structure'].items():assert getattr(model.structural_features,key)==pytest.approx(value)
    for key,value in expected['expected_dimensions'].items():assert getattr(model.dimensions,key)==pytest.approx(value,abs=1e-12)
    for key,value in expected['expected_pre_prior_identity'].items():assert getattr(model.identity,key)==pytest.approx(value,abs=1e-12)
    assert set(model.structural_features.model_dump())==set(example_structure().model_dump())
    assert 'formation_type' not in model.structural_features.model_dump()


def test_real_pipeline_matches_existing_prior_blends_exactly_once():
    with patch('football_engine.team_model.team_model_builder.apply_historical_prior_to_dimensions',wraps=apply_historical_prior_to_dimensions) as dims_blend:
        with patch('football_engine.team_model.team_identity_engine.apply_historical_prior_to_identity',wraps=apply_historical_prior_to_identity) as identity_blend:
            model=build(example_prior())
    assert dims_blend.call_count==1 and identity_blend.call_count==1
    for key,value in reference()['expected_final_dimensions'].items():assert getattr(model.dimensions,key)==pytest.approx(value,abs=1e-12)
    for key,value in reference()['expected_final_identity'].items():assert getattr(model.identity,key)==pytest.approx(value,abs=1e-12)


def test_default_builder_still_refuses_to_fabricate_missing_possession():
    with pytest.raises(TeamIdentitySpecificationGapError,match='possession_tendency'):
        TeamModelBuilder().build(example_players(),example_formation(),None)


def test_formation_failure_precedes_all_source_queries():
    calls=[]
    def source(*,player_season_ids):calls.append(player_season_ids);return .62
    builder=TeamModelBuilder(identity_engine=TeamIdentityEngine(possession_source=source))
    with pytest.raises(FormationEngineError):builder.build(example_players()[:10],example_formation(),None)
    assert calls==[]


def test_bundle_is_frozen_and_contains_only_the_existing_three_models():
    model=build()
    assert {field.name for field in fields(model)}=={'structural_features','dimensions','identity'}
    with pytest.raises(FrozenInstanceError):model.identity=None


def test_tactical_policy_gap_is_not_silently_closed_by_layer2_progress():
    model=build()
    with pytest.raises(SpecificationGapError):
        TacticalProfileGenerator().generate(model.identity,model.structural_features,MatchState.NORMAL)


def transport_only_policy(*,identity,structural_features,state):
    """TEST-ONLY transport, not a proposed canonical Module 5/state equation."""
    assert state==MatchState.NORMAL
    return TacticalProfile(press_final=identity.press_tendency,line_final=structural_features.line_height_feature,
                           width_final=structural_features.width_feature,build_up_control_score=identity.build_up_control_score,
                           defensive_cover_feature=structural_features.defensive_cover_feature,attack_pace_factor=identity.attack_pace_factor,
                           transition_tendency_final=identity.transition_tendency,tempo_final=identity.tempo,
                           possession_tendency_final=identity.possession_tendency)


def test_supplied_test_policy_transports_real_layer2_outputs_without_new_math():
    model=build()
    tactical=TacticalProfileGenerator(policy=transport_only_policy).generate(model.identity,model.structural_features,MatchState.NORMAL)
    assert tactical.build_up_control_score==model.identity.build_up_control_score
    assert tactical.defensive_cover_feature==model.structural_features.defensive_cover_feature
    assert tactical.possession_tendency_final==model.identity.possession_tendency
    helpers=DirectionalMatchupHelpers(press_disruption_m=.2,width_mismatch=.1,press_transition_opportunity_t=.05)
    result=MatchupEngine(DEFAULT_PARAMETER_SET).evaluate_direction(model.dimensions,model.dimensions,tactical,tactical,helpers=helpers)
    assert math.isfinite(result.m) and result.m>0 and math.isfinite(result.t) and result.t>=0
    # This is conditional data transport + known equations, not full simulation.


def test_current_u_and_press_paths_change_share_not_supplied_press_helper():
    model=build();base=transport_only_policy(identity=model.identity,structural_features=model.structural_features,state=MatchState.NORMAL)
    engine=MatchupEngine(DEFAULT_PARAMETER_SET)
    helpers=DirectionalMatchupHelpers(press_disruption_m=.2,width_mismatch=.1,press_transition_opportunity_t=.05)
    def evaluate(a,b):return engine.evaluate_direction(model.dimensions,model.dimensions,a,b,helpers=helpers)
    start=evaluate(base,base)
    more_u=evaluate(base.model_copy(update={'build_up_control_score':.9}),base)
    more_b_press=evaluate(base,base.model_copy(update={'press_final':.9}))
    assert more_u.possession_share>start.possession_share
    assert more_b_press.possession_share<start.possession_share
    assert more_u.i_press==start.i_press==more_b_press.i_press
    assert more_u.t==start.t==more_b_press.t


def test_corrected_partial_log_sensitivity_with_helpers_held_fixed():
    model=build();base=transport_only_policy(identity=model.identity,structural_features=model.structural_features,state=MatchState.NORMAL)
    engine=MatchupEngine(DEFAULT_PARAMETER_SET)
    helpers=DirectionalMatchupHelpers(press_disruption_m=.2,width_mismatch=.1,press_transition_opportunity_t=.05)
    h=1e-5  # Numerical test step, not a model coefficient.
    def evaluate(u,b):
        return engine.evaluate_direction(model.dimensions,model.dimensions,
              base.model_copy(update={'build_up_control_score':u}),base.model_copy(update={'press_final':b}),helpers=helpers)
    for u,b in ((.1,.2),(.5,.5),(.9,.8)):
        central=evaluate(u,b);s=central.possession_share
        analytic=.6*s*(1-s)/(.6+.4*s)
        numeric_u=(math.log(evaluate(u+h,b).m)-math.log(evaluate(u-h,b).m))/(2*h)
        numeric_b=(math.log(evaluate(u,b+h).m)-math.log(evaluate(u,b-h).m))/(2*h)
        assert numeric_u==pytest.approx(analytic,abs=1e-8)
        assert numeric_b==pytest.approx(-analytic,abs=1e-8)


def test_weight_parameter_count_respects_fixed_zeros_and_scale_invariance():
    positive_dimensions=sum(value>0 for row in DW.values() for value in (row.attack,row.creation,row.defense))
    positive_identity=sum(value>0 for row in IW.values() for value in (row.press,row.transition,row.tempo,row.risk,row.attack_pace))
    assert positive_dimensions==21 and positive_identity==34
    assert (positive_dimensions-3)+(positive_identity-5)==47
    # No optimization or free fit occurred; 72 includes the descriptive GK column.
    assert 8*4+8*5==72


def test_new_layer2_production_has_no_forbidden_runtime_or_io_dependencies():
    folder=Path(__file__).parents[1]/'football_engine/team_model'
    forbidden_prefixes=('random','secrets','numpy.random','football_engine.rng','football_engine.matchup','football_engine.data_layer',
                        'football_engine.core.team_runtime_state','football_engine.core.match_runtime','football_engine.core.parameters')
    for name in ('team_dimension_engine.py','team_identity_engine.py','role_weight_priors.py','_validation.py','_weighted_mean.py','dependencies.py'):
        tree=ast.parse((folder/name).read_text())
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.Import):modules=[alias.name for alias in node.names]
            elif isinstance(node,ast.ImportFrom):modules=[node.module or '']
            for module in modules:assert not module.startswith(forbidden_prefixes),(name,module)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                assert node.func.id not in {'open','exec','eval','__import__'},(name,node.func.id)
