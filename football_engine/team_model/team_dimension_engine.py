"""Module 2 — D1 from the user-supplied V2 memo and corrected V3 baseline.

Attack/Creation/Defense are independent role-weighted ability means [0,100].
Goalkeeping is the unique selected GK's ability. These immutable uncalibrated
Layer 2 weights are separate from Section R attribution weights.

D1 validates but does not numerically use StructuralFeatures. For a fixed
squad/role assignment it is invariant to formation geometry: this is an
explicit V1 simplification, not a claim of implemented formation bonuses.
No historical prior, opponent, runtime, RNG, or lambda enters this engine.
The existing builder applies the unchanged dimension-prior adjustment once.
"""
from __future__ import annotations

from football_engine.core.enums import PlayerRole
from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import StructuralFeatures, TeamDimensions
from football_engine.team_model._validation import bounded_number, validated_players
from football_engine.team_model._weighted_mean import role_weighted_mean
from football_engine.team_model.role_weight_priors import DIMENSION_ROLE_WEIGHT_PRIORS


class TeamDimensionEngineError(ValueError):
    """Invalid selection, numeric input, structure, or aggregation denominator."""


class TeamDimensionEngine:
    """Stateless D1 derivation of the four pre-prior team dimensions."""

    def derive(self, players: list[PlayerSeason],
               structural_features: StructuralFeatures) -> TeamDimensions:
        selected = validated_players(players, structural_features,
                                     error_type=TeamDimensionEngineError,
                                     engine_name="TeamDimensionEngine")

        def mean(attribute: str, weight_column: str, output: str) -> float:
            return role_weighted_mean(
                selected, attribute=attribute,
                weight_for_role=lambda role: getattr(DIMENSION_ROLE_WEIGHT_PRIORS[role], weight_column),
                field_name=output, upper=100.0, error_type=TeamDimensionEngineError,
            )

        keeper = next(player for player in selected if player.role == PlayerRole.GK)
        return TeamDimensions(
            attack=mean("attack_ability", "attack", "attack"),
            creation=mean("creation_ability", "creation", "creation"),
            defense=mean("defense_ability", "defense", "defense"),
            goalkeeping=bounded_number(keeper.gk_ability, label="selected GK.gk_ability",
                                       upper=100.0, error_type=TeamDimensionEngineError),
        )
