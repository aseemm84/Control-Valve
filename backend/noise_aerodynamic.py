"""
Aerodynamic noise prediction for gas and steam service.
========================================================
Implements IEC 60534-8-3:2011 — simplified engineering calculation chain.
Step A3, Section 9.

Calculation chain (Equations 9.1 – 9.17):
    Speed of sound c₁ → Critical PR → Jet velocity U_vc
    → Acoustic efficiency η → Mechanical power W_mech
    → Acoustic power W_a → LW_i → Pipe TL → A-weighting → Lpe [dBA]

All intermediate values are stored in the returned NoiseResult.
All inputs in SI.
"""

from __future__ import annotations

import math

from backend.constants import (
    R_UNIVERSAL, W_REF, RHO_STEEL, AERO_EFFICIENCY, A_WEIGHTING_TABLE, NOISE_LIMIT_DBA
)
from backend.models import AeroRegime, NoiseResult


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _speed_of_sound(gamma: float, T_K: float, M: float) -> float:
    """c = √(γ R T / M)  [m/s]"""
    return math.sqrt(gamma * R_UNIVERSAL * T_K / M)


def _a_weighting(f_hz: float) -> float:
    """
    A-weighting correction at frequency f_hz using log-linear interpolation
    over the standard octave-band table.

    Returns dB(A) correction (positive values add, negative subtract).
    """
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


def _lookup_efficiency(Fd: float, is_choked: bool) -> tuple[float, float]:
    """
    Return (Ceta, n_exponent) or (Ceta_choked, _) based on Fd value.
    Selects the closest entry in AERO_EFFICIENCY.
    """
    # Map Fd to valve type
    if Fd >= 0.90:
        key = "globe_single"
    elif Fd >= 0.45:
        key = "ball_v_port"
    elif Fd >= 0.35:
        key = "butterfly"
    elif Fd >= 0.20:
        key = "eccentric_rotary"
    else:
        key = "globe_cage"

    Ceta_sub, n_exp, Ceta_chk = AERO_EFFICIENCY[key]
    if is_choked:
        return Ceta_chk, n_exp
    return Ceta_sub, n_exp


# ---------------------------------------------------------------------------
# MAIN AERODYNAMIC NOISE FUNCTION
# ---------------------------------------------------------------------------

def run_aero_noise(
    W_kgh: float,
    P1_bar: float,
    P2_bar: float,
    T1_K: float,
    gamma: float,
    M: float,
    Di_m: float,
    t_wall_m: float,
    Fd: float,
    rho_wall: float = RHO_STEEL,
) -> NoiseResult:
    """
    Predict A-weighted external SPL at 1 m for gas / steam service.

    Implements the IEC 60534-8-3:2011 calculation chain.

    Parameters
    ----------
    W_kgh    : float  Mass flow [kg/h].
    P1_bar   : float  Upstream pressure [bar abs].
    P2_bar   : float  Downstream pressure [bar abs].
    T1_K     : float  Upstream temperature [K].
    gamma    : float  Isentropic exponent [—].
    M        : float  Molecular weight [kg/kmol].
    Di_m     : float  Downstream pipe internal diameter [m].
    t_wall_m : float  Downstream pipe wall thickness [m].
    Fd       : float  Valve style modifier [—].
    rho_wall : float  Pipe wall material density [kg/m³].

    Returns
    -------
    NoiseResult
    """
    mdot = W_kgh / 3_600.0   # kg/s

    # --- Eq 9.1: Speed of sound at inlet ---
    c1 = _speed_of_sound(gamma, T1_K, M)

    # --- Eq 9.2: Critical pressure ratio ---
    rP_crit = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))

    # --- Eq 9.3: Actual pressure ratio ---
    rP = P2_bar / P1_bar

    # --- Regime classification ---
    is_choked  = rP <= rP_crit
    regime_str = AeroRegime.CHOKED.value if is_choked else AeroRegime.SUBCRITICAL.value

    # --- Eq 9.4 / 9.5: Jet velocity at vena contracta ---
    if is_choked:
        # Eq 9.5: critical (sonic) velocity at throat
        U_vc = c1 * math.sqrt(2.0 / (gamma + 1.0))
    else:
        # Eq 9.4: isentropic expansion velocity
        exp  = (gamma - 1.0) / gamma
        U_vc = c1 * math.sqrt(2.0 / (gamma - 1.0) * (1.0 - rP ** exp))

    # --- Eq 9.6: Downstream temperature and speed of sound ---
    T2_est = T1_K * max(rP ** ((gamma - 1.0) / gamma), 0.5)
    c2     = _speed_of_sound(gamma, T2_est, M)

    # --- Eq 9.7: Downstream Mach number of jet ---
    M_j = U_vc / max(c2, 1.0)

    # --- Eq 9.8 / 9.9: Acoustic efficiency ---
    Ceta, n_exp = _lookup_efficiency(Fd, is_choked)
    if is_choked:
        eta = Ceta
    else:
        eta = Ceta * (M_j ** n_exp)
    eta = min(eta, 0.01)   # Physical upper bound (1 %)

    # --- Eq 9.10: Mechanical stream power ---
    W_mech = mdot * U_vc ** 2 / 2.0   # [W]

    # --- Eq 9.11: Acoustic power ---
    W_a = eta * W_mech   # [W]
    W_a = max(W_a, 1.0e-30)   # Guard against log(0)

    # --- Eq 9.12: Internal sound power level ---
    LWi = 10.0 * math.log10(W_a / W_REF)   # [dB re 1 pW]

    # --- Eq 9.15: Peak frequency ---
    f_p = max(Fd * U_vc / (0.2 * max(Di_m, 0.01)), 10.0)   # [Hz]

    # --- Pipe wall: surface mass density ---
    m_s = rho_wall * t_wall_m   # [kg/m²]

    # --- Downstream gas density (approximate at P2, T2) ---
    rho2_approx = (P2_bar * 1.0e5 * M) / (R_UNIVERSAL * T2_est)   # [kg/m³]
    rho_avg = max(rho2_approx, 0.01)

    # --- Eq 9.16: Pipe wall transmission loss ---
    angular_freq = 2.0 * math.pi * f_p
    ratio        = (angular_freq * m_s) / max(rho_avg * c2, 1.0)
    TL           = 10.0 * math.log10(1.0 + ratio ** 2) / 2.0   # [dB]
    TL           = max(TL, 0.0)

    # --- Pipe geometry correction (cylindrical source at 1 m) ---
    Do_m = Di_m + 2.0 * t_wall_m
    geo_correction = 10.0 * math.log10(max(Do_m / (4.0 * max(Di_m, 1e-3)), 1e-6))

    # --- Eq 9.17: A-weighting correction ---
    delta_LA = _a_weighting(f_p)

    # --- External SPL ---
    Lpe = LWi + geo_correction - TL + delta_LA

    return NoiseResult(
        Lpe_dba=round(Lpe, 1),
        LWi_db=round(LWi, 1),
        TL_db=round(TL, 1),
        f_peak_hz=round(f_p, 1),
        eta=eta,
        regime=regime_str,
        exceeds_limit=Lpe > NOISE_LIMIT_DBA,
    )