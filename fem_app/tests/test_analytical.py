"""
test_analytical.py — Analytical verification tests for the FEM solver.

All tests compare solver results against known closed-form solutions.
Tolerance: 0.5% relative error for all numerical checks.

Uses solver.py directly (no HTTP, no Streamlit).
Run with: pytest tests/test_analytical.py -v
"""

import math
import sys
import os

import pytest

# Add parent directory to path so we can import solver/presets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solver import (
    ModelDefinition, NodeDef, MemberDef, SupportDef, LoadDef,
    MaterialDef, CrossSectionDef, HingeDef,
    solve, result_to_dict,
)
from presets import (
    preset_ss_beam_point_load,
    preset_ss_beam_udl,
    preset_fixed_beam_udl,
    preset_continuous_beam,
    preset_portal_frame,
    preset_warren_truss,
    E_STEEL_S275, HEA200_A, HEA200_IZ, HEA300_A, HEA300_IZ,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REL_TOL = 0.005  # 0.5% relative tolerance

# Unit conversions for analytical calculations
GPA_TO_KN_M2 = 1e6
CM2_TO_M2 = 1e-4
CM4_TO_M4 = 1e-8
M_TO_MM = 1000.0


def assert_close(actual, expected, name="value"):
    """Assert that actual is within REL_TOL of expected."""
    if expected == 0:
        assert abs(actual) < 0.01, f"{name}: expected ~0, got {actual}"
    else:
        rel_err = abs(actual - expected) / abs(expected)
        assert rel_err < REL_TOL, (
            f"{name}: expected {expected}, got {actual} "
            f"(relative error {rel_err:.4%} exceeds {REL_TOL:.1%})"
        )


def get_reaction(result_dict, node_id):
    """Get reaction dict for a specific node."""
    for r in result_dict["reactions"]:
        if r["node_id"] == node_id:
            return r
    raise ValueError(f"No reaction found for node {node_id}")


def get_member_result(result_dict, member_id):
    """Get member result dict for a specific member."""
    for m in result_dict["member_results"]:
        if m["member_id"] == member_id:
            return m
    raise ValueError(f"No member result found for member {member_id}")


# ---------------------------------------------------------------------------
# Test: Simply supported beam, UDL (Preset 2)
# ---------------------------------------------------------------------------


class TestSSBeamUDL:
    """
    Simply supported beam, L=6m, UDL w=10 kN/m.
    Steel S275, HEA 200.

    Analytical:
        M_max = wL²/8 = 10*36/8 = 45.0 kNm at midspan
        R_A = R_B = wL/2 = 30.0 kN
        δ_max = 5wL⁴/(384EI) at midspan
    """

    @pytest.fixture
    def result(self):
        model = preset_ss_beam_udl()
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_reactions_vertical(self, result):
        r1 = get_reaction(result, 1)
        r2 = get_reaction(result, 2)
        assert_close(r1["Ry_kN"], 30.0, "R_A (Ry)")
        assert_close(r2["Ry_kN"], 30.0, "R_B (Ry)")

    def test_reactions_horizontal(self, result):
        r1 = get_reaction(result, 1)
        r2 = get_reaction(result, 2)
        assert_close(r1["Rx_kN"], 0.0, "R_A (Rx)")
        assert_close(r2["Rx_kN"], 0.0, "R_B (Rx)")

    def test_max_bending_moment(self, result):
        m1 = get_member_result(result, 1)
        assert_close(m1["M_max_kNm"], 45.0, "M_max")

    def test_max_shear_force(self, result):
        m1 = get_member_result(result, 1)
        assert_close(m1["V_max_kN"], 30.0, "V_max")

    def test_midspan_deflection(self, result):
        E = E_STEEL_S275 * GPA_TO_KN_M2      # kN/m²
        I = HEA200_IZ * CM4_TO_M4             # m⁴
        w = 10.0                               # kN/m
        L = 6.0                                # m
        delta_analytical = 5 * w * L**4 / (384 * E * I) * M_TO_MM  # mm
        m1 = get_member_result(result, 1)
        assert_close(m1["max_displacement_mm"], delta_analytical, "δ_max")

    def test_equilibrium(self, result):
        """Sum of vertical reactions should equal total applied load."""
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        total_load = 10.0 * 6.0  # wL = 60 kN downward
        assert_close(total_ry, total_load, "ΣRy vs total load")


# ---------------------------------------------------------------------------
# Test: Simply supported beam, central point load (Preset 1)
# ---------------------------------------------------------------------------


class TestSSBeamPointLoad:
    """
    Simply supported beam, L=6m, P=20kN at midspan.
    Steel S275, HEA 200.

    Analytical:
        M_max = PL/4 = 20*6/4 = 30.0 kNm at midspan
        R_A = R_B = P/2 = 10.0 kN
    """

    @pytest.fixture
    def result(self):
        model = preset_ss_beam_point_load()
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_reactions(self, result):
        r1 = get_reaction(result, 1)
        r3 = get_reaction(result, 3)
        assert_close(r1["Ry_kN"], 10.0, "R_A")
        assert_close(r3["Ry_kN"], 10.0, "R_B")

    def test_max_bending_moment(self, result):
        # Both members share the midspan node, M_max occurs at that node
        m1 = get_member_result(result, 1)
        assert_close(m1["M_max_kNm"], 30.0, "M_max")

    def test_equilibrium(self, result):
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        assert_close(total_ry, 20.0, "ΣRy vs P")


# ---------------------------------------------------------------------------
# Test: Fixed-fixed beam, UDL (Preset 3)
# ---------------------------------------------------------------------------


class TestFixedBeamUDL:
    """
    Fixed-fixed beam, L=6m, UDL w=10 kN/m.
    Steel S275, HEA 300.

    Analytical:
        M_end = wL²/12 = 30.0 kNm (hogging at supports)
        M_midspan = wL²/24 = 15.0 kNm (sagging)
        R_A = R_B = wL/2 = 30.0 kN
    """

    @pytest.fixture
    def result(self):
        model = preset_fixed_beam_udl()
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_reactions_vertical(self, result):
        r1 = get_reaction(result, 1)
        r2 = get_reaction(result, 2)
        assert_close(r1["Ry_kN"], 30.0, "R_A")
        assert_close(r2["Ry_kN"], 30.0, "R_B")

    def test_fixed_end_moments(self, result):
        r1 = get_reaction(result, 1)
        r2 = get_reaction(result, 2)
        # Fixed end moment magnitude = wL²/12 = 30 kNm
        assert_close(abs(r1["Mz_kNm"]), 30.0, "M_fixed_left")
        assert_close(abs(r2["Mz_kNm"]), 30.0, "M_fixed_right")

    def test_member_max_moment(self, result):
        """M_max on the member should be the fixed-end moment (30 kNm)."""
        m1 = get_member_result(result, 1)
        assert_close(m1["M_max_kNm"], 30.0, "M_max (end moment)")

    def test_equilibrium(self, result):
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        assert_close(total_ry, 60.0, "ΣRy vs wL")


# ---------------------------------------------------------------------------
# Test: Propped cantilever, UDL
# ---------------------------------------------------------------------------


class TestProppedCantilever:
    """
    Propped cantilever, L=6m, UDL w=10 kN/m.
    Fixed at left, roller at right.

    Analytical:
        R_prop (roller) = 3wL/8 = 22.5 kN
        R_fixed = 5wL/8 = 37.5 kN
        M_fixed = wL²/8 = 45.0 kNm
    """

    @pytest.fixture
    def model(self):
        return ModelDefinition(
            structure_type="beam",
            name="Propped cantilever",
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
                SupportDef(node_id=1, type="fixed"),
                SupportDef(node_id=2, type="roller_x"),
            ],
            loads=[
                LoadDef(id=1, type="UDL", node_or_member_id=1,
                        direction="Fy", magnitude=-10.0),
            ],
        )

    @pytest.fixture
    def result(self, model):
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_prop_reaction(self, result):
        r2 = get_reaction(result, 2)
        assert_close(r2["Ry_kN"], 22.5, "R_prop")

    def test_fixed_reaction(self, result):
        r1 = get_reaction(result, 1)
        assert_close(r1["Ry_kN"], 37.5, "R_fixed")

    def test_fixed_moment(self, result):
        r1 = get_reaction(result, 1)
        # Fixed end moment = wL²/8 = 45 kNm
        assert_close(abs(r1["Mz_kNm"]), 45.0, "M_fixed")

    def test_equilibrium(self, result):
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        assert_close(total_ry, 60.0, "ΣRy vs wL")


# ---------------------------------------------------------------------------
# Test: Warren truss (Preset 6)
# ---------------------------------------------------------------------------


class TestWarrenTruss:
    """
    Warren truss, 3 panels, panel width=2m, height=2m.
    P=10kN at bottom chord node 3 (x=4m).
    Pinned left, roller right.

    Verify:
        - Global equilibrium: ΣFy = 0, ΣFx = 0
        - Top chord members in compression
        - Bottom chord members in tension
        - Reactions by simple statics
    """

    @pytest.fixture
    def result(self):
        model = preset_warren_truss()
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_vertical_equilibrium(self, result):
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        assert_close(total_ry, 10.0, "ΣRy vs P")

    def test_horizontal_equilibrium(self, result):
        total_rx = sum(r["Rx_kN"] for r in result["reactions"])
        assert_close(total_rx, 0.0, "ΣRx")

    def test_left_reaction(self, result):
        """R_left = P * (6-4)/6 = 3.333 kN"""
        r1 = get_reaction(result, 1)
        assert_close(r1["Ry_kN"], 10.0 * 2 / 6, "R_left")

    def test_right_reaction(self, result):
        """R_right = P * 4/6 = 6.667 kN"""
        r4 = get_reaction(result, 4)
        assert_close(r4["Ry_kN"], 10.0 * 4 / 6, "R_right")

    def test_all_members_axial_only(self, result):
        """Truss members should have zero bending and shear."""
        for mr in result["member_results"]:
            assert mr["V_max_kN"] < 0.01, f"Member {mr['member_id']} has shear"
            assert mr["M_max_kNm"] < 0.01, f"Member {mr['member_id']} has bending"


# ---------------------------------------------------------------------------
# Test: Simple portal frame (Preset 5)
# ---------------------------------------------------------------------------


class TestPortalFrame:
    """
    Simple portal frame, column height=4m, beam span=6m.
    Pinned bases, H=10kN horizontal at top-left node.

    Verify:
        - ΣFx reactions = H = 10.0 kN
        - Global moment equilibrium about any point
        - Moment diagram shape and sign
    """

    @pytest.fixture
    def result(self):
        model = preset_portal_frame()
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_horizontal_equilibrium(self, result):
        """Sum of horizontal reactions must equal applied horizontal load."""
        total_rx = sum(r["Rx_kN"] for r in result["reactions"])
        # Applied Fx = 10 kN to the right at node 2
        # Reactions must sum to -10 kN (opposing the load)
        assert_close(abs(total_rx), 10.0, "|ΣRx| vs H")

    def test_vertical_equilibrium(self, result):
        """No vertical loads applied — vertical reactions should form a couple."""
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        assert_close(total_ry, 0.0, "ΣRy (no vertical load)")

    def test_moment_equilibrium(self, result):
        """
        Take moments about base left (node 1):
        H * 4m (clockwise) + R_right_y * 6m (counter-clockwise) = 0
        So R_right_y = +H*4/6 = +6.667 kN (upward)
        """
        r4 = get_reaction(result, 4)
        expected_ry_right = 10.0 * 4.0 / 6.0  # +6.667 kN (upward)
        assert_close(r4["Ry_kN"], expected_ry_right, "R_right_y (moment eq)")

    def test_columns_have_moment(self, result):
        """Both columns should carry bending moment."""
        m1 = get_member_result(result, 1)  # left column
        m3 = get_member_result(result, 3)  # right column
        assert m1["M_max_kNm"] > 1.0, "Left column should have bending"
        assert m3["M_max_kNm"] > 1.0, "Right column should have bending"

    def test_pinned_base_zero_moment(self, result):
        """Pinned bases should have zero moment reaction."""
        r1 = get_reaction(result, 1)
        r4 = get_reaction(result, 4)
        assert_close(r1["Mz_kNm"], 0.0, "M_base_left")
        assert_close(r4["Mz_kNm"], 0.0, "M_base_right")


# ---------------------------------------------------------------------------
# Test: Kopne truss — 14 nodes, 25 members (regression test for node mapping bug)
# ---------------------------------------------------------------------------


KOPNE_STEEL = MaterialDef(id=1, name="Steel", E_GPa=210.0)
KOPNE_SECTION = CrossSectionDef(id=1, A_cm2=28.5, Iz_cm4=19.43, material_id=1)

KOPNE_MEMBERS_DEF = [
    (1, 2), (2, 3), (1, 3), (1, 4), (4, 3), (4, 5), (5, 3), (6, 3), (5, 6), (5, 8),
    (5, 7), (6, 7), (7, 10), (7, 9), (8, 9), (7, 8), (9, 10), (9, 12), (9, 11),
    (10, 11), (11, 14), (11, 12), (11, 13), (12, 13), (14, 13),
]
KOPNE_NODES_DEF = [
    (1, 0, 0), (2, 0, 1), (3, 2, 1), (4, 2, 0), (5, 4, 0), (6, 4, 1), (7, 6, 1),
    (8, 6, 0), (9, 8, 0), (10, 8, 1), (11, 10, 1), (12, 10, 0), (13, 12, 0), (14, 12, 1),
]


def make_kopne_model(mesh_size=2):
    """Build the kopne truss model used in BUG_TRUSS_REACTIONS.md."""
    return ModelDefinition(
        structure_type="truss",
        mesh_size=mesh_size,
        materials=[KOPNE_STEEL],
        cross_sections=[KOPNE_SECTION],
        nodes=[NodeDef(id=n[0], x=n[1], y=n[2]) for n in KOPNE_NODES_DEF],
        members=[
            MemberDef(id=i + 1, start_node=m[0], end_node=m[1], section_id=1)
            for i, m in enumerate(KOPNE_MEMBERS_DEF)
        ],
        supports=[
            SupportDef(node_id=1, type="pinned"),
            SupportDef(node_id=13, type="roller_x"),
        ],
        loads=[
            LoadDef(id=1, type="point_force", node_or_member_id=2, direction="Fy", magnitude=-5.0),
            LoadDef(id=2, type="point_force", node_or_member_id=3, direction="Fy", magnitude=-10.0),
            LoadDef(id=3, type="point_force", node_or_member_id=6, direction="Fy", magnitude=-30.0),
            LoadDef(id=4, type="point_force", node_or_member_id=7, direction="Fy", magnitude=-10.0),
            LoadDef(id=5, type="point_force", node_or_member_id=12, direction="Fy", magnitude=10.0),
            LoadDef(id=6, type="point_force", node_or_member_id=14, direction="Fy", magnitude=-5.0),
        ],
        hinges=[
            HingeDef(member_id=i, start_release=True, end_release=True)
            for i in range(1, 26)
        ],
    )


class TestKopneTruss:
    """
    Kopne truss: 14 nodes, 25 members, all pin-jointed.
    Pinned at node 1 (0,0), roller at node 13 (12,0).

    6 point loads totalling 50 kN downward net.

    Hand calculation (moments about node 1):
        ΣM₁ = (-5)(0) + (-10)(2) + (-30)(4) + (-10)(6) + (+10)(10) + (-5)(12) = -160 kNm
        V₁₃ = 160/12 = 13.333 kN
        V₁ = 50 - 13.333 = 36.667 kN

    This is a regression test for the node mapping bug where anastruct
    swaps node_id1/node_id2 relative to input coordinate order.
    """

    @pytest.fixture
    def result(self):
        model = make_kopne_model()
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_vertical_equilibrium(self, result):
        """Sum of vertical reactions must equal sum of vertical loads (50 kN)."""
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        assert_close(total_ry, 50.0, "ΣRy vs ΣFy")

    def test_horizontal_equilibrium(self, result):
        """No horizontal loads — horizontal reactions must sum to zero."""
        total_rx = sum(r["Rx_kN"] for r in result["reactions"])
        assert_close(total_rx, 0.0, "ΣRx")

    def test_left_reaction(self, result):
        """V₁ = 50 - 160/12 = 36.667 kN."""
        r1 = get_reaction(result, 1)
        assert_close(r1["Ry_kN"], 36.667, "V1")

    def test_right_reaction(self, result):
        """V₁₃ = 160/12 = 13.333 kN."""
        r13 = get_reaction(result, 13)
        assert_close(r13["Ry_kN"], 13.333, "V13")

    def test_all_members_axial_only(self, result):
        """All truss members must have zero shear and bending."""
        for mr in result["member_results"]:
            assert mr["V_max_kN"] < 0.01, f"Member {mr['member_id']} has shear"
            assert mr["M_max_kNm"] < 0.01, f"Member {mr['member_id']} has bending"

    def test_no_equilibrium_warning(self, result):
        """A correctly solved model should produce no equilibrium warnings."""
        assert result["warnings"] == [], f"Unexpected warnings: {result['warnings']}"


# ---------------------------------------------------------------------------
# Test: Simple triangle truss — minimal statically determinate case
# ---------------------------------------------------------------------------


class TestSimpleTriangleTruss:
    """
    Right triangle truss: 3 nodes, 3 members.
    Nodes: A(0,0), B(4,0), C(2,3).
    Pinned at A, roller at B.
    P = 12 kN downward at C.

    Statics:
        ΣM_A = -12*2 + R_B*4 = 0  →  R_B = 6 kN
        R_A_y = 12 - 6 = 6 kN
        R_A_x = 0 (no horizontal loads)
    """

    @pytest.fixture
    def result(self):
        model = ModelDefinition(
            structure_type="truss",
            mesh_size=2,
            materials=[MaterialDef(id=1, name="Steel", E_GPa=210.0)],
            cross_sections=[CrossSectionDef(id=1, A_cm2=20.0, Iz_cm4=10.0, material_id=1)],
            nodes=[
                NodeDef(id=1, x=0.0, y=0.0),
                NodeDef(id=2, x=4.0, y=0.0),
                NodeDef(id=3, x=2.0, y=3.0),
            ],
            members=[
                MemberDef(id=1, start_node=1, end_node=2, section_id=1),
                MemberDef(id=2, start_node=2, end_node=3, section_id=1),
                MemberDef(id=3, start_node=3, end_node=1, section_id=1),
            ],
            supports=[
                SupportDef(node_id=1, type="pinned"),
                SupportDef(node_id=2, type="roller_x"),
            ],
            loads=[
                LoadDef(id=1, type="point_force", node_or_member_id=3, direction="Fy", magnitude=-12.0),
            ],
            hinges=[
                HingeDef(member_id=i, start_release=True, end_release=True)
                for i in range(1, 4)
            ],
        )
        r = solve(model)
        assert r.status == "ok", f"Solve failed: {r.error}"
        return result_to_dict(r)

    def test_vertical_equilibrium(self, result):
        total_ry = sum(r["Ry_kN"] for r in result["reactions"])
        assert_close(total_ry, 12.0, "ΣRy vs P")

    def test_horizontal_equilibrium(self, result):
        total_rx = sum(r["Rx_kN"] for r in result["reactions"])
        assert_close(total_rx, 0.0, "ΣRx")

    def test_left_reaction(self, result):
        r1 = get_reaction(result, 1)
        assert_close(r1["Ry_kN"], 6.0, "R_A_y")

    def test_right_reaction(self, result):
        r2 = get_reaction(result, 2)
        assert_close(r2["Ry_kN"], 6.0, "R_B_y")

    def test_axial_only(self, result):
        for mr in result["member_results"]:
            assert mr["V_max_kN"] < 0.01, f"Member {mr['member_id']} has shear"
            assert mr["M_max_kNm"] < 0.01, f"Member {mr['member_id']} has bending"

    def test_signed_axial_present(self, result):
        """Verify N_signed_kN field is populated for truss members."""
        for mr in result["member_results"]:
            # All members carry axial force under this loading
            assert mr["N_signed_kN"] != 0.0, f"Member {mr['member_id']} has zero signed axial"


# ---------------------------------------------------------------------------
# Test: Mesh independence — reactions must not depend on mesh_size
# ---------------------------------------------------------------------------


class TestTrussMeshIndependence:
    """
    Verify that truss reactions are identical regardless of mesh_size.
    Uses the kopne truss (14 nodes, 25 members) — the model that
    originally exposed the node mapping bug.

    This test catches bugs where mesh subdivision affects node ID mapping.
    """

    @pytest.mark.parametrize("mesh_size", [1, 2, 5, 10, 50])
    def test_reactions_mesh_invariant(self, mesh_size):
        model = make_kopne_model(mesh_size=mesh_size)
        r = solve(model)
        assert r.status == "ok", f"Solve failed with mesh={mesh_size}: {r.error}"
        rd = result_to_dict(r)

        total_ry = sum(rx["Ry_kN"] for rx in rd["reactions"])
        assert_close(total_ry, 50.0, f"ΣRy (mesh={mesh_size})")

        r1 = get_reaction(rd, 1)
        assert_close(r1["Ry_kN"], 36.667, f"V1 (mesh={mesh_size})")

        r13 = get_reaction(rd, 13)
        assert_close(r13["Ry_kN"], 13.333, f"V13 (mesh={mesh_size})")


# ---------------------------------------------------------------------------
# Test: Beam mesh independence — beams also must not depend on mesh_size
# ---------------------------------------------------------------------------


class TestBeamMeshIndependence:
    """
    Verify that beam reactions are identical regardless of mesh_size.
    Uses a simply supported beam with UDL.
    """

    @pytest.mark.parametrize("mesh_size", [1, 2, 5, 50])
    def test_reactions_mesh_invariant(self, mesh_size):
        model = ModelDefinition(
            structure_type="beam",
            mesh_size=mesh_size,
            materials=[MaterialDef(id=1, name="Steel", E_GPa=210.0)],
            cross_sections=[CrossSectionDef(id=1, A_cm2=53.8, Iz_cm4=5410.0, material_id=1)],
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
                LoadDef(id=1, type="UDL", node_or_member_id=1, direction="Fy", magnitude=-10.0),
                LoadDef(id=2, type="UDL", node_or_member_id=2, direction="Fy", magnitude=-10.0),
            ],
        )
        r = solve(model)
        assert r.status == "ok", f"Solve failed with mesh={mesh_size}: {r.error}"
        rd = result_to_dict(r)

        total_ry = sum(rx["Ry_kN"] for rx in rd["reactions"])
        assert_close(total_ry, 60.0, f"ΣRy (mesh={mesh_size})")


# ---------------------------------------------------------------------------
# Test: Equilibrium warning field
# ---------------------------------------------------------------------------


class TestEquilibriumWarning:
    """Verify the equilibrium check produces no warnings for correct models."""

    def test_no_warning_beam(self):
        model = preset_ss_beam_udl()
        r = solve(model)
        assert r.status == "ok"
        assert r.warnings == [], f"Unexpected warnings: {r.warnings}"

    def test_no_warning_truss(self):
        model = preset_warren_truss()
        r = solve(model)
        assert r.status == "ok"
        assert r.warnings == [], f"Unexpected warnings: {r.warnings}"

    def test_no_warning_kopne(self):
        model = make_kopne_model()
        r = solve(model)
        assert r.status == "ok"
        assert r.warnings == [], f"Unexpected warnings: {r.warnings}"
