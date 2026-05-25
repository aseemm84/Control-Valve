"""
Noise analysis display panel.
================================
Renders the NoiseResult from both aerodynamic (gas/steam) and
hydrodynamic (liquid) noise prediction models.
"""

from __future__ import annotations

import streamlit as st

from backend.models import FluidPhase, NoiseResult, SizingResult
from frontend.ui_styles import COLOUR, badge_html, eng_table_html, section_header_html


def render_noise(result: SizingResult) -> None:
    """
    Master noise display function.  Called by app.py inside the Noise tab.

    Parameters
    ----------
    result : SizingResult   Full sizing result containing noise sub-model.
    """
    if not result.success:
        st.info("ℹ Run a successful sizing calculation first to view noise results.")
        return

    if result.noise is None:
        st.warning(
            "⚠ Noise calculation was not completed.  "
            "This may occur when pipe wall thickness is missing or steam "
            "properties could not be retrieved."
        )
        return

    noise = result.noise
    _render_noise_header(noise, result)
    st.divider()
    col_left, col_right = st.columns([1, 1])
    with col_left:
        _render_noise_metrics(noise)
        _render_noise_table(noise)
    with col_right:
        _render_noise_regime_info(noise, result)
        _render_noise_compliance(noise)


# ---------------------------------------------------------------------------
# PRIVATE HELPERS
# ---------------------------------------------------------------------------

def _render_noise_header(noise: NoiseResult, result: SizingResult) -> None:
    """Large SPL metric with compliance badge."""
    st.markdown(
        section_header_html("Aerodynamic / Hydrodynamic Noise Prediction"),
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    with cols[0]:
        st.metric(
            label="External SPL at 1 m",
            value=f"{noise.Lpe_dba:.1f} dBA",
            delta=("⚠ Exceeds limit" if noise.exceeds_limit else "✓ Within limit"),
            delta_color="inverse" if noise.exceeds_limit else "normal",
            help="A-weighted sound pressure level at 1 m from downstream pipe outer wall. "
                 "IEC 60534-8-3 (gas) / IEC 60534-8-4 (liquid).",
        )
    with cols[1]:
        st.metric(
            label="Internal Power Level LWi",
            value=f"{noise.LWi_db:.1f} dB",
            help="Internal acoustic power level [dB re 1 pW].  "
                 "Before pipe wall transmission loss.",
        )
    with cols[2]:
        st.metric(
            label="Pipe Wall Attenuation TL",
            value=f"{noise.TL_db:.1f} dB",
            help="Transmission loss through the downstream pipe wall.",
        )


def _render_noise_metrics(noise: NoiseResult) -> None:
    """Secondary noise metrics: frequency, efficiency."""
    st.markdown(
        section_header_html("Noise Chain Parameters"), unsafe_allow_html=True
    )
    rows = [
        ("Peak Frequency f_p",       f"{noise.f_peak_hz:.0f}",  "Hz"),
        ("Acoustic Efficiency η",    f"{noise.eta:.2e}",         "—"),
        ("Sound Power Level LWi",    f"{noise.LWi_db:.1f}",      "dB re 1 pW"),
        ("Pipe TL",                  f"{noise.TL_db:.1f}",       "dB"),
        ("External Lpe",             f"{noise.Lpe_dba:.1f}",     "dBA at 1 m"),
    ]
    st.markdown(eng_table_html(rows), unsafe_allow_html=True)


def _render_noise_table(noise: NoiseResult) -> None:
    """Chain calculation breakdown."""
    st.markdown(
        section_header_html("Calculation Chain (IEC 60534-8-3/8-4)"),
        unsafe_allow_html=True,
    )

    chain = [
        ("① Mechanical Stream Power W_mech", "ṁ × U_vc² / 2",  "W"),
        ("② Acoustic Power W_a",             "η × W_mech",       "W"),
        ("③ Sound Power Level LWi",           "10·log₁₀(Wa/W_ref)", "dB"),
        ("④ Pipe Wall TL",                    "f(f_p, m_s, ρ, c)", "dB"),
        ("⑤ A-Weighting Correction ΔLA",      "f(f_p) per IEC 61672","dB"),
        ("⑥ External SPL Lpe",               "LWi − TL + ΔLA",   "dBA"),
    ]
    rows = [(step, formula, unit) for step, formula, unit in chain]
    st.markdown(eng_table_html(rows), unsafe_allow_html=True)


def _render_noise_regime_info(noise: NoiseResult, result: SizingResult) -> None:
    """Explain the active noise regime."""
    st.markdown(
        section_header_html("Flow Regime"), unsafe_allow_html=True
    )

    regime = noise.regime.lower()
    badges_html = ""

    if result.fluid_phase in (FluidPhase.GAS, FluidPhase.STEAM):
        if regime == "choked":
            badges_html = badge_html("⚡ CHOKED (Sonic jet — shock waves present)", "danger")
            st.markdown(badges_html, unsafe_allow_html=True)
            st.markdown(
                "Shock waves form at the valve orifice. Noise levels are at their "
                "maximum for the given mass flow. Consider multi-stage pressure "
                "reduction or low-noise trim to reduce SPL."
            )
        else:
            badges_html = badge_html("✓ SUBCRITICAL (Subsonic jet)", "success")
            st.markdown(badges_html, unsafe_allow_html=True)
            st.markdown(
                "Gas expands subsonically through the valve. Aerodynamic noise is "
                "generated by turbulent mixing downstream of the vena contracta."
            )
    else:
        # Liquid (hydrodynamic)
        cav_regime_info = {
            "none":      ("✓ NO CAVITATION",          "success",
                           "Turbulent liquid flow.  Noise is due to hydraulic turbulence only."),
            "incipient": ("⚠ INCIPIENT CAVITATION",  "warning",
                           "Bubble formation begins.  Audible crackling noise; minimal damage."),
            "constant":  ("⚠ CONSTANT CAVITATION",   "warning",
                           "Established cavitation.  Continuous noise; material damage risk.  "
                           "Consider anti-cavitation trim."),
            "choked":    ("❌ CHOKED CAVITATION",      "danger",
                           "Maximum cavitation intensity.  Severe material damage.  "
                           "Anti-cavitation trim required."),
            "flashing":  ("❌ FLASHING",               "purple",
                           "P2 ≤ Pv — two-phase exit.  Flash trim and expanded outlet required."),
        }
        if regime in cav_regime_info:
            label, style, desc = cav_regime_info[regime]
            st.markdown(badge_html(label, style), unsafe_allow_html=True)
            st.markdown(desc)


def _render_noise_compliance(noise: NoiseResult) -> None:
    """Render compliance summary."""
    st.markdown(
        section_header_html("Compliance Summary"), unsafe_allow_html=True
    )
    if noise.exceeds_limit:
        st.markdown(
            f'<div class="err-box">❌ <strong>SPL {noise.Lpe_dba:.1f} dBA exceeds the site limit.</strong><br>'
            "Recommended actions:<br>"
            "• Select low-noise trim (small Fd / multi-port cage)<br>"
            "• Apply acoustic insulation / pipe lagging<br>"
            "• Reduce ΔP with multi-stage pressure letdown<br>"
            "• Increase downstream pipe schedule (thicker wall)</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="ok-box">✅ <strong>SPL {noise.Lpe_dba:.1f} dBA is within the limit.</strong><br>'
            "No additional noise mitigation required based on current inputs.</div>",
            unsafe_allow_html=True,
        )