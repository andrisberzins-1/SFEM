"""
test_robustness.py — Edge case tests for the FEM solver.

Each case must return a clear error message dict, not raise a Python exception.
Assert response contains "error" key with non-empty string.

Uses solver.py directly (no HTTP, no Streamlit).
Run with: pytest tests/test_robustness.py -v
"""

import sys
import os

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solver import (
    ModelDefinition, NodeDef, MemberDef, SupportDef, LoadDef,
    MaterialDef, CrossSectionDef, HingeDef,
    solve, result_to_dict,
)

# Default material and section for tests that need them
DEFAULT_MAT = MaterialDef(id=1, name="Steel", E_GPa=210.0)
DEFAULT_SEC = CrossSectionDef(id=1, name="Default", A_cm2=100.0, Iz_cm4=10000.0, material_id=1)


def make_model(**kwargs) -> ModelDefinition:
    """Create a model with default material/section unless overridden."""
    kwargs.setdefault("materials", [DEFAULT_MAT])
    kwargs.setdefault("cross_sections", [DEFAULT_SEC])
    return ModelDefinition(**kwargs)


def solve_and_check_error(model):
    """Solve the model and verify it returns an error (not an exception)."""
    result = solve(model)
    d = result_to_dict(result)
    assert d["status"] == "error", f"Expected error status, got: {d['status']}"
    assert d["error"] is not None, "Error message should not be None"
    assert len(d["error"]) > 0, "Error message should not be empty"
    return d["error"]


class TestEmptyModel:
    """Empty model — no nodes, no members."""

    def test_no_nodes(self):
        model = ModelDefinition()
        msg = solve_and_check_error(model)
        assert "node" in msg.lower()

    def test_nodes_but_no_members(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0)],
        )
        msg = solve_and_check_error(model)
        assert "member" in msg.lower()

    def test_nodes_members_but_no_supports(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
        )
        msg = solve_and_check_error(model)
        assert "support" in msg.lower()

    def test_nodes_members_supports_but_no_loads(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
        )
        msg = solve_and_check_error(model)
        assert "load" in msg.lower()


class TestZeroLengthMember:
    """Member with start_node == end_node."""

    def test_same_start_end_node(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=1)],
            supports=[SupportDef(node_id=1, type="pinned")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "same" in msg.lower() or "zero" in msg.lower()


class TestDuplicateNodeCoordinates:
    """Two different node IDs at the same coordinates."""

    def test_duplicate_coords(self):
        model = make_model(
            nodes=[
                NodeDef(id=1, x=0, y=0),
                NodeDef(id=2, x=0, y=0),  # same as node 1
                NodeDef(id=3, x=6, y=0),
            ],
            members=[MemberDef(id=1, start_node=1, end_node=3)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=3, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "coordinate" in msg.lower() or "same" in msg.lower()


class TestDuplicateIDs:
    """Duplicate node or member IDs."""

    def test_duplicate_node_ids(self):
        model = make_model(
            nodes=[
                NodeDef(id=1, x=0, y=0),
                NodeDef(id=1, x=6, y=0),  # duplicate
            ],
            members=[MemberDef(id=1, start_node=1, end_node=1)],
            supports=[SupportDef(node_id=1, type="pinned")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "duplicate" in msg.lower()

    def test_duplicate_member_ids(self):
        model = make_model(
            nodes=[
                NodeDef(id=1, x=0, y=0),
                NodeDef(id=2, x=3, y=0),
                NodeDef(id=3, x=6, y=0),
            ],
            members=[
                MemberDef(id=1, start_node=1, end_node=2),
                MemberDef(id=1, start_node=2, end_node=3),  # duplicate
            ],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=3, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=2,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "duplicate" in msg.lower()


class TestNonExistentReferences:
    """References to node/member IDs that don't exist."""

    def test_member_references_missing_node(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=99)],  # 99 doesn't exist
            supports=[SupportDef(node_id=1, type="pinned")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "non-existent" in msg.lower() or "not" in msg.lower()

    def test_load_on_missing_node(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=99,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "non-existent" in msg.lower() or "not" in msg.lower()

    def test_udl_on_missing_member(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="UDL", node_or_member_id=99,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "non-existent" in msg.lower() or "not" in msg.lower()

    def test_support_on_missing_node(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            supports=[SupportDef(node_id=99, type="pinned")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "non-existent" in msg.lower() or "not" in msg.lower()


class TestMechanism:
    """Structure is a mechanism (insufficient supports)."""

    def test_roller_both_ends(self):
        """Beam with roller at both ends — no horizontal restraint."""
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            supports=[
                SupportDef(node_id=1, type="roller_x"),
                SupportDef(node_id=2, type="roller_x"),
            ],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fx", magnitude=10)],
        )
        msg = solve_and_check_error(model)
        assert "error" in msg.lower() or "singular" in msg.lower() or "mechanism" in msg.lower() or "unstable" in msg.lower() or "fail" in msg.lower()


class TestSingleNodeWithLoad:
    """Single node with load but no members."""

    def test_single_node_load(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0)],
            members=[],
            supports=[SupportDef(node_id=1, type="fixed")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "member" in msg.lower() or "no" in msg.lower()


class TestFreeFloatingNode:
    """Node defined but not connected to any member."""

    def test_unconnected_support_node(self):
        model = make_model(
            nodes=[
                NodeDef(id=1, x=0, y=0),
                NodeDef(id=2, x=6, y=0),
                NodeDef(id=3, x=10, y=0),  # not connected to anything
            ],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            supports=[
                SupportDef(node_id=1, type="pinned"),
                SupportDef(node_id=2, type="roller_x"),
                SupportDef(node_id=3, type="pinned"),  # on unconnected node
            ],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "not connected" in msg.lower() or "member" in msg.lower()


class TestOverConstrained:
    """Over-constrained system should solve successfully, not error."""

    def test_three_fixed_supports(self):
        """Beam with 3 fixed supports — highly redundant but valid."""
        model = make_model(
            structure_type="beam",
            nodes=[
                NodeDef(id=1, x=0, y=0),
                NodeDef(id=2, x=3, y=0),
                NodeDef(id=3, x=6, y=0),
            ],
            members=[
                MemberDef(id=1, start_node=1, end_node=2),
                MemberDef(id=2, start_node=2, end_node=3),
            ],
            supports=[
                SupportDef(node_id=1, type="fixed"),
                SupportDef(node_id=2, type="fixed"),
                SupportDef(node_id=3, type="fixed"),
            ],
            loads=[
                LoadDef(id=1, type="point_force", node_or_member_id=2,
                        direction="Fy", magnitude=-10),
            ],
        )
        result = solve(model)
        d = result_to_dict(result)
        # Should solve successfully
        assert d["status"] == "ok", f"Over-constrained should solve, got: {d.get('error')}"
        # Equilibrium should still hold
        total_ry = sum(r["Ry_kN"] for r in d["reactions"])
        assert abs(total_ry - 10.0) < 0.1, f"ΣRy should be 10, got {total_ry}"


class TestCollinearTruss:
    """All truss nodes on the same line — mechanism."""

    def test_collinear_truss(self):
        model = make_model(
            structure_type="truss",
            nodes=[
                NodeDef(id=1, x=0, y=0),
                NodeDef(id=2, x=3, y=0),
                NodeDef(id=3, x=6, y=0),
            ],
            members=[
                MemberDef(id=1, start_node=1, end_node=2),
                MemberDef(id=2, start_node=2, end_node=3),
            ],
            hinges=[
                HingeDef(member_id=1, start_release=True, end_release=True),
                HingeDef(member_id=2, start_release=True, end_release=True),
            ],
            supports=[
                SupportDef(node_id=1, type="pinned"),
                SupportDef(node_id=3, type="roller_x"),
            ],
            loads=[
                LoadDef(id=1, type="point_force", node_or_member_id=2,
                        direction="Fy", magnitude=-10),
            ],
        )
        msg = solve_and_check_error(model)
        assert len(msg) > 0


class TestUnstableFrame:
    """Frame with insufficient supports for load direction."""

    def test_only_vertical_support_horizontal_load(self):
        """Single roller in Y (restrains X only) with vertical load applied."""
        model = make_model(
            nodes=[
                NodeDef(id=1, x=0, y=0),
                NodeDef(id=2, x=0, y=4),
            ],
            members=[
                MemberDef(id=1, start_node=1, end_node=2),
            ],
            supports=[
                # roller_y: free in Y, restrained in X — no vertical support
                SupportDef(node_id=1, type="roller_y"),
            ],
            loads=[
                LoadDef(id=1, type="point_force", node_or_member_id=2,
                        direction="Fy", magnitude=-10),
            ],
        )
        msg = solve_and_check_error(model)
        assert len(msg) > 0


class TestNewValidation:
    """Tests for new validation rules (materials, sections, hinges)."""

    def test_missing_materials(self):
        model = ModelDefinition(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            cross_sections=[DEFAULT_SEC],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "material" in msg.lower()

    def test_missing_cross_sections(self):
        model = ModelDefinition(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            materials=[DEFAULT_MAT],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "cross-section" in msg.lower()

    def test_member_invalid_section_ref(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2, section_id=99)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "cross-section" in msg.lower() or "section" in msg.lower()

    def test_section_invalid_material_ref(self):
        model = ModelDefinition(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            materials=[DEFAULT_MAT],
            cross_sections=[CrossSectionDef(id=1, name="Bad", A_cm2=100, Iz_cm4=10000, material_id=99)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "material" in msg.lower()

    def test_hinge_invalid_member_ref(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            hinges=[HingeDef(member_id=99, start_release=True, end_release=True)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "hinge" in msg.lower() or "member" in msg.lower()

    def test_hinge_no_releases(self):
        model = make_model(
            nodes=[NodeDef(id=1, x=0, y=0), NodeDef(id=2, x=6, y=0)],
            members=[MemberDef(id=1, start_node=1, end_node=2)],
            hinges=[HingeDef(member_id=1, start_release=False, end_release=False)],
            supports=[SupportDef(node_id=1, type="pinned"),
                      SupportDef(node_id=2, type="roller_x")],
            loads=[LoadDef(id=1, type="point_force", node_or_member_id=1,
                          direction="Fy", magnitude=-10)],
        )
        msg = solve_and_check_error(model)
        assert "release" in msg.lower() or "hinge" in msg.lower()
