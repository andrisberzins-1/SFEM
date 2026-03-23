"""
presets.py — Preset cross-section definitions for the section calculator.

Each preset is a function returning a list of RectanglePart ready to calculate.
Presets use realistic dimensions for common structural steel shapes.

Units: mm
"""

from section_solver import RectanglePart


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

def preset_i_beam() -> list[RectanglePart]:
    """Symmetric I-beam (HEA 200-like dimensions).

    h_total = 190 mm, b_flange = 200 mm, t_flange = 10 mm, t_web = 6.5 mm
    """
    b_f = 200.0
    t_f = 10.0
    t_w = 6.5
    h_total = 190.0
    h_web = h_total - 2 * t_f

    return [
        RectanglePart(name="Bottom flange", b=b_f, h=t_f,
                      y_bot=0.0, z_left=0.0),
        RectanglePart(name="Web", b=t_w, h=h_web,
                      y_bot=t_f, z_left=(b_f - t_w) / 2.0),
        RectanglePart(name="Top flange", b=b_f, h=t_f,
                      y_bot=t_f + h_web, z_left=0.0),
    ]


def preset_t_section() -> list[RectanglePart]:
    """T-section (flange on top, web below).

    Flange: 200 x 20 mm, Web: 10 x 180 mm, total height = 200 mm.
    """
    b_f = 200.0
    t_f = 20.0
    t_w = 10.0
    h_web = 180.0

    return [
        RectanglePart(name="Web", b=t_w, h=h_web,
                      y_bot=0.0, z_left=(b_f - t_w) / 2.0),
        RectanglePart(name="Flange", b=b_f, h=t_f,
                      y_bot=h_web, z_left=0.0),
    ]


def preset_l_section() -> list[RectanglePart]:
    """L-section (equal angle 100x100x10).

    Vertical leg: 10 x 90 mm, Horizontal leg: 100 x 10 mm.
    """
    leg = 100.0
    t = 10.0

    return [
        RectanglePart(name="Horizontal leg", b=leg, h=t,
                      y_bot=0.0, z_left=0.0),
        RectanglePart(name="Vertical leg", b=t, h=leg - t,
                      y_bot=t, z_left=0.0),
    ]


def preset_channel() -> list[RectanglePart]:
    """Channel (U-section, UPN 200-like).

    h_total = 200 mm, b_flange = 75 mm, t_flange = 11.5 mm, t_web = 8.5 mm.
    Open on the right side.
    """
    b_f = 75.0
    t_f = 11.5
    t_w = 8.5
    h_total = 200.0
    h_web = h_total - 2 * t_f

    return [
        RectanglePart(name="Bottom flange", b=b_f, h=t_f,
                      y_bot=0.0, z_left=0.0),
        RectanglePart(name="Web", b=t_w, h=h_web,
                      y_bot=t_f, z_left=0.0),
        RectanglePart(name="Top flange", b=b_f, h=t_f,
                      y_bot=t_f + h_web, z_left=0.0),
    ]


def preset_box_section() -> list[RectanglePart]:
    """Rectangular hollow section (box) 200x100x10.

    Outer: 200 mm tall x 100 mm wide, wall thickness: 10 mm.
    """
    h_outer = 200.0
    b_outer = 100.0
    t = 10.0
    h_web = h_outer - 2 * t

    return [
        RectanglePart(name="Bottom plate", b=b_outer, h=t,
                      y_bot=0.0, z_left=0.0),
        RectanglePart(name="Left web", b=t, h=h_web,
                      y_bot=t, z_left=0.0),
        RectanglePart(name="Right web", b=t, h=h_web,
                      y_bot=t, z_left=b_outer - t),
        RectanglePart(name="Top plate", b=b_outer, h=t,
                      y_bot=t + h_web, z_left=0.0),
    ]


def preset_custom() -> list[RectanglePart]:
    """Empty section for custom student input.

    Returns a single default rectangle as a starting point.
    """
    return [
        RectanglePart(name="Part 1", b=100.0, h=100.0,
                      y_bot=0.0, z_left=0.0),
    ]


# ---------------------------------------------------------------------------
# Preset registry
# ---------------------------------------------------------------------------

PRESETS = [
    {"id": "i_beam",      "name": "I-beam (HEA 200)",     "builder": preset_i_beam},
    {"id": "t_section",   "name": "T-section",            "builder": preset_t_section},
    {"id": "l_section",   "name": "L-section (angle)",    "builder": preset_l_section},
    {"id": "channel",     "name": "Channel (U-section)",  "builder": preset_channel},
    {"id": "box_section", "name": "Box section (RHS)",    "builder": preset_box_section},
    {"id": "custom",      "name": "Custom",               "builder": preset_custom},
]
