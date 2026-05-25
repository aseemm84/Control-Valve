"""
Control Valve Sizer — Frontend Package
========================================
All Streamlit UI components.  This package contains:
  - ui_styles.py   : CSS injection and theming
  - ui_inputs.py   : All st.* input widgets
  - ui_results.py  : Sizing result display
  - ui_noise.py    : Noise analysis display
  - ui_warnings.py : Engineering warning panel
  - ui_charts.py   : Plotly visualisations
  - ui_report.py   : PDF / Excel report generation

Architecture contract:
    This package imports ONLY from backend.orchestrator and backend.models.
    No direct import of any other backend module is permitted here.
    All math is performed in the backend; this layer only renders results.
"""
__version__ = "1.0.0"