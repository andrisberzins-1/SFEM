"""
app.py — Streamlit frontend for cross-section properties calculator.

This file does NOT implement any calculations. All math goes through
section_solver.py.

Layout follows fem_app conventions:
  - Sidebar: presets, settings
  - Main area: vertical stacking (cross-section view, then components, then results)

Launch: streamlit run app.py --server.port 8503
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from section_solver import (
    RectanglePart,
    SectionResult,
    calculate,
    validate_parts,
    MM2_TO_CM2,
    MM4_TO_CM4,
    MM3_TO_CM3,
)
from presets import PRESETS

TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "Cross-Section Properties"
APP_ICON = "\U0001f4d0"  # triangular ruler

# Colors for rectangle parts (up to 8 distinct)
PART_COLORS = [
    "rgba(31, 119, 180, 0.4)",   # blue
    "rgba(255, 127, 14, 0.4)",   # orange
    "rgba(44, 160, 44, 0.4)",    # green
    "rgba(214, 39, 40, 0.4)",    # red
    "rgba(148, 103, 189, 0.4)",  # purple
    "rgba(140, 86, 75, 0.4)",    # brown
    "rgba(227, 119, 194, 0.4)",  # pink
    "rgba(127, 127, 127, 0.4)",  # gray
]

PART_BORDER_COLORS = [
    "rgba(31, 119, 180, 1)",
    "rgba(255, 127, 14, 1)",
    "rgba(44, 160, 44, 1)",
    "rgba(214, 39, 40, 1)",
    "rgba(148, 103, 189, 1)",
    "rgba(140, 86, 75, 1)",
    "rgba(227, 119, 194, 1)",
    "rgba(127, 127, 127, 1)",
]

CORNER_MARKER_COLOR = "rgba(80, 80, 80, 0.5)"
CORNER_MARKER_SIZE = 4

# Edge definitions
# Corners: 1=BL, 2=BR, 3=TR, 4=TL (clockwise from bottom-left)
# Edges named by start→end corner
EDGE_OPTIONS = ["bottom", "right", "top", "left"]
EDGE_LABELS = {
    "bottom": "12 (bottom)",
    "right":  "23 (right)",
    "top":    "34 (top)",
    "left":   "41 (left)",
}

SNAP_TYPE_OPTIONS = ["absolute", "edge"]

# Axis convention configurations
# Internal solver: y_bot = vertical coord, z_left = horizontal coord
# Iy = moment about horizontal axis (uses vertical distances dy)
# Iz = moment about vertical axis (uses horizontal distances dz)
#
# EN 1993 Eurocode: y = horizontal, z = vertical
#   I_y = moment about y (horizontal) axis = solver's Iy  (strong axis for I-beams)
#   I_z = moment about z (vertical) axis   = solver's Iz
#
# Basic x,y: x = horizontal, y = vertical
#   I_x = moment about x (horizontal) axis = solver's Iy
#   I_y = moment about y (vertical) axis   = solver's Iz

AXIS_CONVENTIONS = {
    "yz_eurocode": {
        "label": "y, z (Eurocode)",
        "horiz_axis": "y",   "vert_axis": "z",
        "horiz_label": "y",  "vert_label": "z",
        "I_vert": "I_y",     "I_horiz": "I_z",
        "W_vert": "W_y",     "W_horiz": "W_z",
        "i_vert": "i_y",     "i_horiz": "i_z",
    },
    "xy_basic": {
        "label": "x, y (basic)",
        "horiz_axis": "x",   "vert_axis": "y",
        "horiz_label": "x",  "vert_label": "y",
        "I_vert": "I_x",     "I_horiz": "I_y",
        "W_vert": "W_x",     "W_horiz": "W_y",
        "i_vert": "i_x",     "i_horiz": "i_y",
    },
}


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
)

# Custom CSS: top padding, narrower tables, left-aligned LaTeX
st.markdown("""<style>
.block-container { padding-top: 2.5rem; }

/* Data-editor: constrain width so 3-column tables aren't stretched */
.stDataFrame {
    width: fit-content !important;
    min-width: 300px;
    max-width: 100%;
}
.stDataFrame > div:last-child {
    width: fit-content !important;
    max-width: 100%;
}

/* Left-align LaTeX — override Streamlit auto-margin centering + KaTeX text-align */
[data-testid="stMarkdown"] > div {
    margin-left: 0 !important;
    margin-right: auto !important;
}
span.katex-display {
    text-align: left !important;
}
span.katex-display > span.katex {
    text-align: left !important;
}
</style>""", unsafe_allow_html=True)

st.title(f"{APP_ICON} {APP_TITLE}")


# ---------------------------------------------------------------------------
# Helper functions — general
# ---------------------------------------------------------------------------

def _get_conv() -> dict:
    """Get current axis convention config."""
    return AXIS_CONVENTIONS[st.session_state.axis_convention]


def _sub(text: str) -> str:
    """Format property label with HTML subscript.

    Examples: 'I_y' -> 'I<sub>y</sub>'
    """
    if "_" in text:
        base, subscript = text.split("_", 1)
        return f"{base}<sub>{subscript}</sub>"
    return text


# ---------------------------------------------------------------------------
# Snap resolution functions
# ---------------------------------------------------------------------------

def _edge_snap_forward(y_bot: float, z_left: float, b: float, h: float,
                       edge: str, position: float, offset: float
                       ) -> tuple[float, float]:
    """Compute snap point location on a rectangle edge.

    Args:
        y_bot, z_left: rectangle position (internal coords)
        b, h: rectangle dimensions (width=horiz, height=vert)
        edge: "bottom", "right", "top", "left"
        position: 0.0-1.0 along edge (0=start corner, 1=end corner)
        offset: perpendicular distance outward from rectangle

    Returns:
        (y, z) coordinates of the snap point
    """
    if edge == "bottom":    # C1(BL) → C2(BR), outward = down (-y)
        return (y_bot - offset, z_left + position * b)
    elif edge == "right":   # C2(BR) → C3(TR), outward = right (+z)
        return (y_bot + position * h, z_left + b + offset)
    elif edge == "top":     # C3(TR) → C4(TL), outward = up (+y)
        return (y_bot + h + offset, z_left + b * (1 - position))
    elif edge == "left":    # C4(TL) → C1(BL), outward = left (-z)
        return (y_bot + h * (1 - position), z_left - offset)
    else:
        raise ValueError(f"Unknown edge: {edge}")


def _edge_snap_inverse(edge: str, position: float, offset: float,
                       b: float, h: float,
                       y_target: float, z_target: float
                       ) -> tuple[float, float]:
    """Solve for rectangle position given a target snap point location.

    Returns:
        (y_bot, z_left) that places the snap point at (y_target, z_target)
    """
    if edge == "bottom":
        return (y_target + offset, z_target - position * b)
    elif edge == "right":
        return (y_target - position * h, z_target - b - offset)
    elif edge == "top":
        return (y_target - h - offset, z_target - b * (1 - position))
    elif edge == "left":
        return (y_target - h * (1 - position), z_target + offset)
    else:
        raise ValueError(f"Unknown edge: {edge}")


def _resolve_positions(rects_df: pd.DataFrame, snaps_df: pd.DataFrame,
                       joints_df: pd.DataFrame
                       ) -> dict[str, tuple[float, float]] | str:
    """Resolve rectangle positions from snap points and joints.

    Returns:
        dict {rect_name: (y_bot, z_left)} or error message string.
    """
    if rects_df is None or len(rects_df) == 0:
        return "No rectangles defined."

    # Build rectangle info: name -> (b, h)
    rect_dims: dict[str, tuple[float, float]] = {}
    for _, row in rects_df.iterrows():
        name = str(row["Name"]) if pd.notna(row["Name"]) else ""
        if not name:
            continue
        b = row.get("b")
        h = row.get("h")
        if pd.isna(b) or pd.isna(h) or b <= 0 or h <= 0:
            continue
        rect_dims[name] = (float(b), float(h))

    if not rect_dims:
        return "No valid rectangles defined (check dimensions)."

    # Build snap point definitions: id -> snap_info
    snap_defs: dict[int, dict] = {}
    if snaps_df is not None:
        for _, row in snaps_df.iterrows():
            sid = row.get("id")
            if pd.isna(sid):
                continue
            sid = int(sid)
            stype = row.get("type")
            if pd.isna(stype) or stype not in SNAP_TYPE_OPTIONS:
                continue

            if stype == "absolute":
                vc = row.get("vert_coord")
                hc = row.get("horiz_coord")
                if pd.isna(vc) or pd.isna(hc):
                    continue
                snap_defs[sid] = {"type": "absolute", "y": float(vc), "z": float(hc)}
            else:  # edge
                comp = row.get("component")
                edge = row.get("edge")
                pos = row.get("position")
                if pd.isna(comp) or pd.isna(edge) or pd.isna(pos):
                    continue
                comp = str(comp)
                edge = str(edge)
                if comp not in rect_dims:
                    continue
                if edge not in EDGE_OPTIONS:
                    continue
                off = float(row.get("offset", 0)) if pd.notna(row.get("offset")) else 0.0

                # Offset reference: use a rectangle dimension as base offset
                off_ref = row.get("offset_ref")
                off_dim = row.get("offset_dim")
                if pd.notna(off_ref) and pd.notna(off_dim):
                    ref_name = str(off_ref)
                    if ref_name in rect_dims:
                        b_r, h_r = rect_dims[ref_name]
                        dim_val = b_r if str(off_dim) == "width" else h_r
                        off = dim_val + off  # dimension + additional offset

                snap_defs[sid] = {
                    "type": "edge", "component": comp,
                    "edge": edge, "position": float(pos), "offset": off,
                }

    # Build joint list: [(snap_1_id, snap_2_id), ...]
    joint_list: list[tuple[int, int]] = []
    if joints_df is not None:
        for _, row in joints_df.iterrows():
            s1 = row.get("snap_1")
            s2 = row.get("snap_2")
            if pd.isna(s1) or pd.isna(s2):
                continue
            s1, s2 = int(s1), int(s2)
            if s1 in snap_defs and s2 in snap_defs:
                joint_list.append((s1, s2))

    # Iterative resolution
    positions: dict[str, tuple[float, float]] = {}  # rect_name -> (y_bot, z_left)
    max_iterations = len(rect_dims) + 1
    for _ in range(max_iterations):
        progress = False
        for s1_id, s2_id in joint_list:
            s1 = snap_defs[s1_id]
            s2 = snap_defs[s2_id]
            loc1 = _try_resolve_snap(s1, positions, rect_dims)
            loc2 = _try_resolve_snap(s2, positions, rect_dims)

            if loc1 is not None and loc2 is not None:
                # Both resolved — constraint already satisfied (or over-constrained)
                continue

            if loc1 is not None and loc2 is None:
                # loc1 known, solve for loc2's rectangle
                if s2["type"] == "edge" and s2["component"] not in positions:
                    comp = s2["component"]
                    b, h = rect_dims[comp]
                    y_bot, z_left = _edge_snap_inverse(
                        s2["edge"], s2["position"], s2["offset"],
                        b, h, loc1[0], loc1[1],
                    )
                    positions[comp] = (y_bot, z_left)
                    progress = True

            elif loc2 is not None and loc1 is None:
                # loc2 known, solve for loc1's rectangle
                if s1["type"] == "edge" and s1["component"] not in positions:
                    comp = s1["component"]
                    b, h = rect_dims[comp]
                    y_bot, z_left = _edge_snap_inverse(
                        s1["edge"], s1["position"], s1["offset"],
                        b, h, loc2[0], loc2[1],
                    )
                    positions[comp] = (y_bot, z_left)
                    progress = True

        if not progress:
            break

    # Check for unresolved rectangles
    unresolved = [name for name in rect_dims if name not in positions]
    if unresolved:
        return f"Cannot resolve positions for: {', '.join(unresolved)}. Add snap points and joints to connect them."

    return positions


def _try_resolve_snap(snap: dict, positions: dict[str, tuple[float, float]],
                      rect_dims: dict[str, tuple[float, float]]
                      ) -> tuple[float, float] | None:
    """Try to compute a snap point's absolute location.

    Returns (y, z) if resolvable, None otherwise.
    """
    if snap["type"] == "absolute":
        return (snap["y"], snap["z"])

    # Edge snap — needs rectangle to be positioned
    comp = snap["component"]
    if comp not in positions:
        return None
    y_bot, z_left = positions[comp]
    b, h = rect_dims[comp]
    return _edge_snap_forward(y_bot, z_left, b, h,
                              snap["edge"], snap["position"], snap["offset"])


# ---------------------------------------------------------------------------
# Preset conversion: RectanglePart list → three tables
# ---------------------------------------------------------------------------

# Snap point position formulas for each edge:
#   bottom (1→2): z = z_left + pos * b         → pos = (z - z_left) / b
#   top    (3→4): z = z_left + b * (1 - pos)   → pos = (z_left + b - z) / b
#   right  (2→3): y = y_bot + pos * h           → pos = (y - y_bot) / h
#   left   (4→1): y = y_bot + h * (1 - pos)     → pos = (y_bot + h - y) / h

def _find_connection(new_part: RectanglePart,
                     existing_parts: list[RectanglePart]
                     ) -> tuple[str, str, float, str, float] | None:
    """Find an edge adjacency between new_part and an existing part.

    Returns (ref_name, ref_edge, ref_pos, new_edge, new_pos) or None.
    Uses the midpoint of the overlap zone as the connection point.
    """
    TOL = 0.01
    np_ = new_part

    for ref in existing_parts:
        # --- New on top of ref (horizontal shared edge) ---
        if abs(np_.y_bot - (ref.y_bot + ref.h)) < TOL:
            z_start = max(np_.z_left, ref.z_left)
            z_end = min(np_.z_left + np_.b, ref.z_left + ref.b)
            if z_end - z_start > TOL:
                mid_z = (z_start + z_end) / 2
                ref_pos = (ref.z_left + ref.b - mid_z) / ref.b  # top edge
                new_pos = (mid_z - np_.z_left) / np_.b           # bottom edge
                return (ref.name, "top", ref_pos, "bottom", new_pos)

        # --- New below ref ---
        if abs(np_.y_bot + np_.h - ref.y_bot) < TOL:
            z_start = max(np_.z_left, ref.z_left)
            z_end = min(np_.z_left + np_.b, ref.z_left + ref.b)
            if z_end - z_start > TOL:
                mid_z = (z_start + z_end) / 2
                ref_pos = (mid_z - ref.z_left) / ref.b           # bottom edge
                new_pos = (np_.z_left + np_.b - mid_z) / np_.b   # top edge
                return (ref.name, "bottom", ref_pos, "top", new_pos)

        # --- New to right of ref ---
        if abs(np_.z_left - (ref.z_left + ref.b)) < TOL:
            y_start = max(np_.y_bot, ref.y_bot)
            y_end = min(np_.y_bot + np_.h, ref.y_bot + ref.h)
            if y_end - y_start > TOL:
                mid_y = (y_start + y_end) / 2
                ref_pos = (mid_y - ref.y_bot) / ref.h            # right edge
                new_pos = (np_.y_bot + np_.h - mid_y) / np_.h    # left edge
                return (ref.name, "right", ref_pos, "left", new_pos)

        # --- New to left of ref ---
        if abs(np_.z_left + np_.b - ref.z_left) < TOL:
            y_start = max(np_.y_bot, ref.y_bot)
            y_end = min(np_.y_bot + np_.h, ref.y_bot + ref.h)
            if y_end - y_start > TOL:
                mid_y = (y_start + y_end) / 2
                ref_pos = (np_.y_bot + np_.h - mid_y) / ref.h    # left edge
                new_pos = (mid_y - np_.y_bot) / np_.h             # right edge
                return (ref.name, "left", ref_pos, "right", new_pos)

    return None


def _empty_snap_row(**kwargs) -> dict:
    """Create a snap row with all columns, filling missing with None."""
    row = {
        "id": None, "type": None,
        "horiz_coord": None, "vert_coord": None,
        "component": None, "edge": None, "position": None, "offset": None,
        "offset_ref": None, "offset_dim": None,
    }
    row.update(kwargs)
    return row


def _parts_to_tables(parts: list[RectanglePart]
                     ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convert preset RectangleParts into the three-table format.

    First rectangle: anchored at origin via absolute snap.
    Subsequent rectangles: connected to existing rectangles via edge snaps
    (auto-detected from edge adjacency). Falls back to absolute snap if
    no adjacency is found.
    """
    rects_rows = []
    snaps_rows = []
    joints_rows = []
    snap_id = 0

    for i, p in enumerate(parts):
        rects_rows.append({"Name": p.name, "b": p.b, "h": p.h})

        if i == 0:
            # First rectangle: anchor at origin
            snaps_rows.append(_empty_snap_row(
                id=snap_id, type="absolute",
                horiz_coord=p.z_left, vert_coord=p.y_bot,
            ))
            abs_snap = snap_id
            snap_id += 1

            snaps_rows.append(_empty_snap_row(
                id=snap_id, type="edge",
                component=p.name, edge="bottom", position=0.0, offset=0.0,
            ))
            edge_snap = snap_id
            snap_id += 1

            joints_rows.append({"snap_1": abs_snap, "snap_2": edge_snap})
        else:
            # Try to find edge connection to an existing rectangle
            conn = _find_connection(p, [parts[j] for j in range(i)])

            if conn is not None:
                ref_name, ref_edge, ref_pos, new_edge, new_pos = conn

                # Snap on reference rectangle's edge
                snaps_rows.append(_empty_snap_row(
                    id=snap_id, type="edge",
                    component=ref_name, edge=ref_edge,
                    position=ref_pos, offset=0.0,
                ))
                ref_snap = snap_id
                snap_id += 1

                # Snap on new rectangle's edge
                snaps_rows.append(_empty_snap_row(
                    id=snap_id, type="edge",
                    component=p.name, edge=new_edge,
                    position=new_pos, offset=0.0,
                ))
                new_snap = snap_id
                snap_id += 1

                joints_rows.append({"snap_1": ref_snap, "snap_2": new_snap})
            else:
                # Fallback: absolute snap (no edge adjacency found)
                snaps_rows.append(_empty_snap_row(
                    id=snap_id, type="absolute",
                    horiz_coord=p.z_left, vert_coord=p.y_bot,
                ))
                abs_snap = snap_id
                snap_id += 1

                snaps_rows.append(_empty_snap_row(
                    id=snap_id, type="edge",
                    component=p.name, edge="bottom", position=0.0, offset=0.0,
                ))
                edge_snap = snap_id
                snap_id += 1

                joints_rows.append({"snap_1": abs_snap, "snap_2": edge_snap})

    rects_df = pd.DataFrame(rects_rows)
    snaps_df = pd.DataFrame(snaps_rows)
    joints_df = pd.DataFrame(joints_rows)

    return rects_df, snaps_df, joints_df


def _tables_to_parts(rects_df: pd.DataFrame,
                     positions: dict[str, tuple[float, float]]
                     ) -> list[RectanglePart]:
    """Build RectanglePart list from rectangles + resolved positions."""
    parts = []
    for _, row in rects_df.iterrows():
        name = str(row["Name"]) if pd.notna(row["Name"]) else ""
        if not name or name not in positions:
            continue
        b = float(row["b"])
        h = float(row["h"])
        y_bot, z_left = positions[name]
        parts.append(RectanglePart(name=name, b=b, h=h,
                                   y_bot=y_bot, z_left=z_left))
    return parts


# ---------------------------------------------------------------------------
# Auto-assign snap IDs
# ---------------------------------------------------------------------------

def _auto_assign_snap_ids(snaps_df: pd.DataFrame) -> pd.DataFrame:
    """Fill NaN snap IDs with next available integer."""
    if snaps_df is None or len(snaps_df) == 0:
        return snaps_df
    df = snaps_df.copy()
    max_id = int(df["id"].max()) if df["id"].notna().any() else -1
    for idx in df.index:
        if pd.isna(df.at[idx, "id"]):
            max_id += 1
            df.at[idx, "id"] = float(max_id)
    return df


# ---------------------------------------------------------------------------
# Template I/O
# ---------------------------------------------------------------------------

def _load_template_list() -> list[dict]:
    """Scan templates/ for .section.json files and return [{name, path}, ...]."""
    if not TEMPLATES_DIR.is_dir():
        return []
    templates = []
    for fp in sorted(TEMPLATES_DIR.glob("*.section.json")):
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            name = raw.get("metadata", {}).get("name", fp.stem.replace("_", " "))
        except Exception:
            name = fp.stem.replace("_", " ")
        templates.append({"name": name, "path": fp})
    return templates


def _load_template_file(path: pathlib.Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load a .section.json file and return (rects_df, snaps_df, joints_df)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    parts_data = raw.get("parts", [])
    parts = [
        RectanglePart(
            name=p["name"], b=p["b"], h=p["h"],
            y_bot=p["y_bot"], z_left=p["z_left"],
        )
        for p in parts_data
    ]
    return _parts_to_tables(parts)


def _section_to_json(rects_df: pd.DataFrame,
                     snaps_df: pd.DataFrame,
                     joints_df: pd.DataFrame,
                     name: str = "",
                     ) -> str:
    """Serialize current section state to JSON string for saving."""
    # Resolve positions to get absolute part coordinates
    resolved = _resolve_positions(rects_df, snaps_df, joints_df)
    if isinstance(resolved, str):
        # Resolution failed — fall back to storing without coordinates
        parts_data = []
        for _, row in rects_df.iterrows():
            parts_data.append({
                "name": str(row["Name"]) if pd.notna(row["Name"]) else "",
                "b": float(row["b"]),
                "h": float(row["h"]),
                "y_bot": 0.0,
                "z_left": 0.0,
            })
    else:
        parts_data = []
        for _, row in rects_df.iterrows():
            rname = str(row["Name"]) if pd.notna(row["Name"]) else ""
            y_bot, z_left = resolved.get(rname, (0.0, 0.0))
            parts_data.append({
                "name": rname,
                "b": float(row["b"]),
                "h": float(row["h"]),
                "y_bot": y_bot,
                "z_left": z_left,
            })

    data = {
        "metadata": {
            "name": name,
            "format_version": 1,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        "parts": parts_data,
    }
    return json.dumps(data, indent=2)


def _load_section_tables(name: str = "") -> None:
    """Helper to load data into session state and rerun."""
    _clear_editor_keys()


def _clear_editor_keys() -> None:
    """Remove data_editor keys from session state to force re-init on rerun."""
    for key in ("rects_editor", "snaps_editor", "joints_editor"):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "rects_df" not in st.session_state:
    default_parts = PRESETS[0]["builder"]()
    r, s, j = _parts_to_tables(default_parts)
    st.session_state.rects_df = r
    st.session_state.snaps_df = s
    st.session_state.joints_df = j
if "section_name" not in st.session_state:
    st.session_state.section_name = ""

if "axis_convention" not in st.session_state:
    st.session_state.axis_convention = "yz_eurocode"
if "show_centroid" not in st.session_state:
    st.session_state.show_centroid = True
if "show_centroidal_axes" not in st.session_state:
    st.session_state.show_centroidal_axes = True
if "show_principal_axes" not in st.session_state:
    st.session_state.show_principal_axes = True


# ---------------------------------------------------------------------------
# Sidebar: Presets + Settings
# ---------------------------------------------------------------------------

with st.sidebar:
    # --- File menu (popover, matching fem_app pattern) ---
    with st.popover("File", use_container_width=True):
        # New Section
        if st.button("New Section", use_container_width=True):
            default_parts = PRESETS[-1]["builder"]()  # "Custom" preset
            r, s, j = _parts_to_tables(default_parts)
            st.session_state.rects_df = r
            st.session_state.snaps_df = s
            st.session_state.joints_df = j
            st.session_state.section_name = ""
            _clear_editor_keys()
            st.rerun()

        # Load Section (file uploader)
        uploaded = st.file_uploader(
            "Load Section",
            type=["json", "section.json"],
            key="section_uploader",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            try:
                raw = json.loads(uploaded.read().decode("utf-8"))
                parts_data = raw.get("parts", [])
                parts = [
                    RectanglePart(
                        name=p["name"], b=p["b"], h=p["h"],
                        y_bot=p["y_bot"], z_left=p["z_left"],
                    )
                    for p in parts_data
                ]
                r, s, j = _parts_to_tables(parts)
                st.session_state.rects_df = r
                st.session_state.snaps_df = s
                st.session_state.joints_df = j
                name = raw.get("metadata", {}).get("name", "")
                st.session_state.section_name = name
                _clear_editor_keys()
                st.success(f"Loaded: {name}")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load: {e}")

        # Save as Template (geometry → templates/)
        sec_name = st.session_state.get("section_name", "")
        if st.button("Save as Template", use_container_width=True,
                      help="Save section geometry to templates for reuse"):
            if not sec_name.strip():
                st.error("Enter a section name first.")
            else:
                try:
                    json_str = _section_to_json(
                        st.session_state.rects_df,
                        st.session_state.snaps_df,
                        st.session_state.joints_df,
                        name=sec_name,
                    )
                    tpl_dir = pathlib.Path(__file__).resolve().parent / "templates"
                    tpl_dir.mkdir(exist_ok=True)
                    fname = f"{sec_name.replace(' ', '_').lower()}.section.json"
                    (tpl_dir / fname).write_text(json_str, encoding="utf-8")
                    st.success(f"Saved template: {fname}")
                except Exception as e:
                    st.error(f"Save failed: {e}")

        # Save Results (calculated properties → exchange/sections/)
        if st.button("Save Results", use_container_width=True,
                      help="Export calculated properties for use in other modules"):
            cached_result = st.session_state.get("_last_result")
            if cached_result is None:
                st.error("No calculation results yet. Define a valid section first.")
            elif not sec_name.strip():
                st.error("Enter a section name first.")
            else:
                try:
                    exchange_dir = pathlib.Path(__file__).resolve().parent.parent / "exchange" / "sections"
                    exchange_dir.mkdir(parents=True, exist_ok=True)
                    exchange_data = {
                        "format_version": 1,
                        "source": "section_app",
                        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                        "name": sec_name,
                        "properties": {
                            "A_mm2": round(cached_result.A_total, 2),
                            "Iy_mm4": round(cached_result.Iy, 2),
                            "Iz_mm4": round(cached_result.Iz, 2),
                            "iy_mm": round(cached_result.iy, 2),
                            "iz_mm": round(cached_result.iz, 2),
                            "Wy_mm3": round(cached_result.Wy, 2),
                            "Wz_mm3": round(cached_result.Wz, 2),
                        },
                    }
                    fname = f"{sec_name.replace(' ', '_')}.section_result.json"
                    (exchange_dir / fname).write_text(
                        json.dumps(exchange_data, indent=2), encoding="utf-8",
                    )
                    st.success(f"Saved to exchange/sections/{fname}")
                except Exception as e:
                    st.error(f"Save failed: {e}")

        # Templates (built-in presets)
        with st.expander("Templates"):
            templates = _load_template_list()
            if templates:
                for idx, tpl in enumerate(templates):
                    if st.button(tpl["name"], key=f"tpl_{idx}",
                                 use_container_width=True):
                        r, s, j = _load_template_file(tpl["path"])
                        st.session_state.rects_df = r
                        st.session_state.snaps_df = s
                        st.session_state.joints_df = j
                        st.session_state.section_name = tpl["name"]
                        _clear_editor_keys()
                        st.rerun()
            else:
                st.caption("No templates found.")

    # Section name
    st.session_state.section_name = st.text_input(
        "Section name",
        value=st.session_state.get("section_name", ""),
        label_visibility="collapsed",
        placeholder="Section name",
    )

    st.divider()

    st.header("Settings")
    convention = st.radio(
        "Axis convention",
        options=list(AXIS_CONVENTIONS.keys()),
        format_func=lambda x: AXIS_CONVENTIONS[x]["label"],
        index=list(AXIS_CONVENTIONS.keys()).index(st.session_state.axis_convention),
        key="axis_radio",
    )
    st.session_state.axis_convention = convention

    st.divider()

    st.header("Display")
    st.session_state.show_centroid = st.checkbox(
        "Centroid", value=st.session_state.show_centroid,
        key="chk_centroid",
    )
    st.session_state.show_centroidal_axes = st.checkbox(
        "Centroidal axes", value=st.session_state.show_centroidal_axes,
        key="chk_centroidal",
    )
    st.session_state.show_principal_axes = st.checkbox(
        "Principal axes", value=st.session_state.show_principal_axes,
        key="chk_principal",
    )


# ---------------------------------------------------------------------------
# Resolve positions and calculate (pre-edit — for cross-section view)
# ---------------------------------------------------------------------------

conv = _get_conv()

result: SectionResult | None = None
error_msg: str | None = None
parts_list: list[RectanglePart] = []

try:
    # Auto-assign snap IDs
    st.session_state.snaps_df = _auto_assign_snap_ids(st.session_state.snaps_df)

    resolved = _resolve_positions(
        st.session_state.rects_df,
        st.session_state.snaps_df,
        st.session_state.joints_df,
    )
    if isinstance(resolved, str):
        error_msg = resolved
    else:
        parts_list = _tables_to_parts(st.session_state.rects_df, resolved)
        if parts_list:
            validation_error = validate_parts(parts_list)
            if validation_error:
                error_msg = validation_error
            else:
                result = calculate(parts_list)
                # Cache result for sidebar buttons (available on next rerun)
                st.session_state._last_result = result
        else:
            error_msg = "No rectangles could be positioned."
except Exception as e:
    error_msg = f"Calculation error: {e}"


# ---------------------------------------------------------------------------
# Cross-section view (ABOVE components tables)
# ---------------------------------------------------------------------------

if error_msg:
    st.error(error_msg)

if result is not None and error_msg is None:
    st.subheader("Cross-section view")

    fig = go.Figure()

    # Collect all edge coordinates for grid annotations
    all_vert_edges = set()   # internal y-coordinates (vertical edges)
    all_horiz_edges = set()  # internal z-coordinates (horizontal edges)

    # Corner points for separate hover trace
    corner_plot_x: list[float] = []
    corner_plot_y: list[float] = []
    corner_hover: list[str] = []

    for i, (pr, part) in enumerate(zip(result.parts, parts_list)):
        color_idx = i % len(PART_COLORS)

        y0 = part.y_bot
        y1 = y0 + part.h
        z0 = part.z_left
        z1 = z0 + part.b

        all_vert_edges.update([y0, y1])
        all_horiz_edges.update([z0, z1])

        # Plot: x-axis = horizontal (z internal), y-axis = vertical (y internal)
        plot_x = [z0, z1, z1, z0, z0]
        plot_y = [y0, y0, y1, y1, y0]

        # Rectangle fill — hover on fill area shows name + dimensions
        fig.add_trace(go.Scatter(
            x=plot_x, y=plot_y,
            fill="toself",
            fillcolor=PART_COLORS[color_idx],
            line=dict(color=PART_BORDER_COLORS[color_idx], width=2),
            name=pr.name,
            hoveron="fills",
            hovertemplate=(
                f"<b>{pr.name}</b><br>"
                f"{conv['horiz_label']} = {part.b:.1f} mm, "
                f"{conv['vert_label']} = {part.h:.1f} mm<br>"
                f"A = {pr.A:.0f} mm\u00b2"
                "<extra></extra>"
            ),
        ))

        # Collect corner coordinates for hover
        corners = [(z0, y0), (z1, y0), (z1, y1), (z0, y1)]
        for cz, cy in corners:
            corner_plot_x.append(cz)
            corner_plot_y.append(cy)
            corner_hover.append(
                f"<b>({conv['horiz_label']}={cz:.1f}, "
                f"{conv['vert_label']}={cy:.1f})</b>"
                f"<extra></extra>"
            )

    # Corner point markers — hover shows coordinates
    fig.add_trace(go.Scatter(
        x=corner_plot_x, y=corner_plot_y,
        mode="markers",
        marker=dict(size=CORNER_MARKER_SIZE, color=CORNER_MARKER_COLOR),
        name="Corners",
        showlegend=False,
        hovertemplate=corner_hover,
    ))

    # Centroid marker
    if st.session_state.show_centroid:
        fig.add_trace(go.Scatter(
            x=[result.zc], y=[result.yc],
            mode="markers+text",
            marker=dict(symbol="cross-thin", size=15, color="red",
                        line=dict(width=2, color="red")),
            text=["C"],
            textposition="top right",
            textfont=dict(color="red", size=12),
            name="Centroid",
            hovertemplate=(
                f"<b>Centroid</b><br>"
                f"{conv['horiz_label']}<sub>C</sub> = {result.zc:.1f} mm<br>"
                f"{conv['vert_label']}<sub>C</sub> = {result.yc:.1f} mm<br>"
                "<extra></extra>"
            ),
        ))

    # Grid lines at every section edge
    grid_line_style = dict(color="rgba(150,150,150,0.4)", width=1, dash="dot")

    all_z = sorted(all_horiz_edges)
    all_y = sorted(all_vert_edges)
    z_min, z_max = min(all_z), max(all_z)
    y_min, y_max = min(all_y), max(all_y)
    z_span = z_max - z_min if z_max > z_min else 1
    y_span = y_max - y_min if y_max > y_min else 1
    pad = max(z_span, y_span) * 0.15

    # --- Grid lines (short) + labels on initial axes ---
    GRID_FONT = dict(size=14, color="black")
    LEADER_COLOR = "black"
    # Gridlines extend 30% of pad beyond section edges (not to view edge)
    grid_ext = pad * 0.3
    # Label gap threshold (in data units) for collision detection
    MIN_LABEL_GAP_Z = z_span * 0.05 if z_span > 0 else 5
    MIN_LABEL_GAP_Y = y_span * 0.05 if y_span > 0 else 5
    # Estimate data-units per pixel from chart dimensions
    plot_data_span = max(y_span, z_span) + 2 * pad * 1.1
    plot_px = 610  # approximate plot pixel height (chart_height - margins)
    du_per_px = plot_data_span / plot_px if plot_px > 0 else 1
    # Text metrics in data units (14px font)
    text_h = 14 * du_per_px          # height of one text line
    text_w = 10 * du_per_px * 3      # approximate width of 3-digit number
    # Gap between gridline end and nearest label edge (small — just enough to not touch)
    label_gap = text_h * 0.15
    # Tier spacing: must be >= text_h so tiers don't overlap
    tier_step = text_h * 1.2

    def _assign_label_tiers(sorted_vals, min_gap):
        """Assign tier 0, 1, 2 for labels. Higher tiers use leaders."""
        tiers = [0] * len(sorted_vals)
        last_on_tier = {0: -1e9, 1: -1e9, 2: -1e9}
        for i, v in enumerate(sorted_vals):
            placed = False
            for t in [0, 1, 2]:
                if (v - last_on_tier[t]) >= min_gap:
                    tiers[i] = t
                    last_on_tier[t] = v
                    placed = True
                    break
            if not placed:
                best = max([0, 1, 2], key=lambda t: v - last_on_tier[t])
                tiers[i] = best
                last_on_tier[best] = v
        return tiers

    def _get_leader_flags(tiers):
        """If any label in a cluster has tier > 0, ALL adjacent labels get leaders."""
        flags = [t > 0 for t in tiers]
        for i in range(len(tiers)):
            if tiers[i] == 0:
                if (i > 0 and tiers[i - 1] > 0) or \
                   (i < len(tiers) - 1 and tiers[i + 1] > 0):
                    flags[i] = True
        return flags

    # --- Horizontal gridlines (y-value edges) — labels on left ---
    sorted_y = sorted(all_vert_edges)
    y_tiers = _assign_label_tiers(sorted_y, MIN_LABEL_GAP_Y)
    y_leaders = _get_leader_flags(y_tiers)
    y_grid_end = z_min - grid_ext
    for idx, y_val in enumerate(sorted_y):
        fig.add_shape(type="line",
                      x0=y_grid_end, x1=z_max + grid_ext,
                      y0=y_val, y1=y_val, line=grid_line_style)
        tier = y_tiers[idx]
        use_leader = y_leaders[idx]
        x_label = y_grid_end - label_gap - tier * tier_step
        # Vertical spread: cluster labels spread up/down to avoid leader crossings
        if use_leader:
            y_spread = {0: text_h * 0.5, 1: 0, 2: -text_h * 0.5}.get(tier, 0)
        else:
            y_spread = 0
        y_text = y_val + y_spread
        label_str = f"<b>{y_val:.0f}</b>"
        if not use_leader:
            fig.add_annotation(
                x=x_label, y=y_text, text=label_str,
                showarrow=False, font=GRID_FONT, xanchor="right",
            )
        else:
            fig.add_annotation(
                x=y_grid_end, y=y_val, text=label_str,
                ax=x_label, ay=y_text,
                axref="x", ayref="y",
                showarrow=True, arrowhead=0, arrowwidth=0.8,
                arrowcolor=LEADER_COLOR,
                font=GRID_FONT, xanchor="right",
            )

    # --- Vertical gridlines (z-value edges) — labels below ---
    sorted_z = sorted(all_horiz_edges)
    z_tiers = _assign_label_tiers(sorted_z, MIN_LABEL_GAP_Z)
    z_leaders = _get_leader_flags(z_tiers)
    z_grid_end = y_min - grid_ext
    for idx, z_val in enumerate(sorted_z):
        fig.add_shape(type="line",
                      x0=z_val, x1=z_val,
                      y0=z_grid_end, y1=y_max + grid_ext,
                      line=grid_line_style)
        tier = z_tiers[idx]
        use_leader = z_leaders[idx]
        y_label = z_grid_end - label_gap - tier * tier_step
        # Horizontal spread: cluster labels fan out left/right to avoid crossings
        if use_leader:
            x_spread = {0: -text_w * 0.8, 1: 0, 2: text_w * 0.8}.get(tier, 0)
            x_anc = {0: "right", 1: "center", 2: "left"}.get(tier, "center")
        else:
            x_spread = 0
            x_anc = "center"
        x_label = z_val + x_spread
        label_str = f"<b>{z_val:.0f}</b>"
        if not use_leader:
            fig.add_annotation(
                x=x_label, y=y_label, text=label_str,
                showarrow=False, font=GRID_FONT, yanchor="top",
            )
        else:
            fig.add_annotation(
                x=z_val, y=z_grid_end, text=label_str,
                ax=x_label, ay=y_label,
                axref="x", ayref="y",
                showarrow=True, arrowhead=0, arrowwidth=0.8,
                arrowcolor=LEADER_COLOR,
                font=GRID_FONT, yanchor="top", xanchor=x_anc,
            )

    # --- Initial axes at origin (0,0) — Yi, Zi ---
    import math as _math
    v_ax = conv['vert_label']   # z or y
    h_ax = conv['horiz_label']  # y or x
    init_axis_style = dict(color="gray", width=1)
    # Horizontal initial axis (Yi / Xi) at vertical=0
    fig.add_shape(type="line",
                  x0=z_min - pad, x1=z_max + pad, y0=0, y1=0,
                  line=init_axis_style)
    fig.add_annotation(
        x=z_max + pad * 0.85, y=0,
        text=f"{h_ax}<sub>i</sub>", showarrow=False,
        font=dict(size=14, color="gray"), yanchor="bottom",
    )
    # Vertical initial axis (Zi / Yi) at horizontal=0
    fig.add_shape(type="line",
                  x0=0, x1=0, y0=y_min - pad, y1=y_max + pad,
                  line=init_axis_style)
    fig.add_annotation(
        x=0, y=y_max + pad * 0.85,
        text=f"{v_ax}<sub>i</sub>", showarrow=False,
        font=dict(size=14, color="gray"), xanchor="left",
    )

    # --- Centroidal axes through centroid (Y, Z) ---
    axis_ext = max(z_span, y_span) * 0.6

    if st.session_state.show_centroidal_axes:
        fig.add_trace(go.Scatter(
            x=[z_min - pad * 0.8, z_max + pad * 0.8],
            y=[result.yc, result.yc],
            mode="lines",
            line=dict(color="green", width=1.5, dash="dash"),
            name=f"{h_ax}",
            showlegend=True,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[result.zc, result.zc],
            y=[y_min - pad * 0.8, y_max + pad * 0.8],
            mode="lines",
            line=dict(color="blue", width=1.5, dash="dash"),
            name=f"{v_ax}",
            showlegend=True,
            hoverinfo="skip",
        ))

    if st.session_state.show_principal_axes and not result.axes_coincide:
        cos_a = _math.cos(result.alpha_rad)
        sin_a = _math.sin(result.alpha_rad)
        fig.add_trace(go.Scatter(
            x=[result.zc - axis_ext * sin_a, result.zc + axis_ext * sin_a],
            y=[result.yc - axis_ext * cos_a, result.yc + axis_ext * cos_a],
            mode="lines",
            line=dict(color="darkorange", width=1.5, dash="dashdot"),
            name=f"1 (I_max, \u03b1={result.alpha_deg:.1f}\u00b0)",
            showlegend=True,
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=[result.zc - axis_ext * cos_a, result.zc + axis_ext * cos_a],
            y=[result.yc + axis_ext * sin_a, result.yc - axis_ext * sin_a],
            mode="lines",
            line=dict(color="magenta", width=1.5, dash="dashdot"),
            name="2 (I_min)",
            showlegend=True,
            hoverinfo="skip",
        ))
        fig.add_annotation(
            x=result.zc + axis_ext * 0.35 * sin_a,
            y=result.yc + axis_ext * 0.35 * cos_a,
            text=f"\u03b1={result.alpha_deg:.1f}\u00b0",
            showarrow=False,
            font=dict(size=12, color="darkorange"),
        )

    # Calculate chart dimensions to fit section with 1:1 aspect + legend space
    plot_y_range = (y_max + pad * 1.1) - (y_min - pad * 1.1)
    plot_z_range = (z_max + pad * 1.1) - (z_min - pad * 1.1)
    chart_height = 650
    plot_height = chart_height - 40  # subtract margins
    chart_width = int(plot_height * (plot_z_range / plot_y_range)) + 400  # +400 for legend spacing
    chart_width = max(chart_width, 500)  # minimum width
    chart_width = min(chart_width, 1200)  # maximum width

    fig.update_layout(
        xaxis=dict(scaleanchor="y", scaleratio=1,
                   showgrid=False, zeroline=False,
                   showticklabels=False, title="",
                   range=[z_min - pad * 1.3, z_max + pad * 1.1]),
        yaxis=dict(showgrid=False, zeroline=False,
                   showticklabels=False, title="",
                   range=[y_min - pad * 1.3, y_max + pad * 1.1]),
        showlegend=True,
        legend=dict(orientation="v", yanchor="top", y=0.99,
                    xanchor="right", x=0.99,
                    bgcolor="rgba(255,255,255,0.8)",
                    font=dict(size=13)),
        margin=dict(l=20, r=20, t=20, b=20),
        width=chart_width,
        height=chart_height,
        plot_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=False, config={
        "scrollZoom": False, "displaylogo": False,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    })

st.divider()

# ---------------------------------------------------------------------------
# Section components — THREE TABLES (collapsible)
# ---------------------------------------------------------------------------

st.subheader("Section components")

# --- Table (a): Rectangles — name + dimensions only ---
with st.expander("Rectangles", expanded=False):
    st.caption(f"Define rectangle dimensions. "
               f"Axes: {conv['horiz_label']} = horizontal, {conv['vert_label']} = vertical. "
               f"Positions are determined by snap points and joints below.")

    edited_rects = st.data_editor(
        st.session_state.rects_df,
        num_rows="dynamic",
        key="rects_editor",
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "b": st.column_config.NumberColumn(
                f"\u0394{conv['horiz_label']} (mm)",
                min_value=0.1, step=1.0, format="%.1f", width="small",
                help=f"Width along {conv['horiz_label']}-axis",
            ),
            "h": st.column_config.NumberColumn(
                f"\u0394{conv['vert_label']} (mm)",
                min_value=0.1, step=1.0, format="%.1f", width="small",
                help=f"Height along {conv['vert_label']}-axis",
            ),
        },
    )
    st.session_state.rects_df = edited_rects

# Fill NaN names
for i in st.session_state.rects_df.index:
    name = st.session_state.rects_df.at[i, "Name"]
    if pd.isna(name) or str(name).strip() == "":
        st.session_state.rects_df.at[i, "Name"] = f"Part {i + 1}"

# Get current rectangle names for component selectbox
rect_names = list(st.session_state.rects_df["Name"].dropna().astype(str))

# Auto-assign snap IDs before editing
st.session_state.snaps_df = _auto_assign_snap_ids(st.session_state.snaps_df)

# --- Table (b): Snap points ---
with st.expander("Snap points", expanded=False):
    st.caption(
        "Define positioning reference points. "
        "**absolute**: fixed coordinates. "
        "**edge**: point on a rectangle edge (0=start corner, 0.5=mid, 1=end corner). "
        "Corners: 1=BL, 2=BR, 3=TR, 4=TL."
    )

    edited_snaps = st.data_editor(
        st.session_state.snaps_df,
        num_rows="dynamic",
        key="snaps_editor",
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d",
                                                help="Auto-assigned snap point ID"),
            "type": st.column_config.SelectboxColumn("Type", options=SNAP_TYPE_OPTIONS,
                                                      width="small"),
            "horiz_coord": st.column_config.NumberColumn(
                f"{conv['horiz_label']} coord",
                step=1.0, format="%.1f",
                help="For absolute type: horizontal coordinate (mm)",
            ),
            "vert_coord": st.column_config.NumberColumn(
                f"{conv['vert_label']} coord",
                step=1.0, format="%.1f",
                help="For absolute type: vertical coordinate (mm)",
            ),
            "component": st.column_config.SelectboxColumn(
                "Component", options=rect_names, width="medium",
                help="For edge type: which rectangle",
            ),
            "edge": st.column_config.SelectboxColumn(
                "Edge", options=EDGE_OPTIONS, width="small",
                help="For edge type: bottom (1→2), right (2→3), top (3→4), left (4→1)",
            ),
            "position": st.column_config.NumberColumn(
                "Pos (0-1)", min_value=0.0, max_value=1.0,
                step=0.1, format="%.2f",
                help="0.0 = start corner, 0.5 = midpoint, 1.0 = end corner",
            ),
            "offset": st.column_config.NumberColumn(
                "Offset (mm)", step=1.0, format="%.1f",
                help="Perpendicular offset outward from edge. "
                     "If offset_ref is set, this is ADDED to the referenced dimension.",
            ),
            "offset_ref": st.column_config.SelectboxColumn(
                "Offset ref", options=rect_names, width="medium",
                help="Optional: use a rectangle's dimension as base offset "
                     "(for parametric sections)",
            ),
            "offset_dim": st.column_config.SelectboxColumn(
                "Ref dim", options=["width", "height"], width="small",
                help=f"Which dimension: width = \u0394{conv['horiz_label']}, "
                     f"height = \u0394{conv['vert_label']}",
            ),
        },
    )
    st.session_state.snaps_df = edited_snaps

# --- Table (c): Joints ---
with st.expander("Joints", expanded=False):
    st.caption("Connect pairs of snap points. Joined snaps share the same location, "
               "which determines rectangle positions.")

    edited_joints = st.data_editor(
        st.session_state.joints_df,
        num_rows="dynamic",
        key="joints_editor",
        hide_index=True,
        column_config={
            "snap_1": st.column_config.NumberColumn("Snap 1", format="%d",
                                                     help="ID of first snap point"),
            "snap_2": st.column_config.NumberColumn("Snap 2", format="%d",
                                                     help="ID of second snap point"),
        },
    )
    st.session_state.joints_df = edited_joints

# --- Apply changes button ---
if st.button("Apply changes", type="primary", use_container_width=True):
    st.rerun()


# ---------------------------------------------------------------------------
# Re-resolve and calculate (post-edit)
# ---------------------------------------------------------------------------

result = None
error_msg = None
parts_list = []

try:
    st.session_state.snaps_df = _auto_assign_snap_ids(st.session_state.snaps_df)

    resolved = _resolve_positions(
        st.session_state.rects_df,
        st.session_state.snaps_df,
        st.session_state.joints_df,
    )
    if isinstance(resolved, str):
        error_msg = resolved
    else:
        parts_list = _tables_to_parts(st.session_state.rects_df, resolved)
        if parts_list:
            validation_error = validate_parts(parts_list)
            if validation_error:
                error_msg = validation_error
            else:
                result = calculate(parts_list)
                st.session_state._last_result = result
        else:
            error_msg = "No rectangles could be positioned."
except Exception as e:
    error_msg = f"Calculation error: {e}"

if error_msg and not st.session_state.get("_error_shown"):
    st.error(error_msg)

# ---------------------------------------------------------------------------
# Results summary (condensed, below components)
# ---------------------------------------------------------------------------

if result is not None and error_msg is None:
    st.divider()
    st.subheader("Section properties")

    v_ax = conv['vert_label']
    h_ax = conv['horiz_label']

    I_vert_label = conv['I_vert']
    I_horiz_label = conv['I_horiz']
    W_vert_label = conv['W_vert']
    W_horiz_label = conv['W_horiz']
    i_vert_label = conv['i_vert']
    i_horiz_label = conv['i_horiz']

    # I_yz label: standard notation is I_yz (Eurocode) or I_xy (basic)
    Iyz_sub = f"{h_ax}{v_ax}"  # yz for Eurocode, xy for basic

    lines = []
    lines.append(
        f"<b>A</b> = {result.A_total:,.0f} mm\u00b2"
        f" = {result.A_total * MM2_TO_CM2:,.2f} cm\u00b2"
    )
    lines.append(
        f"<b>{_sub(I_vert_label)}</b> = {result.Iy:,.0f} mm\u2074"
        f" = {result.Iy / 1e6:,.2f} \u00d710\u2076 mm\u2074"
        f" = {result.Iy * MM4_TO_CM4:,.1f} cm\u2074"
    )
    lines.append(
        f"<b>{_sub(I_horiz_label)}</b> = {result.Iz:,.0f} mm\u2074"
        f" = {result.Iz / 1e6:,.2f} \u00d710\u2076 mm\u2074"
        f" = {result.Iz * MM4_TO_CM4:,.1f} cm\u2074"
    )
    lines.append(
        f"<b>I<sub>{Iyz_sub}</sub></b>"
        f" = {result.Iyz:,.0f} mm\u2074"
        f" = {result.Iyz * MM4_TO_CM4:,.1f} cm\u2074"
    )
    if result.axes_coincide:
        lines.append(
            f"<b>I<sub>max</sub></b> = {result.I_max:,.0f} mm\u2074"
            f" = {result.I_max * MM4_TO_CM4:,.1f} cm\u2074"
            f" &nbsp; <i>(principal axes coincide with centroidal axes)</i>"
        )
        lines.append(
            f"<b>I<sub>min</sub></b> = {result.I_min:,.0f} mm\u2074"
            f" = {result.I_min * MM4_TO_CM4:,.1f} cm\u2074"
        )
    else:
        lines.append(
            f"<b>I<sub>max</sub></b> = {result.I_max:,.0f} mm\u2074"
            f" = {result.I_max * MM4_TO_CM4:,.1f} cm\u2074"
        )
        lines.append(
            f"<b>I<sub>min</sub></b> = {result.I_min:,.0f} mm\u2074"
            f" = {result.I_min * MM4_TO_CM4:,.1f} cm\u2074"
            f" &nbsp; <b>\u03b1</b> = {result.alpha_deg:.1f}\u00b0"
        )
    lines.append(
        f"<b>{_sub(W_vert_label)}</b>"
        f" = {result.Wy:,.0f} mm\u00b3"
        f" = {result.Wy / 1e3:,.1f} \u00d710\u00b3 mm\u00b3"
        f" = {result.Wy * MM3_TO_CM3:,.1f} cm\u00b3"
    )
    lines.append(
        f"<b>{_sub(W_horiz_label)}</b>"
        f" = {result.Wz:,.0f} mm\u00b3"
        f" = {result.Wz / 1e3:,.1f} \u00d710\u00b3 mm\u00b3"
        f" = {result.Wz * MM3_TO_CM3:,.1f} cm\u00b3"
    )
    lines.append(
        f"<b>{_sub(i_vert_label)}</b>"
        f" = {result.iy:.1f} mm = {result.iy / 10:.2f} cm"
    )
    lines.append(
        f"<b>{_sub(i_horiz_label)}</b>"
        f" = {result.iz:.1f} mm = {result.iz / 10:.2f} cm"
    )

    st.markdown(
        '<div style="line-height:1.9; font-size:0.95em;">'
        + "<br>".join(lines)
        + '</div>',
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------------------------
    # Step-by-step calculation
    # ---------------------------------------------------------------------------

    st.divider()
    st.subheader("Step-by-step calculation")

    # --- Area ---
    st.markdown("**Area**")
    area_parts = " + ".join(f"{pr.b:.0f} \\cdot {pr.h:.0f}" for pr in result.parts)
    area_values = " + ".join(f"{pr.A:.0f}" for pr in result.parts)
    st.latex(
        r"A = \sum b_i \cdot h_i = " + area_parts
        + r" = " + area_values
        + r" = " + f"{result.A_total:.0f}"
        + r"\text{{ mm}}^2"
    )

    # --- Centroid (vertical axis) ---
    st.markdown(f"**Centroid {v_ax}<sub>C</sub>**", unsafe_allow_html=True)
    num_y = " + ".join(
        f"({pr.b:.0f} \\cdot {pr.h:.0f}) \\cdot {pr.yc:.1f}"
        for pr in result.parts
    )
    st.latex(
        v_ax + r"_C = \frac{\sum A_i \cdot "
        + v_ax + r"_{c,i}}{\sum A_i} = "
        r"\frac{" + num_y + r"}{" + f"{result.A_total:.0f}" + r"}"
        r" = " + f"{result.yc:.2f}" + r"\text{{ mm}}"
    )

    st.markdown(f"**Centroid {h_ax}<sub>C</sub>**", unsafe_allow_html=True)
    num_z = " + ".join(
        f"({pr.b:.0f} \\cdot {pr.h:.0f}) \\cdot {pr.zc:.1f}"
        for pr in result.parts
    )
    st.latex(
        h_ax + r"_C = \frac{\sum A_i \cdot "
        + h_ax + r"_{c,i}}{\sum A_i} = "
        r"\frac{" + num_z + r"}{" + f"{result.A_total:.0f}" + r"}"
        r" = " + f"{result.zc:.2f}" + r"\text{{ mm}}"
    )

    # --- Moment of inertia (about horizontal axis — strong for I-beams) ---
    st.markdown(
        f"**{_sub(I_vert_label)}** — Parallel axis theorem (Steiner)",
        unsafe_allow_html=True,
    )
    st.latex(
        r"I_" + v_ax + r" = \sum \left( I_{\text{local},i} + A_i \cdot d_i^2 \right)"
    )

    for pr in result.parts:
        st.latex(
            r"\text{" + pr.name.replace(" ", r"\ ") + r"}: \quad "
            r"I_" + v_ax + r" = \frac{"
            + f"{pr.b:.0f} \\cdot {pr.h:.0f}^3" + r"}{12} + "
            + f"({pr.b:.0f} \\cdot {pr.h:.0f})"
            + r" \cdot "
            + f"({pr.yc:.1f} - {result.yc:.2f})^2"
            + r" = " + f"{pr.Iy_local:,.0f}" + r" + " + f"{pr.Iy_steiner:,.0f}"
            + r" = " + f"{pr.Iy_total:,.0f}" + r"\text{{ mm}}^4"
        )

    Iy_sum = " + ".join(f"{pr.Iy_total:,.0f}" for pr in result.parts)
    st.latex(
        r"I_" + v_ax + r" = " + Iy_sum
        + r" = " + f"{result.Iy:,.0f}" + r"\text{{ mm}}^4"
        + r" = " + f"{result.Iy / 1e6:,.2f}" + r" \times 10^6 \text{{ mm}}^4"
        + r" = " + f"{result.Iy * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4"
    )

    # --- Moment of inertia (about vertical axis — weak for I-beams) ---
    st.markdown(
        f"**{_sub(I_horiz_label)}** — Parallel axis theorem (Steiner)",
        unsafe_allow_html=True,
    )

    for pr in result.parts:
        st.latex(
            r"\text{" + pr.name.replace(" ", r"\ ") + r"}: \quad "
            r"I_" + h_ax + r" = \frac{"
            + f"{pr.h:.0f} \\cdot {pr.b:.0f}^3" + r"}{12} + "
            + f"({pr.b:.0f} \\cdot {pr.h:.0f})"
            + r" \cdot "
            + f"({pr.zc:.1f} - {result.zc:.2f})^2"
            + r" = " + f"{pr.Iz_local:,.0f}" + r" + " + f"{pr.Iz_steiner:,.0f}"
            + r" = " + f"{pr.Iz_total:,.0f}" + r"\text{{ mm}}^4"
        )

    Iz_sum = " + ".join(f"{pr.Iz_total:,.0f}" for pr in result.parts)
    st.latex(
        r"I_" + h_ax + r" = " + Iz_sum
        + r" = " + f"{result.Iz:,.0f}" + r"\text{{ mm}}^4"
        + r" = " + f"{result.Iz / 1e6:,.2f}" + r" \times 10^6 \text{{ mm}}^4"
        + r" = " + f"{result.Iz * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4"
    )

    # --- Product of inertia (centrifugal moment) ---
    st.markdown(
        f"**Product of inertia I<sub>{Iyz_sub}</sub>** — Parallel axis theorem (Steiner)",
        unsafe_allow_html=True,
    )
    st.latex(
        r"I_{" + Iyz_sub + r"} = \sum A_i \cdot d_{" + v_ax
        + r",i} \cdot d_{" + h_ax + r",i}"
    )

    for pr in result.parts:
        st.latex(
            r"\text{" + pr.name.replace(" ", r"\ ") + r"}: \quad "
            + f"({pr.b:.0f} \\cdot {pr.h:.0f})"
            + r" \cdot "
            + f"({pr.yc:.1f} - {result.yc:.2f})"
            + r" \cdot "
            + f"({pr.zc:.1f} - {result.zc:.2f})"
            + r" = " + f"{pr.Iyz_steiner:,.0f}" + r"\text{{ mm}}^4"
        )

    Iyz_sum = " + ".join(
        f"({pr.Iyz_steiner:,.0f})" if pr.Iyz_steiner < 0 else f"{pr.Iyz_steiner:,.0f}"
        for pr in result.parts
    )
    st.latex(
        r"I_{" + Iyz_sub + r"} = " + Iyz_sum
        + r" = " + f"{result.Iyz:,.0f}" + r"\text{{ mm}}^4"
        + r" = " + f"{result.Iyz * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4"
    )

    # --- Principal moments of inertia ---
    st.markdown("**Principal moments of inertia**")
    st.latex(
        r"I_{\max,\min} = \frac{I_" + v_ax + r" + I_" + h_ax
        + r"}{2} \pm \sqrt{\left(\frac{I_" + v_ax + r" - I_" + h_ax
        + r"}{2}\right)^2 + I_{" + Iyz_sub + r"}^2}"
    )
    st.latex(
        r"I_{\max,\min} = \frac{" + f"{result.Iy:,.0f} + {result.Iz:,.0f}"
        + r"}{2} \pm \sqrt{\left(\frac{" + f"{result.Iy:,.0f} - {result.Iz:,.0f}"
        + r"}{2}\right)^2 + " + f"({result.Iyz:,.0f})^2" + r"}"
    )
    st.latex(
        r"I_{\max} = " + f"{result.I_max:,.0f}" + r"\text{{ mm}}^4"
        + r" = " + f"{result.I_max * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4"
    )
    st.latex(
        r"I_{\min} = " + f"{result.I_min:,.0f}" + r"\text{{ mm}}^4"
        + r" = " + f"{result.I_min * MM4_TO_CM4:,.1f}" + r"\text{{ cm}}^4"
    )

    # --- Principal axis angle ---
    st.markdown("**Principal axis rotation angle**")
    if result.axes_coincide:
        st.latex(
            r"I_{" + Iyz_sub + r"} \approx 0 \quad \Rightarrow \quad "
            r"\alpha = 0° \quad \text{(principal axes coincide with centroidal axes)}"
        )
    else:
        st.latex(
            r"\alpha = \frac{1}{2} \arctan\!\left(\frac{-2\,I_{" + Iyz_sub
            + r"}}{I_" + v_ax + r" - I_" + h_ax + r"}\right)"
            + r" = \frac{1}{2} \arctan\!\left(\frac{-2 \cdot "
            + f"({result.Iyz:,.0f})" + r"}{"
            + f"{result.Iy:,.0f} - {result.Iz:,.0f}" + r"}\right)"
            + r" = " + f"{result.alpha_deg:.1f}" + r"°"
        )

    # --- Section modulus (both axes) with W comparison ---
    st.markdown(
        f"**Section modulus — {_sub(W_vert_label)}**",
        unsafe_allow_html=True,
    )
    st.latex(
        r"W_{" + v_ax + r",\text{top}} = \frac{I_" + v_ax + r"}{" + v_ax
        + r"_{\text{top}}} = \frac{"
        + f"{result.Iy:,.0f}" + r"}{" + f"{result.y_top:.1f}" + r"}"
        + r" = " + f"{result.Wy_top:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wy_top * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3"
    )
    st.latex(
        r"W_{" + v_ax + r",\text{bot}} = \frac{I_" + v_ax + r"}{" + v_ax
        + r"_{\text{bot}}} = \frac{"
        + f"{result.Iy:,.0f}" + r"}{" + f"{result.y_bot:.1f}" + r"}"
        + r" = " + f"{result.Wy_bot:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wy_bot * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3"
    )
    # W_y comparison: select governing (minimum)
    Wy_top_val = f"{result.Wy_top:,.0f}"
    Wy_bot_val = f"{result.Wy_bot:,.0f}"
    if result.Wy_top <= result.Wy_bot:
        Wy_comparison = (
            r"W_" + v_ax + r" = \min(" + Wy_top_val + r",\;" + Wy_bot_val
            + r") = " + Wy_top_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{top governs}"
        )
    else:
        Wy_comparison = (
            r"W_" + v_ax + r" = \min(" + Wy_top_val + r",\;" + Wy_bot_val
            + r") = " + Wy_bot_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{bottom governs}"
        )
    st.latex(Wy_comparison)

    st.markdown(
        f"**Section modulus — {_sub(W_horiz_label)}**",
        unsafe_allow_html=True,
    )
    st.latex(
        r"W_{" + h_ax + r",\text{left}} = \frac{I_" + h_ax + r"}{" + h_ax
        + r"_{\text{left}}} = \frac{"
        + f"{result.Iz:,.0f}" + r"}{" + f"{result.z_left:.1f}" + r"}"
        + r" = " + f"{result.Wz_left:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wz_left * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3"
    )
    st.latex(
        r"W_{" + h_ax + r",\text{right}} = \frac{I_" + h_ax + r"}{" + h_ax
        + r"_{\text{right}}} = \frac{"
        + f"{result.Iz:,.0f}" + r"}{" + f"{result.z_right:.1f}" + r"}"
        + r" = " + f"{result.Wz_right:,.0f}" + r"\text{{ mm}}^3"
        + r" = " + f"{result.Wz_right * MM3_TO_CM3:,.1f}" + r"\text{{ cm}}^3"
    )
    # W_z comparison: select governing (minimum)
    Wz_left_val = f"{result.Wz_left:,.0f}"
    Wz_right_val = f"{result.Wz_right:,.0f}"
    if result.Wz_left <= result.Wz_right:
        Wz_comparison = (
            r"W_" + h_ax + r" = \min(" + Wz_left_val + r",\;" + Wz_right_val
            + r") = " + Wz_left_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{left governs}"
        )
    else:
        Wz_comparison = (
            r"W_" + h_ax + r" = \min(" + Wz_left_val + r",\;" + Wz_right_val
            + r") = " + Wz_right_val
            + r"\text{{ mm}}^3 \quad \leftarrow \text{right governs}"
        )
    st.latex(Wz_comparison)

    # --- Radius of gyration ---
    st.markdown("**Radius of gyration**")
    st.latex(
        r"i_" + v_ax + r" = \sqrt{\frac{I_" + v_ax + r"}{A}} = \sqrt{\frac{"
        + f"{result.Iy:,.0f}" + r"}{" + f"{result.A_total:.0f}" + r"}}"
        + r" = " + f"{result.iy:.1f}" + r"\text{{ mm}}"
        + r" = " + f"{result.iy / 10:.2f}" + r"\text{{ cm}}"
    )
    st.latex(
        r"i_" + h_ax + r" = \sqrt{\frac{I_" + h_ax + r"}{A}} = \sqrt{\frac{"
        + f"{result.Iz:,.0f}" + r"}{" + f"{result.A_total:.0f}" + r"}}"
        + r" = " + f"{result.iz:.1f}" + r"\text{{ mm}}"
        + r" = " + f"{result.iz / 10:.2f}" + r"\text{{ cm}}"
    )
