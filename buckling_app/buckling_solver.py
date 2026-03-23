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
