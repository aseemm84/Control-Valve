"""
CSS injection and UI theming constants.
========================================
Call inject_custom_css() once at app startup.
Use the badge_html() and section_header_html() helpers to generate
semantic, colour-coded HTML components rendered via st.markdown(..., unsafe_allow_html=True).
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# COLOUR PALETTE  (matches .streamlit/config.toml primaryColor)
# ---------------------------------------------------------------------------
COLOUR = {
    "primary":  "#1B6CA8",
    "success":  "#198754",
    "warning":  "#fd7e14",
    "danger":   "#dc3545",
    "info":     "#0d6efd",
    "purple":   "#6f42c1",
    "light":    "#f8f9fa",
    "muted":    "#6c757d",
    "border":   "#dee2e6",
    "bg_card":  "#f0f4f8",
}

CAVITATION_COLOURS: dict[str, str] = {
    "none":      COLOUR["success"],
    "incipient": "#ffc107",
    "constant":  COLOUR["warning"],
    "choked":    COLOUR["danger"],
    "flashing":  COLOUR["purple"],
}

# ---------------------------------------------------------------------------
# MAIN CSS
# ---------------------------------------------------------------------------
_CSS = """
<style>
/* ── Page layout ── */
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
.main > div      { padding-top: 0.5rem; }

/* ── App header ── */
.app-header {
    display: flex;
    align-items: center;
    gap: 14px;
    border-bottom: 3px solid #1B6CA8;
    padding-bottom: 14px;
    margin-bottom: 18px;
}
.app-title  { font-size: 1.65rem; font-weight: 700; color: #1B6CA8; margin: 0; }
.app-sub    { font-size: 0.82rem; color: #6c757d; margin: 0; letter-spacing: 0.03em; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #f0f4f8;
    border-right: 2px solid #1B6CA8;
}
[data-testid="stSidebar"] h3 {
    color: #1B6CA8;
    font-size: 0.95rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 1rem;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: #f0f4f8;
    border: 1px solid #dee2e6;
    border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s;
}
[data-testid="metric-container"]:hover {
    box-shadow: 0 4px 12px rgba(27,108,168,0.15);
}
[data-testid="metric-label"] { font-size: 0.78rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.05em; color: #6c757d; }
[data-testid="metric-value"] { font-size: 1.7rem; font-weight: 700; color: #1A1A2E; }

/* ── Section header ── */
.section-hdr {
    background: linear-gradient(135deg, #1B6CA8 0%, #2196F3 100%);
    color: #fff;
    padding: 7px 14px;
    border-radius: 6px;
    font-size: 0.88rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin: 14px 0 10px 0;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 0.80rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    margin: 2px 4px 2px 0;
    vertical-align: middle;
}
.badge-success { background:#198754; color:#fff; }
.badge-warning { background:#fd7e14; color:#fff; }
.badge-danger  { background:#dc3545; color:#fff; }
.badge-info    { background:#0d6efd; color:#fff; }
.badge-purple  { background:#6f42c1; color:#fff; }
.badge-muted   { background:#6c757d; color:#fff; }
.badge-primary { background:#1B6CA8; color:#fff; }

/* ── Engineering data table ── */
.eng-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
    margin: 6px 0 14px 0;
}
.eng-table th {
    background: #1B6CA8;
    color: #fff;
    padding: 7px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 0.80rem;
    letter-spacing: 0.04em;
}
.eng-table td { padding: 5px 10px; border-bottom: 1px solid #dee2e6; }
.eng-table tr:nth-child(even) td { background: #f8f9fa; }
.eng-table .val { font-weight: 700; color: #1B6CA8; }
.eng-table .unit { color: #6c757d; font-size: 0.82rem; }

/* ── Warning / info boxes ── */
.warn-box {
    border-left: 4px solid #fd7e14;
    background: #fff8f0;
    padding: 8px 14px;
    border-radius: 0 6px 6px 0;
    margin: 5px 0;
    font-size: 0.88rem;
}
.err-box {
    border-left: 4px solid #dc3545;
    background: #fff5f5;
    padding: 8px 14px;
    border-radius: 0 6px 6px 0;
    margin: 5px 0;
    font-size: 0.88rem;
}
.info-box {
    border-left: 4px solid #0d6efd;
    background: #f0f6ff;
    padding: 8px 14px;
    border-radius: 0 6px 6px 0;
    margin: 5px 0;
    font-size: 0.88rem;
}
.ok-box {
    border-left: 4px solid #198754;
    background: #f0fff4;
    padding: 8px 14px;
    border-radius: 0 6px 6px 0;
    margin: 5px 0;
    font-size: 0.88rem;
}

/* ── Calculate button ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: #1B6CA8;
    color: white;
    font-weight: 700;
    font-size: 1.05rem;
    border-radius: 8px;
    padding: 14px 24px;
    width: 100%;
    letter-spacing: 0.04em;
    border: none;
    box-shadow: 0 4px 12px rgba(27,108,168,0.35);
    transition: all 0.2s;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #155A8A;
    box-shadow: 0 6px 18px rgba(27,108,168,0.45);
    transform: translateY(-1px);
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0;
    font-weight: 600;
    font-size: 0.88rem;
}

/* ── Status result banner ── */
.result-ok  { background:#f0fff4; border:2px solid #198754; border-radius:10px;
              padding:12px 20px; margin-bottom:18px; }
.result-err { background:#fff5f5; border:2px solid #dc3545; border-radius:10px;
              padding:12px 20px; margin-bottom:18px; }
</style>
"""


def inject_custom_css() -> None:
    """Inject the global CSS stylesheet into the Streamlit page."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HTML COMPONENT HELPERS
# ---------------------------------------------------------------------------

def badge_html(label: str, style: str = "primary") -> str:
    """
    Return a coloured badge as an HTML string.

    Parameters
    ----------
    label : str   Text displayed inside the badge.
    style : str   One of: success, warning, danger, info, purple, muted, primary.
    """
    return f'<span class="badge badge-{style}">{label}</span>'


def section_header_html(title: str) -> str:
    """Return a styled section header as an HTML string."""
    return f'<div class="section-hdr">⚙ {title}</div>'


def eng_table_html(rows: list[tuple[str, str, str]]) -> str:
    """
    Build an engineering data table as HTML.

    Parameters
    ----------
    rows : list[tuple[str, str, str]]
        Each tuple is (label, value, unit).
    """
    html = '<table class="eng-table"><colgroup><col style="width:50%"><col style="width:30%"><col style="width:20%"></colgroup>'
    html += "<thead><tr><th>Parameter</th><th>Value</th><th>Unit</th></tr></thead><tbody>"
    for label, value, unit in rows:
        html += f'<tr><td>{label}</td><td class="val">{value}</td><td class="unit">{unit}</td></tr>'
    html += "</tbody></table>"
    return html


def app_header_html() -> str:
    """Return the styled application header HTML."""
    return """
    <div class="app-header">
        <div>
            <p class="app-title">🔧 Control Valve Sizer</p>
            <p class="app-sub">
                ANSI/ISA-75.01.01 &nbsp;·&nbsp; IEC 60534-2-1 &nbsp;·&nbsp;
                IEC 60534-8-3 / 8-4 &nbsp;·&nbsp; IAPWS-IF97
            </p>
        </div>
    </div>
    """