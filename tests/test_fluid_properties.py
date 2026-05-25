"""
Tests for backend.fluid_properties
=====================================
Verifies fluid property calculation functions against known reference values.
Steam property tests are skipped if the iapws package is not installed.
"""

from __future__ import annotations

import math

import pytest

from backend.constants import R_UNIVERSAL, RHO_WATER_15C
from backend.fluid_properties import (
    gas_density, gas_specific_gravity, get_steam_properties,
    kinematic_viscosity, liquid_density, mass_to_standard_volumetric,
    speed_of_sound, standard_volumetric_to_mass, wet_steam_specific_volume,
)
from backend.models import SteamType


class TestLiquidProperties:

    def test_liquid_density_water(self):
        """Water Gf=1.0 → ρ ≈ 999.1 kg/m³."""
        assert liquid_density(1.0) == pytest.approx(999.1, rel=1e-3)

    def test_liquid_density_propane_60C(self):
        """Propane at 60 °C Gf ≈ 0.50 → ρ ≈ 499.6 kg/m³."""
        assert liquid_density(0.50) == pytest.approx(0.50 * 999.1, rel=1e-3)

    def test_liquid_density_heavy_oil(self):
        rho = liquid_density(0.92)
        assert 900 < rho < 930

    def test_kinematic_viscosity_water(self):
        """Water: μ = 1.002 cP, Gf = 1.0 → ν ≈ 1.003 cSt."""
        nu = kinematic_viscosity(1.002, 1.0)
        assert nu == pytest.approx(1.003, rel=0.01)

    def test_kinematic_viscosity_heavy_oil(self):
        """Heavy oil: μ = 200 cP, Gf = 0.92 → ν ≈ 217 cSt."""
        nu = kinematic_viscosity(200.0, 0.92)
        assert nu == pytest.approx(217.6, rel=0.02)

    def test_kinematic_viscosity_increases_with_viscosity(self):
        nu_low  = kinematic_viscosity(1.0,   1.0)
        nu_high = kinematic_viscosity(100.0, 1.0)
        assert nu_high > nu_low


class TestGasProperties:

    def test_gas_density_ideal_air_at_1atm_300K(self):
        """Air at 1.01325 bar, 300 K: ρ ≈ 1.176 kg/m³."""
        rho = gas_density(P1_bar=1.01325, T1_K=300.0, M=28.97, Z=1.0)
        assert rho == pytest.approx(1.176, rel=0.02)

    def test_gas_density_scales_with_pressure(self):
        """Doubling pressure doubles density (ideal gas)."""
        rho1 = gas_density(5.0, 300.0, 28.97, 1.0)
        rho2 = gas_density(10.0, 300.0, 28.97, 1.0)
        assert rho2 == pytest.approx(2.0 * rho1, rel=1e-6)

    def test_gas_density_scales_inversely_with_temperature(self):
        """Doubling temperature halves density (ideal gas)."""
        rho1 = gas_density(5.0, 300.0, 28.97, 1.0)
        rho2 = gas_density(5.0, 600.0, 28.97, 1.0)
        assert rho2 == pytest.approx(0.5 * rho1, rel=1e-6)

    def test_gas_density_with_Z_correction(self):
        """Z = 0.9 increases density by factor 1/0.9 vs ideal."""
        rho_ideal = gas_density(50.0, 350.0, 16.04, Z=1.0)
        rho_real  = gas_density(50.0, 350.0, 16.04, Z=0.9)
        assert rho_real == pytest.approx(rho_ideal / 0.9, rel=1e-6)

    def test_gas_density_rejects_nonpositive_Z(self):
        with pytest.raises(ValueError, match="Z"):
            gas_density(5.0, 300.0, 28.97, Z=0.0)

    def test_speed_of_sound_air_at_300K(self):
        """c = √(1.40 × 8314 × 300 / 28.97) ≈ 347 m/s."""
        c = speed_of_sound(1.40, 300.0, 28.97)
        assert c == pytest.approx(347.2, rel=0.01)

    def test_speed_of_sound_increases_with_temperature(self):
        c300 = speed_of_sound(1.40, 300.0, 28.97)
        c600 = speed_of_sound(1.40, 600.0, 28.97)
        assert c600 > c300

    def test_gas_specific_gravity_air(self):
        """Air Gg = 28.967/28.967 = 1.0."""
        assert gas_specific_gravity(28.967) == pytest.approx(1.0, rel=1e-4)

    def test_gas_specific_gravity_methane(self):
        """Methane Gg = 16.04/28.967 ≈ 0.554."""
        assert gas_specific_gravity(16.04) == pytest.approx(0.5537, rel=0.01)

    def test_flow_conversion_roundtrip(self):
        """Mass → standard vol → mass must be identity."""
        W_orig    = 1000.0        # kg/h
        M         = 28.97
        q_s       = mass_to_standard_volumetric(W_orig, M)
        W_back    = standard_volumetric_to_mass(q_s, M)
        assert W_back == pytest.approx(W_orig, rel=1e-9)


class TestSteamProperties:

    @pytest.fixture(autouse=True)
    def require_iapws(self):
        pytest.importorskip("iapws", reason="iapws package not installed")

    def test_superheated_steam_type(self):
        """At 10 bar, 230 °C: T > T_sat(10 bar) ≈ 180 °C → SUPERHEATED."""
        T1_K   = 230.0 + 273.15
        P1_bar = 10.0
        props  = get_steam_properties(T1_K, P1_bar)
        assert props.steam_type == SteamType.SUPERHEATED

    def test_superheated_specific_volume_positive(self):
        T1_K   = 230.0 + 273.15
        P1_bar = 10.0
        props  = get_steam_properties(T1_K, P1_bar)
        assert props.v1 > 0.0

    def test_superheated_specific_volume_range(self):
        """At 10 bar, 230 °C: v₁ should be ~0.24–0.27 m³/kg."""
        T1_K   = 230.0 + 273.15
        P1_bar = 10.0
        props  = get_steam_properties(T1_K, P1_bar)
        assert 0.20 < props.v1 < 0.35

    def test_saturated_dry_steam_type(self):
        """At 10 bar, T = T_sat ≈ 179.9 °C → SATURATED_DRY (x_q = None)."""
        props = get_steam_properties(T1_K=453.03, P1_bar=10.0, steam_quality=None)
        assert props.steam_type in (SteamType.SATURATED_DRY, SteamType.SUPERHEATED)

    def test_wet_steam_type(self):
        """x_q = 0.80 → WET."""
        T1_K   = 453.03    # ≈ T_sat at 10 bar
        props  = get_steam_properties(T1_K, 10.0, steam_quality=0.80)
        assert props.steam_type == SteamType.WET

    def test_wet_steam_specific_volume(self):
        """vf < v_wet < vg."""
        T1_K  = 453.03
        props = get_steam_properties(T1_K, 10.0, steam_quality=0.80)
        assert props.vf < props.v1 < props.vg

    def test_gamma_superheated_steam_range(self):
        """γ for steam should be in [1.1, 1.4] range."""
        props = get_steam_properties(503.15, 10.0)
        assert 1.05 < props.gamma < 1.45

    def test_wet_steam_specific_volume_formula(self):
        """v_wet = vf + x*(vg - vf)."""
        vf, vg, x = 0.001127, 0.19444, 0.80
        v_wet = wet_steam_specific_volume(vf, vg, x)
        expected = vf + x * (vg - vf)
        assert v_wet == pytest.approx(expected, rel=1e-9)

    def test_wet_steam_sv_quality_zero_equals_vf(self):
        assert wet_steam_specific_volume(0.001, 0.2, 0.0) == pytest.approx(0.001)

    def test_wet_steam_sv_quality_one_equals_vg(self):
        assert wet_steam_specific_volume(0.001, 0.2, 1.0) == pytest.approx(0.2)

    def test_invalid_quality_raises(self):
        with pytest.raises(ValueError, match="quality"):
            wet_steam_specific_volume(0.001, 0.2, 1.5)