"""
Fluid property calculation functions.
======================================
All functions accept and return SI values.

Steam properties are retrieved from the IAPWS-IF97 formulation via
the ``iapws`` Python library.  The library uses:
    Temperature → Kelvin
    Pressure    → MPa  (conversion: P_MPa = P_bara / 10)

Reference: IAPWS, "Revised Release on the IAPWS Industrial Formulation
1997 for the Thermodynamic Properties of Water and Steam" (IF97-2012).
"""

from __future__ import annotations

import math
from typing import NamedTuple

from backend.constants import R_UNIVERSAL, RHO_WATER_15C, M_AIR, P_STD_BAR, T_STD_K
from backend.models import SteamPropertyError, SteamType

try:
    from iapws import IAPWS97
    _IAPWS_AVAILABLE = True
except ImportError:
    _IAPWS_AVAILABLE = False


# ---------------------------------------------------------------------------
# NAMED TUPLE FOR STEAM PROPERTIES
# ---------------------------------------------------------------------------

class SteamProps(NamedTuple):
    """Thermodynamic properties of steam at a given (T, P) state."""
    v1:         float   # Specific volume [m³/kg]
    gamma:      float   # Isentropic exponent Cp/Cv [—]
    phase:      str     # 'gas', 'liquid', 'Two phase', etc.
    T_sat_K:    float   # Saturation temperature at P1 [K]
    vf:         float   # Saturated liquid specific volume [m³/kg]
    vg:         float   # Saturated vapour specific volume [m³/kg]
    steam_type: SteamType


# ---------------------------------------------------------------------------
# LIQUID PROPERTIES
# ---------------------------------------------------------------------------

def liquid_density(Gf: float) -> float:
    """
    Return liquid density at flowing conditions.

    Parameters
    ----------
    Gf : float
        Specific gravity relative to water at 15 °C [—].

    Returns
    -------
    float
        Liquid density [kg/m³].
    """
    return Gf * RHO_WATER_15C


def kinematic_viscosity(mu_cP: float, Gf: float) -> float:
    """
    Convert dynamic viscosity to kinematic viscosity.

    Parameters
    ----------
    mu_cP : float
        Dynamic viscosity [cP = mPa·s].
    Gf : float
        Specific gravity [—].

    Returns
    -------
    float
        Kinematic viscosity [cSt = mm²/s].
    """
    rho_g_per_cm3 = Gf * 0.9991   # density in g/cm³ (≈ RHO_WATER_15C/1000)
    return mu_cP / rho_g_per_cm3


# ---------------------------------------------------------------------------
# GAS PROPERTIES
# ---------------------------------------------------------------------------

def gas_density(P1_bar: float, T1_K: float, M: float, Z: float = 1.0) -> float:
    """
    Real gas density at inlet conditions using the equation of state.

    ρ₁ = P₁ × 10⁵ × M / (Z × R × T₁)

    Parameters
    ----------
    P1_bar : float
        Absolute inlet pressure [bar].
    T1_K : float
        Absolute inlet temperature [K].
    M : float
        Molecular weight [kg/kmol].
    Z : float
        Compressibility factor [—].  Default 1.0 (ideal gas).

    Returns
    -------
    float
        Gas density at (T1, P1) [kg/m³].
    """
    if Z <= 0:
        raise ValueError(f"Compressibility factor Z must be positive; got {Z}.")
    return (P1_bar * 1.0e5 * M) / (Z * R_UNIVERSAL * T1_K)


def speed_of_sound(gamma: float, T1_K: float, M: float) -> float:
    """
    Isentropic speed of sound in an ideal gas.

    c₁ = √(γ × R × T₁ / M)

    Parameters
    ----------
    gamma : float
        Isentropic exponent Cp/Cv [—].
    T1_K : float
        Absolute temperature [K].
    M : float
        Molecular weight [kg/kmol].

    Returns
    -------
    float
        Speed of sound [m/s].
    """
    return math.sqrt(gamma * R_UNIVERSAL * T1_K / M)


def gas_specific_gravity(M: float) -> float:
    """
    Gas specific gravity relative to air at standard conditions.

    Gg = M / M_air

    Parameters
    ----------
    M : float
        Molecular weight [kg/kmol].

    Returns
    -------
    float
        Specific gravity relative to air [—].
    """
    return M / M_AIR


def standard_volumetric_to_mass(q_s_nm3h: float, M: float, Z: float = 1.0) -> float:
    """
    Convert standard volumetric gas flow to mass flow.

    Uses standard conditions: 0 °C, 101.325 kPa.
    ρ_std = P_std × M / (R × T_std)

    Parameters
    ----------
    q_s_nm3h : float
        Standard volumetric flow [Nm³/h at 0 °C, 101.325 kPa].
    M : float
        Molecular weight [kg/kmol].
    Z : float
        Compressibility at standard conditions (≈ 1.0 for most gases).

    Returns
    -------
    float
        Mass flow [kg/h].
    """
    rho_std = (P_STD_BAR * 1.0e5 * M) / (Z * R_UNIVERSAL * T_STD_K)
    return q_s_nm3h * rho_std


def mass_to_standard_volumetric(W_kgh: float, M: float, Z: float = 1.0) -> float:
    """
    Convert mass flow to standard volumetric flow (inverse of above).

    Parameters
    ----------
    W_kgh : float
        Mass flow [kg/h].
    M : float
        Molecular weight [kg/kmol].
    Z : float
        Compressibility at standard conditions.

    Returns
    -------
    float
        Standard volumetric flow [Nm³/h].
    """
    rho_std = (P_STD_BAR * 1.0e5 * M) / (Z * R_UNIVERSAL * T_STD_K)
    return W_kgh / rho_std


# ---------------------------------------------------------------------------
# STEAM PROPERTIES  (IAPWS-IF97)
# ---------------------------------------------------------------------------

def get_steam_properties(T1_K: float, P1_bar: float,
                         steam_quality: float | None = None) -> SteamProps:
    """
    Retrieve thermodynamic properties of steam/water using IAPWS-IF97.

    Converts pressure from bar to MPa before calling the iapws library.
    P_MPa = P_bar / 10

    Parameters
    ----------
    T1_K : float
        Absolute inlet temperature [K].
    P1_bar : float
        Absolute inlet pressure [bar].
    steam_quality : float | None
        Dryness fraction for wet steam [0 ≤ x ≤ 1].
        None → superheated or saturated dry (determined from T1 vs T_sat).

    Returns
    -------
    SteamProps
        Named tuple with v1, gamma, phase, T_sat_K, vf, vg, steam_type.

    Raises
    ------
    SteamPropertyError
        If iapws library is not installed or conditions are outside IF97 range.
    """
    if not _IAPWS_AVAILABLE:
        raise SteamPropertyError(
            "The 'iapws' package is not installed. "
            "Run: pip install iapws>=1.5.2"
        )

    P_MPa = P1_bar / 10.0   # bar → MPa

    try:
        # --- Saturation properties at P1 ---
        sat_liq = IAPWS97(P=P_MPa, x=0)   # saturated liquid
        sat_vap = IAPWS97(P=P_MPa, x=1)   # saturated vapour
        T_sat_K = sat_vap.T              # saturation temperature [K]
        vf = sat_liq.v                   # m³/kg
        vg = sat_vap.v                   # m³/kg

        # --- Determine steam type ---
        if steam_quality is not None and steam_quality < 1.0:
            steam_type = SteamType.WET
            # Wet steam: quality-weighted specific volume
            v1 = vf + steam_quality * (vg - vf)
            gamma = sat_vap.gamma if hasattr(sat_vap, "gamma") else 1.135
            phase = "Two phase"
        elif T1_K > T_sat_K + 0.1:
            steam_type = SteamType.SUPERHEATED
            superheated = IAPWS97(T=T1_K, P=P_MPa)
            v1    = superheated.v
            gamma = superheated.gamma if hasattr(superheated, "gamma") else 1.30
            phase = superheated.phase
        else:
            steam_type = SteamType.SATURATED_DRY
            v1    = vg
            gamma = sat_vap.gamma if hasattr(sat_vap, "gamma") else 1.135
            phase = "gas"

    except Exception as exc:
        raise SteamPropertyError(
            f"IAPWS-IF97 lookup failed at T={T1_K:.2f} K, "
            f"P={P1_bar:.3f} bar: {exc}"
        ) from exc

    return SteamProps(
        v1=v1, gamma=gamma, phase=phase,
        T_sat_K=T_sat_K, vf=vf, vg=vg,
        steam_type=steam_type
    )


def wet_steam_specific_volume(vf: float, vg: float, quality: float) -> float:
    """
    Quality-weighted specific volume of wet (two-phase) steam.

    v_wet = v_f + x_q × (v_g − v_f)

    Parameters
    ----------
    vf : float
        Saturated liquid specific volume [m³/kg].
    vg : float
        Saturated vapour specific volume [m³/kg].
    quality : float
        Steam dryness fraction [0 ≤ x ≤ 1].

    Returns
    -------
    float
        Wet steam specific volume [m³/kg].
    """
    if not (0.0 <= quality <= 1.0):
        raise ValueError(f"Steam quality must be in [0, 1]; got {quality}.")
    return vf + quality * (vg - vf)