"""
app.py — Streamlit frontend for 2D FEM analysis.

RFEM-inspired layout:
  - Top menu bar (File, Templates, Model name)
  - Left column: model tree (sidebar)
  - Right column: unified canvas + bottom panel (editors/results)

This file does NOT import anastruct directly. All FEM interactions
go through solver.py.

Launch: streamlit run app.py --server.port 8501
"""

from __future__ import annotations

import json
import math
import os
import pathlib
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

import file_io
from library import get_section_families, load_materials_library, load_sections_library
from solver import (
    CrossSectionDef,
    HingeDef,
    LoadDef,
    MaterialDef,
    MemberDef,
    ModelDefinition,
    NodeDef,
    SupportDef,
    dict_to_model,
    get_diagram_data,
    model_to_dict,
    model_to_yaml,
    result_to_dict,
    solve,
    yaml_to_model,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "2D FEM Analysis"
APP_ICON = "\U0001f3d7\ufe0f"

SUPPORT_TYPES = [
    "pinned",            # Ux,Uy restrained
    "fixed",             # Ux,Uy,Rz restrained
    "roller_x",          # Uy restrained (free X)
    "roller_y",          # Ux restrained (free Y)
    "rotational",        # Rz restrained (free X,Y)
    "spring_linear_x",   # Ux elastic (kN/m)
    "spring_linear_y",   # Uy elastic (kN/m)
    "spring_rotational",  # Rz elastic (kNm/rad)
]
LOAD_TYPES = ["point_force", "UDL", "point_moment"]
DIRECTIONS = ["Fx", "Fy", "Mz"]

# Widget keys for all data editors (used for clearing on model reload)
EDITOR_KEYS = [
    "nodes_editor", "members_editor", "materials_editor",
    "sections_editor", "supports_editor", "loads_editor",
]

# Plotly diagram colors (theme-friendly)
COLOR_GEOMETRY = "rgba(40,40,40,1)"             # members — dark gray
COLOR_GEOMETRY_DIMMED = "rgba(40,40,40,0.7)"     # members when overlays active
COLOR_NODE = "rgba(40,40,40,1)"
COLOR_NODE_LABEL = "rgba(60,60,60,1)"
COLOR_MEMBER_LABEL = "rgba(80,80,80,1)"
COLOR_SUPPORT = "rgba(34,139,34,1)"
COLOR_SUPPORT_FILL = "rgba(34,139,34,0.15)"
COLOR_HINGE = "rgba(255,165,0,1)"
COLOR_DEFORMED = "rgba(31,119,180,1)"
COLOR_REACTION = "rgba(34,139,34,0.9)"
COLOR_MOMENT = "rgba(255,127,14,0.5)"
COLOR_MOMENT_LINE = "rgba(255,127,14,1)"
COLOR_SHEAR = "rgba(44,160,44,0.5)"
COLOR_SHEAR_LINE = "rgba(44,160,44,1)"
COLOR_AXIAL_TENSION = "rgba(31,119,180,0.5)"
COLOR_AXIAL_TENSION_LINE = "rgba(31,119,180,1)"
COLOR_AXIAL_COMPRESSION = "rgba(214,39,40,0.5)"
COLOR_AXIAL_COMPRESSION_LINE = "rgba(214,39,40,1)"

DEFAULT_DEFORM_SCALE = 50.0

CANVAS_HEIGHT = 800

# Templates directory (folder of .fem.yaml files)

# User-default settings file
SETTINGS_PATH = pathlib.Path(__file__).parent / "settings.json"

# All saveable display/visualization settings with their built-in defaults
DEFAULT_SETTINGS: dict[str, Any] = {
    "deform_scale": DEFAULT_DEFORM_SCALE,
    "diagram_scale_M": 1.0,
    "diagram_scale_V": 1.0,
    "diagram_scale_N": 1.0,
    "arrow_scale": 1.0,
    "hinge_size": 10,
    "canvas_dark_mode": False,
    "label_scale": 1.0,
    "label_offset_scale": 1.0,
    "line_thickness_scale": 1.0,
}


def load_default_settings() -> dict[str, Any]:
    """Load user-default settings from settings.json, falling back to built-in defaults."""
    defaults = dict(DEFAULT_SETTINGS)
    if SETTINGS_PATH.exists():
        try:
            user = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            defaults.update({k: user[k] for k in user if k in DEFAULT_SETTINGS})
        except Exception:
            pass
    return defaults


def save_default_settings() -> None:
    """Persist current session settings as user defaults in settings.json."""
    settings = {k: st.session_state.get(k, v) for k, v in DEFAULT_SETTINGS.items()}
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _load_template_model(path: pathlib.Path) -> ModelDefinition:
    """Load a template file (old or new envelope format) into a ModelDefinition."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sfem, data, _ = file_io.parse_envelope(raw)
    model = dict_to_model(data)
    model.name = sfem.get("name", "")
    model.description = sfem.get("description", "")
    return model


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------


def init_session_state():
    """Initialize session state with an empty model."""
    if "model" not in st.session_state:
        st.session_state.model = ModelDefinition()
    if "solve_result" not in st.session_state:
        st.session_state.solve_result = None
    if "diagram_data" not in st.session_state:
        st.session_state.diagram_data = None
    if "model_name" not in st.session_state:
        st.session_state.model_name = ""
    if "model_description" not in st.session_state:
        st.session_state.model_description = ""
    if "active_editor" not in st.session_state:
        st.session_state.active_editor = None
    if "show_results" not in st.session_state:
        st.session_state.show_results = False
    # Display toggles (always available)
    if "show_node_ids" not in st.session_state:
        st.session_state.show_node_ids = True
    if "show_member_ids" not in st.session_state:
        st.session_state.show_member_ids = True
    if "show_member_labels" not in st.session_state:
        st.session_state.show_member_labels = False
    if "show_reactions" not in st.session_state:
        st.session_state.show_reactions = False
    if "show_grid" not in st.session_state:
        st.session_state.show_grid = True
    if "show_loads" not in st.session_state:
        st.session_state.show_loads = True
    # Overlay toggles (post-solve)
    if "show_deformed" not in st.session_state:
        st.session_state.show_deformed = False
    if "show_moment" not in st.session_state:
        st.session_state.show_moment = False
    if "show_shear" not in st.session_state:
        st.session_state.show_shear = False
    if "show_axial" not in st.session_state:
        st.session_state.show_axial = False
    # Settings — load from user defaults (settings.json), falling back to built-in defaults
    _defaults = load_default_settings()
    for key, val in _defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _clear_editor_keys():
    """Clear all data-editor widget keys so they reinitialise from model."""
    for key in EDITOR_KEYS:
        if key in st.session_state:
            del st.session_state[key]


def model_from_state() -> ModelDefinition:
    """Build a ModelDefinition from current session state."""
    m = st.session_state.model
    m.name = st.session_state.model_name
    m.description = st.session_state.model_description
    return m


def load_model_to_state(model: ModelDefinition):
    """Load a ModelDefinition into session state."""
    st.session_state.model = model
    st.session_state.model_name = model.name
    st.session_state.model_description = model.description
    st.session_state.solve_result = None
    st.session_state.diagram_data = None
    st.session_state.show_results = False
    st.session_state.show_node_ids = True
    st.session_state.show_member_ids = True
    st.session_state.show_reactions = False
    st.session_state.show_grid = True
    st.session_state.show_loads = True
    st.session_state.show_deformed = False
    st.session_state.show_moment = False
    st.session_state.show_shear = False
    st.session_state.show_axial = False
    st.session_state.diagram_scale_M = 0.3
    st.session_state.diagram_scale_V = 0.3
    st.session_state.diagram_scale_N = 0.3
    st.session_state.active_editor = "nodes"
    _clear_editor_keys()


def has_model_data() -> bool:
    """Check if the current model has any data."""
    m = st.session_state.model
    return len(m.nodes) > 0 or len(m.members) > 0


# ---------------------------------------------------------------------------
# DataFrame <-> Model conversion helpers
# ---------------------------------------------------------------------------


def nodes_to_df(nodes: list[NodeDef]) -> pd.DataFrame:
    if not nodes:
        return pd.DataFrame(columns=["node_id", "x (m)", "y (m)"])
    return pd.DataFrame([
        {"node_id": n.id, "x (m)": n.x, "y (m)": n.y}
        for n in nodes
    ])


def df_to_nodes(df: pd.DataFrame) -> list[NodeDef]:
    nodes = []
    used_ids: set[int] = set()
    # First pass: collect explicitly assigned IDs
    for _, row in df.iterrows():
        try:
            nid = row.get("node_id")
            if not pd.isna(nid):
                used_ids.add(int(nid))
        except (ValueError, TypeError):
            pass
    next_id = max(used_ids, default=0) + 1
    for _, row in df.iterrows():
        try:
            x_val = row.get("x (m)")
            y_val = row.get("y (m)")
            if pd.isna(x_val) or pd.isna(y_val):
                continue  # skip rows without coordinates
            nid = row.get("node_id")
            if pd.isna(nid):
                # Auto-assign next available ID
                nid = next_id
                while nid in used_ids:
                    nid += 1
                next_id = nid + 1
                used_ids.add(nid)
            else:
                nid = int(nid)
            nodes.append(NodeDef(
                id=nid,
                x=float(x_val),
                y=float(y_val),
            ))
        except (ValueError, KeyError, TypeError):
            pass
    return nodes


def members_to_df(members: list[MemberDef],
                  hinges: list[HingeDef]) -> pd.DataFrame:
    """Convert members + hinges into a single DataFrame."""
    hinge_map = {h.member_id: h for h in hinges}
    if not members:
        return pd.DataFrame(columns=[
            "member_id", "label", "start_node", "end_node", "section_id",
            "hinge_start", "hinge_end",
        ])
    rows = []
    for m in members:
        h = hinge_map.get(m.id)
        rows.append({
            "member_id": m.id,
            "label": f"{m.start_node}-{m.end_node}",
            "start_node": m.start_node,
            "end_node": m.end_node,
            "section_id": m.section_id,
            "hinge_start": h.start_release if h else False,
            "hinge_end": h.end_release if h else False,
        })
    return pd.DataFrame(rows)


def df_to_members_and_hinges(
    df: pd.DataFrame,
) -> tuple[list[MemberDef], list[HingeDef]]:
    """Parse a members DataFrame back into MemberDef + HingeDef lists."""
    members: list[MemberDef] = []
    hinges: list[HingeDef] = []
    used_ids: set[int] = set()
    # First pass: collect explicitly assigned IDs
    for _, row in df.iterrows():
        try:
            mid = row.get("member_id")
            if not pd.isna(mid):
                used_ids.add(int(mid))
        except (ValueError, TypeError):
            pass
    next_id = max(used_ids, default=0) + 1
    for _, row in df.iterrows():
        try:
            sn = row.get("start_node")
            en = row.get("end_node")
            if pd.isna(sn) or pd.isna(en):
                continue  # skip rows without connectivity
            mid = row.get("member_id")
            if pd.isna(mid):
                # Auto-assign next available ID
                mid = next_id
                while mid in used_ids:
                    mid += 1
                next_id = mid + 1
                used_ids.add(mid)
            else:
                mid = int(mid)
            sid = row.get("section_id", 1)
            if pd.isna(sid):
                sid = 1
            members.append(MemberDef(
                id=mid,
                start_node=int(sn),
                end_node=int(en),
                section_id=int(sid),
            ))
            hs = bool(row.get("hinge_start", False))
            he = bool(row.get("hinge_end", False))
            if hs or he:
                hinges.append(HingeDef(
                    member_id=mid,
                    start_release=hs,
                    end_release=he,
                ))
        except (ValueError, KeyError, TypeError):
            pass
    return members, hinges


def materials_to_df(materials: list[MaterialDef]) -> pd.DataFrame:
    if not materials:
        return pd.DataFrame(columns=["material_id", "name", "E (GPa)"])
    return pd.DataFrame([
        {"material_id": m.id, "name": m.name, "E (GPa)": m.E_GPa}
        for m in materials
    ])


def df_to_materials(df: pd.DataFrame) -> list[MaterialDef]:
    materials = []
    used_ids: set[int] = set()
    for _, row in df.iterrows():
        try:
            mid = row.get("material_id")
            if not pd.isna(mid):
                used_ids.add(int(mid))
        except (ValueError, TypeError):
            pass
    next_id = max(used_ids, default=0) + 1
    for _, row in df.iterrows():
        try:
            e_val = row.get("E (GPa)")
            if pd.isna(e_val):
                continue
            mid = row.get("material_id")
            if pd.isna(mid):
                mid = next_id
                while mid in used_ids:
                    mid += 1
                next_id = mid + 1
                used_ids.add(mid)
            else:
                mid = int(mid)
            materials.append(MaterialDef(
                id=mid,
                name=str(row.get("name", "Custom")),
                E_GPa=float(e_val),
            ))
        except (ValueError, KeyError, TypeError):
            pass
    return materials


def sections_to_df(sections: list[CrossSectionDef]) -> pd.DataFrame:
    if not sections:
        return pd.DataFrame(columns=["section_id", "name", "A (cm\u00b2)", "Iz (cm\u2074)", "material_id"])
    return pd.DataFrame([
        {
            "section_id": s.id,
            "name": s.name,
            "A (cm\u00b2)": s.A_cm2,
            "Iz (cm\u2074)": s.Iz_cm4,
            "material_id": s.material_id,
        }
        for s in sections
    ])


def df_to_sections(df: pd.DataFrame) -> list[CrossSectionDef]:
    sections = []
    used_ids: set[int] = set()
    for _, row in df.iterrows():
        try:
            sid = row.get("section_id")
            if not pd.isna(sid):
                used_ids.add(int(sid))
        except (ValueError, TypeError):
            pass
    next_id = max(used_ids, default=0) + 1
    for _, row in df.iterrows():
        try:
            a_val = row.get("A (cm\u00b2)")
            iz_val = row.get("Iz (cm\u2074)")
            if pd.isna(a_val) or pd.isna(iz_val):
                continue
            sid = row.get("section_id")
            if pd.isna(sid):
                sid = next_id
                while sid in used_ids:
                    sid += 1
                next_id = sid + 1
                used_ids.add(sid)
            else:
                sid = int(sid)
            mat_id = row.get("material_id", 1)
            if pd.isna(mat_id):
                mat_id = 1
            sections.append(CrossSectionDef(
                id=sid,
                name=str(row.get("name", "Custom")),
                A_cm2=float(a_val),
                Iz_cm4=float(iz_val),
                material_id=int(mat_id),
            ))
        except (ValueError, KeyError, TypeError):
            pass
    return sections


def supports_to_df(supports: list[SupportDef]) -> pd.DataFrame:
    if not supports:
        return pd.DataFrame(columns=[
            "node_id", "support_type", "spring_stiffness (kN/m or kNm/rad)",
        ])
    return pd.DataFrame([
        {
            "node_id": s.node_id,
            "support_type": s.type,
            "spring_stiffness (kN/m or kNm/rad)": s.spring_stiffness,
        }
        for s in supports
    ])


def df_to_supports(df: pd.DataFrame) -> list[SupportDef]:
    supports = []
    for _, row in df.iterrows():
        try:
            if pd.isna(row.get("node_id")):
                continue
            stiffness = row.get("spring_stiffness (kN/m or kNm/rad)")
            if pd.isna(stiffness):
                stiffness = None
            else:
                stiffness = float(stiffness)
            supports.append(SupportDef(
                node_id=int(row["node_id"]),
                type=str(row["support_type"]),
                spring_stiffness=stiffness,
            ))
        except (ValueError, KeyError, TypeError):
            pass
    return supports


def loads_to_df(loads: list[LoadDef], members: list | None = None) -> pd.DataFrame:
    member_map: dict[int, str] = {}
    if members:
        member_map = {m.id: f"{m.start_node}-{m.end_node}" for m in members}
    if not loads:
        return pd.DataFrame(columns=[
            "load_id", "type", "node_or_member_id", "member_label",
            "direction", "magnitude",
        ])
    return pd.DataFrame([
        {
            "load_id": l.id,
            "type": l.type,
            "node_or_member_id": l.node_or_member_id,
            "member_label": member_map.get(l.node_or_member_id, "")
                if l.type == "UDL" else "",
            "direction": l.direction,
            "magnitude": l.magnitude,
        }
        for l in loads
    ])


def df_to_loads(df: pd.DataFrame) -> list[LoadDef]:
    loads = []
    used_ids: set[int] = set()
    # First pass: collect explicitly assigned IDs
    for _, row in df.iterrows():
        try:
            lid = row.get("load_id")
            if not pd.isna(lid):
                used_ids.add(int(lid))
        except (ValueError, TypeError):
            pass
    next_id = max(used_ids, default=0) + 1
    for _, row in df.iterrows():
        try:
            load_type = row.get("type")
            nom_id = row.get("node_or_member_id")
            if pd.isna(load_type) or pd.isna(nom_id):
                continue  # skip rows without essential fields
            lid = row.get("load_id")
            if pd.isna(lid):
                # Auto-assign next available ID
                lid = next_id
                while lid in used_ids:
                    lid += 1
                next_id = lid + 1
                used_ids.add(lid)
            else:
                lid = int(lid)
            loads.append(LoadDef(
                id=lid,
                type=str(load_type),
                node_or_member_id=int(nom_id),
                direction=str(row.get("direction", "Fy")),
                magnitude=float(row["magnitude"]),
            ))
        except (ValueError, KeyError, TypeError):
            pass
    return loads


# ---------------------------------------------------------------------------
# Plotly — unified canvas with overlay support
# ---------------------------------------------------------------------------


def _compute_auto_range(model: ModelDefinition, s_size: float = 0.0) -> tuple:
    """Compute auto-scale range from geometry ONLY.

    This range is fixed and does NOT change when overlays (deformed,
    M/V/N diagrams) are toggled.  Force diagrams and deformed shapes
    are drawn on the geometry and may extend slightly outside the
    viewport — this is the conventional engineering rendering approach.
    """
    all_x = [n.x for n in model.nodes] if model.nodes else [0]
    all_y = [n.y for n in model.nodes] if model.nodes else [0]

    # Add padding for support symbols
    if s_size > 0:
        supported_nodes = {s.node_id for s in model.supports}
        node_coords = {n.id: (n.x, n.y) for n in model.nodes}
        for nid in supported_nodes:
            if nid in node_coords:
                nx, ny = node_coords[nid]
                pad = s_size * 1.5
                all_x.extend([nx - pad, nx + pad])
                all_y.extend([ny - pad, ny + pad])

    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)
    x_range = x_max - x_min if x_max > x_min else 2
    y_range = y_max - y_min if y_max > y_min else 2

    # Fixed generous margin so force diagrams fit reasonably
    margin = max(x_range, y_range, 2) * 0.35

    return (x_min - margin, x_max + margin, y_min - margin, y_max + margin)


def build_canvas_figure(model: ModelDefinition,
                        diagram_data: dict | None = None,
                        show_deformed: bool = False,
                        deform_scale: float = 50.0,
                        show_moment: bool = False,
                        show_shear: bool = False,
                        show_axial: bool = False,
                        show_node_ids: bool = True,
                        show_member_ids: bool = True,
                        show_member_labels_flag: bool = False,
                        show_reactions: bool = False,
                        show_grid: bool = True,
                        show_loads: bool = True,
                        solve_result=None,
                        scale_M: float = 1.0,
                        scale_V: float = 1.0,
                        scale_N: float = 1.0,
                        arrow_scale: float = 1.0,
                        hinge_size: int = 10,
                        dark_mode: bool = False,
                        label_scale: float = 1.0,
                        label_offset_scale: float = 1.0,
                        line_thickness_scale: float = 1.0) -> go.Figure:
    """Build a single unified Plotly figure with geometry + optional overlays."""
    fig = go.Figure()

    # Determine which force overlays are active
    force_quantities = []
    if show_moment:
        force_quantities.append("M")
    if show_shear:
        force_quantities.append("Q")
    if show_axial:
        force_quantities.append("N")

    # --- Geometry layer ---
    node_coords = {n.id: (n.x, n.y) for n in model.nodes}
    hinge_set = {h.member_id: h for h in model.hinges}

    # Compute symbol size from structure dimensions
    all_x = [n.x for n in model.nodes] if model.nodes else [0]
    all_y = [n.y for n in model.nodes] if model.nodes else [0]
    max_dim = max(max(all_x) - min(all_x), max(all_y) - min(all_y), 1)
    s_size = max_dim * 0.05

    # Members — solid dark gray, always same style regardless of overlays
    geom_color = COLOR_GEOMETRY
    geom_width = 3 * line_thickness_scale

    # Compute scaled font sizes and offsets
    _fs_node = max(6, int(11 * label_scale))
    _fs_member = max(6, int(10 * label_scale))
    _fs_load = max(6, int(10 * label_scale))
    _fs_diag = max(6, int(9 * label_scale))
    _fs_react = max(6, int(9 * label_scale))
    _yshift_member = int(12 * label_offset_scale)
    _yshift_node = int(12 * label_offset_scale)
    show_member_labels = show_member_labels_flag

    for m in model.members:
        if m.start_node in node_coords and m.end_node in node_coords:
            x1, y1 = node_coords[m.start_node]
            x2, y2 = node_coords[m.end_node]
            fig.add_trace(go.Scatter(
                x=[x1, x2], y=[y1, y2],
                mode="lines",
                line=dict(color=geom_color, width=geom_width),
                name=f"Member {m.id}",
                hoverinfo="text",
                text=f"Member {m.id}<br>Section {m.section_id}",
                showlegend=False,
            ))
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            # Member ID label (conditional)
            if show_member_ids:
                fig.add_annotation(x=mx, y=my, text=f"M{m.id}",
                                   showarrow=False,
                                   font=dict(size=_fs_member, color=COLOR_MEMBER_LABEL),
                                   yshift=_yshift_member)
            # Member label "start-end" (conditional, below member ID)
            if show_member_labels:
                fig.add_annotation(
                    x=mx, y=my,
                    text=f"{m.start_node}-{m.end_node}",
                    showarrow=False,
                    font=dict(size=_fs_member, color=COLOR_MEMBER_LABEL),
                    yshift=-_yshift_member,
                )

    # Draw hinge symbols AFTER all members so they appear on top
    hinge_bg = "#0e1117" if dark_mode else "white"
    for m in model.members:
        if m.id in hinge_set and m.start_node in node_coords and m.end_node in node_coords:
            h = hinge_set[m.id]
            x1, y1 = node_coords[m.start_node]
            x2, y2 = node_coords[m.end_node]
            if h.start_release:
                fig.add_trace(go.Scatter(
                    x=[x1], y=[y1], mode="markers",
                    marker=dict(size=hinge_size, color=hinge_bg,
                                symbol="circle",
                                line=dict(width=2.5, color=COLOR_HINGE)),
                    showlegend=False, hoverinfo="text",
                    hovertext=f"Hinge at M{m.id} start",
                ))
            if h.end_release:
                fig.add_trace(go.Scatter(
                    x=[x2], y=[y2], mode="markers",
                    marker=dict(size=hinge_size, color=hinge_bg,
                                symbol="circle",
                                line=dict(width=2.5, color=COLOR_HINGE)),
                    showlegend=False, hoverinfo="text",
                    hovertext=f"Hinge at M{m.id} end",
                ))

    # Nodes
    for n in model.nodes:
        fig.add_trace(go.Scatter(
            x=[n.x], y=[n.y],
            mode="markers",
            marker=dict(size=6, color=COLOR_NODE),
            hoverinfo="text",
            hovertext=f"Node {n.id}<br>({n.x}, {n.y}) m",
            showlegend=False,
        ))
        # Node label as annotation (supports yshift for offset control)
        if show_node_ids:
            fig.add_annotation(
                x=n.x, y=n.y, text=f"{n.id}",
                showarrow=False,
                font=dict(size=_fs_node, color=COLOR_NODE_LABEL),
                yshift=_yshift_node,
            )

    # Support symbols — proper structural conventions
    _draw_support_symbols(fig, model, s_size)

    # Applied loads — conditional on show_loads toggle
    if show_loads:
        member_map = {m.id: m for m in model.members}

        # Pre-compute max point force for proportional arrow scaling
        max_point_force = 0.0
        for ld in model.loads:
            if ld.type == "point_force":
                max_point_force = max(max_point_force, abs(ld.magnitude))

        min_arrow = max_dim * 0.03 * arrow_scale
        max_arrow = max_dim * 0.15 * arrow_scale

        for load in model.loads:
            if load.type == "point_force" and load.node_or_member_id in node_coords:
                x, y = node_coords[load.node_or_member_id]
                # Scale arrow length proportionally to magnitude
                if max_point_force > 1e-9:
                    ratio = abs(load.magnitude) / max_point_force
                    arrow_len = min_arrow + ratio * (max_arrow - min_arrow)
                else:
                    arrow_len = min_arrow
                dx, dy = 0, 0
                if load.direction == "Fx":
                    dx = arrow_len * (1 if load.magnitude > 0 else -1)
                elif load.direction == "Fy":
                    dy = arrow_len * (1 if load.magnitude > 0 else -1)
                fig.add_annotation(
                    x=x, y=y, ax=x - dx, ay=y - dy,
                    xref="x", yref="y", axref="x", ayref="y",
                    showarrow=True,
                    arrowhead=2, arrowsize=1.5, arrowwidth=2,
                    arrowcolor="red",
                    text=f"{abs(load.magnitude)} kN",
                    font=dict(color="red", size=_fs_load),
                )
            elif load.type == "point_moment" and load.node_or_member_id in node_coords:
                x, y = node_coords[load.node_or_member_id]
                fig.add_annotation(
                    x=x, y=y, text=f"M={load.magnitude} kNm",
                    showarrow=False, font=dict(color="purple", size=_fs_load),
                    yshift=-20,
                )
            elif load.type == "UDL" and load.node_or_member_id in member_map:
                _draw_udl_load(fig, load, member_map[load.node_or_member_id],
                               node_coords, s_size, font_size=_fs_load)

    # --- Deformed shape overlay ---
    if show_deformed and diagram_data:
        _add_deformed_overlay(fig, diagram_data, deform_scale)

    # --- Force diagram overlays ---
    if show_moment and diagram_data:
        _add_force_overlay(fig, diagram_data, "M", COLOR_MOMENT, COLOR_MOMENT_LINE,
                           scale_factor=scale_M)
        _add_force_value_annotations(fig, diagram_data, "M", scale_factor=scale_M, font_size=_fs_diag)
    if show_shear and diagram_data:
        _add_force_overlay(fig, diagram_data, "Q", COLOR_SHEAR, COLOR_SHEAR_LINE,
                           scale_factor=scale_V)
        _add_force_value_annotations(fig, diagram_data, "Q", scale_factor=scale_V, font_size=_fs_diag)
    if show_axial and diagram_data:
        _add_force_overlay(fig, diagram_data, "N",
                           COLOR_AXIAL_TENSION, COLOR_AXIAL_TENSION_LINE,
                           scale_factor=scale_N)
        _add_force_value_annotations(fig, diagram_data, "N", scale_factor=scale_N, font_size=_fs_diag)

    # --- Reaction arrows ---
    if show_reactions and solve_result and solve_result.status == "ok":
        _draw_reaction_arrows(fig, model, solve_result, s_size,
                              font_size=_fs_react)

    # --- Layout with fixed geometry-based scale ---
    x_lo, x_hi, y_lo, y_hi = _compute_auto_range(model, s_size=s_size)

    if dark_mode:
        bg_color = "#0e1117"
        grid_clr = "rgba(100,100,100,0.3)"
        line_clr = "rgba(180,180,180,0.6)"
        zero_clr = "rgba(255,255,255,0.2)"
        text_clr = "rgba(230,230,230,1)"
    else:
        bg_color = "white"
        grid_clr = "rgba(200,200,200,0.5)"
        line_clr = "rgba(80,80,80,0.8)"
        zero_clr = "rgba(0,0,0,0.3)"
        text_clr = None

    axis_common = dict(
        showgrid=show_grid,
        gridcolor=grid_clr,
        showline=True,
        linewidth=1,
        linecolor=line_clr,
        zeroline=True,
        zerolinewidth=1,
        zerolinecolor=zero_clr,
        mirror="ticks",
        ticks="outside",
        ticklen=5,
    )

    layout_kwargs = dict(
        xaxis=dict(title="x (m)", scaleanchor="y", scaleratio=1,
                   range=[x_lo, x_hi], **axis_common),
        yaxis=dict(title="y (m)", range=[y_lo, y_hi], **axis_common),
        plot_bgcolor=bg_color,
        paper_bgcolor=bg_color,
        height=CANVAS_HEIGHT,
        margin=dict(l=40, r=40, t=20, b=40),
        showlegend=False,
        dragmode="pan",
    )
    if text_clr:
        layout_kwargs["font"] = dict(color=text_clr)
    fig.update_layout(**layout_kwargs)
    return fig


# ---------------------------------------------------------------------------
# Support symbol drawing — structural conventions
# ---------------------------------------------------------------------------


def _get_fixed_support_direction(model: ModelDefinition, node_id: int) -> float:
    """Return direction away from connected members (for fixed wall)."""
    node_coords = {n.id: (n.x, n.y) for n in model.nodes}
    if node_id not in node_coords:
        return -math.pi / 2

    nx, ny = node_coords[node_id]
    member_angles = []
    for m in model.members:
        if m.start_node == node_id and m.end_node in node_coords:
            ox, oy = node_coords[m.end_node]
            member_angles.append(math.atan2(oy - ny, ox - nx))
        elif m.end_node == node_id and m.start_node in node_coords:
            ox, oy = node_coords[m.start_node]
            member_angles.append(math.atan2(oy - ny, ox - nx))

    if not member_angles:
        return -math.pi / 2

    avg_sin = sum(math.sin(a) for a in member_angles) / len(member_angles)
    avg_cos = sum(math.cos(a) for a in member_angles) / len(member_angles)
    member_angle = math.atan2(avg_sin, avg_cos)
    return member_angle + math.pi  # opposite direction


def _draw_pinned_support(fig: go.Figure, x: float, y: float,
                         s: float, direction: float):
    """Draw a pinned (hinge) support: triangle + ground line + hatching."""
    cos_d = math.cos(direction)
    sin_d = math.sin(direction)
    # perpendicular direction
    cos_p = math.cos(direction + math.pi / 2)
    sin_p = math.sin(direction + math.pi / 2)

    # Triangle: apex at node, two base corners at distance s along direction
    bx = x + s * cos_d  # base center
    by = y + s * sin_d
    b1x = bx + s * 0.5 * cos_p
    b1y = by + s * 0.5 * sin_p
    b2x = bx - s * 0.5 * cos_p
    b2y = by - s * 0.5 * sin_p

    # Triangle outline
    fig.add_trace(go.Scatter(
        x=[x, b1x, b2x, x], y=[y, b1y, b2y, y],
        mode="lines", fill="toself",
        fillcolor=COLOR_SUPPORT_FILL,
        line=dict(color=COLOR_SUPPORT, width=2),
        showlegend=False, hoverinfo="skip",
    ))

    # Ground line at base
    g1x = bx + s * 0.6 * cos_p
    g1y = by + s * 0.6 * sin_p
    g2x = bx - s * 0.6 * cos_p
    g2y = by - s * 0.6 * sin_p
    fig.add_trace(go.Scatter(
        x=[g1x, g2x], y=[g1y, g2y],
        mode="lines", line=dict(color=COLOR_SUPPORT, width=2.5),
        showlegend=False, hoverinfo="skip",
    ))

    # Hatching lines below ground line
    n_hatch = 5
    for i in range(n_hatch):
        t = (i + 0.5) / n_hatch
        hx = g2x + t * (g1x - g2x)
        hy = g2y + t * (g1y - g2y)
        hx2 = hx + s * 0.25 * cos_d
        hy2 = hy + s * 0.25 * sin_d
        fig.add_trace(go.Scatter(
            x=[hx, hx2], y=[hy, hy2],
            mode="lines", line=dict(color=COLOR_SUPPORT, width=1),
            showlegend=False, hoverinfo="skip",
        ))


def _draw_fixed_support(fig: go.Figure, x: float, y: float,
                        s: float, direction: float):
    """Draw a fixed support: thick wall line + hatching behind wall."""
    cos_d = math.cos(direction)
    sin_d = math.sin(direction)
    cos_p = math.cos(direction + math.pi / 2)
    sin_p = math.sin(direction + math.pi / 2)

    # Wall line at node, perpendicular to direction
    w1x = x + s * 0.6 * cos_p
    w1y = y + s * 0.6 * sin_p
    w2x = x - s * 0.6 * cos_p
    w2y = y - s * 0.6 * sin_p
    fig.add_trace(go.Scatter(
        x=[w1x, w2x], y=[w1y, w2y],
        mode="lines", line=dict(color=COLOR_SUPPORT, width=3.5),
        showlegend=False, hoverinfo="skip",
    ))

    # Hatching behind wall
    n_hatch = 6
    for i in range(n_hatch):
        t = (i + 0.5) / n_hatch
        hx = w2x + t * (w1x - w2x)
        hy = w2y + t * (w1y - w2y)
        hx2 = hx + s * 0.3 * cos_d
        hy2 = hy + s * 0.3 * sin_d
        fig.add_trace(go.Scatter(
            x=[hx, hx2], y=[hy, hy2],
            mode="lines", line=dict(color=COLOR_SUPPORT, width=1),
            showlegend=False, hoverinfo="skip",
        ))


def _draw_roller_support(fig: go.Figure, x: float, y: float,
                         s: float, direction: float):
    """Draw a roller support: pinned triangle + 2 circles below base."""
    cos_d = math.cos(direction)
    sin_d = math.sin(direction)
    cos_p = math.cos(direction + math.pi / 2)
    sin_p = math.sin(direction + math.pi / 2)

    # Triangle (same as pinned)
    bx = x + s * cos_d
    by = y + s * sin_d
    b1x = bx + s * 0.5 * cos_p
    b1y = by + s * 0.5 * sin_p
    b2x = bx - s * 0.5 * cos_p
    b2y = by - s * 0.5 * sin_p

    fig.add_trace(go.Scatter(
        x=[x, b1x, b2x, x], y=[y, b1y, b2y, y],
        mode="lines", fill="toself",
        fillcolor=COLOR_SUPPORT_FILL,
        line=dict(color=COLOR_SUPPORT, width=2),
        showlegend=False, hoverinfo="skip",
    ))

    # Two roller circles below triangle base
    r = s * 0.12
    c1x = bx + s * 0.2 * cos_p + r * cos_d
    c1y = by + s * 0.2 * sin_p + r * sin_d
    c2x = bx - s * 0.2 * cos_p + r * cos_d
    c2y = by - s * 0.2 * sin_p + r * sin_d

    # Draw circles via scatter markers
    fig.add_trace(go.Scatter(
        x=[c1x, c2x], y=[c1y, c2y],
        mode="markers",
        marker=dict(size=s * 18, color=COLOR_SUPPORT_FILL,
                    symbol="circle",
                    line=dict(width=1.5, color=COLOR_SUPPORT)),
        showlegend=False, hoverinfo="skip",
    ))

    # Ground line below rollers
    gd = s * 1.0 + 2 * r
    gcx = x + gd * cos_d
    gcy = y + gd * sin_d
    g1x = gcx + s * 0.6 * cos_p
    g1y = gcy + s * 0.6 * sin_p
    g2x = gcx - s * 0.6 * cos_p
    g2y = gcy - s * 0.6 * sin_p
    fig.add_trace(go.Scatter(
        x=[g1x, g2x], y=[g1y, g2y],
        mode="lines", line=dict(color=COLOR_SUPPORT, width=2.5),
        showlegend=False, hoverinfo="skip",
    ))


def _draw_spring_support(fig: go.Figure, x: float, y: float,
                         s: float, direction: float):
    """Draw a spring support: zigzag polyline + ground line."""
    cos_d = math.cos(direction)
    sin_d = math.sin(direction)
    cos_p = math.cos(direction + math.pi / 2)
    sin_p = math.sin(direction + math.pi / 2)

    # Zigzag from node along direction
    n_coils = 4
    coil_len = s * 1.2
    seg_len = coil_len / (n_coils * 2 + 1)
    amp = s * 0.25

    pts_x = [x]
    pts_y = [y]
    for i in range(1, n_coils * 2 + 2):
        dist = seg_len * i
        px = x + dist * cos_d
        py = y + dist * sin_d
        if 0 < i <= n_coils * 2:
            side = amp if (i % 2 == 1) else -amp
            px += side * cos_p
            py += side * sin_p
        pts_x.append(px)
        pts_y.append(py)

    fig.add_trace(go.Scatter(
        x=pts_x, y=pts_y,
        mode="lines", line=dict(color=COLOR_SUPPORT, width=2),
        showlegend=False, hoverinfo="skip",
    ))

    # Ground line at end
    end_x = x + coil_len * cos_d
    end_y = y + coil_len * sin_d
    g1x = end_x + s * 0.5 * cos_p
    g1y = end_y + s * 0.5 * sin_p
    g2x = end_x - s * 0.5 * cos_p
    g2y = end_y - s * 0.5 * sin_p
    fig.add_trace(go.Scatter(
        x=[g1x, g2x], y=[g1y, g2y],
        mode="lines", line=dict(color=COLOR_SUPPORT, width=2.5),
        showlegend=False, hoverinfo="skip",
    ))


def _draw_udl_load(fig: go.Figure, load, member: MemberDef,
                    node_coords: dict, s_size: float,
                    font_size: int = 10):
    """Draw a UDL as a row of arrows along the member with a connecting line."""
    if member.start_node not in node_coords or member.end_node not in node_coords:
        return
    x1, y1 = node_coords[member.start_node]
    x2, y2 = node_coords[member.end_node]
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1e-9:
        return

    # UDL start/end positions along member (fraction 0..1)
    t_start = (load.udl_start / length) if load.udl_start is not None else 0.0
    t_end = (load.udl_end / length) if load.udl_end is not None else 1.0
    t_start = max(0.0, min(1.0, t_start))
    t_end = max(t_start, min(1.0, t_end))

    # Arrow direction: perpendicular for Fy, along member for Fx
    # Plotly annotations: (ax,ay) = tail, (x,y) = arrowhead/tip.
    # For downward load (magnitude < 0): tail above beam, tip at beam → arrow points DOWN.
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = s_size * 1.5
    if load.direction == "Fy":
        # Tail offset is OPPOSITE to load direction so arrows point WITH the load
        sign = 1 if load.magnitude < 0 else -1
        ax_dx = 0
        ax_dy = sign * arrow_len
    elif load.direction == "Fx":
        sign = -1 if load.magnitude > 0 else 1
        ax_dx = sign * arrow_len
        ax_dy = 0
    else:
        return  # Mz UDL not visualised

    # Draw arrows at regular intervals
    n_arrows = max(4, int(length * (t_end - t_start) / (s_size * 1.5)))
    n_arrows = min(n_arrows, 15)

    arrow_tips_x = []
    arrow_tips_y = []
    arrow_tails_x = []
    arrow_tails_y = []

    for i in range(n_arrows + 1):
        t = t_start + (t_end - t_start) * i / n_arrows
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        arrow_tips_x.append(px)
        arrow_tips_y.append(py)
        arrow_tails_x.append(px + ax_dx)
        arrow_tails_y.append(py + ax_dy)

        # Individual arrows
        fig.add_annotation(
            x=px, y=py,
            ax=px + ax_dx, ay=py + ax_dy,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True,
            arrowhead=2, arrowsize=1, arrowwidth=1.5,
            arrowcolor="red",
            text="",
        )

    # Connecting line across arrow tails
    fig.add_trace(go.Scatter(
        x=arrow_tails_x, y=arrow_tails_y,
        mode="lines",
        line=dict(color="red", width=1.5),
        showlegend=False, hoverinfo="skip",
    ))

    # Label at midpoint
    mid_t = (t_start + t_end) / 2
    mid_x = x1 + mid_t * (x2 - x1) + ax_dx
    mid_y = y1 + mid_t * (y2 - y1) + ax_dy
    fig.add_annotation(
        x=mid_x, y=mid_y,
        text=f"{abs(load.magnitude)} kN/m",
        showarrow=False,
        font=dict(color="red", size=font_size),
        yshift=12 if ax_dy > 0 else -12,
    )


def _draw_support_symbols(fig: go.Figure, model: ModelDefinition, s_size: float):
    """Draw all support symbols on the figure."""
    node_coords = {n.id: (n.x, n.y) for n in model.nodes}

    for sup in model.supports:
        if sup.node_id not in node_coords:
            continue
        x, y = node_coords[sup.node_id]

        if sup.type == "pinned":
            # Pinned: always downward
            _draw_pinned_support(fig, x, y, s_size, -math.pi / 2)
        elif sup.type == "fixed":
            # Fixed: wall faces away from connected member
            direction = _get_fixed_support_direction(model, sup.node_id)
            _draw_fixed_support(fig, x, y, s_size, direction)
        elif sup.type == "roller_x":
            # Roller in x → restrained vertically → symbol downward
            _draw_roller_support(fig, x, y, s_size, -math.pi / 2)
        elif sup.type == "roller_y":
            # Roller in y → restrained horizontally → symbol left
            _draw_roller_support(fig, x, y, s_size, math.pi)
        elif sup.type == "spring_linear_x":
            # Spring in x → horizontal → symbol left
            _draw_spring_support(fig, x, y, s_size, math.pi)
        elif sup.type == "spring_linear_y":
            # Spring in y → vertical → symbol downward
            _draw_spring_support(fig, x, y, s_size, -math.pi / 2)
        elif sup.type == "spring_rotational":
            # Rotational spring → symbol downward
            _draw_spring_support(fig, x, y, s_size, -math.pi / 2)
        elif sup.type == "rotational":
            # Rotational support: circle around node (rotation restrained, free to translate)
            r = s_size * 0.4
            n_pts = 30
            cx = [x + r * math.cos(2 * math.pi * i / n_pts) for i in range(n_pts + 1)]
            cy = [y + r * math.sin(2 * math.pi * i / n_pts) for i in range(n_pts + 1)]
            fig.add_trace(go.Scatter(
                x=cx, y=cy,
                mode="lines", line=dict(color=COLOR_SUPPORT, width=2.5),
                fill="toself", fillcolor="rgba(34,139,34,0.15)",
                showlegend=False, hoverinfo="text",
                hovertext=f"Rotational support at node {sup.node_id}",
            ))
        else:
            # Fallback: simple marker
            fig.add_trace(go.Scatter(
                x=[x], y=[y], mode="markers",
                marker=dict(size=10, color=COLOR_SUPPORT, symbol="triangle-up",
                            line=dict(width=2, color=COLOR_SUPPORT)),
                showlegend=False, hoverinfo="text",
                hovertext=f"Support: {sup.type}",
            ))


def _add_deformed_overlay(fig: go.Figure, diagram_data: dict, scale: float):
    """Add deformed shape traces to an existing figure."""
    for member in diagram_data["members"]:
        x_coords = member["x_coords"]
        y_coords = member["y_coords"]
        defl = member["deflection"]
        ext = member["extension"]
        angle = member["angle"]
        n_pts = len(x_coords)

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        dx_def = []
        dy_def = []
        for i in range(n_pts):
            d_perp = defl[i] if i < len(defl) else 0
            d_par = ext[i] if i < len(ext) else 0
            dx = d_par * cos_a - d_perp * sin_a
            dy = d_par * sin_a + d_perp * cos_a
            dx_def.append(x_coords[i] + dx * scale)
            dy_def.append(y_coords[i] + dy * scale)

        fig.add_trace(go.Scatter(
            x=dx_def, y=dy_def,
            mode="lines",
            line=dict(color=COLOR_DEFORMED, width=3),
            name=f"Deformed M{member['member_id']}",
            showlegend=False,
            hoverinfo="text",
            text=[f"M{member['member_id']}" for _ in dx_def],
        ))


def _add_force_overlay(fig: go.Figure, diagram_data: dict,
                       quantity: str, fill_color: str, line_color: str,
                       scale_factor: float = 1.0):
    """Add a force diagram (M, Q, or N) overlay to an existing figure."""
    is_axial = (quantity == "N")

    max_val = 0
    for member in diagram_data["members"]:
        arr = member.get(quantity, [])
        if arr:
            max_val = max(max_val, max(abs(v) for v in arr))

    if max_val < 1e-6:
        return  # All values are zero — skip drawing entirely

    all_x = [n["x"] for n in diagram_data["nodes"]]
    all_y = [n["y"] for n in diagram_data["nodes"]]
    struct_size = max(max(all_x) - min(all_x), max(all_y) - min(all_y), 1)
    diagram_scale = struct_size * scale_factor * 0.05 / max_val

    for member in diagram_data["members"]:
        x_coords = member["x_coords"]
        y_coords = member["y_coords"]
        values = member.get(quantity, [0] * len(x_coords))
        angle = member["angle"]
        n_pts = len(x_coords)

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        sign = -1 if quantity == "M" else 1

        x_diag = []
        y_diag = []
        hover_texts = []
        for i in range(n_pts):
            v = values[i] if i < len(values) else 0
            offset = v * diagram_scale * sign
            x_diag.append(x_coords[i] + offset * (-sin_a))
            y_diag.append(y_coords[i] + offset * cos_a)
            unit = "kNm" if quantity == "M" else "kN"
            label = ""
            if is_axial:
                label = " T" if v > 0 else (" C" if v < 0 else "")
            hover_texts.append(f"M{member['member_id']}: {v:.3f} {unit}{label}")

        if is_axial:
            # Color by tension/compression
            avg_val = sum(values) / n_pts if n_pts > 0 else 0
            if avg_val >= 0:
                fc = COLOR_AXIAL_TENSION
                lc = COLOR_AXIAL_TENSION_LINE
            else:
                fc = COLOR_AXIAL_COMPRESSION
                lc = COLOR_AXIAL_COMPRESSION_LINE

            x_poly = list(x_coords) + list(reversed(x_diag))
            y_poly = list(y_coords) + list(reversed(y_diag))
            fig.add_trace(go.Scatter(
                x=x_poly, y=y_poly,
                fill="toself", fillcolor=fc,
                line=dict(color=fc, width=0),
                showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=x_diag, y=y_diag,
                mode="lines", line=dict(color=lc, width=2),
                showlegend=False, hoverinfo="text", text=hover_texts,
            ))
        else:
            x_poly = list(x_coords) + list(reversed(x_diag))
            y_poly = list(y_coords) + list(reversed(y_diag))

            fig.add_trace(go.Scatter(
                x=x_poly, y=y_poly,
                fill="toself", fillcolor=fill_color,
                line=dict(color=fill_color, width=0),
                showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=x_diag, y=y_diag,
                mode="lines", line=dict(color=line_color, width=2),
                showlegend=False, hoverinfo="text", text=hover_texts,
            ))


def _add_force_value_annotations(fig: go.Figure, diagram_data: dict,
                                  quantity: str, scale_factor: float = 1.0,
                                  font_size: int = 9):
    """Add value annotations at start, end, and max locations of force diagrams."""
    if quantity == "M":
        color = COLOR_MOMENT_LINE
        unit = "kNm"
    elif quantity == "Q":
        color = COLOR_SHEAR_LINE
        unit = "kN"
    else:  # N
        color = COLOR_AXIAL_TENSION_LINE
        unit = "kN"

    # Compute diagram scale (same as _add_force_overlay)
    max_val = 0
    for member in diagram_data["members"]:
        arr = member.get(quantity, [])
        if arr:
            max_val = max(max_val, max(abs(v) for v in arr))
    if max_val == 0:
        return

    all_x = [n["x"] for n in diagram_data["nodes"]]
    all_y = [n["y"] for n in diagram_data["nodes"]]
    struct_size = max(max(all_x) - min(all_x), max(all_y) - min(all_y), 1)
    diagram_scale = struct_size * scale_factor * 0.05 / max_val
    sign = -1 if quantity == "M" else 1

    for member in diagram_data["members"]:
        x_coords = member["x_coords"]
        y_coords = member["y_coords"]
        values = member.get(quantity, [0] * len(x_coords))
        angle = member["angle"]
        n_pts = len(x_coords)
        if n_pts == 0:
            continue

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Find indices: start (0), end (-1), and max abs location
        indices_to_label = set()
        indices_to_label.add(0)
        indices_to_label.add(n_pts - 1)

        # Find interior max
        if n_pts > 2:
            max_abs_val = 0
            max_idx = 0
            for i in range(1, n_pts - 1):
                v = values[i] if i < len(values) else 0
                if abs(v) > max_abs_val:
                    max_abs_val = abs(v)
                    max_idx = i
            if max_abs_val > 0.001:
                indices_to_label.add(max_idx)

        for idx in indices_to_label:
            v = values[idx] if idx < len(values) else 0
            if abs(v) < 0.001:
                continue
            offset = v * diagram_scale * sign
            lx = x_coords[idx] + offset * (-sin_a)
            ly = y_coords[idx] + offset * cos_a
            fig.add_annotation(
                x=lx, y=ly,
                text=f"{v:.2f}",
                showarrow=False,
                font=dict(size=font_size, color=color),
                bgcolor="rgba(255,255,255,0.8)",
                borderpad=1,
            )


def _draw_reaction_arrows(fig: go.Figure, model: ModelDefinition,
                           solve_result, s_size: float,
                           font_size: int = 9):
    """Draw reaction force arrows at support nodes (including zero values)."""
    node_coords = {n.id: (n.x, n.y) for n in model.nodes}
    arrow_len = s_size * 3

    # Build a map of which DOFs are restrained per node
    sup_map = {s.node_id: s for s in model.supports}

    for reaction in solve_result.reactions:
        nid = reaction.node_id
        if nid not in node_coords:
            continue
        nx, ny = node_coords[nid]
        sup = sup_map.get(nid)

        # Determine which DOFs are restrained by this support type
        has_rx = sup and sup.type in ("pinned", "fixed", "roller_y",
                                       "spring_linear_x")
        has_ry = sup and sup.type in ("pinned", "fixed", "roller_x",
                                       "spring_linear_y")
        has_mz = sup and sup.type in ("fixed", "rotational",
                                       "spring_rotational")

        # Rx — horizontal arrow
        if has_rx:
            direction = 1 if reaction.Rx_kN >= 0 else -1
            if reaction.Rx_kN == 0:
                direction = 1  # default rightward for zero
            ax_start = nx - direction * arrow_len
            fig.add_annotation(
                x=nx, y=ny,
                ax=ax_start, ay=ny,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True,
                arrowhead=2, arrowsize=1.5, arrowwidth=2,
                arrowcolor=COLOR_REACTION,
                text=f"Rx={reaction.Rx_kN:.2f} kN",
                font=dict(color=COLOR_REACTION, size=font_size),
                bgcolor="rgba(255,255,255,0.8)",
                borderpad=1,
            )

        # Ry — vertical arrow
        if has_ry:
            direction = 1 if reaction.Ry_kN >= 0 else -1
            if reaction.Ry_kN == 0:
                direction = 1  # default upward for zero
            ay_start = ny - direction * arrow_len
            fig.add_annotation(
                x=nx, y=ny,
                ax=nx, ay=ay_start,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True,
                arrowhead=2, arrowsize=1.5, arrowwidth=2,
                arrowcolor=COLOR_REACTION,
                text=f"Ry={reaction.Ry_kN:.2f} kN",
                font=dict(color=COLOR_REACTION, size=font_size),
                bgcolor="rgba(255,255,255,0.8)",
                borderpad=1,
            )

        # Mz — curved moment arc (polyline approximation)
        if has_mz:
            direction = 1 if reaction.Mz_kNm > 0 else -1
            r = s_size * 1.5
            n_arc = 20
            arc_range = 1.5 * math.pi  # 270 degrees
            start_angle = -math.pi / 4
            arc_x = []
            arc_y = []
            for i in range(n_arc + 1):
                t = i / n_arc
                a = start_angle + direction * t * arc_range
                arc_x.append(nx + r * math.cos(a))
                arc_y.append(ny + r * math.sin(a))

            fig.add_trace(go.Scatter(
                x=arc_x, y=arc_y,
                mode="lines", line=dict(color=COLOR_REACTION, width=2),
                showlegend=False, hoverinfo="skip",
            ))

            # Arrowhead at end of arc
            end_a = start_angle + direction * arc_range
            fig.add_annotation(
                x=arc_x[-1], y=arc_y[-1],
                ax=arc_x[-2], ay=arc_y[-2],
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True,
                arrowhead=2, arrowsize=1.5, arrowwidth=2,
                arrowcolor=COLOR_REACTION,
                text=f"Mz={reaction.Mz_kNm:.2f} kNm",
                font=dict(color=COLOR_REACTION, size=font_size),
                bgcolor="rgba(255,255,255,0.8)",
                borderpad=1,
            )


# ---------------------------------------------------------------------------
# Top menu bar
# ---------------------------------------------------------------------------


def render_sidebar_file():
    """Render the File expander and model name in the sidebar."""
    with st.sidebar:
        # --- File section (expander) ---
        with st.expander("File", expanded=False):
            # New Model
            if st.button("New Model", use_container_width=True):
                st.session_state.model = ModelDefinition()
                st.session_state.model_name = ""
                st.session_state.model_description = ""
                st.session_state.solve_result = None
                st.session_state.diagram_data = None
                st.session_state.show_results = False
                st.session_state.show_node_ids = True
                st.session_state.show_member_ids = True
                st.session_state.show_member_labels = False
                st.session_state.show_reactions = False
                st.session_state.show_grid = True
                st.session_state.show_loads = True
                st.session_state.show_deformed = False
                st.session_state.show_moment = False
                st.session_state.show_shear = False
                st.session_state.show_axial = False
                _defaults = load_default_settings()
                for key, val in _defaults.items():
                    st.session_state[key] = val
                st.session_state.active_editor = None
                _clear_editor_keys()
                st.rerun()

            # Load Model
            uploaded = st.file_uploader(
                "Load Model",
                type=["yaml", "fem.yaml"],
                key="file_uploader",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                try:
                    text = uploaded.read().decode("utf-8")
                    raw = file_io.deserialize(text)
                    sfem, data, ds = file_io.parse_envelope(raw)
                    model = dict_to_model(data)
                    model.name = sfem.get("name", "")
                    model.description = sfem.get("description", "")
                    load_model_to_state(model)
                    # Restore display settings
                    _defaults = load_default_settings()
                    for key in DEFAULT_SETTINGS:
                        if ds and key in ds:
                            st.session_state[key] = ds[key]
                        else:
                            st.session_state[key] = _defaults[key]
                    st.success(f"Loaded: {model.name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load: {e}")

            # Save Model
            model = model_from_state()
            has_data = has_model_data()
            if has_data:
                model_data = model_to_dict(model)
                model_data["structure_type"] = model.structure_type
                model_data["mesh_size"] = model.mesh_size
                ds = {k: st.session_state.get(k, v) for k, v in DEFAULT_SETTINGS.items()}
                envelope = file_io.make_model_envelope(
                    model.name or "fem_model", model_data, display_settings=ds)
                yaml_str = file_io.serialize_model(envelope)
                name = st.session_state.model_name or "fem_model"
                filename = f"{name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.{file_io.MODEL_EXT}"
            else:
                yaml_str = ""
                filename = "fem_model.fem.yaml"
            st.download_button(
                "Save Model",
                data=yaml_str,
                file_name=filename,
                mime="text/yaml",
                use_container_width=True,
                disabled=not has_data,
            )

            st.markdown("---")

            # Save as Template
            if st.button("Save as Template", use_container_width=True,
                          help="Save model to templates for reuse"):
                tpl_name = st.session_state.model_name
                if not tpl_name.strip():
                    st.error("Enter a model name first.")
                elif not has_data:
                    st.error("No model data to save.")
                else:
                    try:
                        model_data = model_to_dict(model)
                        model_data["structure_type"] = model.structure_type
                        model_data["mesh_size"] = model.mesh_size
                        env = file_io.make_model_envelope(tpl_name, model_data)
                        path = file_io.save_template(env, tpl_name)
                        st.success(f"Saved template: {path.name}")
                    except Exception as e:
                        st.error(f"Save failed: {e}")

            st.markdown("---")

            # Templates
            with st.expander("Templates"):
                templates = file_io.load_template_list()
                if templates:
                    for idx, tpl in enumerate(templates):
                        if st.button(tpl["name"], key=f"tpl_{idx}", use_container_width=True):
                            model = _load_template_model(tpl["path"])
                            load_model_to_state(model)
                            st.rerun()
                else:
                    st.caption("No templates found.")

        # Model name
        st.session_state.model_name = st.text_input(
            "Model name",
            value=st.session_state.model_name,
            label_visibility="collapsed",
            placeholder="Model name",
        )



# ---------------------------------------------------------------------------
# Model tree (left column)
# ---------------------------------------------------------------------------


def render_model_tree():
    """Render the model tree with entity counts, toggles, and solve button."""
    model = st.session_state.model

    tree_items = [
        ("Nodes", len(model.nodes), "nodes"),
        ("Members", len(model.members), "members"),
        ("Load & Supports", len(model.loads) + len(model.supports), "load_supports"),
        ("Properties", len(model.materials) + len(model.cross_sections), "properties"),
    ]

    for label, count, key in tree_items:
        btn_label = f"{label} ({count})"
        btn_type = "primary" if st.session_state.active_editor == key else "secondary"
        if st.button(btn_label, key=f"tree_{key}", use_container_width=True, type=btn_type):
            st.session_state.active_editor = key
            st.session_state.show_results = False
            st.rerun()

    # Results button — right after tree items
    has_results = (
        st.session_state.solve_result is not None
        and st.session_state.solve_result.status == "ok"
    )
    if has_results:
        if st.button("Results", use_container_width=True,
                     type="primary" if st.session_state.show_results else "secondary"):
            st.session_state.show_results = True
            st.session_state.active_editor = None
            st.rerun()

    # Settings button
    if st.button("Settings", key="tree_settings", use_container_width=True,
                 type="primary" if st.session_state.active_editor == "settings" else "secondary"):
        st.session_state.active_editor = "settings"
        st.session_state.show_results = False
        st.rerun()

    # --- Visualization toggles ---
    with st.expander("Display", expanded=True):
        st.session_state.show_node_ids = st.checkbox(
            "Node #", value=st.session_state.show_node_ids, key="cb_node_ids",
        )
        st.session_state.show_member_ids = st.checkbox(
            "Member #", value=st.session_state.show_member_ids, key="cb_member_ids",
        )
        st.session_state.show_member_labels = st.checkbox(
            "Member Label", value=st.session_state.show_member_labels,
            key="cb_member_labels",
        )
        st.session_state.show_loads = st.checkbox(
            "Loads", value=st.session_state.show_loads, key="cb_loads",
        )
        st.session_state.show_grid = st.checkbox(
            "Grid", value=st.session_state.show_grid, key="cb_grid",
        )
        st.session_state.show_reactions = st.checkbox(
            "Reactions", value=st.session_state.show_reactions,
            disabled=not has_results, key="cb_reactions",
        )
        st.session_state.show_deformed = st.checkbox(
            "Deformed", value=st.session_state.show_deformed,
            disabled=not has_results, key="cb_deformed",
        )
        st.session_state.show_moment = st.checkbox(
            "Moment (M)", value=st.session_state.show_moment,
            disabled=not has_results, key="cb_moment",
        )
        st.session_state.show_shear = st.checkbox(
            "Shear (V)", value=st.session_state.show_shear,
            disabled=not has_results, key="cb_shear",
        )
        st.session_state.show_axial = st.checkbox(
            "Axial (N)", value=st.session_state.show_axial,
            disabled=not has_results, key="cb_axial",
        )

    st.divider()

    # Solve button
    if st.button("Solve", type="primary", use_container_width=True):
        model = model_from_state()
        with st.status("Solving...", expanded=True) as status:
            st.write("Validating model...")
            result = solve(model)
            st.session_state.solve_result = result
            if result.status == "ok":
                st.write("Extracting diagrams...")
                st.session_state.diagram_data = get_diagram_data(model)
                st.session_state.show_results = True
                st.session_state.active_editor = None
                status.update(label="Analysis complete!", state="complete")
                st.toast("Analysis complete!")
                st.rerun()
            else:
                st.session_state.diagram_data = None
                st.session_state.show_results = False
                status.update(label="Analysis failed", state="error")
                st.error(result.error)


# ---------------------------------------------------------------------------
# Bottom panel editors
# ---------------------------------------------------------------------------


def render_editor_nodes():
    model = st.session_state.model
    st.caption("Define node positions. Coordinates in metres (m).")
    edited = st.data_editor(
        nodes_to_df(model.nodes),
        num_rows="dynamic", use_container_width=True, key="nodes_editor",
        column_config={
            "node_id": st.column_config.NumberColumn("Node ID", min_value=1, step=1, format="%d"),
            "x (m)": st.column_config.NumberColumn("x (m)", format="%.2f"),
            "y (m)": st.column_config.NumberColumn("y (m)", format="%.2f"),
        },
    )
    if st.button("Apply", key="apply_nodes", type="primary"):
        model.nodes = df_to_nodes(edited)
        st.rerun()


def render_editor_members():
    model = st.session_state.model
    st.caption(
        "Connect nodes with members. Assign a section ID. "
        "Tick hinge columns for moment releases (both = truss member)."
    )
    df = members_to_df(model.members, model.hinges)
    edited = st.data_editor(
        df, num_rows="dynamic", use_container_width=True, key="members_editor",
        column_config={
            "member_id": st.column_config.NumberColumn("Member ID", min_value=1, step=1, format="%d"),
            "label": st.column_config.TextColumn("Label", disabled=True),
            "start_node": st.column_config.NumberColumn("Start Node", min_value=1, step=1, format="%d"),
            "end_node": st.column_config.NumberColumn("End Node", min_value=1, step=1, format="%d"),
            "section_id": st.column_config.NumberColumn("Section ID", min_value=1, step=1, format="%d"),
            "hinge_start": st.column_config.CheckboxColumn("Hinge Start"),
            "hinge_end": st.column_config.CheckboxColumn("Hinge End"),
        },
    )
    if st.button("Apply", key="apply_members", type="primary"):
        members, hinges = df_to_members_and_hinges(edited)
        model.members = members
        model.hinges = hinges
        st.rerun()


def render_editor_properties():
    """Render Materials and Sections tables together with library pickers."""
    model = st.session_state.model

    # ── Materials ────────────────────────────────────────────────────────
    st.markdown("**Materials**")

    # Library picker
    lib_mats = load_materials_library()
    if lib_mats:
        mat_names = [m["name"] for m in lib_mats]
        c1, c2 = st.columns([3, 1])
        with c1:
            sel_mat = st.selectbox(
                "Add from library", mat_names,
                key="lib_mat_select", label_visibility="collapsed",
                placeholder="Add material from library...",
                index=None,
            )
        with c2:
            if st.button("Add", key="add_lib_mat") and sel_mat:
                lib_entry = next(m for m in lib_mats if m["name"] == sel_mat)
                next_id = max((m.id for m in model.materials), default=0) + 1
                model.materials.append(MaterialDef(
                    id=next_id,
                    name=lib_entry["name"],
                    E_GPa=lib_entry["E_GPa"],
                ))
                st.rerun()

    st.caption("Define materials. E in GPa. Leave Material ID blank for auto-assign.")
    edited_mat = st.data_editor(
        materials_to_df(model.materials),
        num_rows="dynamic", use_container_width=True, key="materials_editor",
        column_config={
            "material_id": st.column_config.NumberColumn("Material ID", min_value=1, step=1, format="%d"),
            "name": st.column_config.TextColumn("Name"),
            "E (GPa)": st.column_config.NumberColumn("E (GPa)", format="%.1f"),
        },
    )
    if st.button("Apply Materials", key="apply_materials", type="primary"):
        model.materials = df_to_materials(edited_mat)
        st.rerun()

    # ── Cross-Sections ───────────────────────────────────────────────────
    st.markdown("**Cross-Sections**")

    # Library picker
    families = get_section_families()
    if families:
        c1, c2, c3, c4 = st.columns([1.5, 2, 2, 1])
        with c1:
            sel_fam = st.selectbox(
                "Profile family", families,
                key="lib_sec_family",
            )
        with c2:
            lib_secs = load_sections_library(sel_fam) if sel_fam else []
            sec_names = [s["name"] for s in lib_secs]
            sel_sec = st.selectbox(
                "Section", sec_names,
                key="lib_sec_select",
                index=None, placeholder="Select section...",
            )
        with c3:
            # Material picker from model's materials
            mat_options = {f"{m.id}: {m.name}": m.id for m in model.materials}
            sel_mat_ref = st.selectbox(
                "Material", list(mat_options.keys()),
                key="lib_sec_mat",
                index=0 if mat_options else None,
                placeholder="Select material...",
            )
        with c4:
            if st.button("Add", key="add_lib_sec") and sel_sec and sel_mat_ref:
                lib_entry = next(s for s in lib_secs if s["name"] == sel_sec)
                next_id = max((s.id for s in model.cross_sections), default=0) + 1
                model.cross_sections.append(CrossSectionDef(
                    id=next_id,
                    name=lib_entry["name"],
                    A_cm2=lib_entry["A_cm2"],
                    Iz_cm4=lib_entry["Iz_cm4"],
                    material_id=mat_options[sel_mat_ref],
                ))
                st.rerun()

    st.caption("Define cross-sections. A in cm\u00b2, Iz in cm\u2074. Reference a material ID.")
    edited_sec = st.data_editor(
        sections_to_df(model.cross_sections),
        num_rows="dynamic", use_container_width=True, key="sections_editor",
        column_config={
            "section_id": st.column_config.NumberColumn("Section ID", min_value=1, step=1, format="%d"),
            "name": st.column_config.TextColumn("Name"),
            "A (cm\u00b2)": st.column_config.NumberColumn("A (cm\u00b2)", format="%.1f"),
            "Iz (cm\u2074)": st.column_config.NumberColumn("Iz (cm\u2074)", format="%.1f"),
            "material_id": st.column_config.NumberColumn("Material ID", min_value=1, step=1, format="%d"),
        },
    )
    if st.button("Apply Sections", key="apply_sections", type="primary"):
        model.cross_sections = df_to_sections(edited_sec)
        st.rerun()


def render_editor_load_supports():
    """Render Supports and Loads tables together."""
    model = st.session_state.model

    st.markdown("**Supports**")
    st.caption(
        "Assign support conditions to nodes. "
        "Spring stiffness: kN/m for linear, kNm/rad for rotational."
    )
    edited_sup = st.data_editor(
        supports_to_df(model.supports),
        num_rows="dynamic", use_container_width=True, key="supports_editor",
        column_config={
            "node_id": st.column_config.NumberColumn("Node ID", min_value=1, step=1, format="%d"),
            "support_type": st.column_config.SelectboxColumn("Type", options=SUPPORT_TYPES),
            "spring_stiffness (kN/m or kNm/rad)": st.column_config.NumberColumn(
                "Spring k (kN/m | kNm/rad)", format="%.1f",
                help="kN/m for spring_linear_x/y, kNm/rad for spring_rotational."),
        },
    )
    if st.button("Apply Supports", key="apply_supports", type="primary"):
        model.supports = df_to_supports(edited_sup)
        st.rerun()

    st.markdown("**Loads**")
    st.caption(
        "Apply loads. Point force/moment: reference a node ID. "
        "UDL: reference a member ID (full span). Negative Fy = downward."
    )
    edited_loads = st.data_editor(
        loads_to_df(model.loads, members=model.members),
        num_rows="dynamic", use_container_width=True, key="loads_editor",
        column_config={
            "load_id": st.column_config.NumberColumn("Load ID", min_value=1, step=1, format="%d"),
            "type": st.column_config.SelectboxColumn("Type", options=LOAD_TYPES),
            "node_or_member_id": st.column_config.NumberColumn("Node/Member ID", min_value=1, step=1, format="%d"),
            "member_label": st.column_config.TextColumn("Member Label", disabled=True),
            "direction": st.column_config.SelectboxColumn("Direction", options=DIRECTIONS),
            "magnitude": st.column_config.NumberColumn("Magnitude", format="%.2f"),
        },
    )
    if st.button("Apply Loads", key="apply_loads", type="primary"):
        model.loads = df_to_loads(edited_loads)
        st.rerun()


# ---------------------------------------------------------------------------
# Bottom panel — editors or results
# ---------------------------------------------------------------------------


def render_settings_panel():
    """Render settings in the bottom panel."""
    model = st.session_state.model
    has_results = (
        st.session_state.solve_result is not None
        and st.session_state.solve_result.status == "ok"
    )

    # Wrap in a narrower container to keep number inputs compact (Issue 6)
    col_main, col_spacer = st.columns([3, 1])
    with col_main:
        # --- General ---
        st.markdown("**General**")
        c1, c2, c3 = st.columns(3)
        with c1:
            model.mesh_size = st.number_input(
                "FE mesh size",
                min_value=2,
                max_value=200,
                value=model.mesh_size,
                step=5,
                key="settings_mesh_size",
                help="Number of sub-elements per member for FE discretisation",
            )
        with c2:
            st.number_input(
                "Deformation scale",
                min_value=1.0,
                max_value=1000.0,
                value=st.session_state.deform_scale,
                step=10.0,
                key="deform_scale",
            )

        # --- Diagram scales ---
        st.markdown("**Diagram Scales**")
        st.caption("Multiplier for force diagram height (default 1.0).")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input(
                "Moment (M)",
                min_value=0.1,
                max_value=10.0,
                value=st.session_state.diagram_scale_M,
                step=0.1,
                format="%.1f",
                key="diagram_scale_M",
            )
        with c2:
            st.number_input(
                "Shear (V)",
                min_value=0.1,
                max_value=10.0,
                value=st.session_state.diagram_scale_V,
                step=0.1,
                format="%.1f",
                key="diagram_scale_V",
            )
        with c3:
            st.number_input(
                "Axial (N)",
                min_value=0.1,
                max_value=10.0,
                value=st.session_state.diagram_scale_N,
                step=0.1,
                format="%.1f",
                key="diagram_scale_N",
            )

        # --- Symbols & Loads ---
        st.markdown("**Symbols & Loads**")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input(
                "Arrow scale",
                min_value=0.2,
                max_value=3.0,
                value=st.session_state.arrow_scale,
                step=0.1,
                format="%.1f",
                key="arrow_scale",
                help="Multiplier for load arrow length (default 1.0)",
            )
        with c2:
            st.number_input(
                "Hinge size",
                min_value=1,
                max_value=50,
                value=st.session_state.hinge_size,
                step=1,
                key="hinge_size",
                help="Hinge circle diameter in pixels (default 10)",
            )

        # --- Display ---
        st.markdown("**Display**")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input(
                "Label size",
                min_value=0.5,
                max_value=3.0,
                value=st.session_state.label_scale,
                step=0.1,
                format="%.1f",
                key="label_scale",
                help="Multiplier for all text labels — node #, member #, values (default 1.0)",
            )
        with c2:
            st.number_input(
                "Label offset",
                min_value=0.5,
                max_value=3.0,
                value=st.session_state.label_offset_scale,
                step=0.1,
                format="%.1f",
                key="label_offset_scale",
                help="Multiplier for label distance from objects (default 1.0)",
            )
        with c3:
            st.number_input(
                "Line thickness",
                min_value=0.5,
                max_value=3.0,
                value=st.session_state.line_thickness_scale,
                step=0.1,
                format="%.1f",
                key="line_thickness_scale",
                help="Multiplier for member and diagram line widths (default 1.0)",
            )

        # --- Canvas ---
        st.markdown("**Canvas**")
        st.checkbox(
            "Dark mode",
            value=st.session_state.canvas_dark_mode,
            key="canvas_dark_mode",
        )

        # --- Save as Defaults ---
        st.divider()
        if st.button("Save as Defaults", help="Save current settings as defaults for new models"):
            save_default_settings()
            st.success("Settings saved as defaults.")


def render_bottom_panel():
    """Render the bottom panel with the active editor or results."""
    editor = st.session_state.active_editor

    if st.session_state.show_results:
        render_results_panel()
    elif editor == "nodes":
        render_editor_nodes()
    elif editor == "members":
        render_editor_members()
    elif editor == "load_supports":
        render_editor_load_supports()
    elif editor == "properties":
        render_editor_properties()
    elif editor == "settings":
        render_settings_panel()
    else:
        st.info("Select an item from the Model Tree to edit, or click **Solve**.")


def render_results_panel():
    """Render result tables in the bottom panel (no metrics bar)."""
    result = st.session_state.solve_result
    if result is None or result.status != "ok":
        st.info("No results available.")
        return

    result_dict = result_to_dict(result)

    # Result tables in expanders
    reactions = result_dict["reactions"]
    member_results = result_dict["member_results"]
    nodes_disp = result_dict["nodes_displaced"]

    with st.expander(f"Reaction Forces ({len(reactions)} supports)", expanded=True):
        if reactions:
            react_df = pd.DataFrame(reactions)
            react_df.columns = ["Node ID", "Rx (kN)", "Ry (kN)", "Mz (kNm)"]
            react_df["Node ID"] = react_df["Node ID"].astype(str)
            sum_row = pd.DataFrame([{
                "Node ID": "Sum",
                "Rx (kN)": react_df["Rx (kN)"].sum(),
                "Ry (kN)": react_df["Ry (kN)"].sum(),
                "Mz (kNm)": react_df["Mz (kNm)"].sum(),
            }])
            react_df = pd.concat([react_df, sum_row], ignore_index=True)
            st.dataframe(react_df, use_container_width=True, hide_index=True)

    with st.expander(f"Element Results ({len(member_results)} members)", expanded=False):
        if member_results:
            mr_df = pd.DataFrame(member_results)
            mr_df.columns = [
                "Member ID", "N_max (kN)", "N_signed (kN)", "V_max (kN)", "M_max (kNm)",
                "Max Disp. (mm)", "M_max loc. (m)", "V_max loc. (m)",
            ]
            st.dataframe(mr_df, use_container_width=True, hide_index=True)

    with st.expander(f"Node Displacements ({len(nodes_disp)} nodes)", expanded=False):
        if nodes_disp:
            nd_df = pd.DataFrame(nodes_disp)
            nd_df.columns = ["Node ID", "dx (mm)", "dy (mm)", "rz (mrad)"]
            st.dataframe(nd_df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Canvas area — unified with overlay toggles
# ---------------------------------------------------------------------------


def render_canvas():
    """Render the main canvas (toggles are in the left column)."""
    has_results = (
        st.session_state.diagram_data is not None
        and st.session_state.solve_result is not None
        and st.session_state.solve_result.status == "ok"
    )

    model = model_from_state()
    if has_model_data():
        fig = build_canvas_figure(
            model,
            diagram_data=st.session_state.diagram_data if has_results else None,
            show_deformed=st.session_state.show_deformed and has_results,
            deform_scale=st.session_state.deform_scale,
            show_moment=st.session_state.show_moment and has_results,
            show_shear=st.session_state.show_shear and has_results,
            show_axial=st.session_state.show_axial and has_results,
            show_node_ids=st.session_state.show_node_ids,
            show_member_ids=st.session_state.show_member_ids,
            show_member_labels_flag=st.session_state.get("show_member_labels", False),
            show_reactions=st.session_state.show_reactions and has_results,
            show_grid=st.session_state.show_grid,
            show_loads=st.session_state.show_loads,
            solve_result=st.session_state.solve_result if has_results else None,
            scale_M=st.session_state.get("diagram_scale_M", 1.0),
            scale_V=st.session_state.get("diagram_scale_V", 1.0),
            scale_N=st.session_state.get("diagram_scale_N", 1.0),
            arrow_scale=st.session_state.get("arrow_scale", 1.0),
            hinge_size=st.session_state.get("hinge_size", 10),
            dark_mode=st.session_state.get("canvas_dark_mode", False),
            label_scale=st.session_state.get("label_scale", 1.0),
            label_offset_scale=st.session_state.get("label_offset_scale", 1.0),
            line_thickness_scale=st.session_state.get("line_thickness_scale", 1.0),
        )
        st.plotly_chart(fig, use_container_width=True, config={
            "scrollZoom": False,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        })
    else:
        st.container(border=True, height=300).markdown(
            "**No model defined yet.**\n\n"
            "Get started:\n"
            "1. Pick a template from the top menu, or\n"
            "2. Click **Nodes** in the model tree to start building"
        )


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout="wide",
    )

    # Reduce default Streamlit top padding
    st.markdown(
        "<style>.block-container{padding-top:2.5rem;}</style>",
        unsafe_allow_html=True,
    )

    init_session_state()

    # Sidebar: File section + model name
    render_sidebar_file()

    # Main layout: tree column + canvas/panel column
    tree_col, main_col = st.columns([1.2, 5])

    with tree_col:
        render_model_tree()

    with main_col:
        render_canvas()
        st.divider()
        render_bottom_panel()


if __name__ == "__main__":
    main()
