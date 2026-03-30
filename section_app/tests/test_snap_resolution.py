"""
test_snap_resolution.py — Tests for the three-table snap resolution system.

Verifies that the constraint-based positioning (rectangles + snap points + joints)
correctly resolves rectangle positions matching known preset geometries.

Run: pytest section_app/tests/test_snap_resolution.py -v
"""

import math
import sys
import os

import pandas as pd
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import (
    _edge_snap_forward,
    _edge_snap_inverse,
    _resolve_positions,
    _parts_to_tables,
    _tables_to_parts,
)
from section_solver import RectanglePart


# ---------------------------------------------------------------------------
# Edge snap forward tests
# ---------------------------------------------------------------------------

class TestEdgeSnapForward:
    """Test forward computation of snap point locations on rectangle edges."""

    def test_bottom_edge_start(self):
        """Position 0.0 on bottom edge = corner 1 (BL)."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="bottom",
                                  position=0.0, offset=0.0)
        assert y == pytest.approx(10)
        assert z == pytest.approx(20)

    def test_bottom_edge_end(self):
        """Position 1.0 on bottom edge = corner 2 (BR)."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="bottom",
                                  position=1.0, offset=0.0)
        assert y == pytest.approx(10)
        assert z == pytest.approx(120)

    def test_bottom_edge_mid(self):
        """Position 0.5 on bottom edge = midpoint."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="bottom",
                                  position=0.5, offset=0.0)
        assert y == pytest.approx(10)
        assert z == pytest.approx(70)

    def test_bottom_edge_with_offset(self):
        """Positive offset on bottom edge = outward (downward)."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="bottom",
                                  position=0.5, offset=5.0)
        assert y == pytest.approx(5)   # 10 - 5
        assert z == pytest.approx(70)

    def test_right_edge_mid(self):
        """Position 0.5 on right edge = midpoint of right side."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="right",
                                  position=0.5, offset=0.0)
        assert y == pytest.approx(35)   # 10 + 0.5*50
        assert z == pytest.approx(120)  # 20 + 100

    def test_top_edge_start(self):
        """Position 0.0 on top edge = corner 3 (TR)."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="top",
                                  position=0.0, offset=0.0)
        assert y == pytest.approx(60)   # 10 + 50
        assert z == pytest.approx(120)  # 20 + 100

    def test_top_edge_end(self):
        """Position 1.0 on top edge = corner 4 (TL)."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="top",
                                  position=1.0, offset=0.0)
        assert y == pytest.approx(60)
        assert z == pytest.approx(20)

    def test_top_edge_mid(self):
        """Position 0.5 on top edge = top midpoint."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="top",
                                  position=0.5, offset=0.0)
        assert y == pytest.approx(60)
        assert z == pytest.approx(70)

    def test_left_edge_start(self):
        """Position 0.0 on left edge = corner 4 (TL)."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="left",
                                  position=0.0, offset=0.0)
        assert y == pytest.approx(60)  # 10 + 50*(1-0)
        assert z == pytest.approx(20)

    def test_left_edge_end(self):
        """Position 1.0 on left edge = corner 1 (BL)."""
        y, z = _edge_snap_forward(10, 20, b=100, h=50, edge="left",
                                  position=1.0, offset=0.0)
        assert y == pytest.approx(10)
        assert z == pytest.approx(20)


# ---------------------------------------------------------------------------
# Edge snap inverse tests
# ---------------------------------------------------------------------------

class TestEdgeSnapInverse:
    """Test inverse computation: given target location, solve for rectangle position."""

    def test_bottom_roundtrip(self):
        """Forward then inverse should recover original position."""
        y_bot, z_left = 15.0, 25.0
        b, h = 80.0, 40.0
        for pos in [0.0, 0.25, 0.5, 0.75, 1.0]:
            y_t, z_t = _edge_snap_forward(y_bot, z_left, b, h, "bottom", pos, 0.0)
            yb, zl = _edge_snap_inverse("bottom", pos, 0.0, b, h, y_t, z_t)
            assert yb == pytest.approx(y_bot)
            assert zl == pytest.approx(z_left)

    def test_right_roundtrip(self):
        y_bot, z_left = 15.0, 25.0
        b, h = 80.0, 40.0
        for pos in [0.0, 0.5, 1.0]:
            y_t, z_t = _edge_snap_forward(y_bot, z_left, b, h, "right", pos, 0.0)
            yb, zl = _edge_snap_inverse("right", pos, 0.0, b, h, y_t, z_t)
            assert yb == pytest.approx(y_bot)
            assert zl == pytest.approx(z_left)

    def test_top_roundtrip(self):
        y_bot, z_left = 15.0, 25.0
        b, h = 80.0, 40.0
        for pos in [0.0, 0.5, 1.0]:
            y_t, z_t = _edge_snap_forward(y_bot, z_left, b, h, "top", pos, 0.0)
            yb, zl = _edge_snap_inverse("top", pos, 0.0, b, h, y_t, z_t)
            assert yb == pytest.approx(y_bot)
            assert zl == pytest.approx(z_left)

    def test_left_roundtrip(self):
        y_bot, z_left = 15.0, 25.0
        b, h = 80.0, 40.0
        for pos in [0.0, 0.5, 1.0]:
            y_t, z_t = _edge_snap_forward(y_bot, z_left, b, h, "left", pos, 0.0)
            yb, zl = _edge_snap_inverse("left", pos, 0.0, b, h, y_t, z_t)
            assert yb == pytest.approx(y_bot)
            assert zl == pytest.approx(z_left)

    def test_with_offset_roundtrip(self):
        """Forward+inverse roundtrip with non-zero offset."""
        y_bot, z_left = 10.0, 20.0
        b, h = 100.0, 50.0
        for edge in ["bottom", "right", "top", "left"]:
            y_t, z_t = _edge_snap_forward(y_bot, z_left, b, h, edge, 0.5, 10.0)
            yb, zl = _edge_snap_inverse(edge, 0.5, 10.0, b, h, y_t, z_t)
            assert yb == pytest.approx(y_bot), f"Failed for edge={edge}"
            assert zl == pytest.approx(z_left), f"Failed for edge={edge}"


# ---------------------------------------------------------------------------
# Preset round-trip tests
# ---------------------------------------------------------------------------

class TestPresetRoundTrip:
    """Verify presets survive conversion to 3-table format and resolution."""

    def _roundtrip(self, parts: list[RectanglePart]):
        """Convert parts → tables → resolve → parts, verify match."""
        rects_df, snaps_df, joints_df = _parts_to_tables(parts)
        resolved = _resolve_positions(rects_df, snaps_df, joints_df)
        assert isinstance(resolved, dict), f"Resolution failed: {resolved}"

        result_parts = _tables_to_parts(rects_df, resolved)
        assert len(result_parts) == len(parts)

        for orig, res in zip(parts, result_parts):
            assert res.name == orig.name
            assert res.b == pytest.approx(orig.b)
            assert res.h == pytest.approx(orig.h)
            assert res.y_bot == pytest.approx(orig.y_bot)
            assert res.z_left == pytest.approx(orig.z_left)

    def _load_template_parts(self, template_name: str):
        """Load parts from a template file by searching for a matching name."""
        import json
        import pathlib
        templates_dir = pathlib.Path(__file__).parent.parent / "templates"
        for fp in templates_dir.glob("*.section.json"):
            raw = json.loads(fp.read_text(encoding="utf-8"))
            # Support both new envelope and old format
            if "sfem" in raw:
                name = raw["sfem"].get("name", "")
                parts_list = raw.get("data", {}).get("parts", [])
            else:
                name = raw.get("metadata", {}).get("name", "")
                parts_list = raw.get("parts", [])
            if template_name.lower() in name.lower() or template_name.lower() in fp.stem:
                from section_solver import RectanglePart
                return [
                    RectanglePart(name=p["name"], b=p["b"], h=p["h"],
                                  y_bot=p["y_bot"], z_left=p["z_left"])
                    for p in parts_list
                ]
        raise FileNotFoundError(f"Template '{template_name}' not found")

    def test_i_beam(self):
        self._roundtrip(self._load_template_parts("i_beam"))

    def test_t_section(self):
        self._roundtrip(self._load_template_parts("t_section"))

    def test_l_section(self):
        self._roundtrip(self._load_template_parts("l_section"))

    def test_channel(self):
        self._roundtrip(self._load_template_parts("channel"))

    def test_box_section(self):
        self._roundtrip(self._load_template_parts("box_section"))


# ---------------------------------------------------------------------------
# Constraint resolution tests
# ---------------------------------------------------------------------------

class TestResolution:
    """Test the constraint resolution algorithm."""

    def test_single_rect_absolute(self):
        """Single rectangle anchored by absolute snap."""
        rects = pd.DataFrame([{"Name": "R1", "b": 100.0, "h": 50.0}])
        snaps = pd.DataFrame([
            {"id": 0, "type": "absolute", "horiz_coord": 10.0, "vert_coord": 20.0,
             "component": None, "edge": None, "position": None, "offset": None},
            {"id": 1, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "R1", "edge": "bottom", "position": 0.0, "offset": 0.0},
        ])
        joints = pd.DataFrame([{"snap_1": 0, "snap_2": 1}])

        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, dict)
        y_bot, z_left = resolved["R1"]
        assert y_bot == pytest.approx(20.0)
        assert z_left == pytest.approx(10.0)

    def test_chained_resolution(self):
        """Second rectangle positioned relative to first via edge snaps."""
        rects = pd.DataFrame([
            {"Name": "Base", "b": 200.0, "h": 10.0},
            {"Name": "Column", "b": 10.0, "h": 100.0},
        ])
        snaps = pd.DataFrame([
            # Anchor Base at origin
            {"id": 0, "type": "absolute", "horiz_coord": 0.0, "vert_coord": 0.0,
             "component": None, "edge": None, "position": None, "offset": None},
            {"id": 1, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Base", "edge": "bottom", "position": 0.0, "offset": 0.0},
            # Column bottom-center snaps to Base top-center
            {"id": 2, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Base", "edge": "top", "position": 0.5, "offset": 0.0},
            {"id": 3, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Column", "edge": "bottom", "position": 0.5, "offset": 0.0},
        ])
        joints = pd.DataFrame([
            {"snap_1": 0, "snap_2": 1},   # anchor Base
            {"snap_1": 2, "snap_2": 3},   # Column on top of Base
        ])

        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, dict)

        # Base at origin
        assert resolved["Base"][0] == pytest.approx(0.0)   # y_bot
        assert resolved["Base"][1] == pytest.approx(0.0)   # z_left

        # Column: bottom-center at (10, 100) → y_bot=10, z_left=100-5=95
        assert resolved["Column"][0] == pytest.approx(10.0)
        assert resolved["Column"][1] == pytest.approx(95.0)

    def test_unresolved_rectangle_error(self):
        """Rectangle with no snap/joint returns error message."""
        rects = pd.DataFrame([
            {"Name": "R1", "b": 100.0, "h": 50.0},
            {"Name": "R2", "b": 50.0, "h": 30.0},
        ])
        snaps = pd.DataFrame([
            {"id": 0, "type": "absolute", "horiz_coord": 0.0, "vert_coord": 0.0,
             "component": None, "edge": None, "position": None, "offset": None},
            {"id": 1, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "R1", "edge": "bottom", "position": 0.0, "offset": 0.0},
        ])
        joints = pd.DataFrame([{"snap_1": 0, "snap_2": 1}])

        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, str)
        assert "R2" in resolved

    def test_empty_tables(self):
        """Empty rectangles returns error."""
        rects = pd.DataFrame(columns=["Name", "b", "h"])
        snaps = pd.DataFrame(columns=["id", "type", "horiz_coord", "vert_coord",
                                       "component", "edge", "position", "offset"])
        joints = pd.DataFrame(columns=["snap_1", "snap_2"])
        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, str)


class TestEdgeWithOffset:
    """Test edge snap with perpendicular offsets."""

    def test_bottom_offset_gap(self):
        """Column placed with 5mm gap below base using bottom edge offset."""
        rects = pd.DataFrame([
            {"Name": "Base", "b": 100.0, "h": 10.0},
            {"Name": "Below", "b": 50.0, "h": 20.0},
        ])
        snaps = pd.DataFrame([
            {"id": 0, "type": "absolute", "horiz_coord": 0.0, "vert_coord": 0.0,
             "component": None, "edge": None, "position": None, "offset": None},
            {"id": 1, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Base", "edge": "bottom", "position": 0.0, "offset": 0.0},
            # Point on Base bottom edge, offset 5mm outward (downward)
            {"id": 2, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Base", "edge": "bottom", "position": 0.5, "offset": 5.0},
            # Below's top midpoint
            {"id": 3, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Below", "edge": "top", "position": 0.5, "offset": 0.0},
        ])
        joints = pd.DataFrame([
            {"snap_1": 0, "snap_2": 1},
            {"snap_1": 2, "snap_2": 3},
        ])

        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, dict)
        # Base bottom edge mid with 5mm offset = (0-5, 50) = (-5, 50)
        # Below top mid at (-5, 50) → y_bot = -5 - 20 = -25, z_left = 50 - 25 = 25
        assert resolved["Below"][0] == pytest.approx(-25.0)
        assert resolved["Below"][1] == pytest.approx(25.0)


class TestOffsetRef:
    """Test offset referencing a rectangle dimension for parametric sections."""

    def test_offset_ref_height(self):
        """Use flange height as offset to place web above flange."""
        rects = pd.DataFrame([
            {"Name": "Flange", "b": 200.0, "h": 15.0},
            {"Name": "Web", "b": 10.0, "h": 100.0},
        ])
        snaps = pd.DataFrame([
            # Anchor flange at origin
            {"id": 0, "type": "absolute", "horiz_coord": 0.0, "vert_coord": 0.0,
             "component": None, "edge": None, "position": None, "offset": None,
             "offset_ref": None, "offset_dim": None},
            {"id": 1, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Flange", "edge": "bottom", "position": 0.0, "offset": 0.0,
             "offset_ref": None, "offset_dim": None},
            # Web bottom-center snaps to flange bottom-center with offset = flange height
            # This effectively places web ON TOP of flange (offset pushes outward = down,
            # but the INVERSE places it correctly)
            # Actually, let's snap web bottom-center to flange top-center directly
            {"id": 2, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Flange", "edge": "top", "position": 0.5, "offset": 0.0,
             "offset_ref": None, "offset_dim": None},
            {"id": 3, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Web", "edge": "bottom", "position": 0.5, "offset": 0.0,
             "offset_ref": None, "offset_dim": None},
        ])
        joints = pd.DataFrame([
            {"snap_1": 0, "snap_2": 1},
            {"snap_1": 2, "snap_2": 3},
        ])

        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, dict)
        # Web bottom-center at flange top-center: (15, 100)
        # Web: y_bot=15, z_left=100-5=95
        assert resolved["Web"][0] == pytest.approx(15.0)
        assert resolved["Web"][1] == pytest.approx(95.0)

    def test_offset_ref_parametric_gap(self):
        """Offset = flange height + 5mm gap using offset_ref."""
        rects = pd.DataFrame([
            {"Name": "Base", "b": 100.0, "h": 20.0},
            {"Name": "Upper", "b": 100.0, "h": 30.0},
        ])
        snaps = pd.DataFrame([
            {"id": 0, "type": "absolute", "horiz_coord": 0.0, "vert_coord": 0.0,
             "component": None, "edge": None, "position": None, "offset": None,
             "offset_ref": None, "offset_dim": None},
            {"id": 1, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Base", "edge": "bottom", "position": 0.0, "offset": 0.0,
             "offset_ref": None, "offset_dim": None},
            # Upper's bottom-left at Base's bottom-left, with offset_ref=Base height
            # Offset outward from bottom edge = downward, but offset_ref adds Base.h
            # So effective offset = 20 + 0 = 20mm downward from Base bottom
            # Actually let's use top edge with offset_ref for the gap
            # Point on Base top, with offset = Base.h (upward from top) + 5mm
            {"id": 2, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Base", "edge": "top", "position": 0.5, "offset": 5.0,
             "offset_ref": None, "offset_dim": None},
            {"id": 3, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Upper", "edge": "bottom", "position": 0.5, "offset": 0.0,
             "offset_ref": None, "offset_dim": None},
        ])
        joints = pd.DataFrame([
            {"snap_1": 0, "snap_2": 1},
            {"snap_1": 2, "snap_2": 3},
        ])

        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, dict)
        # Base top at pos=0.5 with 5mm offset upward: (20+5, 50) = (25, 50)
        # Upper bottom-center at (25, 50): y_bot=25, z_left=0
        assert resolved["Upper"][0] == pytest.approx(25.0)
        assert resolved["Upper"][1] == pytest.approx(0.0)

    def test_offset_ref_uses_dimension(self):
        """offset_ref + offset_dim uses the referenced rectangle's dimension."""
        rects = pd.DataFrame([
            {"Name": "Plate", "b": 80.0, "h": 12.0},
            {"Name": "Stiff", "b": 8.0, "h": 60.0},
        ])
        snaps = pd.DataFrame([
            {"id": 0, "type": "absolute", "horiz_coord": 0.0, "vert_coord": 0.0,
             "component": None, "edge": None, "position": None, "offset": None,
             "offset_ref": None, "offset_dim": None},
            {"id": 1, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Plate", "edge": "bottom", "position": 0.0, "offset": 0.0,
             "offset_ref": None, "offset_dim": None},
            # Stiffener bottom-center, offset from Plate right edge by Stiff width
            # right edge outward = rightward. offset_ref=Stiff, offset_dim=width → 8mm
            # So snap point = Plate right edge mid + 8mm right
            {"id": 2, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Plate", "edge": "right", "position": 0.5,
             "offset": 0.0,
             "offset_ref": "Stiff", "offset_dim": "width"},
            {"id": 3, "type": "edge", "horiz_coord": None, "vert_coord": None,
             "component": "Stiff", "edge": "left", "position": 0.5, "offset": 0.0,
             "offset_ref": None, "offset_dim": None},
        ])
        joints = pd.DataFrame([
            {"snap_1": 0, "snap_2": 1},
            {"snap_1": 2, "snap_2": 3},
        ])

        resolved = _resolve_positions(rects, snaps, joints)
        assert isinstance(resolved, dict)
        # Plate right edge mid (pos=0.5): y=0+0.5*12=6, z=0+80=80
        # With offset_ref=Stiff width=8: effective offset=8+0=8 outward (rightward)
        # Snap point: (6, 80+8) = (6, 88)
        # Stiff left edge mid (pos=0.5) at (6, 88):
        #   left edge: y = y_bot + h*(1-pos) = y_bot + 30
        #   z = z_left - offset = z_left
        #   So: y_bot + 30 = 6 → y_bot = -24
        #   z_left = 88
        assert resolved["Stiff"][0] == pytest.approx(-24.0)
        assert resolved["Stiff"][1] == pytest.approx(88.0)
