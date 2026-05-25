"""
Reynolds number and viscous flow correction.
=============================================
Implements ISA-75.01.01-2012, Annex B / IEC 60534-2-1, Annex B.
Step A3, Section 8.

For Rev < 10,000 the turbulent-flow Cv equation overestimates the true
required Cv.  The Reynolds Number Factor FR < 1 corrects for this.

Equation 8.1  — Valve Reynolds number Rev
FR table      — Log-linear interpolation (ISA curve)
Section 8.3   — Iterative convergence procedure

All inputs in SI (m³/h, cSt, mm).
"""

from __future__ import annotations

import math

from backend.constants import SI_N, FR_TABLE
from backend.models import ConvergenceError

_N2 = SI_N["N2"]   # 0.00214 (d in mm)
_N4 = SI_N["N4"]   # 17,300  (Q in m³/h, ν in cSt, d in mm)

# Regime thresholds
REV_TURBULENT:    float = 40_000.0
REV_LAMINAR_WARN: float = 10_000.0


# ---------------------------------------------------------------------------
# VALVE REYNOLDS NUMBER
# ---------------------------------------------------------------------------

def calc_Rev(
    Q_m3h: float,
    nu_cSt: float,
    FL: float,
    Cv: float,
    d_mm: float,
    Fd: float,
) -> float:
    """
    Valve Reynolds number for liquid flow.

    Equation 8.1 (IEC 60534-2-1, Annex B):
        Rev = (N₄ × Fd × Q) / (ν × (FL × Cv)^0.5) × [FL² × Cv² / (N₂ × d⁴) + 1]^0.25

    Parameters
    ----------
    Q_m3h  : float  Volumetric flow [m³/h].
    nu_cSt : float  Kinematic viscosity [cSt].
    FL     : float  Liquid pressure recovery factor [—].
    Cv     : float  Current Cv estimate [—].
    d_mm   : float  Valve nominal size [mm].
    Fd     : float  Valve style modifier [—].

    Returns
    -------
    float
        Valve Reynolds number Rev [—].
    """
    if nu_cSt <= 0:
        raise ValueError("Kinematic viscosity must be positive.")
    if Cv <= 0 or FL <= 0 or d_mm <= 0:
        raise ValueError("Cv, FL, and d must be strictly positive.")

    denom_cv = math.sqrt(FL * Cv)
    bracket  = (FL ** 2 * Cv ** 2) / (_N2 * d_mm ** 4) + 1.0
    return (_N4 * Fd * Q_m3h) / (nu_cSt * denom_cv) * bracket ** 0.25


# ---------------------------------------------------------------------------
# REYNOLDS NUMBER FACTOR  FR  (log-linear interpolation)
# ---------------------------------------------------------------------------

def calc_FR(Rev: float) -> float:
    """
    Reynolds Number Factor FR from the ISA tabulated curve.

    Uses log-linear interpolation between entries in FR_TABLE.
    FR = 1.0 for Rev ≥ 40,000 (fully turbulent).
    FR → 0.10 as Rev → 1 (fully laminar).

    Parameters
    ----------
    Rev : float  Valve Reynolds number [—].

    Returns
    -------
    float
        FR ∈ [0.10, 1.00].
    """
    if Rev <= 0:
        return FR_TABLE[0][1]      # Clamp to lowest table value
    if Rev >= REV_TURBULENT:
        return 1.0

    # Log-linear interpolation
    log_rev = math.log10(Rev)
    for i in range(len(FR_TABLE) - 1):
        rev_a, fr_a = FR_TABLE[i]
        rev_b, fr_b = FR_TABLE[i + 1]
        if rev_a <= Rev <= rev_b:
            log_a = math.log10(rev_a)
            log_b = math.log10(rev_b)
            t     = (log_rev - log_a) / (log_b - log_a)
            return fr_a + t * (fr_b - fr_a)

    return 1.0   # Fallback (should not reach here)


# ---------------------------------------------------------------------------
# ITERATIVE VISCOUS CORRECTION
# ---------------------------------------------------------------------------

def apply_viscous_correction(
    Cv_turbulent: float,
    Q_m3h: float,
    nu_cSt: float,
    FL: float,
    Fd: float,
    d_mm: float,
    max_iter: int = 50,
    tol: float = 1.0e-5,
) -> tuple[float, float, float]:
    """
    Iteratively determine the viscosity-corrected Cv.

    Procedure (Step A3, Section 8.3):
        1. Start with Cv_turbulent (FR = 1 assumption).
        2. Compute Rev using current Cv estimate.
        3. Look up FR from the ISA table.
        4. Cv_new = Cv_turbulent / FR.
        5. Repeat until convergence.

    Parameters
    ----------
    Cv_turbulent : float  Cv computed assuming FR = 1.
    Q_m3h        : float  Volumetric flow [m³/h].
    nu_cSt       : float  Kinematic viscosity [cSt].
    FL           : float  Liquid pressure recovery factor [—].
    Fd           : float  Valve style modifier [—].
    d_mm         : float  Valve nominal size [mm].
    max_iter     : int    Maximum iterations (default 50).
    tol          : float  Relative convergence tolerance.

    Returns
    -------
    tuple[float, float, float]
        (Cv_corrected, Rev_final, FR_final)

    Raises
    ------
    ConvergenceError
        If the solver does not converge within max_iter.
    """
    Cv_k = Cv_turbulent
    for _ in range(max_iter):
        Rev_k  = calc_Rev(Q_m3h, nu_cSt, FL, Cv_k, d_mm, Fd)
        FR_k   = calc_FR(Rev_k)
        Cv_new = Cv_turbulent / FR_k

        if abs(Cv_new - Cv_k) / max(Cv_k, 1.0e-12) < tol:
            return Cv_new, Rev_k, FR_k
        Cv_k = Cv_new

    raise ConvergenceError("viscous_correction", max_iter)