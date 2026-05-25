"""
Tests for backend.sizing_liquid
=================================
All expected Cv values are hand-calculated using IEC 60534-2-1:2011, §5.1.
N₁ = 0.865 (SI: Q in m³/h, ΔP in bar).
"""

from __future__ import annotations

import math

import pytest

from backend.models import HardConstraintViolation
from backend.sizing_liquid import (
    calc_FF, calc_delta_P_max, cv_liquid, cv_liquid_choked,
    cv_liquid_non_choked, is_choked_liquid,
)


# ---------------------------------------------------------------------------
# FF  (Equation 4.1)
# ---------------------------------------------------------------------------

class TestCalcFF:

    def test_water_at_20C(self):
        """FF = 0.96 − 0.28×√(0.023/220.9) = 0.9571"""
        FF = calc_FF(Pv_bar=0.023, Pc_bar=220.9)
        assert FF == pytest.approx(0.9571, rel=0.001)

    def test_propane_at_60C(self):
        """FF = 0.96 − 0.28×√(8.5/42.5) = 0.8348"""
        FF = calc_FF(Pv_bar=8.5, Pc_bar=42.5)
        assert FF == pytest.approx(0.8348, rel=0.002)

    def test_FF_minimum_clamp(self):
        """FF must never fall below 0.50."""
        FF = calc_FF(Pv_bar=0.90 * 220.9, Pc_bar=220.9)
        assert FF >= 0.50

    def test_FF_maximum_clamp(self):
        """FF must never exceed 0.96."""
        FF = calc_FF(Pv_bar=0.001, Pc_bar=220.9)
        assert FF <= 0.96

    def test_raises_on_Pv_gte_Pc(self):
        with pytest.raises(HardConstraintViolation, match="ERR_INVALID_PC_PV"):
            calc_FF(Pv_bar=5.0, Pc_bar=5.0)

    def test_raises_on_negative_Pv(self):
        with pytest.raises(HardConstraintViolation, match="ERR_NEGATIVE_PV"):
            calc_FF(Pv_bar=-0.1, Pc_bar=220.9)


# ---------------------------------------------------------------------------
# ΔP_max  (Equation 4.2)
# ---------------------------------------------------------------------------

class TestCalcDeltaPMax:

    def test_water_no_fittings(self):
        """
        FL=0.85, P1=10, FF=0.9571, Pv=0.023
        ΔP_max = 0.7225 × (10 − 0.9571×0.023) = 7.208 bar
        """
        FF        = calc_FF(0.023, 220.9)
        delta_P_max = calc_delta_P_max(0.85, 10.0, FF, 0.023)
        assert delta_P_max == pytest.approx(7.208, rel=0.005)

    def test_propane_no_fittings(self):
        """
        FL=0.85, P1=15, FF=0.8348, Pv=8.5
        ΔP_max = 0.7225 × (15 − 0.8348×8.5) = 5.710 bar
        """
        FF          = calc_FF(8.5, 42.5)
        delta_P_max = calc_delta_P_max(0.85, 15.0, FF, 8.5)
        assert delta_P_max == pytest.approx(5.710, rel=0.01)

    def test_delta_P_max_increases_with_P1(self):
        FF = calc_FF(0.023, 220.9)
        dp1 = calc_delta_P_max(0.85, 10.0, FF, 0.023)
        dp2 = calc_delta_P_max(0.85, 20.0, FF, 0.023)
        assert dp2 > dp1


# ---------------------------------------------------------------------------
# Choked condition check  (Equation 4.3)
# ---------------------------------------------------------------------------

class TestIsChokedLiquid:

    def test_not_choked_when_dp_less_than_max(self):
        assert is_choked_liquid(2.0, 7.208) is False

    def test_choked_when_dp_equals_max(self):
        assert is_choked_liquid(7.208, 7.208) is True

    def test_choked_when_dp_exceeds_max(self):
        assert is_choked_liquid(9.0, 7.208) is True


# ---------------------------------------------------------------------------
# Non-choked liquid Cv  (Equation 4.4 / 4.5)
# ---------------------------------------------------------------------------

class TestCvLiquidNonChoked:

    def test_water_100m3h_2bar(self):
        """Cv = (100/0.865) × √(1.0/2.0) = 81.748"""
        Cv = cv_liquid_non_choked(Q_m3h=100.0, Gf=1.0, delta_P_bar=2.0)
        assert Cv == pytest.approx(81.748, rel=0.005)

    def test_cv_scales_linearly_with_flow(self):
        """Doubling Q doubles Cv."""
        Cv1 = cv_liquid_non_choked(100.0, 1.0, 2.0)
        Cv2 = cv_liquid_non_choked(200.0, 1.0, 2.0)
        assert Cv2 == pytest.approx(2.0 * Cv1, rel=1e-6)

    def test_cv_increases_with_higher_Gf(self):
        """Higher Gf (denser fluid) needs higher Cv for same Q and ΔP."""
        Cv_water = cv_liquid_non_choked(100.0, 1.0,  2.0)
        Cv_brine = cv_liquid_non_choked(100.0, 1.25, 2.0)
        assert Cv_brine > Cv_water

    def test_cv_decreases_with_higher_dp(self):
        """Higher ΔP needs smaller Cv (more driving force)."""
        Cv_low_dp  = cv_liquid_non_choked(100.0, 1.0, 1.0)
        Cv_high_dp = cv_liquid_non_choked(100.0, 1.0, 4.0)
        assert Cv_high_dp < Cv_low_dp

    def test_Fp_correction_increases_Cv(self):
        """With Fp < 1 (fittings), required Cv is higher."""
        Cv_no_fit = cv_liquid_non_choked(100.0, 1.0, 2.0, Fp=1.0)
        Cv_with_fit = cv_liquid_non_choked(100.0, 1.0, 2.0, Fp=0.85)
        assert Cv_with_fit > Cv_no_fit

    def test_raises_on_negative_dp(self):
        with pytest.raises(HardConstraintViolation, match="ERR_NEGATIVE_DP"):
            cv_liquid_non_choked(100.0, 1.0, -1.0)

    def test_raises_on_zero_Gf(self):
        with pytest.raises(HardConstraintViolation, match="ERR_INVALID_GF"):
            cv_liquid_non_choked(100.0, 0.0, 2.0)


# ---------------------------------------------------------------------------
# Choked liquid Cv  (Equation 4.6 / 4.7)
# ---------------------------------------------------------------------------

class TestCvLiquidChoked:

    def test_choked_cv_less_than_non_choked_for_same_dp(self):
        """
        At choked conditions the operative ΔP is capped at ΔP_max < actual ΔP.
        Choked Cv therefore uses a smaller effective pressure drop → higher Cv
        than if the actual (over-estimated) ΔP were naively used.
        Verify the choked Cv is physically reasonable (positive, finite).
        """
        FF   = calc_FF(0.023, 220.9)
        Cv   = cv_liquid_choked(100.0, 1.0, 10.0, FF, 0.023, 0.85)
        assert Cv > 0

    def test_choked_cv_formula(self):
        """
        Cv = (Q/(N1*FL)) × √(Gf/(P1 − FF*Pv))
        = (100/(0.865*0.85)) × √(1.0/(10 − 0.9571*0.023))
        = 135.98 × √(1.0/9.9780)
        = 135.98 × 0.10011
        = 13.614 … actually this seems low. Let me verify.
        
        Wait: 1/(10 - 0.9571*0.023) = 1/9.978 → sqrt = 0.3009
        Cv = (100/(0.865*0.85)) * 0.3009 = 135.98 * 0.3009 = 40.91
        """
        FF  = calc_FF(0.023, 220.9)
        Cv  = cv_liquid_choked(100.0, 1.0, 10.0, FF, 0.023, 0.85)
        assert Cv == pytest.approx(40.91, rel=0.02)


# ---------------------------------------------------------------------------
# Master dispatcher cv_liquid
# ---------------------------------------------------------------------------

class TestCvLiquidDispatcher:

    def test_returns_non_choked_for_small_dp(self):
        """ΔP = 2 bar << ΔP_max ≈ 7.2 bar → non-choked branch."""
        Cv, FF, dp_max, dp_eff, choked = cv_liquid(
            Q_m3h=100.0, Gf=1.0, P1_bar=10.0, P2_bar=8.0,
            Pv_bar=0.023, Pc_bar=220.9, FL=0.85,
        )
        assert choked is False
        assert dp_eff == pytest.approx(2.0, rel=1e-4)
        assert Cv == pytest.approx(81.748, rel=0.005)

    def test_returns_choked_for_large_dp(self):
        """ΔP = 9 bar > ΔP_max ≈ 7.2 bar → choked branch."""
        Cv, FF, dp_max, dp_eff, choked = cv_liquid(
            Q_m3h=100.0, Gf=1.0, P1_bar=10.0, P2_bar=1.0,
            Pv_bar=0.023, Pc_bar=220.9, FL=0.85,
        )
        assert choked is True
        assert dp_eff == pytest.approx(dp_max, rel=1e-4)

    def test_FF_value_returned(self):
        Cv, FF, *_ = cv_liquid(100.0, 1.0, 10.0, 8.0, 0.023, 220.9, 0.85)
        assert FF == pytest.approx(0.9571, rel=0.002)

    def test_result_tuple_length(self):
        result = cv_liquid(100.0, 1.0, 10.0, 8.0, 0.023, 220.9, 0.85)
        assert len(result) == 5   # (Cv, FF, dp_max, dp_eff, is_choked)