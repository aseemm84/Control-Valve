"""
Cavitation and flashing analysis for liquid service.
=====================================================
Implements IEC 60534-8-4:2015, Clause 5 / Step A3, Section 7.

Equations
---------
7.1  P_vc  — vena contracta pressure
7.2  ΔP_i  — incipient cavitation differential pressure
7.3  σ     — cavitation index
7.4        — 5-tier severity regime classification
7.5  ΔP_eff— effective ΔP (capped at ΔP_max for choked / cavitating service)

All values in SI units (bar abs).
"""

from __future__ import annotations

from backend.models import CavitationRegime, CavitationResult, HardConstraintViolation
from backend.sizing_liquid import calc_FF, calc_delta_P_max


# ---------------------------------------------------------------------------
# VENA CONTRACTA PRESSURE
# ---------------------------------------------------------------------------

def calc_vena_contracta_pressure(P1_bar: float, delta_P_bar: float, FL: float) -> float:
    """
    Pressure at the vena contracta (lowest point in the flow stream).

    Equation 7.1:
        P_vc = P₁ − ΔP / FL²

    Parameters
    ----------
    P1_bar     : float  Upstream pressure [bar abs].
    delta_P_bar: float  Differential pressure [bar].
    FL         : float  Liquid pressure recovery factor [—].

    Returns
    -------
    float
        P_vc [bar abs].
    """
    if FL <= 0:
        raise HardConstraintViolation("ERR_INVALID_FL", "FL must be positive.")
    return P1_bar - delta_P_bar / (FL ** 2)


# ---------------------------------------------------------------------------
# INCIPIENT CAVITATION ΔP
# ---------------------------------------------------------------------------

def calc_delta_P_incipient(FL: float, P1_bar: float, Pv_bar: float) -> float:
    """
    Differential pressure at onset of cavitation (incipient cavitation).

    Equation 7.2:
        ΔP_i = FL² × (P₁ − Pv)

    Cavitation begins when P_vc = Pv, i.e., when ΔP reaches ΔP_i.

    Parameters
    ----------
    FL     : float  Liquid pressure recovery factor [—].
    P1_bar : float  Upstream pressure [bar abs].
    Pv_bar : float  Vapour pressure at T1 [bar abs].

    Returns
    -------
    float
        ΔP_i [bar].
    """
    return FL ** 2 * (P1_bar - Pv_bar)


# ---------------------------------------------------------------------------
# CAVITATION INDEX  σ
# ---------------------------------------------------------------------------

def calc_sigma(P1_bar: float, Pv_bar: float, delta_P_bar: float) -> float:
    """
    Cavitation index (sigma).

    Equation 7.3:
        σ = (P₁ − Pv) / ΔP

    High σ → low cavitation risk.
    Cavitation onset at σ ≈ 1 / FL² (when ΔP = ΔP_i).

    Parameters
    ----------
    P1_bar     : float  Upstream pressure [bar abs].
    Pv_bar     : float  Vapour pressure [bar abs].
    delta_P_bar: float  Differential pressure [bar].

    Returns
    -------
    float
        σ [—].  Returns inf when ΔP → 0.
    """
    if delta_P_bar <= 0:
        return float("inf")
    return (P1_bar - Pv_bar) / delta_P_bar


# ---------------------------------------------------------------------------
# CAVITATION SEVERITY REGIME CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_cavitation_regime(
    P1_bar: float,
    P2_bar: float,
    Pv_bar: float,
    Pc_bar: float,
    FL: float,
    delta_P_bar: float,
) -> CavitationRegime:
    """
    Classify the cavitation severity regime using the 5-tier system.

    Equation 7.4 (IEC 60534-8-4, Clause 5):

    Regime 4 — FLASHING:        P₂ ≤ Pv
    Regime 3 — CHOKED:          ΔP ≥ ΔP_max  (and P₂ > Pv)
    Regime 2 — CONSTANT:        ΔP_i ≤ ΔP < ΔP_max  (established cavitation)
    Regime 1 — INCIPIENT:       ΔP_c ≤ ΔP < ΔP_i    (noise onset)
    Regime 0 — NONE:            ΔP < ΔP_i / threshold

    where ΔP_c ≈ 0.25 × ΔP_i (onset of audible cavitation noise, approximate).

    Parameters
    ----------
    P1_bar     : float  Upstream pressure [bar abs].
    P2_bar     : float  Downstream pressure [bar abs].
    Pv_bar     : float  Vapour pressure [bar abs].
    Pc_bar     : float  Critical pressure [bar abs].
    FL         : float  Liquid pressure recovery factor [—].
    delta_P_bar: float  Actual differential pressure [bar].

    Returns
    -------
    CavitationRegime
    """
    # Regime 4: Flashing
    if P2_bar <= Pv_bar:
        return CavitationRegime.FLASHING

    FF          = calc_FF(Pv_bar, Pc_bar)
    delta_P_max = calc_delta_P_max(FL, P1_bar, FF, Pv_bar)
    delta_P_i   = calc_delta_P_incipient(FL, P1_bar, Pv_bar)
    delta_P_c   = 0.25 * delta_P_i   # approximate incipient noise threshold

    # Regime 3: Choked cavitation (supercavitation)
    if delta_P_bar >= delta_P_max:
        return CavitationRegime.CHOKED

    # Regime 2: Constant (established) cavitation
    if delta_P_bar >= delta_P_i:
        return CavitationRegime.CONSTANT

    # Regime 1: Incipient cavitation (noise onset)
    if delta_P_bar >= delta_P_c:
        return CavitationRegime.INCIPIENT

    # Regime 0: No cavitation
    return CavitationRegime.NONE


# ---------------------------------------------------------------------------
# EFFECTIVE DIFFERENTIAL PRESSURE  ΔP_eff
# ---------------------------------------------------------------------------

def calc_delta_P_eff(delta_P_bar: float, delta_P_max_bar: float) -> float:
    """
    Effective differential pressure used in the Cv equation.

    Equation 7.5:
        ΔP_eff = min(ΔP, ΔP_max)

    Caps the operative pressure drop at the choked value.
    Using the actual ΔP when choked would underestimate Cv.

    Parameters
    ----------
    delta_P_bar     : float  Actual differential pressure [bar].
    delta_P_max_bar : float  Maximum choked ΔP [bar].

    Returns
    -------
    float
        ΔP_eff [bar].
    """
    return min(delta_P_bar, delta_P_max_bar)


# ---------------------------------------------------------------------------
# COMPLETE CAVITATION ANALYSIS
# ---------------------------------------------------------------------------

def analyse_cavitation(
    P1_bar: float,
    P2_bar: float,
    Pv_bar: float,
    Pc_bar: float,
    FL: float,
) -> CavitationResult:
    """
    Run full cavitation / flashing analysis and return a CavitationResult.

    Parameters
    ----------
    P1_bar : float  Upstream pressure [bar abs].
    P2_bar : float  Downstream pressure [bar abs].
    Pv_bar : float  Vapour pressure [bar abs].
    Pc_bar : float  Critical pressure [bar abs].
    FL     : float  Liquid pressure recovery factor [—].

    Returns
    -------
    CavitationResult
    """
    delta_P   = P1_bar - P2_bar
    FF        = calc_FF(Pv_bar, Pc_bar)
    delta_P_max = calc_delta_P_max(FL, P1_bar, FF, Pv_bar)
    delta_P_i   = calc_delta_P_incipient(FL, P1_bar, Pv_bar)
    P_vc        = calc_vena_contracta_pressure(P1_bar, delta_P, FL)
    sigma       = calc_sigma(P1_bar, Pv_bar, delta_P)
    regime      = classify_cavitation_regime(P1_bar, P2_bar, Pv_bar, Pc_bar, FL, delta_P)

    is_choked   = regime in (CavitationRegime.CHOKED, CavitationRegime.FLASHING)
    is_flashing = regime == CavitationRegime.FLASHING

    return CavitationResult(
        regime=regime,
        sigma=sigma,
        P_vc=P_vc,
        delta_P_incipient=delta_P_i,
        delta_P_max=delta_P_max,
        FF=FF,
        is_choked=is_choked,
        is_flashing=is_flashing,
    )