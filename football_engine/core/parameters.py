"""
ParameterSet — Section T.20 "Final ParameterSet".

This is the single object that carries every calibration-sensitive
constant through the engine. Calculation functions (Layer 3/4) must take
a ParameterSet argument rather than importing constants directly, so that
calibration (Layer 7) can vary parameters without touching model code.

Architecture reference: Section 44 (Locked Parameter Priors), T.12
(Phase 1 Parameter Space + bounds), T.13 (parameters fixed in Phase 1),
T.20 (Final ParameterSet schema).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from football_engine.core import constants as C


class ParameterSet(BaseModel):
    """
    Bundle of all calibration-sensitive constants.

    Split into three groups, matching T.12/T.13:
      1. Free parameters (Phase 1 — optimizable against match NLL)
      2. Fixed-in-Phase-1 parameters (Q/R layer, not λ-identifiable)
      3. Calibration metadata (T.20 bookkeeping fields)

    All fields have Section-44 default priors so the engine is runnable
    before any calibration has taken place.
    """

    model_config = ConfigDict(frozen=True)

    # --- Phase 1 free parameters (T.12) ------------------------------------
    k_p: float = Field(default=C.DEFAULT_K_P, description="Press impact on I_press")
    k_w: float = Field(default=C.DEFAULT_K_W, description="Width mismatch impact on I_width")
    k_te: float = Field(default=C.DEFAULT_K_TE, description="Tempo effect on I_tempo")
    k_t: float = Field(
        default=C.DEFAULT_K_T,
        description="Base transition/space weight (definition finalized at implementation)",
    )
    k_t2: float = Field(default=C.DEFAULT_K_T2, description="Turnover-to-transition weight in T")
    k_poss_calc: float = Field(
        default=C.DEFAULT_K_POSS_CALC, description="Possession-share sensitivity (sigmoid steepness)"
    )
    k_gk: float = Field(default=C.DEFAULT_K_GK, description="Goalkeeper effect on BaseRelativeStrength")
    baseline: float = Field(default=C.DEFAULT_BASELINE, description="BASELINE_GOALS_PER_MATCH anchor")
    transition_weight: float = Field(
        default=C.DEFAULT_TRANSITION_WEIGHT, description="TRANSITION_GOAL_WEIGHT in lambda_base"
    )
    h_home: float = Field(default=C.DEFAULT_H_HOME, description="Home advantage multiplier H_A")
    a_away: float = Field(default=C.DEFAULT_A_AWAY, description="Away multiplier A_A")
    rho: float = Field(default=C.DEFAULT_RHO, description="Dixon-Coles low-score correction")

    # --- Form (Section 18) --------------------------------------------------
    k_form: float = Field(default=C.DEFAULT_K_FORM, description="Form effect on FormFactor")

    # --- T.13 — fixed in Phase 1 (Q/R layer; not identifiable from λ NLL) --
    conversion_prior: float = Field(default=C.DEFAULT_CONVERSION_PRIOR, description="Q.2 shot generation")
    p_off_target: float = Field(default=C.DEFAULT_P_OFF_TARGET, description="Q.4 saves")
    k_yc: float = Field(default=C.DEFAULT_K_YC, description="Q.5 yellow card rate")
    k_rc: float = Field(default=C.DEFAULT_K_RC, description="Q.7 red card rate")
    p_assist_exists: float = Field(default=C.DEFAULT_P_ASSIST_EXISTS, description="R.4 assist probability")
    r_card: float = Field(
        default=C.DEFAULT_R_CARD,
        description="V2-only red card lambda modifier; inert (unused) in V1",
    )

    # --- Global calibration anchors (Section 9) -----------------------------
    global_avg_attack: float = Field(default=C.GLOBAL_AVG_ATTACK)
    global_avg_creation: float = Field(default=C.GLOBAL_AVG_CREATION)
    global_avg_defense: float = Field(default=C.GLOBAL_AVG_DEFENSE)
    global_avg_gk: float = Field(default=C.GLOBAL_AVG_GK)

    # --- T.20 calibration metadata (all optional — absent for an
    #     un-calibrated, prior-only ParameterSet) -----------------------------
    calibration_date: Optional[date] = None
    train_set: Optional[str] = None
    validation_nll: Optional[float] = None
    holdout_nll: Optional[float] = None
    holdout_brier: Optional[float] = None
    n_train_matches: Optional[int] = None
    n_holdout_matches: Optional[int] = None

    @model_validator(mode="after")
    def _check_bounds(self) -> "ParameterSet":
        """
        Soft validation against T.12 bounds.

        These bounds are calibration search bounds, not hard physical
        constraints — but a ParameterSet wildly outside them is almost
        always a bug (e.g. a unit mix-up), so we fail fast here rather
        than let it silently poison a simulation.
        """
        checks = {
            "k_p": self.k_p,
            "k_w": self.k_w,
            "k_te": self.k_te,
            "k_t2": self.k_t2,
            "k_poss_calc": self.k_poss_calc,
            "k_gk": self.k_gk,
            "baseline": self.baseline,
            "transition_weight": self.transition_weight,
            "h_home": self.h_home,
            "a_away": self.a_away,
            "rho": self.rho,
        }
        for name, value in checks.items():
            lo, hi = C.PARAMETER_BOUNDS[name]
            if not (lo <= value <= hi):
                raise ValueError(
                    f"ParameterSet.{name}={value} outside T.12 bound [{lo}, {hi}]. "
                    "If this is intentional (e.g. exploratory calibration), "
                    "widen PARAMETER_BOUNDS explicitly rather than bypassing this check."
                )
        return self


# A ready-to-use default instance for callers that don't need a custom
# calibration (e.g. tests, examples, uncalibrated V1 runs).
DEFAULT_PARAMETER_SET = ParameterSet()
