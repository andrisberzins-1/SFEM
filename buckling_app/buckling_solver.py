"""
buckling_solver.py -- Single source of truth for member capacity calculations.

This module provides strength and buckling checks for steel members
according to Eurocode EC3 / EN 1993-1-1.

app.py must NOT implement any calculations -- all math goes through this module.

Checks performed:
  1. Strength check (tension or compression) -- 3 equivalent methods
  2. Buckling check (compression only) -- both y and z axes independently

Units throughout:
    Forces:             kN (input/output), N (internal where noted)
    Stresses:           MPa (N/mm2)
    Lengths:            m (input), mm (section properties)
    Area:               mm2
    Moment of inertia:  mm4
    Elastic modulus:    MPa (N/mm2)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

E_STEEL_MPA = 200_000.0            # Default elastic modulus for steel (N/mm2)
GAMMA_M0_DEFAULT = 1.0             # Partial safety factor for cross-section resistance
GAMMA_M1_DEFAULT = 1.0             # Partial safety factor for buckling resistance
SLENDERNESS_THRESHOLD = 0.2        # Below this, buckling check may be skipped

# Imperfection factors per buckling curve (EN 1993-1-1 Table 6.1)
IMPERFECTION_FACTORS: dict[str, float] = {
    "a0": 0.13,
    "a": 0.21,
    "b": 0.34,
    "c": 0.49,
    "d": 0.76,
}

# Buckling curve labels for display
BUCKLING_CURVES = list(IMPERFECTION_FACTORS.keys())

# Effective length factors (mu) for common boundary conditions
MU_VALUES: dict[str, float] = {
    "cantilever": 2.0,          # One end fixed, other free
    "pinned_pinned": 1.0,       # Both ends pinned (hinges)
    "fixed_pinned": 0.7,        # One end fixed, other pinned
    "fixed_fixed": 0.5,         # Both ends fixed
}

# Display labels for boundary conditions
MU_LABELS: dict[str, str] = {
    "cantilever": "Cantilever (one fixed, one free) -- \u03bc = 2.0",
    "pinned_pinned": "Pinned-pinned (both hinges) -- \u03bc = 1.0",
    "fixed_pinned": "Fixed-pinned -- \u03bc = 0.7",
    "fixed_fixed": "Fixed-fixed -- \u03bc = 0.5",
}

# Common steel grades: name -> fy (MPa)
STEEL_GRADES: dict[str, float] = {
    "S235": 235.0,
    "S275": 275.0,
    "S355": 355.0,
    "S420": 420.0,
}

# Conversion
KN_TO_N = 1000.0
N_TO_KN = 0.001
M_TO_MM = 1000.0


# ---------------------------------------------------------------------------
# Data classes -- Input
# ---------------------------------------------------------------------------

@dataclass
class MemberInput:
    """Input parameters for a single member capacity check.

    Sign convention for N_Ed:
        Positive = tension
        Negative = compression
    """
    name: str = "Member"
    N_Ed_kN: float = -100.0         # Design axial force (kN)
    A_mm2: float = 2163.0           # Cross-section area (mm2)
    Iy_mm4: float = 3_115_000.0     # Moment of inertia about y-axis (mm4)
    Iz_mm4: float = 3_115_000.0     # Moment of inertia about z-axis (mm4)
    fy_MPa: float = 235.0           # Yield strength (MPa)
    E_MPa: float = E_STEEL_MPA      # Elastic modulus (MPa)
    L_m: float = 6.0                # Member geometric length (m)
    mu_y: float = 1.0               # Effective length factor, y-axis
    mu_z: float = 1.0               # Effective length factor, z-axis
    curve_y: str = "c"              # Buckling curve for y-axis
    curve_z: str = "c"              # Buckling curve for z-axis
    gamma_M0: float = GAMMA_M0_DEFAULT  # Partial safety factor (strength)
    gamma_M1: float = GAMMA_M1_DEFAULT  # Partial safety factor (buckling)


# ---------------------------------------------------------------------------
# Data classes -- Output (step-by-step results)
# ---------------------------------------------------------------------------

@dataclass
class StrengthResult:
    """Step-by-step strength check results (EN 1993-1-1 cl. 6.2.3/6.2.4).

    Shows all three equivalent verification methods for educational purposes.
    """
    is_tension: bool                # True if N_Ed > 0

    N_Ed_kN: float                  # Absolute design force (kN)

    # Method 1: Force comparison
    N_Rd_kN: float                  # Design resistance = A * fy / gamma_M0 (kN)
    force_ok: bool                  # |N_Ed| <= N_Rd

    # Method 2: Stress comparison
    sigma_Ed_MPa: float             # Design stress = |N_Ed| / A (MPa)
    sigma_Rd_MPa: float             # Design resistance stress = fy / gamma_M0 (MPa)
    stress_ok: bool                 # sigma_Ed <= sigma_Rd

    # Method 3: Area comparison
    A_min_mm2: float                # Minimum required area = |N_Ed| * gamma_M0 / fy (mm2)
    A_actual_mm2: float             # Actual area (mm2)
    area_ok: bool                   # A >= A_min

    # Summary
    utilization: float              # |N_Ed| / N_Rd (0 to 1+)
    passed: bool                    # All checks passed


@dataclass
class BucklingAxisResult:
    """Step-by-step buckling check for ONE axis (EN 1993-1-1 cl. 6.3.1).

    Contains all intermediate values so students can follow the calculation.
    """
    axis_label: str                 # "y" or "z"

    # Step 1: Effective length
    L_m: float                      # Geometric length (m)
    mu: float                       # Effective length factor
    L_cr_m: float                   # Effective (buckling) length = mu * L (m)
    L_cr_mm: float                  # Same in mm for formula display

    # Step 2: Section properties used
    I_mm4: float                    # Moment of inertia for this axis (mm4)
    i_mm: float                     # Radius of gyration = sqrt(I/A) (mm)

    # Step 3: Characteristic resistance
    N_Rk_kN: float                  # = A * fy / 1000 (kN)

    # Step 4: Euler critical force
    N_cr_kN: float                  # = pi^2 * E * I / L_cr^2 / 1000 (kN)

    # Step 5: Relative slenderness
    lambda_bar: float               # = sqrt(N_Rk / N_cr) = sqrt(A * fy / N_cr)
    skip_buckling: bool             # True if lambda_bar <= 0.2

    # Step 6-7: Imperfection
    curve: str                      # Buckling curve name (a0, a, b, c, d)
    alpha: float                    # Imperfection factor from table

    # Step 8: Intermediate factor
    Phi: float                      # = 0.5 * [1 + alpha*(lambda_bar - 0.2) + lambda_bar^2]

    # Step 9: Reduction factor
    chi: float                      # = 1 / (Phi + sqrt(Phi^2 - lambda_bar^2)), <= 1.0

    # Step 10: Design buckling resistance
    N_b_Rd_kN: float                # = chi * A * fy / gamma_M1 / 1000 (kN)

    # Step 11: Verification
    N_Ed_kN: float                  # Absolute design compression force (kN)
    utilization: float              # |N_Ed| / N_b_Rd
    passed: bool                    # N_Ed <= N_b_Rd


@dataclass
class MemberCheckResult:
    """Complete check result combining strength and buckling for one member."""
    name: str
    input: MemberInput

    strength: StrengthResult

    # None for tension members (no buckling check needed)
    buckling_y: Optional[BucklingAxisResult]
    buckling_z: Optional[BucklingAxisResult]

    governing_utilization: float    # Maximum utilization across all checks
    governing_check: str            # "strength", "buckling_y", or "buckling_z"
    overall_passed: bool            # All applicable checks passed


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_input(inp: MemberInput) -> Optional[str]:
    """Validate member input. Returns error message string, or None if valid."""
    if inp.A_mm2 <= 0:
        return f"Cross-section area A must be positive, got {inp.A_mm2} mm\u00b2."
    if inp.Iy_mm4 <= 0:
        return f"Moment of inertia Iy must be positive, got {inp.Iy_mm4} mm\u2074."
    if inp.Iz_mm4 <= 0:
        return f"Moment of inertia Iz must be positive, got {inp.Iz_mm4} mm\u2074."
    if inp.fy_MPa <= 0:
        return f"Yield strength fy must be positive, got {inp.fy_MPa} MPa."
    if inp.E_MPa <= 0:
        return f"Elastic modulus E must be positive, got {inp.E_MPa} MPa."
    if inp.L_m <= 0:
        return f"Member length L must be positive, got {inp.L_m} m."
    if inp.mu_y <= 0:
        return f"Effective length factor \u03bcy must be positive, got {inp.mu_y}."
    if inp.mu_z <= 0:
        return f"Effective length factor \u03bcz must be positive, got {inp.mu_z}."
    if inp.gamma_M0 <= 0:
        return f"Safety factor \u03b3M0 must be positive, got {inp.gamma_M0}."
    if inp.gamma_M1 <= 0:
        return f"Safety factor \u03b3M1 must be positive, got {inp.gamma_M1}."
    if inp.curve_y not in IMPERFECTION_FACTORS:
        return (f"Invalid buckling curve for y-axis: '{inp.curve_y}'. "
                f"Must be one of: {', '.join(BUCKLING_CURVES)}.")
    if inp.curve_z not in IMPERFECTION_FACTORS:
        return (f"Invalid buckling curve for z-axis: '{inp.curve_z}'. "
                f"Must be one of: {', '.join(BUCKLING_CURVES)}.")
    if inp.N_Ed_kN == 0:
        return "Design force N_Ed must not be zero."
    return None


# ---------------------------------------------------------------------------
# Strength check (EN 1993-1-1 cl. 6.2.3 tension / cl. 6.2.4 compression)
# ---------------------------------------------------------------------------

def check_strength(inp: MemberInput) -> StrengthResult:
    """Perform strength check using all three equivalent methods.

    Works for both tension and compression members.
    """
    is_tension = inp.N_Ed_kN > 0
    N_Ed_abs_kN = abs(inp.N_Ed_kN)
    N_Ed_abs_N = N_Ed_abs_kN * KN_TO_N

    # Method 1: Force comparison
    N_Rd_N = inp.A_mm2 * inp.fy_MPa / inp.gamma_M0
    N_Rd_kN = N_Rd_N * N_TO_KN
    force_ok = N_Ed_abs_kN <= N_Rd_kN

    # Method 2: Stress comparison
    sigma_Ed = N_Ed_abs_N / inp.A_mm2       # MPa
    sigma_Rd = inp.fy_MPa / inp.gamma_M0    # MPa
    stress_ok = sigma_Ed <= sigma_Rd

    # Method 3: Area comparison
    A_min = N_Ed_abs_N * inp.gamma_M0 / inp.fy_MPa   # mm2
    area_ok = inp.A_mm2 >= A_min

    # Utilization
    utilization = N_Ed_abs_kN / N_Rd_kN if N_Rd_kN > 0 else float("inf")
    passed = force_ok  # All three methods are equivalent

    return StrengthResult(
        is_tension=is_tension,
        N_Ed_kN=N_Ed_abs_kN,
        N_Rd_kN=N_Rd_kN,
        force_ok=force_ok,
        sigma_Ed_MPa=sigma_Ed,
        sigma_Rd_MPa=sigma_Rd,
        stress_ok=stress_ok,
        A_min_mm2=A_min,
        A_actual_mm2=inp.A_mm2,
        area_ok=area_ok,
        utilization=utilization,
        passed=passed,
    )


# ---------------------------------------------------------------------------
# Buckling check for one axis (EN 1993-1-1 cl. 6.3.1)
# ---------------------------------------------------------------------------

def check_buckling_axis(inp: MemberInput, axis: str) -> BucklingAxisResult:
    """Perform buckling check for one axis.

    Args:
        inp: Member input data.
        axis: "y" or "z" -- determines which I and mu to use.

    Returns:
        BucklingAxisResult with all intermediate values.
    """
    if axis == "y":
        I_mm4 = inp.Iy_mm4
        mu = inp.mu_y
        curve = inp.curve_y
    elif axis == "z":
        I_mm4 = inp.Iz_mm4
        mu = inp.mu_z
        curve = inp.curve_z
    else:
        raise ValueError(f"axis must be 'y' or 'z', got '{axis}'")

    N_Ed_abs_kN = abs(inp.N_Ed_kN)

    # Step 1: Effective length
    L_cr_m = mu * inp.L_m
    L_cr_mm = L_cr_m * M_TO_MM

    # Step 2: Radius of gyration
    i_mm = math.sqrt(I_mm4 / inp.A_mm2)

    # Step 3: Characteristic compressive resistance
    N_Rk_N = inp.A_mm2 * inp.fy_MPa
    N_Rk_kN = N_Rk_N * N_TO_KN

    # Step 4: Euler critical force
    N_cr_N = math.pi ** 2 * inp.E_MPa * I_mm4 / (L_cr_mm ** 2)
    N_cr_kN = N_cr_N * N_TO_KN

    # Step 5: Relative slenderness
    lambda_bar = math.sqrt(N_Rk_N / N_cr_N)
    skip_buckling = lambda_bar <= SLENDERNESS_THRESHOLD

    # Step 6-7: Imperfection factor
    alpha = IMPERFECTION_FACTORS[curve]

    # Step 8: Intermediate factor Phi
    Phi = 0.5 * (1.0 + alpha * (lambda_bar - 0.2) + lambda_bar ** 2)

    # Step 9: Reduction factor chi
    discriminant = Phi ** 2 - lambda_bar ** 2
    if discriminant < 0:
        # Theoretically shouldn't happen, but guard against numerical issues
        chi = 0.0
    else:
        chi = 1.0 / (Phi + math.sqrt(discriminant))
    chi = min(chi, 1.0)  # chi cannot exceed 1.0

    # Step 10: Design buckling resistance
    N_b_Rd_N = chi * inp.A_mm2 * inp.fy_MPa / inp.gamma_M1
    N_b_Rd_kN = N_b_Rd_N * N_TO_KN

    # Step 11: Verification
    utilization = N_Ed_abs_kN / N_b_Rd_kN if N_b_Rd_kN > 0 else float("inf")
    passed = N_Ed_abs_kN <= N_b_Rd_kN

    return BucklingAxisResult(
        axis_label=axis,
        L_m=inp.L_m,
        mu=mu,
        L_cr_m=L_cr_m,
        L_cr_mm=L_cr_mm,
        I_mm4=I_mm4,
        i_mm=i_mm,
        N_Rk_kN=N_Rk_kN,
        N_cr_kN=N_cr_kN,
        lambda_bar=lambda_bar,
        skip_buckling=skip_buckling,
        curve=curve,
        alpha=alpha,
        Phi=Phi,
        chi=chi,
        N_b_Rd_kN=N_b_Rd_kN,
        N_Ed_kN=N_Ed_abs_kN,
        utilization=utilization,
        passed=passed,
    )


# ---------------------------------------------------------------------------
# Complete member check
# ---------------------------------------------------------------------------

def check_member(inp: MemberInput) -> MemberCheckResult:
    """Perform complete member capacity check: strength + buckling.

    For tension members: strength check only.
    For compression members: strength check + buckling check on both axes.
    The governing check is the one with the highest utilization ratio.
    """
    strength = check_strength(inp)

    buckling_y: Optional[BucklingAxisResult] = None
    buckling_z: Optional[BucklingAxisResult] = None

    is_compression = inp.N_Ed_kN < 0

    if is_compression:
        buckling_y = check_buckling_axis(inp, "y")
        buckling_z = check_buckling_axis(inp, "z")

    # Determine governing check
    governing_utilization = strength.utilization
    governing_check = "strength"

    if buckling_y is not None and buckling_y.utilization > governing_utilization:
        governing_utilization = buckling_y.utilization
        governing_check = "buckling_y"

    if buckling_z is not None and buckling_z.utilization > governing_utilization:
        governing_utilization = buckling_z.utilization
        governing_check = "buckling_z"

    # Overall pass: all applicable checks must pass
    overall_passed = strength.passed
    if buckling_y is not None:
        overall_passed = overall_passed and buckling_y.passed
    if buckling_z is not None:
        overall_passed = overall_passed and buckling_z.passed

    return MemberCheckResult(
        name=inp.name,
        input=inp,
        strength=strength,
        buckling_y=buckling_y,
        buckling_z=buckling_z,
        governing_utilization=governing_utilization,
        governing_check=governing_check,
        overall_passed=overall_passed,
    )


# ---------------------------------------------------------------------------
# Buckling curve data for plotting
# ---------------------------------------------------------------------------

def buckling_curve_points(
    curve: str,
    lambda_max: float = 3.0,
    n_points: int = 200,
) -> tuple[list[float], list[float]]:
    """Generate (lambda_bar, chi) points for plotting a buckling curve.

    Args:
        curve: Buckling curve name (a0, a, b, c, d).
        lambda_max: Maximum lambda_bar value.
        n_points: Number of points to generate.

    Returns:
        Tuple of (lambda_bar_list, chi_list).
    """
    alpha = IMPERFECTION_FACTORS[curve]
    lambdas: list[float] = []
    chis: list[float] = []

    for i in range(n_points + 1):
        lam = i * lambda_max / n_points
        if lam < 1e-10:
            chi = 1.0
        else:
            phi = 0.5 * (1.0 + alpha * (lam - 0.2) + lam ** 2)
            disc = phi ** 2 - lam ** 2
            if disc < 0:
                chi = 0.0
            else:
                chi = 1.0 / (phi + math.sqrt(disc))
            chi = min(chi, 1.0)
        lambdas.append(lam)
        chis.append(chi)

    return lambdas, chis


# ---------------------------------------------------------------------------
# LaTeX step builder
# ---------------------------------------------------------------------------

def build_latex_steps(
    result: MemberCheckResult,
    inp: MemberInput,
    skip_buckling_if_stocky: bool = False,
) -> list[tuple[str, str]]:
    """Build step-by-step LaTeX strings for strength + buckling check.

    Returns a list of (heading, latex_expression) tuples.
    Empty heading means continuation of the previous section.

    When skip_buckling_if_stocky=True:
    - Tension: shows strength check only.
    - Compression with lambda_bar <= 0.2 (all axes): strength only, note
      that buckling is not required.
    - Compression with lambda_bar > 0.2 (any axis): buckling only
      (strength is skipped — buckling governs).

    When Iy == Iz and mu_y == mu_z and curve_y == curve_z (single-axis mode):
    emits one buckling check section without axis subscripts.
    """
    steps: list[tuple[str, str]] = []
    sr = result.strength
    is_compression = not sr.is_tension

    # --- Task A: determine what to show ---
    show_strength = True
    if skip_buckling_if_stocky and is_compression:
        any_non_stocky = any(
            bax is not None and not bax.skip_buckling
            for bax in (result.buckling_y, result.buckling_z)
        )
        if any_non_stocky:
            show_strength = False  # buckling governs, skip strength

    # --- Task C: single-axis detection ---
    single_axis = (
        is_compression
        and inp.Iy_mm4 == inp.Iz_mm4
        and inp.mu_y == inp.mu_z
        and inp.curve_y == inp.curve_z
    )

    # --- Strength check ---
    if show_strength:
        force_type = "tension" if sr.is_tension else "compression"
        steps.append((
            f"Strength Check (EN 1993-1-1) \u2014 {force_type}",
            "",
        ))
        steps.append((
            f"Force direction: N_{{Ed}} = {inp.N_Ed_kN:+.1f} kN \u2192 {force_type}",
            "",
        ))

        # Method 1: Force comparison
        check_sym = r"\leq" if sr.force_ok else r">"
        steps.append((
            "Method 1: Force comparison",
            r"N_{Rd} = \frac{A \cdot f_y}{\gamma_{M0}} = "
            r"\frac{" + f"{inp.A_mm2:.0f}" + r" \cdot " + f"{inp.fy_MPa:.0f}"
            + r"}{" + f"{inp.gamma_M0:.2f}" + r"} = "
            + f"{sr.N_Rd_kN * KN_TO_N:,.0f}" + r" \text{ N} = "
            + f"{sr.N_Rd_kN:,.1f}" + r" \text{ kN}",
        ))
        verdict = "OK!" if sr.force_ok else "FAIL"
        steps.append((
            "",
            r"|N_{Ed}| = " + f"{sr.N_Ed_kN:,.1f}"
            + r" \text{ kN} " + check_sym + r" N_{Rd} = "
            + f"{sr.N_Rd_kN:,.1f}" + r" \text{ kN}"
            + r" \quad \rightarrow \text{ " + verdict + r"}",
        ))
        steps.append((
            "",
            r"\text{Utilization: } \frac{|N_{Ed}|}{N_{Rd}} = \frac{"
            + f"{sr.N_Ed_kN:,.1f}" + r"}{" + f"{sr.N_Rd_kN:,.1f}" + r"} = "
            + f"{sr.utilization * 100:.1f}" + r"\%",
        ))

        # Method 2: Stress comparison
        check_sym = r"\leq" if sr.stress_ok else r">"
        verdict = "OK!" if sr.stress_ok else "FAIL"
        steps.append((
            "Method 2: Stress comparison",
            r"\sigma_{Ed} = \frac{|N_{Ed}|}{A} = \frac{"
            + f"{sr.N_Ed_kN * KN_TO_N:,.0f}" + r"}{" + f"{inp.A_mm2:.0f}" + r"} = "
            + f"{sr.sigma_Ed_MPa:.1f}" + r" \text{ MPa}",
        ))
        steps.append((
            "",
            r"\sigma_{Ed} = " + f"{sr.sigma_Ed_MPa:.1f}"
            + r" \text{ MPa} " + check_sym
            + r" \frac{f_y}{\gamma_{M0}} = "
            + f"{sr.sigma_Rd_MPa:.1f}" + r" \text{ MPa}"
            + r" \quad \rightarrow \text{ " + verdict + r"}",
        ))

        # Method 3: Area comparison
        check_sym = r"\geq" if sr.area_ok else r"<"
        verdict = "OK!" if sr.area_ok else "FAIL"
        steps.append((
            "Method 3: Area comparison",
            r"A_{min} = \frac{|N_{Ed}| \cdot \gamma_{M0}}{f_y} = \frac{"
            + f"{sr.N_Ed_kN * KN_TO_N:,.0f}" + r" \cdot " + f"{inp.gamma_M0:.2f}"
            + r"}{" + f"{inp.fy_MPa:.0f}" + r"} = "
            + f"{sr.A_min_mm2:,.1f}" + r" \text{ mm}^2",
        ))
        steps.append((
            "",
            r"A = " + f"{inp.A_mm2:,.1f}"
            + r" \text{ mm}^2 " + check_sym + r" A_{min} = "
            + f"{sr.A_min_mm2:,.1f}" + r" \text{ mm}^2"
            + r" \quad \rightarrow \text{ " + verdict + r"}",
        ))

    # --- Buckling check ---
    if is_compression:
        # Single-axis: show only y-axis check (identical to z)
        axes_to_show = [result.buckling_y]
        if not single_axis:
            axes_to_show.append(result.buckling_z)

        for bax in axes_to_show:
            if bax is None:
                continue

            # Build subscript labels (omit axis for single-axis mode)
            if single_axis:
                I_s = "I"
                mu_s = r"\mu"
                Lcr_s = "L_{cr}"
                Ncr_s = "N_{cr}"
                lam_s = r"\bar{\lambda}"
                Phi_s = r"\Phi"
                chi_s = r"\chi"
                NbRd_s = "N_{b,Rd}"
                heading_sfx = ""
            else:
                a = bax.axis_label
                I_s = f"I_{{{a}}}"
                mu_s = rf"\mu_{{{a}}}"
                Lcr_s = f"L_{{cr,{a}}}"
                Ncr_s = f"N_{{cr,{a}}}"
                lam_s = rf"\bar{{\lambda}}_{{{a}}}"
                Phi_s = rf"\Phi_{{{a}}}"
                chi_s = rf"\chi_{{{a}}}"
                NbRd_s = f"N_{{b,Rd,{a}}}"
                heading_sfx = f" \u2014 {a}-axis"

            steps.append((
                f"Buckling Check{heading_sfx} (EN 1993-1-1 cl. 6.3.1)",
                "",
            ))

            # Step 1: Effective length
            steps.append((
                "Step 1: Effective length",
                Lcr_s + r" = " + mu_s + r" \cdot L = "
                + f"{bax.mu:.1f}" + r" \cdot " + f"{bax.L_m:.2f}" + r" = "
                + f"{bax.L_cr_m:.2f}" + r" \text{ m} = "
                + f"{bax.L_cr_mm:.0f}" + r" \text{ mm}",
            ))

            # Step 2: Characteristic compressive resistance
            steps.append((
                "Step 2: Characteristic compressive resistance",
                r"N_{Rk} = A \cdot f_y = " + f"{inp.A_mm2:.0f}" + r" \cdot "
                + f"{inp.fy_MPa:.0f}"
                + r" = " + f"{bax.N_Rk_kN * KN_TO_N:,.0f}" + r" \text{ N} = "
                + f"{bax.N_Rk_kN:,.1f}" + r" \text{ kN}",
            ))

            # Step 3: Euler critical force
            steps.append((
                "Step 3: Euler critical force",
                Ncr_s + r" = \frac{\pi^2 \cdot E \cdot " + I_s
                + r"}{" + Lcr_s + r"^2} = "
                + r"\frac{\pi^2 \cdot " + f"{inp.E_MPa:,.0f}" + r" \cdot "
                + f"{bax.I_mm4:,.0f}" + r"}{" + f"{bax.L_cr_mm:.0f}" + r"^2} = "
                + f"{bax.N_cr_kN * KN_TO_N:,.0f}" + r" \text{ N} = "
                + f"{bax.N_cr_kN:,.1f}" + r" \text{ kN}",
            ))

            # Step 4: Relative slenderness
            steps.append((
                "Step 4: Relative slenderness",
                lam_s + r" = \sqrt{\frac{N_{Rk}}{" + Ncr_s + r"}} = "
                + r"\sqrt{\frac{" + f"{bax.N_Rk_kN:,.1f}" + r"}{" + f"{bax.N_cr_kN:,.1f}"
                + r"}} = " + f"{bax.lambda_bar:.3f}",
            ))

            # Skip buckling if stocky
            if skip_buckling_if_stocky and bax.skip_buckling:
                steps.append((
                    "",
                    lam_s + r" = " + f"{bax.lambda_bar:.3f}"
                    + r" \leq " + f"{SLENDERNESS_THRESHOLD}"
                    + r" \quad \Rightarrow \quad "
                    + r"\text{Buckling check not required (stocky member).}",
                ))
                steps.append((
                    "",
                    r"\text{Member verified by strength check only.}",
                ))
                continue

            if bax.skip_buckling:
                steps.append((
                    "",
                    lam_s + r" = " + f"{bax.lambda_bar:.3f}"
                    + r" \leq " + f"{SLENDERNESS_THRESHOLD}"
                    + r" \quad \text{(stocky member \u2014 continuing for educational purposes)}",
                ))

            # Step 5: Buckling curve selection
            steps.append((
                "Step 5: Buckling curve selection",
                r"\text{Buckling curve: }" + f'\\text{{"{bax.curve}"}}'
                + r" \quad \rightarrow \quad \alpha = " + f"{bax.alpha}",
            ))

            # Step 6: Intermediate factor Φ
            steps.append((
                "Step 6: Intermediate factor \u03a6",
                Phi_s + r" = 0.5 \cdot \left[1 + \alpha \cdot ("
                + lam_s + r" - 0.2) + " + lam_s + r"^2\right]",
            ))
            steps.append((
                "",
                Phi_s + r" = 0.5 \cdot \left[1 + "
                + f"{bax.alpha}" + r" \cdot (" + f"{bax.lambda_bar:.3f}"
                + r" - 0.2) + " + f"{bax.lambda_bar:.3f}" + r"^2\right] = "
                + f"{bax.Phi:.3f}",
            ))

            # Step 7: Reduction factor χ
            steps.append((
                "Step 7: Reduction factor \u03c7",
                chi_s + r" = \frac{1}{" + Phi_s + r" + \sqrt{" + Phi_s + r"^2 - "
                + lam_s + r"^2}} = "
                + r"\frac{1}{" + f"{bax.Phi:.3f}" + r" + \sqrt{"
                + f"{bax.Phi:.3f}" + r"^2 - " + f"{bax.lambda_bar:.3f}"
                + r"^2}} = " + f"{bax.chi:.3f}",
            ))

            # Step 8: Design buckling resistance
            steps.append((
                "Step 8: Design buckling resistance",
                NbRd_s + r" = \frac{" + chi_s
                + r" \cdot A \cdot f_y}{\gamma_{M1}} = "
                + r"\frac{" + f"{bax.chi:.3f}" + r" \cdot " + f"{inp.A_mm2:.0f}"
                + r" \cdot " + f"{inp.fy_MPa:.0f}" + r"}{" + f"{inp.gamma_M1:.2f}"
                + r"} = " + f"{bax.N_b_Rd_kN * KN_TO_N:,.0f}" + r" \text{ N} = "
                + f"{bax.N_b_Rd_kN:,.1f}" + r" \text{ kN}",
            ))

            # Step 9: Verification
            check_sym = r"\leq" if bax.passed else r">"
            verdict = "OK!" if bax.passed else "FAIL"
            steps.append((
                "Step 9: Verification",
                r"|N_{Ed}| = " + f"{bax.N_Ed_kN:,.1f}" + r" \text{ kN} "
                + check_sym + r" " + NbRd_s + r" = "
                + f"{bax.N_b_Rd_kN:,.1f}" + r" \text{ kN}"
                + r" \quad \rightarrow \text{ " + verdict + r"}",
            ))
            steps.append((
                "",
                r"\text{Utilization: } \frac{|N_{Ed}|}{" + NbRd_s
                + r"} = \frac{" + f"{bax.N_Ed_kN:,.1f}"
                + r"}{" + f"{bax.N_b_Rd_kN:,.1f}" + r"} = "
                + f"{bax.utilization * 100:.1f}" + r"\%",
            ))

    # --- Conclusion ---
    gov_label = result.governing_check.replace("_", " ")
    if single_axis:
        gov_label = gov_label.replace("buckling y", "buckling").replace(
            "buckling z", "buckling"
        )
    if result.overall_passed:
        steps.append((
            "Conclusion",
            r"\text{Member passes all checks. Governing: "
            + gov_label + r" at "
            + f"{result.governing_utilization * 100:.1f}" + r"\% utilization.}",
        ))
    else:
        steps.append((
            "Conclusion",
            r"\text{Member FAILS. Governing: "
            + gov_label + r" at "
            + f"{result.governing_utilization * 100:.1f}" + r"\% utilization.}",
        ))

    return steps


# ---------------------------------------------------------------------------
# HTML rendering for LaTeX steps
# ---------------------------------------------------------------------------

def _pass_fail_html(passed: bool) -> str:
    """Plain HTML pass/fail badge (no Streamlit dependency)."""
    if passed:
        return '<span class="report-pass">✅ PASS</span>'
    return '<span class="report-fail">❌ FAIL</span>'


def _utilization_class(util: float) -> str:
    """CSS class for utilization color: pass / warn / fail."""
    if util <= 0.8:
        return "report-pass"
    elif util <= 1.0:
        return "report-warn"
    return "report-fail"


def build_summary_html(
    result: MemberCheckResult,
    inp: MemberInput,
    member_name: str,
    timestamp: str = "",
) -> str:
    """Build the input + results summary block for the HTML report.

    Mirrors the on-screen "Results Summary" block plus a compact input
    table (geometry, section, material, boundary conditions). Returned
    HTML is intended to be passed to ``render_latex_html`` via the
    ``intro_html`` parameter.
    """
    # --- Detect single-axis mode (both axes identical) ---
    single_axis = (
        result.buckling_y is not None
        and result.buckling_z is not None
        and inp.Iy_mm4 == inp.Iz_mm4
        and inp.mu_y == inp.mu_z
        and inp.curve_y == inp.curve_z
    )

    # --- Meta line ---
    name_label = member_name.strip() or "(unnamed)"
    meta_parts = [f"Member: <b>{name_label}</b>"]
    if timestamp:
        meta_parts.append(f"Generated: {timestamp}")
    meta_html = " &nbsp;|&nbsp; ".join(meta_parts)

    # --- Input table ---
    input_rows = [
        ("N<sub>Ed</sub>", f"{inp.N_Ed_kN:+.2f} kN",
         "tension" if inp.N_Ed_kN > 0 else "compression"),
        ("L", f"{inp.L_m:.3f} m", "geometric length"),
        ("A", f"{inp.A_mm2:,.1f} mm²", "cross-section area"),
        ("I<sub>y</sub>", f"{inp.Iy_mm4:,.0f} mm⁴", "moment of inertia (y)"),
        ("I<sub>z</sub>", f"{inp.Iz_mm4:,.0f} mm⁴", "moment of inertia (z)"),
        ("f<sub>y</sub>", f"{inp.fy_MPa:.0f} MPa", "yield strength"),
        ("E", f"{inp.E_MPa:,.0f} MPa", "Young's modulus"),
        ("μ<sub>y</sub> / μ<sub>z</sub>",
         f"{inp.mu_y} / {inp.mu_z}",
         "effective length factors"),
        ("Curve y / z",
         f"{inp.curve_y} / {inp.curve_z}",
         "buckling curves (EN 1993-1-1 Table 6.1)"),
        ("γ<sub>M0</sub> / γ<sub>M1</sub>",
         f"{inp.gamma_M0} / {inp.gamma_M1}",
         "partial safety factors"),
    ]
    input_table = (
        '<table class="report-table">'
        '<tr><th>Symbol</th><th>Value</th><th>Description</th></tr>'
        + "".join(
            f"<tr><td>{sym}</td><td>{val}</td><td>{desc}</td></tr>"
            for sym, val, desc in input_rows
        )
        + "</table>"
    )

    # --- Direction note ---
    if result.strength.is_tension:
        direction_html = (
            f"<p><b>N<sub>Ed</sub> = {inp.N_Ed_kN:+.1f} kN</b> "
            "&rarr; member is in <b>TENSION</b>. Only strength check required.</p>"
        )
    else:
        direction_html = (
            f"<p><b>N<sub>Ed</sub> = {inp.N_Ed_kN:+.1f} kN</b> "
            "&rarr; member is in <b>COMPRESSION</b>. "
            "Strength + buckling checks required.</p>"
        )

    # --- Utilization summary lines ---
    lines: list[str] = []

    sr = result.strength
    util_cls = _utilization_class(sr.utilization)
    lines.append(
        f"<b>Strength check</b>: N<sub>Rd</sub> = {sr.N_Rd_kN:,.1f} kN, "
        f'utilization = <span class="{util_cls}">'
        f"{sr.utilization * 100:.1f}%</span> {_pass_fail_html(sr.passed)}"
    )

    if single_axis and result.buckling_y is not None:
        by = result.buckling_y
        util_cls = _utilization_class(by.utilization)
        skip_note = " (skip: λ̄ ≤ 0.2)" if by.skip_buckling else ""
        lines.append(
            f"<b>Buckling</b>: χ = {by.chi:.3f}, "
            f"N<sub>b,Rd</sub> = {by.N_b_Rd_kN:,.1f} kN, "
            f'utilization = <span class="{util_cls}">'
            f"{by.utilization * 100:.1f}%</span> "
            f"{_pass_fail_html(by.passed)}{skip_note}"
        )
    else:
        if result.buckling_y is not None:
            by = result.buckling_y
            util_cls = _utilization_class(by.utilization)
            skip_note = " (skip: λ̄ ≤ 0.2)" if by.skip_buckling else ""
            lines.append(
                f"<b>Buckling y-axis</b>: χ<sub>y</sub> = {by.chi:.3f}, "
                f"N<sub>b,Rd,y</sub> = {by.N_b_Rd_kN:,.1f} kN, "
                f'utilization = <span class="{util_cls}">'
                f"{by.utilization * 100:.1f}%</span> "
                f"{_pass_fail_html(by.passed)}{skip_note}"
            )
        if result.buckling_z is not None:
            bz = result.buckling_z
            util_cls = _utilization_class(bz.utilization)
            skip_note = " (skip: λ̄ ≤ 0.2)" if bz.skip_buckling else ""
            lines.append(
                f"<b>Buckling z-axis</b>: χ<sub>z</sub> = {bz.chi:.3f}, "
                f"N<sub>b,Rd,z</sub> = {bz.N_b_Rd_kN:,.1f} kN, "
                f'utilization = <span class="{util_cls}">'
                f"{bz.utilization * 100:.1f}%</span> "
                f"{_pass_fail_html(bz.passed)}{skip_note}"
            )

    # Governing
    gov_cls = _utilization_class(result.governing_utilization)
    gov_label = result.governing_check.replace("_", " ")
    if single_axis:
        gov_label = (
            gov_label.replace("buckling y", "buckling")
                     .replace("buckling z", "buckling")
        )
    lines.append(
        f"<br><b>Governing check</b>: <b>{gov_label}</b>, "
        f'utilization = <span class="{gov_cls}" style="font-size:1.1em;">'
        f"{result.governing_utilization * 100:.1f}%</span> "
        f"{_pass_fail_html(result.overall_passed)}"
    )

    summary_block = (
        '<div class="report-summary">'
        + "<br>".join(lines)
        + "</div>"
    )

    return (
        f'<div class="report-meta">{meta_html}</div>\n'
        '<h3>Member input</h3>\n'
        + input_table
        + '\n<h3>Results summary</h3>\n'
        + direction_html
        + summary_block
    )


def figure_to_img_html(fig, alt: str = "figure") -> str:
    """Encode a Plotly figure as a base64 PNG ``<img>`` tag.

    Returns empty string if image export (kaleido) is unavailable.
    """
    import base64
    try:
        png_bytes = fig.to_image(format="png", scale=2)
    except Exception:
        return ""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return (
        '<div class="report-image">'
        f'<img src="data:image/png;base64,{b64}" alt="{alt}">'
        '</div>'
    )


def render_latex_html(
    title: str,
    steps: list[tuple[str, str]],
    intro_html: str = "",
) -> str:
    """Render a self-contained HTML report with KaTeX-rendered LaTeX.

    The returned HTML opens in any browser and can be printed to PDF
    (browser print dialog -> "Save as PDF").

    Args:
        title: Report title shown as ``<h2>``.
        steps: List of ``(heading, latex)`` tuples for the calculation steps.
        intro_html: Optional HTML inserted between the title and the steps
            (e.g. input table, results summary, embedded chart). Pass an
            empty string to keep the bare-steps layout.
    """
    body_lines = [f"<h2>{title}</h2>"]
    if intro_html:
        body_lines.append(intro_html)
    if steps:
        body_lines.append('<h2 class="section-heading">Step-by-step calculation</h2>')
    for heading, latex_str in steps:
        if heading:
            body_lines.append(f"<h3>{heading}</h3>")
        if latex_str:
            body_lines.append(f"<p>$${latex_str}$$</p>")
    body = "\n".join(body_lines)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="UTF-8">\n'
        f"<title>{title}</title>\n"
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">\n'
        '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>\n'
        '<script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>\n'
        "<style>\n"
        "  body { font-family: sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; line-height: 1.6; color: #222; }\n"
        "  h2 { border-bottom: 2px solid #333; padding-bottom: 0.3em; margin-top: 1.6em; }\n"
        "  h2:first-of-type { margin-top: 0; }\n"
        "  h3 { margin-top: 1.5em; color: #333; }\n"
        "  .katex-display { text-align: left !important; margin: 0.5em 0 !important; }\n"
        "  .report-summary { background: #f7f7f9; border-left: 4px solid #4a76b8; padding: 0.8em 1.2em; margin: 1em 0; line-height: 1.9; font-size: 0.95em; }\n"
        "  .report-summary b { color: #1a3050; }\n"
        "  .report-image { text-align: center; margin: 1em 0; }\n"
        "  .report-image img { max-width: 100%; height: auto; }\n"
        "  .report-meta { color: #666; font-size: 0.9em; margin-bottom: 1em; }\n"
        "  .report-pass { color: #28a745; font-weight: bold; }\n"
        "  .report-fail { color: #dc3545; font-weight: bold; }\n"
        "  .report-warn { color: #b78a00; font-weight: bold; }\n"
        "  table.report-table { border-collapse: collapse; margin: 0.6em 0; font-size: 0.95em; }\n"
        "  table.report-table td, table.report-table th { border: 1px solid #ccc; padding: 4px 10px; text-align: left; }\n"
        "  table.report-table th { background: #eef; }\n"
        "  @media print {\n"
        "    body { max-width: 100%; margin: 0; padding: 0 0.5cm; font-size: 11pt; }\n"
        "    h2 { page-break-after: avoid; }\n"
        "    h3 { page-break-after: avoid; }\n"
        "    p { page-break-inside: avoid; }\n"
        "    .report-summary { page-break-inside: avoid; }\n"
        "    .report-image { page-break-inside: avoid; }\n"
        "  }\n"
        "</style>\n</head>\n<body>\n"
        f"{body}\n"
        "<script>\n"
        '  renderMathInElement(document.body, {\n'
        '    delimiters: [{ left: "$$", right: "$$", display: true }],\n'
        "    throwOnError: false,\n"
        "  });\n"
        "</script>\n</body>\n</html>"
    )
