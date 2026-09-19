"""Module 6 — the exact authorized M/T equations, with explicit helper inputs.

Source of mathematics: FINAL AUTHORIZATION (2026-09-08), formulas 1-11.
No Layer 2 derivation, home advantage, form, probability model, or sampling.

PossessionShare is evaluated independently for each ordered direction, using
TacticalProfile.possession_tendency_final (the actual state-adjusted core
field). The quoted expression is NOT antisymmetric, so silently setting the
other direction to 1-share or normalizing the pair would change the formula.

Three missing canonical helper equations are NOT implemented here:
PressDisruption_M, WidthMismatch, PressTransitionOpportunity_T. Their distinct
outputs must be explicitly supplied, independently for both directions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from football_engine.core.matchup import MatchupResult
from football_engine.core.parameters import ParameterSet
from football_engine.core.tactical_profile import TacticalProfile
from football_engine.core.team_dimensions import TeamDimensions
from football_engine.matchup._validation import (
    finite_number,
    nonnegative,
    positive,
    unit_interval,
)
from football_engine.matchup.configuration import (
    DEFAULT_LAYER3_COEFFICIENTS,
    Layer3Coefficients,
)
from football_engine.matchup.dependencies import DirectionalMatchupHelpers
from football_engine.matchup.errors import Layer3InputError, SpecificationGapError


def sigmoid(value: float) -> float:
    """1 / (1 + exp(-value)), evaluated without exponential overflow."""
    value = finite_number("sigmoid input", value)
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def gk_factor(defender: TeamDimensions, parameters: ParameterSet) -> float:
    average = positive("GlobalAvgGK", parameters.global_avg_gk)
    keeper = nonnegative("GK_B", defender.goalkeeping)
    k_gk = nonnegative("k_gk", parameters.k_gk)
    return nonnegative("GK_Factor", 1.0 - k_gk * (keeper - average) / average)


def base_relative_strength(
    attacker: TeamDimensions,
    defender: TeamDimensions,
    parameters: ParameterSet,
) -> float:
    attack_average = positive("GlobalAvgAttack", parameters.global_avg_attack)
    defense_average = positive("GlobalAvgDefense", parameters.global_avg_defense)
    attack = nonnegative("Attack_A", attacker.attack)
    defense = positive("Defense_B", defender.defense)
    relative_defense = positive("Defense_B / GlobalAvgDefense", defense / defense_average)
    return nonnegative(
        "BaseRelativeStrength",
        (attack / attack_average) / relative_defense * gk_factor(defender, parameters),
    )


def possession_share(
    attacker: TacticalProfile,
    defender: TacticalProfile,
    parameters: ParameterSet,
) -> float:
    a_poss = unit_interval("A.possession_tendency_final", attacker.possession_tendency_final)
    b_poss = unit_interval("B.possession_tendency_final", defender.possession_tendency_final)
    build_up = unit_interval("A.build_up_control_score", attacker.build_up_control_score)
    press = unit_interval("B.press_final", defender.press_final)
    k_poss = finite_number("k_poss_calc", parameters.k_poss_calc)
    return sigmoid(k_poss * (a_poss - b_poss + build_up - press))


def creation_realization(
    possession: float,
    coefficients: Layer3Coefficients = DEFAULT_LAYER3_COEFFICIENTS,
) -> float:
    possession = unit_interval("PossessionShare", possession)
    return nonnegative(
        "CreationRealization",
        coefficients.creation_realization_offset
        + coefficients.creation_realization_possession_weight * possession,
    )


def creation_factor(
    attacker: TeamDimensions,
    possession: float,
    parameters: ParameterSet,
    coefficients: Layer3Coefficients = DEFAULT_LAYER3_COEFFICIENTS,
) -> float:
    average = positive("GlobalAvgCreation", parameters.global_avg_creation)
    creation = nonnegative("Creation_A", attacker.creation)
    return nonnegative(
        "CreationFactor",
        (
            coefficients.creation_factor_offset
            + coefficients.creation_factor_creation_weight * creation / average
        )
        * creation_realization(possession, coefficients),
    )


def adjusted_base(base_strength: float, creation: float) -> float:
    return nonnegative(
        "AdjustedBase",
        nonnegative("BaseRelativeStrength", base_strength)
        * nonnegative("CreationFactor", creation),
    )


def press_interaction(
    press_disruption_m_defender_to_attacker: float,
    parameters: ParameterSet,
) -> float:
    disruption = finite_number("PressDisruption_M", press_disruption_m_defender_to_attacker)
    k_p = finite_number("k_p", parameters.k_p)
    return nonnegative("I_press", 1.0 - k_p * disruption)


def width_interaction(
    width_mismatch_attacker_to_defender: float,
    parameters: ParameterSet,
) -> float:
    mismatch = finite_number("WidthMismatch", width_mismatch_attacker_to_defender)
    k_w = finite_number("k_w", parameters.k_w)
    return nonnegative("I_width", 1.0 + k_w * mismatch)


def tempo_interaction(attacker: TacticalProfile, parameters: ParameterSet) -> float:
    tempo = unit_interval("A.tempo_final", attacker.tempo_final)
    k_te = finite_number("k_te", parameters.k_te)
    return nonnegative("I_tempo", 1.0 + k_te * tempo)


def organized_attack(adjusted: float, press: float, width: float, tempo: float) -> float:
    return nonnegative(
        "M",
        nonnegative("AdjustedBase", adjusted)
        * nonnegative("I_press", press)
        * nonnegative("I_width", width)
        * nonnegative("I_tempo", tempo),
    )


def space_behind_defense(defender: TacticalProfile) -> float:
    line = unit_interval("B.line_final", defender.line_final)
    cover = unit_interval("B.defensive_cover_feature", defender.defensive_cover_feature)
    return unit_interval("SpaceBehindDefense", line * (1.0 - cover))


def transition_threat(
    attacker: TacticalProfile,
    defender: TacticalProfile,
    press_transition_opportunity_t_defender_to_attacker: float,
    parameters: ParameterSet,
) -> float:
    tendency = unit_interval("A.transition_tendency_final", attacker.transition_tendency_final)
    pace = unit_interval("A.attack_pace_factor", attacker.attack_pace_factor)
    opportunity = finite_number(
        "PressTransitionOpportunity_T", press_transition_opportunity_t_defender_to_attacker
    )
    k_t2 = finite_number("k_t2", parameters.k_t2)
    # No k_t, tempo, width, possession, press quality, or build-up input here.
    # In particular this is NOT PressDisruption_M reused as a transition signal.
    return nonnegative(
        "T",
        tendency * pace * space_behind_defense(defender)
        + opportunity * tendency * k_t2,
    )


@dataclass(frozen=True)
class DirectionalMatchupBreakdown:
    """Read-only diagnostics; not a replacement for any existing core model."""

    gk_factor: float
    base_relative_strength: float
    possession_share: float
    creation_realization: float
    creation_factor: float
    adjusted_base: float
    i_press: float
    i_width: float
    i_tempo: float
    space_behind_defense: float
    m: float
    t: float


@dataclass(frozen=True)
class MatchupEngine:
    parameters: ParameterSet
    coefficients: Layer3Coefficients = DEFAULT_LAYER3_COEFFICIENTS

    def evaluate_direction(
        self,
        attacker_dimensions: TeamDimensions,
        defender_dimensions: TeamDimensions,
        attacker_tactical: TacticalProfile,
        defender_tactical: TacticalProfile,
        *,
        helpers: DirectionalMatchupHelpers | None = None,
    ) -> DirectionalMatchupBreakdown:
        """A -> B, with disruption/opportunity supplied in the B -> A sense."""
        if helpers is None:
            raise SpecificationGapError(
                "Module 6 specification gap: supply separate values for "
                "PressDisruption_M(defender -> attacker), WidthMismatch(attacker, defender), "
                "and PressTransitionOpportunity_T(defender -> attacker). "
                "Their canonical helper equations are absent; no defaults are used."
            )
        if not isinstance(helpers, DirectionalMatchupHelpers):
            raise Layer3InputError("helpers must be DirectionalMatchupHelpers")
        base = base_relative_strength(attacker_dimensions, defender_dimensions, self.parameters)
        share = possession_share(attacker_tactical, defender_tactical, self.parameters)
        realized = creation_realization(share, self.coefficients)
        creation = creation_factor(attacker_dimensions, share, self.parameters, self.coefficients)
        adjusted = adjusted_base(base, creation)
        press = press_interaction(helpers.press_disruption_m, self.parameters)
        width = width_interaction(helpers.width_mismatch, self.parameters)
        tempo = tempo_interaction(attacker_tactical, self.parameters)
        return DirectionalMatchupBreakdown(
            gk_factor=gk_factor(defender_dimensions, self.parameters),
            base_relative_strength=base,
            possession_share=share,
            creation_realization=realized,
            creation_factor=creation,
            adjusted_base=adjusted,
            i_press=press,
            i_width=width,
            i_tempo=tempo,
            space_behind_defense=space_behind_defense(defender_tactical),
            m=organized_attack(adjusted, press, width, tempo),
            t=transition_threat(
                attacker_tactical,
                defender_tactical,
                helpers.press_transition_opportunity_t,
                self.parameters,
            ),
        )

    def calculate(
        self,
        home_dimensions: TeamDimensions,
        away_dimensions: TeamDimensions,
        home_tactical: TacticalProfile,
        away_tactical: TacticalProfile,
        *,
        home_to_away_helpers: DirectionalMatchupHelpers | None = None,
        away_to_home_helpers: DirectionalMatchupHelpers | None = None,
    ) -> MatchupResult:
        """Return the existing four-field M/T model, independently both ways.

        Home/away labels ONLY assign output directions. No venue multiplier,
        form factor, runtime state, or snapshot-quality weight is read here.
        """
        home = self.evaluate_direction(
            home_dimensions, away_dimensions, home_tactical, away_tactical,
            helpers=home_to_away_helpers,
        )
        away = self.evaluate_direction(
            away_dimensions, home_dimensions, away_tactical, home_tactical,
            helpers=away_to_home_helpers,
        )
        return MatchupResult(
            m_home_to_away=home.m,
            m_away_to_home=away.m,
            t_home_to_away=home.t,
            t_away_to_home=away.t,
        )
