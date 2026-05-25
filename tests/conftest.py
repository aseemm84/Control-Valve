"""
Shared pytest fixtures for the control valve sizing test suite.
================================================================
All fixtures return fully-populated Pydantic models ready to pass
to backend functions or orchestrator.run_sizing().

Hand-calculated reference values are documented inline alongside
each fixture so that expected test outputs can be verified manually.

SI unit convention throughout:
    Pressure      → bar absolute
    Temperature   → °C (stored as display value; orchestrator converts to K)
    Flow (liquid) → m³/h
    Flow (gas)    → kg/h  (mass flow basis; avoids Nm³/h standard-condition ambiguity)
    Dimensions    → mm
"""

from __future__ import annotations

import pytest

from backend.models import (
    FlowBasis, FluidPhase, FluidProperties, MessageLevel,
    ProcessConditions, SizingInputs, UnitSystem, ValveParameters,
)


# ===========================================================================
# LIQUID FIXTURES
# ===========================================================================

@pytest.fixture
def water_si() -> SizingInputs:
    """
    Standard water sizing — SI units, turbulent, non-choked, no cavitation.

    Process
    -------
    P1 = 10 bar abs,  P2 = 8 bar abs,  ΔP = 2 bar
    Q  = 100 m³/h,    Gf = 1.0,        T1 = 20 °C
    Pv = 0.023 bar (water at 20 °C),   Pc = 220.9 bar

    Valve
    -----
    FL = 0.85,  xT = 0.65,  Fd = 1.0,  d = 50 mm,  D1 = D2 = 50 mm

    Hand-calculated reference
    -------------------------
    FF        = 0.96 − 0.28 × √(0.023/220.9)   = 0.9571
    ΔP_max    = 0.85² × (10 − 0.9571×0.023)    = 7.208 bar
    ΔP < ΔP_max → NOT choked
    Cv_req    = (100/0.865) × √(1.0/2.0)        ≈ 81.75
    Rev (est) >> 40,000                          → FR = 1.0
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=10.0, P2=8.0, T1=20.0,
            flow_value=100.0, flow_basis=FlowBasis.VOLUMETRIC,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            Gf=1.0, Pv=0.023, Pc=220.9, mu=1.002,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.65, Fd=1.0,
            d=50.0, D1=50.0, D2=50.0,
            Cv_rated=120.0, t_wall_mm=3.91,
        ),
        sizing_margin_pct=20.0,
    )


@pytest.fixture
def water_us() -> SizingInputs:
    """
    Standard water sizing — US Customary units (equivalent to water_si).

    P1 = 145 psia,  P2 = 116 psia,  ΔP = 29 psi  (≈ 2 bar)
    Q  = 440.3 GPM  (≈ 100 m³/h),   Gf = 1.0,    T1 = 68 °F
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=145.04, P2=116.03, T1=68.0,
            flow_value=440.3, flow_basis=FlowBasis.VOLUMETRIC,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.US,
        ),
        fluid=FluidProperties(
            Gf=1.0, Pv=0.334, Pc=3204.0, mu=1.002,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.65, Fd=1.0,
            d=1.969, D1=1.969, D2=1.969,
            Cv_rated=120.0, t_wall_mm=3.91,
        ),
        sizing_margin_pct=20.0,
    )


@pytest.fixture
def cavitating_water() -> SizingInputs:
    """
    Liquid service with established (constant) cavitation.

    Process
    -------
    Propane at 60 °C:  Pv ≈ 8.5 bar,  Pc = 42.5 bar
    P1 = 15 bar,  P2 = 10 bar,  ΔP = 5 bar
    W  = 10,000 kg/h,  FL = 0.85

    Hand-calculated reference
    -------------------------
    FF     = 0.96 − 0.28×√(8.5/42.5)  = 0.8348
    ΔP_i   = 0.85²×(15−8.5)           = 4.696 bar
    ΔP_max = 0.85²×(15−0.8348×8.5)    = 5.710 bar
    ΔP = 5 > ΔP_i = 4.696 → CONSTANT cavitation
    ΔP = 5 < ΔP_max = 5.710 → NOT fully choked
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=15.0, P2=10.0, T1=60.0,
            flow_value=10_000.0, flow_basis=FlowBasis.MASS,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            Gf=0.50, Pv=8.5, Pc=42.5, mu=0.12,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.65, Fd=1.0,
            d=100.0, D1=100.0, D2=100.0,
            Cv_rated=300.0, t_wall_mm=6.02,
        ),
        sizing_margin_pct=25.0,
    )


@pytest.fixture
def flashing_liquid() -> SizingInputs:
    """
    Liquid service where P2 ≤ Pv → flashing condition.

    Propane: Pv = 8.5 bar at 60 °C; P2 = 8.0 bar < Pv
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=15.0, P2=8.0, T1=60.0,
            flow_value=5_000.0, flow_basis=FlowBasis.MASS,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            Gf=0.50, Pv=8.5, Pc=42.5, mu=0.12,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.65, Fd=1.0,
            d=80.0, D1=80.0, D2=80.0,
            Cv_rated=200.0, t_wall_mm=7.62,
        ),
        sizing_margin_pct=30.0,
    )


@pytest.fixture
def viscous_oil() -> SizingInputs:
    """
    Viscous liquid — heavy fuel oil requiring Reynolds number correction.

    μ = 200 cP (viscous regime; Rev expected < 10,000 → FR < 1.0)
    Gf = 0.92 (heavy fuel oil)
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=8.0, P2=6.0, T1=80.0,
            flow_value=30.0, flow_basis=FlowBasis.VOLUMETRIC,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            Gf=0.92, Pv=0.001, Pc=20.0, mu=200.0,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.65, Fd=1.0,
            d=50.0, D1=50.0, D2=50.0,
            Cv_rated=60.0, t_wall_mm=3.91,
        ),
    )


@pytest.fixture
def water_with_reducers() -> SizingInputs:
    """
    Water with upstream and downstream pipe reducers → Fp < 1.

    Valve d = 50 mm installed in D1 = D2 = 80 mm pipe.
    Fp correction is expected; Cv_required will be higher than no-fittings case.
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=10.0, P2=8.0, T1=20.0,
            flow_value=100.0, flow_basis=FlowBasis.VOLUMETRIC,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            Gf=1.0, Pv=0.023, Pc=220.9, mu=1.002,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.65, Fd=1.0,
            d=50.0, D1=80.0, D2=80.0,
            Cv_rated=150.0, t_wall_mm=5.49,
        ),
    )


# ===========================================================================
# GAS FIXTURES
# ===========================================================================

@pytest.fixture
def air_si() -> SizingInputs:
    """
    Air — subcritical gas sizing, SI units.

    Process
    -------
    P1 = 5 bar,  P2 = 3 bar,  T1 = 27 °C (300 K),  W = 500 kg/h
    M = 28.97,   γ = 1.40,    Z = 1.0

    Hand-calculated reference
    -------------------------
    ρ₁   = (5×10⁵×28.97)/(1.0×8314×300)         = 5.814 kg/m³
    x    = (5−3)/5                               = 0.400
    Fγ   = 1.40/1.40                             = 1.000
    xT   = 0.60  →  Fγ·xT = 0.600
    x < Fγ·xT → NOT choked
    Y    = 1 − 0.400/(3×1.000×0.600)            = 0.778
    Cv   = [500/(27.3×0.778)]×√[1/(0.4×5×5.814)] ≈ 6.90
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=5.0, P2=3.0, T1=27.0,
            flow_value=500.0, flow_basis=FlowBasis.MASS,
            fluid_phase=FluidPhase.GAS, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            M=28.97, gamma=1.40, Z=1.0,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.60, Fd=1.0,
            d=50.0, D1=50.0, D2=50.0,
            Cv_rated=15.0, t_wall_mm=3.91,
        ),
    )


@pytest.fixture
def air_choked() -> SizingInputs:
    """
    Air — choked gas sizing (x >> Fγ·xT).

    P1 = 5 bar,  P2 = 0.5 bar → x = 0.90 >> Fγ·xT = 0.60
    Expected: is_choked = True, Y = 2/3
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=5.0, P2=0.5, T1=27.0,
            flow_value=500.0, flow_basis=FlowBasis.MASS,
            fluid_phase=FluidPhase.GAS, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            M=28.97, gamma=1.40, Z=1.0,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.60, Fd=1.0,
            d=50.0, D1=50.0, D2=50.0,
            Cv_rated=15.0, t_wall_mm=3.91,
        ),
    )


@pytest.fixture
def natural_gas_si() -> SizingInputs:
    """
    Natural gas (methane dominant) — subcritical.

    M = 16.04 (methane),  γ = 1.31,  Z = 0.98
    P1 = 50 bar,  P2 = 30 bar,  T1 = 15 °C,  W = 5000 kg/h
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=50.0, P2=30.0, T1=15.0,
            flow_value=5_000.0, flow_basis=FlowBasis.MASS,
            fluid_phase=FluidPhase.GAS, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            M=16.04, gamma=1.31, Z=0.98,
        ),
        valve=ValveParameters(
            FL=0.85, xT=0.60, Fd=1.0,
            d=100.0, D1=100.0, D2=100.0,
            Cv_rated=50.0, t_wall_mm=6.02,
        ),
    )


# ===========================================================================
# STEAM FIXTURE
# ===========================================================================

@pytest.fixture
def superheated_steam_si() -> SizingInputs:
    """
    Superheated steam — SI units, subcritical.

    P1 = 10 bar,  T1 = 230 °C (superheated; T_sat ≈ 180 °C at 10 bar)
    W  = 2000 kg/h
    v₁ ≈ 0.2608 m³/kg at (10 bar, 230 °C) from IF97
    """
    return SizingInputs(
        process=ProcessConditions(
            P1=10.0, P2=5.0, T1=230.0,
            flow_value=2_000.0, flow_basis=FlowBasis.MASS,
            fluid_phase=FluidPhase.STEAM, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(),   # IF97 provides all steam properties
        valve=ValveParameters(
            FL=0.85, xT=0.65, Fd=1.0,
            d=50.0, D1=50.0, D2=50.0,
            Cv_rated=40.0, t_wall_mm=3.91,
        ),
    )


# ===========================================================================
# INVALID / EDGE CASE INPUTS (for validator tests)
# ===========================================================================

@pytest.fixture
def invalid_pressure_inversion() -> SizingInputs:
    """P2 ≥ P1 — must raise HardConstraintViolation."""
    return SizingInputs(
        process=ProcessConditions(
            P1=5.0, P2=8.0, T1=20.0,
            flow_value=100.0, flow_basis=FlowBasis.VOLUMETRIC,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(Gf=1.0, Pv=0.023, Pc=220.9, mu=1.0),
        valve=ValveParameters(FL=0.85, xT=0.65, Fd=1.0, d=50.0),
    )


@pytest.fixture
def invalid_zero_flow() -> SizingInputs:
    """Flow = 0 — must raise HardConstraintViolation."""
    return SizingInputs(
        process=ProcessConditions(
            P1=10.0, P2=8.0, T1=20.0,
            flow_value=0.001,               # near zero; Pydantic rejects ≤ 0
            flow_basis=FlowBasis.VOLUMETRIC,
            fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(Gf=1.0, Pv=0.023, Pc=220.9, mu=1.0),
        valve=ValveParameters(FL=0.85, xT=0.65, Fd=1.0, d=50.0),
    )