"""
Tests for backend.piping_geometry
===================================
All expected values are derived from IEC 60534-2-1:2011, Clause 6 equations.
"""

from __future__ import annotations

import math

import pytest

from backend.models import ConvergenceError
from backend.piping_geometry import (
    calc_FLP, calc_Fp_iterative, calc_Fp_single, calc_xTP,
    fitting_loss_coefficients, sum_loss_coefficients,
)


class TestFittingLossCoefficients:

    def test_no_reducers_all_zero(self):
        """When D1 = D2 = d, all coefficients are zero."""
        c = fitting_loss_coefficients(50.0, 50.0, 50.0)
        assert c["xi1"]  == 0.0
        assert c["xi2"]  == 0.0
        assert c["xiB1"] == 0.0
        assert c["xiB2"] == 0.0

    def test_upstream_reducer_nonzero(self):
        """D1 > d → xi1 and xiB1 are nonzero."""
        c = fitting_loss_coefficients(50.0, 80.0, 50.0)
        assert c["xi1"]  > 0.0
        assert c["xiB1"] > 0.0
        assert c["xi2"]  == 0.0
        assert c["xiB2"] == 0.0

    def test_downstream_expander_nonzero(self):
        """D2 > d → xi2 and xiB2 are nonzero."""
        c = fitting_loss_coefficients(50.0, 50.0, 80.0)
        assert c["xi2"]  > 0.0
        assert c["xiB2"] > 0.0
        assert c["xi1"]  == 0.0
        assert c["xiB1"] == 0.0

    def test_xi2_larger_than_xi1_for_same_ratio(self):
        """
        Outlet expander has coefficient 1.0 vs 0.5 for inlet reducer.
        With identical d/D ratio, xi2 > xi1.
        """
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        assert c["xi2"] == pytest.approx(2.0 * c["xi1"], rel=1e-6)

    def test_xi1_formula(self):
        """ξ₁ = 0.5 × (1 − (d/D₁)²)²"""
        d, D1 = 50.0, 80.0
        ratio  = (d / D1) ** 2
        expected = 0.5 * (1.0 - ratio) ** 2
        c = fitting_loss_coefficients(d, D1, D1)
        assert c["xi1"] == pytest.approx(expected, rel=1e-9)

    def test_xiB1_formula(self):
        """ξ_B1 = 1 − (d/D₁)⁴"""
        d, D1 = 50.0, 80.0
        expected = 1.0 - (d / D1) ** 4
        c = fitting_loss_coefficients(d, D1, D1)
        assert c["xiB1"] == pytest.approx(expected, rel=1e-9)


class TestSumLossCoefficients:

    def test_no_fittings_returns_zero(self):
        c = fitting_loss_coefficients(50.0, 50.0, 50.0)
        sx, sx1 = sum_loss_coefficients(c)
        assert sx  == 0.0
        assert sx1 == 0.0

    def test_sum_xi_formula(self):
        """Σξ = ξ₁ + ξ₂ + ξ_B1 − ξ_B2"""
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        sx, _ = sum_loss_coefficients(c)
        expected = c["xi1"] + c["xi2"] + c["xiB1"] - c["xiB2"]
        assert sx == pytest.approx(expected, rel=1e-9)

    def test_sum_xi1_formula(self):
        """Σξ₁ = ξ₁ + ξ_B1 (upstream fittings only)"""
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        _, sx1 = sum_loss_coefficients(c)
        expected = c["xi1"] + c["xiB1"]
        assert sx1 == pytest.approx(expected, rel=1e-9)


class TestFpSingle:
    """
    Fp = [1 + (Σξ/N₂) × (Cv/d²)²]^(−1/2)
    N₂ = 0.00214 (d in mm)
    """

    def test_Fp_no_fittings_is_unity(self):
        """Σξ = 0 → Fp = 1.0 regardless of Cv or d."""
        Fp = calc_Fp_single(Cv=100.0, d_mm=50.0, sum_xi=0.0)
        assert Fp == pytest.approx(1.0, rel=1e-9)

    def test_Fp_with_fittings_less_than_unity(self):
        """Any positive Σξ must give Fp < 1."""
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        sx, _ = sum_loss_coefficients(c)
        Fp = calc_Fp_single(80.0, 50.0, sx)
        assert Fp < 1.0

    def test_Fp_hand_calculation(self):
        """
        d=50 mm, Cv=80, D1=D2=80 mm
        ξ₁=0.5*(1-(50/80)²)²=0.1857, ξ₂=2*ξ₁=0.3713
        ξ_B1=1-(50/80)⁴=0.8474, ξ_B2=ξ_B1=0.8474
        Σξ = 0.1857+0.3713+0.8474−0.8474 = 0.5570
        term = (0.5570/0.00214)*(80/2500)² = 260.3*0.001024 = 0.2665
        Fp = (1.2665)^(-0.5) = 0.8884
        """
        c   = fitting_loss_coefficients(50.0, 80.0, 80.0)
        sx, _ = sum_loss_coefficients(c)
        Fp  = calc_Fp_single(80.0, 50.0, sx)
        assert Fp == pytest.approx(0.8884, rel=0.02)

    def test_Fp_bounded_between_zero_and_one(self):
        c  = fitting_loss_coefficients(50.0, 100.0, 100.0)
        sx, _ = sum_loss_coefficients(c)
        Fp = calc_Fp_single(200.0, 50.0, sx)
        assert 0.0 < Fp <= 1.0

    def test_Fp_decreases_with_larger_reducer(self):
        """Larger pipe (smaller d/D ratio) → larger Σξ → smaller Fp."""
        c80  = fitting_loss_coefficients(50.0, 80.0,  80.0)
        c100 = fitting_loss_coefficients(50.0, 100.0, 100.0)
        sx80,  _ = sum_loss_coefficients(c80)
        sx100, _ = sum_loss_coefficients(c100)
        Fp80  = calc_Fp_single(80.0, 50.0, sx80)
        Fp100 = calc_Fp_single(80.0, 50.0, sx100)
        assert Fp100 < Fp80


class TestFpIterative:

    def test_no_fittings_returns_fp_one(self):
        Fp, Cv = calc_Fp_iterative(81.74, 50.0, 0.0)
        assert Fp == pytest.approx(1.0, rel=1e-6)
        assert Cv == pytest.approx(81.74, rel=1e-6)

    def test_convergence_with_fittings(self):
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        sx, _ = sum_loss_coefficients(c)
        Fp, Cv_corrected = calc_Fp_iterative(81.74, 50.0, sx)
        assert 0.8 < Fp < 1.0
        assert Cv_corrected > 81.74       # fittings always increase required Cv

    def test_convergence_is_tight(self):
        """Converged Fp must be consistent with corrected Cv."""
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        sx, _ = sum_loss_coefficients(c)
        Fp, Cv_corrected = calc_Fp_iterative(81.74, 50.0, sx)
        Fp_check = calc_Fp_single(Cv_corrected, 50.0, sx)
        assert Fp == pytest.approx(Fp_check, rel=1e-4)


class TestFLP:

    def test_no_fittings_returns_FL(self):
        """With Σξ₁ = 0, FLP = FL."""
        FLP = calc_FLP(FL=0.85, Cv=80.0, d_mm=50.0, sum_xi1=0.0)
        assert FLP == pytest.approx(0.85, rel=1e-9)

    def test_FLP_less_than_FL_with_fittings(self):
        """FLP < FL when fittings are present (IEC 60534-2-1 Clause 6)."""
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        _, sx1 = sum_loss_coefficients(c)
        FLP = calc_FLP(0.85, 80.0, 50.0, sx1)
        assert FLP < 0.85


class TestXTP:

    def test_no_fittings_returns_xT(self):
        """With Σξ₁ = 0 and Fp = 1, xTP = xT."""
        xTP = calc_xTP(xT=0.65, Fp=1.0, Cv=80.0, d_mm=50.0, sum_xi1=0.0)
        assert xTP == pytest.approx(0.65, rel=1e-6)

    def test_xTP_less_than_xT_with_fittings(self):
        """xTP ≤ xT always (fittings reduce the choked ratio)."""
        c = fitting_loss_coefficients(50.0, 80.0, 80.0)
        sx, sx1 = sum_loss_coefficients(c)
        Fp = calc_Fp_single(80.0, 50.0, sx)
        xTP = calc_xTP(0.65, Fp, 80.0, 50.0, sx1)
        assert xTP <= 0.65

    def test_xTP_bounded_positive(self):
        c = fitting_loss_coefficients(50.0, 100.0, 100.0)
        sx, sx1 = sum_loss_coefficients(c)
        Fp = calc_Fp_single(80.0, 50.0, sx)
        xTP = calc_xTP(0.65, Fp, 80.0, 50.0, sx1)
        assert xTP > 0.0