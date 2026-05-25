"""
Piping geometry correction factors.
=====================================
Implements IEC 60534-2-1:2011, Clause 6.

Functions
---------
fitting_loss_coefficients  → ξ₁, ξ₂, ξ_B1, ξ_B2
sum_loss_coefficients      → Σξ, Σξ₁
calc_Fp_single             → Fp for a known Cv (Equation 3.1)
calc_Fp_iterative          → Iterative Fp solving when Cv is unknown
calc_FLP                   → Combined FL·Fp for choked liquid (Equation 3.2)
calc_xTP                   → Combined xT with fittings for gas (Equation 3.3)

All dimensions in mm; N2 and N5 are always the SI values from constants.py.
"""

from __future__ import annotations

import math
from backend.constants import SI_N
from backend.models import ConvergenceError

_N2 = SI_N["N2"]   # 0.00214  (d in mm)
_N5 = SI_N["N5"]   # 0.00241  (d in mm)


# ---------------------------------------------------------------------------
# FITTING LOSS COEFFICIENTS
# ---------------------------------------------------------------------------

def fitting_loss_coefficients(
    d_mm: float,
    D1_mm: float,
    D2_mm: float,
) -> dict[str, float]:
    """
    Calculate individual velocity head loss coefficients for reducers/expanders.

    Equations (IEC 60534-2-1, Clause 6):
        ξ₁   = 0.5 × (1 − (d/D₁)²)²      inlet reducer
        ξ₂   = 1.0 × (1 − (d/D₂)²)²      outlet expander
        ξ_B1 = 1 − (d/D₁)⁴               Bernoulli term, upstream
        ξ_B2 = 1 − (d/D₂)⁴               Bernoulli term, downstream

    If D₁ = d or D₂ = d the corresponding coefficients are zero.

    Parameters
    ----------
    d_mm  : float  Valve nominal body size [mm].
    D1_mm : float  Upstream pipe internal diameter [mm].
    D2_mm : float  Downstream pipe internal diameter [mm].

    Returns
    -------
    dict with keys: xi1, xi2, xiB1, xiB2
    """
    ratio1 = d_mm / D1_mm if D1_mm > 0 else 1.0
    ratio2 = d_mm / D2_mm if D2_mm > 0 else 1.0

    xi1  = 0.5 * (1.0 - ratio1 ** 2) ** 2 if D1_mm != d_mm else 0.0
    xi2  = 1.0 * (1.0 - ratio2 ** 2) ** 2 if D2_mm != d_mm else 0.0
    xiB1 = (1.0 - ratio1 ** 4)              if D1_mm != d_mm else 0.0
    xiB2 = (1.0 - ratio2 ** 4)              if D2_mm != d_mm else 0.0

    return {"xi1": xi1, "xi2": xi2, "xiB1": xiB1, "xiB2": xiB2}


def sum_loss_coefficients(coeffs: dict[str, float]) -> tuple[float, float]:
    """
    Compute summed loss coefficients for Fp and FLP / xTP.

    Σξ   = ξ₁ + ξ₂ + ξ_B1 − ξ_B2      used in Fp
    Σξ₁  = ξ₁ + ξ_B1                   upstream fittings only, used in FLP / xTP

    Parameters
    ----------
    coeffs : dict
        Output of fitting_loss_coefficients().

    Returns
    -------
    tuple[float, float]
        (sum_xi, sum_xi1)
    """
    sum_xi  = coeffs["xi1"] + coeffs["xi2"] + coeffs["xiB1"] - coeffs["xiB2"]
    sum_xi1 = coeffs["xi1"] + coeffs["xiB1"]
    return sum_xi, sum_xi1


# ---------------------------------------------------------------------------
# PIPING GEOMETRY FACTOR  Fp
# ---------------------------------------------------------------------------

def calc_Fp_single(Cv: float, d_mm: float, sum_xi: float) -> float:
    """
    Compute Fp for a *known* Cv value.

    Equation 3.1 (IEC 60534-2-1, Clause 6):
        Fp = [1 + (Σξ / N₂) × (Cv / d²)²]^(−1/2)

    Parameters
    ----------
    Cv     : float  Flow coefficient [—].
    d_mm   : float  Valve size [mm].
    sum_xi : float  Σξ from sum_loss_coefficients().

    Returns
    -------
    float
        Fp ∈ (0, 1].
    """
    if d_mm <= 0:
        raise ValueError("Valve diameter d must be positive.")
    term = (sum_xi / _N2) * (Cv / d_mm ** 2) ** 2
    return (1.0 + term) ** (-0.5)


def calc_Fp_iterative(
    Cv_no_fittings: float,
    d_mm: float,
    sum_xi: float,
    max_iter: int = 50,
    tol: float = 1.0e-6,
) -> tuple[float, float]:
    """
    Iteratively solve for Fp and the corrected Cv when fittings are present.

    The iteration is necessary because Fp depends on Cv (which is unknown):
        STEP 1: Cv_k+1 = Cv_no_fittings / Fp_k
        STEP 2: Fp_k+1 = calc_Fp_single(Cv_k+1)
        REPEAT until |Cv_k+1 − Cv_k| / Cv_k < tol

    Parameters
    ----------
    Cv_no_fittings : float  Cv computed assuming Fp = 1.0 (initial estimate).
    d_mm           : float  Valve size [mm].
    sum_xi         : float  Σξ from sum_loss_coefficients().
    max_iter       : int    Maximum iterations (default 50).
    tol            : float  Relative convergence tolerance (default 1×10⁻⁶).

    Returns
    -------
    tuple[float, float]
        (Fp_converged, Cv_corrected)

    Raises
    ------
    ConvergenceError
        If the solver does not converge within max_iter.
    """
    if sum_xi == 0.0:
        return 1.0, Cv_no_fittings   # No fittings — trivial solution

    Cv_k = Cv_no_fittings
    for k in range(max_iter):
        Fp_k   = calc_Fp_single(Cv_k, d_mm, sum_xi)
        Cv_new = Cv_no_fittings / Fp_k
        if abs(Cv_new - Cv_k) / max(Cv_k, 1e-12) < tol:
            return Fp_k, Cv_new
        Cv_k = Cv_new

    raise ConvergenceError("Fp_iterative", max_iter)


# ---------------------------------------------------------------------------
# COMBINED FACTOR  FLP  (Liquid, choked, with fittings)
# ---------------------------------------------------------------------------

def calc_FLP(
    FL: float,
    Cv: float,
    d_mm: float,
    sum_xi1: float,
) -> float:
    """
    Combined liquid pressure recovery and piping geometry factor FLP.

    Equation 3.2 (IEC 60534-2-1, Clause 6):
        FLP = FL × [1 + FL² × (Σξ₁ / N₂) × (Cv / d²)²]^(−1/2)

    FLP replaces FL × Fp *only* in the choked ΔP_max and choked Cv
    equations when fittings (reducers/expanders) are present.

    Parameters
    ----------
    FL      : float  Liquid pressure recovery factor [—].
    Cv      : float  Flow coefficient to evaluate at [—].
    d_mm    : float  Valve size [mm].
    sum_xi1 : float  Σξ₁ (upstream fittings only).

    Returns
    -------
    float
        FLP [—].
    """
    if sum_xi1 == 0.0:
        return FL
    term = FL ** 2 * (sum_xi1 / _N2) * (Cv / d_mm ** 2) ** 2
    return FL * (1.0 + term) ** (-0.5)


# ---------------------------------------------------------------------------
# COMBINED FACTOR  xTP  (Gas, with fittings)
# ---------------------------------------------------------------------------

def calc_xTP(
    xT: float,
    Fp: float,
    Cv: float,
    d_mm: float,
    sum_xi1: float,
) -> float:
    """
    Combined pressure differential ratio factor xTP for gas service with fittings.

    Equation 3.3 (IEC 60534-2-1, Clause 6):
        xTP = (xT / Fp²) × [1 + (xT × Σξ₁ / N₅) × (Cv / d²)²]⁻¹

    Parameters
    ----------
    xT      : float  Pressure differential ratio factor [—] at choked flow.
    Fp      : float  Piping geometry factor [—].
    Cv      : float  Flow coefficient [—].
    d_mm    : float  Valve size [mm].
    sum_xi1 : float  Σξ₁ (upstream fittings only).

    Returns
    -------
    float
        xTP [—], constrained to (0, xT].
    """
    if sum_xi1 == 0.0 or Fp >= 1.0:
        return xT
    term  = (xT * sum_xi1 / _N5) * (Cv / d_mm ** 2) ** 2
    xTP   = (xT / Fp ** 2) / (1.0 + term)
    return max(min(xTP, xT), 1e-6)