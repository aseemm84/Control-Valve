"""
Control Valve Sizer — Backend Package
======================================
Pure Python math engine implementing:
  - ANSI/ISA-75.01.01-2012  (Flow Equations for Sizing Control Valves)
  - IEC 60534-2-1:2011       (Sizing equations for fluid flow)
  - IEC 60534-8-3:2011       (Aerodynamic noise prediction)
  - IEC 60534-8-4:2015       (Hydrodynamic noise prediction)
  - IAPWS-IF97               (Steam/water thermodynamic properties)

Architecture contract
---------------------
This package contains ZERO Streamlit imports. Every function herein is
callable from a CLI, a pytest runner, or a REST API without any UI present.
All public functions accept and return typed values (Pydantic models or
Python primitives). The single external entry-point is:

    from backend.orchestrator import run_sizing

Internal unit convention
------------------------
ALL math functions operate in SI units:
  Pressure       → bar (absolute)
  Temperature    → K
  Flow (liquid)  → m³ / h
  Flow (gas)     → Nm³ / h  (0 °C, 101.325 kPa reference)
  Mass flow      → kg / h
  Pipe / valve   → mm
  Density        → kg / m³
  Viscosity (dyn)→ cP  (mPa · s)
  Viscosity (kin)→ cSt (mm² / s)

Conversion from US customary inputs is performed once, at the top of
``orchestrator.run_sizing()``, before any sizing function is called.
"""

__version__   = "1.0.0"
__standards__ = [
    "ANSI/ISA-75.01.01-2012",
    "IEC 60534-2-1:2011",
    "IEC 60534-8-3:2011",
    "IEC 60534-8-4:2015",
    "IAPWS-IF97",
    "ASME B16.34-2017",
    "API RP 553",
]