"""
Tests for backend.constants
============================
Verifies that all N-factor values, physical constants, and reference tables
are present, correctly typed, and within expected physical ranges.
"""

from __future__ import annotations

import pytest

from backend.constants import (
    A_WEIGHTING_TABLE, AERO_EFFICIENCY, CV_TO_KV, FR_TABLE,
    GAMMA_AIR, M_AIR, P_ATM_BAR, P_STD_BAR, PIPE_SCHEDULES,
    PT_RATINGS, R_UNIVERSAL, RHO_AIR_STD, RHO_STEEL, RHO_WATER_15C,
    SI_N, T_STD_K, US_N, W_REF,
)


class TestNFactorsSI:
    """N-factor table integrity checks (ISA-75.01.01, Table 1 — SI values)."""

    def test_N1_si_value(self):
        assert SI_N["N1"] == pytest.approx(0.865, rel=1e-3)

    def test_N2_si_value(self):
        assert SI_N["N2"] == pytest.approx(0.00214, rel=1e-3)

    def test_N4_si_value(self):
        assert SI_N["N4"] == pytest.approx(17_300.0, rel=1e-3)

    def test_N5_si_value(self):
        assert SI_N["N5"] == pytest.approx(0.00241, rel=1e-3)

    def test_N6_si_value(self):
        assert SI_N["N6"] == pytest.approx(27.3, rel=1e-3)

    def test_N7_si_value(self):
        assert SI_N["N7"] == pytest.approx(417.0, rel=1e-3)

    def test_all_si_keys_present(self):
        required = {"N1", "N2", "N4", "N5", "N6", "N7", "N8", "N9"}
        assert required.issubset(set(SI_N.keys()))

    def test_all_si_values_positive(self):
        for key, val in SI_N.items():
            assert val > 0, f"SI_N['{key}'] = {val} is not positive."


class TestNFactorsUS:
    """N-factor table integrity checks — US Customary values."""

    def test_N1_us_value(self):
        assert US_N["N1"] == pytest.approx(1.00, rel=1e-3)

    def test_N2_us_value(self):
        assert US_N["N2"] == pytest.approx(890.0, rel=1e-3)

    def test_N4_us_value(self):
        assert US_N["N4"] == pytest.approx(76_000.0, rel=1e-3)

    def test_N6_us_value(self):
        assert US_N["N6"] == pytest.approx(63.3, rel=1e-3)

    def test_N7_us_value(self):
        assert US_N["N7"] == pytest.approx(1_360.0, rel=1e-3)

    def test_all_us_values_positive(self):
        for key, val in US_N.items():
            assert val > 0, f"US_N['{key}'] = {val} is not positive."


class TestNFactorConsistency:
    """
    Verify SI and US N-constants give the same Cv for the same physical case.

    Reference: 1 m³/h = 4.4029 GPM, 1 bar = 14.504 psi.
    Liquid Cv = Q/(N1*sqrt(ΔP/Gf)).
    """

    def test_cv_unit_equivalence(self):
        import math
        # SI
        Q_si   = 100.0       # m³/h
        dP_si  = 2.0         # bar
        Cv_si  = (Q_si / SI_N["N1"]) * math.sqrt(1.0 / dP_si)

        # US (same physical flow)
        Q_us   = Q_si * 4.4029    # GPM
        dP_us  = dP_si * 14.504   # psi
        Cv_us  = (Q_us / US_N["N1"]) * math.sqrt(1.0 / dP_us)

        # Must agree within 0.5%
        assert Cv_si == pytest.approx(Cv_us, rel=0.005)


class TestPhysicalConstants:
    """Physical constant spot checks."""

    def test_universal_gas_constant(self):
        assert R_UNIVERSAL == pytest.approx(8_314.0, rel=1e-3)

    def test_water_density_at_15C(self):
        assert RHO_WATER_15C == pytest.approx(999.1, rel=1e-3)

    def test_standard_pressure(self):
        assert P_STD_BAR == pytest.approx(1.01325, rel=1e-4)

    def test_standard_temperature(self):
        assert T_STD_K == pytest.approx(273.15, rel=1e-4)

    def test_air_molecular_weight(self):
        assert M_AIR == pytest.approx(28.967, rel=1e-3)

    def test_air_std_density(self):
        # Verify: ρ = P*M/(R*T) = 101325*28.967/(8314*273.15) = 1.293 kg/Nm³
        import math
        rho_calc = (P_STD_BAR * 1e5 * M_AIR) / (R_UNIVERSAL * T_STD_K)
        assert rho_calc == pytest.approx(RHO_AIR_STD, rel=0.01)

    def test_gamma_air(self):
        assert GAMMA_AIR == pytest.approx(1.40, rel=1e-4)

    def test_acoustic_reference_power(self):
        assert W_REF == pytest.approx(1.0e-12, rel=1e-6)

    def test_cv_to_kv_conversion(self):
        assert CV_TO_KV == pytest.approx(0.865, rel=1e-3)


class TestFRTable:
    """FR vs Rev interpolation table checks."""

    def test_table_is_monotone(self):
        """Both Rev and FR values must be strictly increasing."""
        revs = [row[0] for row in FR_TABLE]
        frs  = [row[1] for row in FR_TABLE]
        for i in range(len(FR_TABLE) - 1):
            assert revs[i] < revs[i + 1], f"Rev not monotone at index {i}"
            assert frs[i]  < frs[i + 1],  f"FR not monotone at index {i}"

    def test_table_bounds(self):
        assert FR_TABLE[0][1]  >= 0.05   # minimum FR > 0
        assert FR_TABLE[-1][1] == pytest.approx(1.00, rel=1e-4)  # max FR = 1

    def test_table_turbulent_threshold_present(self):
        """Table must contain an entry at Rev = 40,000 (turbulent transition)."""
        revs = [row[0] for row in FR_TABLE]
        assert 40_000.0 in revs


class TestPipeScheduleTable:
    """Pipe schedule reference data integrity checks."""

    def test_key_nps_sizes_present(self):
        for size in ("1", "2", "4", "6", "8", "12"):
            assert size in PIPE_SCHEDULES, f"NPS {size}\" missing from PIPE_SCHEDULES"

    def test_sch40_id_less_than_od(self):
        for nps, data in PIPE_SCHEDULES.items():
            od = data["od_mm"]
            sch40_id = data["schedules"]["SCH40"]["id_mm"]
            assert sch40_id < od, f"NPS {nps}\": SCH40 ID >= OD"

    def test_sch80_thicker_than_sch40(self):
        for nps, data in PIPE_SCHEDULES.items():
            t40 = data["schedules"]["SCH40"]["t_mm"]
            t80 = data["schedules"]["SCH80"]["t_mm"]
            assert t80 > t40, f"NPS {nps}\": SCH80 wall not thicker than SCH40"


class TestAWeightingTable:
    """A-weighting correction table checks."""

    def test_reference_1khz_is_zero(self):
        """A-weighting is defined as 0 dB at 1000 Hz."""
        for freq, da in A_WEIGHTING_TABLE:
            if freq == 1_000.0:
                assert da == pytest.approx(0.0, abs=0.1)
                return
        pytest.fail("1000 Hz not found in A_WEIGHTING_TABLE")

    def test_low_frequencies_negative(self):
        """Sub-500 Hz corrections must be negative (attenuated)."""
        for freq, da in A_WEIGHTING_TABLE:
            if freq < 500.0:
                assert da < 0.0, f"A-weighting at {freq} Hz should be negative"