"""
Tests for backend.viscous_correction
======================================
Validates the ISA-75.01.01 Annex B Reynolds number equation,
the FR interpolation table, and the iterative viscous correction procedure.
"""

from __future__ import annotations

import math

import pytest

from backend.models import ConvergenceError
from backend.viscous_correction import (
    REV_LAMINAR_WARN, REV_TURBULENT, apply_viscous_correction,
    calc_FR, calc_Rev,
)


class TestCalcRev:
    """Equation 8.1: Rev = (N4·Fd·Q)/(ν·√(FL·Cv)) × (FL²·Cv²/(N2·d⁴) + 1)^0.25"""

    def test_water_turbulent_regime(self):
        """
        Q=100 m³/h, ν=1.0 cSt, FL=0.85, Cv=81.75, d=50 mm, Fd=1.0
        Rev expected >> 40,000 → fully turbulent.
        """
        Rev = calc_Rev(100.0, 1.0, 0.85, 81.75, 50.0, 1.0)
        assert Rev > REV_TURBULENT

    def test_viscous_oil_laminar_regime(self):
        """
        Q=10 m³/h, ν=500 cSt (heavy oil), FL=0.85, Cv=20, d=50 mm, Fd=1.0
        Rev expected << 10,000.
        """
        Rev = calc_Rev(10.0, 500.0, 0.85, 20.0, 50.0, 1.0)
        assert Rev < REV_LAMINAR_WARN

    def test_Rev_increases_with_flow(self):
        """Higher flow → higher Rev."""
        Rev1 = calc_Rev(50.0,  1.0, 0.85, 80.0, 50.0, 1.0)
        Rev2 = calc_Rev(100.0, 1.0, 0.85, 80.0, 50.0, 1.0)
        assert Rev2 > Rev1

    def test_Rev_decreases_with_viscosity(self):
        """Higher viscosity → lower Rev."""
        Rev1 = calc_Rev(100.0, 1.0,   0.85, 80.0, 50.0, 1.0)
        Rev2 = calc_Rev(100.0, 100.0, 0.85, 80.0, 50.0, 1.0)
        assert Rev2 < Rev1

    def test_raises_on_zero_viscosity(self):
        with pytest.raises(ValueError, match="viscosity"):
            calc_Rev(100.0, 0.0, 0.85, 80.0, 50.0, 1.0)


class TestCalcFR:
    """FR log-linear interpolation from ISA curve."""

    def test_FR_fully_turbulent(self):
        """Rev ≥ 40,000 → FR = 1.0 exactly."""
        assert calc_FR(40_000.0) == pytest.approx(1.0, rel=1e-6)
        assert calc_FR(100_000.0) == pytest.approx(1.0, rel=1e-6)

    def test_FR_at_known_table_entry(self):
        """At exact table entries, FR must match the table value."""
        from backend.constants import FR_TABLE
        for Rev, FR_expected in FR_TABLE:
            if Rev <= REV_TURBULENT:
                assert calc_FR(Rev) == pytest.approx(FR_expected, rel=1e-4)

    def test_FR_monotone_increasing_with_Rev(self):
        """FR must increase monotonically with Rev."""
        rev_values = [1, 10, 100, 1_000, 10_000, 40_000]
        frs = [calc_FR(r) for r in rev_values]
        for i in range(len(frs) - 1):
            assert frs[i] <= frs[i + 1]

    def test_FR_at_Rev_1000_interpolated(self):
        """Rev=1000 is a table entry; FR should equal 0.730."""
        assert calc_FR(1_000.0) == pytest.approx(0.730, rel=0.01)

    def test_FR_interpolation_between_entries(self):
        """FR at intermediate Rev must be between the bounding table values."""
        FR_300  = calc_FR(300.0)
        FR_1000 = calc_FR(1_000.0)
        FR_mid  = calc_FR(550.0)   # between 300 and 1000
        assert FR_300 < FR_mid < FR_1000

    def test_FR_clamped_at_low_Rev(self):
        """Very low Rev must not return negative FR."""
        assert calc_FR(0.01) >= 0.05

    def test_FR_less_than_one_for_laminar(self):
        assert calc_FR(500.0) < 1.0


class TestApplyViscousCorrection:
    """Iterative correction procedure (Section 8.3)."""

    def test_turbulent_flow_no_correction(self):
        """Water (ν=1 cSt): FR ≈ 1.0, Cv_corrected ≈ Cv_turbulent."""
        Cv_T = 81.75
        Cv_c, Rev, FR = apply_viscous_correction(
            Cv_T, 100.0, 1.0, 0.85, 1.0, 50.0
        )
        assert FR  == pytest.approx(1.0, abs=0.01)
        assert Cv_c == pytest.approx(Cv_T, rel=0.01)

    def test_viscous_flow_increases_cv(self):
        """High viscosity oil: corrected Cv > turbulent Cv."""
        Cv_T = 30.0
        Cv_c, Rev, FR = apply_viscous_correction(
            Cv_T, 30.0, 200.0, 0.85, 1.0, 50.0
        )
        assert Cv_c >= Cv_T

    def test_FR_less_than_one_for_viscous(self):
        """Viscous regime must yield FR < 1."""
        Cv_c, Rev, FR = apply_viscous_correction(
            30.0, 10.0, 500.0, 0.85, 1.0, 50.0
        )
        assert FR < 1.0

    def test_returns_tuple_of_three(self):
        result = apply_viscous_correction(81.75, 100.0, 1.0, 0.85, 1.0, 50.0)
        assert len(result) == 3

    def test_Cv_corrected_equals_CvT_over_FR(self):
        """Cv_corrected must satisfy Cv_corrected = Cv_T / FR at convergence."""
        Cv_T = 30.0
        Cv_c, Rev, FR = apply_viscous_correction(
            Cv_T, 10.0, 100.0, 0.85, 1.0, 50.0
        )
        assert Cv_c == pytest.approx(Cv_T / FR, rel=0.005)