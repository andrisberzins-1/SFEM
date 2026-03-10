"""
presets.py — All preset model definitions for the FEM app.

Each preset returns a fully populated ModelDefinition ready to solve.
Presets are designed for bachelor-level structural engineering students
verifying hand calculations.

Units: kN, m, kNm, GPa, cm², cm⁴
"""

from solver import (
    ModelDefinition, NodeDef, MemberDef, SupportDef, LoadDef,
    MaterialDef, CrossSectionDef, HingeDef,
)

# ---------------------------------------------------------------------------
# Section/material constants used across presets
# ---------------------------------------------------------------------------

# Steel S275
E_STEEL_S275 = 210.0       # GPa

# HEA 200
HEA200_A = 53.8            # cm²
HEA200_IZ = 3690.0         # cm⁴

# HEA 300
HEA300_A = 112.5           # cm²
HEA300_IZ = 18260.0        # cm⁴

# HEB 200
HEB200_A = 78.1            # cm²
HEB200_IZ = 5700.0         # cm⁴

# HEB 300
HEB300_A = 149.1           # cm²
HEB300_IZ = 25170.0        # cm⁴


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------


def preset_ss_beam_point_load() -> ModelDefinition:
    """
    Preset 1: Simply supported beam — central point load.

    L = 6 m, P = 20 kN at midspan, Steel S275, HEA 200.
    Pinned at left (node 1), roller_x at right (node 3).
    """
    return ModelDefinition(
        structure_type="beam",
        name="Simply supported beam - central point load",
        description="L=6m, P=20kN at midspan. Steel S275, HEA 200.",
        materials=[MaterialDef(id=1, name="Steel S275", E_GPa=E_STEEL_S275)],
        cross_sections=[CrossSectionDef(id=1, name="HEA 200", A_cm2=HEA200_A, Iz_cm4=HEA200_IZ, material_id=1)],
        nodes=[
            NodeDef(id=1, x=0.0, y=0.0),
            NodeDef(id=2, x=3.0, y=0.0),
            NodeDef(id=3, x=6.0, y=0.0),
        ],
        members=[
            MemberDef(id=1, start_node=1, end_node=2, section_id=1),
            MemberDef(id=2, start_node=2, end_node=3, section_id=1),
        ],
        supports=[
            SupportDef(node_id=1, type="pinned"),
            SupportDef(node_id=3, type="roller_x"),
        ],
        loads=[
            LoadDef(id=1, type="point_force", node_or_member_id=2,
                    direction="Fy", magnitude=-20.0),
        ],
    )


def preset_ss_beam_udl() -> ModelDefinition:
    """
    Preset 2: Simply supported beam — full span UDL.

    L = 6 m, w = 10 kN/m, Steel S275, HEA 200.
    Pinned at left (node 1), roller_x at right (node 2).
    """
    return ModelDefinition(
        structure_type="beam",
        name="Simply supported beam - UDL",
        description="L=6m, w=10 kN/m full span. Steel S275, HEA 200.",
        materials=[MaterialDef(id=1, name="Steel S275", E_GPa=E_STEEL_S275)],
        cross_sections=[CrossSectionDef(id=1, name="HEA 200", A_cm2=HEA200_A, Iz_cm4=HEA200_IZ, material_id=1)],
        nodes=[
            NodeDef(id=1, x=0.0, y=0.0),
            NodeDef(id=2, x=6.0, y=0.0),
        ],
        members=[
            MemberDef(id=1, start_node=1, end_node=2, section_id=1),
        ],
        supports=[
            SupportDef(node_id=1, type="pinned"),
            SupportDef(node_id=2, type="roller_x"),
        ],
        loads=[
            LoadDef(id=1, type="UDL", node_or_member_id=1,
                    direction="Fy", magnitude=-10.0),
        ],
    )


def preset_fixed_beam_udl() -> ModelDefinition:
    """
    Preset 3: Fixed-fixed beam — full span UDL.

    L = 6 m, w = 10 kN/m, Steel S275, HEA 300.
    Fixed at both ends.
    """
    return ModelDefinition(
        structure_type="beam",
        name="Fixed-fixed beam - UDL",
        description="L=6m, w=10 kN/m full span. Steel S275, HEA 300.",
        materials=[MaterialDef(id=1, name="Steel S275", E_GPa=E_STEEL_S275)],
        cross_sections=[CrossSectionDef(id=1, name="HEA 300", A_cm2=HEA300_A, Iz_cm4=HEA300_IZ, material_id=1)],
        nodes=[
            NodeDef(id=1, x=0.0, y=0.0),
            NodeDef(id=2, x=6.0, y=0.0),
        ],
        members=[
            MemberDef(id=1, start_node=1, end_node=2, section_id=1),
        ],
        supports=[
            SupportDef(node_id=1, type="fixed"),
            SupportDef(node_id=2, type="fixed"),
        ],
        loads=[
            LoadDef(id=1, type="UDL", node_or_member_id=1,
                    direction="Fy", magnitude=-10.0),
        ],
    )


def preset_continuous_beam() -> ModelDefinition:
    """
    Preset 4: Two-span continuous beam — point load at midspan each span.

    L1 = 6 m, L2 = 6 m, P = 20 kN at midspan of each span.
    Pinned left, roller middle, roller right. Steel S275, HEA 300.
    """
    return ModelDefinition(
        structure_type="beam",
        name="Two-span continuous beam",
        description="L1=L2=6m, P=20kN at midspan each. Steel S275, HEA 300.",
        materials=[MaterialDef(id=1, name="Steel S275", E_GPa=E_STEEL_S275)],
        cross_sections=[CrossSectionDef(id=1, name="HEA 300", A_cm2=HEA300_A, Iz_cm4=HEA300_IZ, material_id=1)],
        nodes=[
            NodeDef(id=1, x=0.0, y=0.0),   # left support
            NodeDef(id=2, x=3.0, y=0.0),   # midspan span 1
            NodeDef(id=3, x=6.0, y=0.0),   # middle support
            NodeDef(id=4, x=9.0, y=0.0),   # midspan span 2
            NodeDef(id=5, x=12.0, y=0.0),  # right support
        ],
        members=[
            MemberDef(id=1, start_node=1, end_node=2, section_id=1),
            MemberDef(id=2, start_node=2, end_node=3, section_id=1),
            MemberDef(id=3, start_node=3, end_node=4, section_id=1),
            MemberDef(id=4, start_node=4, end_node=5, section_id=1),
        ],
        supports=[
            SupportDef(node_id=1, type="pinned"),
            SupportDef(node_id=3, type="roller_x"),
            SupportDef(node_id=5, type="roller_x"),
        ],
        loads=[
            LoadDef(id=1, type="point_force", node_or_member_id=2,
                    direction="Fy", magnitude=-20.0),
            LoadDef(id=2, type="point_force", node_or_member_id=4,
                    direction="Fy", magnitude=-20.0),
        ],
    )


def preset_portal_frame() -> ModelDefinition:
    """
    Preset 5: Simple portal frame — horizontal point load at top.

    Column height = 4 m, beam span = 6 m, pinned bases.
    H = 10 kN horizontal at top-left node. Steel S275, HEB 200.
    """
    return ModelDefinition(
        structure_type="frame",
        name="Simple portal frame",
        description="Columns 4m, beam 6m, pinned bases, H=10kN top-left. Steel S275, HEB 200.",
        materials=[MaterialDef(id=1, name="Steel S275", E_GPa=E_STEEL_S275)],
        cross_sections=[CrossSectionDef(id=1, name="HEB 200", A_cm2=HEB200_A, Iz_cm4=HEB200_IZ, material_id=1)],
        nodes=[
            NodeDef(id=1, x=0.0, y=0.0),   # base left
            NodeDef(id=2, x=0.0, y=4.0),   # top left
            NodeDef(id=3, x=6.0, y=4.0),   # top right
            NodeDef(id=4, x=6.0, y=0.0),   # base right
        ],
        members=[
            MemberDef(id=1, start_node=1, end_node=2, section_id=1),
            MemberDef(id=2, start_node=2, end_node=3, section_id=1),
            MemberDef(id=3, start_node=3, end_node=4, section_id=1),
        ],
        supports=[
            SupportDef(node_id=1, type="pinned"),
            SupportDef(node_id=4, type="pinned"),
        ],
        loads=[
            LoadDef(id=1, type="point_force", node_or_member_id=2,
                    direction="Fx", magnitude=10.0),
        ],
    )


def preset_warren_truss() -> ModelDefinition:
    """
    Preset 6: Warren truss — 3 panels, midspan point load.

    Panel width = 2 m, height = 2 m, P = 10 kN at midspan bottom chord.
    Pinned left, roller right. Steel S275, custom A = 20 cm².
    All members have hinges at both ends (truss behavior).
    """
    TRUSS_A = 20.0       # cm²
    TRUSS_IZ = 10.0      # cm⁴ (nominal, needed for numerical stability with hinges)

    return ModelDefinition(
        structure_type="truss",
        name="Warren truss - 3 panels",
        description="3 panels, w=2m, h=2m, P=10kN midspan. Steel S275, A=20cm².",
        materials=[MaterialDef(id=1, name="Steel S275", E_GPa=E_STEEL_S275)],
        cross_sections=[CrossSectionDef(id=1, name="Truss bar", A_cm2=TRUSS_A, Iz_cm4=TRUSS_IZ, material_id=1)],
        nodes=[
            # Bottom chord nodes
            NodeDef(id=1, x=0.0, y=0.0),
            NodeDef(id=2, x=2.0, y=0.0),
            NodeDef(id=3, x=4.0, y=0.0),
            NodeDef(id=4, x=6.0, y=0.0),
            # Top chord nodes
            NodeDef(id=5, x=1.0, y=2.0),
            NodeDef(id=6, x=3.0, y=2.0),
            NodeDef(id=7, x=5.0, y=2.0),
        ],
        members=[
            # Bottom chord
            MemberDef(id=1, start_node=1, end_node=2, section_id=1),
            MemberDef(id=2, start_node=2, end_node=3, section_id=1),
            MemberDef(id=3, start_node=3, end_node=4, section_id=1),
            # Top chord
            MemberDef(id=4, start_node=5, end_node=6, section_id=1),
            MemberDef(id=5, start_node=6, end_node=7, section_id=1),
            # Diagonals (Warren pattern)
            MemberDef(id=6, start_node=1, end_node=5, section_id=1),
            MemberDef(id=7, start_node=5, end_node=2, section_id=1),
            MemberDef(id=8, start_node=2, end_node=6, section_id=1),
            MemberDef(id=9, start_node=6, end_node=3, section_id=1),
            MemberDef(id=10, start_node=3, end_node=7, section_id=1),
            MemberDef(id=11, start_node=7, end_node=4, section_id=1),
        ],
        hinges=[HingeDef(member_id=i, start_release=True, end_release=True) for i in range(1, 12)],
        supports=[
            SupportDef(node_id=1, type="pinned"),
            SupportDef(node_id=4, type="roller_x"),
        ],
        loads=[
            LoadDef(id=1, type="point_force", node_or_member_id=3,
                    direction="Fy", magnitude=-10.0),
        ],
    )


# ---------------------------------------------------------------------------
# Registry — ordered list of all presets
# ---------------------------------------------------------------------------

PRESETS = [
    {
        "id": 1,
        "name": "Simply supported beam - central point load",
        "builder": preset_ss_beam_point_load,
    },
    {
        "id": 2,
        "name": "Simply supported beam - UDL",
        "builder": preset_ss_beam_udl,
    },
    {
        "id": 3,
        "name": "Fixed-fixed beam - UDL",
        "builder": preset_fixed_beam_udl,
    },
    {
        "id": 4,
        "name": "Two-span continuous beam",
        "builder": preset_continuous_beam,
    },
    {
        "id": 5,
        "name": "Simple portal frame",
        "builder": preset_portal_frame,
    },
    {
        "id": 6,
        "name": "Warren truss - 3 panels",
        "builder": preset_warren_truss,
    },
]


def get_preset_by_id(preset_id: int) -> ModelDefinition:
    """Get a preset model by its ID (1-6)."""
    for p in PRESETS:
        if p["id"] == preset_id:
            return p["builder"]()
    raise ValueError(f"No preset with ID {preset_id}. Valid IDs: 1-6.")


def get_preset_names() -> list[dict]:
    """Return list of {id, name} for all presets."""
    return [{"id": p["id"], "name": p["name"]} for p in PRESETS]
