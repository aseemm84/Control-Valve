"""
Tests for backend.noise_aerodynamic
======================================
Validates the IEC 60534-8-3 aerodynamic noise chain step by step.
"""

from __future__ import annotations

import math

import pytest

from backend.constants import R_UNIVERSAL
from backend.noise_aerodynamic import run_aero_noise
from backend.models import AeroRegime, NoiseResult


def _speed_of_sound_ref(gamma: float, T_K: float, M: float) -> float:
    return math.sqrt(gamma * R_UNIVERSAL * T_K / M)


class TestSpeedOfSoundReference:
    """Equation 9.1 — speed of sound validation."""

    def test_air_at_300K(self):
        """c = √(1.40 × 8314 × 300 / 28.97) ≈ 347.2 m/s"""
        c = _speed_of_sound_ref(1.40, 300.0, 28.97)
        assert c == pytest.approx(347.2, rel=0.01)

    def test_methane_faster_than_air(self):
        """Lighter gas (M=16.04) has higher speed of sound than air (M=28.97)."""
        c_air  = _speed_of_sound_ref(1.40, 300.0, 28.97)
        c_ch4  = _speed_of_sound_ref(1.31, 300.0, 16.04)
        assert c_ch4 > c_air


class TestCriticalPressureRatioReference:
    """Equation 9.2 — critical pressure ratio."""

    def test_air_critical_PR(self):
        """rPc = (2/2.40)^3.5 ≈ 0.5283 for air."""
        gamma   = 1.40
        rPc     = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
        assert rPc == pytest.approx(0.5283, rel=0.01)

    def test_methane_critical_PR(self):
        """γ=1.31 → rPc = (2/2.31)^(1.31/0.31) ≈ 0.545"""
        gamma = 1.31
        rPc   = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
        assert 0.50 < rPc < 0.60


class TestRunAeroNoise:
    """Integration test for the full IEC 60534-8-3 noise chain."""

    @pytest.fixture
    def air_subcritical_noise(self) -> NoiseResult:
        """Air, P1=5 bar, P2=3 bar (rP=0.6 > rPc≈0.528 → subcritical)."""
        return run_aero_noise(
            W_kgh=500.0, P1_bar=5.0, P2_bar=3.0, T1_K=300.0,
            gamma=1.40, M=28.97, Di_m=0.0525, t_wall_m=0.00391, Fd=1.0,
        )

    @pytest.fixture
    def air_choked_noise(self) -> NoiseResult:
        """Air, P1=5 bar, P2=0.5 bar (rP=0.1 < rPc≈0.528 → choked)."""
        return run_aero_noise(
            W_kgh=500.0, P1_bar=5.0, P2_bar=0.5, T1_K=300.0,
            gamma=1.40, M=28.97, Di_m=0.0525, t_wall_m=0.00391, Fd=1.0,
        )

    def test_returns_NoiseResult_model(self, air_subcritical_noise):
        assert isinstance(air_subcritical_noise, NoiseResult)

    def test_subcritical_regime_flag(self, air_subcritical_noise):
        assert air_subcritical_noise.regime == AeroRegime.SUBCRITICAL.value

    def test_choked_regime_flag(self, air_choked_noise):
        assert air_choked_noise.regime == AeroRegime.CHOKED.value

    def test_LWi_positive_finite(self, air_subcritical_noise):
        assert math.isfinite(air_subcritical_noise.LWi_db)
        assert air_subcritical_noise.LWi_db > 0.0

    def test_TL_positive(self, air_subcritical_noise):
        assert air_subcritical_noise.TL_db >= 0.0

    def test_Lpe_finite(self, air_subcritical_noise):
        assert math.isfinite(air_subcritical_noise.Lpe_dba)

    def test_f_peak_positive(self, air_subcritical_noise):
        assert air_subcritical_noise.f_peak_hz > 0.0

    def test_choked_louder_than_subcritical_same_flow(
        self, air_subcritical_noise, air_choked_noise
    ):
        """
        At higher pressure ratio (choked), higher jet velocity →
        more acoustic power → higher Lpe.
        """
        assert air_choked_noise.Lpe_dba >= air_subcritical_noise.Lpe_dba

    def test_exceeds_limit_flag_type(self, air_subcritical_noise):
        assert isinstance(air_subcritical_noise.exceeds_limit, bool)

    def test_higher_flow_gives_higher_noise(self):
        """Doubling mass flow increases mechanical power and thus noise."""
        r1 = run_aero_noise(500.0, 5.0, 3.0, 300.0, 1.40, 28.97, 0.0525, 0.00391, 1.0)
        r2 = run_aero_noise(1_000.0, 5.0, 3.0, 300.0, 1.40, 28.97, 0.0525, 0.00391, 1.0)
        assert r2.Lpe_dba > r1.Lpe_dba

    def test_smaller_Fd_gives_lower_noise(self):
        """Multi-port trim (Fd=0.1) has lower acoustic efficiency → quieter."""
        r_globe = run_aero_noise(500.0, 5.0, 0.5, 300.0, 1.40, 28.97, 0.0525, 0.00391, Fd=1.0)
        r_cage  = run_aero_noise(500.0, 5.0, 0.5, 300.0, 1.40, 28.97, 0.0525, 0.00391, Fd=0.1)
        assert r_cage.Lpe_dba < r_globe.Lpe_dba