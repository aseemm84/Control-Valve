"""
Sizing result display panel.
==============================
Renders the SizingResult returned by orchestrator.run_sizing() into
organised Streamlit components — metric cards, badges, data tables, and charts.
No computation is performed here; all values are taken directly from the model.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from backend.models import CavitationRegime, FluidPhase, MessageLevel, SizingResult
from frontend.ui_styles import (
    CAVITATION_COLOURS, COLOUR,
    badge_html, eng_table_html, section_header_html,
)


# ---------------------------------------------------------------------------
# STATUS BANNER
# ---------------------------------------------------------------------------

def render_status_banner(result: SizingResult) -> None:
    """Render a success / failure banner at the top of the results panel."""
    if result.success:
        st.markdown(
            '<div class="result-ok">'
            '✅ <strong>Sizing calculation completed successfully.</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="result-err">'
            '❌ <strong>Calculation failed — see errors below.</strong>'
            '</div>',
            unsafe_allow_html=True,
        )
        for msg in result.messages:
            if msg.level == MessageLevel.ERROR:
                st.error(f"**[{msg.code}]** {msg.message}")


# ---------------------------------------------------------------------------
# PRIMARY Cv METRICS
# ---------------------------------------------------------------------------

def render_cv_metrics(result: SizingResult, unit_system: str) -> None:
    """Render the top-row Cv / Kv metric cards."""
    st.markdown(
        section_header_html("Primary Sizing Results"), unsafe_allow_html=True
    )

    cols = st.columns(4)
    with cols[0]:
        st.metric(
            label="Cv Required",
            value=f"{result.Cv_required:.2f}" if result.Cv_required else "—",
            help="Required valve flow coefficient (no margin).",
        )
    with cols[1]:
        st.metric(
            label="Cv Design",
            value=f"{result.Cv_design:.2f}" if result.Cv_design else "—",
            help="Cv with engineering margin applied.  Select a valve ≥ this value.",
        )
    with cols[2]:
        st.metric(
            label="Kv Required",
            value=f"{result.Kv_required:.2f}" if result.Kv_required else "—",
            help="Metric flow coefficient.  Kv = 0.865 × Cv.",
        )
    with cols[3]:
        if result.sizing_ratio is not None:
            pct  = result.sizing_ratio * 100
            col  = (COLOUR["success"] if 60 <= pct <= 85
                    else COLOUR["warning"] if 20 <= pct < 60 or 85 < pct <= 100
                    else COLOUR["danger"])
            st.metric(
                label="Sizing Ratio",
                value=f"{pct:.1f} %",
                help="Cv_required / Cv_rated.  Optimal range: 60 – 85 %.",
            )
        else:
            st.metric(label="Sizing Ratio", value="—",
                      help="Enter Rated Cv to compute.")


# ---------------------------------------------------------------------------
# FLOW CONDITION BADGES
# ---------------------------------------------------------------------------

def render_condition_badges(result: SizingResult) -> None:
    """Render colour-coded flow condition badges."""
    st.markdown(
        section_header_html("Flow Condition Flags"), unsafe_allow_html=True
    )
    badges_html = ""

    # Fluid phase
    phase_colours = {
        FluidPhase.LIQUID: "info",
        FluidPhase.GAS:    "primary",
        FluidPhase.STEAM:  "purple",
    }
    if result.fluid_phase:
        pcolour = phase_colours.get(result.fluid_phase, "muted")
        badges_html += badge_html(result.fluid_phase.value.upper(), pcolour) + " "

    # Steam type
    if result.steam_type:
        badges_html += badge_html(result.steam_type.value.replace("_", " ").upper(), "purple") + " "

    # Choked
    if result.is_choked:
        badges_html += badge_html("⚡ CHOKED", "warning") + " "
    else:
        badges_html += badge_html("✓ NOT CHOKED", "success") + " "

    # Cavitation
    if result.cavitation:
        cav = result.cavitation
        reg = cav.regime.value
        cav_colour_map = {
            "none":      "success",
            "incipient": "warning",
            "constant":  "warning",
            "choked":    "danger",
            "flashing":  "purple",
        }
        col = cav_colour_map.get(reg, "muted")
        badges_html += badge_html(f"💧 {reg.upper()}", col) + " "

    # Viscous
    if result.FR is not None and result.FR < 0.99:
        badges_html += badge_html("🌊 VISCOUS CORRECTED", "info") + " "

    st.markdown(badges_html, unsafe_allow_html=True)
    st.caption("Flow condition flags are determined automatically from process inputs.")


# ---------------------------------------------------------------------------
# INTERMEDIATE VALUES TABLE
# ---------------------------------------------------------------------------

def render_intermediate_values(result: SizingResult, unit_system: str) -> None:
    """Render the engineering intermediate values table."""
    st.markdown(
        section_header_html("Intermediate Computed Values"), unsafe_allow_html=True
    )

    p_unit = "bar" if unit_system == "SI" else "psi"

    rows: list[tuple[str, str, str]] = []

    def _add(label: str, val: Optional[float], unit: str, decimals: int = 4) -> None:
        rows.append((label, f"{val:.{decimals}f}" if val is not None else "—", unit))

    # Process conditions (SI internal values always displayed in SI)
    _add("Inlet Pressure P1 (abs)",    result.P1_bar,           "bar abs", 3)
    _add("Outlet Pressure P2 (abs)",   result.P2_bar,           "bar abs", 3)
    _add("Inlet Temperature T1",       result.T1_K - 273.15 if result.T1_K else None,
         "°C", 1)
    _add("Fluid Density ρ₁",           result.rho1_kgm3,        "kg/m³", 2)
    _add("Mass Flow W",                result.W_kgh,             "kg/h", 2)

    # Piping correction
    _add("Piping Factor Fp",           result.Fp,                "—", 4)
    if result.FLP is not None:
        _add("Combined Factor FLP",    result.FLP,               "—", 4)
    if result.xTP is not None:
        _add("Combined Factor xTP",    result.xTP,               "—", 4)

    # Liquid specific
    if result.FF is not None:
        _add("Crit. Pressure Ratio FF", result.FF,               "—", 4)
    if result.delta_P_max_bar is not None:
        _add("ΔP_max (choked ΔP)",     result.delta_P_max_bar,   "bar", 3)
    if result.delta_P_eff_bar is not None:
        _add("ΔP_eff (used in Cv)",    result.delta_P_eff_bar,   "bar", 3)

    # Cavitation
    if result.cavitation:
        cav = result.cavitation
        _add("Vena Contracta Pressure Pvc", cav.P_vc,           "bar abs", 3)
        _add("Cavitation Index σ",      cav.sigma,               "—", 3)
        _add("Incipient Cavitation ΔP", cav.delta_P_incipient,   "bar", 3)

    # Gas specific
    if result.Fgamma is not None:
        _add("Specific Heat Ratio Factor Fγ", result.Fgamma,     "—", 4)
    if result.x is not None:
        _add("Pressure Differential Ratio x",  result.x,         "—", 4)
    if result.Y is not None:
        _add("Expansion Factor Y",       result.Y,               "—", 4)

    # Viscous
    if result.Rev is not None:
        _add("Valve Reynolds Number Rev", result.Rev,            "—", 0)
    if result.FR is not None:
        _add("Reynolds Number Factor FR",  result.FR,            "—", 4)

    st.markdown(eng_table_html(rows), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# OUTPUT METRICS
# ---------------------------------------------------------------------------

def render_output_metrics(result: SizingResult) -> None:
    """Render output sizing metrics: opening %, velocity, rangeability."""
    st.markdown(
        section_header_html("Sizing Output Metrics"), unsafe_allow_html=True
    )

    cols = st.columns(3)
    with cols[0]:
        if result.opening_pct is not None:
            val   = result.opening_pct
            delta = ("✓ Good" if 10 <= val <= 90 else "⚠ Outside 10-90%")
            st.metric("Valve Opening %", f"{val:.1f} %",
                      delta=delta,
                      delta_color=("normal" if 10 <= val <= 90 else "inverse"))
        else:
            st.metric("Valve Opening %", "—",
                      help="Provide Cv_rated to compute estimated opening.")

    with cols[1]:
        if result.velocity_ms is not None:
            v     = result.velocity_ms
            phase = result.fluid_phase
            limit = 5.0 if phase == FluidPhase.LIQUID else 80.0
            delta = "✓ OK" if v < limit * 0.6 else "⚠ Check limit"
            st.metric("Pipe Velocity", f"{v:.2f} m/s",
                      delta=delta,
                      delta_color=("normal" if v < limit * 0.6 else "inverse"))
        else:
            st.metric("Pipe Velocity", "—")

    with cols[2]:
        if result.sizing_ratio is not None:
            cv_r = result.Cv_required or 0
            cv_d = result.Cv_design or 0
            st.metric(
                "Cv_required / Cv_design",
                f"{cv_r:.2f} / {cv_d:.2f}",
                help="Required Cv vs. design Cv (with margin).",
            )
        else:
            st.metric("Cv Required", f"{result.Cv_required:.2f}" if result.Cv_required else "—")


# ---------------------------------------------------------------------------
# MASTER RESULTS RENDERER
# ---------------------------------------------------------------------------

def render_results(result: SizingResult, unit_system: str = "SI") -> None:
    """
    Master function — renders the complete results panel.
    Called by app.py inside the Results tab.

    Parameters
    ----------
    result      : SizingResult   Output from orchestrator.run_sizing().
    unit_system : str            Active unit system string ('SI' or 'US').
    """
    render_status_banner(result)

    if not result.success:
        return

    render_cv_metrics(result, unit_system)
    st.divider()
    render_condition_badges(result)
    st.divider()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        render_intermediate_values(result, unit_system)

    with col_right:
        render_output_metrics(result)

        # Cavitation detail
        if result.cavitation and result.cavitation.regime.value != "none":
            st.markdown(
                section_header_html("Cavitation Detail"), unsafe_allow_html=True
            )
            cav = result.cavitation
            cav_rows = [
                ("Regime",          cav.regime.value.upper(),  ""),
                ("Sigma σ",         f"{cav.sigma:.3f}",        "—"),
                ("P vena contracta",f"{cav.P_vc:.3f}",         "bar abs"),
                ("ΔP incipient",    f"{cav.delta_P_incipient:.3f}", "bar"),
                ("ΔP max",          f"{cav.delta_P_max:.3f}",  "bar"),
                ("FF factor",       f"{cav.FF:.4f}",           "—"),
            ]
            st.markdown(eng_table_html(cav_rows), unsafe_allow_html=True)