"""
app.py — Hub / launcher for the SFEM educational platform.

Auto-discovers modules by scanning sibling directories for module.json files.
Displays each module as a clickable card that opens in a new browser tab.

Launch: streamlit run hub/app.py --server.port 8500
"""

from __future__ import annotations

import json
import pathlib

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SFEM Educational Platform",
    page_icon="\U0001f393",  # graduation cap
    layout="centered",
)

st.title("\U0001f393 SFEM Educational Platform")
st.markdown("Structural Engineering Educational Tools")
st.divider()

# ---------------------------------------------------------------------------
# Discover modules
# ---------------------------------------------------------------------------

HUB_DIR = pathlib.Path(__file__).parent
PROJECT_ROOT = HUB_DIR.parent

modules = []
for child in sorted(PROJECT_ROOT.iterdir()):
    module_json = child / "module.json"
    if child.is_dir() and module_json.exists():
        try:
            data = json.loads(module_json.read_text(encoding="utf-8"))
            data["dir"] = child.name
            modules.append(data)
        except (json.JSONDecodeError, KeyError):
            pass

# ---------------------------------------------------------------------------
# Display module cards
# ---------------------------------------------------------------------------

if not modules:
    st.warning("No modules found. Add a module.json file to a module directory.")
else:
    cols = st.columns(min(len(modules), 3))

    for i, mod in enumerate(modules):
        col = cols[i % len(cols)]
        with col:
            icon = mod.get("icon", "\U0001f4e6")
            name = mod.get("name", mod["dir"])
            port = mod.get("port", "?")
            desc = mod.get("description", "")

            st.markdown(f"### {icon} {name}")
            st.caption(desc)
            st.markdown(
                f'<a href="http://localhost:{port}" target="_blank">'
                f'<button style="width:100%;padding:8px 16px;font-size:16px;'
                f'cursor:pointer;border-radius:4px;border:1px solid #ccc;'
                f'background:#f0f2f6;">Open (port {port})</button></a>',
                unsafe_allow_html=True,
            )
            st.markdown("")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Each module runs as an independent Streamlit app. "
    "Use run_all.bat to start all modules together."
)
