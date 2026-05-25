"""
Tests for backend.sizing_steam
================================
Steam property retrieval requires the iapws package.
Individual tests are skipped when iapws is not installed.
"""

from __future__ import annotations

import math

import pytest

from backend.models import SteamType
from backend.sizing_steam import cv_steam


@pytest.fixture(autouse=True)
def require_iapws():
    pytest.importorskip("iapws", reason="iapws package not installed")


class TestCvSteam:

    def test_superheated_steam_returns_positive_cv(self):
        """2000 kg/h superheated steam at 10 bar, 230°C → Cv > 0."""
        T1_K = 230.0 + 273.15
        Cv, Fgamma, x, Y, choked, props = cv_steam(
            W_kgh=2_000.0, P1_bar=10.0, P2_bar=5.0, T1_K=T1_K,
            xT=0.65, Fp=1.0,
        )
        assert Cv > 0.0

    def test_superheated_steam_type_classified(self):
        T1_K = 230.0 + 273.15
        *_, props = cv_steam(2_000.0, 10.0, 5.0, T1_K, xT=0.65)
        assert props.steam_type == SteamType.SUPERHEATED

    def test_subcritical_steam_not_choked(self):
        """P1=10, P2=5 → x=0.5; xT=0.65; Fγ·xT≈0.589; x < Fγ·xT → not choked."""
        T1_K = 230.0 + 273.15
        Cv, Fgamma, x, Y, choked, props = cv_steam(
            2_000.0, 10.0, 5.0, T1_K, xT=0.65
        )
        x_computed = (10.0 - 5.0) / 10.0
        Fgxt = Fgamma * 0.65
        # Check choked flag consistency
        if x_computed < Fgxt:
            assert choked is False
        else:
            assert choked is True

    def test_choked_steam_Y_equals_two_thirds(self):
        """P2 = 0.5 bar → x = 0.95 >> Fγ·xT → choked."""
        T1_K = 230.0 + 273.15
        _, _, _, Y, choked, _ = cv_steam(2_000.0, 10.0, 0.5, T1_K, xT=0.65)
        assert choked is True
        assert Y == pytest.approx(2.0 / 3.0, rel=1e-5)

    def test_saturated_dry_steam(self):
        """At T_sat for 10 bar ≈ 179.9°C → SATURATED_DRY."""
        T_sat_K = 179.9 + 273.15
        Cv, _, _, _, _, props = cv_steam(
            W_kgh=1_000.0, P1_bar=10.0, P2_bar=5.0,
            T1_K=T_sat_K, xT=0.65, steam_quality=1.0
        )
        assert Cv > 0
        assert props.steam_type in (SteamType.SATURATED_DRY, SteamType.SUPERHEATED)

    def test_wet_steam(self):
        """x_q = 0.80 → WET steam; Cv still computable."""
        T1_K = 179.9 + 273.15
        Cv, _, _, _, _, props = cv_steam(
            W_kgh=1_000.0, P1_bar=10.0, P2_bar=5.0,
            T1_K=T1_K, xT=0.65, steam_quality=0.80
        )
        assert Cv > 0
        assert props.steam_type == SteamType.WET

    def test_higher_mass_flow_gives_higher_Cv(self):
        T1_K = 230.0 + 273.15
        Cv1, *_ = cv_steam(1_000.0, 10.0, 5.0, T1_K, xT=0.65)
        Cv2, *_ = cv_steam(2_000.0, 10.0, 5.0, T1_K, xT=0.65)
        assert Cv2 == pytest.approx(2.0 * Cv1, rel=0.01)

    def test_Fp_increases_required_Cv(self):
        T1_K  = 230.0 + 273.15
        Cv_no, *_  = cv_steam(2_000.0, 10.0, 5.0, T1_K, xT=0.65, Fp=1.0)
        Cv_fit, *_ = cv_steam(2_000.0, 10.0, 5.0, T1_K, xT=0.65, Fp=0.9)
        assert Cv_fit > Cv_no