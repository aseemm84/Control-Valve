"""
Control Valve Sizer — Main Streamlit Application
=================================================
Entry point for the Streamlit web application.

Architecture
------------
This file is intentionally thin.  All rendering logic is in frontend/;
all math is in backend/orchestrator.py.  This file's sole responsibilities:
  1. Page configuration and CSS injection.
  2. Dependency checking at session start.
  3. Sidebar global settings.
  4. Tab layout and navigation.
  5. Triggering orchestrator.run_sizing() on button click.
  6. Storing and retrieving results in st.session_state.

Run
---
    streamlit run app.py
"""

from __future__ import annotations

import traceback
from typing import Any, Callable

import streamlit as st

# ── Backend (only orchestrator and models) ────────────────────────────────────
from backend.models import FluidPhase, SizingResult
from backend.orchestrator import run_sizing

# ── Frontend modules ──────────────────────────────────────────────────────────
from frontend.ui_inputs import (
    build_sizing_inputs,
    render_fluid_properties,
    render_process_conditions,
    render_sidebar_globals,
    render_valve_parameters,
)
from frontend.ui_noise import render_noise
from frontend.ui_report import render_report_panel
from frontend.ui_results import render_results
from frontend.ui_styles import app_header_html, inject_custom_css, section_header_html
from frontend.ui_warnings import render_warning_panel

# ── Plotly charts ─────────────────────────────────────────────────────────────
from frontend.ui_charts import (
    plot_cavitation_map,
    plot_cv_characteristic,
    plot_noise_gauge,
    plot_pressure_profile,
    plot_sizing_gauge,
)


# =============================================================================
# PAGE CONFIGURATION  (must be the very first Streamlit call)
# =============================================================================

st.set_page_config(
    page_title="Control Valve Sizer",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://github.com/your-org/control-valve-sizer",
        "Report a bug": "https://github.com/your-org/control-valve-sizer/issues",
        "About": (
            "### Control Valve Sizer\n"
            "Professional sizing per **IEC 60534-2-1:2011** and **ISA-75.01.01-2012**.\n\n"
            "Noise prediction per **IEC 60534-8-3:2011** and **IEC 60534-8-4:2015**.\n\n"
            "Steam properties via **IAPWS-IF97**."
        ),
    },
)


# =============================================================================
#  DEPENDENCY GUARD
# =============================================================================

def _check_dependencies() -> dict[str, bool]:
    """
    Check optional heavy dependencies once per browser session.

    Results are stored in st.session_state so the import attempt only
    runs on the first interaction — not on every widget callback.

    Returns
    -------
    dict[str, bool]
        Keys: 'iapws', 'fpdf2', 'openpyxl'
        Values: True if importable, False if missing.
    """
    if "dep_check_done" not in st.session_state:
        deps: dict[str, bool] = {}

        try:
            import iapws          # noqa: F401
            deps["iapws"] = True
        except ImportError:
            deps["iapws"] = False

        try:
            from fpdf import FPDF  # noqa: F401
            deps["fpdf2"] = True
        except ImportError:
            deps["fpdf2"] = False

        try:
            import openpyxl        # noqa: F401
            deps["openpyxl"] = True
        except ImportError:
            deps["openpyxl"] = False

        st.session_state["dep_check_done"] = True
        st.session_state["deps"] = deps

    return st.session_state.get("deps", {"iapws": True, "fpdf2": True, "openpyxl": True})


# =============================================================================
#  SAFE CHART RENDERER
# =============================================================================

def _safe_chart(
    fig_func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Call fig_func(*args, **kwargs) and render the returned Plotly figure.

    If the figure function raises any exception (e.g. bad data, missing
    Plotly version feature), the error is caught silently and a short
    informational caption is shown instead of crashing the whole tab.

    Parameters
    ----------
    fig_func : Callable
        A function from frontend.ui_charts that returns a go.Figure.
    *args, **kwargs
        Forwarded to fig_func.
    """
    try:
        fig = fig_func(*args, **kwargs)
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False},
        )
    except Exception as exc:
        st.caption(f"ℹ Chart unavailable: {exc}")


# =============================================================================
# SESSION STATE INITIALISATION
# =============================================================================

def _init_session_state() -> None:
    """Initialise all session-state keys with safe defaults."""
    defaults: dict[str, Any] = {
        "result":          None,   # SizingResult | None
        "calc_error":      None,   # str | None
        "calc_attempted":  False,  # bool — True after first Calculate click
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main() -> None:
    """
    Top-level application function.

    Called on every Streamlit script re-run (widget interaction, page load,
    tab switch).  Session state ensures results persist across re-runs.
    """
    _init_session_state()
    inject_custom_css()

    # ── FIX 1: Dependency check (once per session) ────────────────────────────
    deps = _check_dependencies()
    if not deps.get("iapws", True):
        st.warning(
            "⚠ **Steam sizing unavailable:** The `iapws` library could not be "
            "imported.  All liquid and gas calculations are unaffected.  "
            "To enable steam service, run:  `pip install iapws==1.5.2`",
            icon="♨️",
        )

    # ── App Header ────────────────────────────────────────────────────────────
    st.markdown(app_header_html(), unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    sidebar_vals = render_sidebar_globals()
    unit_system  = sidebar_vals["unit_system"]
    fluid_phase  = sidebar_vals["fluid_phase"]

    # Block Steam if iapws unavailable
    if fluid_phase == "Steam" and not deps.get("iapws", True):
        st.sidebar.error(
            "Steam requires iapws.  "
            "Select Liquid or Gas, or install iapws."
        )

    # ── Main Tabs ─────────────────────────────────────────────────────────────
    tab_inputs, tab_results, tab_noise, tab_warnings, tab_report = st.tabs([
        "📋 Process Inputs",
        "📊 Sizing Results",
        "🔊 Noise Analysis",
        "⚠ Warnings",
        "📄 Report",
    ])

    # =========================================================================
    # TAB 1 — INPUTS
    # =========================================================================
    with tab_inputs:
        col_left, col_right = st.columns([1, 1], gap="large")

        with col_left:
            process_vals = render_process_conditions(unit_system, fluid_phase)
            fluid_vals   = render_fluid_properties(unit_system, fluid_phase)

        with col_right:
            valve_vals = render_valve_parameters(unit_system)

        # Quick summary expander
        st.divider()
        with st.expander(
            "🔍 Input Summary — what will be sent to the sizing engine",
            expanded=False,
        ):
            delta_P = process_vals["P1_gauge"] - process_vals["P2_gauge"]
            atm     = 1.01325 if unit_system == "SI" else 14.696
            p_unit  = "bar" if unit_system == "SI" else "psi"
            st.markdown(
                f"""
| Parameter | Value | Unit |
|---|---|---|
| Fluid Phase | **{fluid_phase}** | |
| Unit System | **{unit_system}** | |
| P1 (gauge) | **{process_vals['P1_gauge']:.3f}** | {p_unit}g |
| P2 (gauge) | **{process_vals['P2_gauge']:.3f}** | {p_unit}g |
| ΔP | **{delta_P:.3f}** | {p_unit} |
| P1 (absolute) | **{process_vals['P1_gauge'] + atm:.4f}** | {p_unit}a |
| Flow | **{process_vals['flow_value']:.2f}** | basis: {process_vals['flow_basis'].value} |
| FL | **{valve_vals['FL']:.3f}** | — |
| xT | **{valve_vals['xT']:.3f}** | — |
| Valve Size d | **{valve_vals['d']:.1f}** | {'mm' if unit_system == 'SI' else 'in'} |
| Sizing Margin | **{sidebar_vals['sizing_margin_pct']:.0f} %** | |
"""
            )

    # =========================================================================
    # CALCULATE BUTTON LOGIC
    # =========================================================================
    if sidebar_vals["calculate_clicked"]:

        # Block if Steam + iapws missing
        if fluid_phase == "Steam" and not deps.get("iapws", True):
            st.error(
                "❌ Cannot size Steam service: `iapws` is not installed.  "
                "Please select Liquid or Gas, or install the package."
            )
            st.session_state["calc_attempted"]  = True
            st.session_state["result"]          = None
            st.session_state["calc_error"]      = "iapws not installed"

        else:
            with st.spinner("🔬 Running sizing calculation…"):
                try:
                    inputs_model = build_sizing_inputs(
                        sidebar_vals, process_vals, fluid_vals, valve_vals
                    )
                    result: SizingResult = run_sizing(inputs_model)
                    st.session_state["result"]         = result
                    st.session_state["calc_error"]     = None
                    st.session_state["calc_attempted"] = True

                except Exception as exc:
                    st.session_state["result"]         = None
                    st.session_state["calc_error"]     = (
                        f"**Input Error:** {exc}\n\n"
                        f"```\n{traceback.format_exc()}\n```"
                    )
                    st.session_state["calc_attempted"] = True

            # Toast notification
            if (
                st.session_state.get("result")
                and st.session_state["result"].success
            ):
                st.toast("✅ Calculation complete — see Results tab", icon="✅")
            elif st.session_state.get("calc_error"):
                st.toast("❌ Input error — check your inputs", icon="❌")
            else:
                st.toast("⚠ Completed with warnings", icon="⚠")

    # =========================================================================
    # TAB 2 — SIZING RESULTS
    # =========================================================================
    with tab_results:
        if not st.session_state["calc_attempted"]:
            st.info(
                "👈 Fill in the **Process Inputs** tab, then click "
                "**🔬 CALCULATE** in the sidebar to run the sizing calculation."
            )
        elif st.session_state.get("calc_error") and not st.session_state.get("result"):
            st.error(st.session_state["calc_error"])
        else:
            result: SizingResult = st.session_state["result"]

            if result is None:
                st.error("No result available. Check your inputs and try again.")
            else:
                # Render the main results panel
                render_results(result, unit_system)

                # ── Charts (Fix 3: all wrapped in _safe_chart) ────────────────
                if result.success:
                    st.divider()
                    col_chart1, col_chart2 = st.columns(2, gap="medium")

                    with col_chart1:
                        # Cv characteristic curve
                        cv_rated_val = valve_vals.get("Cv_rated")
                        if cv_rated_val is None and result.sizing_ratio:
                            cv_rated_val = (
                                result.Cv_required / result.sizing_ratio
                                if result.sizing_ratio else None
                            )

                        if cv_rated_val and result.Cv_required:
                            _safe_chart(
                                plot_cv_characteristic,
                                Cv_rated=cv_rated_val,
                                Cv_required=result.Cv_required,
                                R_inherent=valve_vals.get("R_inherent", 50.0),
                                char=valve_vals.get("char"),
                                opening_pct=result.opening_pct,
                            )
                        else:
                            st.info(
                                "Enter **Rated Cv** in the Inputs tab to see "
                                "the characteristic curve."
                            )

                    with col_chart2:
                        # Sizing ratio gauge
                        if result.sizing_ratio and result.Cv_required:
                            cv_rated_for_gauge = (
                                result.Cv_required / result.sizing_ratio
                            )
                            _safe_chart(
                                plot_sizing_gauge,
                                sizing_ratio=result.sizing_ratio,
                                Cv_required=result.Cv_required,
                                Cv_rated=cv_rated_for_gauge,
                            )
                        else:
                            st.info(
                                "Enter **Rated Cv** to see the sizing ratio gauge."
                            )

                    # Pressure profile (liquid only)
                    if (
                        result.fluid_phase == FluidPhase.LIQUID
                        and result.cavitation
                        and result.P1_bar
                        and result.P2_bar
                    ):
                        st.markdown(
                            section_header_html("Pressure Profile Through Valve"),
                            unsafe_allow_html=True,
                        )
                        Pv_bar_si = fluid_vals.get("Pv", 0.023)
                        if unit_system == "US":
                            Pv_bar_si = Pv_bar_si / 14.504

                        _safe_chart(
                            plot_pressure_profile,
                            P1_bar=result.P1_bar,
                            P_vc_bar=result.cavitation.P_vc,
                            P2_bar=result.P2_bar,
                            Pv_bar=Pv_bar_si,
                            delta_P_max_bar=result.delta_P_max_bar,
                        )

                    # Cavitation map (liquid with active cavitation)
                    if (
                        result.fluid_phase == FluidPhase.LIQUID
                        and result.cavitation
                        and result.cavitation.regime.value != "none"
                        and result.P1_bar
                        and result.P2_bar
                    ):
                        st.markdown(
                            section_header_html("Cavitation Map"),
                            unsafe_allow_html=True,
                        )
                        Pv_bar_si = fluid_vals.get("Pv", 0.023)
                        if unit_system == "US":
                            Pv_bar_si = Pv_bar_si / 14.504

                        _safe_chart(
                            plot_cavitation_map,
                            P1_bar=result.P1_bar,
                            P2_bar=result.P2_bar,
                            Pv_bar=Pv_bar_si,
                            FL=valve_vals["FL"],
                            delta_P_max=result.cavitation.delta_P_max,
                            delta_P_incipient=result.cavitation.delta_P_incipient,
                        )

    # =========================================================================
    # TAB 3 — NOISE ANALYSIS
    # =========================================================================
    with tab_noise:
        if not st.session_state["calc_attempted"]:
            st.info("Run a calculation first to see noise analysis.")
        elif st.session_state.get("calc_error") and not st.session_state.get("result"):
            st.error("Fix input errors first, then recalculate.")
        else:
            result: SizingResult = st.session_state["result"]

            if result is not None:
                render_noise(result)

                # Noise SPL gauge
                if result.success and result.noise:
                    st.divider()
                    col_ng, _ = st.columns([1, 1])
                    with col_ng:
                        _safe_chart(
                            plot_noise_gauge,
                            Lpe_dba=result.noise.Lpe_dba,
                            limit_dba=sidebar_vals["noise_limit_dba"],
                        )

    # =========================================================================
    # TAB 4 — WARNINGS
    # =========================================================================
    with tab_warnings:
        if not st.session_state["calc_attempted"]:
            st.info("Run a calculation first to see engineering warnings.")
        elif st.session_state.get("calc_error") and not st.session_state.get("result"):
            st.error("Fix input errors first, then recalculate.")
        else:
            result: SizingResult = st.session_state["result"]
            if result is not None:
                render_warning_panel(result)

    # =========================================================================
    # TAB 5 — REPORT
    # =========================================================================
    with tab_report:
        if not st.session_state["calc_attempted"]:
            st.info("Run a calculation first to generate a report.")
        elif st.session_state.get("calc_error") and not st.session_state.get("result"):
            st.error("Fix input errors first, then recalculate.")
        else:
            result: SizingResult = st.session_state["result"]
            if result is not None:
                render_report_panel(result)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()