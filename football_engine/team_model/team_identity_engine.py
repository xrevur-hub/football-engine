"""Module 3 — specified V3 mathematics with an explicit possession-source gap.

Five role-weighted player components plus C/U proxies are implemented using
V2's numerical tables. They are uncalibrated modeling proxies, not proof of
causal independence or complete downstream tactical/state specifications.

A caller must explicitly inject an independent, preloaded possession source.
No ability-based/press-based proxy, neutral constant, or prior-only fallback
is invented. Default use therefore raises a named specification-gap error.
With a valid source, return a full eight-field pre-prior identity and call
existing historical-prior blending exactly once. Core models and the public
three-argument derive call shape are unchanged; the dependency is configured
at engine construction and the existing builder injection accepts it.
"""
from __future__ import annotations

from football_engine.core.player_season import PlayerSeason
from football_engine.core.team_dimensions import StructuralFeatures
from football_engine.core.team_identity import TeamIdentity
from football_engine.core.team_season import HistoricalPrior, apply_historical_prior_to_identity
from football_engine.team_model._validation import bounded_number, validated_players
from football_engine.team_model._weighted_mean import role_weighted_mean
from football_engine.team_model.dependencies import PossessionTendencySource
from football_engine.team_model.role_weight_priors import IDENTITY_ROLE_WEIGHT_PRIORS


class TeamIdentityEngineError(ValueError):
    """Invalid inputs, denominator, source configuration, or source result."""


class TeamIdentitySpecificationGapError(NotImplementedError):
    """No explicit source exists for the still-unspecified possession input."""


def _derive_pre_prior_identity(
    players: tuple[PlayerSeason, ...],
    structural_features: StructuralFeatures,
    possession_source: PossessionTendencySource,
) -> TeamIdentity:
    def mean(attribute: str, column: str, output: str) -> float:
        return role_weighted_mean(
            players, attribute=attribute,
            weight_for_role=lambda role: getattr(IDENTITY_ROLE_WEIGHT_PRIORS[role], column),
            field_name=output, upper=1.0, error_type=TeamIdentityEngineError,
        )

    components = {
        "press_tendency": mean("press_tendency", "press", "press_tendency"),
        "transition_tendency": mean("transition_tendency", "transition", "transition_tendency"),
        "tempo": mean("pace", "tempo", "tempo"),
        "risk_tolerance": mean("shot_tendency", "risk", "risk_tolerance"),
        "attack_pace_factor": mean("pace", "attack_pace", "attack_pace_factor"),
        "compactness": bounded_number(structural_features.defensive_cover_feature,
                                        label="C", upper=1.0, error_type=TeamIdentityEngineError),
        "build_up_control_score": bounded_number(structural_features.build_up_structure_feature,
                                                  label="U", upper=1.0, error_type=TeamIdentityEngineError),
    }
    # Validated/sorted immutable IDs only; do not expose abilities, priors,
    # structure, opponent, or runtime objects through this dependency.
    value = possession_source(player_season_ids=tuple(player.id for player in players))
    components["possession_tendency"] = bounded_number(
        value, label="possession source result", upper=1.0, error_type=TeamIdentityEngineError,
    )
    return TeamIdentity(**components)


class TeamIdentityEngine:
    """Stateless per-team computation with a configured external data source.

    The only stored object is the caller-supplied dependency, never a cached
    team identity or mutable match state. Source purity is a caller contract.
    """

    def __init__(self, *, possession_source: PossessionTendencySource | None = None) -> None:
        if possession_source is not None and not callable(possession_source):
            raise TeamIdentityEngineError("possession_source must be callable or None")
        self._possession_source = possession_source

    def derive(self, players: list[PlayerSeason], structural_features: StructuralFeatures,
               historical_prior: HistoricalPrior | None) -> TeamIdentity:
        selected = validated_players(players, structural_features,
                                     error_type=TeamIdentityEngineError,
                                     engine_name="TeamIdentityEngine")
        if historical_prior is not None:
            if not isinstance(historical_prior, HistoricalPrior):
                raise TeamIdentityEngineError("historical_prior must be a HistoricalPrior or None")
            try:
                HistoricalPrior.model_validate(historical_prior.model_dump())
            except (ValueError, TypeError, AttributeError) as exc:
                raise TeamIdentityEngineError(f"Invalid HistoricalPrior: {exc}") from exc
            bounded_number(historical_prior.alpha, label="HistoricalPrior.alpha",
                           upper=1.0, error_type=TeamIdentityEngineError)
            for name, value in historical_prior.identity_priors.model_dump().items():
                if value is not None:
                    bounded_number(value, label=f"IdentityPriors.{name}",
                                   upper=1.0, error_type=TeamIdentityEngineError)
        if self._possession_source is None:
            raise TeamIdentitySpecificationGapError(
                "Cannot build a pre-prior TeamIdentity: possession_tendency has no approved "
                "automatic estimator in the current PlayerSeason schema. Supply an explicit "
                "PossessionTendencySource with independently established pre-prior data. "
                "No neutral, ability/press proxy, or historical-prior fallback is used."
            )
        derived = _derive_pre_prior_identity(selected, structural_features, self._possession_source)
        return apply_historical_prior_to_identity(derived, historical_prior)
