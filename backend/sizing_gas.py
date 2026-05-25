"""
Gas and vapour Cv sizing equations.
=====================================
Implements IEC 60534-2-1:2011, Clause 5.2 (Equations 5.1 – 5.8 from Step A3).

All inputs must be in SI units (bar abs, kg/h or Nm³/h, K, mm).
N6 = 27.3 is used for mass-flow Cv (kg/h, bar, kg/m³).

Functions
---------
calc_Fgamma    → Specific heat ratio factor Fγ (Eq 5.1)
calc_x         → Pressure differential ratio x (Eq 5.2)
is_choked_gas  → Choked gas condition check (Eq 5.3)
calc_Y         → Expansion factor Y (Eq 5.4)
cv_gas_mass    → Cv from mass flow W (Eq 5.6 / 5.8)
cv_gas         → Master dispatcher
"""

from __future__ import annotations

import math

from backend.constants import SI_N, GAMMA_AIR
from backend.models import HardConstraintViolation

_N6 = SI_N["N6"]   # 27.3  (W in kg/h, P in bar, ρ in kg/m³)

Y_MIN: float = 2.0 / 3.0   # Minimum expansion factor (choked condition)


# ---------------------------------------------------------------------------
# SPECIFIC HEAT RATIO FACTOR  Fγ
# ---------------------------------------------------------------------------

def calc_Fgamma(gamma: float) -> float:
    """
    Specific heat ratio factor.

    Equation 5.1:  Fγ = γ / 1.40

    Normalises the choked pressure ratio to the reference gas (air, γ = 1.40).
    Fγ = 1.0 for air; Fγ < 1 for heavier molecules; Fγ > 1 for lighter ones.

    Parameters
    ----------
    gamma : float
        Isentropic exponent Cp / Cv [—].

    Returns
    -------
    float
        Fγ, constrained to [0.50, 1.30].
    """
    Fg = gamma / GAMMA_AIR
    return max(0.50, min(Fg, 1.30))


# ---------------------------------------------------------------------------
# PRESSURE DIFFERENTIAL RATIO  x
# ---------------------------------------------------------------------------

def calc_x(P1_bar: float, P2_bar: float) -> float:
    """
    Actual pressure differential ratio x = ΔP / P1.

    Equation 5.2.

    Parameters
    ----------
    P1_bar : float  Upstream absolute pressure [bar].
    P2_bar : float  Downstream absolute pressure [bar].

    Returns
    -------
    float
        x ∈ (0, 1).
    """
    if P1_bar <= 0:
        raise HardConstraintViolation("ERR_NONPOSITIVE_PRESSURE", "P1 must be > 0.")
    if P2_bar >= P1_bar:
        raise HardConstraintViolation("ERR_PRESSURE_INVERSION", "P2 must be < P1.")
    return (P1_bar - P2_bar) / P1_bar


# ---------------------------------------------------------------------------
# CHOKED CONDITION  (Gas / Vapour)
# ---------------------------------------------------------------------------

def is_choked_gas(x: float, Fgamma: float, xT_or_xTP: float) -> bool:
    """
    Determine whether gas / vapour flow is choked.

    Equation 5.3:  Choked when x ≥ Fγ × xT (or xTP with fittings).

    Parameters
    ----------
    x            : float  Actual pressure differential ratio [—].
    Fgamma       : float  Specific heat ratio factor [—].
    xT_or_xTP    : float  Pressure differential ratio factor [—].

    Returns
    -------
    bool
        True if choked.
    """
    return x >= Fgamma * xT_or_xTP


# ---------------------------------------------------------------------------
# EXPANSION FACTOR  Y
# ---------------------------------------------------------------------------

def calc_Y(
    x: float,
    Fgamma: float,
    xT_or_xTP: float,
) -> tuple[float, float, bool]:
    """
    Gas expansion factor Y and effective x.

    Equation 5.4:
        Y = 1 − x / (3 × Fγ × xT)      [unclamped]
        Y ≥ 2/3  always enforced

    When choked (x ≥ Fγ × xT):
        x_eff = Fγ × xT    (capped)
        Y     = 2/3        (minimum)

    Parameters
    ----------
    x          : float  Actual pressure differential ratio [—].
    Fgamma     : float  Fγ [—].
    xT_or_xTP  : float  xT or xTP [—].

    Returns
    -------
    tuple[float, float, bool]
        (Y, x_eff, is_choked)
        Y       : expansion factor, clamped to [2/3, 1.0]
        x_eff   : effective x used in Cv equation
        is_choked: True when choked
    """
    x_limit  = Fgamma * xT_or_xTP
    choked   = x >= x_limit
    x_eff    = x_limit if choked else x
    Y        = 1.0 - x_eff / (3.0 * x_limit)
    Y        = max(Y_MIN, min(Y, 1.0))
    return Y, x_eff, choked


# ---------------------------------------------------------------------------
# GAS Cv  — MASS FLOW BASIS
# ---------------------------------------------------------------------------

def cv_gas_mass(
    W_kgh: float,
    P1_bar: float,
    rho1_kgm3: float,
    Y: float,
    x_eff: float,
    Fp: float = 1.0,
) -> float:
    """
    Required Cv for gas / vapour service using mass flow.

    Equation 5.6 (no fittings) / 5.8 (with fittings):
        Cv = W / (N₆ × Fp × Y) × √(1 / (x × P₁ × ρ₁))

    where N₆ = 27.3 (SI: W in kg/h, P in bar, ρ in kg/m³).

    Parameters
    ----------
    W_kgh    : float  Mass flow [kg/h].
    P1_bar   : float  Upstream pressure [bar abs].
    rho1_kgm3: float  Gas density at inlet conditions [kg/m³].
    Y        : float  Expansion factor [—].
    x_eff    : float  Effective pressure differential ratio (capped if choked).
    Fp       : float  Piping geometry factor (1.0 if no fittings).

    Returns
    -------
    float
        Required Cv [—].
    """
    if W_kgh <= 0:
        raise HardConstraintViolation("ERR_NONPOSITIVE_FLOW", "Mass flow W must be positive.")
    if Y < Y_MIN - 1e-9:
        raise HardConstraintViolation("ERR_INVALID_Y", f"Y={Y:.4f} is below minimum {Y_MIN:.4f}.")
    if x_eff <= 0 or P1_bar <= 0 or rho1_kgm3 <= 0:
        raise HardConstraintViolation(
            "ERR_GAS_PROPERTIES",
            "x_eff, P1, and rho1 must all be strictly positive."
        )

    inner = 1.0 / (x_eff * P1_bar * rho1_kgm3)
    return (W_kgh / (_N6 * Fp * Y)) * math.sqrt(inner)


# ---------------------------------------------------------------------------
# MASTER GAS DISPATCHER
# ---------------------------------------------------------------------------

def cv_gas(
    W_kgh: float,
    P1_bar: float,
    P2_bar: float,
    rho1_kgm3: float,
    gamma: float,
    xT: float,
    Fp: float = 1.0,
    xTP: float | None = None,
) -> tuple[float, float, float, float, bool]:
    """
    Master gas Cv dispatcher.

    Computes Fγ, x, Y, checks for choked flow, and calls cv_gas_mass.
    Uses xTP (with fittings) when provided; otherwise uses xT.

    Parameters
    ----------
    W_kgh    : float         Mass flow [kg/h].
    P1_bar   : float         Upstream pressure [bar abs].
    P2_bar   : float         Downstream pressure [bar abs].
    rho1_kgm3: float         Gas inlet density [kg/m³].
    gamma    : float         Isentropic exponent [—].
    xT       : float         Valve pressure differential ratio [—].
    Fp       : float         Piping geometry factor (1.0 = no fittings).
    xTP      : float | None  Combined xTP (use when fittings present).

    Returns
    -------
    tuple: (Cv, Fgamma, x, Y, is_choked)
    """
    Fgamma     = calc_Fgamma(gamma)
    x          = calc_x(P1_bar, P2_bar)
    xT_eff     = xTP if (xTP is not None and Fp < 1.0) else xT
    Y, x_eff, choked = calc_Y(x, Fgamma, xT_eff)
    Cv         = cv_gas_mass(W_kgh, P1_bar, rho1_kgm3, Y, x_eff, Fp)
    return Cv, Fgamma, x, Y, choked