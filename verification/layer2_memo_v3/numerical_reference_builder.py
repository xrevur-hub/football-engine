from pathlib import Path
from fractions import Fraction as F
import json
import sys

work=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
work.mkdir(parents=True,exist_ok=True)
# Fully specified synthetic example, not reconstructed historical player data.
rows=[
 ('GK',10,30,35,85,.02,.10,.15,.30,'center','back'),
 ('CB',20,35,84,0,.10,.40,.20,.45,'left','back'),
 ('CB',25,40,82,0,.12,.45,.25,.50,'right','back'),
 ('FB',45,65,72,0,.30,.65,.50,.75,'left','back'),
 ('FB',50,60,70,0,.35,.60,.55,.80,'right','back'),
 ('DM',35,70,78,0,.20,.70,.30,.55,'center','mid'),
 ('CM',60,80,65,0,.45,.65,.45,.65,'left','mid'),
 ('AM',75,90,40,0,.60,.50,.55,.70,'right','mid'),
 ('WM',82,78,38,0,.70,.55,.75,.90,'left','front'),
 ('FW',90,68,25,0,.90,.40,.70,.85,'center','front'),
 ('FW',86,72,30,0,.85,.45,.80,.95,'right','front'),
]
dw={'GK':(0,0,0),'CB':(.05,.10,1),'FB':(.15,.35,.65),'DM':(.10,.45,.55),'CM':(.25,.70,.35),'WM':(.65,.55,.15),'AM':(.55,.85,.10),'FW':(1,.30,.05)}
iw={'GK':(0,0,.05,0,0),'CB':(.30,.10,.20,.05,0),'FB':(.50,.40,.30,.15,.20),'DM':(.60,.20,.30,.10,0),'CM':(.55,.30,.35,.25,.10),'WM':(.45,.60,.30,.45,.60),'AM':(.35,.45,.35,.55,.50),'FW':(.25,.55,.25,.75,1)}
players=[];slots=[]
for i,r in enumerate(rows):
 role,a,c,d,g,shot,press,trans,pace,side,depth=r
 players.append(dict(id=f'memo_p{i:02}',name=f'Synthetic {role} {i}',season='synthetic-v3',role=role,attack_ability=a,creation_ability=c,defense_ability=d,gk_ability=g,shot_tendency=shot,press_tendency=press,transition_tendency=trans,pace=pace,discipline_score=.5,impact_score=.5))
 slots.append(dict(slot_id=f'memo_slot_{i:02}',role=role,side=side,depth=depth))
def weighted(table,column,attribute):
 weights=[F(str(table[p['role']][column])) for p in players]
 return sum((w*F(str(p[attribute])) for w,p in zip(weights,players)),F(0))/sum(weights,F(0))
dim={name:weighted(dw,i,attr) for i,(name,attr) in enumerate([('attack','attack_ability'),('creation','creation_ability'),('defense','defense_ability')])}
dim['goalkeeping']=F(85)
identity={name:weighted(iw,i,attr) for i,(name,attr) in enumerate([('press_tendency','press_tendency'),('transition_tendency','transition_tendency'),('tempo','pace'),('risk_tolerance','shot_tendency'),('attack_pace_factor','pace')])}
identity.update(possession_tendency=F(62,100),compactness=F(1,2),build_up_control_score=F(8,25))
prior=dict(tier=1,alpha=.55,identity_priors=dict(possession_tendency=.95,press_tendency=.90,transition_tendency=.25,tempo=.70,risk_tolerance=.50,compactness=.75),dimension_adjustment=dict(creation=.03))
post_i={key:(F(55,100)*value+F(45,100)*F(str(prior['identity_priors'][key])) if key in prior['identity_priors'] else value) for key,value in identity.items()}
post_d=dict(dim);post_d['creation']+=F(45,100)*F(3)
result=dict(provenance='Synthetic 11-player arithmetic/contract fixture; NOT real historical data',players=players,formation=dict(name='Synthetic 4-3-3 (all role types)',position_pool=slots),explicit_pre_prior_possession=.62,prior=prior,expected_structure=dict(width_feature=.8,line_height_feature=.5,defensive_cover_feature=.5,press_structure_feature=.28,build_up_structure_feature=.32,transition_structure_feature=.84),expected_dimensions={k:float(v) for k,v in dim.items()},expected_pre_prior_identity={k:float(v) for k,v in identity.items()},expected_final_dimensions={k:float(v) for k,v in post_d.items()},expected_final_identity={k:float(v) for k,v in post_i.items()},exact_fraction_reference={k:{n:str(v) for n,v in values.items()} for k,values in [('dimensions',dim),('identity',identity),('final_dimensions',post_d),('final_identity',post_i)]})
(work/'eleven_player_example.json').write_text(json.dumps(result,indent=2)+'\n')
for group in ('expected_dimensions','expected_pre_prior_identity','expected_final_dimensions','expected_final_identity'):
 print(group, result[group])
print('Weight counts: 72 displayed entries; 55 adjustable positive mean weights; 47 scale-normalized ratios if topology is fixed; 0 fitted parameters in this delivery.')
