"""
Tests for backend.noise_hydrodynamic
========================================
Validates the IEC 60534-8-4 hydrodynamic noise chain.
"""

from __future__ import annotations

import math

import pytest

from backend.models import CavitationRegime, NoiseResult
from backend.noise_hydrodynamic import run_hydro_noise
from backend.sizing_liquid import calc_FF, calc_delta_P_incipient


def _make_hydro_result(
    regime: CavitationRegime,
    delta_P_bar: float = 2.0,
) -> NoiseResult:
    """Helper to create a noise result for a given regime and ΔP."""
    P1_bar = 10.0
    Pv_bar = 0.023
    Pc_bar = 220.9
    FL     = 0.85
    FF     = calc_FF(Pv_bar, Pc_bar)
    dPi    = calc_delta_P_incipient(FL, P1_bar, Pv_bar)
    return run_hydro_noise(
        Q_m3h=100.0,
        P1_bar=P1_bar,
        Pv_bar=Pv_bar,
        FF=FF,
        rho_L=999.1,
        Di_m=0.0525,
        t_wall_m=0.00391,
        delta_P_i_bar=dPi,
        delta_P_bar=delta_P_bar,
        cavitation_regime=regime,
    )


class TestRunHydroNoise:

    def test_returns_NoiseResult_model(self):
        result = _make_hydro_result(CavitationRegime.NONE, 2.0)
        assert isinstance(result, NoiseResult)

    def test_Lpe_finite_no_cavitation(self):
        result = _make_hydro_result(CavitationRegime.NONE, 2.0)
        assert math.isfinite(result.Lpe_dba)

    def test_Lpe_finite_choked(self):
        result = _make_hydro_result(CavitationRegime.CHOKED, 7.5)
        assert math.isfinite(result.Lpe_dba)

    def test_TL_non_negative(self):
        result = _make_hydro_result(CavitationRegime.NONE, 2.0)
        assert result.TL_db >= 0.0

    def test_f_peak_positive(self):
        result = _make_hydro_result(CavitationRegime.CONSTANT, 5.0)
        assert result.f_peak_hz > 0.0

    def test_choked_louder_than_none(self):
        """Choked cavitation is noisier than turbulent flow."""
        r_none   = _make_hydro_result(CavitationRegime.NONE,   2.0)
        r_choked = _make_hydro_result(CavitationRegime.CHOKED, 7.5)
        assert r_choked.Lpe_dba > r_none.Lpe_dba

    def test_flashing_louder_than_choked(self):
        """Flashing adds +6 dB over the choked regime (Lpi level)."""
        r_choked   = _make_hydro_result(CavitationRegime.CHOKED,   7.5)
        r_flashing = _make_hydro_result(CavitationRegime.FLASHING, 7.5)
        assert r_flashing.Lpe_dba > r_choked.Lpe_dba

    def test_exceeds_limit_flag_type(self):
        result = _make_hydro_result(CavitationRegime.NONE, 2.0)
        assert isinstance(result.exceeds_limit, bool)

    def test_regime_field_is_string(self):
        result = _make_hydro_result(CavitationRegime.CONSTANT, 5.0)
        assert isinstance(result.regime, str)

    def test_noise_increases_with_flow(self):
        """Higher flow → higher acoustic power → louder noise."""
        P1, Pv, Pc, FL = 10.0, 0.023, 220.9, 0.85
        FF  = calc_FF(Pv, Pc)
        dPi = calc_delta_P_incipient(FL, P1, Pv)
        r1  = run_hydro_noise(50.0,  P1, Pv, FF, 999.1, 0.0525, 0.00391, dPi, 2.0, CavitationRegime.NONE)
        r2  = run_hydro_noise(200.0, P1, Pv, FF, 999.1, 0.0525, 0.00391, dPi, 2.0, CavitationRegime.NONE)
        assert r2.Lpe_dba > r1.Lpe_dba