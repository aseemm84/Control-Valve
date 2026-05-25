"""
Tests for backend.validator
==============================
Verifies that all hard constraints raise HardConstraintViolation with
the correct error code, and that soft warnings are correctly triggered.
"""

from __future__ import annotations

import pytest

from backend.models import (
    FlowBasis, FluidPhase, FluidProperties, HardConstraintViolation,
    MessageLevel, ProcessConditions, SizingInputs, SizingResult,
    UnitSystem, ValveParameters, ValidationMessage, CavitationResult,
    CavitationRegime,
)
from backend.validator import (
    check_PT_rating, validate_hard_constraints, validate_soft_constraints,
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _make_liquid_inputs(**overrides) -> SizingInputs:
    defaults = dict(
        P1=10.0, P2=8.0, T1=20.0, flow_value=100.0,
        Gf=1.0, Pv=0.023, Pc=220.9, mu=1.002,
        FL=0.85, xT=0.65, d=50.0,
    )
    defaults.update(overrides)
    return SizingInputs(
        process=ProcessConditions(
            P1=defaults["P1"], P2=defaults["P2"], T1=defaults["T1"],
            flow_value=defaults["flow_value"],
            flow_basis=FlowBasis.VOLUMETRIC,
            fluid_phase=FluidPhase.LIQUID,
            unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(
            Gf=defaults["Gf"], Pv=defaults["Pv"],
            Pc=defaults["Pc"], mu=defaults["mu"],
        ),
        valve=ValveParameters(
            FL=defaults["FL"], xT=defaults["xT"],
            Fd=1.0, d=defaults["d"],
        ),
    )


def _make_gas_inputs(**overrides) -> SizingInputs:
    defaults = dict(P1=5.0, P2=3.0, T1=27.0, flow_value=500.0, M=28.97, gamma=1.40)
    defaults.update(overrides)
    return SizingInputs(
        process=ProcessConditions(
            P1=defaults["P1"], P2=defaults["P2"], T1=defaults["T1"],
            flow_value=defaults["flow_value"],
            flow_basis=FlowBasis.MASS,
            fluid_phase=FluidPhase.GAS,
            unit_system=UnitSystem.SI,
        ),
        fluid=FluidProperties(M=defaults["M"], gamma=defaults["gamma"], Z=1.0),
        valve=ValveParameters(FL=0.85, xT=0.60, Fd=1.0, d=50.0),
    )


# ---------------------------------------------------------------------------
# HARD CONSTRAINT TESTS
# ---------------------------------------------------------------------------

class TestHardConstraintPressure:

    def test_pressure_inversion_raises(self):
        inputs = _make_liquid_inputs(P1=5.0, P2=8.0)
        with pytest.raises(HardConstraintViolation) as exc:
            validate_hard_constraints(inputs)
        assert exc.value.code == "ERR_PRESSURE_INVERSION"

    def test_zero_flow_validation(self):
        """Pydantic rejects flow_value ≤ 0 at model creation."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            _make_liquid_inputs(flow_value=0.0)


class TestHardConstraintLiquidFluid:

    def test_missing_Gf_raises(self):
        inputs = SizingInputs(
            process=ProcessConditions(
                P1=10.0, P2=8.0, T1=20.0, flow_value=100.0,
                flow_basis=FlowBasis.VOLUMETRIC,
                fluid_phase=FluidPhase.LIQUID, unit_system=UnitSystem.SI,
            ),
            fluid=FluidProperties(Gf=None, Pv=0.023, Pc=220.9, mu=1.0),
            valve=ValveParameters(FL=0.85, xT=0.65, Fd=1.0, d=50.0),
        )
        with pytest.raises(HardConstraintViolation) as exc:
            validate_hard_constraints(inputs)
        assert "ERR_MISSING_GF" in exc.value.code

    def test_Pv_exceeds_P1_raises(self):
        inputs = _make_liquid_inputs(P1=5.0, P2=3.0, Pv=8.0, Pc=220.9)
        with pytest.raises(HardConstraintViolation) as exc:
            validate_hard_constraints(inputs)
        assert exc.value.code == "ERR_PV_EXCEEDS_P1"

    def test_Pv_gte_Pc_raises(self):
        inputs = _make_liquid_inputs(Pv=50.0, Pc=42.0)
        with pytest.raises(HardConstraintViolation) as exc:
            validate_hard_constraints(inputs)
        assert exc.value.code == "ERR_INVALID_PC_PV"


class TestHardConstraintGasFluid:

    def test_missing_M_raises(self):
        inputs = SizingInputs(
            process=ProcessConditions(
                P1=5.0, P2=3.0, T1=27.0, flow_value=500.0,
                flow_basis=FlowBasis.MASS,
                fluid_phase=FluidPhase.GAS, unit_system=UnitSystem.SI,
            ),
            fluid=FluidProperties(M=None, gamma=1.40, Z=1.0),
            valve=ValveParameters(FL=0.85, xT=0.60, Fd=1.0, d=50.0),
        )
        with pytest.raises(HardConstraintViolation) as exc:
            validate_hard_constraints(inputs)
        assert "ERR_MISSING_M" in exc.value.code

    def test_invalid_gamma_raises(self):
        inputs = _make_gas_inputs(gamma=0.9)
        with pytest.raises(HardConstraintViolation) as exc:
            validate_hard_constraints(inputs)
        assert "ERR_INVALID_GAMMA" in exc.value.code


class TestHardConstraintValve:

    def test_FL_out_of_range_raises(self):
        """Pydantic enforces FL bounds at model creation."""
        with pytest.raises(Exception):
            ValveParameters(FL=1.5, xT=0.65, Fd=1.0, d=50.0)

    def test_xT_out_of_range_raises(self):
        with pytest.raises(Exception):
            ValveParameters(FL=0.85, xT=0.95, Fd=1.0, d=50.0)


class TestHardConstraintReturnsMessages:

    def test_valid_inputs_returns_list(self):
        inputs = _make_liquid_inputs()
        result = validate_hard_constraints(inputs)
        assert isinstance(result, list)

    def test_reducer_generates_info_message(self):
        inputs = _make_liquid_inputs()
        # Override D1 > d to trigger reducer info message
        inputs.valve.D1 = 80.0
        msgs = validate_hard_constraints(inputs)
        codes = [m.code for m in msgs]
        assert "INFO_PIPE_REDUCER" in codes


# ---------------------------------------------------------------------------
# SOFT WARNING TESTS
# ---------------------------------------------------------------------------

def _make_partial_result(**kwargs) -> SizingResult:
    """Build a minimal SizingResult for soft constraint testing."""
    defaults = dict(
        success=True,
        Cv_required=50.0,
        Cv_design=60.0,
        Kv_required=43.25,
        fluid_phase=FluidPhase.LIQUID,
        is_choked=False,
        Fp=1.0,
        FR=1.0,
    )
    defaults.update(kwargs)
    return SizingResult(**defaults)


class TestSoftWarnings:

    def test_choked_liquid_warning(self):
        result  = _make_partial_result(is_choked=True)
        inputs  = _make_liquid_inputs()
        msgs    = validate_soft_constraints(result, inputs)
        codes   = [m.code for m in msgs]
        assert "WARN_CHOKED_LIQUID" in codes

    def test_viscous_warning(self):
        result  = _make_partial_result(FR=0.65, Rev=420.0)
        inputs  = _make_liquid_inputs()
        msgs    = validate_soft_constraints(result, inputs)
        codes   = [m.code for m in msgs]
        assert "WARN_VISCOUS" in codes

    def test_sizing_ratio_oversized_warning(self):
        """Cv_required/Cv_rated = 10/100 = 0.10 < 0.20 → oversized."""
        result = _make_partial_result(
            Cv_required=10.0, sizing_ratio=0.10, opening_pct=20.0
        )
        inputs = _make_liquid_inputs()
        inputs.valve.Cv_rated = 100.0
        msgs   = validate_soft_constraints(result, inputs)
        codes  = [m.code for m in msgs]
        assert "WARN_OVERSIZED" in codes

    def test_sizing_ratio_near_capacity_warning(self):
        """Cv_required/Cv_rated = 0.90 → near capacity."""
        result = _make_partial_result(
            Cv_required=90.0, sizing_ratio=0.90, opening_pct=85.0
        )
        inputs = _make_liquid_inputs()
        inputs.valve.Cv_rated = 100.0
        msgs   = validate_soft_constraints(result, inputs)
        codes  = [m.code for m in msgs]
        assert "WARN_NEAR_CAPACITY" in codes

    def test_high_velocity_warning(self):
        result = _make_partial_result(velocity_ms=6.0)
        inputs = _make_liquid_inputs()
        msgs   = validate_soft_constraints(result, inputs)
        codes  = [m.code for m in msgs]
        assert "WARN_HIGH_VELOCITY" in codes

    def test_noise_limit_warning(self):
        noise  = NoiseResult(
            Lpe_dba=90.0, LWi_db=130.0, TL_db=20.0,
            f_peak_hz=2000.0, eta=1e-4, regime="choked",
            exceeds_limit=True,
        )
        result = _make_partial_result(noise=noise)
        inputs = _make_liquid_inputs()
        msgs   = validate_soft_constraints(result, inputs)
        codes  = [m.code for m in msgs]
        assert "WARN_NOISE_LIMIT" in codes

    def test_no_spurious_warnings_for_clean_result(self):
        """A perfectly sized, non-cavitating, non-noisy case should emit no warnings."""
        result = _make_partial_result(
            sizing_ratio=0.75, opening_pct=65.0,
            velocity_ms=2.0, is_choked=False,
        )
        inputs = _make_liquid_inputs()
        inputs.valve.Cv_rated = 100.0
        msgs   = validate_soft_constraints(result, inputs)
        warn_msgs = [m for m in msgs if m.level == MessageLevel.WARNING]
        assert len(warn_msgs) == 0


# ---------------------------------------------------------------------------
# P-T RATING CHECK
# ---------------------------------------------------------------------------

class TestCheckPTRating:

    def test_within_rating_returns_None(self):
        msg = check_PT_rating(10.0, "Class150", 20.0, "SI")
        assert msg is None

    def test_exceeds_rating_returns_message(self):
        """Class 150 at 20°C → 19.6 bar; P1=25 bar → should warn."""
        msg = check_PT_rating(25.0, "Class150", 20.0, "SI")
        assert msg is not None
        assert msg.level   == MessageLevel.ERROR
        assert "WARN_PTRATING" in msg.code

    def test_unknown_pressure_class_returns_None(self):
        msg = check_PT_rating(50.0, "ClassXXX", 20.0, "SI")
        assert msg is None