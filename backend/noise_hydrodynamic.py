"""
Hydrodynamic noise prediction for liquid service.
==================================================
Implements IEC 60534-8-4:2015 — simplified engineering calculation chain.
Step A3, Section 10.

The internal SPL depends on the active cavitation regime (5 tiers).
All inputs in SI.
"""

from __future__ import annotations

import math

from backend.constants import W_REF, A_WEIGHTING_TABLE, NOISE_LIMIT_DBA
from backend.models import CavitationRegime, NoiseResult


def _a_weighting(f_hz: float) -> float:
    """Log-linear A-weighting interpolation (same as aerodynamic module)."""
    if f_hz <= 0:
        return A_WEIGHTING_TABLE[0][1]
    if f_hz >= A_WEIGHTING_TABLE[-1][0]:
        return A_WEIGHTING_TABLE[-1][1]
    log_f = math.log10(f_hz)
    for i in range(len(A_WEIGHTING_TABLE) - 1):
        f_a, da_a = A_WEIGHTING_TABLE[i]
        f_b, da_b = A_WEIGHTING_TABLE[i + 1]
        if f_a <= f_hz <= f_b:
            t = (log_f - math.log10(f_a)) / (math.log10(f_b) - math.log10(f_a))
            return da_a + t * (da_b - da_a)
    return 0.0


def _calc_Lpi_by_regime(
    regime: CavitationRegime,
    rho_L: float,
    delta_P_bar: float,
    delta_P_i_bar: float,
    delta_P_e_bar: float,
    Q_m3h: float,
    Di_m: float,
) -> float:
    """
    Internal sound pressure level Lpi [dB] as a function of cavitation regime.

    Equations 10 (IEC 60534-8-4, Clause 5).

    Parameters
    ----------
    regime        : CavitationRegime  Active regime.
    rho_L         : float  Liquid density [kg/m³].
    delta_P_bar   : float  Actual ΔP [bar].
    delta_P_i_bar : float  Incipient cavitation ΔP [bar].
    delta_P_e_bar : float  Effective (choked) ΔP = P1 − FF·Pv [bar].
    Q_m3h         : float  Volumetric flow [m³/h].
    Di_m          : float  Pipe internal diameter [m].

    Returns
    -------
    float
        Lpi [dB].
    """
    Di2  = max(Di_m ** 2, 1.0e-6)
    Q_si = Q_m3h / 3_600.0   # m³/s

    # Convert bar to Pa for dimensional consistency
    dP_Pa   = delta_P_bar   * 1.0e5
    dP_i_Pa = delta_P_i_bar * 1.0e5
    dP_e_Pa = delta_P_e_bar * 1.0e5

    if regime == CavitationRegime.NONE:
        # Turbulent (no cavitation) regime
        # Eq 10: Lpi ~ turbulent pressure fluctuations
        inner = 2.3e-5 * rho_L * (dP_Pa ** 3.5) * Q_si / (Di2 * rho_L ** 1.5)
        inner = max(inner, 1.0e-60)
        return 10.0 * math.log10(inner / (W_REF * 1.0e12))   # referenced to 20 µPa

    if regime == CavitationRegime.INCIPIENT:
        # Blend between turbulent and constant cavitation
        base = 2.3e-5 * rho_L * (dP_Pa ** 3.5) * Q_si / (Di2 * rho_L ** 1.5)
        excess_factor = 1.0 + 25.0 * max(0, (delta_P_bar - 0.5 * delta_P_i_bar) / delta_P_i_bar)
        inner = max(base * excess_factor, 1.0e-60)
        return 10.0 * math.log10(inner / (W_REF * 1.0e12))

    if regime == CavitationRegime.CONSTANT:
        # Constant cavitation — dominant bubble collapse noise
        excess_Pa = max(dP_Pa - dP_i_Pa, 0.0)
        inner = 1.6e-3 * rho_L * (excess_Pa ** 1.5) * Q_si / Di2
        inner = max(inner, 1.0e-60)
        return 10.0 * math.log10(inner / (W_REF * 1.0e12))

    if regime == CavitationRegime.CHOKED:
        # Choked (supercavitation) — maximum cavitation noise
        inner = 8.0e-2 * rho_L * (dP_e_Pa ** 1.5) * Q_si / Di2
        inner = max(inner, 1.0e-60)
        return 10.0 * math.log10(inner / (W_REF * 1.0e12))

    if regime == CavitationRegime.FLASHING:
        # Flashing: +6 dB penalty over choked regime
        inner = 8.0e-2 * rho_L * (dP_e_Pa ** 1.5) * Q_si / Di2
        inner = max(inner, 1.0e-60)
        return 10.0 * math.log10(inner / (W_REF * 1.0e12)) + 6.0

    return 0.0


def run_hydro_noise(
    Q_m3h: float,
    P1_bar: float,
    Pv_bar: float,
    FF: float,
    rho_L: float,
    Di_m: float,
    t_wall_m: float,
    delta_P_i_bar: float,
    delta_P_bar: float,
    cavitation_regime: CavitationRegime,
    rho_wall: float = 7_800.0,
    c_L: float = 1_480.0,
) -> NoiseResult:
    """
    Predict A-weighted external SPL at 1 m for liquid service.

    Parameters
    ----------
    Q_m3h              : float  Volumetric flow [m³/h].
    P1_bar             : float  Upstream pressure [bar abs].
    Pv_bar             : float  Vapour pressure [bar abs].
    FF                 : float  Liquid critical pressure ratio factor [—].
    rho_L              : float  Liquid density [kg/m³].
    Di_m               : float  Downstream pipe internal diameter [m].
    t_wall_m           : float  Downstream pipe wall thickness [m].
    delta_P_i_bar      : float  Incipient cavitation ΔP [bar].
    delta_P_bar        : float  Actual ΔP [bar].
    cavitation_regime  : CavitationRegime  Active cavitation regime.
    rho_wall           : float  Pipe wall density [kg/m³] (default steel).
    c_L                : float  Speed of sound in liquid [m/s] (default water).

    Returns
    -------
    NoiseResult
    """
    # --- Eq 10.1: Effective ΔP ---
    delta_P_e_bar = P1_bar - FF * Pv_bar

    # --- Peak frequency for liquid noise ---
    f_p = max(4_000.0 * math.sqrt(max(delta_P_bar, 0.01)), 100.0)   # [Hz]

    # --- Internal SPL ---
    Lpi = _calc_Lpi_by_regime(
        cavitation_regime, rho_L,
        delta_P_bar, delta_P_i_bar, delta_P_e_bar,
        Q_m3h, Di_m,
    )

    # --- Pipe wall transmission loss (liquid) ---
    m_s          = rho_wall * t_wall_m            # surface mass density [kg/m²]
    angular_freq = 2.0 * math.pi * f_p
    ratio        = (angular_freq * m_s) / max(rho_L * c_L, 1.0)
    TL           = 10.0 * math.log10(1.0 + ratio ** 2) / 2.0
    TL           = max(TL, 0.0)

    # --- Eq 10.2: External SPL ---
    delta_LA = _a_weighting(f_p)
    Lpe      = Lpi - TL + delta_LA

    return NoiseResult(
        Lpe_dba=round(Lpe, 1),
        LWi_db=round(Lpi, 1),
        TL_db=round(TL, 1),
        f_peak_hz=round(f_p, 1),
        eta=0.0,   # not applicable for liquid
        regime=cavitation_regime.value,
        exceeds_limit=Lpe > NOISE_LIMIT_DBA,
    )