"""D1 numerical/contract regressions independent of production mean code."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict
from fractions import Fraction as F
import math

import pytest

from football_engine.core.enums import PlayerRole
from football_engine.team_model import FormationEngine, TeamDimensionEngine, TeamDimensionEngineError
from football_engine.team_model.role_weight_priors import DIMENSION_ROLE_WEIGHT_PRIORS as W
from football_engine.team_model._weighted_mean import role_weighted_mean
from tests.layer2_memo_v3_helpers import example_players, example_structure, example_formation, reference
from tests.team_model_helpers import make_test_player

EXPECTED={
 'GK':(0,0,0),'CB':(.05,.10,1),'FB':(.15,.35,.65),'DM':(.10,.45,.55),
 'CM':(.25,.70,.35),'WM':(.65,.55,.15),'AM':(.55,.85,.10),'FW':(1,.30,.05),
}


def derive(players=None, features=None):
    return TeamDimensionEngine().derive(example_players() if players is None else players,
                                        example_structure() if features is None else features)


def test_dimension_weight_values_match_supplied_memo():
    assert set(W)==set(PlayerRole)
    for role, values in EXPECTED.items():
        profile=W[PlayerRole[role]]
        assert (profile.attack,profile.creation,profile.defense)==values


def test_dimension_weight_mapping_and_rows_are_immutable():
    with pytest.raises(TypeError):
        W[PlayerRole.CB]=W[PlayerRole.FW]
    with pytest.raises(FrozenInstanceError):
        W[PlayerRole.FW].attack=2


def test_golden_dimensions_match_independent_fraction_reference():
    actual=derive().model_dump()
    for key, expected in reference()['expected_dimensions'].items():
        assert actual[key]==pytest.approx(expected,abs=1e-12)
    players=example_players()
    for column,(key,attribute) in enumerate([('attack','attack_ability'),('creation','creation_ability'),('defense','defense_ability')]):
        weights=[F(str(EXPECTED[p.role.name][column])) for p in players]
        exact=sum((w*F(str(getattr(p,attribute))) for w,p in zip(weights,players)),F(0))/sum(weights,F(0))
        assert actual[key]==pytest.approx(float(exact),abs=1e-12)


def test_constant_zero_midpoint_and_maximum_abilities():
    for value in (0.,12.5,50.,100.):
        players=[p.model_copy(update=dict(attack_ability=value,creation_ability=value,defense_ability=value,gk_ability=value)) for p in example_players()]
        assert derive(players).model_dump()==dict(attack=value,creation=value,defense=value,goalkeeping=value)


def test_dimensions_are_finite_and_convex_over_positive_contributors():
    players=example_players(); result=derive(players)
    for column,(key,attribute) in enumerate([('attack','attack_ability'),('creation','creation_ability'),('defense','defense_ability')]):
        values=[getattr(p,attribute) for p in players if EXPECTED[p.role.name][column]>0]
        assert math.isfinite(getattr(result,key))
        assert min(values)<=getattr(result,key)<=max(values)


def test_player_order_is_exactly_invariant():
    players=example_players(); expected=derive(players)
    for shift in range(11):
        assert derive(players[shift:]+players[:shift])==expected
    assert derive(list(reversed(players)))==expected


def test_repeated_execution_does_not_cache_or_mutate_inputs():
    players=list(reversed(example_players())); features=example_structure()
    before=[p.model_dump() for p in players]; sf_before=features.model_dump()
    engine=TeamDimensionEngine(); first=engine.derive(players,features)
    for _ in range(4):assert engine.derive(players,features)==first
    assert vars(engine)=={}
    assert [p.model_dump() for p in players]==before
    assert features.model_dump()==sf_before


def test_each_ability_has_only_its_corresponding_dimension_effect():
    players=example_players(); base=derive(players).model_dump(); index=9
    for field,column in [('attack_ability','attack'),('creation_ability','creation'),('defense_ability','defense')]:
        changed=list(players); changed[index]=players[index].model_copy(update={field:getattr(players[index],field)+1})
        actual=derive(changed).model_dump()
        denominator=math.fsum(getattr(W[p.role],column) for p in players)
        expected_delta=getattr(W[players[index].role],column)/denominator
        assert actual[column]-base[column]==pytest.approx(expected_delta,abs=1e-12)
        for key in base:
            if key!=column:assert actual[key]==base[key]


def test_gk_attack_creation_defense_have_zero_dimension_weight():
    players=example_players(); expected=derive(players)
    players[0]=players[0].model_copy(update=dict(attack_ability=100,creation_ability=100,defense_ability=100))
    assert derive(players)==expected


def test_only_the_selected_gk_ability_controls_goalkeeping():
    players=example_players(); base=derive(players)
    changed=[p if p.role==PlayerRole.GK else p.model_copy(update={'gk_ability':100}) for p in players]
    assert derive(changed)==base
    keeper=next(p for p in players if p.role==PlayerRole.GK)
    others=[p for p in players if p.role!=PlayerRole.GK]
    result=derive(others+[keeper.model_copy(update={'gk_ability':42.})])
    assert result.goalkeeping==42.
    for key in ('attack','creation','defense'):assert getattr(result,key)==getattr(base,key)


def test_identity_and_attribution_attributes_do_not_change_dimensions():
    players=example_players(); base=derive(players)
    changed=[p.model_copy(update=dict(press_tendency=1,shot_tendency=0,transition_tendency=1,pace=0,discipline_score=1,impact_score=0)) for p in players]
    assert derive(changed)==base


def test_all_valid_structural_values_and_metadata_are_dimension_inert():
    features=example_structure(); expected=derive(features=features)
    keys=set(features.model_dump())-{'formation_name'}
    for value in (0.,1.):
        variant=features.model_copy(update={**{key:value for key in keys},'formation_name':'arbitrary metadata'})
        assert derive(features=variant)==expected


def test_real_geometry_change_with_same_players_leaves_d1_unchanged():
    players=example_players(); formation=example_formation()
    from football_engine.core.formation import SlotSide, SlotDepth
    other=formation.model_copy(update={'name':'same players, different geometry','position_pool':[
        slot.model_copy(update={'side':SlotSide.CENTER,'depth':SlotDepth.BACK}) for slot in formation.position_pool
    ]})
    a=FormationEngine().derive(players,formation); b=FormationEngine().derive(players,other)
    assert a.width_feature!=b.width_feature
    assert a.defensive_cover_feature!=b.defensive_cover_feature
    assert derive(players,a)==derive(players,b)


def test_common_weight_scale_cancels():
    players=tuple(example_players())
    for factor in (.1,1.,17.):
        value=role_weighted_mean(players,attribute='attack_ability',weight_for_role=lambda role:W[role].attack*factor,
                                 field_name='attack',upper=100,error_type=TeamDimensionEngineError)
        assert value==pytest.approx(reference()['expected_dimensions']['attack'],abs=1e-12)


def test_zero_or_invalid_weight_denominator_is_not_replaced_by_default():
    players=tuple(example_players())
    for weight in (0.,-1.,float('nan'),float('inf'),True):
        with pytest.raises(TeamDimensionEngineError):
            role_weighted_mean(players,attribute='attack_ability',weight_for_role=lambda role:weight,
                               field_name='attack',upper=100,error_type=TeamDimensionEngineError)


def test_wrong_selection_types_and_counts_rejected():
    for players in (None,[],example_players()[:10],example_players()+[example_players()[0]],iter(example_players())):
        with pytest.raises(TeamDimensionEngineError,match='exactly 11'):derive(players=players if players is not None else [])
    with pytest.raises(TeamDimensionEngineError):TeamDimensionEngine().derive(None,example_structure())


def test_invalid_member_ids_roles_and_duplicates_rejected():
    variants=[object(),example_players()[0].model_copy(update={'id':''}),example_players()[0].model_copy(update={'role':'GK'})]
    for bad in variants:
        players=example_players();players[0]=bad
        with pytest.raises(TeamDimensionEngineError):derive(players)
    players=example_players();players[1]=players[2]
    with pytest.raises(TeamDimensionEngineError,match='duplicate'):derive(players)


def test_zero_and_multiple_goalkeepers_are_rejected():
    for count in (0,2):
        players=[make_test_player(f'gk_case_{i}',PlayerRole.GK if i<count else PlayerRole.CB) for i in range(11)]
        with pytest.raises(TeamDimensionEngineError,match='exactly one GK'):derive(players)


def test_corrupted_nonfinite_or_out_of_range_consumed_abilities_rejected():
    for value in (float('nan'),float('inf'),float('-inf'),-1.,101.,True,'80',None):
        players=example_players();players[9]=players[9].model_copy(update={'attack_ability':value})
        with pytest.raises(TeamDimensionEngineError):derive(players)


def test_wrong_or_corrupted_structure_is_rejected():
    with pytest.raises(TeamDimensionEngineError):TeamDimensionEngine().derive(example_players(),None)
    for value in (float('nan'),2.,-1.):
        with pytest.raises(TeamDimensionEngineError):derive(features=example_structure().model_copy(update={'width_feature':value}))


def test_dimension_output_is_immutable():
    result=derive()
    with pytest.raises(ValueError):result.attack=1
