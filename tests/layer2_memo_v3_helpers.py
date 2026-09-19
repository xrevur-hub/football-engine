"""Fully labeled synthetic V3 fixtures; never a production possession source."""
from __future__ import annotations

import json
from pathlib import Path

from football_engine.core.enums import PlayerRole, HistoricalTier
from football_engine.core.formation import Formation, PositionSlot, SlotSide, SlotDepth
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_season import HistoricalPrior, IdentityPriors, DimensionAdjustment
from football_engine.team_model import FormationEngine, TeamIdentityEngine


def reference():
    return json.loads((Path(__file__).parent/'fixtures/layer2_memo_v3_example.json').read_text())


def example_players():
    return [PlayerSeason(**dict(item, role=PlayerRole[item['role']])) for item in reference()['players']]


def example_formation():
    record=reference()['formation']
    return Formation(name=record['name'], position_pool=[
        PositionSlot(**dict(slot, role=PlayerRole[slot['role']], side=SlotSide(slot['side']), depth=SlotDepth(slot['depth'])))
        for slot in record['position_pool']
    ])


def example_structure():
    return FormationEngine().derive(example_players(), example_formation())


def example_prior():
    record=reference()['prior']
    return HistoricalPrior(tier=HistoricalTier(record['tier']), alpha=record['alpha'],
                           identity_priors=IdentityPriors(**record['identity_priors']),
                           dimension_adjustment=DimensionAdjustment(**record['dimension_adjustment']))


def example_source(players=None, value=None):
    """Explicit fixture observation for exactly one roster, not a fallback."""
    selected=players if players is not None else example_players()
    key=tuple(sorted(player.id for player in selected))
    observed=reference()['explicit_pre_prior_possession'] if value is None else value
    def source(*, player_season_ids):
        if player_season_ids != key:
            raise LookupError('No synthetic observation for that roster')
        return observed
    return source


def example_identity(players=None, structure=None, prior=None):
    selected=example_players() if players is None else players
    features=example_structure() if structure is None else structure
    return TeamIdentityEngine(possession_source=example_source(selected)).derive(selected, features, prior)
