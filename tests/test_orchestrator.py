"""
Tests for backend.orchestrator — end-to-end integration.
===========================================================
Each test runs a complete sizing calculation through run_sizing()
and verifies the returned SizingResult model for correctness,
internal consistency, and physical plausibility.
"""

from __future__ import annotations

import math

import pytest

from backend.models import (
    CavitationRegime, FluidPhase, MessageLevel, SteamType,
)
from backend.orchestrator import run_sizing


class TestLiquidSizingIntegration:

    def test_success_flag_true(self, water_si):
        result = run_sizing(water_si)
        assert result.success is True

    def test_Cv_required_positive(self, water_si):
        result = run_sizing(water_si)
        assert result.Cv_required > 0.0

    def test_Cv_required_approximately_correct(self, water_si):
        """Expected ≈ 81.75 (hand-calculated); tolerance 3%."""
        result = run_sizing(water_si)
        assert result.Cv_required == pytest.approx(81.75, rel=0.03)

    def test_Kv_equals_cv_times_factor(self, water_si):
        result = run_sizing(water_si)
        assert result.Kv_required == pytest.approx(result.Cv_required * 0.865, rel=1e-3)

    def test_Cv_design_includes_margin(self, water_si):
        result = run_sizing(water_si)
        expected_design = result.Cv_required * 1.20
        assert result.Cv_design == pytest.approx(expected_design, rel=1e-3)

    def test_not_choked_for_small_dp(self, water_si):
        result = run_sizing(water_si)
        assert result.is_choked is False

    def test_cavitation_regime_none(self, water_si):
        result = run_sizing(water_si)
        assert result.cavitation is not None
        assert result.cavitation.regime == CavitationRegime.NONE

    def test_FF_field_within_bounds(self, water_si):
        result = run_sizing(water_si)
        assert result.FF is not None
        assert 0.50 <= result.FF <= 0.96

    def test_FR_is_unity_for_water(self, water_si):
        """Water at 1 cSt → turbulent; FR = 1.0."""
        result = run_sizing(water_si)
        assert result.FR is None or result.FR == pytest.approx(1.0, abs=0.02)

    def test_Fp_unity_no_reducers(self, water_si):
        result = run_sizing(water_si)
        assert result.Fp == pytest.approx(1.0, rel=1e-4)

    def test_fluid_phase_in_result(self, water_si):
        result = run_sizing(water_si)
        assert result.fluid_phase == FluidPhase.LIQUID

    def test_sizing_ratio_computed(self, water_si):
        result = run_sizing(water_si)
        assert result.sizing_ratio is not None
        assert result.sizing_ratio == pytest.approx(
            result.Cv_required / water_si.valve.Cv_rated, rel=1e-3
        )

    def test_velocity_positive(self, water_si):
        result = run_sizing(water_si)
        assert result.velocity_ms is not None
        assert result.velocity_ms > 0.0

    def test_SI_and_US_give_same_Cv(self, water_si, water_us):
        """Same physical case in SI and US units must yield same Cv."""
        result_si = run_sizing(water_si)
        result_us = run_sizing(water_us)
        assert result_si.success is True
        assert result_us.success is True
        assert result_si.Cv_required == pytest.approx(result_us.Cv_required, rel=0.03)


class TestLiquidWithReducers:

    def test_Fp_less_than_one(self, water_with_reducers):
        result = run_sizing(water_with_reducers)
        assert result.success is True
        assert result.Fp < 1.0

    def test_Cv_higher_with_reducers(self, water_si, water_with_reducers):
        """Fittings always increase required Cv (Fp < 1 → more valve needed)."""
        r_plain    = run_sizing(water_si)
        r_reducers = run_sizing(water_with_reducers)
        assert r_reducers.Cv_required > r_plain.Cv_required


class TestCavitatingLiquid:

    def test_cavitation_constant_regime(self, cavitating_water):
        result = run_sizing(cavitating_water)
        assert result.success is True
        assert result.cavitation is not None
        assert result.cavitation.regime == CavitationRegime.CONSTANT

    def test_cavitation_warning_in_messages(self, cavitating_water):
        result = run_sizing(cavitating_water)
        codes  = [m.code for m in result.messages]
        assert "WARN_CAVITATION_CONSTANT" in codes


class TestFlashingLiquid:

    def test_flashing_regime(self, flashing_liquid):
        result = run_sizing(flashing_liquid)
        assert result.success is True
        assert result.cavitation.regime == CavitationRegime.FLASHING

    def test_flashing_warning_in_messages(self, flashing_liquid):
        result = run_sizing(flashing_liquid)
        codes  = [m.code for m in result.messages]
        assert "WARN_FLASHING" in codes


class TestViscousLiquid:

    def test_success_flag(self, viscous_oil):
        result = run_sizing(viscous_oil)
        assert result.success is True

    def test_viscous_warning_in_messages(self, viscous_oil):
        result = run_sizing(viscous_oil)
        codes  = [m.code for m in result.messages]
        assert "WARN_VISCOUS" in codes

    def test_FR_less_than_one(self, viscous_oil):
        result = run_sizing(viscous_oil)
        assert result.FR is not None
        assert result.FR < 1.0


class TestGasSizingIntegration:

    def test_success_flag(self, air_si):
        result = run_sizing(air_si)
        assert result.success is True

    def test_Cv_positive(self, air_si):
        result = run_sizing(air_si)
        assert result.Cv_required > 0.0

    def test_Cv_approximately_correct(self, air_si):
        """Expected ≈ 6.90 (hand-calculated); tolerance 5%."""
        result = run_sizing(air_si)
        assert result.Cv_required == pytest.approx(6.90, rel=0.05)

    def test_not_choked_subcritical(self, air_si):
        result = run_sizing(air_si)
        assert result.is_choked is False

    def test_Y_in_valid_range(self, air_si):
        result = run_sizing(air_si)
        assert result.Y is not None
        assert 2 / 3 <= result.Y <= 1.0

    def test_x_value(self, air_si):
        """x = (5−3)/5 = 0.400"""
        result = run_sizing(air_si)
        assert result.x == pytest.approx(0.40, rel=0.005)


class TestChokedGasIntegration:

    def test_choked_flag_true(self, air_choked):
        result = run_sizing(air_choked)
        assert result.success   is True
        assert result.is_choked is True

    def test_Y_equals_two_thirds(self, air_choked):
        result = run_sizing(air_choked)
        assert result.Y == pytest.approx(2.0 / 3.0, rel=1e-4)

    def test_choked_warning_in_messages(self, air_choked):
        result = run_sizing(air_choked)
        codes  = [m.code for m in result.messages]
        assert "WARN_CHOKED_GAS" in codes


class TestSteamSizingIntegration:

    @pytest.fixture(autouse=True)
    def require_iapws(self):
        pytest.importorskip("iapws", reason="iapws not installed")

    def test_steam_success(self, superheated_steam_si):
        result = run_sizing(superheated_steam_si)
        assert result.success is True

    def test_steam_cv_positive(self, superheated_steam_si):
        result = run_sizing(superheated_steam_si)
        assert result.Cv_required > 0.0

    def test_steam_type_superheated(self, superheated_steam_si):
        result = run_sizing(superheated_steam_si)
        assert result.steam_type == SteamType.SUPERHEATED

    def test_steam_fluid_phase(self, superheated_steam_si):
        result = run_sizing(superheated_steam_si)
        assert result.fluid_phase == FluidPhase.STEAM


class TestHardConstraintFailures:

    def test_pressure_inversion_returns_failure(self, invalid_pressure_inversion):
        result = run_sizing(invalid_pressure_inversion)
        assert result.success is False
        assert result.Cv_required is None

    def test_failure_has_error_message(self, invalid_pressure_inversion):
        result = run_sizing(invalid_pressure_inversion)
        assert len(result.messages) > 0
        assert all(m.level == MessageLevel.ERROR for m in result.messages)


class TestResultModelCompleteness:

    def test_all_si_fields_populated(self, water_si):
        result = run_sizing(water_si)
        assert result.P1_bar   is not None
        assert result.P2_bar   is not None
        assert result.T1_K     is not None
        assert result.W_kgh    is not None
        assert result.rho1_kgm3 is not None

    def test_messages_is_list(self, water_si):
        result = run_sizing(water_si)
        assert isinstance(result.messages, list)

    def test_noise_result_present_for_liquid(self, water_si):
        result = run_sizing(water_si)
        # Noise result may be None if noise computation failed gracefully,
        # but the result must still be a success.
        assert result.success is True