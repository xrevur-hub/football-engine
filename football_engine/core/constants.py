"""
Default V1 parameter priors.

These are the *initial* calibration priors from Section 44 ("Locked
Parameter Priors — Current V1") and T.12 ("Phase 1 Parameter Space").
They are NOT empirical truth — Section 44 explicitly states:

    "همه این مقادیر، به‌جز قوانینی که ساختاری هستند، calibration priors
    محسوب می‌شوند نه truth نهایی."

They exist so that:
  1. The engine is runnable out of the box before any calibration pass.
  2. calibration/optimization code has a documented starting point and
     bound (see PARAMETER_BOUNDS, from T.12).

Do NOT hardcode these values inside formulas in the calculation layer
(Layer 3/4) — always thread a ParameterSet through. This module only
supplies the *default* ParameterSet.
"""

from __future__ import annotations

# --- Global calibration anchors (Section 9) --------------------------------
# "Global averages فقط calibration anchors هستند. مقادیر اولیه نمونه 78 بودند."
GLOBAL_AVG_ATTACK = 78.0
GLOBAL_AVG_CREATION = 78.0
GLOBAL_AVG_DEFENSE = 78.0
GLOBAL_AVG_GK = 78.0

# --- Section 44 / T.12 — Free (optimizable) parameters ----------------------
DEFAULT_K_GK = 0.10
DEFAULT_K_POSS_CALC = 1.5
DEFAULT_K_P = 0.40
DEFAULT_K_W = 0.20
DEFAULT_K_TE = 0.15
DEFAULT_K_T = 0.50
DEFAULT_K_T2 = 0.50
DEFAULT_BASELINE = 1.35
DEFAULT_TRANSITION_WEIGHT = 0.55
DEFAULT_H_HOME = 1.10
DEFAULT_A_AWAY = 0.95
DEFAULT_K_FORM = 0.15
DEFAULT_RHO = -0.13

# --- T.12 bounds for the free parameters (used by calibration, Layer 7) ----
PARAMETER_BOUNDS: dict[str, tuple[float, float]] = {
    "k_p": (0.10, 0.80),
    "k_w": (0.00, 0.50),
    "k_te": (0.00, 0.40),
    "k_t2": (0.10, 1.00),
    "k_poss_calc": (0.50, 3.00),
    "k_gk": (0.00, 0.30),
    "baseline": (0.80, 1.80),
    "transition_weight": (0.20, 1.00),
    "h_home": (1.00, 1.25),
    "a_away": (0.75, 1.00),
    "rho": (-0.30, 0.00),
}

# --- T.13 — Parameters fixed in Phase 1 (not identifiable from λ-based NLL) -
DEFAULT_CONVERSION_PRIOR = 0.10  # Q.2 — shot generation
DEFAULT_P_OFF_TARGET = 0.40  # Q.4 — saves
DEFAULT_K_YC = 0.15  # Q.5 — yellow cards
DEFAULT_K_RC = 0.012  # Q.7 — red cards
DEFAULT_P_ASSIST_EXISTS = 0.75  # R.4 — assist probability

# --- Role weight tables (Section R.3 / R.4) ---------------------------------
# NOTE: kept here (not on PlayerRole enum) because they are calibration-
# adjacent priors, not structural facts about the enum itself.
ROLE_ATTACK_WEIGHT: dict[str, float] = {
    "FW": 1.00,
    "AM": 0.75,
    "WM": 0.55,
    "CM": 0.40,
    "FB": 0.12,
    "DM": 0.15,
    "CB": 0.08,
    "GK": 0.00,
}

ROLE_CREATION_WEIGHT: dict[str, float] = {
    "AM": 1.00,
    "WM": 0.85,
    "CM": 0.80,
    "FW": 0.50,
    "FB": 0.35,
    "DM": 0.25,
    "CB": 0.08,
    "GK": 0.00,
}

# --- V2 priors, defined now so ParameterSet schema doesn't break later ------
DEFAULT_R_CARD = 0.75  # Q.7 — red card λ modifier (V2 only, inert in V1)

# --- Section S.3 — canonical segment schedule -------------------------------
SEGMENT_SCHEDULE: list[tuple[int, int, int]] = [
    # (segment_id, start_minute, end_minute)
    (1, 0, 30),
    (2, 30, 60),
    (3, 60, 75),
    (4, 75, 90),
]

# --- Section 26.2 — DC vs Poisson sampling threshold ------------------------
DC_MIN_DURATION_MINUTES = 15

# --- Section 23 — scoreline grid for DC normalization -----------------------
DC_MAX_GOALS_GRID = 8

# --- Invariant 9 / Q.7 — legal football minimum -----------------------------
MIN_PLAYER_COUNT = 7
MAX_PLAYER_COUNT = 11

# --- Q.6 — substitution rules ------------------------------------------------
MAX_SUBSTITUTIONS_PER_TEAM = 3
