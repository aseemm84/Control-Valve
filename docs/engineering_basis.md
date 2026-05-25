# Engineering Basis Document

**Control Valve Sizer — Mathematical Reference**  
Standard: IEC 60534-2-1:2011 / ANSI/ISA-75.01.01-2012  
Revision: A | Status: Approved

---

## 1. Scope

This document defines the exact equations, constraints, and decision logic
implemented in the Control Valve Sizer backend. All equations are referenced
to their source clause in the applicable international standard.

---

## 2. N-Factor Constants (ISA-75.01.01, Table 1)

| N | SI Value | SI Context | US Value | US Context |
|---|---|---|---|---|
| N₁ | 0.865 | Q[m³/h], ΔP[bar] | 1.00 | Q[GPM], ΔP[psi] |
| N₂ | 0.00214 | d[mm] | 890 | d[in] |
| N₄ | 17,300 | Q[m³/h], ν[cSt], d[mm] | 76,000 | Q[GPM], ν[cSt], d[in] |
| N₅ | 0.00241 | d[mm] | 1,000 | d[in] |
| N₆ | 27.3 | W[kg/h], P[bar], ρ[kg/m³] | 63.3 | W[lb/h], P[psia], ρ[lb/ft³] |
| N₇ | 417 | q[Nm³/h], P[bar], T[K] | 1,360 | q[SCFH], P[psia], T[°R] |

---

## 3. Liquid Sizing (IEC 60534-2-1, §5.1)

### 3.1 Liquid Critical Pressure Ratio Factor
```
FF = 0.96 − 0.28 × √(Pv / Pc)        (Eq. 4.1)
```
Constraint: 0.50 ≤ FF ≤ 0.96

### 3.2 Maximum Effective Differential Pressure
```
ΔP_max = FL² × (P₁ − FF × Pv)        (no fittings)    (Eq. 4.2a)
ΔP_max = (FLP/Fp)² × (P₁ − FF × Pv)  (with fittings)  (Eq. 4.2b)
```

### 3.3 Required Cv — Non-Choked
```
Cv = (Q / (N₁ × Fp)) × √(Gf / ΔP)   (Eq. 4.4 / 4.5)
```

### 3.4 Required Cv — Choked
```
Cv = (Q / (N₁ × FLP)) × √(Gf / (P₁ − FF × Pv))   (Eq. 4.6 / 4.7)
```

---

## 4. Gas Sizing (IEC 60534-2-1, §5.2)

### 4.1 Specific Heat Ratio Factor
```
Fγ = γ / 1.40         (Eq. 5.1)
```

### 4.2 Expansion Factor
```
Y = 1 − x / (3 × Fγ × xT)    (Eq. 5.4)
Y_min = 2/3  (hard lower limit — choked condition)
```

### 4.3 Required Cv (mass flow)
```
Cv = [W / (N₆ × Fp × Y)] × √[1 / (x × P₁ × ρ₁)]   (Eq. 5.6 / 5.8)
```

---

## 5. Piping Geometry Factors (IEC 60534-2-1, §6)

```
ξ₁ = 0.5 × (1 − (d/D₁)²)²      inlet reducer
ξ₂ = 1.0 × (1 − (d/D₂)²)²      outlet expander
ξ_B1 = 1 − (d/D₁)⁴              Bernoulli, upstream
ξ_B2 = 1 − (d/D₂)⁴              Bernoulli, downstream

Fp  = [1 + (Σξ/N₂)×(Cv/d²)²]^(−1/2)           (Eq. 3.1)
FLP = FL × [1 + FL²×(Σξ₁/N₂)×(Cv/d²)²]^(−1/2) (Eq. 3.2)
xTP = (xT/Fp²) × [1 + (xT×Σξ₁/N₅)×(Cv/d²)²]⁻¹ (Eq. 3.3)
```

---

## 6. Cavitation Analysis (IEC 60534-8-4, §5)

| Regime | Condition | Description |
|---|---|---|
| None | ΔP < 0.25 × ΔP_i | No cavitation |
| Incipient | 0.25 × ΔP_i ≤ ΔP < ΔP_i | Bubble formation onset |
| Constant | ΔP_i ≤ ΔP < ΔP_max | Established cavitation |
| Choked | ΔP ≥ ΔP_max, P₂ > Pv | Supercavitation |
| Flashing | P₂ ≤ Pv | Two-phase exit |

---

## 7. Noise Prediction

### 7.1 Aerodynamic (IEC 60534-8-3)
Chain: `c₁ → rP_crit → U_vc → M_j → η → W_mech → W_a → LWi → TL → Lpe`

### 7.2 Hydrodynamic (IEC 60534-8-4)
```
Lpe = Lpi(regime) − TL + ΔLA(f_p)
```

---

## 8. Validation Constraints

### Hard Constraints (abort sizing)
- P₂ ≥ P₁ → `ERR_PRESSURE_INVERSION`
- Pv ≥ P₁ → `ERR_PV_EXCEEDS_P1`
- Pv ≥ Pc → `ERR_INVALID_PC_PV`
- Q ≤ 0 or W ≤ 0 → `ERR_NONPOSITIVE_FLOW`
- FL ∉ (0.10, 1.00) → `ERR_INVALID_FL`
- xT ∉ (0.12, 0.80) → `ERR_INVALID_XT`
- Non-convergence after 50 iterations → `ERR_CONVERGENCE_FAIL`

### Soft Warnings
`WARN_CHOKED_LIQUID`, `WARN_CHOKED_GAS`, `WARN_CAVITATION_*`, `WARN_FLASHING`,
`WARN_VISCOUS`, `WARN_OVERSIZED`, `WARN_NEAR_CAPACITY`, `WARN_NOISE_LIMIT`,
`WARN_HIGH_VELOCITY`, `WARN_WET_STEAM`, `WARN_PTRATING`