"""
Liquid Cv sizing equations.
============================
Implements IEC 60534-2-1:2011, Clause 5.1 (Equations 4.1 – 4.7 from Step A3).

All inputs must be in SI units (bar abs, m³/h, mm).
N1 = 0.865 is used throughout (SI: Q in m³/h, ΔP in bar).

Functions
---------
calc_FF              → Liquid critical pressure ratio factor (Eq 4.1)
calc_delta_P_max     → Maximum effective ΔP for liquid (Eq 4.2)
is_choked_liquid     → Choked flow decision gate (Eq 4.3)
cv_liquid_non_choked → Cv for non-choked liquid (Eq 4.4 / 4.5)
cv_liquid_choked     → Cv for choked liquid (Eq 4.6 / 4.7)
cv_liquid            → Master dispatcher: selects correct equation branch
"""

from __future__ import annotations

import math

from backend.constants import SI_N
from backend.models import HardConstraintViolation

_N1 = SI_N["N1"]   # 0.865  (Q in m³/h, ΔP in bar)


# ---------------------------------------------------------------------------
# LIQUID CRITICAL PRESSURE RATIO FACTOR  FF
# ---------------------------------------------------------------------------

def calc_FF(Pv_bar: float, Pc_bar: float) -> float:
    """
    Liquid critical pressure ratio factor FF.

    Equation 4.1 (IEC 60534-2-1, Clause 5.1):
        FF = 0.96 − 0.28 × √(Pv / Pc)

    Physical meaning: FF defines the fraction of P1 above which the
    vena contracta pressure cannot fall before the fluid vaporises completely.

    Parameters
    ----------
    Pv_bar : float  Vapour pressure at T1 [bar abs].
    Pc_bar : float  Thermodynamic critical pressure [bar abs].

    Returns
    -------
    float
        FF ∈ [0.50, 0.96].
    """
    if Pc_bar <= 0:
        raise HardConstraintViolation("ERR_INVALID_PC", "Critical pressure Pc must be positive.")
    if Pv_bar < 0:
        raise HardConstraintViolation("ERR_NEGATIVE_PV", "Vapour pressure Pv must be ≥ 0.")
    if Pv_bar >= Pc_bar:
        raise HardConstraintViolation(
            "ERR_INVALID_PC_PV",
            f"Vapour pressure Pv ({Pv_bar:.3f} bar) must be less than Pc ({Pc_bar:.3f} bar)."
        )
    FF = 0.96 - 0.28 * math.sqrt(Pv_bar / Pc_bar)
    return max(0.50, min(FF, 0.96))


# ---------------------------------------------------------------------------
# MAXIMUM EFFECTIVE DIFFERENTIAL PRESSURE  ΔP_max
# ---------------------------------------------------------------------------

def calc_delta_P_max(
    FL: float,
    P1_bar: float,
    FF: float,
    Pv_bar: float,
    FLP: float | None = None,
    Fp:  float | None = None,
) -> float:
    """
    Maximum effective differential pressure for liquid service.

    Without fittings (Equation 4.2a):
        ΔP_max = FL² × (P1 − FF × Pv)

    With fittings (Equation 4.2b):
        ΔP_max = (FLP / Fp)² × (P1 − FF × Pv)

    Parameters
    ----------
    FL     : float         Liquid pressure recovery factor [—].
    P1_bar : float         Upstream pressure [bar abs].
    FF     : float         Liquid critical pressure ratio factor [—].
    Pv_bar : float         Vapour pressure [bar abs].
    FLP    : float | None  Combined factor FLP (required when fittings present).
    Fp     : float | None  Piping geometry factor (required with FLP).

    Returns
    -------
    float
        ΔP_max [bar].
    """
    effective_pressure = P1_bar - FF * Pv_bar
    if effective_pressure <= 0:
        raise HardConstraintViolation(
            "ERR_PV_EXCEEDS_P1",
            f"P1 − FF·Pv = {effective_pressure:.4f} bar ≤ 0.  "
            "Inlet pressure is insufficient for the given vapour pressure."
        )

    if FLP is not None and Fp is not None and Fp > 0:
        recovery_sq = (FLP / Fp) ** 2
    else:
        recovery_sq = FL ** 2

    return recovery_sq * effective_pressure


# ---------------------------------------------------------------------------
# CHOKED FLOW DECISION
# ---------------------------------------------------------------------------

def is_choked_liquid(delta_P_bar: float, delta_P_max_bar: float) -> bool:
    """
    Determine whether liquid flow is choked.

    Equation 4.3:  Choked if ΔP ≥ ΔP_max

    Parameters
    ----------
    delta_P_bar     : float  Actual differential pressure [bar].
    delta_P_max_bar : float  Maximum effective ΔP [bar].

    Returns
    -------
    bool
        True if choked.
    """
    return delta_P_bar >= delta_P_max_bar


# ---------------------------------------------------------------------------
# NON-CHOKED LIQUID  Cv
# ---------------------------------------------------------------------------

def cv_liquid_non_choked(
    Q_m3h: float,
    Gf: float,
    delta_P_bar: float,
    Fp: float = 1.0,
) -> float:
    """
    Required Cv for non-choked (turbulent) liquid flow.

    Without fittings (Equation 4.4):
        Cv = (Q / N₁) × √(Gf / ΔP)

    With fittings, Fp < 1 (Equation 4.5):
        Cv = (Q / (N₁ × Fp)) × √(Gf / ΔP)

    Parameters
    ----------
    Q_m3h     : float  Volumetric flow [m³/h].
    Gf        : float  Specific gravity [—].
    delta_P_bar: float Differential pressure [bar].
    Fp        : float  Piping geometry factor (1.0 if no fittings).

    Returns
    -------
    float
        Required Cv [—].
    """
    if delta_P_bar <= 0:
        raise HardConstraintViolation("ERR_NEGATIVE_DP", "ΔP must be positive for liquid sizing.")
    if Gf <= 0:
        raise HardConstraintViolation("ERR_INVALID_GF", "Specific gravity Gf must be positive.")
    if Fp <= 0:
        raise HardConstraintViolation("ERR_INVALID_FP", "Piping factor Fp must be positive.")

    return (Q_m3h / (_N1 * Fp)) * math.sqrt(Gf / delta_P_bar)


# ---------------------------------------------------------------------------
# CHOKED LIQUID  Cv
# ---------------------------------------------------------------------------

def cv_liquid_choked(
    Q_m3h: float,
    Gf: float,
    P1_bar: float,
    FF: float,
    Pv_bar: float,
    FL: float,
    FLP: float | None = None,
) -> float:
    """
    Required Cv for choked liquid flow.

    Without fittings (Equation 4.6):
        Cv = (Q / (N₁ × FL)) × √(Gf / (P₁ − FF × Pv))

    With fittings (Equation 4.7):
        Cv = (Q / (N₁ × FLP)) × √(Gf / (P₁ − FF × Pv))

    Parameters
    ----------
    Q_m3h  : float         Volumetric flow [m³/h].
    Gf     : float         Specific gravity [—].
    P1_bar : float         Upstream pressure [bar abs].
    FF     : float         Liquid critical pressure ratio factor [—].
    Pv_bar : float         Vapour pressure [bar abs].
    FL     : float         Liquid pressure recovery factor [—].
    FLP    : float | None  Use FLP in place of FL when fittings are present.

    Returns
    -------
    float
        Required Cv [—].
    """
    recovery = FLP if FLP is not None else FL
    if recovery <= 0:
        raise HardConstraintViolation("ERR_INVALID_FL", "Recovery factor FL / FLP must be positive.")

    denom_pressure = P1_bar - FF * Pv_bar
    if denom_pressure <= 0:
        raise HardConstraintViolation(
            "ERR_PV_EXCEEDS_P1",
            f"P1 − FF·Pv = {denom_pressure:.4f} bar ≤ 0."
        )
    return (Q_m3h / (_N1 * recovery)) * math.sqrt(Gf / denom_pressure)


# ---------------------------------------------------------------------------
# MASTER LIQUID DISPATCHER
# ---------------------------------------------------------------------------

def cv_liquid(
    Q_m3h: float,
    Gf: float,
    P1_bar: float,
    P2_bar: float,
    Pv_bar: float,
    Pc_bar: float,
    FL: float,
    Fp: float = 1.0,
    FLP: float | None = None,
) -> tuple[float, float, float, float, bool]:
    """
    Master liquid Cv dispatcher.  Selects the correct equation branch
    (non-choked vs choked) and returns all intermediate values.

    Parameters
    ----------
    Q_m3h   : float         Volumetric flow [m³/h].
    Gf      : float         Specific gravity [—].
    P1_bar  : float         Upstream pressure [bar abs].
    P2_bar  : float         Downstream pressure [bar abs].
    Pv_bar  : float         Vapour pressure [bar abs].
    Pc_bar  : float         Critical pressure [bar abs].
    FL      : float         Liquid pressure recovery factor [—].
    Fp      : float         Piping geometry factor (1.0 if no fittings).
    FLP     : float | None  Combined FLP factor (None if no fittings).

    Returns
    -------
    tuple: (Cv_required, FF, delta_P_max, delta_P_eff, is_choked)
        Cv_required  : float  Required Cv [—].
        FF           : float  Liquid critical pressure ratio factor [—].
        delta_P_max  : float  Maximum effective ΔP [bar].
        delta_P_eff  : float  Effective ΔP actually used in sizing [bar].
        is_choked    : bool   True if choked.
    """
    delta_P = P1_bar - P2_bar

    FF           = calc_FF(Pv_bar, Pc_bar)
    delta_P_max  = calc_delta_P_max(FL, P1_bar, FF, Pv_bar, FLP, Fp)
    choked       = is_choked_liquid(delta_P, delta_P_max)
    delta_P_eff  = delta_P_max if choked else delta_P

    if choked:
        Cv = cv_liquid_choked(Q_m3h, Gf, P1_bar, FF, Pv_bar, FL, FLP)
    else:
        Cv = cv_liquid_non_choked(Q_m3h, Gf, delta_P_eff, Fp)

    return Cv, FF, delta_P_max, delta_P_eff, choked