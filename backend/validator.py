"""
Input validation engine.
=========================
Implements all hard constraints (Section 12.1) and soft warnings (Section 12.2 / 12.3).

Hard constraint violations raise HardConstraintViolation immediately.
Soft warnings are collected and returned as a list[ValidationMessage].

validate_hard_constraints() must be called first in the orchestrator.
validate_soft_constraints() is called after the Cv is computed.
"""

from __future__ import annotations

import math

from backend.constants import (
    PT_RATINGS, NOISE_LIMIT_DBA, VELOCITY_LIMITS
)
from backend.models import (
    FluidPhase, HardConstraintViolation, MessageLevel,
    SizingInputs, SizingResult, ValidationMessage
)


# ---------------------------------------------------------------------------
# HARD CONSTRAINT VALIDATION
# ---------------------------------------------------------------------------

def validate_hard_constraints(inputs: SizingInputs) -> list[ValidationMessage]:
    """
    Check all hard constraints that abort the calculation.

    Raises HardConstraintViolation on the first fatal violation found.
    Returns a list of non-fatal informational messages collected during checks.

    Parameters
    ----------
    inputs : SizingInputs
        Composed root input model.

    Returns
    -------
    list[ValidationMessage]
        Informational messages (hard violations raise exceptions, not messages).

    Raises
    ------
    HardConstraintViolation
        On any fatal input error.
    """
    msgs: list[ValidationMessage] = []
    pc  = inputs.process
    fld = inputs.fluid
    vp  = inputs.valve

    # --- Pressure checks ---
    if pc.P1 <= 0:
        raise HardConstraintViolation("ERR_NONPOSITIVE_PRESSURE", "P1 must be > 0.")
    if pc.P2 <= 0:
        raise HardConstraintViolation("ERR_NONPOSITIVE_PRESSURE", "P2 must be > 0.")
    if pc.P2 >= pc.P1:
        raise HardConstraintViolation(
            "ERR_PRESSURE_INVERSION",
            f"P2 ({pc.P2:.3f}) must be strictly less than P1 ({pc.P1:.3f}). "
            "Check pressure inputs."
        )

    # --- Temperature check ---
    # Note: T1 stored in display °C/°F; orchestrator converts before math.
    # We validate the raw value is not clearly impossible.
    if pc.unit_system.value == "SI" and pc.T1 < -273.15:
        raise HardConstraintViolation("ERR_NONPOSITIVE_TEMP", "T1 is below absolute zero.")
    if pc.unit_system.value == "US" and pc.T1 < -459.67:
        raise HardConstraintViolation("ERR_NONPOSITIVE_TEMP", "T1 is below absolute zero.")

    # --- Flow check ---
    if pc.flow_value <= 0:
        raise HardConstraintViolation("ERR_NONPOSITIVE_FLOW", "Flow value must be strictly positive.")

    # --- Valve parameter ranges ---
    if not (0.10 < vp.FL < 1.00):
        raise HardConstraintViolation(
            "ERR_INVALID_FL",
            f"FL = {vp.FL:.3f} is outside the physical range (0.10, 1.00)."
        )
    if not (0.12 < vp.xT < 0.80):
        raise HardConstraintViolation(
            "ERR_INVALID_XT",
            f"xT = {vp.xT:.3f} is outside the physical range (0.12, 0.80)."
        )

    # --- Fluid-specific checks ---
    if pc.fluid_phase == FluidPhase.LIQUID:
        if fld.Gf is None or fld.Gf <= 0:
            raise HardConstraintViolation("ERR_MISSING_GF", "Specific gravity Gf is required for liquid.")
        if fld.Pv is None or fld.Pv < 0:
            raise HardConstraintViolation("ERR_MISSING_PV", "Vapour pressure Pv is required (≥ 0) for liquid.")
        if fld.Pc is None or fld.Pc <= 0:
            raise HardConstraintViolation("ERR_MISSING_PC", "Critical pressure Pc is required for liquid.")
        if fld.mu is None or fld.mu <= 0:
            raise HardConstraintViolation("ERR_MISSING_MU", "Dynamic viscosity μ is required for liquid.")
        if fld.Pv >= fld.Pc:
            raise HardConstraintViolation(
                "ERR_INVALID_PC_PV",
                f"Pv ({fld.Pv:.3f}) must be less than Pc ({fld.Pc:.3f})."
            )
        if fld.Pv >= pc.P1:
            raise HardConstraintViolation(
                "ERR_PV_EXCEEDS_P1",
                f"Vapour pressure Pv ({fld.Pv:.3f}) ≥ P1 ({pc.P1:.3f}). "
                "Fluid is already vaporised at inlet."
            )

    elif pc.fluid_phase == FluidPhase.GAS:
        if fld.M is None or fld.M <= 0:
            raise HardConstraintViolation("ERR_MISSING_M", "Molecular weight M is required for gas.")
        if fld.gamma is None or fld.gamma <= 1.0:
            raise HardConstraintViolation(
                "ERR_INVALID_GAMMA",
                f"Isentropic exponent γ must be > 1.0; got {fld.gamma}."
            )
        if fld.Z <= 0:
            raise HardConstraintViolation("ERR_INVALID_Z", "Compressibility Z must be positive.")

    # --- Pipe geometry check ---
    if vp.D1 and vp.D1 < vp.d:
        msgs.append(ValidationMessage(
            code="INFO_PIPE_REDUCER",
            level=MessageLevel.INFO,
            message=f"Upstream reducer detected: D1={vp.D1:.1f} mm < d={vp.d:.1f} mm. "
                    "Piping correction factors (Fp, FLP) will be applied."
        ))
    if vp.D2 and vp.D2 < vp.d:
        msgs.append(ValidationMessage(
            code="INFO_PIPE_EXPANDER",
            level=MessageLevel.INFO,
            message=f"Downstream expander detected: D2={vp.D2:.1f} mm < d={vp.d:.1f} mm."
        ))

    return msgs


# ---------------------------------------------------------------------------
# SOFT WARNING VALIDATION
# ---------------------------------------------------------------------------

def validate_soft_constraints(
    result: SizingResult,
    inputs: SizingInputs,
) -> list[ValidationMessage]:
    """
    Check all soft constraints after Cv has been computed.

    Parameters
    ----------
    result : SizingResult  Partially assembled result (Cv fields populated).
    inputs : SizingInputs  Original inputs.

    Returns
    -------
    list[ValidationMessage]
        All applicable soft warnings and infos.
    """
    msgs: list[ValidationMessage] = []
    pc  = inputs.process
    vp  = inputs.valve

    # --- Choked flow ---
    if result.is_choked and pc.fluid_phase == FluidPhase.LIQUID:
        msgs.append(ValidationMessage(
            code="WARN_CHOKED_LIQUID",
            level=MessageLevel.WARNING,
            message="Liquid flow is choked. ΔP exceeds the maximum effective ΔP_max. "
                    "Increasing pressure drop will NOT increase flow. "
                    "Cv has been calculated using ΔP_max."
        ))
    if result.is_choked and pc.fluid_phase in (FluidPhase.GAS, FluidPhase.STEAM):
        msgs.append(ValidationMessage(
            code="WARN_CHOKED_GAS",
            level=MessageLevel.WARNING,
            message="Gas / steam flow is choked (sonic at vena contracta). "
                    "Expansion factor Y has been set to 2/3."
        ))

    # --- Cavitation ---
    if result.cavitation is not None:
        cav = result.cavitation
        from backend.models import CavitationRegime
        regime_messages = {
            CavitationRegime.INCIPIENT: (
                "WARN_CAVITATION_INCIPIENT", MessageLevel.WARNING,
                "Incipient cavitation: bubble formation is beginning. "
                "Increased noise levels expected. Monitor trim condition."
            ),
            CavitationRegime.CONSTANT: (
                "WARN_CAVITATION_CONSTANT", MessageLevel.WARNING,
                "Constant cavitation: established cavitation present. "
                "Material damage is occurring. Consider anti-cavitation trim."
            ),
            CavitationRegime.CHOKED: (
                "WARN_CAVITATION_CHOKED", MessageLevel.ERROR,
                "Choked cavitation (supercavitation): severe material damage. "
                "Anti-cavitation trim or multi-stage pressure reduction required."
            ),
            CavitationRegime.FLASHING: (
                "WARN_FLASHING", MessageLevel.ERROR,
                "Flashing: downstream pressure is below vapour pressure. "
                "Two-phase exit — hardened trim, enlarged outlet body, and "
                "downstream expansion must be provided."
            ),
        }
        if cav.regime in regime_messages:
            code, level, message = regime_messages[cav.regime]
            msgs.append(ValidationMessage(code=code, level=level, message=message))

    # --- Viscous correction ---
    if result.FR is not None and result.FR < 1.0:
        msgs.append(ValidationMessage(
            code="WARN_VISCOUS",
            level=MessageLevel.WARNING,
            message=f"Viscous flow detected (Rev = {result.Rev:.0f}, FR = {result.FR:.3f}). "
                    "Reynolds Number Factor has been applied. Cv is higher than turbulent value."
        ))

    # --- Sizing ratio ---
    if result.sizing_ratio is not None:
        sr = result.sizing_ratio
        if sr > 1.00:
            msgs.append(ValidationMessage(
                code="ERR_UNDERSIZED",
                level=MessageLevel.ERROR,
                message=f"Valve is UNDERSIZED: Cv_required ({result.Cv_required:.1f}) "
                        f"exceeds Cv_rated ({vp.Cv_rated:.1f}). Flow target cannot be achieved."
            ))
        elif sr < 0.20:
            msgs.append(ValidationMessage(
                code="WARN_OVERSIZED",
                level=MessageLevel.WARNING,
                message=f"Valve is severely oversized (ratio = {sr:.2%}). "
                        "Consider a smaller valve for better controllability."
            ))
        elif sr < 0.60:
            msgs.append(ValidationMessage(
                code="INFO_OVERSIZED",
                level=MessageLevel.INFO,
                message=f"Valve sizing ratio = {sr:.2%}. A smaller size may improve control."
            ))
        elif sr > 0.85:
            msgs.append(ValidationMessage(
                code="WARN_NEAR_CAPACITY",
                level=MessageLevel.WARNING,
                message=f"Valve sizing ratio = {sr:.2%}. Near full capacity. "
                        "Consider a larger valve to maintain control margin."
            ))

    # --- Opening percentage ---
    if result.opening_pct is not None:
        op = result.opening_pct
        if op < 10.0:
            msgs.append(ValidationMessage(
                code="WARN_LOW_OPENING",
                level=MessageLevel.WARNING,
                message=f"Estimated valve opening at normal flow is {op:.1f} %. "
                        "Opening below 10 % gives poor controllability."
            ))
        elif op > 90.0:
            msgs.append(ValidationMessage(
                code="WARN_HIGH_OPENING",
                level=MessageLevel.WARNING,
                message=f"Estimated valve opening at normal flow is {op:.1f} %. "
                        "Opening above 90 % leaves insufficient control headroom."
            ))

    # --- Noise ---
    if result.noise is not None and result.noise.exceeds_limit:
        msgs.append(ValidationMessage(
            code="WARN_NOISE_LIMIT",
            level=MessageLevel.WARNING,
            message=f"Predicted noise level {result.noise.Lpe_dba:.1f} dBA exceeds "
                    f"the limit of {inputs.noise_limit_dba:.0f} dBA. "
                    "Consider noise attenuating trim or acoustic insulation."
        ))

    # --- Velocity ---
    if result.velocity_ms is not None:
        _check_velocity(result.velocity_ms, pc.fluid_phase, msgs)

    # --- Wet steam warning ---
    if result.steam_type is not None:
        from backend.models import SteamType
        if result.steam_type == SteamType.WET:
            msgs.append(ValidationMessage(
                code="WARN_WET_STEAM",
                level=MessageLevel.WARNING,
                message="Wet steam service: steam quality is below 1.0. "
                        "Erosion risk — use hardened trim and verify quality at valve inlet."
            ))

    # --- P-T rating check ---
    pt_msg = check_PT_rating(
        inputs.process.P1,
        inputs.pressure_class,
        inputs.process.T1,
        inputs.process.unit_system.value,
    )
    if pt_msg:
        msgs.append(pt_msg)

    return msgs


def _check_velocity(
    velocity_ms: float,
    fluid_phase: FluidPhase,
    msgs: list[ValidationMessage],
) -> None:
    """Append velocity warnings to msgs in-place."""
    if fluid_phase == FluidPhase.LIQUID:
        lims = VELOCITY_LIMITS["liquid_clean"]
        if velocity_ms > lims["reject"]:
            msgs.append(ValidationMessage(
                code="WARN_HIGH_VELOCITY",
                level=MessageLevel.WARNING,
                message=f"Downstream pipe velocity {velocity_ms:.1f} m/s exceeds "
                        f"the reject threshold of {lims['reject']:.0f} m/s. Erosion risk."
            ))
        elif velocity_ms > lims["warn"]:
            msgs.append(ValidationMessage(
                code="INFO_HIGH_VELOCITY",
                level=MessageLevel.INFO,
                message=f"Downstream pipe velocity {velocity_ms:.1f} m/s is above "
                        f"the recommended limit of {lims['warn']:.0f} m/s."
            ))
    elif fluid_phase == FluidPhase.STEAM:
        lims = VELOCITY_LIMITS["steam"]
        if velocity_ms > lims["reject"]:
            msgs.append(ValidationMessage(
                code="WARN_HIGH_VELOCITY",
                level=MessageLevel.WARNING,
                message=f"Steam velocity {velocity_ms:.1f} m/s exceeds {lims['reject']:.0f} m/s."
            ))


def check_PT_rating(
    P1: float,
    pressure_class: str,
    T1_display: float,
    unit_system: str,
) -> ValidationMessage | None:
    """
    Check if inlet pressure exceeds ASME B16.34 P-T rating.

    Parameters
    ----------
    P1             : float  Inlet pressure in user's units.
    pressure_class : str    e.g. 'Class300'.
    T1_display     : float  Inlet temperature in user's display units.
    unit_system    : str    'SI' or 'US'.

    Returns
    -------
    ValidationMessage or None.
    """
    if pressure_class not in PT_RATINGS:
        return None

    # Convert T1 to °C for table lookup
    T1_C = T1_display if unit_system == "SI" else (T1_display - 32.0) * 5.0 / 9.0

    # Convert P1 to bar abs for comparison
    P1_bar = P1 if unit_system == "SI" else P1 / 14.504

    rating_curve = PT_RATINGS[pressure_class]

    # Interpolate P-T rating at T1_C
    if T1_C <= rating_curve[0][0]:
        P_rated = rating_curve[0][1]
    elif T1_C >= rating_curve[-1][0]:
        P_rated = rating_curve[-1][1]
    else:
        for i in range(len(rating_curve) - 1):
            T_a, P_a = rating_curve[i]
            T_b, P_b = rating_curve[i + 1]
            if T_a <= T1_C <= T_b:
                t       = (T1_C - T_a) / (T_b - T_a)
                P_rated = P_a + t * (P_b - P_a)
                break
        else:
            return None

    if P1_bar > P_rated:
        return ValidationMessage(
            code="WARN_PTRATING",
            level=MessageLevel.ERROR,
            message=f"Inlet pressure {P1_bar:.1f} bar exceeds ASME B16.34 {pressure_class} "
                    f"rating of {P_rated:.1f} bar at {T1_C:.0f} °C. "
                    "Upgrade pressure class or reduce operating pressure."
        )
    return None