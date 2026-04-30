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


# ---------------------------------------------------------------------------
# Axis convention definitions (shared with app.py display)
# ---------------------------------------------------------------------------

AXIS_CONVENTIONS = {
    "yz_eurocode": {
        "horiz_axis": "y", "vert_axis": "z",
        "I_vert": "I_y", "I_horiz": "I_z",
        "W_vert": "W_y", "W_horiz": "W_z",
        "i_vert": "i_y", "i_horiz": "i_z",
        "Iyz_sub": "yz",
    },
    "xy_basic": {
        "horiz_axis": "x", "vert_axis": "y",
        "I_vert": "I_x", "I_horiz": "I_y",
        "W_vert": "W_x", "W_horiz": "W_y",
        "i_vert": "i_x", "i_horiz": "i_y",
        "Iyz_sub": "xy",
    },
}


# ---------------------------------------------------------------------------
# LaTeX step builder
# ---------------------------------------------------------------------------

def _fmt(v: float) -> str:
    """Format dimension: 1 decimal if fractional, integer otherwise."""
    return f"{v:.1f}" if v % 1 else f"{v:.0f}"


def _sub(text: str) -> str:
    """Format property label with HTML subscript: 'I_y' -> 'I<sub>y</sub>'."""
    if "_" in text:
        base, subscript = text.split("_", 1)
        return f"{base}<sub>{subscript}</sub>"
    return text


def build_latex_steps(
    result: SectionResult,
    axis_convention: str = "yz_eurocode",
) -> list[tuple[str, str]]:
    """Build step-by-step LaTeX strings for section property calculation.

    Returns a list of (heading, latex_expression) tuples.
    Headings may contain HTML (subscripts). Empty heading means
    continuation of the previous section (no new heading rendered).

    Args:
        result: Computed SectionResult from calculate().
        axis_convention: "yz_eurocode" or "xy_basic".

    Returns:
        List of (heading_str, latex_str) tuples.
    """
    conv = AXIS_CONVENTIONS[axis_convention]
    v_ax = conv["vert_axis"]
    h_ax = conv["horiz_axis"]
    Iyz_sub = conv["Iyz_sub"]
    I_vert_label = conv["I_vert"]
    I_horiz_label = conv["I_horiz"]
    W_vert_label = conv["W_vert"]
    W_horiz_label = conv["W_horiz"]

    # Property subscripts for I, W, i formulas:
    # Iy (about horizontal axis) → named after horizontal axis = h_ax
    # Iz (about vertical axis)   → named after vertical axis  = v_ax
    Iy_s = h_ax   # "y" for yz_eurocode, "x" for xy_basic
    Iz_s = v_ax   # "z" for yz_eurocode, "y" for xy_basic

    steps: list[tuple[str, str]] = []

    # --- Area ---
    area_parts = " + ".join(
        f"{_fmt(pr.b)} \\cdot {_fmt(pr.h)}" for pr in result.parts
    )
    area_values = " + ".join(f"{pr.A:.0f}" for pr in result.parts)
    steps.append((
        "Area",
        r"A = \sum b_i \cdot h_i = " + area_parts
        + r" = " + area_values
        + r" = " + f"{result.A_total:.0f}"
        + r"\text{{ mm}}^2",
    ))

    # --- Centroid (vertical axis) ---
    num_y = " + ".join(
        f"({_fmt(pr.b)} \\cdot {_fmt(pr.h)}) \\cdot {pr.yc:.1f}"
        for pr in result.parts
    )
    steps.append((
        f"Centroid {v_ax}<sub>C</sub>",
        v_ax + r"_C = \frac{\sum A_i \cdot "
        + v_ax + r"_{c,i}}{\sum A_i} = "
        r"\frac{" + num_y + r"}{" + f"{result.A_total:.0f}" + r"}"
        r" = " + f"{result.yc:.2f}" + r"\text{{ mm}}",
    ))

    # --- Centroid (horizontal axis) ---
    num_z = " + ".join(
        f"({_fmt(pr.b)} \\cdot {_fmt(pr.h)}) \\cdot {pr.zc:.1f}"
        for pr in result.parts
    )
    steps.append((
        f"Centroid {h_ax}<sub>C</sub>",
        h_ax + r"_C = \frac{\sum A_i \cdot "
        + h_ax + r"_{c,i}}{\sum A_i} = "
        r"\frac{" + num_z + r"}{" + f"{result.A_total:.0f}" + r"}"
        r" = " + f"{result.zc:.2f}" + r"\text{{ mm}}",
    ))

    # --- Moment of inertia Iy (about horizontal axis) ---
    steps.append((
        f"{_sub(I_vert_label)} \u2014 Parallel axis theorem (Steiner)",
        r"I_" + Iy_s + r" = \sum \left( I_{\text{local},i} + A_i \cdot d_i^2 \right)",
    ))

    for pr in result.parts:
        steps.append((
            "",
            r"\text{" + pr.name.replace(" ", r"\ ") + r"}: \quad "
            r"I_" + Iy_s + r" = \frac{"
            + f"{_fmt(pr.b)} \\cdot {_fmt(pr.h)}^3" + r"}{12} + "
            + f"({_fmt(pr.b)} \\cdot {_fmt(pr.h)})"
            + r" \cdot "
            + f"({pr.yc:.1f} - {result.yc:.2f})^2"
            + r" = " + f"{pr.Iy_local:,.0f}" + r" + " + f"{pr.Iy_steiner:,.0f}"
            + r" = " + f"{pr.Iy_total:,.0f}" + r"\text{{ mm}}^4",
        ))

    Iy_sum = " + ".join(f"{pr.Iy_total:,.0f}" for pr in result.parts)
    steps.append((
        "",
        r"I_" + Iy_s + r" = " + Iy_sum
        + r" = " + f"{result.Iy:,.0f}" + r"\text{{ mm}}^4"
        + r" = " + f"{result.Iy / 1e6:,.2f}" + r" \times 10^6 \text{{ mm}}^4"
        + r" = " + f"{result.Iy * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4",
    ))

    # --- Moment of inertia Iz (about vertical axis) ---
    steps.append((
        f"{_sub(I_horiz_label)} \u2014 Parallel axis theorem (Steiner)",
        "",  # heading-only, no formula on this line
    ))

    for pr in result.parts:
        steps.append((
            "",
            r"\text{" + pr.name.replace(" ", r"\ ") + r"}: \quad "
            r"I_" + Iz_s + r" = \frac{"
            + f"{_fmt(pr.h)} \\cdot {_fmt(pr.b)}^3" + r"}{12} + "
            + f"({_fmt(pr.b)} \\cdot {_fmt(pr.h)})"
            + r" \cdot "
            + f"({pr.zc:.1f} - {result.zc:.2f})^2"
            + r" = " + f"{pr.Iz_local:,.0f}" + r" + " + f"{pr.Iz_steiner:,.0f}"
            + r" = " + f"{pr.Iz_total:,.0f}" + r"\text{{ mm}}^4",
        ))

    Iz_sum = " + ".join(f"{pr.Iz_total:,.0f}" for pr in result.parts)
    steps.append((
        "",
        r"I_" + Iz_s + r" = " + Iz_sum
        + r" = " + f"{result.Iz:,.0f}" + r"\text{{ mm}}^4"
        + r" = " + f"{result.Iz / 1e6:,.2f}" + r" \times 10^6 \text{{ mm}}^4"
        + r" = " + f"{result.Iz * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4",
    ))

    # --- Product of inertia + Principal moments (skip for symmetric sections) ---
    if not result.axes_coincide:
        steps.append((
            f"Product of inertia I<sub>{Iyz_sub}</sub> \u2014 Parallel axis theorem (Steiner)",
            r"I_{" + Iyz_sub + r"} = \sum A_i \cdot d_{" + v_ax
            + r",i} \cdot d_{" + h_ax + r",i}",
        ))

        for pr in result.parts:
            steps.append((
                "",
                r"\text{" + pr.name.replace(" ", r"\ ") + r"}: \quad "
                + f"({_fmt(pr.b)} \\cdot {_fmt(pr.h)})"
                + r" \cdot "
                + f"({pr.yc:.1f} - {result.yc:.2f})"
                + r" \cdot "
                + f"({pr.zc:.1f} - {result.zc:.2f})"
                + r" = " + f"{pr.Iyz_steiner:,.0f}" + r"\text{{ mm}}^4",
            ))

        Iyz_sum = " + ".join(
            f"({pr.Iyz_steiner:,.0f})" if pr.Iyz_steiner < 0
            else f"{pr.Iyz_steiner:,.0f}"
            for pr in result.parts
        )
        steps.append((
            "",
            r"I_{" + Iyz_sub + r"} = " + Iyz_sum
            + r" = " + f"{result.Iyz:,.0f}" + r"\text{{ mm}}^4"
            + r" = " + f"{result.Iyz * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4",
        ))

        # --- Principal moments of inertia ---
        steps.append((
            "Principal moments of inertia",
            r"I_{\max,\min} = \frac{I_" + Iy_s + r" + I_" + Iz_s
            + r"}{2} \pm \sqrt{\left(\frac{I_" + Iy_s + r" - I_" + Iz_s
            + r"}{2}\right)^2 + I_{" + Iyz_sub + r"}^2}",
        ))
        steps.append((
            "",
            r"I_{\max,\min} = \frac{" + f"{result.Iy:,.0f} + {result.Iz:,.0f}"
            + r"}{2} \pm \sqrt{\left(\frac{" + f"{result.Iy:,.0f} - {result.Iz:,.0f}"
            + r"}{2}\right)^2 + " + f"({result.Iyz:,.0f})^2" + r"}",
        ))
        steps.append((
            "",
            r"I_{\max} = " + f"{result.I_max:,.0f}" + r"\text{{ mm}}^4"
            + r" = " + f"{result.I_max * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4",
        ))
        steps.append((
            "",
            r"I_{\min} = " + f"{result.I_min:,.0f}" + r"\text{{ mm}}^4"
            + r" = " + f"{result.I_min * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4",
        ))

        # --- Principal axis angle ---
        steps.append((
            "Principal axis rotation angle",
            r"\alpha = \frac{1}{2} \arctan\!\left(\frac{-2\,I_{" + Iyz_sub
            + r"}}{I_" + Iy_s + r" - I_" + Iz_s + r"}\right)"
            + r" = \frac{1}{2} \arctan\!\left(\frac{-2 \cdot "
            + f"({result.Iyz:,.0f})" + r"}{"
            + f"{result.Iy:,.0f} - {result.Iz:,.0f}" + r"}\right)"
            + r" = " + f"{result.alpha_deg:.1f}" + r"\degree",
        ))

    # --- Section modulus Wy ---
    steps.append((
        f"Section modulus \u2014 {_sub(W_vert_label)}",
        r"W_{" + Iy_s + r",\text{top}} = \frac{I_" + Iy_s + r"}{" + v_ax
        + r"_{\text{top}}} = \frac{"
        + f"{result.Iy:,.0f}" + r"}{" + f"{result.y_top:.1f}" + r"}"
        + r" = " + f"{result.Wy_top:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wy_top * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3",
    ))
    steps.append((
        "",
        r"W_{" + Iy_s + r",\text{bot}} = \frac{I_" + Iy_s + r"}{" + v_ax
        + r"_{\text{bot}}} = \frac{"
        + f"{result.Iy:,.0f}" + r"}{" + f"{result.y_bot:.1f}" + r"}"
        + r" = " + f"{result.Wy_bot:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wy_bot * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3",
    ))
    Wy_top_val = f"{result.Wy_top:,.0f}"
    Wy_bot_val = f"{result.Wy_bot:,.0f}"
    if result.Wy_top <= result.Wy_bot:
        steps.append((
            "",
            r"W_" + Iy_s + r" = \min(" + Wy_top_val + r",\;" + Wy_bot_val
            + r") = " + Wy_top_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{top governs}",
        ))
    else:
        steps.append((
            "",
            r"W_" + Iy_s + r" = \min(" + Wy_top_val + r",\;" + Wy_bot_val
            + r") = " + Wy_bot_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{bottom governs}",
        ))

    # --- Section modulus Wz ---
    steps.append((
        f"Section modulus \u2014 {_sub(W_horiz_label)}",
        r"W_{" + Iz_s + r",\text{left}} = \frac{I_" + Iz_s + r"}{" + h_ax
        + r"_{\text{left}}} = \frac{"
        + f"{result.Iz:,.0f}" + r"}{" + f"{result.z_left:.1f}" + r"}"
        + r" = " + f"{result.Wz_left:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wz_left * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3",
    ))
    steps.append((
        "",
        r"W_{" + Iz_s + r",\text{right}} = \frac{I_" + Iz_s + r"}{" + h_ax
        + r"_{\text{right}}} = \frac{"
        + f"{result.Iz:,.0f}" + r"}{" + f"{result.z_right:.1f}" + r"}"
        + r" = " + f"{result.Wz_right:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wz_right * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3",
    ))
    Wz_left_val = f"{result.Wz_left:,.0f}"
    Wz_right_val = f"{result.Wz_right:,.0f}"
    if result.Wz_left <= result.Wz_right:
        steps.append((
            "",
            r"W_" + Iz_s + r" = \min(" + Wz_left_val + r",\;" + Wz_right_val
            + r") = " + Wz_left_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{left governs}",
        ))
    else:
        steps.append((
            "",
            r"W_" + Iz_s + r" = \min(" + Wz_left_val + r",\;" + Wz_right_val
            + r") = " + Wz_right_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{right governs}",
        ))

    # --- Radius of gyration ---
    steps.append((
        "Radius of gyration",
        r"i_" + Iy_s + r" = \sqrt{\frac{I_" + Iy_s + r"}{A}} = \sqrt{\frac{"
        + f"{result.Iy:,.0f}" + r"}{" + f"{result.A_total:.0f}" + r"}}"
        + r" = " + f"{result.iy:.1f}" + r"\text{{ mm}}"
        + r" = " + f"{result.iy / 10:.2f}" + r"\text{{ cm}}",
    ))
    steps.append((
        "",
        r"i_" + Iz_s + r" = \sqrt{\frac{I_" + Iz_s + r"}{A}} = \sqrt{\frac{"
        + f"{result.Iz:,.0f}" + r"}{" + f"{result.A_total:.0f}" + r"}}"
        + r" = " + f"{result.iz:.1f}" + r"\text{{ mm}}"
        + r" = " + f"{result.iz / 10:.2f}" + r"\text{{ cm}}",
    ))

    return steps


# ---------------------------------------------------------------------------
# HTML report helpers (summary block + image embedding)
# ---------------------------------------------------------------------------

def build_summary_html(
    result: SectionResult,
    section_name: str,
    axis_convention: str = "yz_eurocode",
    convention_label: str = "",
    timestamp: str = "",
) -> str:
    """Build the section properties summary block for the HTML report.

    Mirrors the on-screen "Section properties" block: A, Iy, Iz, Iyz, Imax,
    Imin, Wy, Wz, iy, iz with cm-equivalent units. Returned HTML is intended
    to be passed to ``render_latex_html`` via the ``intro_html`` parameter.
    """
    conv = AXIS_CONVENTIONS[axis_convention]
    h_ax = conv["horiz_axis"]
    v_ax = conv["vert_axis"]
    Iyz_sub = conv["Iyz_sub"]

    lines: list[str] = []
    lines.append(
        f"<b>A</b> = {result.A_total:,.0f} mm²"
        f" = {result.A_total * MM2_TO_CM2:,.2f} cm²"
    )
    lines.append(
        f"<b>{_sub(conv['I_vert'])}</b> = {result.Iy:,.0f} mm⁴"
        f" = {result.Iy / 1e6:,.2f} ×10⁶ mm⁴"
        f" = {result.Iy * MM4_TO_CM4:,.1f} cm⁴"
    )
    lines.append(
        f"<b>{_sub(conv['I_horiz'])}</b> = {result.Iz:,.0f} mm⁴"
        f" = {result.Iz / 1e6:,.2f} ×10⁶ mm⁴"
        f" = {result.Iz * MM4_TO_CM4:,.1f} cm⁴"
    )
    lines.append(
        f"<b>I<sub>{Iyz_sub}</sub></b>"
        f" = {result.Iyz:,.0f} mm⁴"
        f" = {result.Iyz * MM4_TO_CM4:,.1f} cm⁴"
    )
    lines.append(
        f"<b>I<sub>max</sub></b> = {result.I_max:,.0f} mm⁴"
        f" = {result.I_max * MM4_TO_CM4:,.1f} cm⁴"
    )
    if result.axes_coincide:
        lines.append(
            f"<b>I<sub>min</sub></b> = {result.I_min:,.0f} mm⁴"
            f" = {result.I_min * MM4_TO_CM4:,.1f} cm⁴"
            f" &nbsp; <i>(principal axes coincide with centroidal axes)</i>"
        )
    else:
        lines.append(
            f"<b>I<sub>min</sub></b> = {result.I_min:,.0f} mm⁴"
            f" = {result.I_min * MM4_TO_CM4:,.1f} cm⁴"
            f" &nbsp; <b>α</b> = {result.alpha_deg:.1f}°"
        )
    lines.append(
        f"<b>{_sub(conv['W_vert'])}</b>"
        f" = {result.Wy:,.0f} mm³"
        f" = {result.Wy * MM3_TO_CM3:,.1f} cm³"
    )
    lines.append(
        f"<b>{_sub(conv['W_horiz'])}</b>"
        f" = {result.Wz:,.0f} mm³"
        f" = {result.Wz * MM3_TO_CM3:,.1f} cm³"
    )
    lines.append(
        f"<b>{_sub(conv['i_vert'])}</b>"
        f" = {result.iy:.1f} mm = {result.iy / 10:.2f} cm"
    )
    lines.append(
        f"<b>{_sub(conv['i_horiz'])}</b>"
        f" = {result.iz:.1f} mm = {result.iz / 10:.2f} cm"
    )

    name_label = section_name.strip() or "(unnamed)"
    label_str = convention_label or f"{h_ax}, {v_ax}"
    meta_parts = [f"Section: <b>{name_label}</b>",
                  f"Convention: {label_str}"]
    if timestamp:
        meta_parts.append(f"Generated: {timestamp}")
    meta_html = " &nbsp;|&nbsp; ".join(meta_parts)

    return (
        f'<div class="report-meta">{meta_html}</div>\n'
        '<h3>Section properties</h3>\n'
        '<div class="report-summary">'
        + "<br>".join(lines)
        + "</div>"
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


# ---------------------------------------------------------------------------
# HTML rendering for LaTeX steps (used by app.py download and test prep)
# ---------------------------------------------------------------------------

def render_latex_html(
    title: str,
    steps: list[tuple[str, str]],
    intro_html: str = "",
) -> str:
    """Render a self-contained HTML report with KaTeX-rendered LaTeX.

    The returned HTML opens in any browser and can be printed to PDF
    (browser print dialog → "Save as PDF").

    Args:
        title: Report title shown as ``<h2>``.
        steps: List of ``(heading, latex)`` tuples for the calculation steps.
        intro_html: Optional HTML inserted between the title and the steps
            (e.g. summary table, embedded image). Pass an empty string to
            keep the bare-steps layout.
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
