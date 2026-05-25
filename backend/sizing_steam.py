"""
Steam Cv sizing equations.
===========================
Implements IEC 60534-2-1:2011, Clause 5.2 applied to steam.
Uses IAPWS-IF97 specific volume from backend.fluid_properties.

Equations 6.1 – 6.5 from Step A3.
All inputs in SI units.  N₆ = 27.3.

Functions
---------
classify_steam_type    → Determine steam state from T1, P1, quality
cv_steam               → Master steam Cv dispatcher
"""

from __future__ import annotations

import math

from backend.constants import SI_N
from backend.fluid_properties import get_steam_properties, SteamProps
from backend.models import HardConstraintViolation, SteamType
from backend.sizing_gas import calc_Fgamma, calc_Y, Y_MIN

_N6 = SI_N["N6"]   # 27.3  (W in kg/h, P in bar, v in m³/kg)


# ---------------------------------------------------------------------------
# STEAM Cv  (specific volume form, Equations 6.1 – 6.3)
# ---------------------------------------------------------------------------

def _cv_steam_from_specific_volume(
    W_kgh: float,
    P1_bar: float,
    v1_m3kg: float,
    Y: float,
    x_eff: float,
    Fp: float = 1.0,
) -> float:
    """
    Cv from steam mass flow using inlet specific volume.

    Equations 6.1 / 6.2 / 6.3:
        Cv = W / (N₆ × Fp × Y) × √(v₁ / (x × P₁))

    Parameters
    ----------
    W_kgh   : float  Mass flow [kg/h].
    P1_bar  : float  Upstream pressure [bar abs].
    v1_m3kg : float  Specific volume at inlet [m³/kg].
    Y       : float  Expansion factor [—].
    x_eff   : float  Effective pressure differential ratio.
    Fp      : float  Piping geometry factor.

    Returns
    -------
    float
        Required Cv [—].
    """
    if v1_m3kg <= 0:
        raise HardConstraintViolation("ERR_STEAM_V1", "Steam specific volume v₁ must be positive.")
    if x_eff <= 0 or P1_bar <= 0:
        raise HardConstraintViolation("ERR_STEAM_PRESSURE", "x_eff and P1 must be positive.")
    inner = v1_m3kg / (x_eff * P1_bar)
    return (W_kgh / (_N6 * Fp * Y)) * math.sqrt(inner)


# ---------------------------------------------------------------------------
# MASTER STEAM DISPATCHER
# ---------------------------------------------------------------------------

def cv_steam(
    W_kgh: float,
    P1_bar: float,
    P2_bar: float,
    T1_K: float,
    xT: float,
    Fp: float = 1.0,
    xTP: float | None = None,
    steam_quality: float | None = None,
) -> tuple[float, float, float, float, bool, SteamProps]:
    """
    Master steam Cv dispatcher.

    Retrieves steam properties from IAPWS-IF97, classifies steam state,
    computes Y and the choked condition, then calls the specific-volume Cv equation.

    Parameters
    ----------
    W_kgh         : float         Mass flow [kg/h].
    P1_bar        : float         Upstream pressure [bar abs].
    P2_bar        : float         Downstream pressure [bar abs].
    T1_K          : float         Upstream temperature [K].
    xT            : float         Valve pressure differential ratio [—].
    Fp            : float         Piping geometry factor.
    xTP           : float | None  Combined xTP (fittings).
    steam_quality : float | None  Dryness fraction for wet steam.

    Returns
    -------
    tuple: (Cv, Fgamma, x, Y, is_choked, SteamProps)
    """
    # --- Retrieve IF97 properties ---
    props = get_steam_properties(T1_K, P1_bar, steam_quality)

    # Wet steam: warn if quality < 0.90
    if props.steam_type == SteamType.WET and (steam_quality or 1.0) < 0.90:
        # Caller (orchestrator) will add the warning message; we just proceed.
        pass

    # --- Gas expansion (same logic as gas, using steam γ) ---
    Fgamma          = calc_Fgamma(props.gamma)
    x               = (P1_bar - P2_bar) / P1_bar
    xT_eff          = xTP if (xTP is not None and Fp < 1.0) else xT
    Y, x_eff, choked = calc_Y(x, Fgamma, xT_eff)

    # --- Cv calculation ---
    Cv = _cv_steam_from_specific_volume(W_kgh, P1_bar, props.v1, Y, x_eff, Fp)

    return Cv, Fgamma, x, Y, choked, props