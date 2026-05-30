"""
Plotly chart definitions for the Control Valve Sizer.
======================================================
All charts accept plain Python / Pydantic values and return plotly Figure
objects rendered by app.py via st.plotly_chart().

No Streamlit calls are made inside chart functions to keep them testable
and reusable outside the Streamlit context.
"""

from __future__ import annotations

import math
from typing import Optional

import plotly.graph_objects as go

from backend.models import CavitationRegime, SizingResult, ValveCharacteristic
from frontend.ui_styles import CAVITATION_COLOURS, COLOUR

# ---------------------------------------------------------------------------
# SHARED LAYOUT DEFAULTS
# 'margin' intentionally excluded — each chart passes its own margin.
# ---------------------------------------------------------------------------
_LAYOUT = dict(
    font=dict(family="Inter, Arial, sans-serif", size=12, color="#1A1A2E"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#fafafa",
    hoverlabel=dict(bgcolor="white", font_size=12),
)

# Margin presets referenced by each chart individually
_M_STD   = dict(l=10, r=10, t=40, b=10)   # standard chart margin
_M_GAUGE = dict(l=20, r=20, t=30, b=10)   # gauge chart margin


# ---------------------------------------------------------------------------
# 1. Cv CHARACTERISTIC CURVE
# ---------------------------------------------------------------------------

def plot_cv_characteristic(
    Cv_rated: float,
    Cv_required: Optional[float],
    R_inherent: float,
    char: ValveCharacteristic,
    opening_pct: Optional[float],
) -> go.Figure:
    """Plot all three inherent flow characteristic curves with operating point.

    Equations (IEC 60534-2-4):
        Equal %:  Cv(x) = Cv_min x R^(x/100)
        Linear:   Cv(x) = Cv_min + (Cv_rated - Cv_min) x x/100
        Quick-O:  Cv(x) = Cv_rated x sqrt(x/100)
    """
    x_vals  = list(range(0, 101))
    Cv_min  = Cv_rated / max(R_inherent, 1.0)

    ep_vals  = [Cv_min * R_inherent ** (xi / 100) for xi in x_vals]
    lin_vals = [Cv_min + (Cv_rated - Cv_min) * xi / 100 for xi in x_vals]
    qo_vals  = [Cv_rated * math.sqrt(xi / 100) if xi > 0 else 0 for xi in x_vals]

    fig = go.Figure()

    traces = [
        ("Equal Percentage", ep_vals,  COLOUR["primary"],  ValveCharacteristic.EQUAL_PERCENTAGE),
        ("Linear",           lin_vals, COLOUR["success"],  ValveCharacteristic.LINEAR),
        ("Quick Opening",    qo_vals,  COLOUR["warning"],  ValveCharacteristic.QUICK_OPENING),
    ]

    for name, y_vals, colour, cv_type in traces:
        is_active = (cv_type == char)
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode="lines",
            name=name,
            line=dict(
                color=colour,
                width=3 if is_active else 1.5,
                dash="solid" if is_active else "dot",
            ),
            opacity=1.0 if is_active else 0.45,
        ))

    if Cv_required is not None and opening_pct is not None:
        fig.add_trace(go.Scatter(
            x=[opening_pct], y=[Cv_required],
            mode="markers+text",
            name="Operating Point",
            marker=dict(color="#dc3545", size=14, symbol="diamond",
                        line=dict(width=2, color="white")),
            text=[f" Cv={Cv_required:.1f}"],
            textposition="middle right",
            textfont=dict(color="#dc3545", size=11, family="Arial Black"),
        ))

    fig.add_vrect(
        x0=10, x1=90,
        fillcolor="rgba(25, 135, 84, 0.06)",
        layer="below", line_width=0,
        annotation_text="Controllable zone (10-90%)",
        annotation_position="top left",
        annotation_font_color=COLOUR["success"],
        annotation_font_size=10,
    )

    fig.update_layout(
        **_LAYOUT,
        margin=_M_STD,
        title=dict(text="Inherent Flow Characteristic Curves", font_size=14),
        xaxis=dict(title="Valve Opening [%]", range=[0, 100], gridcolor="#e9ecef"),
        yaxis=dict(title="Cv [-]", range=[0, Cv_rated * 1.05], gridcolor="#e9ecef"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ---------------------------------------------------------------------------
# 2. PRESSURE PROFILE  (Liquid only)
# ---------------------------------------------------------------------------

def plot_pressure_profile(
    P1_bar: float,
    P_vc_bar: float,
    P2_bar: float,
    Pv_bar: float,
    delta_P_max_bar: Optional[float],
) -> go.Figure:
    """Horizontal pressure profile bar chart showing P1, P_vc, P2 vs Pv."""
    labels = ["P1 (Inlet)", "Pvc (Vena Contracta)", "P2 (Outlet)"]
    values = [P1_bar, P_vc_bar, P2_bar]
    colours = [COLOUR["primary"], COLOUR["warning"], COLOUR["success"]]
    display_values = [max(v, 0.0) for v in values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels, x=display_values,
        orientation="h",
        marker_color=colours,
        text=[f"{v:.3f} bar" for v in values],
        textposition="inside",
        insidetextanchor="start",
        textfont=dict(color="white", size=11, family="Arial Black"),
    ))

    fig.add_vline(
        x=Pv_bar, line_color="#dc3545",
        line_dash="dash", line_width=2,
        annotation_text=f"Pv = {Pv_bar:.3f} bar",
        annotation_position="top right",
        annotation_font_color="#dc3545",
    )

    if delta_P_max_bar and P1_bar > delta_P_max_bar:
        choked_p2 = P1_bar - delta_P_max_bar
        fig.add_vline(
            x=choked_p2, line_color=COLOUR["warning"],
            line_dash="dashdot", line_width=1.5,
            annotation_text="P2 choked threshold",
            annotation_position="bottom right",
            annotation_font_color=COLOUR["warning"],
        )

    fig.update_layout(
        **_LAYOUT,
        margin=_M_STD,
        title=dict(text="Pressure Profile Through Valve", font_size=14),
        xaxis=dict(title="Absolute Pressure [bar]", gridcolor="#e9ecef"),
        yaxis=dict(gridcolor="#e9ecef"),
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# 3. SIZING RATIO GAUGE
# ---------------------------------------------------------------------------

def plot_sizing_gauge(
    sizing_ratio: float,
    Cv_required: float,
    Cv_rated: float,
) -> go.Figure:
    """Gauge chart showing Cv_required / Cv_rated with colour-coded zones."""
    pct = min(sizing_ratio * 100, 120)

    if pct < 20:
        bar_colour = "#dc3545"
    elif pct < 60:
        bar_colour = "#fd7e14"
    elif pct <= 85:
        bar_colour = "#198754"
    elif pct <= 100:
        bar_colour = "#fd7e14"
    else:
        bar_colour = "#dc3545"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number=dict(suffix=" %", font=dict(size=28, color=bar_colour)),
        delta=dict(reference=72.5, valueformat=".1f", suffix=" %"),
        gauge=dict(
            axis=dict(range=[0, 120], ticksuffix="%",
                      tickfont=dict(size=10), nticks=7),
            bar=dict(color=bar_colour, thickness=0.25),
            bgcolor="white",
            bordercolor="#dee2e6",
            steps=[
                dict(range=[0, 20],    color="#fde8e8"),
                dict(range=[20, 60],   color="#fff8f0"),
                dict(range=[60, 85],   color="#edf7f1"),
                dict(range=[85, 100],  color="#fff8f0"),
                dict(range=[100, 120], color="#fde8e8"),
            ],
            threshold=dict(
                line=dict(color="#dc3545", width=3),
                thickness=0.75,
                value=100,
            ),
        ),
        title=dict(
            text=(
                f"Sizing Ratio<br>"
                f"<span style='font-size:0.8em'>Cv {Cv_required:.1f}"
                f" / {Cv_rated:.1f}</span>"
            ),
            font=dict(size=13),
        ),
    ))

    # margin passed directly — NOT via **_LAYOUT to avoid duplicate key error
    fig.update_layout(
        **_LAYOUT,
        margin=_M_GAUGE,
        height=260,
    )
    return fig


# ---------------------------------------------------------------------------
# 4. NOISE GAUGE
# ---------------------------------------------------------------------------

def plot_noise_gauge(Lpe_dba: float, limit_dba: float) -> go.Figure:
    """Gauge chart for A-weighted external SPL at 1 m."""
    max_range = max(120.0, Lpe_dba + 10)

    if Lpe_dba >= limit_dba:
        bar_colour = "#dc3545"
    elif Lpe_dba >= limit_dba * 0.9:
        bar_colour = "#fd7e14"
    else:
        bar_colour = "#198754"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=Lpe_dba,
        number=dict(suffix=" dBA", font=dict(size=28, color=bar_colour)),
        gauge=dict(
            axis=dict(range=[0, max_range], ticksuffix=" dB",
                      tickfont=dict(size=10), nticks=7),
            bar=dict(color=bar_colour, thickness=0.25),
            bgcolor="white",
            bordercolor="#dee2e6",
            steps=[
                dict(range=[0, 70],             color="#edf7f1"),
                dict(range=[70, limit_dba],      color="#fff8f0"),
                dict(range=[limit_dba, max_range], color="#fde8e8"),
            ],
            threshold=dict(
                line=dict(color="#dc3545", width=3),
                thickness=0.75,
                value=limit_dba,
            ),
        ),
        title=dict(
            text=(
                f"External SPL at 1 m<br>"
                f"<span style='font-size:0.8em'>Limit: {limit_dba:.0f} dBA</span>"
            ),
            font=dict(size=13),
        ),
    ))

    # margin passed directly — NOT via **_LAYOUT to avoid duplicate key error
    fig.update_layout(
        **_LAYOUT,
        margin=_M_GAUGE,
        height=260,
    )
    return fig


# ---------------------------------------------------------------------------
# 5. CAVITATION MAP  (Liquid only)
# ---------------------------------------------------------------------------

def plot_cavitation_map(
    P1_bar: float,
    P2_bar: float,
    Pv_bar: float,
    FL: float,
    delta_P_max: float,
    delta_P_incipient: float,
) -> go.Figure:
    """Sigma vs dP space showing cavitation regime boundaries."""
    delta_P_actual = P1_bar - P2_bar
    sigma_actual   = (P1_bar - Pv_bar) / max(delta_P_actual, 1e-6)

    dp_range    = [max(0.01, i * delta_P_max * 1.3 / 100) for i in range(1, 101)]
    sigma_curve = [(P1_bar - Pv_bar) / dp for dp in dp_range]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dp_range, y=sigma_curve,
        mode="lines",
        name="sigma = (P1-Pv)/dP",
        line=dict(color=COLOUR["primary"], width=2),
    ))

    sigma_at_incipient = 1.0 / (FL ** 2)
    fig.add_hline(
        y=sigma_at_incipient, line_dash="dash",
        line_color=COLOUR["warning"], line_width=1.5,
        annotation_text="sigma_incipient = 1/FL2",
        annotation_font_color=COLOUR["warning"],
    )
    fig.add_vline(
        x=delta_P_max, line_dash="dash",
        line_color=COLOUR["danger"], line_width=1.5,
        annotation_text="dP_max (choked)",
        annotation_font_color=COLOUR["danger"],
    )
    fig.add_vline(
        x=delta_P_incipient, line_dash="dot",
        line_color="#ffc107", line_width=1.5,
        annotation_text="dP_incipient",
        annotation_font_color="#ffc107",
    )

    fig.add_trace(go.Scatter(
        x=[delta_P_actual], y=[sigma_actual],
        mode="markers+text",
        name="Operating Point",
        marker=dict(color="#dc3545", size=14, symbol="diamond",
                    line=dict(width=2, color="white")),
        text=[f" sigma={sigma_actual:.2f}"],
        textposition="middle right",
        textfont=dict(color="#dc3545", size=11),
    ))

    fig.update_layout(
        **_LAYOUT,
        margin=_M_STD,
        title=dict(text="Cavitation Map (sigma vs dP)", font_size=14),
        xaxis=dict(title="dP [bar]", gridcolor="#e9ecef"),
        yaxis=dict(title="Cavitation Index sigma [-]", gridcolor="#e9ecef"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
