"""
Master sizing coordinator.
===========================
This is the ONLY file that app.py and the frontend import from the backend.
All other backend modules are internal implementation details.

Public API:
    run_sizing(inputs: SizingInputs) -> SizingResult

Execution order (Step A3, Master Decision Logic):
    1.  validate_hard_constraints()
    2.  Unit conversion: user units → SI
    3.  Fluid property calculation
    4.  Piping geometry factors (Fp, FLP, xTP) — iterative
    5.  Fluid branch dispatch (LIQUID / GAS / STEAM)
       5a. Liquid: cavitation analysis + viscous correction
       5b. Gas:    Y factor, choked check
       5c. Steam:  IF97 properties, same gas logic
    6.  Noise prediction (aerodynamic or hydrodynamic)
    7.  Output metrics (Cv ratio, opening %, velocity)
    8.  validate_soft_constraints()
    9.  Assemble and return SizingResult
"""

from __future__ import annotations

import math
import traceback

from backend.cavitation import analyse_cavitation, calc_delta_P_eff
from backend.constants import CV_TO_KV, SIZING_MARGINS, SI_N
from backend.fluid_properties import (
    gas_density, kinematic_viscosity, liquid_density,
    mass_to_standard_volumetric, speed_of_sound,
    standard_volumetric_to_mass,
)
from backend.models import (
    FlowBasis, FluidPhase, HardConstraintViolation, MessageLevel,
    SizingInputs, SizingResult, SteamType, UnitSystem, ValidationMessage,
)
from backend.noise_aerodynamic import run_aero_noise
from backend.noise_hydrodynamic import run_hydro_noise
from backend.piping_geometry import (
    calc_FLP, calc_Fp_iterative, calc_xTP,
    fitting_loss_coefficients, sum_loss_coefficients,
)
from backend.sizing_gas import cv_gas
from backend.sizing_liquid import cv_liquid
from backend.sizing_steam import cv_steam
from backend.validator import validate_hard_constraints, validate_soft_constraints
from backend.viscous_correction import apply_viscous_correction


# ---------------------------------------------------------------------------
# UNIT CONVERSION HELPERS
# ---------------------------------------------------------------------------

def _to_SI_pressure(P: float, unit_system: UnitSystem) -> float:
    """Convert pressure to bar absolute."""
    return P / 14.504 if unit_system == UnitSystem.US else P


def _to_SI_temperature(T: float, unit_system: UnitSystem) -> float:
    """Convert temperature to Kelvin."""
    if unit_system == UnitSystem.US:
        return (T - 32.0) * 5.0 / 9.0 + 273.15   # °F → K
    return T + 273.15                               # °C → K


def _to_SI_flow_liquid(flow: float, basis: FlowBasis, unit_system: UnitSystem,
                       Gf: float = 1.0) -> tuple[float, float]:
    """
    Convert liquid flow to (Q_m3h, W_kgh) in SI.

    Returns
    -------
    tuple[float, float]
        (Q_m3h, W_kgh)
    """
    if unit_system == UnitSystem.US:
        if basis == FlowBasis.VOLUMETRIC:
            Q_m3h = flow * 0.22712          # US GPM → m³/h
            W_kgh = Q_m3h * liquid_density(Gf)
        else:
            W_kgh = flow * 0.453592         # lb/h → kg/h
            Q_m3h = W_kgh / liquid_density(Gf)
    else:
        if basis == FlowBasis.VOLUMETRIC:
            Q_m3h = flow
            W_kgh = Q_m3h * liquid_density(Gf)
        else:
            W_kgh = flow
            Q_m3h = W_kgh / liquid_density(Gf)
    return Q_m3h, W_kgh


def _to_SI_flow_gas(flow: float, basis: FlowBasis, unit_system: UnitSystem,
                    M: float, Z: float) -> tuple[float, float]:
    """
    Convert gas flow to (q_s_Nm3h, W_kgh) in SI.

    Returns
    -------
    tuple[float, float]
        (q_s_Nm3h, W_kgh)
    """
    if unit_system == UnitSystem.US:
        if basis == FlowBasis.VOLUMETRIC:
            q_s_Nm3h = flow * 0.026853      # SCFH → Nm³/h
            W_kgh    = standard_volumetric_to_mass(q_s_Nm3h, M, Z)
        else:
            W_kgh    = flow * 0.453592      # lb/h → kg/h
            q_s_Nm3h = mass_to_standard_volumetric(W_kgh, M, Z)
    else:
        if basis == FlowBasis.VOLUMETRIC:
            q_s_Nm3h = flow
            W_kgh    = standard_volumetric_to_mass(q_s_Nm3h, M, Z)
        else:
            W_kgh    = flow
            q_s_Nm3h = mass_to_standard_volumetric(W_kgh, M, Z)
    return q_s_Nm3h, W_kgh


def _to_SI_flow_steam(flow: float, basis: FlowBasis, unit_system: UnitSystem) -> float:
    """Convert steam flow to W_kgh (steam is always mass-flow based)."""
    if unit_system == UnitSystem.US:
        return flow * 0.453592 if basis == FlowBasis.MASS else flow * 0.453592
    return flow


def _to_SI_dimension(d: float, unit_system: UnitSystem) -> float:
    """Convert valve/pipe dimension to mm."""
    return d * 25.4 if unit_system == UnitSystem.US else d


# ---------------------------------------------------------------------------
# OUTPUT METRIC CALCULATIONS
# ---------------------------------------------------------------------------

def _calc_opening_pct(
    Cv_required: float,
    Cv_rated: float,
    R_inherent: float,
    char: str,
) -> float:
    """
    Estimate valve opening % at the computed Cv.

    Equal-percentage (Eq 11.3):
        Opening% = 100 × log(Cv/Cv_min) / log(Cv_rated/Cv_min)

    Linear (Eq 11.4):
        Opening% = 100 × Cv / Cv_rated

    Parameters
    ----------
    Cv_required  : float  Required Cv [—].
    Cv_rated     : float  Manufacturer rated Cv [—].
    R_inherent   : float  Inherent valve rangeability [—].
    char         : str    'equal_percentage' | 'linear' | 'quick_opening'.

    Returns
    -------
    float
        Opening [%], clamped to [0, 100].
    """
    if Cv_rated <= 0 or Cv_required <= 0:
        return 0.0

    ratio = min(Cv_required / Cv_rated, 1.0)
    Cv_min = Cv_rated / max(R_inherent, 1.0)

    if char == "equal_percentage":
        if Cv_required <= Cv_min:
            return 0.0
        opening = 100.0 * math.log(Cv_required / Cv_min) / math.log(Cv_rated / Cv_min)
    elif char == "linear":
        opening = 100.0 * ratio
    else:   # quick_opening
        opening = 100.0 * math.sqrt(ratio)

    return max(0.0, min(opening, 100.0))


def _calc_velocity_ms(
    fluid_phase: FluidPhase,
    W_kgh: float,
    Q_m3h: float,
    rho1_kgm3: float,
    D2_mm: float,
) -> float:
    """
    Downstream pipe flow velocity.

    Liquid (Eq 11.5):  v = Q [m³/s] / A [m²]
    Gas / Steam (Eq 11.6):  v = (W/3600) / (ρ₂ × A)

    Uses the inlet density as a conservative approximation for gas density.
    """
    D2_m = D2_mm / 1_000.0
    A    = math.pi * (D2_m / 2.0) ** 2   # pipe cross-sectional area [m²]

    if fluid_phase == FluidPhase.LIQUID:
        Q_m3s = Q_m3h / 3_600.0
        return Q_m3s / max(A, 1.0e-6)
    else:
        W_kgs = W_kgh / 3_600.0
        return W_kgs / max(rho1_kgm3 * A, 1.0e-6)


# ---------------------------------------------------------------------------
# MASTER SIZING FUNCTION
# ---------------------------------------------------------------------------

def run_sizing(inputs: SizingInputs) -> SizingResult:
    """
    Execute the complete control valve sizing calculation.

    This is the single external entry-point for all sizing computations.
    The frontend calls only this function; all other backend modules are
    internal to the package.

    Parameters
    ----------
    inputs : SizingInputs
        Fully populated input model (process conditions, fluid properties,
        valve parameters).

    Returns
    -------
    SizingResult
        Complete sizing result including Cv, fluid state flags, noise,
        cavitation analysis, output metrics, and all validation messages.
        ``success = False`` when a hard constraint is violated; in that case
        ``Cv_required`` is None but ``messages`` contains the error detail.
    """
    all_messages: list[ValidationMessage] = []

    # =========================================================================
    # STEP 1 — HARD CONSTRAINT VALIDATION
    # =========================================================================
    try:
        info_msgs = validate_hard_constraints(inputs)
        all_messages.extend(info_msgs)
    except HardConstraintViolation as exc:
        return SizingResult(
            success=False,
            messages=[ValidationMessage(
                code=exc.code,
                level=MessageLevel.ERROR,
                message=str(exc),
            )],
        )
    except Exception as exc:
        return SizingResult(
            success=False,
            messages=[ValidationMessage(
                code="ERR_VALIDATION_UNEXPECTED",
                level=MessageLevel.ERROR,
                message=f"Unexpected validation error: {exc}",
            )],
        )

    # =========================================================================
    # STEP 2 — UNIT CONVERSION (user units → SI absolute values)
    # =========================================================================
    try:
        pc   = inputs.process
        fld  = inputs.fluid
        vp   = inputs.valve
        us   = pc.unit_system

        P1_bar = _to_SI_pressure(pc.P1, us)
        P2_bar = _to_SI_pressure(pc.P2, us)
        T1_K   = _to_SI_temperature(pc.T1, us)
        d_mm   = _to_SI_dimension(vp.d, us)
        D1_mm  = _to_SI_dimension(vp.D1 or vp.d, us)
        D2_mm  = _to_SI_dimension(vp.D2 or vp.d, us)

        # Valve-side fluid properties (phase-specific conversion)
        if pc.fluid_phase == FluidPhase.LIQUID:
            Pv_bar = _to_SI_pressure(fld.Pv or 0.0, us)
            Pc_bar = _to_SI_pressure(fld.Pc or 220.0, us)
            Q_m3h, W_kgh = _to_SI_flow_liquid(
                pc.flow_value, pc.flow_basis, us, fld.Gf or 1.0
            )
            rho1_kgm3 = liquid_density(fld.Gf or 1.0)
            nu_cSt    = kinematic_viscosity(fld.mu or 1.0, fld.Gf or 1.0)

        elif pc.fluid_phase == FluidPhase.GAS:
            _, W_kgh = _to_SI_flow_gas(
                pc.flow_value, pc.flow_basis, us, fld.M or 28.97, fld.Z
            )
            rho1_kgm3 = gas_density(P1_bar, T1_K, fld.M or 28.97, fld.Z)
            Q_m3h     = 0.0   # not used for gas sizing

        else:   # STEAM
            W_kgh     = _to_SI_flow_steam(pc.flow_value, pc.flow_basis, us)
            Q_m3h     = 0.0
            rho1_kgm3 = 0.0   # set after IF97 lookup

    except HardConstraintViolation as exc:
        return SizingResult(
            success=False,
            messages=[ValidationMessage(
                code=exc.code, level=MessageLevel.ERROR, message=str(exc)
            )],
        )
    except Exception as exc:
        return SizingResult(
            success=False,
            messages=[ValidationMessage(
                code="ERR_UNIT_CONVERSION",
                level=MessageLevel.ERROR,
                message=f"Unit conversion failed: {exc}",
            )],
        )

    # =========================================================================
    # STEP 3 — PIPING GEOMETRY FACTORS
    # =========================================================================
    try:
        coeffs        = fitting_loss_coefficients(d_mm, D1_mm, D2_mm)
        sum_xi, sum_xi1 = sum_loss_coefficients(coeffs)
        has_fittings  = (sum_xi != 0.0)

        # For liquid/gas initial Fp, start with Fp=1 estimate then iterate
        # Fp and FLP are refined after initial Cv is computed in Step 5.
        Fp  = 1.0
        FLP = None
        xTP = None

    except Exception as exc:
        return SizingResult(
            success=False,
            messages=[ValidationMessage(
                code="ERR_PIPING_GEOMETRY",
                level=MessageLevel.ERROR,
                message=f"Piping geometry factor calculation failed: {exc}",
            )],
        )

    # =========================================================================
    # STEP 4 — FLUID BRANCH DISPATCH
    # =========================================================================
    Cv_required   = None
    FF_val        = None
    delta_P_max   = None
    delta_P_eff   = None
    Y_val         = None
    Fgamma_val    = None
    x_val         = None
    is_choked     = False
    FR_val        = None
    Rev_val       = None
    steam_type    = None
    steam_props   = None
    cavitation_result = None
    noise_result  = None

    try:
        # ── 4A: LIQUID ────────────────────────────────────────────────────────
        if pc.fluid_phase == FluidPhase.LIQUID:

            # First pass: no fittings correction (Fp = 1)
            Cv0, FF_val, delta_P_max, delta_P_eff, is_choked = cv_liquid(
                Q_m3h, fld.Gf or 1.0, P1_bar, P2_bar,
                Pv_bar, Pc_bar, vp.FL, Fp=1.0, FLP=None
            )

            # Viscous correction
            nu_cSt_val = nu_cSt
            if nu_cSt_val > 1.0:   # non-negligible viscosity
                try:
                    Cv_visc, Rev_val, FR_val = apply_viscous_correction(
                        Cv0, Q_m3h, nu_cSt_val, vp.FL, vp.Fd, d_mm
                    )
                except Exception:
                    Cv_visc, Rev_val, FR_val = Cv0, None, 1.0
            else:
                Cv_visc  = Cv0
                Rev_val  = None
                FR_val   = 1.0

            # Piping geometry refinement (iterative)
            if has_fittings:
                try:
                    Fp, Cv_fp = calc_Fp_iterative(Cv_visc, d_mm, sum_xi)
                    FLP_val   = calc_FLP(vp.FL, Cv_fp, d_mm, sum_xi1)
                    # Recompute with corrected Fp and FLP
                    Cv_required, FF_val, delta_P_max, delta_P_eff, is_choked = cv_liquid(
                        Q_m3h, fld.Gf or 1.0, P1_bar, P2_bar,
                        Pv_bar, Pc_bar, vp.FL, Fp=Fp, FLP=FLP_val
                    )
                    FLP = FLP_val
                except Exception:
                    Cv_required = Cv_visc   # fallback to no-fittings result
            else:
                Cv_required = Cv_visc

            # Cavitation analysis
            cavitation_result = analyse_cavitation(
                P1_bar, P2_bar, Pv_bar, Pc_bar, vp.FL
            )

            # Hydrodynamic noise
            try:
                Di_m    = D2_mm / 1_000.0
                t_wall  = vp.t_wall_mm / 1_000.0
                dP_i    = cavitation_result.delta_P_incipient
                noise_result = run_hydro_noise(
                    Q_m3h=Q_m3h,
                    P1_bar=P1_bar,
                    Pv_bar=Pv_bar,
                    FF=FF_val,
                    rho_L=rho1_kgm3,
                    Di_m=Di_m,
                    t_wall_m=t_wall,
                    delta_P_i_bar=dP_i,
                    delta_P_bar=(P1_bar - P2_bar),
                    cavitation_regime=cavitation_result.regime,
                )
            except Exception:
                noise_result = None

        # ── 4B: GAS ───────────────────────────────────────────────────────────
        elif pc.fluid_phase == FluidPhase.GAS:

            gamma_val = fld.gamma or 1.40
            M_val     = fld.M or 28.97
            Z_val     = fld.Z

            # First pass: no fittings
            Cv0, Fgamma_val, x_val, Y_val, is_choked = cv_gas(
                W_kgh, P1_bar, P2_bar, rho1_kgm3,
                gamma_val, vp.xT, Fp=1.0, xTP=None
            )

            # Piping geometry refinement
            if has_fittings:
                try:
                    Fp, Cv_fp = calc_Fp_iterative(Cv0, d_mm, sum_xi)
                    xTP_val   = calc_xTP(vp.xT, Fp, Cv_fp, d_mm, sum_xi1)
                    Cv_required, Fgamma_val, x_val, Y_val, is_choked = cv_gas(
                        W_kgh, P1_bar, P2_bar, rho1_kgm3,
                        gamma_val, vp.xT, Fp=Fp, xTP=xTP_val
                    )
                    xTP = xTP_val
                except Exception:
                    Cv_required = Cv0
            else:
                Cv_required = Cv0

            # Aerodynamic noise
            try:
                Di_m   = D2_mm / 1_000.0
                t_wall = vp.t_wall_mm / 1_000.0
                noise_result = run_aero_noise(
                    W_kgh=W_kgh, P1_bar=P1_bar, P2_bar=P2_bar,
                    T1_K=T1_K, gamma=gamma_val, M=M_val,
                    Di_m=Di_m, t_wall_m=t_wall, Fd=vp.Fd,
                )
            except Exception:
                noise_result = None

        # ── 4C: STEAM ─────────────────────────────────────────────────────────
        elif pc.fluid_phase == FluidPhase.STEAM:

            quality = fld.steam_quality

            # First pass: no fittings
            Cv0, Fgamma_val, x_val, Y_val, is_choked, steam_props = cv_steam(
                W_kgh, P1_bar, P2_bar, T1_K,
                xT=vp.xT, Fp=1.0, xTP=None,
                steam_quality=quality,
            )
            steam_type    = steam_props.steam_type
            rho1_kgm3     = 1.0 / max(steam_props.v1, 1.0e-6)

            # Piping geometry refinement
            if has_fittings:
                try:
                    Fp, Cv_fp = calc_Fp_iterative(Cv0, d_mm, sum_xi)
                    xTP_val   = calc_xTP(vp.xT, Fp, Cv_fp, d_mm, sum_xi1)
                    Cv_required, Fgamma_val, x_val, Y_val, is_choked, _ = cv_steam(
                        W_kgh, P1_bar, P2_bar, T1_K,
                        xT=vp.xT, Fp=Fp, xTP=xTP_val,
                        steam_quality=quality,
                    )
                    xTP = xTP_val
                except Exception:
                    Cv_required = Cv0
            else:
                Cv_required = Cv0

            # Aerodynamic noise (steam treated as gas)
            try:
                Di_m   = D2_mm / 1_000.0
                t_wall = vp.t_wall_mm / 1_000.0
                noise_result = run_aero_noise(
                    W_kgh=W_kgh, P1_bar=P1_bar, P2_bar=P2_bar,
                    T1_K=T1_K, gamma=steam_props.gamma, M=18.015,
                    Di_m=Di_m, t_wall_m=t_wall, Fd=vp.Fd,
                )
            except Exception:
                noise_result = None

    except HardConstraintViolation as exc:
        return SizingResult(
            success=False,
            messages=[ValidationMessage(
                code=exc.code, level=MessageLevel.ERROR, message=str(exc)
            )],
        )
    except Exception as exc:
        return SizingResult(
            success=False,
            messages=[ValidationMessage(
                code="ERR_SIZING_ENGINE",
                level=MessageLevel.ERROR,
                message=f"Sizing engine error: {exc}\n{traceback.format_exc()}",
            )],
        )

    # =========================================================================
    # STEP 5 — SIZING MARGIN AND Kv
    # =========================================================================
    margin_factor = 1.0 + inputs.sizing_margin_pct / 100.0
    Cv_design     = Cv_required * margin_factor
    Kv_required   = Cv_required * CV_TO_KV

    # =========================================================================
    # STEP 6 — OUTPUT METRICS
    # =========================================================================
    sizing_ratio = None
    opening_pct  = None
    velocity_ms  = None

    if vp.Cv_rated and vp.Cv_rated > 0:
        sizing_ratio = Cv_required / vp.Cv_rated
        opening_pct  = _calc_opening_pct(
            Cv_required, vp.Cv_rated, vp.R_inherent, vp.char.value
        )

    velocity_ms = _calc_velocity_ms(
        pc.fluid_phase, W_kgh, Q_m3h, rho1_kgm3, D2_mm
    )

    # =========================================================================
    # STEP 7 — ASSEMBLE RESULT (partial — before soft warnings)
    # =========================================================================
    result = SizingResult(
        success=True,
        Cv_required=round(Cv_required, 3),
        Cv_design=round(Cv_design, 3),
        Kv_required=round(Kv_required, 3),
        fluid_phase=pc.fluid_phase,
        steam_type=steam_type,
        is_choked=is_choked,
        cavitation=cavitation_result,
        noise=noise_result,
        FF=round(FF_val, 4) if FF_val is not None else None,
        delta_P_max_bar=round(delta_P_max, 4) if delta_P_max is not None else None,
        delta_P_eff_bar=round(delta_P_eff, 4) if delta_P_eff is not None else None,
        Y=round(Y_val, 4) if Y_val is not None else None,
        Fp=round(Fp, 4),
        FLP=round(FLP, 4) if FLP is not None else None,
        xTP=round(xTP, 4) if xTP is not None else None,
        FR=round(FR_val, 4) if FR_val is not None else None,
        Rev=round(Rev_val, 1) if Rev_val is not None else None,
        Fgamma=round(Fgamma_val, 4) if Fgamma_val is not None else None,
        x=round(x_val, 4) if x_val is not None else None,
        sizing_ratio=round(sizing_ratio, 4) if sizing_ratio is not None else None,
        opening_pct=round(opening_pct, 1) if opening_pct is not None else None,
        velocity_ms=round(velocity_ms, 2) if velocity_ms is not None else None,
        P1_bar=round(P1_bar, 4),
        P2_bar=round(P2_bar, 4),
        T1_K=round(T1_K, 2),
        W_kgh=round(W_kgh, 3),
        Q_m3h=round(Q_m3h, 3),
        rho1_kgm3=round(rho1_kgm3, 4),
        messages=all_messages,
    )

    # =========================================================================
    # STEP 8 — SOFT CONSTRAINT VALIDATION
    # =========================================================================
    try:
        soft_msgs = validate_soft_constraints(result, inputs)
        all_messages.extend(soft_msgs)
        result.messages = all_messages
    except Exception:
        pass   # Soft warnings must never abort the result

    return result