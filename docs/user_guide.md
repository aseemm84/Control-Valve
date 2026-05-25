# User Guide

**Control Valve Sizer — Step-by-Step Operating Instructions**

---

## Getting Started

Launch the application:
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## Step 1 — Global Settings (Sidebar)

| Setting | Description |
|---|---|
| **Unit System** | SI (bar, m³/h, mm, °C) or US (psi, GPM, inches, °F) |
| **Fluid Phase** | Liquid / Gas / Steam |
| **ASME Class** | Pressure class for P-T rating check (B16.34) |
| **Sizing Margin** | Extra Cv beyond calculated (API RP 553: 20% liquid, 25% steam) |
| **Noise Limit** | Site regulatory SPL limit in dBA (default 85 dBA) |

Click **🔬 CALCULATE** after entering all inputs.

---

## Step 2 — Process Inputs Tab

### Pressures
Enter **gauge pressures** (barg or psig). Atmospheric pressure is added automatically.  
Both P1 and P2 must be positive. P2 must be less than P1.

### Temperature
Enter in °C (SI) or °F (US). Converted to Kelvin internally for all calculations.

### Flow Rate
- **Liquid Volumetric**: m³/h or US GPM
- **Gas Volumetric**: Nm³/h (0 °C, 1 atm) or SCFH (60 °F, 14.696 psia)
- **Mass flow**: kg/h or lb/h — recommended for gas/steam to avoid standard-condition ambiguity

### Fluid Properties

**Liquid:**
| Field | Description |
|---|---|
| Gf | Specific gravity relative to water at 15 °C |
| Pv | Vapour pressure at T1 (absolute) — critical for cavitation |
| Pc | Thermodynamic critical pressure — used in FF = 0.96 − 0.28√(Pv/Pc) |
| μ | Dynamic viscosity in cP — needed for Reynolds number correction |

**Gas:**
| Field | Description |
|---|---|
| M | Molecular weight [kg/kmol] |
| γ | Isentropic exponent Cp/Cv (air = 1.40, methane ≈ 1.31) |
| Z | Compressibility factor (Z = 1.0 for ideal gas) |

**Steam:**
- All properties retrieved automatically from IAPWS-IF97
- Only specify steam quality for wet steam (x_q < 1.0)

### Valve Parameters
| Field | Description |
|---|---|
| FL | Liquid pressure recovery factor (manufacturer data; typical 0.55–0.95) |
| xT | Pressure differential ratio at choked flow (manufacturer data; typical 0.20–0.75) |
| Fd | Valve style modifier for noise (globe = 1.0; multi-port cage ≈ 0.1–0.3) |
| d | Valve nominal body size |
| D1, D2 | Upstream/downstream pipe internal diameter (set = d if no reducers) |
| t_wall | Downstream pipe wall thickness for noise calculation |
| Cv_rated | Optional: manufacturer rated Cv — enables sizing ratio and opening % |

---

## Step 3 — Interpreting Results

### Sizing Results Tab

**Cv Required**: The calculated Cv without margin.  Select a valve with rated Cv ≥ Cv_design.

**Sizing Ratio**: Cv_required / Cv_rated
- < 20%: Valve is severely oversized — consider smaller valve
- 60–85%: **Optimal range**
- > 85%: Near full capacity — limited control headroom
- > 100%: Undersized — flow target cannot be achieved

**Valve Opening %**: Estimated opening at the design flow condition.
- Keep between 10% and 90% for good controllability

### Flow Condition Flags
| Badge | Meaning |
|---|---|
| ✓ NOT CHOKED | Normal flow; ΔP below maximum |
| ⚡ CHOKED | Maximum flow reached; increasing ΔP won't increase flow |
| 💧 NONE | No cavitation |
| 💧 INCIPIENT | Bubble formation starting; monitor |
| 💧 CONSTANT | Established cavitation; anti-cavitation trim recommended |
| 💧 CHOKED | Severe cavitation; special trim required |
| 💧 FLASHING | P2 ≤ Pv; two-phase exit; flash-service trim required |

### Noise Analysis Tab
- **Lpe > 85 dBA**: Exceeds standard site limit — action required
- **Mitigation options**: Multi-port trim (reduce Fd), pipe lagging, multi-stage letdown

---

## Step 4 — Warnings Tab

All engineering messages are classified:
- 🔴 **ERROR**: Hard constraint violated; results may be invalid
- 🟠 **WARNING**: Soft constraint; results computed but review required
- 🔵 **INFO**: Informational note; no action needed

---

## Step 5 — Report Download

Available from the **Report** tab after a successful calculation:
- **PDF**: Professional sizing report with all sections
- **Excel**: Structured workbook for project documentation

---

## Common Issues

| Symptom | Likely Cause | Solution |
|---|---|---|
| ERR_PRESSURE_INVERSION | P2 ≥ P1 | Check pressure inputs; ensure P1 > P2 |
| ERR_PV_EXCEEDS_P1 | Pv ≥ P1 (fluid already vaporised) | Increase P1 or reduce T1 |
| WARN_CHOKED_LIQUID | ΔP > ΔP_max | Reduce ΔP or use multi-stage letdown |
| WARN_CAVITATION_CHOKED | Severe cavitation | Use anti-cavitation trim |
| WARN_OVERSIZED | Sizing ratio < 20% | Select a smaller valve size |
| Steam property error | iapws not installed | Run `pip install iapws>=1.5.2` |

---

## Fluid and Valve Presets

The **Quick-Select** dropdowns in the inputs form load from:
- `data/fluid_presets.json` — common fluid properties
- `data/valve_presets.json` — typical valve coefficients (FL, xT, Fd)

**Always verify preset values against manufacturer datasheets** before finalising a design.

---

## Quick Reference — Sizing Flow

```
1. Select unit system + fluid phase
2. Enter P1, P2 (gauge), T1, flow rate
3. Enter fluid properties (Gf/M/γ + Pv/Pc for liquid)
4. Enter valve FL, xT, Fd, d, D1, D2
5. Click CALCULATE
6. Check sizing ratio (target: 60–85%)
7. Review warnings — address any ERRORS
8. Check noise level vs. site limit
9. Download PDF or Excel report
```