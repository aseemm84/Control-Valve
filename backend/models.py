"""
Pydantic v2 data models for the control valve sizing engine.
=============================================================
All input models store values in the user's chosen unit system.
The orchestrator converts them to SI before invoking math functions.
All output models store computed SI values; the frontend converts for display.

Models defined here:
  Enums       → FluidPhase, UnitSystem, FlowBasis, SteamType,
                ValveCharacteristic, CavitationRegime, AeroRegime,
                MessageLevel
  Inputs      → FluidProperties, ValveParameters, ProcessConditions,
                SizingInputs
  Outputs     → CavitationResult, NoiseResult, SizingResult
  Messaging   → ValidationMessage
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ===========================================================================
# ENUMERATIONS
# ===========================================================================

class FluidPhase(str, Enum):
    """Primary fluid phase at valve inlet."""
    LIQUID = "liquid"
    GAS    = "gas"
    STEAM  = "steam"


class UnitSystem(str, Enum):
    """Active unit system for all user-facing I/O."""
    SI = "SI"   # bar, m³/h, kg/h, mm, K/°C
    US = "US"   # psi, GPM/SCFH, lb/h, in, °R/°F


class FlowBasis(str, Enum):
    """Whether the user-supplied flow is volumetric or mass-based."""
    VOLUMETRIC = "volumetric"   # Q: m³/h or GPM (liquid); Nm³/h or SCFH (gas)
    MASS       = "mass"         # W: kg/h or lb/h


class SteamType(str, Enum):
    """Steam state at valve inlet (relevant only when FluidPhase = STEAM)."""
    SUPERHEATED   = "superheated"
    SATURATED_DRY = "saturated_dry"   # quality = 1.0
    WET           = "wet"             # 0 < quality < 1


class ValveCharacteristic(str, Enum):
    """Inherent flow characteristic curve of the selected valve."""
    EQUAL_PERCENTAGE = "equal_percentage"
    LINEAR           = "linear"
    QUICK_OPENING    = "quick_opening"


class CavitationRegime(str, Enum):
    """Five-tier cavitation severity classification (IEC 60534-8-4, §5)."""
    NONE          = "none"
    INCIPIENT     = "incipient"
    CONSTANT      = "constant"
    CHOKED        = "choked"
    FLASHING      = "flashing"


class AeroRegime(str, Enum):
    """Aerodynamic noise flow regime (IEC 60534-8-3, §5)."""
    SUBCRITICAL = "subcritical"   # rP > rP_crit
    CHOKED      = "choked"        # rP ≤ rP_crit (shock waves)


class MessageLevel(str, Enum):
    """Severity level for validation messages displayed in the UI."""
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"


# ===========================================================================
# CUSTOM EXCEPTIONS
# ===========================================================================

class SizingError(Exception):
    """Base class for all sizing engine errors."""


class HardConstraintViolation(SizingError):
    """Raised when a physical hard constraint is violated (no Cv can be computed)."""
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class ConvergenceError(SizingError):
    """Raised when an iterative solver fails to converge within max_iter."""
    def __init__(self, solver: str, iterations: int) -> None:
        self.solver = solver
        self.iterations = iterations
        super().__init__(
            f"Solver '{solver}' did not converge after {iterations} iterations."
        )


class SteamPropertyError(SizingError):
    """Raised when the IAPWS-IF97 property lookup fails."""


# ===========================================================================
# INPUT MODELS
# ===========================================================================

class FluidProperties(BaseModel):
    """
    Thermodynamic and transport properties of the process fluid.

    Liquid fields (required when FluidPhase = LIQUID):
        Gf   — specific gravity relative to water at 15 °C / 60 °F
        Pv   — vapour pressure at T1 [bar abs | psia]
        Pc   — thermodynamic critical pressure [bar abs | psia]
        mu   — dynamic viscosity [cP]

    Gas fields (required when FluidPhase = GAS):
        M    — molecular weight [kg/kmol | lb/lb-mol]
        gamma— isentropic exponent Cp/Cv [—]
        Z    — compressibility factor at (T1, P1) [—]

    Steam fields (required when FluidPhase = STEAM):
        steam_quality — dryness fraction for wet steam (0 < x_q ≤ 1.0)
                        Leave None for superheated; set 1.0 for saturated dry.
    """
    # Liquid
    Gf:            Optional[float] = Field(None, gt=0.0,  description="Specific gravity [—]")
    Pv:            Optional[float] = Field(None, ge=0.0,  description="Vapour pressure [bar or psia]")
    Pc:            Optional[float] = Field(None, gt=0.0,  description="Critical pressure [bar or psia]")
    mu:            Optional[float] = Field(None, gt=0.0,  description="Dynamic viscosity [cP]")

    # Gas
    M:             Optional[float] = Field(None, gt=0.0,  description="Molecular weight [kg/kmol]")
    gamma:         Optional[float] = Field(None, gt=1.0,  description="Isentropic exponent [—]")
    Z:             float           = Field(1.0,  gt=0.0,  description="Compressibility factor [—]")

    # Steam
    steam_quality: Optional[float] = Field(None, ge=0.0, le=1.0,
                                           description="Steam quality / dryness fraction [—]")


class ValveParameters(BaseModel):
    """
    Valve hydraulic coefficients and physical geometry.

    All coefficients are as-published by the valve manufacturer at 100 % open
    (rated Cv) unless otherwise noted.

    Parameters
    ----------
    FL      : Liquid pressure recovery factor [—]  (IEC 60534-2-1)
    xT      : Pressure differential ratio factor for gas at choked flow [—]
    Fd      : Valve style modifier for noise calculations [—]  (IEC 60534-8-3)
    d       : Valve nominal body size [mm | in]
    D1      : Upstream pipe internal diameter [mm | in]  (=d if no reducer)
    D2      : Downstream pipe internal diameter [mm | in]  (=d if no expander)
    Cv_rated: Rated (manufacturer) Cv at 100 % open.
              Required for sizing-ratio and opening-% calculations.
    char    : Inherent flow characteristic curve.
    R_inherent: Inherent rangeability of the selected valve (default 50:1).
    """
    FL:         float           = Field(..., gt=0.10,  lt=1.00,
                                        description="Liquid pressure recovery factor [—]")
    xT:         float           = Field(..., gt=0.12,  lt=0.80,
                                        description="Pressure differential ratio (gas choked) [—]")
    Fd:         float           = Field(1.0, gt=0.0,   le=1.0,
                                        description="Valve style modifier (noise) [—]")
    d:          float           = Field(..., gt=0.0,
                                        description="Valve body size [mm or in]")
    D1:         Optional[float] = Field(None, gt=0.0,
                                        description="Upstream pipe ID [mm or in] (None = same as d)")
    D2:         Optional[float] = Field(None, gt=0.0,
                                        description="Downstream pipe ID [mm or in] (None = same as d)")
    Cv_rated:   Optional[float] = Field(None, gt=0.0,
                                        description="Manufacturer rated Cv at 100 % open [—]")
    char:       ValveCharacteristic = ValveCharacteristic.EQUAL_PERCENTAGE
    R_inherent: float           = Field(50.0, gt=1.0,
                                        description="Inherent valve rangeability [—]")
    t_wall_mm:  float           = Field(8.18, gt=0.0,
                                        description="Downstream pipe wall thickness [mm]")

    @model_validator(mode="after")
    def _default_pipe_diameters(self) -> "ValveParameters":
        """If D1 or D2 are omitted, default them to valve size d (no reducers)."""
        if self.D1 is None:
            self.D1 = self.d
        if self.D2 is None:
            self.D2 = self.d
        return self


class ProcessConditions(BaseModel):
    """
    Operating process conditions at the valve flanges.

    Pressures and temperatures are stored in the user's chosen unit system.
    The orchestrator converts them to SI (bar abs, K) before computation.

    Parameters
    ----------
    P1          : Upstream absolute pressure [bar abs | psia]
    P2          : Downstream absolute pressure [bar abs | psia]
    T1          : Upstream temperature [°C | °F]  (stored as display value)
    flow_value  : Process flow — units depend on fluid_phase and flow_basis
    flow_basis  : VOLUMETRIC (m³/h or GPM for liquid; Nm³/h or SCFH for gas)
                  or MASS (kg/h or lb/h).
    fluid_phase : Primary phase of process fluid.
    unit_system : SI or US.
    """
    P1:          float      = Field(..., gt=0.0,  description="Inlet pressure [bar abs | psia]")
    P2:          float      = Field(..., gt=0.0,  description="Outlet pressure [bar abs | psia]")
    T1:          float      = Field(...,           description="Inlet temperature [°C | °F]")
    flow_value:  float      = Field(..., gt=0.0,  description="Process flow [m³/h, GPM, Nm³/h, SCFH, kg/h, lb/h]")
    flow_basis:  FlowBasis  = FlowBasis.VOLUMETRIC
    fluid_phase: FluidPhase = FluidPhase.LIQUID
    unit_system: UnitSystem = UnitSystem.SI

    @field_validator("P1", "P2")
    @classmethod
    def _positive_pressure(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Pressures must be strictly positive (absolute).")
        return v


class SizingInputs(BaseModel):
    """
    Composed root input model passed to ``orchestrator.run_sizing()``.

    Parameters
    ----------
    process     : Process-side conditions (P, T, flow, fluid phase).
    fluid       : Fluid thermodynamic and transport properties.
    valve       : Valve coefficients and geometry.
    sizing_margin_pct : Extra Cv margin applied after calculation [%].
    pressure_class    : ASME B16.34 pressure class for P-T rating check.
    noise_limit_dba   : Site-specific A-weighted SPL limit [dBA].
    """
    process:           ProcessConditions
    fluid:             FluidProperties
    valve:             ValveParameters
    sizing_margin_pct: float = Field(20.0, ge=0.0, le=50.0,
                                     description="Sizing margin [%]")
    pressure_class:    str   = Field("Class300",
                                     description="ASME B16.34 pressure class")
    noise_limit_dba:   float = Field(85.0, gt=0.0,
                                     description="Allowable SPL limit [dBA]")


# ===========================================================================
# OUTPUT MODELS
# ===========================================================================

class ValidationMessage(BaseModel):
    """A single validation message (hard error, soft warning, or information)."""
    code:    str          = Field(..., description="Machine-readable error code")
    level:   MessageLevel = Field(..., description="INFO | WARNING | ERROR")
    message: str          = Field(..., description="Human-readable description")


class CavitationResult(BaseModel):
    """
    Complete cavitation / flashing analysis for liquid service.

    All pressure values in bar absolute (SI internal).
    """
    regime:          CavitationRegime
    sigma:           float  = Field(..., description="Cavitation index σ = (P1−Pv)/ΔP [—]")
    P_vc:            float  = Field(..., description="Vena contracta pressure [bar abs]")
    delta_P_incipient: float= Field(..., description="ΔP at cavitation onset [bar]")
    delta_P_max:     float  = Field(..., description="Choked ΔP for liquid [bar]")
    FF:              float  = Field(..., description="Liquid critical pressure ratio factor [—]")
    is_choked:       bool
    is_flashing:     bool


class NoiseResult(BaseModel):
    """
    Noise prediction result (aerodynamic or hydrodynamic).
    Values follow IEC 60534-8-3 / -8-4 chain.
    """
    Lpe_dba:    float  = Field(..., description="External SPL at 1 m [dBA]")
    LWi_db:     float  = Field(..., description="Internal acoustic power level [dB re 1pW]")
    TL_db:      float  = Field(..., description="Pipe wall transmission loss [dB]")
    f_peak_hz:  float  = Field(..., description="Peak noise frequency [Hz]")
    eta:        float  = Field(..., description="Acoustic efficiency factor [—]")
    regime:     str    = Field(..., description="Flow regime used for noise model")
    exceeds_limit: bool


class SizingResult(BaseModel):
    """
    Complete sizing output returned by ``orchestrator.run_sizing()``.

    Fields prefixed with ``_si`` store values in SI units (bar, m³/h, etc.).
    The frontend layer is responsible for converting to the user's display units.
    """
    # ── Status ────────────────────────────────────────────────────────────────
    success:         bool
    messages:        list[ValidationMessage] = Field(default_factory=list)

    # ── Primary Sizing Outputs ────────────────────────────────────────────────
    Cv_required:     Optional[float] = None   # Required Cv (no margin)
    Cv_design:       Optional[float] = None   # Cv_required × (1 + margin)
    Kv_required:     Optional[float] = None   # Kv_required = 0.865 × Cv_required

    # ── Fluid / Flow State ────────────────────────────────────────────────────
    fluid_phase:     Optional[FluidPhase]        = None
    steam_type:      Optional[SteamType]         = None
    is_choked:       bool                        = False
    cavitation:      Optional[CavitationResult]  = None

    # ── Noise ─────────────────────────────────────────────────────────────────
    noise:           Optional[NoiseResult]       = None

    # ── Intermediate Computed Values (for engineering detail display) ─────────
    FF:              Optional[float] = None   # Liquid critical pressure ratio factor
    delta_P_max_bar: Optional[float] = None   # Maximum effective ΔP [bar]
    delta_P_eff_bar: Optional[float] = None   # Effective ΔP used in Cv calc [bar]
    Y:               Optional[float] = None   # Gas expansion factor
    Fp:              Optional[float] = None   # Piping geometry factor
    FLP:             Optional[float] = None   # Combined FL·Fp (liquid with fittings)
    xTP:             Optional[float] = None   # Combined xT with fittings (gas)
    FR:              Optional[float] = None   # Reynolds number factor
    Rev:             Optional[float] = None   # Valve Reynolds number
    Fgamma:          Optional[float] = None   # Specific heat ratio factor
    x:               Optional[float] = None   # Pressure differential ratio (gas)

    # ── Output Metrics ────────────────────────────────────────────────────────
    sizing_ratio:    Optional[float] = None   # Cv_required / Cv_rated
    opening_pct:     Optional[float] = None   # Estimated valve opening [%]
    velocity_ms:     Optional[float] = None   # Downstream pipe velocity [m/s]
    rangeability:    Optional[float] = None   # Q_max / Q_min capability

    # ── Internal: SI values used in computation ───────────────────────────────
    P1_bar:          Optional[float] = None
    P2_bar:          Optional[float] = None
    T1_K:            Optional[float] = None
    W_kgh:           Optional[float] = None   # Mass flow rate used [kg/h]
    Q_m3h:           Optional[float] = None   # Volumetric flow used [m³/h]
    rho1_kgm3:       Optional[float] = None   # Inlet fluid density [kg/m³]