"""
Streamlit input widgets for all process and valve parameters.
==============================================================

All functions render st.* widgets and return raw Python values (dicts,
floats, strings).  No Pydantic models are created here; model construction
happens in build_sizing_inputs() which is called by app.py on Calculate.

Unit convention
---------------
All raw values returned are in the user's chosen unit system (SI or US).
Gauge pressures entered by the user are converted to absolute in
build_sizing_inputs() by adding the atmospheric pressure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from backend.models import (
    FlowBasis,
    FluidPhase,
    FluidProperties,
    ProcessConditions,
    SizingInputs,
    UnitSystem,
    ValveCharacteristic,
    ValveParameters,
)

# ---------------------------------------------------------------------------
# DATA DIRECTORY PATH
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# ROBUST DATA FILE LOADERS WITH HARDCODED FALLBACKS
# ---------------------------------------------------------------------------

@st.cache_data
def _load_valve_presets() -> list[dict]:
    """
    Load valve type presets from data/valve_presets.json.

    If the file is missing, malformed, or inaccessible (e.g. first deploy
    on Streamlit Cloud before the data/ directory is indexed), a hardcoded
    set of representative valve types is returned instead.  This guarantees
    the application never crashes due to a missing data file.
    """
    try:
        with open(_DATA_DIR / "valve_presets.json", encoding="utf-8") as f:
            data = json.load(f)
            presets = data.get("valve_presets", [])
            if presets:
                return presets
            raise ValueError("valve_presets list is empty")
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        # Hardcoded fallback — representative values from IEC 60534-2-3
        return [
            {
                "id": "globe_single_port",
                "name": "Globe Valve — Single-Port",
                "FL": 0.90, "xT": 0.72, "Fd": 1.00,
                "characteristic": "equal_percentage",
            },
            {
                "id": "globe_cage_balanced",
                "name": "Globe Valve — Cage-Guided, Balanced",
                "FL": 0.85, "xT": 0.68, "Fd": 0.42,
                "characteristic": "equal_percentage",
            },
            {
                "id": "globe_double_port",
                "name": "Globe Valve — Double-Port",
                "FL": 0.80, "xT": 0.65, "Fd": 0.70,
                "characteristic": "linear",
            },
            {
                "id": "ball_full_bore",
                "name": "Ball Valve — Full-Bore (Rotary)",
                "FL": 0.55, "xT": 0.20, "Fd": 0.98,
                "characteristic": "quick_opening",
            },
            {
                "id": "ball_v_port",
                "name": "Ball Valve — V-Port (Rotary)",
                "FL": 0.60, "xT": 0.35, "Fd": 0.70,
                "characteristic": "equal_percentage",
            },
            {
                "id": "butterfly_conventional",
                "name": "Butterfly Valve — Conventional",
                "FL": 0.55, "xT": 0.35, "Fd": 0.57,
                "characteristic": "equal_percentage",
            },
            {
                "id": "butterfly_high_perf",
                "name": "Butterfly Valve — High Performance",
                "FL": 0.68, "xT": 0.50, "Fd": 0.42,
                "characteristic": "equal_percentage",
            },
            {
                "id": "eccentric_rotary_plug",
                "name": "Rotary Valve — Eccentric Plug",
                "FL": 0.77, "xT": 0.54, "Fd": 0.44,
                "characteristic": "equal_percentage",
            },
            {
                "id": "needle_valve",
                "name": "Needle Valve — Low-Flow Precision",
                "FL": 0.95, "xT": 0.78, "Fd": 1.00,
                "characteristic": "linear",
            },
            {
                "id": "anti_cavitation",
                "name": "Globe Valve — Anti-Cavitation Multi-Stage",
                "FL": 0.85, "xT": 0.65, "Fd": 0.10,
                "characteristic": "equal_percentage",
            },
        ]


@st.cache_data
def _load_fluid_presets() -> dict[str, list[dict]]:
    """
    Load fluid property presets from data/fluid_presets.json.

    If the file is missing or malformed, a hardcoded set of the most
    common process fluids is returned.  This guarantees the application
    never crashes due to a missing data file.
    """
    try:
        with open(_DATA_DIR / "fluid_presets.json", encoding="utf-8") as f:
            data = json.load(f)
            result = {
                "liquid": data.get("liquid_presets", []),
                "gas":    data.get("gas_presets", []),
                "steam":  data.get("steam_presets", []),
            }
            # Only trust the file if it has at least some entries
            if any(result.values()):
                return result
            raise ValueError("All fluid preset lists are empty")
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        # Hardcoded fallback — most common process fluids
        return {
            "liquid": [
                {
                    "id": "water",
                    "name": "Water",
                    "Gf": 1.000,
                    "Pc_bar": 220.9,
                    "mu_cP_at_20C": 1.002,
                    "Pv_data": [
                        {"T_C": 0,   "Pv_bar": 0.006},
                        {"T_C": 20,  "Pv_bar": 0.023},
                        {"T_C": 40,  "Pv_bar": 0.074},
                        {"T_C": 60,  "Pv_bar": 0.199},
                        {"T_C": 80,  "Pv_bar": 0.474},
                        {"T_C": 100, "Pv_bar": 1.013},
                    ],
                },
                {
                    "id": "propane",
                    "name": "Propane (C3H8)",
                    "Gf": 0.507,
                    "Pc_bar": 42.48,
                    "mu_cP_at_20C": 0.110,
                    "Pv_data": [
                        {"T_C": -20, "Pv_bar": 2.44},
                        {"T_C": 0,   "Pv_bar": 4.74},
                        {"T_C": 20,  "Pv_bar": 8.35},
                        {"T_C": 40,  "Pv_bar": 13.69},
                        {"T_C": 60,  "Pv_bar": 21.20},
                    ],
                },
                {
                    "id": "ammonia",
                    "name": "Ammonia (NH3)",
                    "Gf": 0.682,
                    "Pc_bar": 113.5,
                    "mu_cP_at_20C": 0.141,
                    "Pv_data": [
                        {"T_C": -20, "Pv_bar": 2.34},
                        {"T_C": 0,   "Pv_bar": 4.30},
                        {"T_C": 20,  "Pv_bar": 8.57},
                        {"T_C": 40,  "Pv_bar": 15.54},
                    ],
                },
                {
                    "id": "hfo",
                    "name": "Heavy Fuel Oil (HFO)",
                    "Gf": 0.970,
                    "Pc_bar": 20.0,
                    "mu_cP_at_20C": 800.0,
                    "Pv_data": [{"T_C": 80, "Pv_bar": 0.002}],
                },
                {
                    "id": "light_crude",
                    "name": "Light Crude Oil",
                    "Gf": 0.855,
                    "Pc_bar": 25.0,
                    "mu_cP_at_20C": 5.0,
                    "Pv_data": [{"T_C": 20, "Pv_bar": 0.15}],
                },
                {
                    "id": "glycol_50",
                    "name": "50 % Ethylene Glycol / Water",
                    "Gf": 1.070,
                    "Pc_bar": 100.0,
                    "mu_cP_at_20C": 5.5,
                    "Pv_data": [{"T_C": 20, "Pv_bar": 0.015}],
                },
            ],
            "gas": [
                {"id": "air",     "name": "Air (dry)",              "M": 28.967, "gamma": 1.400},
                {"id": "nitrogen","name": "Nitrogen (N2)",           "M": 28.014, "gamma": 1.400},
                {"id": "methane", "name": "Natural Gas (~97% CH4)",  "M": 16.54,  "gamma": 1.310},
                {"id": "methane_pure", "name": "Methane (CH4) Pure","M": 16.043, "gamma": 1.306},
                {"id": "hydrogen","name": "Hydrogen (H2)",           "M": 2.016,  "gamma": 1.407},
                {"id": "co2",     "name": "Carbon Dioxide (CO2)",    "M": 44.010, "gamma": 1.289},
                {"id": "oxygen",  "name": "Oxygen (O2)",             "M": 31.999, "gamma": 1.395},
                {"id": "propane_gas","name": "Propane Vapour (C3H8)","M": 44.096, "gamma": 1.130},
            ],
            "steam": [
                {"id": "steam_sat_low",   "name": "Saturated Steam — Low P (2–5 bar)"},
                {"id": "steam_sat_med",   "name": "Saturated Steam — Medium P (5–20 bar)"},
                {"id": "steam_super_med", "name": "Superheated Steam — Medium P (10–40 bar)"},
                {"id": "steam_super_hi",  "name": "Superheated Steam — High P (40–100 bar)"},
            ],
        }


# ---------------------------------------------------------------------------
# UNIT LABEL MAPS
# ---------------------------------------------------------------------------

def _labels(us: str) -> dict[str, str]:
    """Return the correct unit label strings for the active unit system."""
    if us == "SI":
        return {
            "p_gauge":  "bar g",
            "p_abs":    "bar a",
            "t":        "°C",
            "q_liq":    "m³/h",
            "q_gas":    "Nm³/h",
            "w":        "kg/h",
            "d":        "mm",
            "density":  "kg/m³",
            "visc":     "cP",
            "p_crit":   "bar a",
            "p_vap":    "bar a",
        }
    return {
        "p_gauge":  "psig",
        "p_abs":    "psia",
        "t":        "°F",
        "q_liq":    "US GPM",
        "q_gas":    "SCFH",
        "w":        "lb/h",
        "d":        "inches",
        "density":  "lb/ft³",
        "visc":     "cP",
        "p_crit":   "psia",
        "p_vap":    "psia",
    }


def _atm(us: str) -> float:
    """Atmospheric pressure in the user's pressure unit."""
    return 1.01325 if us == "SI" else 14.696


# ---------------------------------------------------------------------------
# SIDEBAR GLOBAL SETTINGS
# ---------------------------------------------------------------------------

def render_sidebar_globals() -> dict[str, Any]:
    """
    Render global settings in the Streamlit sidebar.

    Returns
    -------
    dict with keys: unit_system, fluid_phase, pressure_class,
                    noise_limit_dba, sizing_margin_pct, calculate_clicked
    """
    st.sidebar.markdown("### ⚙ Global Settings")

    unit_system = st.sidebar.radio(
        "Unit System",
        options=["SI", "US"],
        horizontal=True,
        help="SI: bar, m³/h, mm, °C  |  US: psi, GPM, inches, °F",
    )

    fluid_phase = st.sidebar.selectbox(
        "Fluid Phase",
        options=["Liquid", "Gas", "Steam"],
        help="Select the primary state of the process fluid at the valve inlet.",
    )

    st.sidebar.markdown("### 🏭 Valve Specification")

    pressure_class = st.sidebar.selectbox(
        "ASME Pressure Class",
        options=[
            "Class150", "Class300", "Class600",
            "Class900", "Class1500", "Class2500",
        ],
        index=1,
        help="Used for ASME B16.34 P-T rating check.",
    )

    st.sidebar.markdown("### 🎛 Sizing Options")

    sizing_margin_pct = st.sidebar.slider(
        "Sizing Margin",
        min_value=5,
        max_value=40,
        value=20,
        step=5,
        format="%d %%",
        help=(
            "Additional Cv margin applied to required Cv before valve selection. "
            "API RP 553 recommends 20 % (liquid/gas) or 25 % (steam)."
        ),
    )

    noise_limit_dba = st.sidebar.number_input(
        "Noise Limit",
        min_value=60.0,
        max_value=120.0,
        value=85.0,
        step=1.0,
        format="%.0f",
        help="Site regulatory A-weighted SPL limit at 1 m from pipe [dBA].",
    )

    st.sidebar.divider()

    calculate_clicked = st.sidebar.button(
        "🔬  CALCULATE",
        type="primary",
        use_container_width=True,
    )

    st.sidebar.divider()
    st.sidebar.caption(
        "📐 **Standards:** IEC 60534-2-1:2011 · ISA-75.01.01 · "
        "IEC 60534-8-3/8-4 · IAPWS-IF97 · ASME B16.34"
    )

    return {
        "unit_system":       unit_system,
        "fluid_phase":       fluid_phase,
        "pressure_class":    pressure_class,
        "sizing_margin_pct": float(sizing_margin_pct),
        "noise_limit_dba":   noise_limit_dba,
        "calculate_clicked": calculate_clicked,
    }


# ---------------------------------------------------------------------------
# PROCESS CONDITIONS
# ---------------------------------------------------------------------------

def render_process_conditions(unit_system: str, fluid_phase: str) -> dict[str, Any]:
    """
    Render process condition input widgets.

    Returns
    -------
    dict with keys: P1_gauge, P2_gauge, T1, flow_value, flow_basis
    """
    from frontend.ui_styles import section_header_html

    ul = _labels(unit_system)
    st.markdown(section_header_html("Process Conditions"), unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        default_P1 = 10.0 if unit_system == "SI" else 145.0
        P1_gauge   = st.number_input(
            f"Upstream Pressure ({ul['p_gauge']})",
            min_value=0.0,
            value=default_P1,
            step=0.5,
            format="%.3f",
            help="Inlet pressure at valve flange — enter as gauge pressure.",
        )

    with col2:
        default_P2 = 8.0 if unit_system == "SI" else 116.0
        P2_gauge   = st.number_input(
            f"Downstream Pressure ({ul['p_gauge']})",
            min_value=0.0,
            value=default_P2,
            step=0.5,
            format="%.3f",
            help="Outlet pressure at valve flange — enter as gauge pressure.",
        )

    delta_P_display = P1_gauge - P2_gauge
    dp_unit = ul["p_gauge"]
    if delta_P_display < 0:
        st.error(
            f"⚠ P2 > P1 by {abs(delta_P_display):.3f} {dp_unit}. "
            "Check pressure inputs."
        )
    else:
        st.caption(f"ΔP = **{delta_P_display:.3f} {dp_unit}**")

    with col1:
        default_T1 = 20.0 if unit_system == "SI" else 68.0
        T1 = st.number_input(
            f"Inlet Temperature ({ul['t']})",
            value=default_T1,
            step=5.0,
            format="%.1f",
            help="Process fluid temperature at valve inlet.",
        )

    with col2:
        flow_basis_choice = st.radio(
            "Flow Basis",
            options=["Volumetric", "Mass"],
            horizontal=True,
            help=(
                "Volumetric: m³/h or GPM (liquid), Nm³/h or SCFH (gas).  "
                "Mass: kg/h or lb/h."
            ),
        )

    flow_basis = (
        FlowBasis.VOLUMETRIC
        if flow_basis_choice == "Volumetric"
        else FlowBasis.MASS
    )

    # Determine flow unit and default based on phase + basis
    if flow_basis == FlowBasis.VOLUMETRIC:
        if fluid_phase == "Liquid":
            flow_unit    = ul["q_liq"]
            flow_default = 100.0 if unit_system == "SI" else 440.0
        elif fluid_phase == "Gas":
            flow_unit    = ul["q_gas"]
            flow_default = 1_000.0 if unit_system == "SI" else 35_300.0
        else:
            # Steam — force to mass flow
            flow_unit    = ul["w"]
            flow_default = 2_000.0 if unit_system == "SI" else 4_409.0
            flow_basis   = FlowBasis.MASS
    else:
        flow_unit    = ul["w"]
        flow_default = 100.0 if unit_system == "SI" else 220.0

    flow_value = st.number_input(
        f"Flow Rate ({flow_unit})",
        min_value=0.001,
        value=flow_default,
        step=10.0,
        format="%.2f",
        help="Process flow at normal / design conditions.",
    )

    return {
        "P1_gauge":   P1_gauge,
        "P2_gauge":   P2_gauge,
        "T1":         T1,
        "flow_value": flow_value,
        "flow_basis": flow_basis,
    }


# ---------------------------------------------------------------------------
# FLUID PROPERTIES
# ---------------------------------------------------------------------------

def render_fluid_properties(unit_system: str, fluid_phase: str) -> dict[str, Any]:
    """
    Render fluid property input widgets (phase-specific).

    Returns
    -------
    dict with all fluid property values (None for irrelevant fields).
    """
    from frontend.ui_styles import section_header_html

    st.markdown(section_header_html("Fluid Properties"), unsafe_allow_html=True)

    ul      = _labels(unit_system)
    presets = _load_fluid_presets()
    props: dict[str, Any] = {
        "Gf": None, "Pv": None, "Pc": None, "mu": None,
        "M": None, "gamma": None, "Z": 1.0, "steam_quality": None,
    }

    # ── Fluid Quick-Select ─────────────────────────────────────────────────────
    phase_key    = fluid_phase.lower()
    preset_list  = presets.get(phase_key, [])
    preset_names = ["— manual entry —"] + [p["name"] for p in preset_list]

    sel_preset = st.selectbox(
        "Quick-Select Fluid",
        options=preset_names,
        help=(
            "Pre-fills common fluid properties. "
            "Always verify against actual process data."
        ),
    )

    selected_fluid = None
    if sel_preset != "— manual entry —":
        selected_fluid = next(
            (p for p in preset_list if p["name"] == sel_preset), None
        )

    # ── LIQUID ────────────────────────────────────────────────────────────────
    if fluid_phase == "Liquid":
        col1, col2 = st.columns(2)

        with col1:
            default_Gf = (
                1.000 if selected_fluid is None
                else float(selected_fluid.get("Gf", 1.0))
            )
            Gf = st.number_input(
                "Specific Gravity Gf [—]",
                min_value=0.01,
                max_value=3.0,
                value=default_Gf,
                step=0.01,
                format="%.4f",
                help="Density relative to water at 15 °C / 60 °F.",
            )
            props["Gf"] = Gf

            mu = st.number_input(
                "Dynamic Viscosity μ [cP]",
                min_value=0.001,
                value=1.002,
                step=0.1,
                format="%.3f",
                help="Dynamic viscosity at inlet temperature.",
            )
            props["mu"] = mu

        with col2:
            # Default Pv from preset (first entry) or fallback
            if selected_fluid and "Pv_data" in selected_fluid:
                pv_entries  = selected_fluid["Pv_data"]
                default_Pv  = float(pv_entries[0]["Pv_bar"]) if pv_entries else 0.023
                if unit_system == "US":
                    default_Pv *= 14.504
            else:
                default_Pv = 0.023 if unit_system == "SI" else 0.334

            Pv = st.number_input(
                f"Vapour Pressure Pv ({ul['p_vap']})",
                min_value=0.0,
                value=default_Pv,
                step=0.01,
                format="%.4f",
                help=(
                    "Absolute vapour pressure at T1.  "
                    "Required for cavitation / flashing analysis."
                ),
            )
            props["Pv"] = Pv

            default_Pc = (
                220.9 if unit_system == "SI" else 3_204.0
            )
            if selected_fluid:
                pc_raw     = float(selected_fluid.get("Pc_bar", 220.9))
                default_Pc = pc_raw if unit_system == "SI" else pc_raw * 14.504

            Pc = st.number_input(
                f"Critical Pressure Pc ({ul['p_crit']})",
                min_value=1.0,
                value=default_Pc,
                step=1.0,
                format="%.2f",
                help="Thermodynamic critical pressure.  Used in FF = 0.96 − 0.28√(Pv/Pc).",
            )
            props["Pc"] = Pc

    # ── GAS ──────────────────────────────────────────────────────────────────
    elif fluid_phase == "Gas":
        col1, col2, col3 = st.columns(3)

        with col1:
            default_M = (
                28.967 if selected_fluid is None
                else float(selected_fluid.get("M", 28.967))
            )
            M = st.number_input(
                "Molecular Weight M [kg/kmol]",
                min_value=1.0,
                max_value=500.0,
                value=default_M,
                step=0.1,
                format="%.3f",
                help="Molecular weight of the gas mixture.",
            )
            props["M"] = M

        with col2:
            default_gamma = (
                1.40 if selected_fluid is None
                else float(selected_fluid.get("gamma", 1.40))
            )
            gamma = st.number_input(
                "Isentropic Exponent γ [—]",
                min_value=1.01,
                max_value=2.0,
                value=default_gamma,
                step=0.01,
                format="%.3f",
                help=(
                    "Cp/Cv ratio.  "
                    "Air = 1.40 · Methane ≈ 1.31 · Steam ≈ 1.13–1.30"
                ),
            )
            props["gamma"] = gamma

        with col3:
            Z = st.number_input(
                "Compressibility Z [—]",
                min_value=0.1,
                max_value=2.0,
                value=1.0,
                step=0.01,
                format="%.4f",
                help="Real gas compressibility factor at (T1, P1).  Z = 1.0 for ideal gas.",
            )
            props["Z"] = Z

    # ── STEAM ────────────────────────────────────────────────────────────────
    else:
        st.info(
            "ℹ Steam properties (specific volume, γ) are retrieved automatically "
            "from **IAPWS-IF97** using the inlet T and P.  "
            "Only specify quality for **wet steam** service."
        )
        use_wet = st.checkbox(
            "Wet Steam (quality < 1.0)",
            help="Enable to specify the steam quality x_q for two-phase inlet conditions.",
        )
        if use_wet:
            quality = st.slider(
                "Steam Quality x_q [—]",
                min_value=0.70,
                max_value=0.99,
                value=0.95,
                step=0.01,
                format="%.2f",
                help=(
                    "Dryness fraction: 1.0 = dry saturated, < 1.0 = wet/two-phase. "
                    "x_q < 0.90 carries significant erosion risk."
                ),
            )
            props["steam_quality"] = quality
            st.warning(
                "⚠ Wet steam service (x_q < 0.90) carries significant erosion risk.  "
                "Use hardened trim materials (Stellite, ceramic)."
            )

    return props


# ---------------------------------------------------------------------------
# VALVE PARAMETERS
# ---------------------------------------------------------------------------

def render_valve_parameters(unit_system: str) -> dict[str, Any]:
    """
    Render valve coefficient and geometry input widgets.

    Returns
    -------
    dict with keys: FL, xT, Fd, d, D1, D2, t_wall_mm, Cv_rated,
                    char, R_inherent
    """
    from frontend.ui_styles import section_header_html

    st.markdown(section_header_html("Valve Parameters"), unsafe_allow_html=True)

    valve_presets  = _load_valve_presets()
    preset_options = ["— manual entry —"] + [v["name"] for v in valve_presets]

    sel_preset = st.selectbox(
        "Quick-Select Valve Type",
        options=preset_options,
        help=(
            "Pre-fills typical FL, xT, Fd from IEC 60534-2-3 representative data.  "
            "Always use manufacturer datasheet values for final design."
        ),
    )

    selected_valve = None
    if sel_preset != "— manual entry —":
        selected_valve = next(
            (v for v in valve_presets if v["name"] == sel_preset), None
        )

    # ── Hydraulic coefficients ────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        default_FL = (
            0.85 if selected_valve is None
            else float(selected_valve.get("FL", 0.85))
        )
        FL = st.number_input(
            "FL [—]",
            min_value=0.10,
            max_value=0.99,
            value=default_FL,
            step=0.01,
            format="%.3f",
            help="Liquid pressure recovery factor.  Higher FL = lower cavitation risk.",
        )

    with col2:
        default_xT = (
            0.65 if selected_valve is None
            else float(selected_valve.get("xT", 0.65))
        )
        xT = st.number_input(
            "xT [—]",
            min_value=0.12,
            max_value=0.79,
            value=default_xT,
            step=0.01,
            format="%.3f",
            help="Pressure differential ratio factor for gas at choked flow.",
        )

    with col3:
        default_Fd = (
            1.00 if selected_valve is None
            else float(selected_valve.get("Fd", 1.00))
        )
        Fd = st.number_input(
            "Fd [—]",
            min_value=0.01,
            max_value=1.00,
            value=default_Fd,
            step=0.01,
            format="%.3f",
            help=(
                "Valve style modifier for aerodynamic noise (IEC 60534-8-3).  "
                "Globe = 1.0 · Multi-port cage ≈ 0.1–0.3"
            ),
        )

    # ── Physical dimensions ───────────────────────────────────────────────────
    ul = _labels(unit_system)
    st.caption(f"All dimensions in **{ul['d']}**")
    col1, col2, col3 = st.columns(3)

    d_default  = 50.0 if unit_system == "SI" else 2.0
    D1_default = 50.0 if unit_system == "SI" else 2.0
    D2_default = 50.0 if unit_system == "SI" else 2.0
    step_dim   = 5.0  if unit_system == "SI" else 0.5
    min_dim    = 6.0  if unit_system == "SI" else 0.25
    max_dim    = 1_200.0 if unit_system == "SI" else 48.0

    with col1:
        d = st.number_input(
            f"Valve Size d ({ul['d']})",
            min_value=min_dim,
            max_value=max_dim,
            value=d_default,
            step=step_dim,
            format="%.1f",
            help="Nominal valve body size (not pipe NPS).",
        )

    with col2:
        D1 = st.number_input(
            f"Upstream Pipe ID D1 ({ul['d']})",
            min_value=min_dim,
            value=D1_default,
            step=step_dim,
            format="%.1f",
            help="Upstream pipe internal diameter.  Set equal to d if no reducer.",
        )

    with col3:
        D2 = st.number_input(
            f"Downstream Pipe ID D2 ({ul['d']})",
            min_value=min_dim,
            value=D2_default,
            step=step_dim,
            format="%.1f",
            help="Downstream pipe internal diameter.  Set equal to d if no expander.",
        )

    t_wall_mm = st.number_input(
        "Downstream Pipe Wall Thickness [mm]",
        min_value=1.0,
        max_value=80.0,
        value=8.18,
        step=0.5,
        format="%.2f",
        help=(
            "Used for pipe wall transmission loss in IEC 60534-8-3/8-4 noise calculations.  "
            "Typical SCH40 values: 2\" = 3.91 mm · 4\" = 6.02 mm · 8\" = 8.18 mm"
        ),
    )

    # ── Optional: rated Cv ────────────────────────────────────────────────────
    with st.expander(
        "📊 Selected Valve — optional (enables sizing ratio & opening %)",
        expanded=False,
    ):
        use_rated = st.checkbox("I have selected a specific valve", value=False)
        Cv_rated   = None
        R_inherent = 50.0
        char_name  = "Equal Percentage"

        if use_rated:
            col1, col2, col3 = st.columns(3)
            with col1:
                Cv_rated = st.number_input(
                    "Rated Cv",
                    min_value=0.01,
                    value=100.0,
                    step=1.0,
                    format="%.2f",
                    help="Manufacturer rated Cv at 100 % open.",
                )
            with col2:
                char_name = st.selectbox(
                    "Flow Characteristic",
                    options=["Equal Percentage", "Linear", "Quick Opening"],
                )
            with col3:
                R_inherent = st.number_input(
                    "Rangeability",
                    min_value=5.0,
                    max_value=500.0,
                    value=50.0,
                    step=5.0,
                    format="%.0f",
                    help="Inherent valve rangeability Cv_max / Cv_min (typically 50:1).",
                )

    char_map = {
        "Equal Percentage": ValveCharacteristic.EQUAL_PERCENTAGE,
        "Linear":           ValveCharacteristic.LINEAR,
        "Quick Opening":    ValveCharacteristic.QUICK_OPENING,
    }

    return {
        "FL":         FL,
        "xT":         xT,
        "Fd":         Fd,
        "d":          d,
        "D1":         D1,
        "D2":         D2,
        "t_wall_mm":  t_wall_mm,
        "Cv_rated":   Cv_rated,
        "char":       char_map.get(char_name, ValveCharacteristic.EQUAL_PERCENTAGE),
        "R_inherent": R_inherent,
    }


# ---------------------------------------------------------------------------
# MODEL BUILDER
# ---------------------------------------------------------------------------

def build_sizing_inputs(
    sidebar: dict[str, Any],
    process: dict[str, Any],
    fluid:   dict[str, Any],
    valve:   dict[str, Any],
) -> SizingInputs:
    """
    Assemble a validated SizingInputs Pydantic model from raw widget values.

    Converts gauge pressures to absolute by adding atmospheric pressure.
    All other unit conversions are handled by the backend orchestrator.

    Parameters
    ----------
    sidebar : dict   Output of render_sidebar_globals().
    process : dict   Output of render_process_conditions().
    fluid   : dict   Output of render_fluid_properties().
    valve   : dict   Output of render_valve_parameters().

    Returns
    -------
    SizingInputs

    Raises
    ------
    ValueError / pydantic.ValidationError on invalid inputs.
    """
    us  = sidebar["unit_system"]
    atm = _atm(us)

    P1_abs = process["P1_gauge"] + atm
    P2_abs = process["P2_gauge"] + atm

    phase_map = {
        "Liquid": FluidPhase.LIQUID,
        "Gas":    FluidPhase.GAS,
        "Steam":  FluidPhase.STEAM,
    }

    proc = ProcessConditions(
        P1=P1_abs,
        P2=P2_abs,
        T1=process["T1"],
        flow_value=process["flow_value"],
        flow_basis=process["flow_basis"],
        fluid_phase=phase_map[sidebar["fluid_phase"]],
        unit_system=UnitSystem.SI if us == "SI" else UnitSystem.US,
    )

    fld = FluidProperties(
        Gf=fluid.get("Gf"),
        Pv=fluid.get("Pv"),
        Pc=fluid.get("Pc"),
        mu=fluid.get("mu"),
        M=fluid.get("M"),
        gamma=fluid.get("gamma"),
        Z=fluid.get("Z", 1.0),
        steam_quality=fluid.get("steam_quality"),
    )

    vp = ValveParameters(
        FL=valve["FL"],
        xT=valve["xT"],
        Fd=valve["Fd"],
        d=valve["d"],
        D1=valve["D1"],
        D2=valve["D2"],
        t_wall_mm=valve["t_wall_mm"],
        Cv_rated=valve.get("Cv_rated"),
        char=valve["char"],
        R_inherent=valve["R_inherent"],
    )

    return SizingInputs(
        process=proc,
        fluid=fld,
        valve=vp,
        sizing_margin_pct=sidebar["sizing_margin_pct"],
        pressure_class=sidebar["pressure_class"],
        noise_limit_dba=sidebar["noise_limit_dba"],
    )