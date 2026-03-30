"""
app.py -- Streamlit frontend for member capacity check (strength + buckling).

This file does NOT implement any calculations. All math goes through
buckling_solver.py.

Layout follows section_app conventions:
  - Sidebar: file, presets, settings, display toggles
  - Main area: visualization, input, results, step-by-step

Launch: streamlit run app.py --server.port 8504
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime
from typing import Optional

import plotly.graph_objects as go
import streamlit as st

from buckling_solver import (
    MemberInput,
    MemberCheckResult,
    StrengthResult,
    BucklingAxisResult,
    check_member,
    validate_input,
    buckling_curve_points,
    IMPERFECTION_FACTORS,
    BUCKLING_CURVES,
    MU_VALUES,
    MU_LABELS,
    STEEL_GRADES,
    E_STEEL_MPA,
    GAMMA_M0_DEFAULT,
    GAMMA_M1_DEFAULT,
    SLENDERNESS_THRESHOLD,
    KN_TO_N,
    N_TO_KN,
)
import file_io

EXCHANGE_SECTIONS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "exchange" / "sections"
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE = "Member Capacity Check"
APP_ICON = "\U0001f3cb\ufe0f"  # weight lifter

# Boundary condition options for selectbox
BC_OPTIONS = list(MU_VALUES.keys())
BC_LABELS = [MU_LABELS[k] for k in BC_OPTIONS]

# Colors
COLOR_PASS = "#28a745"
COLOR_FAIL = "#dc3545"
COLOR_WARN = "#ffc107"
COLOR_STRENGTH = "rgba(31, 119, 180, 0.8)"
COLOR_BUCKLING_Y = "rgba(255, 127, 14, 0.8)"
COLOR_BUCKLING_Z = "rgba(44, 160, 44, 0.8)"

CURVE_COLORS = {
    "a0": "#1f77b4",
    "a": "#ff7f0e",
    "b": "#2ca02c",
    "c": "#d62728",
    "d": "#9467bd",
}


# ---------------------------------------------------------------------------
# Page config (MUST be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
)

# ---------------------------------------------------------------------------
# CSS overrides (standard for all modules)
# ---------------------------------------------------------------------------
st.markdown("""<style>
.block-container { padding-top: 2.5rem; }

.stDataFrame {
    width: fit-content !important;
    min-width: 300px;
    max-width: 100%;
}
.stDataFrame > div:last-child {
    width: fit-content !important;
    max-width: 100%;
}

/* Left-align LaTeX */
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
# Helpers
# ---------------------------------------------------------------------------

def _sub(text: str) -> str:
    """Convert 'A_min' to 'A<sub>min</sub>' for HTML display."""
    if "_" in text:
        base, subscript = text.split("_", 1)
        return f"{base}<sub>{subscript}</sub>"
    return text


def _pass_fail_badge(passed: bool) -> str:
    """Return HTML badge for pass/fail."""
    if passed:
        return f'<span style="color:{COLOR_PASS};font-weight:bold;">\u2705 PASS</span>'
    return f'<span style="color:{COLOR_FAIL};font-weight:bold;">\u274c FAIL</span>'


def _utilization_color(util: float) -> str:
    if util <= 0.8:
        return COLOR_PASS
    elif util <= 1.0:
        return COLOR_WARN
    return COLOR_FAIL


def _member_to_data(inp: MemberInput) -> dict:
    """Convert MemberInput to envelope data dict."""
    return {
        "member": {
            "name": inp.name,
            "N_Ed_kN": inp.N_Ed_kN,
            "A_mm2": inp.A_mm2,
            "Iy_mm4": inp.Iy_mm4,
            "Iz_mm4": inp.Iz_mm4,
            "fy_MPa": inp.fy_MPa,
            "E_MPa": inp.E_MPa,
            "L_m": inp.L_m,
            "mu_y": inp.mu_y,
            "mu_z": inp.mu_z,
            "curve_y": inp.curve_y,
            "curve_z": inp.curve_z,
            "gamma_M0": inp.gamma_M0,
            "gamma_M1": inp.gamma_M1,
        }
    }


def _data_to_member(data: dict) -> MemberInput:
    """Convert envelope data dict to MemberInput."""
    m = data["member"]
    return MemberInput(
        name=m.get("name", "Loaded"),
        N_Ed_kN=float(m["N_Ed_kN"]),
        A_mm2=float(m["A_mm2"]),
        Iy_mm4=float(m["Iy_mm4"]),
        Iz_mm4=float(m["Iz_mm4"]),
        fy_MPa=float(m.get("fy_MPa", 235.0)),
        E_MPa=float(m.get("E_MPa", E_STEEL_MPA)),
        L_m=float(m["L_m"]),
        mu_y=float(m.get("mu_y", 1.0)),
        mu_z=float(m.get("mu_z", 1.0)),
        curve_y=str(m.get("curve_y", "b")),
        curve_z=str(m.get("curve_z", "c")),
        gamma_M0=float(m.get("gamma_M0", GAMMA_M0_DEFAULT)),
        gamma_M1=float(m.get("gamma_M1", GAMMA_M1_DEFAULT)),
    )


def _load_exchange_sections() -> list[dict]:
    """List available section results from exchange directory."""
    if not EXCHANGE_SECTIONS_DIR.is_dir():
        return []
    sections = []
    for fp in sorted(EXCHANGE_SECTIONS_DIR.glob("*.json")):
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            # Handle both new envelope and old flat format
            if "sfem" in raw:
                name = raw["sfem"].get("name", fp.stem)
                data = raw.get("data", {})
            else:
                name = raw.get("name", fp.stem)
                data = {"properties": raw.get("properties", {})}
            sections.append({"name": name, "path": fp, "data": data})
        except Exception:
            continue
    return sections


# Widget keys that must be cleared when member_input changes externally
# (preset, import, file load) so widgets re-read from session state.
_INPUT_WIDGET_KEYS = [
    "inp_name", "inp_NEd", "inp_L", "inp_A", "inp_Iy", "inp_Iz",
    "inp_E", "inp_gM0", "inp_gM1", "inp_bc_y", "inp_bc_z",
    "inp_curve_y", "inp_curve_z", "inp_steel",
]


def _sync_widget_keys(mi: "MemberInput"):
    """Write member_input values into widget keys so widgets show updated values.

    No calculations here — just copying dataclass fields into Streamlit widget keys
    so the UI reflects the new member_input after preset/import/load.
    """
    st.session_state["inp_name"] = mi.name
    st.session_state["inp_NEd"] = mi.N_Ed_kN
    st.session_state["inp_L"] = mi.L_m
    st.session_state["inp_A"] = mi.A_mm2
    st.session_state["inp_Iy"] = mi.Iy_mm4
    st.session_state["inp_Iz"] = mi.Iz_mm4
    st.session_state["inp_E"] = mi.E_MPa
    st.session_state["inp_gM0"] = mi.gamma_M0
    st.session_state["inp_gM1"] = mi.gamma_M1
    # Selectboxes: find matching label for the mu value
    for bc_key, mu_val in [("inp_bc_y", mi.mu_y), ("inp_bc_z", mi.mu_z)]:
        for i, opt in enumerate(BC_OPTIONS):
            if abs(MU_VALUES[opt] - mu_val) < 0.01:
                st.session_state[bc_key] = BC_LABELS[i]
                break
    st.session_state["inp_curve_y"] = mi.curve_y
    st.session_state["inp_curve_z"] = mi.curve_z
    # Steel grade: find matching grade name for fy value
    for gname, gfy in STEEL_GRADES.items():
        if abs(gfy - mi.fy_MPa) < 0.1:
            st.session_state["inp_steel"] = gname
            break


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "member_input" not in st.session_state:
    _tpls = file_io.load_template_list()
    if _tpls:
        _sfem, _data, _ = file_io.load_template(_tpls[0]["path"])
        default = _data_to_member(_data)
        st.session_state.member_name = _sfem.get("name", default.name)
    else:
        default = MemberInput()
        st.session_state.member_name = default.name
    st.session_state.member_input = default
    _sync_widget_keys(default)
if "member_name" not in st.session_state:
    st.session_state.member_name = st.session_state.member_input.name
if "show_all_curves" not in st.session_state:
    st.session_state.show_all_curves = True
if "show_step_by_step" not in st.session_state:
    st.session_state.show_step_by_step = True


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    # --- File section ---
    with st.expander("File", expanded=False):
        # ── New ──
        if st.button("New Member", use_container_width=True):
            st.session_state.member_input = MemberInput()
            st.session_state.member_name = ""
            _sync_widget_keys(st.session_state.member_input)
            st.rerun()

        st.markdown("---")

        # ── Load ──
        st.caption("Load")
        # Compact file uploader (button-only, no dropzone)
        st.markdown(
            "<style>"
            "[data-testid='stFileUploaderDropzone'] > div {"
            "  display: none !important;}"
            "[data-testid='stFileUploaderDropzone'] {"
            "  border: none !important;"
            "  padding: 0 !important;"
            "  min-height: 0 !important;}"
            "[data-testid='stFileUploaderDropzone'] span {"
            "  width: 100%;}"
            "[data-testid='stFileUploaderDropzone'] span button {"
            "  width: 100%;"
            "  border-radius: 0.5rem;}"
            "</style>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Browse",
            type=["json"],
            key="buckling_uploader",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            fid = uploaded.file_id
            if fid != st.session_state.get("_last_upload_id"):
                st.session_state._last_upload_id = fid
                try:
                    raw = file_io.deserialize(uploaded.read().decode("utf-8"))
                    sfem, data, _ = file_io.parse_envelope(raw)
                    inp = _data_to_member(data)
                    st.session_state.member_input = inp
                    st.session_state.member_name = sfem.get("name", inp.name)
                    _sync_widget_keys(st.session_state.member_input)
                    st.success(f"Loaded: {inp.name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load: {e}")

        # Import Section (from exchange) — simple button list
        with st.expander("Import Section"):
            exchange_sections = _load_exchange_sections()
            if exchange_sections:
                for idx, sec in enumerate(exchange_sections):
                    if st.button(sec["name"], key=f"imp_{idx}",
                                 use_container_width=True):
                        props = sec["data"].get("properties", sec["data"])
                        current = st.session_state.member_input
                        st.session_state.member_input = MemberInput(
                            name=sec["name"],
                            N_Ed_kN=current.N_Ed_kN,
                            A_mm2=props["A_mm2"],
                            Iy_mm4=props["Iy_mm4"],
                            Iz_mm4=props["Iz_mm4"],
                            fy_MPa=current.fy_MPa,
                            E_MPa=current.E_MPa,
                            L_m=current.L_m,
                            mu_y=current.mu_y,
                            mu_z=current.mu_z,
                            curve_y=current.curve_y,
                            curve_z=current.curve_z,
                            gamma_M0=current.gamma_M0,
                            gamma_M1=current.gamma_M1,
                        )
                        st.session_state.member_name = sec["name"]
                        _sync_widget_keys(st.session_state.member_input)
                        st.rerun()
            else:
                st.caption("No sections in exchange/.")

        # Templates
        with st.expander("Templates"):
            templates = file_io.load_template_list()
            if templates:
                for idx, tpl in enumerate(templates):
                    if st.button(tpl["name"], key=f"tpl_{idx}", use_container_width=True):
                        _sfem, _data, _ = file_io.load_template(tpl["path"])
                        st.session_state.member_input = _data_to_member(_data)
                        st.session_state.member_name = tpl["name"]
                        _sync_widget_keys(st.session_state.member_input)
                        st.rerun()
            else:
                st.caption("No templates found.")

        st.markdown("---")

        # ── Save ──
        st.caption("Save")
        inp = st.session_state.member_input
        name = st.session_state.get("member_name", inp.name)
        model_data = _member_to_data(inp)
        envelope = file_io.make_model_envelope(name or "member", model_data)

        # Save Template
        if st.button("Save Template", use_container_width=True,
                      help="Save member to templates for reuse"):
            if not name.strip():
                st.error("Enter a member name first.")
            else:
                try:
                    path = file_io.save_template(envelope, name)
                    st.success(f"Saved template: {path.name}")
                except Exception as e:
                    st.error(f"Save failed: {e}")

        # Save Case (to saves/ folder)
        if st.button("Save Case", use_container_width=True,
                      help="Save case file to saves/ folder"):
            if not name.strip():
                st.error("Enter a member name first.")
            else:
                try:
                    path = file_io.save_case(envelope, name)
                    st.success(f"Saved: {path.name}")
                except Exception as e:
                    st.error(f"Save failed: {e}")

    # Member name
    st.session_state.member_name = st.text_input(
        "Member name",
        value=st.session_state.get("member_name", ""),
        label_visibility="collapsed",
        placeholder="Member name",
    )

    st.divider()

    # Display toggles
    st.header("Display")
    st.session_state.show_all_curves = st.checkbox(
        "Show all buckling curves",
        value=st.session_state.show_all_curves,
        key="chk_all_curves",
    )
    st.session_state.show_step_by_step = st.checkbox(
        "Show step-by-step calculation",
        value=st.session_state.show_step_by_step,
        key="chk_step_by_step",
    )


# ---------------------------------------------------------------------------
# Input section
# ---------------------------------------------------------------------------

inp = st.session_state.member_input

with st.expander("Member Input", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Force & Geometry**")
        new_name = st.text_input("Member name", key="inp_name")
        new_N_Ed = st.number_input(
            "N_Ed (kN)", step=10.0, format="%.1f",
            help="Design axial force. Positive = tension, negative = compression.",
            key="inp_NEd",
        )
        new_L = st.number_input(
            "L (m)", min_value=0.01, step=0.5, format="%.2f",
            help="Member geometric length.",
            key="inp_L",
        )

        st.markdown("**Boundary Conditions**")
        new_bc_y = st.selectbox(
            "\u03bcy (y-axis)", BC_LABELS, key="inp_bc_y",
        )
        new_mu_y = MU_VALUES[BC_OPTIONS[BC_LABELS.index(new_bc_y)]]

        new_bc_z = st.selectbox(
            "\u03bcz (z-axis)", BC_LABELS, key="inp_bc_z",
        )
        new_mu_z = MU_VALUES[BC_OPTIONS[BC_LABELS.index(new_bc_z)]]

    with col2:
        st.markdown("**Section Properties**")
        new_A = st.number_input(
            "A (mm\u00b2)", min_value=1.0, step=100.0, format="%.1f",
            help="Cross-section area.",
            key="inp_A",
        )
        new_Iy = st.number_input(
            "Iy (mm\u2074)", min_value=1.0, step=100_000.0, format="%.0f",
            help="Moment of inertia about y-axis.",
            key="inp_Iy",
        )
        new_Iz = st.number_input(
            "Iz (mm\u2074)", min_value=1.0, step=100_000.0, format="%.0f",
            help="Moment of inertia about z-axis.",
            key="inp_Iz",
        )

        st.markdown("**Material & Safety**")
        steel_names = list(STEEL_GRADES.keys())
        new_steel = st.selectbox(
            "Steel grade", steel_names, key="inp_steel",
            placeholder="Select grade...",
        )
        new_fy = STEEL_GRADES[new_steel] if new_steel else inp.fy_MPa

        new_E = st.number_input(
            "E (MPa)", min_value=1000.0, step=10000.0, format="%.0f",
            key="inp_E",
        )
        c1, c2 = st.columns(2)
        with c1:
            new_gamma_M0 = st.number_input(
                "\u03b3M0", min_value=0.1, step=0.05, format="%.2f",
                key="inp_gM0",
            )
        with c2:
            new_gamma_M1 = st.number_input(
                "\u03b3M1", min_value=0.1, step=0.05, format="%.2f",
                key="inp_gM1",
            )

        st.markdown("**Buckling Curves**")
        new_curve_y = st.selectbox(
            "Curve y-axis", BUCKLING_CURVES, key="inp_curve_y",
            help="Buckling curve for y-axis bending.",
        )
        new_curve_z = st.selectbox(
            "Curve z-axis", BUCKLING_CURVES, key="inp_curve_z",
            help="Buckling curve for z-axis bending.",
        )

    # Imperfection factor reference table
    with st.expander("Imperfection factor reference (EN 1993-1-1 Table 6.1)"):
        ref_cols = st.columns(5)
        for i, (curve, alpha) in enumerate(IMPERFECTION_FACTORS.items()):
            with ref_cols[i]:
                st.metric(f"Curve {curve}", f"\u03b1 = {alpha}")

# Build updated MemberInput from form values
new_inp = MemberInput(
    name=new_name,
    N_Ed_kN=new_N_Ed,
    A_mm2=new_A,
    Iy_mm4=new_Iy,
    Iz_mm4=new_Iz,
    fy_MPa=new_fy,
    E_MPa=new_E,
    L_m=new_L,
    mu_y=new_mu_y,
    mu_z=new_mu_z,
    curve_y=new_curve_y,
    curve_z=new_curve_z,
    gamma_M0=new_gamma_M0,
    gamma_M1=new_gamma_M1,
)
st.session_state.member_input = new_inp
inp = new_inp

# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

result: Optional[MemberCheckResult] = None
error_msg: Optional[str] = None

try:
    validation_error = validate_input(inp)
    if validation_error:
        error_msg = validation_error
    else:
        result = check_member(inp)
except Exception as e:
    error_msg = f"Calculation error: {e}"

if error_msg:
    st.error(error_msg)

st.divider()

# ---------------------------------------------------------------------------
# Visualization: Buckling curves plot
# ---------------------------------------------------------------------------

if result is not None:
    is_compression = inp.N_Ed_kN < 0

    if is_compression and result.buckling_y is not None:
        fig = go.Figure()

        # Plot reference curves
        if st.session_state.show_all_curves:
            for curve_name in BUCKLING_CURVES:
                lambdas, chis = buckling_curve_points(curve_name)
                is_active = (curve_name == result.buckling_y.curve
                             or curve_name == result.buckling_z.curve)
                fig.add_trace(go.Scatter(
                    x=lambdas, y=chis,
                    mode="lines",
                    line=dict(
                        color=CURVE_COLORS.get(curve_name, "gray"),
                        width=3 if is_active else 1.5,
                        dash="solid" if is_active else "dot",
                    ),
                    name=f"Curve {curve_name} (\u03b1={IMPERFECTION_FACTORS[curve_name]})",
                    hovertemplate=f"Curve {curve_name}<br>\u03bb\u0304 = %{{x:.2f}}<br>\u03c7 = %{{y:.3f}}<extra></extra>",
                ))
        else:
            # Only show active curves
            shown = set()
            for bax in (result.buckling_y, result.buckling_z):
                if bax and bax.curve not in shown:
                    shown.add(bax.curve)
                    lambdas, chis = buckling_curve_points(bax.curve)
                    fig.add_trace(go.Scatter(
                        x=lambdas, y=chis,
                        mode="lines",
                        line=dict(color=CURVE_COLORS.get(bax.curve, "gray"), width=3),
                        name=f"Curve {bax.curve} (\u03b1={IMPERFECTION_FACTORS[bax.curve]})",
                    ))

        # Plot current member points
        if result.buckling_y:
            by = result.buckling_y
            fig.add_trace(go.Scatter(
                x=[by.lambda_bar], y=[by.chi],
                mode="markers+text",
                marker=dict(size=14, color=COLOR_BUCKLING_Y, symbol="circle",
                            line=dict(width=2, color="white")),
                text=[f"y: \u03c7={by.chi:.3f}"],
                textposition="top right",
                textfont=dict(size=13, color=COLOR_BUCKLING_Y),
                name=f"Member (y-axis): \u03bb\u0304={by.lambda_bar:.2f}, \u03c7={by.chi:.3f}",
                hovertemplate=(
                    f"<b>y-axis</b><br>"
                    f"\u03bb\u0304 = {by.lambda_bar:.3f}<br>"
                    f"\u03c7 = {by.chi:.3f}<br>"
                    f"Curve {by.curve}<br>"
                    f"N<sub>b,Rd</sub> = {by.N_b_Rd_kN:.1f} kN<br>"
                    f"Utilization = {by.utilization * 100:.1f}%<extra></extra>"
                ),
            ))

        if result.buckling_z and result.buckling_z.curve != result.buckling_y.curve or \
           (result.buckling_z and abs(result.buckling_z.lambda_bar - result.buckling_y.lambda_bar) > 0.01):
            bz = result.buckling_z
            fig.add_trace(go.Scatter(
                x=[bz.lambda_bar], y=[bz.chi],
                mode="markers+text",
                marker=dict(size=14, color=COLOR_BUCKLING_Z, symbol="diamond",
                            line=dict(width=2, color="white")),
                text=[f"z: \u03c7={bz.chi:.3f}"],
                textposition="bottom right",
                textfont=dict(size=13, color=COLOR_BUCKLING_Z),
                name=f"Member (z-axis): \u03bb\u0304={bz.lambda_bar:.2f}, \u03c7={bz.chi:.3f}",
                hovertemplate=(
                    f"<b>z-axis</b><br>"
                    f"\u03bb\u0304 = {bz.lambda_bar:.3f}<br>"
                    f"\u03c7 = {bz.chi:.3f}<br>"
                    f"Curve {bz.curve}<br>"
                    f"N<sub>b,Rd</sub> = {bz.N_b_Rd_kN:.1f} kN<br>"
                    f"Utilization = {bz.utilization * 100:.1f}%<extra></extra>"
                ),
            ))

        # Threshold line at lambda = 0.2
        fig.add_vline(x=SLENDERNESS_THRESHOLD, line=dict(color="gray", width=1, dash="dash"))
        fig.add_annotation(
            x=SLENDERNESS_THRESHOLD, y=1.02, text=f"\u03bb\u0304 = {SLENDERNESS_THRESHOLD}",
            showarrow=False, font=dict(size=11, color="gray"), yanchor="bottom",
        )

        fig.update_layout(
            xaxis=dict(
                title="\u03bb\u0304 (relative slenderness)",
                range=[0, 3.2],
                showgrid=True, gridcolor="rgba(200,200,200,0.3)",
            ),
            yaxis=dict(
                title="\u03c7 (reduction factor)",
                range=[0, 1.1],
                showgrid=True, gridcolor="rgba(200,200,200,0.3)",
            ),
            showlegend=True,
            legend=dict(
                orientation="v", yanchor="top", y=0.99,
                xanchor="right", x=0.99,
                bgcolor="rgba(255,255,255,0.8)",
                font=dict(size=12),
            ),
            margin=dict(l=60, r=20, t=30, b=60),
            width=800,
            height=500,
            plot_bgcolor="white",
        )

        st.plotly_chart(fig, use_container_width=False, config={
            "scrollZoom": False,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        })

    st.divider()

    # -------------------------------------------------------------------
    # Results summary
    # -------------------------------------------------------------------

    st.subheader("Results Summary")

    # Force direction
    if result.strength.is_tension:
        st.info(f"**N_Ed = {inp.N_Ed_kN:+.1f} kN** \u2192 Member is in **TENSION**. Only strength check required.")
    else:
        st.info(f"**N_Ed = {inp.N_Ed_kN:+.1f} kN** \u2192 Member is in **COMPRESSION**. Strength + buckling checks required.")

    # Utilization summary
    lines = []

    # Strength
    sr = result.strength
    util_color = _utilization_color(sr.utilization)
    lines.append(
        f"<b>Strength check</b>: N<sub>Rd</sub> = {sr.N_Rd_kN:,.1f} kN, "
        f"utilization = <span style='color:{util_color};font-weight:bold;'>"
        f"{sr.utilization * 100:.1f}%</span> {_pass_fail_badge(sr.passed)}"
    )

    # Buckling y
    if result.buckling_y:
        by = result.buckling_y
        util_color = _utilization_color(by.utilization)
        skip_note = " (skip: \u03bb\u0304 \u2264 0.2)" if by.skip_buckling else ""
        lines.append(
            f"<b>Buckling y-axis</b>: \u03c7<sub>y</sub> = {by.chi:.3f}, "
            f"N<sub>b,Rd,y</sub> = {by.N_b_Rd_kN:,.1f} kN, "
            f"utilization = <span style='color:{util_color};font-weight:bold;'>"
            f"{by.utilization * 100:.1f}%</span> {_pass_fail_badge(by.passed)}{skip_note}"
        )

    # Buckling z
    if result.buckling_z:
        bz = result.buckling_z
        util_color = _utilization_color(bz.utilization)
        skip_note = " (skip: \u03bb\u0304 \u2264 0.2)" if bz.skip_buckling else ""
        lines.append(
            f"<b>Buckling z-axis</b>: \u03c7<sub>z</sub> = {bz.chi:.3f}, "
            f"N<sub>b,Rd,z</sub> = {bz.N_b_Rd_kN:,.1f} kN, "
            f"utilization = <span style='color:{util_color};font-weight:bold;'>"
            f"{bz.utilization * 100:.1f}%</span> {_pass_fail_badge(bz.passed)}{skip_note}"
        )

    # Governing
    gov_color = _utilization_color(result.governing_utilization)
    gov_label = result.governing_check.replace("_", " ")
    lines.append(
        f"<br><b>Governing check</b>: <b>{gov_label}</b>, "
        f"utilization = <span style='color:{gov_color};font-weight:bold;font-size:1.1em;'>"
        f"{result.governing_utilization * 100:.1f}%</span> "
        f"{_pass_fail_badge(result.overall_passed)}"
    )

    st.markdown(
        '<div style="line-height:2.0; font-size:0.95em;">'
        + "<br>".join(lines)
        + '</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # -------------------------------------------------------------------
    # Step-by-step calculation
    # -------------------------------------------------------------------

    if st.session_state.show_step_by_step:
        st.subheader("Step-by-step Calculation")

        # --- Strength check ---
        st.markdown("### Strength Check (EN 1993-1-1)")
        sr = result.strength

        force_type = "tension" if sr.is_tension else "compression"
        st.markdown(f"**Force direction**: N_Ed = {inp.N_Ed_kN:+.1f} kN \u2192 **{force_type}**")

        st.markdown("**Method 1: Force comparison**")
        st.latex(
            r"N_{Rd} = \frac{A \cdot f_y}{\gamma_{M0}} = "
            r"\frac{" + f"{inp.A_mm2:.0f}" + r" \cdot " + f"{inp.fy_MPa:.0f}" + r"}{" + f"{inp.gamma_M0:.2f}" + r"} = "
            + f"{sr.N_Rd_kN * KN_TO_N:,.0f}" + r" \text{ N} = " + f"{sr.N_Rd_kN:,.1f}" + r" \text{ kN}"
        )
        check_sym = r"\leq" if sr.force_ok else r">"
        st.latex(
            r"|N_{Ed}| = " + f"{sr.N_Ed_kN:,.1f}" + r" \text{{ kN}} {check} N_{{Rd}} = {nrd:,.1f} \text{{ kN}} \quad \rightarrow \text{{ {verdict}}}".format(
                check=check_sym, nrd=sr.N_Rd_kN, verdict="OK!" if sr.force_ok else "FAIL",
            )
        )
        st.latex(
            r"\text{Utilization: } \frac{|N_{Ed}|}{N_{Rd}} = \frac{"
            + f"{sr.N_Ed_kN:,.1f}" + r"}{" + f"{sr.N_Rd_kN:,.1f}" + r"} = "
            + f"{sr.utilization * 100:.1f}" + r"\%"
        )

        st.markdown("**Method 2: Stress comparison**")
        st.latex(
            r"\sigma_{Ed} = \frac{|N_{Ed}|}{A} = \frac{"
            + f"{sr.N_Ed_kN * KN_TO_N:,.0f}" + r"}{" + f"{inp.A_mm2:.0f}" + r"} = "
            + f"{sr.sigma_Ed_MPa:.1f}" + r" \text{ MPa}"
        )
        check_sym = r"\leq" if sr.stress_ok else r">"
        st.latex(
            r"\sigma_{Ed} = " + f"{sr.sigma_Ed_MPa:.1f}"
            + r" \text{{ MPa}} {check} \frac{{f_y}}{{\gamma_{{M0}}}} = {srd:.1f} \text{{ MPa}} \quad \rightarrow \text{{ {verdict}}}".format(
                check=check_sym, srd=sr.sigma_Rd_MPa, verdict="OK!" if sr.stress_ok else "FAIL",
            )
        )

        st.markdown("**Method 3: Area comparison**")
        st.latex(
            r"A_{min} = \frac{|N_{Ed}| \cdot \gamma_{M0}}{f_y} = \frac{"
            + f"{sr.N_Ed_kN * KN_TO_N:,.0f}" + r" \cdot " + f"{inp.gamma_M0:.2f}" + r"}{" + f"{inp.fy_MPa:.0f}" + r"} = "
            + f"{sr.A_min_mm2:,.1f}" + r" \text{ mm}^2"
        )
        check_sym = r"\geq" if sr.area_ok else r"<"
        st.latex(
            r"A = " + f"{inp.A_mm2:,.1f}"
            + r" \text{{ mm}}^2 {check} A_{{min}} = {amin:,.1f} \text{{ mm}}^2 \quad \rightarrow \text{{ {verdict}}}".format(
                check=check_sym, amin=sr.A_min_mm2, verdict="OK!" if sr.area_ok else "FAIL",
            )
        )

        # --- Buckling check ---
        if is_compression:
            for bax in (result.buckling_y, result.buckling_z):
                if bax is None:
                    continue

                st.markdown(f"### Buckling Check -- {bax.axis_label}-axis (EN 1993-1-1 cl. 6.3.1)")

                st.markdown(f"**Step 1: Effective length**")
                st.latex(
                    r"L_{cr," + bax.axis_label + r"} = \mu_{" + bax.axis_label + r"} \cdot L = "
                    + f"{bax.mu:.1f}" + r" \cdot " + f"{bax.L_m:.2f}" + r" = "
                    + f"{bax.L_cr_m:.2f}" + r" \text{ m} = " + f"{bax.L_cr_mm:.0f}" + r" \text{ mm}"
                )

                st.markdown(f"**Step 2: Radius of gyration**")
                st.latex(
                    r"i_{" + bax.axis_label + r"} = \sqrt{\frac{I_{" + bax.axis_label + r"}}{A}} = \sqrt{\frac{"
                    + f"{bax.I_mm4:,.0f}" + r"}{" + f"{inp.A_mm2:.0f}" + r"}} = "
                    + f"{bax.i_mm:.1f}" + r" \text{ mm}"
                )

                st.markdown(f"**Step 3: Characteristic compressive resistance**")
                st.latex(
                    r"N_{Rk} = A \cdot f_y = " + f"{inp.A_mm2:.0f}" + r" \cdot " + f"{inp.fy_MPa:.0f}"
                    + r" = " + f"{bax.N_Rk_kN * KN_TO_N:,.0f}" + r" \text{ N} = " + f"{bax.N_Rk_kN:,.1f}" + r" \text{ kN}"
                )

                st.markdown(f"**Step 4: Euler critical force**")
                st.latex(
                    r"N_{cr," + bax.axis_label + r"} = \frac{\pi^2 \cdot E \cdot I_{" + bax.axis_label + r"}}{L_{cr," + bax.axis_label + r"}^2} = "
                    r"\frac{\pi^2 \cdot " + f"{inp.E_MPa:,.0f}" + r" \cdot " + f"{bax.I_mm4:,.0f}" + r"}{" + f"{bax.L_cr_mm:.0f}" + r"^2} = "
                    + f"{bax.N_cr_kN * KN_TO_N:,.0f}" + r" \text{ N} = " + f"{bax.N_cr_kN:,.1f}" + r" \text{ kN}"
                )

                st.markdown(f"**Step 5: Relative slenderness**")
                st.latex(
                    r"\bar{\lambda}_{" + bax.axis_label + r"} = \sqrt{\frac{N_{Rk}}{N_{cr," + bax.axis_label + r"}}} = "
                    r"\sqrt{\frac{" + f"{bax.N_Rk_kN:,.1f}" + r"}{" + f"{bax.N_cr_kN:,.1f}" + r"}} = "
                    + f"{bax.lambda_bar:.3f}"
                )

                if bax.skip_buckling:
                    st.success(
                        f"\u03bb\u0304 = {bax.lambda_bar:.3f} \u2264 {SLENDERNESS_THRESHOLD} "
                        f"\u2192 Buckling check may be skipped (member is stocky). "
                        f"Continuing for educational purposes."
                    )

                st.markdown(f"**Step 6: Buckling curve selection**")
                st.latex(
                    r"\text{Buckling curve: }" + f'\\text{{"{bax.curve}"}}' + r" \quad \rightarrow \quad "
                    r"\alpha = " + f"{bax.alpha}"
                )

                st.markdown(f"**Step 7: Intermediate factor \u03a6**")
                st.latex(
                    r"\Phi_{" + bax.axis_label + r"} = 0.5 \cdot \left[1 + \alpha \cdot (\bar{\lambda} - 0.2) + \bar{\lambda}^2\right]"
                )
                st.latex(
                    r"\Phi_{" + bax.axis_label + r"} = 0.5 \cdot \left[1 + " + f"{bax.alpha}" + r" \cdot ("
                    + f"{bax.lambda_bar:.3f}" + r" - 0.2) + " + f"{bax.lambda_bar:.3f}" + r"^2\right] = "
                    + f"{bax.Phi:.3f}"
                )

                st.markdown(f"**Step 8: Reduction factor \u03c7**")
                st.latex(
                    r"\chi_{" + bax.axis_label + r"} = \frac{1}{\Phi + \sqrt{\Phi^2 - \bar{\lambda}^2}} = "
                    r"\frac{1}{" + f"{bax.Phi:.3f}" + r" + \sqrt{" + f"{bax.Phi:.3f}" + r"^2 - "
                    + f"{bax.lambda_bar:.3f}" + r"^2}} = " + f"{bax.chi:.3f}"
                )

                st.markdown(f"**Step 9: Design buckling resistance**")
                st.latex(
                    r"N_{b,Rd," + bax.axis_label + r"} = \frac{\chi_{" + bax.axis_label + r"} \cdot A \cdot f_y}{\gamma_{M1}} = "
                    r"\frac{" + f"{bax.chi:.3f}" + r" \cdot " + f"{inp.A_mm2:.0f}" + r" \cdot " + f"{inp.fy_MPa:.0f}" + r"}{" + f"{inp.gamma_M1:.2f}" + r"} = "
                    + f"{bax.N_b_Rd_kN * KN_TO_N:,.0f}" + r" \text{ N} = " + f"{bax.N_b_Rd_kN:,.1f}" + r" \text{ kN}"
                )

                st.markdown(f"**Step 10: Verification**")
                check_sym = r"\leq" if bax.passed else r">"
                st.latex(
                    r"|N_{Ed}| = " + f"{bax.N_Ed_kN:,.1f}" + r" \text{{ kN}} {check} N_{{b,Rd,{ax}}} = {nbrd:,.1f} \text{{ kN}} \quad \rightarrow \text{{ {verdict}}}".format(
                        check=check_sym, ax=bax.axis_label, nbrd=bax.N_b_Rd_kN,
                        verdict="OK!" if bax.passed else "FAIL",
                    )
                )
                st.latex(
                    r"\text{Utilization: } \frac{|N_{Ed}|}{N_{b,Rd," + bax.axis_label + r"}} = \frac{"
                    + f"{bax.N_Ed_kN:,.1f}" + r"}{" + f"{bax.N_b_Rd_kN:,.1f}" + r"} = "
                    + f"{bax.utilization * 100:.1f}" + r"\%"
                )

        # --- Conclusion ---
        st.markdown("### Conclusion")
        gov_label = result.governing_check.replace("_", " ")
        if result.overall_passed:
            st.success(
                f"**Member passes all checks.** "
                f"Governing: {gov_label} at {result.governing_utilization * 100:.1f}% utilization."
            )
        else:
            st.error(
                f"**Member FAILS.** "
                f"Governing: {gov_label} at {result.governing_utilization * 100:.1f}% utilization."
            )
