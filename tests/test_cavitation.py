"""
Tests for backend.cavitation
==============================
Verifies the 5-tier cavitation severity classification (IEC 60534-8-4:2015, §5)
and all intermediate cavitation analysis parameters.
"""

from __future__ import annotations

import math

import pytest

from backend.cavitation import (
    analyse_cavitation, calc_delta_P_eff, calc_delta_P_incipient,
    calc_sigma, calc_vena_contracta_pressure, classify_cavitation_regime,
)
from backend.models import CavitationRegime


# Parameters shared across tests
_P1    = 15.0   # bar abs
_Pv    = 8.5    # bar abs  (propane at 60°C)
_Pc    = 42.5   # bar abs
_FL    = 0.85


class TestVenaContractaPressure:
    """Equation 7.1: P_vc = P1 − ΔP/FL²"""

    def test_formula(self):
        """P_vc = 15 − 5/0.7225 = 15 − 6.920 = 8.080 bar"""
        P_vc = calc_vena_contracta_pressure(15.0, 5.0, 0.85)
        assert P_vc == pytest.approx(8.080, rel=0.005)

    def test_P_vc_below_P1(self):
        assert calc_vena_contracta_pressure(10.0, 2.0, 0.85) < 10.0

    def test_P_vc_increases_with_FL(self):
        """Higher FL (lower vena contracta drop) → higher P_vc."""
        P_vc_lo = calc_vena_contracta_pressure(10.0, 3.0, 0.70)
        P_vc_hi = calc_vena_contracta_pressure(10.0, 3.0, 0.95)
        assert P_vc_hi > P_vc_lo


class TestDeltaPIncipient:
    """Equation 7.2: ΔP_i = FL² × (P1 − Pv)"""

    def test_propane_case(self):
        """ΔP_i = 0.7225 × (15 − 8.5) = 0.7225 × 6.5 = 4.696 bar"""
        dPi = calc_delta_P_incipient(0.85, 15.0, 8.5)
        assert dPi == pytest.approx(4.696, rel=0.005)

    def test_water_case(self):
        """ΔP_i = 0.7225 × (10 − 0.023) = 7.208 bar"""
        dPi = calc_delta_P_incipient(0.85, 10.0, 0.023)
        assert dPi == pytest.approx(7.208, rel=0.005)

    def test_incipient_dp_increases_with_P1(self):
        dPi1 = calc_delta_P_incipient(0.85, 10.0, 0.023)
        dPi2 = calc_delta_P_incipient(0.85, 20.0, 0.023)
        assert dPi2 > dPi1


class TestSigma:
    """Equation 7.3: σ = (P1 − Pv) / ΔP"""

    def test_formula(self):
        """σ = (15 − 8.5) / 5 = 6.5/5 = 1.30"""
        sigma = calc_sigma(15.0, 8.5, 5.0)
        assert sigma == pytest.approx(1.30, rel=1e-4)

    def test_sigma_infinite_at_zero_dp(self):
        assert calc_sigma(10.0, 0.023, 0.0) == float("inf")

    def test_sigma_decreases_with_increasing_dp(self):
        s1 = calc_sigma(10.0, 0.023, 2.0)
        s2 = calc_sigma(10.0, 0.023, 5.0)
        assert s2 < s1


class TestClassifyCavitationRegime:
    """Five-tier regime classification (IEC 60534-8-4, §5)."""

    def test_regime_none_small_dp(self):
        """ΔP = 1 bar << ΔP_c = 0.25×ΔP_i = 0.25×4.696 = 1.174 bar → NONE"""
        regime = classify_cavitation_regime(_P1, _P1 - 1.0, _Pv, _Pc, _FL, 1.0)
        assert regime == CavitationRegime.NONE

    def test_regime_incipient(self):
        """ΔP = 2 bar; ΔP_c=1.174 ≤ 2.0 < ΔP_i=4.696 → INCIPIENT"""
        regime = classify_cavitation_regime(_P1, _P1 - 2.0, _Pv, _Pc, _FL, 2.0)
        assert regime == CavitationRegime.INCIPIENT

    def test_regime_constant_cavitation(self):
        """ΔP = 5 bar; ΔP_i=4.696 ≤ 5 < ΔP_max=5.710 → CONSTANT"""
        regime = classify_cavitation_regime(_P1, _P1 - 5.0, _Pv, _Pc, _FL, 5.0)
        assert regime == CavitationRegime.CONSTANT

    def test_regime_choked(self):
        """ΔP = 6 bar > ΔP_max = 5.710; P2 > Pv → CHOKED"""
        P2 = _P1 - 6.0   # = 9.0 bar > Pv=8.5
        regime = classify_cavitation_regime(_P1, P2, _Pv, _Pc, _FL, 6.0)
        assert regime == CavitationRegime.CHOKED

    def test_regime_flashing(self):
        """P2 = 8.0 bar < Pv = 8.5 bar → FLASHING (overrides everything)"""
        P2 = 8.0   # < Pv = 8.5
        regime = classify_cavitation_regime(_P1, P2, _Pv, _Pc, _FL, _P1 - P2)
        assert regime == CavitationRegime.FLASHING

    def test_water_no_cavitation(self):
        """Water at ΔP = 2 bar; ΔP_i = 7.2 bar → NONE"""
        regime = classify_cavitation_regime(10.0, 8.0, 0.023, 220.9, 0.85, 2.0)
        assert regime == CavitationRegime.NONE


class TestDeltaPEff:
    """Equation 7.5: ΔP_eff = min(ΔP, ΔP_max)"""

    def test_non_choked_returns_actual_dp(self):
        assert calc_delta_P_eff(2.0, 7.0) == pytest.approx(2.0, rel=1e-6)

    def test_choked_caps_at_max(self):
        assert calc_delta_P_eff(9.0, 7.0) == pytest.approx(7.0, rel=1e-6)

    def test_at_boundary(self):
        assert calc_delta_P_eff(7.0, 7.0) == pytest.approx(7.0, rel=1e-6)


class TestAnalyseCavitation:
    """Integration test for the full cavitation analysis function."""

    def test_returns_CavitationResult_model(self):
        from backend.models import CavitationResult
        result = analyse_cavitation(10.0, 8.0, 0.023, 220.9, 0.85)
        assert isinstance(result, CavitationResult)

    def test_no_cavitation_water_small_dp(self):
        result = analyse_cavitation(10.0, 8.0, 0.023, 220.9, 0.85)
        assert result.regime    == CavitationRegime.NONE
        assert result.is_choked is False
        assert result.is_flashing is False

    def test_flashing_propane(self):
        """P2 = 8.0 < Pv = 8.5 → FLASHING"""
        result = analyse_cavitation(15.0, 8.0, 8.5, 42.5, 0.85)
        assert result.regime      == CavitationRegime.FLASHING
        assert result.is_flashing is True
        assert result.is_choked   is True

    def test_sigma_field_positive(self):
        result = analyse_cavitation(10.0, 8.0, 0.023, 220.9, 0.85)
        assert result.sigma > 0.0

    def test_FF_field_within_bounds(self):
        result = analyse_cavitation(10.0, 8.0, 0.023, 220.9, 0.85)
        assert 0.5 <= result.FF <= 0.96

    def test_delta_P_max_positive(self):
        result = analyse_cavitation(10.0, 8.0, 0.023, 220.9, 0.85)
        assert result.delta_P_max > 0.0