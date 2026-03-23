"""
test_section_calc.py — Analytical verification of cross-section property calculations.

Tests verify against known catalogue values for standard steel profiles.
Expected tolerance: 1-2% (fillet radii are excluded in rectangular decomposition).

Run: pytest section_app/tests/ -v
"""

import math
import sys
import os

import pytest

# Add parent directory to path so we can import section_solver
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from section_solver import RectanglePart, calculate, validate_parts, MM2_TO_CM2, MM4_TO_CM4, MM3_TO_CM3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assert_close(actual: float, expected: float, tol: float = 0.02, label: str = ""):
    """Assert that actual is within tol (relative) of expected."""
    if expected == 0:
        assert abs(actual) < 1e-9, f"{label}: expected ~0, got {actual}"
    else:
        rel_err = abs(actual - expected) / abs(expected)
        assert rel_err <= tol, (
            f"{label}: expected {expected}, got {actual}, "
            f"relative error {rel_err:.4f} > {tol}"
        )


# ---------------------------------------------------------------------------
# Test: Simple rectangle
# ---------------------------------------------------------------------------

class TestSingleRectangle:
    """A single rectangle — all properties have closed-form solutions."""

    def setup_method(self):
        # 200 mm wide x 300 mm tall rectangle, origin at (0, 0)
        self.parts = [RectanglePart(name="Rect", b=200.0, h=300.0, y_bot=0.0, z_left=0.0)]
        self.result = calculate(self.parts)

    def test_area(self):
        assert_close(self.result.A_total, 200 * 300, label="Area")

    def test_centroid(self):
        assert_close(self.result.yc, 150.0, label="yc")
        assert_close(self.result.zc, 100.0, label="zc")

    def test_moment_of_inertia_y(self):
        # Iy = b * h^3 / 12 = 200 * 300^3 / 12
        Iy_expected = 200 * 300**3 / 12.0
        assert_close(self.result.Iy, Iy_expected, label="Iy")

    def test_moment_of_inertia_z(self):
        # Iz = h * b^3 / 12 = 300 * 200^3 / 12
        Iz_expected = 300 * 200**3 / 12.0
        assert_close(self.result.Iz, Iz_expected, label="Iz")

    def test_section_modulus(self):
        Iy = 200 * 300**3 / 12.0
        # y_top = y_bot = 150 mm from centroid
        W_expected = Iy / 150.0
        assert_close(self.result.Wy_top, W_expected, label="Wy_top")
        assert_close(self.result.Wy_bot, W_expected, label="Wy_bot")

    def test_radius_of_gyration(self):
        A = 200 * 300
        Iy = 200 * 300**3 / 12.0
        iy_expected = math.sqrt(Iy / A)
        assert_close(self.result.iy, iy_expected, label="iy")

    def test_no_steiner_term(self):
        """Single rectangle: Steiner term should be zero."""
        for pr in self.result.parts:
            assert_close(pr.Iy_steiner, 0.0, label=f"{pr.name} Iy_steiner")
            assert_close(pr.Iz_steiner, 0.0, label=f"{pr.name} Iz_steiner")


# ---------------------------------------------------------------------------
# Test: Symmetric I-beam (HEA 200 approximation)
# ---------------------------------------------------------------------------

class TestHEA200:
    """HEA 200 approximated as three rectangles (no fillet radii).

    Catalogue values (with fillets):
        A  = 53.83 cm²
        Iy = 3692 cm⁴  (strong axis)
        Iz = 1336 cm⁴  (weak axis)
        Wy = 388.6 cm³
        iy = 8.28 cm

    HEA 200 dimensions:
        h_total = 190 mm, b_flange = 200 mm, t_flange = 10 mm, t_web = 6.5 mm
        h_web = 190 - 2*10 = 170 mm
    """

    def setup_method(self):
        b_f = 200.0   # flange width
        t_f = 10.0    # flange thickness
        t_w = 6.5     # web thickness
        h_total = 190.0
        h_web = h_total - 2 * t_f  # 170 mm

        self.parts = [
            RectanglePart(name="Bottom flange", b=b_f, h=t_f,
                          y_bot=0.0, z_left=0.0),
            RectanglePart(name="Web", b=t_w, h=h_web,
                          y_bot=t_f, z_left=(b_f - t_w) / 2.0),
            RectanglePart(name="Top flange", b=b_f, h=t_f,
                          y_bot=t_f + h_web, z_left=0.0),
        ]
        self.result = calculate(self.parts)

    def test_area(self):
        # Without fillets: 2 * 200 * 10 + 6.5 * 170 = 4000 + 1105 = 5105 mm²
        # Catalogue: 5383 mm² (fillets add ~5%)
        A_rect = 5105.0
        assert_close(self.result.A_total, A_rect, tol=0.001, label="Area (rectangular)")
        # Also verify within 6% of catalogue
        assert_close(self.result.A_total * MM2_TO_CM2, 53.83, tol=0.06, label="Area vs catalogue")

    def test_centroid_symmetric(self):
        """Centroid should be at mid-height for a doubly-symmetric section."""
        assert_close(self.result.yc, 190.0 / 2, tol=0.001, label="yc symmetry")
        assert_close(self.result.zc, 200.0 / 2, tol=0.001, label="zc symmetry")

    def test_Iy_strong_axis(self):
        """Iy (strong axis) should be close to catalogue (3692 cm⁴)."""
        # Rectangular decomposition gives slightly less due to missing fillets
        Iy_cm4 = self.result.Iy * MM4_TO_CM4
        assert_close(Iy_cm4, 3692, tol=0.06, label="Iy vs catalogue")

    def test_Iz_weak_axis(self):
        """Iz (weak axis) should be close to catalogue (1336 cm⁴)."""
        Iz_cm4 = self.result.Iz * MM4_TO_CM4
        assert_close(Iz_cm4, 1336, tol=0.06, label="Iz vs catalogue")

    def test_Wy_section_modulus(self):
        """Wy should be close to catalogue (388.6 cm³)."""
        # For symmetric section, Wy_top == Wy_bot
        assert_close(self.result.Wy_top, self.result.Wy_bot, tol=0.001,
                      label="Wy symmetry")
        Wy_cm3 = self.result.Wy_top * MM3_TO_CM3
        assert_close(Wy_cm3, 388.6, tol=0.06, label="Wy vs catalogue")

    def test_step_by_step_parts(self):
        """Verify we get 3 part results with correct Steiner terms."""
        assert len(self.result.parts) == 3
        # Flanges should have large Steiner terms, web should have small
        bottom_flange = self.result.parts[0]
        web = self.result.parts[1]
        top_flange = self.result.parts[2]

        # Flanges are far from centroid, web is centered
        assert abs(bottom_flange.dy) > 80  # ~85 mm from centroid
        assert abs(web.dy) < 1.0  # web centroid is at section centroid
        assert abs(top_flange.dy) > 80


# ---------------------------------------------------------------------------
# Test: IPE 300 approximation
# ---------------------------------------------------------------------------

class TestIPE300:
    """IPE 300 approximated as three rectangles.

    Catalogue values:
        A  = 53.81 cm²
        Iy = 8356 cm⁴  (strong axis)
        Iz = 603.8 cm⁴  (weak axis)

    IPE 300 dimensions:
        h_total = 300 mm, b_flange = 150 mm, t_flange = 10.7 mm, t_web = 7.1 mm
    """

    def setup_method(self):
        b_f = 150.0
        t_f = 10.7
        t_w = 7.1
        h_total = 300.0
        h_web = h_total - 2 * t_f  # 278.6 mm

        self.parts = [
            RectanglePart(name="Bottom flange", b=b_f, h=t_f,
                          y_bot=0.0, z_left=0.0),
            RectanglePart(name="Web", b=t_w, h=h_web,
                          y_bot=t_f, z_left=(b_f - t_w) / 2.0),
            RectanglePart(name="Top flange", b=b_f, h=t_f,
                          y_bot=t_f + h_web, z_left=0.0),
        ]
        self.result = calculate(self.parts)

    def test_area(self):
        A_cm2 = self.result.A_total * MM2_TO_CM2
        assert_close(A_cm2, 53.81, tol=0.06, label="IPE300 Area vs catalogue")

    def test_Iy(self):
        Iy_cm4 = self.result.Iy * MM4_TO_CM4
        assert_close(Iy_cm4, 8356, tol=0.06, label="IPE300 Iy vs catalogue")

    def test_Iz(self):
        Iz_cm4 = self.result.Iz * MM4_TO_CM4
        assert_close(Iz_cm4, 603.8, tol=0.06, label="IPE300 Iz vs catalogue")

    def test_centroid_symmetric(self):
        assert_close(self.result.yc, 300.0 / 2, tol=0.001, label="yc")
        assert_close(self.result.zc, 150.0 / 2, tol=0.001, label="zc")


# ---------------------------------------------------------------------------
# Test: Asymmetric T-section
# ---------------------------------------------------------------------------

class TestTSection:
    """T-section: flange on top, web below. Asymmetric about y-axis."""

    def setup_method(self):
        # Flange: 200 x 20 mm, Web: 10 x 180 mm
        self.parts = [
            RectanglePart(name="Web", b=10.0, h=180.0,
                          y_bot=0.0, z_left=95.0),
            RectanglePart(name="Flange", b=200.0, h=20.0,
                          y_bot=180.0, z_left=0.0),
        ]
        self.result = calculate(self.parts)

    def test_area(self):
        A_expected = 10 * 180 + 200 * 20  # 1800 + 4000 = 5800
        assert_close(self.result.A_total, A_expected, label="T-section area")

    def test_centroid_y(self):
        # yc = (1800 * 90 + 4000 * 190) / 5800
        yc_expected = (1800 * 90 + 4000 * 190) / 5800
        assert_close(self.result.yc, yc_expected, label="T-section yc")

    def test_centroid_z_symmetric(self):
        """T-section is symmetric about z, so zc should be at z = 100 mm."""
        assert_close(self.result.zc, 100.0, tol=0.001, label="T-section zc")

    def test_asymmetric_section_moduli(self):
        """For T-section, Wy_top != Wy_bot because centroid is not at mid-height."""
        assert self.result.Wy_top != self.result.Wy_bot
        # Wy_bot < Wy_top because bottom fiber is further from centroid
        # (centroid is closer to flange for T-section)
        assert self.result.y_bot > self.result.y_top

    def test_Iy_by_hand(self):
        """Verify Iy by manual parallel axis calculation."""
        A_web = 10 * 180
        A_flange = 200 * 20
        A_total = A_web + A_flange
        yc = (A_web * 90 + A_flange * 190) / A_total

        # Web: Iy_local = 10 * 180^3 / 12, dy = 90 - yc
        Iy_web_local = 10 * 180**3 / 12
        dy_web = 90 - yc
        Iy_web = Iy_web_local + A_web * dy_web**2

        # Flange: Iy_local = 200 * 20^3 / 12, dy = 190 - yc
        Iy_flange_local = 200 * 20**3 / 12
        dy_flange = 190 - yc
        Iy_flange = Iy_flange_local + A_flange * dy_flange**2

        Iy_expected = Iy_web + Iy_flange
        assert_close(self.result.Iy, Iy_expected, tol=0.001, label="T-section Iy by hand")


# ---------------------------------------------------------------------------
# Test: L-section (angle)
# ---------------------------------------------------------------------------

class TestLSection:
    """L-section (angle): vertical leg + horizontal leg. Asymmetric in both axes."""

    def setup_method(self):
        # L 100x100x10 (equal angle)
        self.parts = [
            RectanglePart(name="Horizontal leg", b=100.0, h=10.0,
                          y_bot=0.0, z_left=0.0),
            RectanglePart(name="Vertical leg", b=10.0, h=90.0,
                          y_bot=10.0, z_left=0.0),
        ]
        self.result = calculate(self.parts)

    def test_area(self):
        # 100*10 + 10*90 = 1000 + 900 = 1900
        assert_close(self.result.A_total, 1900, label="L-section area")

    def test_centroid_not_at_center(self):
        """L-section centroid should not be at geometric center."""
        # yc = (1000*5 + 900*55) / 1900 = (5000 + 49500) / 1900 = 28.68
        yc_expected = (1000 * 5 + 900 * 55) / 1900
        assert_close(self.result.yc, yc_expected, label="L-section yc")

        # zc = (1000*50 + 900*5) / 1900 = (50000 + 4500) / 1900 = 28.68
        zc_expected = (1000 * 50 + 900 * 5) / 1900
        assert_close(self.result.zc, zc_expected, label="L-section zc")

    def test_equal_angle_symmetry(self):
        """Equal angle: yc should equal zc due to rotational symmetry."""
        assert_close(self.result.yc, self.result.zc, tol=0.001,
                      label="Equal angle yc == zc")


# ---------------------------------------------------------------------------
# Test: Validation
# ---------------------------------------------------------------------------

class TestValidation:
    """Test input validation catches bad data."""

    def test_empty_parts(self):
        err = validate_parts([])
        assert err is not None
        assert "No rectangular parts" in err

    def test_zero_width(self):
        parts = [RectanglePart(name="Bad", b=0, h=10, y_bot=0, z_left=0)]
        err = validate_parts(parts)
        assert err is not None
        assert "width" in err

    def test_negative_height(self):
        parts = [RectanglePart(name="Bad", b=10, h=-5, y_bot=0, z_left=0)]
        err = validate_parts(parts)
        assert err is not None
        assert "height" in err

    def test_duplicate_names(self):
        parts = [
            RectanglePart(name="Flange", b=10, h=10, y_bot=0, z_left=0),
            RectanglePart(name="Flange", b=10, h=10, y_bot=10, z_left=0),
        ]
        err = validate_parts(parts)
        assert err is not None
        assert "Duplicate" in err

    def test_calculate_raises_on_invalid(self):
        with pytest.raises(ValueError):
            calculate([])

    def test_valid_parts(self):
        parts = [RectanglePart(name="OK", b=10, h=10, y_bot=0, z_left=0)]
        err = validate_parts(parts)
        assert err is None


# ---------------------------------------------------------------------------
# Test: Conversion constants
# ---------------------------------------------------------------------------

class TestProductOfInertia:
    """Test I_yz (centrifugal/product moment of inertia) and principal axes."""

    def test_Iyz_zero_for_single_rectangle(self):
        """Single rectangle centered: I_yz = 0."""
        parts = [RectanglePart(name="Rect", b=200.0, h=300.0, y_bot=0.0, z_left=0.0)]
        result = calculate(parts)
        assert abs(result.Iyz) < 1e-6, f"I_yz should be ~0 for single rect, got {result.Iyz}"

    def test_Iyz_zero_for_symmetric_I_beam(self):
        """Doubly-symmetric I-beam: I_yz = 0."""
        parts = [
            RectanglePart(name="Bot fl", b=200.0, h=10.0, y_bot=0.0, z_left=0.0),
            RectanglePart(name="Web", b=6.5, h=170.0, y_bot=10.0, z_left=96.75),
            RectanglePart(name="Top fl", b=200.0, h=10.0, y_bot=180.0, z_left=0.0),
        ]
        result = calculate(parts)
        assert abs(result.Iyz) < 1e-6, f"I_yz should be ~0 for symmetric I-beam, got {result.Iyz}"

    def test_Iyz_nonzero_for_L_section(self):
        """L-section (asymmetric in both axes): I_yz != 0."""
        parts = [
            RectanglePart(name="Horiz", b=100.0, h=10.0, y_bot=0.0, z_left=0.0),
            RectanglePart(name="Vert", b=10.0, h=90.0, y_bot=10.0, z_left=0.0),
        ]
        result = calculate(parts)
        assert abs(result.Iyz) > 1000, f"I_yz should be significant for L-section, got {result.Iyz}"

    def test_principal_axes_invariant(self):
        """I_max + I_min must equal I_y + I_z (trace invariant)."""
        parts = [
            RectanglePart(name="Horiz", b=100.0, h=10.0, y_bot=0.0, z_left=0.0),
            RectanglePart(name="Vert", b=10.0, h=90.0, y_bot=10.0, z_left=0.0),
        ]
        result = calculate(parts)
        assert_close(result.I_max + result.I_min, result.Iy + result.Iz,
                     tol=1e-9, label="I_max + I_min = Iy + Iz")

    def test_principal_axes_symmetric_section(self):
        """For symmetric section, principal axes = centroidal axes (alpha ≈ 0)."""
        parts = [RectanglePart(name="Rect", b=200.0, h=300.0, y_bot=0.0, z_left=0.0)]
        result = calculate(parts)
        # I_max should be the larger of Iy, Iz
        assert_close(result.I_max, max(result.Iy, result.Iz), tol=1e-9,
                     label="I_max for symmetric")
        assert_close(result.I_min, min(result.Iy, result.Iz), tol=1e-9,
                     label="I_min for symmetric")

    def test_Iyz_steiner_parts(self):
        """Each part's Iyz_steiner = A * dy * dz."""
        parts = [
            RectanglePart(name="Horiz", b=100.0, h=10.0, y_bot=0.0, z_left=0.0),
            RectanglePart(name="Vert", b=10.0, h=90.0, y_bot=10.0, z_left=0.0),
        ]
        result = calculate(parts)
        for pr in result.parts:
            expected = pr.A * pr.dy * pr.dz
            assert_close(pr.Iyz_steiner, expected, tol=1e-9,
                         label=f"{pr.name} Iyz_steiner")


class TestGoverningW:
    """Test Wy, Wz (governing = minimum section moduli)."""

    def test_symmetric_section_Wy_equals_both(self):
        """Symmetric section: Wy = Wy_top = Wy_bot."""
        parts = [RectanglePart(name="Rect", b=200.0, h=300.0, y_bot=0.0, z_left=0.0)]
        result = calculate(parts)
        assert_close(result.Wy, result.Wy_top, tol=1e-9, label="Wy symmetric")

    def test_T_section_Wy_is_smaller(self):
        """T-section: Wy = min(Wy_top, Wy_bot)."""
        parts = [
            RectanglePart(name="Web", b=10.0, h=180.0, y_bot=0.0, z_left=95.0),
            RectanglePart(name="Flange", b=200.0, h=20.0, y_bot=180.0, z_left=0.0),
        ]
        result = calculate(parts)
        assert_close(result.Wy, min(result.Wy_top, result.Wy_bot),
                     tol=1e-9, label="Wy T-section")
        assert result.Wy < max(result.Wy_top, result.Wy_bot)


class TestConversions:
    """Verify conversion factor values."""

    def test_mm2_to_cm2(self):
        assert MM2_TO_CM2 == pytest.approx(0.01)

    def test_mm4_to_cm4(self):
        assert MM4_TO_CM4 == pytest.approx(0.0001)
