# 🔧 Control Valve Sizer

**Professional control valve sizing application** implementing international standards for liquid, gas, and steam service. Built with Python and Streamlit.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/streamlit-1.32%2B-red)](https://streamlit.io)
[![Standards](https://img.shields.io/badge/standard-IEC%2060534--2--1-green)](https://iec.ch)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

---

## 📐 Standards Implemented

| Standard | Scope |
|---|---|
| **IEC 60534-2-1:2011** | Primary sizing equations — liquid, gas, steam (turbulent, choked, viscous) |
| **ANSI/ISA-75.01.01-2012** | US equivalent — cross-validated N-factors and worked examples |
| **IEC 60534-8-3:2011** | Aerodynamic noise prediction (gas and steam service) |
| **IEC 60534-8-4:2015** | Hydrodynamic noise prediction (liquid — 5 cavitation regimes) |
| **IAPWS-IF97** | Steam/water thermodynamic properties (via `iapws` library) |
| **ASME B16.34-2017** | Pressure-temperature rating check |
| **API RP 553** | Sizing margin recommendations and velocity limits |

---

## 🚀 Features

- **Fluid phases:** Liquid (all regimes), Gas/Vapour (subcritical + choked), Superheated / Saturated / Wet Steam
- **Flow conditions:** Turbulent, Laminar (viscous FR correction), Choked, Cavitating (5-tier), Flashing
- **Piping corrections:** Fp, FLP, xTP for reducers and expanders (iterative solver)
- **Noise prediction:** Full IEC 60534-8-3 and 8-4 calculation chains with A-weighting
- **Unit systems:** SI (bar, m³/h, mm, °C) and US Customary (psi, GPM, inches, °F)
- **Interactive charts:** Cv characteristic curves, pressure profiles, cavitation maps, noise gauges
- **Reports:** Downloadable PDF and Excel engineering reports
- **Validation:** 10 hard constraint checks + 12 soft engineering warnings

---

## 📦 Installation

### Prerequisites

- Python ≥ 3.10
- pip

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/control-valve-sizer.git
cd control-valve-sizer

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the application
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

### Development Installation

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

---

## 🗂 Directory Structure

```
control_valve_sizer/
├── app.py                       ← Streamlit entry point
├── requirements.txt             ← Production dependencies
├── requirements-dev.txt         ← Development / test dependencies
├── README.md
│
├── .streamlit/
│   └── config.toml              ← Theme and server configuration
│
├── backend/                     ← Math engine (zero Streamlit)
│   ├── constants.py             ← N-factors, pipe tables, physical constants
│   ├── models.py                ← Pydantic v2 data models
│   ├── fluid_properties.py      ← Density, viscosity, IAPWS-IF97 steam
│   ├── piping_geometry.py       ← Fp, FLP, xTP (IEC 60534-2-1 §6)
│   ├── sizing_liquid.py         ← Liquid Cv equations
│   ├── sizing_gas.py            ← Gas/vapour Cv equations
│   ├── sizing_steam.py          ← Steam Cv + IF97 integration
│   ├── cavitation.py            ← 5-tier cavitation analysis
│   ├── viscous_correction.py    ← Reynolds number + FR factor
│   ├── noise_aerodynamic.py     ← IEC 60534-8-3 noise chain
│   ├── noise_hydrodynamic.py    ← IEC 60534-8-4 noise chain
│   ├── validator.py             ← Hard/soft constraint checks
│   └── orchestrator.py          ← Master coordinator (public API)
│
├── frontend/                    ← Streamlit UI (zero math)
│   ├── ui_styles.py             ← CSS and theming
│   ├── ui_inputs.py             ← Input widgets
│   ├── ui_results.py            ← Results display
│   ├── ui_noise.py              ← Noise analysis display
│   ├── ui_warnings.py           ← Warning panel
│   ├── ui_charts.py             ← Plotly charts
│   └── ui_report.py             ← PDF / Excel report generation
│
├── data/                        ← Static JSON reference data
│   ├── pipe_schedules.json      ← ASME B36.10M pipe dimensions
│   ├── valve_presets.json       ← Default FL, xT, Fd by valve type
│   └── fluid_presets.json       ← Common fluid properties
│
├── tests/                       ← pytest test suite
│   ├── conftest.py              ← Shared fixtures
│   └── test_*.py                ← Unit + integration tests
│
└── docs/
    ├── engineering_basis.md     ← Full mathematical reference
    └── user_guide.md            ← How to use the application
```

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=backend --cov-report=html

# Run a specific test file
pytest tests/test_sizing_liquid.py -v

# Run only fast unit tests (skip steam tests if iapws not installed)
pytest tests/ -v -k "not steam"
```

---

## 🔧 Usage Guide

1. **Select unit system** (SI or US) and **fluid phase** in the sidebar.
2. Enter **process conditions** (P1, P2, T1, flow) in the *Process Inputs* tab.
3. Enter **fluid properties** (Gf, Pv, Pc, μ for liquid; M, γ, Z for gas).
4. Enter **valve parameters** (FL, xT, Fd, d, D1, D2).
5. Optionally enter **Rated Cv** to compute sizing ratio and opening %.
6. Click **🔬 CALCULATE** in the sidebar.
7. View results in the **Sizing Results**, **Noise Analysis**, and **Warnings** tabs.
8. Download the engineering report from the **Report** tab.

---

## 📋 Input Conventions

| Parameter | Convention |
|---|---|
| Pressures | Enter as **gauge** pressure; atmospheric is added automatically |
| Temperature | Display in °C (SI) or °F (US); converted to K internally |
| Gas flow | Mass flow (kg/h or lb/h) avoids standard-condition ambiguity |
| Steam | All properties from IAPWS-IF97 automatically; only specify quality for wet steam |
| Cv_rated | Optional; required for sizing ratio and opening % calculation |

---

## ⚙ Configuration

Edit `.streamlit/config.toml` to customise:
- Colour theme (`primaryColor`, etc.)
- Server settings (port, CORS, upload size)
- Error detail visibility (set `showErrorDetails = false` for production)

---

## 📄 Licence

MIT Licence — see [LICENSE](LICENSE).

---

## 🏭 Standards References

- IEC 60534-2-1:2011, *Industrial-process control valves — Flow capacity — Sizing equations*
- ANSI/ISA-75.01.01-2012, *Flow Equations for Sizing Control Valves*
- IEC 60534-8-3:2011, *Control valve aerodynamic noise prediction*
- IEC 60534-8-4:2015, *Prediction of noise generated by hydrodynamic flow*
- IAPWS-IF97, *Industrial Formulation for Thermodynamic Properties of Water and Steam*
- ASME B16.34-2017, *Valves — Flanged, Threaded, and Welding End*
- API RP 553, *Refinery Control Valves*