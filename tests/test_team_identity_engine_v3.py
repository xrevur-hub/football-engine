"""Identity component math plus explicit, non-default possession boundaries."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from fractions import Fraction as F
import math

import pytest

from football_engine.core.enums import PlayerRole, HistoricalTier
from football_engine.core.team_season import HistoricalPrior, IdentityPriors
from football_engine.team_model import TeamIdentityEngine, TeamIdentityEngineError, TeamIdentitySpecificationGapError
from football_engine.team_model.role_weight_priors import IDENTITY_ROLE_WEIGHT_PRIORS as W
from tests.layer2_memo_v3_helpers import example_players, example_structure, example_prior, example_identity, example_source, reference
from tests.team_model_helpers import make_test_player

EXPECTED={
 'GK':(0,0,.05,0,0),'CB':(.30,.10,.20,.05,0),'FB':(.50,.40,.30,.15,.20),'DM':(.60,.20,.30,.10,0),
 'CM':(.55,.30,.35,.25,.10),'WM':(.45,.60,.30,.45,.60),'AM':(.35,.45,.35,.55,.50),'FW':(.25,.55,.25,.75,1),
}


def test_identity_weight_tables_and_all_eight_roles():
    assert set(W)==set(PlayerRole)
    for role,values in EXPECTED.items():
        row=W[PlayerRole[role]]
        assert (row.press,row.transition,row.tempo,row.risk,row.attack_pace)==values


def test_identity_weight_tables_are_immutable():
    with pytest.raises(TypeError):W[PlayerRole.GK]=W[PlayerRole.FW]
    with pytest.raises(FrozenInstanceError):W[PlayerRole.GK].tempo=0


def test_exact_pre_prior_identity_matches_independent_reference():
    result=example_identity().model_dump()
    for key,expected in reference()['expected_pre_prior_identity'].items():
        assert result[key]==pytest.approx(expected,abs=1e-12)
    players=example_players()
    for column,(key,attribute) in enumerate([('press_tendency','press_tendency'),('transition_tendency','transition_tendency'),('tempo','pace'),('risk_tolerance','shot_tendency'),('attack_pace_factor','pace')]):
        weights=[F(str(EXPECTED[p.role.name][column])) for p in players]
        exact=sum((weight*F(str(getattr(p,attribute))) for weight,p in zip(weights,players)),F(0))/sum(weights,F(0))
        assert result[key]==pytest.approx(float(exact),abs=1e-12)


def test_missing_source_is_named_specification_gap_not_default():
    with pytest.raises(TeamIdentitySpecificationGapError,match='possession_tendency'):
        TeamIdentityEngine().derive(example_players(),example_structure(),None)
    assert issubclass(TeamIdentitySpecificationGapError,NotImplementedError)


def test_prior_even_at_alpha_zero_does_not_replace_missing_source():
    for alpha in (0.,.55,1.):
        prior=example_prior().model_copy(update={'alpha':alpha})
        with pytest.raises(TeamIdentitySpecificationGapError):
            TeamIdentityEngine().derive(example_players(),example_structure(),prior)


def test_invalid_noncallable_source_is_rejected():
    for source in (0.,.5,{},'lookup'):
        with pytest.raises(TeamIdentityEngineError):TeamIdentityEngine(possession_source=source)


def test_invalid_source_outputs_are_not_coerced_or_clamped():
    for value in (None,True,False,'0.62',float('nan'),float('inf'),-.01,1.01):
        def source(*,player_season_ids):return value
        with pytest.raises(TeamIdentityEngineError,match='possession source result'):
            TeamIdentityEngine(possession_source=source).derive(example_players(),example_structure(),None)


def test_source_values_at_both_boundaries_are_valid_not_missing():
    for value in (0.,1.):
        source=example_source(value=value)
        result=TeamIdentityEngine(possession_source=source).derive(example_players(),example_structure(),None)
        assert result.possession_tendency==value


def test_source_exceptions_propagate_without_fallback():
    def absent(*,player_season_ids):raise LookupError('missing observation')
    with pytest.raises(LookupError,match='missing observation'):
        TeamIdentityEngine(possession_source=absent).derive(example_players(),example_structure(),example_prior())


def test_source_receives_only_sorted_immutable_ids_once():
    players=list(reversed(example_players()));calls=[]
    def source(*,player_season_ids):
        assert isinstance(player_season_ids,tuple)
        assert all(isinstance(value,str) for value in player_season_ids)
        assert player_season_ids==tuple(sorted(p.id for p in players))
        calls.append(player_season_ids)
        return .62
    before=[p.model_dump() for p in players]
    TeamIdentityEngine(possession_source=source).derive(players,example_structure(),None)
    assert len(calls)==1
    assert [p.model_dump() for p in players]==before


def test_same_engine_queries_distinct_rosters_not_a_cached_value():
    a=example_players();b=[p.model_copy(update={'id':'other_'+p.id}) for p in a]
    lookup={tuple(sorted(p.id for p in a)):.2,tuple(sorted(p.id for p in b)):.8}
    def source(*,player_season_ids):return lookup[player_season_ids]
    engine=TeamIdentityEngine(possession_source=source)
    assert engine.derive(a,example_structure(),None).possession_tendency==.2
    assert engine.derive(b,example_structure(),None).possession_tendency==.8
    assert engine.derive(a,example_structure(),None).possession_tendency==.2
    assert set(vars(engine))=={'_possession_source'}


def test_source_not_called_for_invalid_input_or_zero_denominator():
    calls=[]
    def source(*,player_season_ids):calls.append(player_season_ids);return .62
    engine=TeamIdentityEngine(possession_source=source)
    with pytest.raises(TeamIdentityEngineError):engine.derive(example_players()[:10],example_structure(),None)
    players=[make_test_player(f'zero_{i}',PlayerRole.GK if i==0 else PlayerRole.CB) for i in range(11)]
    with pytest.raises(TeamIdentityEngineError,match='attack_pace_factor.*zero role-weight denominator'):
        engine.derive(players,example_structure(),None)
    assert calls==[]


def test_player_order_and_repeated_calculation_are_exactly_invariant():
    players=example_players();engine=TeamIdentityEngine(possession_source=example_source(players));features=example_structure()
    expected=engine.derive(players,features,None)
    for shift in range(11):assert engine.derive(players[shift:]+players[:shift],features,None)==expected
    assert engine.derive(list(reversed(players)),features,None)==expected


def test_zero_midpoint_and_one_tendencies_are_convex_and_finite():
    for value in (0.,.37,1.):
        players=[p.model_copy(update=dict(press_tendency=value,transition_tendency=value,shot_tendency=value,pace=value)) for p in example_players()]
        result=example_identity(players)
        for name in ('press_tendency','transition_tendency','tempo','risk_tolerance','attack_pace_factor'):
            assert getattr(result,name)==pytest.approx(value,abs=1e-15)
        assert all(math.isfinite(v) and 0<=v<=1 for v in result.model_dump().values())


def test_player_abilities_and_attribution_metadata_do_not_feed_identity():
    players=example_players();expected=example_identity(players)
    changed=[p.model_copy(update=dict(attack_ability=100,creation_ability=0,defense_ability=100,gk_ability=0,discipline_score=0,impact_score=1)) for p in players]
    assert example_identity(changed)==expected


def test_press_transition_and_shot_changes_affect_only_their_local_component():
    players=example_players();base=example_identity(players).model_dump();index=6
    for attribute,output,column in [('press_tendency','press_tendency','press'),('transition_tendency','transition_tendency','transition'),('shot_tendency','risk_tolerance','risk')]:
        changed=list(players);changed[index]=players[index].model_copy(update={attribute:getattr(players[index],attribute)+.1})
        actual=example_identity(changed).model_dump()
        delta=.1*getattr(W[players[index].role],column)/math.fsum(getattr(W[p.role],column) for p in players)
        assert actual[output]-base[output]==pytest.approx(delta,abs=1e-12)
        for key in base:
            if key!=output:assert actual[key]==base[key]


def test_cb_pace_changes_tempo_but_not_attack_pace():
    players=example_players();base=example_identity(players)
    changed=list(players);changed[1]=players[1].model_copy(update={'pace':players[1].pace+.1})
    result=example_identity(changed)
    assert result.tempo>base.tempo
    assert result.attack_pace_factor==base.attack_pace_factor


def test_fb_pace_changes_both_scopes_as_table_requires():
    players=example_players();base=example_identity(players)
    changed=list(players);changed[3]=players[3].model_copy(update={'pace':players[3].pace+.1})
    result=example_identity(changed)
    assert result.tempo>base.tempo and result.attack_pace_factor>base.attack_pace_factor
    for column,name in [('tempo','tempo'),('attack_pace','attack_pace_factor')]:
        delta=.1*getattr(W[PlayerRole.FB],column)/math.fsum(getattr(W[p.role],column) for p in players)
        assert getattr(result,name)-getattr(base,name)==pytest.approx(delta,abs=1e-12)


def test_gk_pace_is_included_in_tempo_but_not_other_means():
    players=example_players();base=example_identity(players).model_dump()
    changed=list(players);changed[0]=players[0].model_copy(update={'pace':.9})
    actual=example_identity(changed).model_dump()
    assert actual['tempo']>base['tempo']
    for key in base:
        if key!='tempo':assert actual[key]==base[key]


def test_only_c_and_u_have_local_structural_effects():
    features=example_structure();base=example_identity(structure=features).model_dump()
    for key,value in [('width_feature',.1),('line_height_feature',.9),('press_structure_feature',.8),('transition_structure_feature',.1),('cb_pairing_quality',.1),('fullback_exposure',.9),('formation_name','no name semantics')]:
        assert example_identity(structure=features.model_copy(update={key:value})).model_dump()==base
    for field,output in [('defensive_cover_feature','compactness'),('build_up_structure_feature','build_up_control_score')]:
        actual=example_identity(structure=features.model_copy(update={field:.9})).model_dump()
        assert actual[output]==.9
        for key in base:
            if key!=output:assert actual[key]==base[key]


def test_existing_prior_blend_matches_all_six_fields_and_two_passthroughs():
    result=example_identity(prior=example_prior()).model_dump()
    for key,expected in reference()['expected_final_identity'].items():
        assert result[key]==pytest.approx(expected,abs=1e-12)
    assert result['compactness']!=example_structure().defensive_cover_feature
    assert result['build_up_control_score']==example_structure().build_up_structure_feature


def test_none_tier3_and_partial_priors_preserve_existing_behavior():
    players=example_players();features=example_structure();engine=TeamIdentityEngine(possession_source=example_source(players))
    base=engine.derive(players,features,None)
    tier3=HistoricalPrior(tier=HistoricalTier.TIER_3,alpha=1.)
    assert engine.derive(players,features,tier3)==base
    partial=HistoricalPrior(tier=HistoricalTier.TIER_1,alpha=.5,identity_priors=IdentityPriors(possession_tendency=.9))
    actual=engine.derive(players,features,partial).model_dump()
    assert actual['possession_tendency']==pytest.approx(.5*.62+.5*.9)
    for key,value in base.model_dump().items():
        if key!='possession_tendency':assert actual[key]==value


def test_invalid_numeric_player_fields_rejected_without_source_fallback():
    for value in (float('nan'),float('inf'),-.01,1.01,True,'0.5'):
        players=example_players();players[9]=players[9].model_copy(update={'pace':value})
        with pytest.raises(TeamIdentityEngineError):example_identity(players)


def test_invalid_prior_numeric_values_rejected_before_blend():
    for value in (float('nan'),float('inf'),-.1,1.1,True):
        with pytest.raises(TeamIdentityEngineError):example_identity(prior=example_prior().model_copy(update={'alpha':value}))
    bad=example_prior().model_copy(update={'identity_priors':IdentityPriors.model_construct(possession_tendency=float('nan'))})
    with pytest.raises(TeamIdentityEngineError):example_identity(prior=bad)
    with pytest.raises(TeamIdentityEngineError):example_identity(prior={})


def test_identity_output_and_inputs_are_immutable():
    players=example_players();features=example_structure();prior=example_prior()
    before=[p.model_dump() for p in players];sf=features.model_dump();hp=prior.model_dump()
    result=example_identity(players,features,prior)
    with pytest.raises(ValueError):result.tempo=0
    assert [p.model_dump() for p in players]==before
    assert features.model_dump()==sf and prior.model_dump()==hp
