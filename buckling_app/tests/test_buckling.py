"""
Tests for buckling_solver.py

Verification against the algorithm document example (EC3 / EN 1993-1-1):
  SHS 100x100x6 cold-formed, S235, L=6m, mu=1.0, NEd=100kN

Expected intermediate values from the document:
  NRk = 508.3 kN (A * fy)
  Ncr = 170.6 kN (Euler critical force)
  lambda_bar = 1.726
  Buckling curve "c", alpha = 0.49
  Phi = 2.360
  chi = 0.251 (document says 0.26 from chart, 0.251 from formula)
  Nb,Rd = 127.5 kN
  Utilization = 78.4%

Run: pytest buckling_app/tests/ -v
"""

import math

import pytest

from buckling_solver import (
    MemberInput,
    StrengthResult,
    BucklingAxisResult,
    MemberCheckResult,
    check_strength,
    check_buckling_axis,
    check_member,
    validate_input,
    buckling_curve_points,
    IMPERFECTION_FACTORS,
    SLENDERNESS_THRESHOLD,
)


def assert_close(actual: float, expected: float, rel_tol: float = 0.02, label: str = ""):
    """Assert two values are within relative tolerance."""
    if expected == 0:
        assert abs(actual) < 1e-10, f"{label}: expected ~0, got {actual}"
    else:
        ratio = abs(actual - expected) / abs(expected)
        assert ratio < rel_tol, (
            f"{label}: expected {expected}, got {actual}, "
            f"diff = {ratio * 100:.2f}% (tol = {rel_tol * 100:.0f}%)"
        )


# ---------------------------------------------------------------------------
# Document example: SHS 100x100x6, S235, L=6m
# ---------------------------------------------------------------------------

# Note: The document uses A=2163 mm2 and Imin=3,115,000 mm4 (3.115e6)
# These match cold-formed SHS 100x100x6 catalogue values

SHS_EXAMPLE = MemberInput(
    name="SHS 100x100x6",
    N_Ed_kN=-100.0,
    A_mm2=2163.0,
    Iy_mm4=3_115_000.0,
    Iz_mm4=3_115_000.0,
    fy_MPa=235.0,
    E_MPa=200_000.0,
    L_m=6.0,
    mu_y=1.0,
    mu_z=1.0,
    curve_y="c",
    curve_z="c",
    gamma_M0=1.0,
    gamma_M1=1.0,
)


class TestDocumentExample:
    """Verify all intermediate values against the algorithm document."""

    def test_strength_NRd(self):
        """NRd = A * fy / gamma_M0 = 2163 * 235 / 1.0 = 508,305 N = 508.3 kN"""
        result = check_strength(SHS_EXAMPLE)
        assert_close(result.N_Rd_kN, 508.3, rel_tol=0.01, label="N_Rd")

    def test_strength_utilization(self):
        """Strength utilization = 100 / 508.3 = 19.7%"""
        result = check_strength(SHS_EXAMPLE)
        assert_close(result.utilization, 100.0 / 508.3, rel_tol=0.01, label="strength util")

    def test_strength_passed(self):
        result = check_strength(SHS_EXAMPLE)
        assert result.passed is True

    def test_strength_stress_method(self):
        """sigma_Ed = 100000/2163 = 46.2 MPa, sigma_Rd = 235 MPa"""
        result = check_strength(SHS_EXAMPLE)
        assert_close(result.sigma_Ed_MPa, 100_000 / 2163.0, rel_tol=0.01, label="sigma_Ed")
        assert_close(result.sigma_Rd_MPa, 235.0, rel_tol=0.001, label="sigma_Rd")
        assert result.stress_ok is True

    def test_strength_area_method(self):
        """A_min = 100000 * 1.0 / 235 = 425.5 mm2"""
        result = check_strength(SHS_EXAMPLE)
        assert_close(result.A_min_mm2, 100_000 / 235.0, rel_tol=0.01, label="A_min")
        assert result.area_ok is True

    def test_euler_critical_force(self):
        """Ncr = pi^2 * 200000 * 3115000 / 6000^2 = 170,582 N = 170.6 kN"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        expected_Ncr = math.pi ** 2 * 200_000 * 3_115_000 / (6000 ** 2) / 1000
        assert_close(result.N_cr_kN, expected_Ncr, rel_tol=0.001, label="N_cr")
        assert_close(result.N_cr_kN, 170.6, rel_tol=0.01, label="N_cr vs doc")

    def test_relative_slenderness(self):
        """lambda_bar = sqrt(NRk / Ncr) = sqrt(508305 / 170582) = 1.726"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert_close(result.lambda_bar, 1.726, rel_tol=0.01, label="lambda_bar")

    def test_buckling_not_skipped(self):
        """lambda_bar = 1.726 > 0.2, so buckling check is required"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert result.skip_buckling is False

    def test_imperfection_factor(self):
        """Curve c -> alpha = 0.49"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert result.curve == "c"
        assert result.alpha == 0.49

    def test_phi(self):
        """Phi = 0.5 * [1 + 0.49*(1.726 - 0.2) + 1.726^2] = 2.360"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert_close(result.Phi, 2.360, rel_tol=0.01, label="Phi")

    def test_chi(self):
        """chi = 1 / (Phi + sqrt(Phi^2 - lambda_bar^2)) = 0.251"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert_close(result.chi, 0.251, rel_tol=0.02, label="chi")

    def test_buckling_resistance(self):
        """Nb,Rd = chi * A * fy / gamma_M1 = 0.251 * 2163 * 235 / 1.0 = 127.5 kN"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert_close(result.N_b_Rd_kN, 127.5, rel_tol=0.02, label="Nb,Rd")

    def test_buckling_utilization(self):
        """Utilization = 100 / 127.5 = 78.4%"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert_close(result.utilization, 100.0 / 127.5, rel_tol=0.02, label="util")

    def test_buckling_passed(self):
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert result.passed is True

    def test_effective_length(self):
        """L_cr = mu * L = 1.0 * 6.0 = 6.0 m = 6000 mm"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert_close(result.L_cr_m, 6.0, rel_tol=0.001, label="L_cr_m")
        assert_close(result.L_cr_mm, 6000.0, rel_tol=0.001, label="L_cr_mm")

    def test_NRk(self):
        """NRk = A * fy = 2163 * 235 = 508,305 N = 508.3 kN"""
        result = check_buckling_axis(SHS_EXAMPLE, "y")
        assert_close(result.N_Rk_kN, 508.3, rel_tol=0.01, label="N_Rk")


class TestCompleteCheck:
    """Test the combined check_member function with document example."""

    def test_governing_is_buckling(self):
        """For slender member, buckling governs over strength."""
        result = check_member(SHS_EXAMPLE)
        assert result.governing_check in ("buckling_y", "buckling_z")
        assert_close(result.governing_utilization, 100.0 / 127.5, rel_tol=0.02)

    def test_symmetric_section_same_both_axes(self):
        """SHS has same I on both axes, so both buckling checks give same result."""
        result = check_member(SHS_EXAMPLE)
        assert result.buckling_y is not None
        assert result.buckling_z is not None
        assert_close(result.buckling_y.chi, result.buckling_z.chi, rel_tol=0.001)
        assert_close(result.buckling_y.N_b_Rd_kN, result.buckling_z.N_b_Rd_kN, rel_tol=0.001)

    def test_overall_passed(self):
        result = check_member(SHS_EXAMPLE)
        assert result.overall_passed is True


# ---------------------------------------------------------------------------
# Tension member (no buckling check)
# ---------------------------------------------------------------------------

class TestTensionMember:
    """Tension members should only get strength check, no buckling."""

    def test_no_buckling_for_tension(self):
        inp = MemberInput(
            name="Tension member",
            N_Ed_kN=100.0,  # Positive = tension
            A_mm2=2163.0,
            Iy_mm4=3_115_000.0,
            Iz_mm4=3_115_000.0,
            fy_MPa=235.0,
        )
        result = check_member(inp)
        assert result.strength.is_tension is True
        assert result.buckling_y is None
        assert result.buckling_z is None
        assert result.governing_check == "strength"

    def test_tension_strength_check(self):
        inp = MemberInput(
            name="Tension member",
            N_Ed_kN=100.0,
            A_mm2=2163.0,
            Iy_mm4=3_115_000.0,
            Iz_mm4=3_115_000.0,
            fy_MPa=235.0,
        )
        result = check_member(inp)
        assert result.strength.passed is True
        assert_close(result.strength.N_Rd_kN, 508.3, rel_tol=0.01)


# ---------------------------------------------------------------------------
# Stocky member (lambda_bar <= 0.2, buckling may be skipped)
# ---------------------------------------------------------------------------

class TestStockyMember:
    """Short/stocky member where lambda_bar <= 0.2."""

    def test_skip_flag_set(self):
        """Very short member with large I should have lambda_bar <= 0.2."""
        inp = MemberInput(
            name="Stocky member",
            N_Ed_kN=-10.0,
            A_mm2=10_000.0,
            Iy_mm4=100_000_000.0,  # Very large I
            Iz_mm4=100_000_000.0,
            fy_MPa=235.0,
            L_m=0.5,               # Very short
            mu_y=1.0,
            mu_z=1.0,
            curve_y="a",
            curve_z="a",
        )
        result = check_buckling_axis(inp, "y")
        assert result.lambda_bar <= SLENDERNESS_THRESHOLD
        assert result.skip_buckling is True
        # Still computes chi (will be ~1.0)
        assert result.chi > 0.99


# ---------------------------------------------------------------------------
# Asymmetric section (different results for y and z axes)
# ---------------------------------------------------------------------------

class TestAsymmetricSection:
    """Section with different Iy and Iz gives different buckling results."""

    def test_weak_axis_governs(self):
        """Member with Iz << Iy should have buckling_z as governing."""
        inp = MemberInput(
            name="Asymmetric",
            N_Ed_kN=-200.0,
            A_mm2=5000.0,
            Iy_mm4=50_000_000.0,   # Strong axis
            Iz_mm4=5_000_000.0,     # Weak axis (10x smaller)
            fy_MPa=235.0,
            E_MPa=200_000.0,
            L_m=4.0,
            mu_y=1.0,
            mu_z=1.0,
            curve_y="b",
            curve_z="c",
        )
        result = check_member(inp)
        assert result.buckling_y is not None
        assert result.buckling_z is not None
        # Weak axis (z) should have higher utilization
        assert result.buckling_z.utilization > result.buckling_y.utilization
        assert result.governing_check == "buckling_z"


# ---------------------------------------------------------------------------
# Different boundary conditions
# ---------------------------------------------------------------------------

class TestBoundaryConditions:
    """Test different effective length factors."""

    def test_cantilever_doubles_length(self):
        inp = MemberInput(
            name="Cantilever",
            N_Ed_kN=-50.0,
            A_mm2=2163.0,
            Iy_mm4=3_115_000.0,
            Iz_mm4=3_115_000.0,
            fy_MPa=235.0,
            L_m=3.0,
            mu_y=2.0,
            mu_z=2.0,
            curve_y="c",
            curve_z="c",
        )
        result = check_buckling_axis(inp, "y")
        assert_close(result.L_cr_m, 6.0, rel_tol=0.001)

    def test_fixed_fixed_halves_length(self):
        inp = MemberInput(
            name="Fixed-fixed",
            N_Ed_kN=-50.0,
            A_mm2=2163.0,
            Iy_mm4=3_115_000.0,
            Iz_mm4=3_115_000.0,
            fy_MPa=235.0,
            L_m=6.0,
            mu_y=0.5,
            mu_z=0.5,
            curve_y="c",
            curve_z="c",
        )
        result = check_buckling_axis(inp, "y")
        assert_close(result.L_cr_m, 3.0, rel_tol=0.001)

    def test_fixed_more_resistance(self):
        """Fixed-fixed should give higher resistance than pinned-pinned."""
        base = MemberInput(
            N_Ed_kN=-100.0,
            A_mm2=2163.0,
            Iy_mm4=3_115_000.0,
            Iz_mm4=3_115_000.0,
            fy_MPa=235.0,
            L_m=6.0,
            curve_y="c",
            curve_z="c",
        )
        pinned = check_buckling_axis(
            MemberInput(**{**base.__dict__, "mu_y": 1.0}), "y"
        )
        fixed = check_buckling_axis(
            MemberInput(**{**base.__dict__, "mu_y": 0.5}), "y"
        )
        assert fixed.N_b_Rd_kN > pinned.N_b_Rd_kN
        assert fixed.chi > pinned.chi


# ---------------------------------------------------------------------------
# All buckling curves
# ---------------------------------------------------------------------------

class TestBucklingCurves:
    """Verify imperfection factors and that curves rank correctly."""

    def test_imperfection_factors(self):
        assert IMPERFECTION_FACTORS["a0"] == 0.13
        assert IMPERFECTION_FACTORS["a"] == 0.21
        assert IMPERFECTION_FACTORS["b"] == 0.34
        assert IMPERFECTION_FACTORS["c"] == 0.49
        assert IMPERFECTION_FACTORS["d"] == 0.76

    def test_curve_ordering(self):
        """a0 gives highest chi, d gives lowest for same lambda_bar."""
        inp = MemberInput(
            N_Ed_kN=-100.0,
            A_mm2=2163.0,
            Iy_mm4=3_115_000.0,
            Iz_mm4=3_115_000.0,
            fy_MPa=235.0,
            L_m=6.0,
            mu_y=1.0,
            mu_z=1.0,
        )
        results = {}
        for curve in ("a0", "a", "b", "c", "d"):
            inp_c = MemberInput(**{**inp.__dict__, "curve_y": curve})
            results[curve] = check_buckling_axis(inp_c, "y")

        assert results["a0"].chi > results["a"].chi
        assert results["a"].chi > results["b"].chi
        assert results["b"].chi > results["c"].chi
        assert results["c"].chi > results["d"].chi


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_chi_capped_at_1(self):
        """Chi should never exceed 1.0, even for very stocky members."""
        inp = MemberInput(
            N_Ed_kN=-1.0,
            A_mm2=50_000.0,
            Iy_mm4=500_000_000.0,
            Iz_mm4=500_000_000.0,
            fy_MPa=235.0,
            L_m=0.1,
            curve_y="a0",
            curve_z="a0",
        )
        result = check_buckling_axis(inp, "y")
        assert result.chi <= 1.0

    def test_high_utilization_fails(self):
        """Member with force exceeding resistance should fail."""
        inp = MemberInput(
            N_Ed_kN=-600.0,  # Exceeds NRk=508 kN
            A_mm2=2163.0,
            Iy_mm4=3_115_000.0,
            Iz_mm4=3_115_000.0,
            fy_MPa=235.0,
            L_m=6.0,
            curve_y="c",
            curve_z="c",
        )
        result = check_member(inp)
        assert result.overall_passed is False
        assert result.governing_utilization > 1.0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    """Input validation tests."""

    def test_valid_input(self):
        assert validate_input(SHS_EXAMPLE) is None

    def test_zero_area(self):
        inp = MemberInput(A_mm2=0.0)
        err = validate_input(inp)
        assert err is not None
        assert "area" in err.lower() or "A" in err

    def test_negative_length(self):
        inp = MemberInput(L_m=-1.0)
        err = validate_input(inp)
        assert err is not None
        assert "length" in err.lower() or "L" in err

    def test_invalid_curve(self):
        inp = MemberInput(curve_y="x")
        err = validate_input(inp)
        assert err is not None
        assert "curve" in err.lower()

    def test_zero_force(self):
        inp = MemberInput(N_Ed_kN=0.0)
        err = validate_input(inp)
        assert err is not None


# ---------------------------------------------------------------------------
# Buckling curve plotting data
# ---------------------------------------------------------------------------

class TestBucklingCurvePoints:
    """Test buckling curve data generation for plotting."""

    def test_returns_correct_length(self):
        lambdas, chis = buckling_curve_points("c", lambda_max=3.0, n_points=100)
        assert len(lambdas) == 101
        assert len(chis) == 101

    def test_starts_at_chi_1(self):
        lambdas, chis = buckling_curve_points("a", lambda_max=3.0, n_points=100)
        assert chis[0] == 1.0

    def test_chi_decreases(self):
        """Chi should generally decrease as lambda increases."""
        lambdas, chis = buckling_curve_points("b", lambda_max=3.0, n_points=100)
        # Check that chi at lambda=3 is less than chi at lambda=0.5
        chi_low = chis[int(0.5 / 3.0 * 100)]
        chi_high = chis[-1]
        assert chi_high < chi_low
