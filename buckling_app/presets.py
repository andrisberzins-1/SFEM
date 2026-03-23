"""
presets.py -- Preset member configurations for the buckling app.

Each preset returns a MemberInput dataclass with realistic catalogue values.
"""

from buckling_solver import MemberInput


def preset_shs_100x6_s235() -> MemberInput:
    """SHS 100x100x6 cold-formed, S235, L=6m, pinned-pinned.

    Matches the algorithm document example.
    A = 2163 mm2, Iy = Iz = 3,115,000 mm4, imin = 37.9 mm.
    Buckling curve 'c' for cold-formed hollow sections.
    """
    return MemberInput(
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


def preset_hea200_s355() -> MemberInput:
    """HEA 200, S355, L=4m, pinned-pinned.

    Hot-rolled H-section. A = 5380 mm2.
    Iy = 36,920,000 mm4 (strong), Iz = 13,360,000 mm4 (weak).
    Buckling curve 'b' (y-axis), 'c' (z-axis) for hot-rolled H, h/b <= 1.2.
    """
    return MemberInput(
        name="HEA 200",
        N_Ed_kN=-300.0,
        A_mm2=5380.0,
        Iy_mm4=36_920_000.0,
        Iz_mm4=13_360_000.0,
        fy_MPa=355.0,
        E_MPa=200_000.0,
        L_m=4.0,
        mu_y=1.0,
        mu_z=1.0,
        curve_y="b",
        curve_z="c",
        gamma_M0=1.0,
        gamma_M1=1.0,
    )


def preset_ipe300_cantilever() -> MemberInput:
    """IPE 300 cantilever column, S275, L=3m.

    Hot-rolled I-section. A = 5381 mm2.
    Iy = 83,560,000 mm4 (strong), Iz = 6,038,000 mm4 (weak).
    Cantilever: mu = 2.0 for both axes.
    Buckling curve 'a' (y-axis), 'b' (z-axis) for hot-rolled I, h/b > 1.2.
    """
    return MemberInput(
        name="IPE 300",
        N_Ed_kN=-150.0,
        A_mm2=5381.0,
        Iy_mm4=83_560_000.0,
        Iz_mm4=6_038_000.0,
        fy_MPa=275.0,
        E_MPa=200_000.0,
        L_m=3.0,
        mu_y=2.0,
        mu_z=2.0,
        curve_y="a",
        curve_z="b",
        gamma_M0=1.0,
        gamma_M1=1.0,
    )


def preset_tension_member() -> MemberInput:
    """Tension member example -- L80x80x8 angle, S235, L=3m.

    Simple tension check (no buckling).
    A = 1230 mm2.
    """
    return MemberInput(
        name="L80x80x8 (tension)",
        N_Ed_kN=150.0,      # Positive = tension
        A_mm2=1230.0,
        Iy_mm4=876_000.0,
        Iz_mm4=876_000.0,
        fy_MPa=235.0,
        E_MPa=200_000.0,
        L_m=3.0,
        mu_y=1.0,
        mu_z=1.0,
        curve_y="c",
        curve_z="c",
        gamma_M0=1.0,
        gamma_M1=1.0,
    )


def preset_custom() -> MemberInput:
    """Custom member -- blank starting point for manual input."""
    return MemberInput(
        name="Custom",
        N_Ed_kN=-100.0,
        A_mm2=1000.0,
        Iy_mm4=1_000_000.0,
        Iz_mm4=1_000_000.0,
        fy_MPa=235.0,
        E_MPa=200_000.0,
        L_m=3.0,
        mu_y=1.0,
        mu_z=1.0,
        curve_y="b",
        curve_z="b",
        gamma_M0=1.0,
        gamma_M1=1.0,
    )


PRESETS = [
    {
        "id": "shs_100x6_s235",
        "name": "SHS 100\u00d7100\u00d76, S235, L=6m (Lecture example)",
        "builder": preset_shs_100x6_s235,
    },
    {
        "id": "hea200_s355",
        "name": "HEA 200, S355, L=4m",
        "builder": preset_hea200_s355,
    },
    {
        "id": "ipe300_cantilever",
        "name": "IPE 300 cantilever, S275, L=3m",
        "builder": preset_ipe300_cantilever,
    },
    {
        "id": "tension_member",
        "name": "L80\u00d780\u00d78 tension member, S235",
        "builder": preset_tension_member,
    },
    {
        "id": "custom",
        "name": "Custom",
        "builder": preset_custom,
    },
]
