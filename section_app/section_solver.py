"""
section_solver.py — Single source of truth for cross-section property calculations.

This module provides analytical calculation of composite cross-section properties
by decomposing the section into rectangles and applying the parallel axis theorem
(Steiner's theorem) step by step.

app.py must NOT implement any calculations — all math goes through this module.

Units throughout:
    Widths/heights:     mm
    Area:               mm²
    Moment of inertia:  mm⁴
    Section modulus:     mm³
    Radius of gyration:  mm
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Conversion factors
# ---------------------------------------------------------------------------

MM2_TO_CM2 = 1e-2      # 1 mm² = 0.01 cm²
MM4_TO_CM4 = 1e-4      # 1 mm⁴ = 0.0001 cm⁴
MM3_TO_CM3 = 1e-3      # 1 mm³ = 0.001 cm³


# ---------------------------------------------------------------------------
# Data classes — Input
# ---------------------------------------------------------------------------

@dataclass
class RectanglePart:
    """A single rectangular component of a composite cross-section.

    Coordinates are absolute, measured from a reference origin (typically
    the bottom-left corner of the bounding box).
    """
    name: str       # e.g. "Top flange", "Web"
    b: float        # width (mm)
    h: float        # height (mm)
    y_bot: float    # y-coordinate of bottom edge (mm)
    z_left: float   # z-coordinate of left edge (mm)


# ---------------------------------------------------------------------------
# Data classes — Output (step-by-step results)
# ---------------------------------------------------------------------------

@dataclass
class PartResult:
    """Calculation results for a single rectangular component.

    Contains all intermediate values needed to show the step-by-step
    parallel axis theorem calculation to students.
    """
    name: str
    b: float            # width (mm)
    h: float            # height (mm)
    A: float            # area = b * h (mm²)
    yc: float           # centroid y-coordinate (mm)
    zc: float           # centroid z-coordinate (mm)
    Iy_local: float     # b * h³ / 12 — about own centroid (mm⁴)
    Iz_local: float     # h * b³ / 12 — about own centroid (mm⁴)
    dy: float           # yc_part - yc_composite (mm)
    dz: float           # zc_part - zc_composite (mm)
    Iy_steiner: float   # A * dy² — parallel axis term (mm⁴)
    Iz_steiner: float   # A * dz² — parallel axis term (mm⁴)
    Iy_total: float     # Iy_local + Iy_steiner (mm⁴)
    Iz_total: float     # Iz_local + Iz_steiner (mm⁴)
    Iyz_steiner: float  # A * dy * dz — product of inertia Steiner term (mm⁴)


@dataclass
class SectionResult:
    """Complete cross-section calculation results with step-by-step records.

    The `parts` list contains one PartResult per rectangle, allowing the UI
    to display the full parallel axis theorem calculation process.
    """
    parts: list[PartResult]

    # Composite properties
    A_total: float      # total area (mm²)
    yc: float           # composite centroid y (mm)
    zc: float           # composite centroid z (mm)

    # Moments of inertia about centroidal axes
    Iy: float           # mm⁴ (bending about y-axis, resistance to vertical loads)
    Iz: float           # mm⁴ (bending about z-axis)

    # Extreme fiber distances
    y_top: float        # distance from centroid to top fiber (mm)
    y_bot: float        # distance from centroid to bottom fiber (mm)
    z_left: float       # distance from centroid to left fiber (mm)
    z_right: float      # distance from centroid to right fiber (mm)

    # Section moduli
    Wy_top: float       # Iy / y_top (mm³)
    Wy_bot: float       # Iy / y_bot (mm³)
    Wz_left: float      # Iz / z_left (mm³)
    Wz_right: float     # Iz / z_right (mm³)

    # Radii of gyration
    iy: float           # sqrt(Iy / A) (mm)
    iz: float           # sqrt(Iz / A) (mm)

    # Product of inertia (centrifugal moment)
    Iyz: float          # mm⁴ — Σ(A_i * dy_i * dz_i)

    # Principal axes
    I_max: float        # mm⁴ — maximum principal moment of inertia
    I_min: float        # mm⁴ — minimum principal moment of inertia
    alpha_rad: float    # radians — rotation angle of principal axes
    alpha_deg: float    # degrees — rotation angle of principal axes
    axes_coincide: bool # True if principal axes ≈ centroidal axes (Iyz ≈ 0)

    # Governing section moduli (minimum values)
    Wy: float           # min(Wy_top, Wy_bot) (mm³)
    Wz: float           # min(Wz_left, Wz_right) (mm³)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_parts(parts: list[RectanglePart]) -> Optional[str]:
    """Validate input parts. Returns error message string, or None if valid."""
    if not parts:
        return "No rectangular parts defined. Add at least one rectangle."

    for i, p in enumerate(parts):
        label = p.name or f"Part {i + 1}"
        if p.b <= 0:
            return f"{label}: width (b) must be positive, got {p.b} mm."
        if p.h <= 0:
            return f"{label}: height (h) must be positive, got {p.h} mm."

    # Check for duplicate names
    names = [p.name for p in parts if p.name]
    if len(names) != len(set(names)):
        return "Duplicate part names found. Each part must have a unique name."

    return None


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def calculate(parts: list[RectanglePart]) -> SectionResult:
    """Calculate composite cross-section properties from rectangular parts.

    This is the main entry point. It validates the input, computes all
    properties step by step, and returns a SectionResult with full
    intermediate values for educational display.

    Args:
        parts: List of RectanglePart defining the composite section.

    Returns:
        SectionResult with all properties and step-by-step part results.

    Raises:
        ValueError: If input validation fails.
    """
    error = validate_parts(parts)
    if error:
        raise ValueError(error)

    # Step 1: Compute area and centroid of each part
    areas = []
    y_centroids = []
    z_centroids = []

    for p in parts:
        A_i = p.b * p.h
        yc_i = p.y_bot + p.h / 2.0
        zc_i = p.z_left + p.b / 2.0
        areas.append(A_i)
        y_centroids.append(yc_i)
        z_centroids.append(zc_i)

    # Step 2: Composite centroid
    A_total = sum(areas)
    yc_composite = sum(A * yc for A, yc in zip(areas, y_centroids)) / A_total
    zc_composite = sum(A * zc for A, zc in zip(areas, z_centroids)) / A_total

    # Step 3: Parallel axis theorem for each part
    part_results = []
    Iy_total = 0.0
    Iz_total = 0.0
    Iyz_total = 0.0

    for p, A_i, yc_i, zc_i in zip(parts, areas, y_centroids, z_centroids):
        # Local moments of inertia (about part's own centroid)
        Iy_local = p.b * p.h ** 3 / 12.0
        Iz_local = p.h * p.b ** 3 / 12.0

        # Transfer distances
        dy = yc_i - yc_composite
        dz = zc_i - zc_composite

        # Steiner (parallel axis) terms
        Iy_steiner = A_i * dy ** 2
        Iz_steiner = A_i * dz ** 2
        Iyz_steiner = A_i * dy * dz  # product of inertia Steiner term

        # Total contribution of this part
        Iy_part = Iy_local + Iy_steiner
        Iz_part = Iz_local + Iz_steiner

        Iy_total += Iy_part
        Iz_total += Iz_part
        Iyz_total += Iyz_steiner  # Iyz_local = 0 for axis-aligned rectangles

        part_results.append(PartResult(
            name=p.name,
            b=p.b,
            h=p.h,
            A=A_i,
            yc=yc_i,
            zc=zc_i,
            Iy_local=Iy_local,
            Iz_local=Iz_local,
            dy=dy,
            dz=dz,
            Iy_steiner=Iy_steiner,
            Iz_steiner=Iz_steiner,
            Iy_total=Iy_part,
            Iz_total=Iz_part,
            Iyz_steiner=Iyz_steiner,
        ))

    # Step 4: Extreme fiber distances
    y_max = max(p.y_bot + p.h for p in parts)
    y_min = min(p.y_bot for p in parts)
    z_max = max(p.z_left + p.b for p in parts)
    z_min = min(p.z_left for p in parts)

    y_top = y_max - yc_composite    # distance from centroid to top
    y_bot = yc_composite - y_min    # distance from centroid to bottom
    z_right = z_max - zc_composite  # distance from centroid to right
    z_left = zc_composite - z_min   # distance from centroid to left

    # Step 5: Section moduli
    Wy_top = Iy_total / y_top if y_top > 0 else 0.0
    Wy_bot = Iy_total / y_bot if y_bot > 0 else 0.0
    Wz_left = Iz_total / z_left if z_left > 0 else 0.0
    Wz_right = Iz_total / z_right if z_right > 0 else 0.0

    # Step 6: Radii of gyration
    iy = math.sqrt(Iy_total / A_total)
    iz = math.sqrt(Iz_total / A_total)

    # Step 7: Principal axes
    I_avg = (Iy_total + Iz_total) / 2.0
    I_diff_half = (Iy_total - Iz_total) / 2.0
    R = math.sqrt(I_diff_half ** 2 + Iyz_total ** 2)
    I_max = I_avg + R
    I_min = I_avg - R

    # Rotation angle of principal axes
    # alpha = 0.5 * atan2(-2*Iyz, Iy - Iz)
    alpha_rad = 0.5 * math.atan2(-2.0 * Iyz_total, Iy_total - Iz_total)
    alpha_deg = math.degrees(alpha_rad)

    # Check if principal axes coincide with centroidal axes
    PRINCIPAL_TOL = 1e-3
    axes_coincide = abs(Iyz_total) < PRINCIPAL_TOL * max(abs(Iy_total), abs(Iz_total), 1.0)

    # Governing (minimum) section moduli
    Wy = min(Wy_top, Wy_bot) if (Wy_top > 0 and Wy_bot > 0) else max(Wy_top, Wy_bot)
    Wz = min(Wz_left, Wz_right) if (Wz_left > 0 and Wz_right > 0) else max(Wz_left, Wz_right)

    return SectionResult(
        parts=part_results,
        A_total=A_total,
        yc=yc_composite,
        zc=zc_composite,
        Iy=Iy_total,
        Iz=Iz_total,
        y_top=y_top,
        y_bot=y_bot,
        z_left=z_left,
        z_right=z_right,
        Wy_top=Wy_top,
        Wy_bot=Wy_bot,
        Wz_left=Wz_left,
        Wz_right=Wz_right,
        iy=iy,
        iz=iz,
        Iyz=Iyz_total,
        I_max=I_max,
        I_min=I_min,
        alpha_rad=alpha_rad,
        alpha_deg=alpha_deg,
        axes_coincide=axes_coincide,
        Wy=Wy,
        Wz=Wz,
    )
