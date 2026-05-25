"""
Tests for backend.sizing_gas
==============================
All expected values are hand-calculated from IEC 60534-2-1:2011, §5.2.
N₆ = 27.3 (SI: W in kg/h, P in bar, ρ in kg/m³).
"""

from __future__ import annotations

import math

import pytest

from backend.fluid_properties import gas_density
from backend.models import HardConstraintViolation
from backend.sizing_gas import (
    Y_MIN, calc_Fgamma, calc_Y, calc_x, cv_gas, cv_gas_mass, is_choked_gas,
)


# ---------------------------------------------------------------------------
# Fγ  (Equation 5.1)
# ---------------------------------------------------------------------------

class TestCalcFgamma:

    def test_air_fgamma_is_unity(self):
        """Air: γ = 1.40 → Fγ = 1.40/1.40 = 1.000"""
        assert calc_Fgamma(1.40) == pytest.approx(1.000, rel=1e-6)

    def test_methane_fgamma(self):
        """Methane: γ = 1.31 → Fγ = 1.31/1.40 = 0.9357"""
        assert calc_Fgamma(1.31) == pytest.approx(0.9357, rel=0.005)

    def test_hydrogen_fgamma(self):
        """Hydrogen: γ = 1.41 → Fγ = 1.41/1.40 = 1.007"""
        assert calc_Fgamma(1.41) == pytest.approx(1.007, rel=0.005)

    def test_fgamma_upper_clamp(self):
        assert calc_Fgamma(2.0) <= 1.30

    def test_fgamma_lower_clamp(self):
        assert calc_Fgamma(1.01) >= 0.50


# ---------------------------------------------------------------------------
# x  (Equation 5.2)
# ---------------------------------------------------------------------------

class TestCalcX:

    def test_x_formula(self):
        """x = (P1 − P2) / P1 = (5 − 3) / 5 = 0.400"""
        assert calc_x(5.0, 3.0) == pytest.approx(0.400, rel=1e-6)

    def test_x_range_zero_to_one(self):
        x = calc_x(10.0, 1.0)
        assert 0.0 < x < 1.0

    def test_raises_on_pressure_inversion(self):
        with pytest.raises(HardConstraintViolation, match="ERR_PRESSURE_INVERSION"):
            calc_x(5.0, 8.0)


# ---------------------------------------------------------------------------
# Choked gas condition  (Equation 5.3)
# ---------------------------------------------------------------------------

class TestIsChokedGas:

    def test_not_choked(self):
        """x = 0.40 < Fγ·xT = 0.60 → not choked"""
        assert is_choked_gas(0.40, 1.00, 0.60) is False

    def test_choked_at_boundary(self):
        """x = Fγ·xT → choked"""
        assert is_choked_gas(0.60, 1.00, 0.60) is True

    def test_choked_above_boundary(self):
        assert is_choked_gas(0.90, 1.00, 0.60) is True


# ---------------------------------------------------------------------------
# Y  (Equation 5.4)
# ---------------------------------------------------------------------------

class TestCalcY:

    def test_subcritical_Y_formula(self):
        """
        x = 0.40, Fγ = 1.00, xT = 0.60
        Y = 1 − 0.40/(3×1.00×0.60) = 1 − 0.2222 = 0.7778
        """
        Y, x_eff, choked = calc_Y(0.40, 1.00, 0.60)
        assert Y      == pytest.approx(0.7778, rel=0.001)
        assert x_eff  == pytest.approx(0.40,   rel=1e-6)
        assert choked is False

    def test_choked_Y_is_two_thirds(self):
        """When choked, Y must equal 2/3 exactly."""
        Y, x_eff, choked = calc_Y(0.90, 1.00, 0.60)
        assert Y      == pytest.approx(2.0 / 3.0, rel=1e-6)
        assert x_eff  == pytest.approx(0.60, rel=1e-6)   # capped
        assert choked is True

    def test_Y_never_below_two_thirds(self):
        for x in [0.5, 0.7, 0.9, 0.99]:
            Y, _, _ = calc_Y(x, 1.00, 0.60)
            assert Y >= Y_MIN - 1e-9

    def test_Y_at_zero_x_is_unity(self):
        """At x → 0 (ΔP → 0), Y → 1.0 (no expansion correction)."""
        Y, _, _ = calc_Y(0.001, 1.00, 0.60)
        assert Y == pytest.approx(1.0, rel=0.01)


# ---------------------------------------------------------------------------
# Gas Cv — mass flow  (Equation 5.6)
# ---------------------------------------------------------------------------

class TestCvGasMass:

    def test_air_subcritical(self):
        """
        W=500 kg/h, P1=5 bar, ρ1=5.814 kg/m³, Y=0.7778, x=0.40
        Cv = [500/(27.3×0.7778)] × √[1/(0.40×5×5.814)]
           = [500/21.23] × √[1/11.628]
           = 23.55 × 0.2932
           = 6.905
        """
        rho1 = gas_density(5.0, 300.0, 28.97, 1.0)
        Y, x_eff, _ = calc_Y(0.40, 1.00, 0.60)
        Cv   = cv_gas_mass(500.0, 5.0, rho1, Y, x_eff)
        assert Cv == pytest.approx(6.905, rel=0.03)

    def test_cv_scales_linearly_with_mass_flow(self):
        rho1 = gas_density(5.0, 300.0, 28.97, 1.0)
        Y, x_eff, _ = calc_Y(0.40, 1.00, 0.60)
        Cv1 = cv_gas_mass(500.0, 5.0, rho1, Y, x_eff)
        Cv2 = cv_gas_mass(1000.0, 5.0, rho1, Y, x_eff)
        assert Cv2 == pytest.approx(2.0 * Cv1, rel=1e-6)

    def test_Fp_correction(self):
        rho1 = gas_density(5.0, 300.0, 28.97, 1.0)
        Y, x_eff, _ = calc_Y(0.40, 1.00, 0.60)
        Cv_no  = cv_gas_mass(500.0, 5.0, rho1, Y, x_eff, Fp=1.0)
        Cv_fit = cv_gas_mass(500.0, 5.0, rho1, Y, x_eff, Fp=0.9)
        assert Cv_fit > Cv_no


# ---------------------------------------------------------------------------
# Master gas dispatcher
# ---------------------------------------------------------------------------

class TestCvGasDispatcher:

    def test_subcritical_returns_correct_flags(self):
        rho1 = gas_density(5.0, 300.0, 28.97, 1.0)
        Cv, Fgamma, x, Y, choked = cv_gas(500.0, 5.0, 3.0, rho1, 1.40, 0.60)
        assert choked  is False
        assert x       == pytest.approx(0.40, rel=1e-4)
        assert Fgamma  == pytest.approx(1.00, rel=1e-4)
        assert Y       == pytest.approx(0.778, rel=0.005)
        assert Cv      == pytest.approx(6.905, rel=0.03)

    def test_choked_returns_Y_two_thirds(self):
        rho1 = gas_density(5.0, 300.0, 28.97, 1.0)
        Cv, _, _, Y, choked = cv_gas(500.0, 5.0, 0.5, rho1, 1.40, 0.60)
        assert choked is True
        assert Y      == pytest.approx(2.0 / 3.0, rel=1e-6)

    def test_result_tuple_length(self):
        rho1   = gas_density(5.0, 300.0, 28.97, 1.0)
        result = cv_gas(500.0, 5.0, 3.0, rho1, 1.40, 0.60)
        assert len(result) == 5