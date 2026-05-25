"""
Engineering constants, N-factors, and reference data tables.
=============================================================
All values are sourced from:
  - ISA-75.01.01-2012, Table 1  (N-factors, SI and US)
  - ASME B36.10M-2018           (Pipe dimensions)
  - IEC 60534-8-3:2011, Annex A (Acoustic efficiency)
  - IEC 60534-8-4:2015, Annex A (A-weighting)
  - ASME B16.34-2017, Table 2   (P-T ratings)

This module contains ONLY data. Zero functions. Zero logic.
Import via:  from backend.constants import SI_N, PIPE_SCHEDULES, FR_TABLE
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# N-FACTOR TABLES  (ISA-75.01.01, Table 1)
# ---------------------------------------------------------------------------
# Internal computation uses SI exclusively.
# US constants are provided for reference and unit-conversion validation only.

SI_N: dict[str, float] = {
    # Liquid volumetric Cv  |  Q [m³/h],  ΔP [bar],  Gf [—]
    "N1": 0.865,
    # Piping geometry (Fp, FLP)  |  d, D [mm],  Cv [—]
    "N2": 0.00214,
    # Valve Reynolds number  |  Q [m³/h],  ν [cSt],  d [mm]
    "N4": 17_300.0,
    # xTP combined factor  |  d [mm]
    "N5": 0.00241,
    # Gas/steam mass-flow Cv  |  W [kg/h],  P [bar],  ρ [kg/m³]
    "N6": 27.3,
    # Gas volumetric Cv (std conditions: 0 °C, 101.325 kPa)
    # Q [Nm³/h], P [bar], T [K], M [kg/kmol] → Gg = M/28.967
    "N7": 417.0,
    # Steam specific-volume Cv  |  W [kg/h], P [bar], v [m³/kg]
    "N8": 0.948,
    # Gas volumetric Cv alt std (15 °C, 101.325 kPa)  |  same units as N7
    "N9": 22_500.0,
}

US_N: dict[str, float] = {
    # Liquid volumetric Cv  |  Q [US gal/min],  ΔP [psi],  Gf [—]
    "N1": 1.00,
    # Piping geometry  |  d, D [in]
    "N2": 890.0,
    # Valve Reynolds number  |  Q [US gal/min],  ν [cSt],  d [in]
    "N4": 76_000.0,
    # xTP combined factor  |  d [in]
    "N5": 1_000.0,
    # Gas/steam mass-flow Cv  |  W [lb/h],  P [psia],  ρ [lb/ft³]
    "N6": 63.3,
    # Gas volumetric Cv  |  Q [SCFH],  P [psia],  T [°R],  M [lb/lb-mol]
    "N7": 1_360.0,
    # Steam  |  W [lb/h],  P [psia],  v [ft³/lb]
    "N8": 19.3,
    "N9": 7_320.0,
}

# ---------------------------------------------------------------------------
# PHYSICAL CONSTANTS
# ---------------------------------------------------------------------------
R_UNIVERSAL: float = 8_314.0      # J / (kmol · K)  — universal gas constant
RHO_WATER_15C: float = 999.1      # kg / m³         — ref density for Gf (15 °C)
RHO_AIR_STD: float = 1.293        # kg / Nm³        — air at 0 °C, 101.325 kPa
M_AIR: float = 28.967             # kg / kmol        — molecular weight of air
P_STD_BAR: float = 1.01325        # bar              — standard pressure
T_STD_K: float = 273.15           # K                — standard temperature (0 °C)
P_ATM_BAR: float = 1.01325        # bar              — atmospheric pressure
GAMMA_AIR: float = 1.40           # —                — isentropic exponent reference
W_REF: float = 1.0e-12            # W                — acoustic power reference
RHO_STEEL: float = 7_800.0        # kg / m³          — carbon steel pipe wall density
CV_TO_KV: float = 0.8650          # Kv = CV_TO_KV × Cv

# ---------------------------------------------------------------------------
# FR vs Rev INTERPOLATION TABLE  (ISA-75.01.01, Annex B)
# Log-linear interpolation; x-axis = log10(Rev), y-axis = FR
# ---------------------------------------------------------------------------
FR_TABLE: list[tuple[float, float]] = [
    (1.0,       0.100),
    (3.0,       0.150),
    (10.0,      0.220),
    (30.0,      0.310),
    (100.0,     0.450),
    (300.0,     0.590),
    (1_000.0,   0.730),
    (3_000.0,   0.870),
    (10_000.0,  0.980),
    (40_000.0,  1.000),
]

# ---------------------------------------------------------------------------
# A-WEIGHTING CORRECTION TABLE  (IEC 61672-1)
# Standard octave-band A-weighting network values.
# Interpolation: log-linear on frequency axis.
# ---------------------------------------------------------------------------
A_WEIGHTING_TABLE: list[tuple[float, float]] = [
    (31.5,    -39.4),
    (63.0,    -26.2),
    (125.0,   -16.1),
    (250.0,    -8.6),
    (500.0,    -3.2),
    (1_000.0,   0.0),
    (2_000.0,   1.2),
    (4_000.0,   1.0),
    (8_000.0,  -1.1),
    (16_000.0, -6.6),
]

# ---------------------------------------------------------------------------
# ACOUSTIC EFFICIENCY CONSTANTS  (IEC 60534-8-3, Annex A — representative)
# Key: Fd value (rounded to nearest entry)
# Value: (Ceta_subsonic, n_exponent, Ceta_choked)
# ---------------------------------------------------------------------------
AERO_EFFICIENCY: dict[str, tuple[float, float, float]] = {
    "globe_single":   (1.0e-4, 3.6, 1.0e-3),   # Fd ≈ 1.0
    "globe_cage":     (2.0e-5, 3.6, 2.0e-4),   # Fd ≈ 0.3
    "ball_v_port":    (5.0e-5, 3.6, 5.0e-4),   # Fd ≈ 0.5
    "butterfly":      (5.0e-5, 3.6, 5.0e-4),   # Fd ≈ 0.5
    "eccentric_rotary": (3.0e-5, 3.6, 3.0e-4), # Fd ≈ 0.4
}

# ---------------------------------------------------------------------------
# PIPE SCHEDULE TABLE  (ASME B36.10M-2018 — key NPS sizes)
# Structure: NPS_str → {od_mm, dn_mm, schedules: {sch_str: {id_mm, t_mm}}}
# ---------------------------------------------------------------------------
PIPE_SCHEDULES: dict[str, dict] = {
    "0.5":  {"dn_mm": 15,  "od_mm": 21.3,  "schedules": {
        "SCH40": {"t_mm": 2.77, "id_mm": 15.76},
        "SCH80": {"t_mm": 3.73, "id_mm": 13.84}}},
    "0.75": {"dn_mm": 20,  "od_mm": 26.7,  "schedules": {
        "SCH40": {"t_mm": 2.87, "id_mm": 20.96},
        "SCH80": {"t_mm": 3.91, "id_mm": 18.88}}},
    "1":    {"dn_mm": 25,  "od_mm": 33.4,  "schedules": {
        "SCH40": {"t_mm": 3.38, "id_mm": 26.64},
        "SCH80": {"t_mm": 4.55, "id_mm": 24.30}}},
    "1.5":  {"dn_mm": 40,  "od_mm": 48.3,  "schedules": {
        "SCH40": {"t_mm": 3.68, "id_mm": 40.94},
        "SCH80": {"t_mm": 5.08, "id_mm": 38.14}}},
    "2":    {"dn_mm": 50,  "od_mm": 60.3,  "schedules": {
        "SCH40": {"t_mm": 3.91, "id_mm": 52.48},
        "SCH80": {"t_mm": 5.54, "id_mm": 49.22}}},
    "3":    {"dn_mm": 80,  "od_mm": 88.9,  "schedules": {
        "SCH40": {"t_mm": 5.49, "id_mm": 77.92},
        "SCH80": {"t_mm": 7.62, "id_mm": 73.66}}},
    "4":    {"dn_mm": 100, "od_mm": 114.3, "schedules": {
        "SCH40": {"t_mm": 6.02, "id_mm": 102.26},
        "SCH80": {"t_mm": 8.56, "id_mm": 97.18}}},
    "6":    {"dn_mm": 150, "od_mm": 168.3, "schedules": {
        "SCH40": {"t_mm": 7.11, "id_mm": 154.08},
        "SCH80": {"t_mm": 10.97,"id_mm": 146.36}}},
    "8":    {"dn_mm": 200, "od_mm": 219.1, "schedules": {
        "SCH40": {"t_mm": 8.18, "id_mm": 202.74},
        "SCH80": {"t_mm": 12.70,"id_mm": 193.70}}},
    "10":   {"dn_mm": 250, "od_mm": 273.1, "schedules": {
        "SCH40": {"t_mm": 9.27, "id_mm": 254.56},
        "SCH80": {"t_mm": 15.09,"id_mm": 242.92}}},
    "12":   {"dn_mm": 300, "od_mm": 323.9, "schedules": {
        "SCH40": {"t_mm": 9.53, "id_mm": 304.84},
        "SCH80": {"t_mm": 17.48,"id_mm": 288.94}}},
    "16":   {"dn_mm": 400, "od_mm": 406.4, "schedules": {
        "SCH40": {"t_mm": 9.53, "id_mm": 387.34},
        "SCH80": {"t_mm": 16.66,"id_mm": 373.08}}},
    "20":   {"dn_mm": 500, "od_mm": 508.0, "schedules": {
        "SCH40": {"t_mm": 9.53, "id_mm": 488.94},
        "SCH80": {"t_mm": 19.05,"id_mm": 469.90}}},
    "24":   {"dn_mm": 600, "od_mm": 609.6, "schedules": {
        "SCH40": {"t_mm": 9.53, "id_mm": 590.54},
        "SCH80": {"t_mm": 22.23,"id_mm": 565.14}}},
}

# ---------------------------------------------------------------------------
# ASME B16.34-2017  P-T RATINGS  (Carbon steel A105, bar absolute)
# Structure: pressure_class → list of (T_max_°C, P_max_bar)
# Linear interpolation between temperature breakpoints.
# ---------------------------------------------------------------------------
PT_RATINGS: dict[str, list[tuple[float, float]]] = {
    "Class150":  [(-29, 19.6), (38, 19.6), (100, 17.7), (150, 15.8),
                  (200, 13.8), (250, 12.1), (300, 10.2), (371, 9.3)],
    "Class300":  [(-29, 51.1), (38, 51.1), (100, 46.6), (150, 41.4),
                  (200, 38.6), (250, 34.3), (300, 31.6), (371, 26.8)],
    "Class600":  [(-29, 102.1),(38, 102.1),(100, 93.2), (150, 82.7),
                  (200, 77.2), (250, 68.9), (300, 63.4), (371, 53.7)],
    "Class900":  [(-29, 153.2),(38, 153.2),(100, 139.8),(150, 124.1),
                  (200, 115.8),(250, 103.4),(300, 95.1), (371, 80.5)],
    "Class1500": [(-29, 255.3),(38, 255.3),(100, 233.0),(150, 206.8),
                  (200, 193.0),(250, 172.3),(300, 158.6),(371, 134.2)],
    "Class2500": [(-29, 425.5),(38, 425.5),(100, 388.3),(150, 344.7),
                  (200, 321.6),(250, 287.2),(300, 264.4),(371, 223.7)],
}

# ---------------------------------------------------------------------------
# VELOCITY WARNING THRESHOLDS  [m/s]  (API RP 553, Section 6)
# ---------------------------------------------------------------------------
VELOCITY_LIMITS: dict[str, dict[str, float]] = {
    "liquid_clean":   {"warn": 3.0, "reject": 5.0},
    "liquid_erosive": {"warn": 1.0, "reject": 2.0},
    "gas_general":    {"warn": 0.3, "reject": 0.5},   # as fraction of Mach
    "steam":          {"warn": 50.0, "reject": 80.0},
}

# ---------------------------------------------------------------------------
# SIZING MARGIN DEFAULTS  (API RP 553, Section 4)
# ---------------------------------------------------------------------------
SIZING_MARGINS: dict[str, float] = {
    "liquid_clean":  0.20,  # +20 %
    "liquid_flash":  0.30,  # +30 %
    "gas":           0.20,
    "steam":         0.25,
}
NOISE_LIMIT_DBA: float = 85.0    # regulatory / industry default SPL limit