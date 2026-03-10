# SFEM — 2D FEM Web App

## Project Structure
- `fem_app/app.py` — Streamlit frontend (RFEM-style layout), port 8501
- `fem_app/solver.py` — anastruct wrapper, single source of truth for FEM
- `fem_app/api.py` — FastAPI backend, port 8502
- `fem_app/presets.py` — preset/template models
- `fem_app/library.py` — material/section library loader
- `fem_app/library/` — JSON data files (materials, HEA/HEB/IPE sections)
- `fem_app/templates/` — .fem.yaml template files
- `fem_app/settings.json` — user-default display settings
- `fem_app/tests/` — pytest tests (79 analytical + robustness)

## Key Commands
```bash
# Run the app
streamlit run fem_app/app.py --server.port 8501

# Run tests
pytest fem_app/tests/ -x -q

# Install dependencies
pip install -r fem_app/requirements.txt
```

## Architecture Rules
- **solver.py** is the ONLY file that imports anastruct
- **app.py** does NOT import anastruct directly
- Data model v2: MaterialDef, CrossSectionDef, MemberDef, HingeDef, LoadDef
- Truss behavior via hinges (both ends released), not element_type

## Sign Conventions
- anastruct `invert_y_loads=True`: positive Fy in `point_load()` = downward
- Our loads: negative magnitude = downward force
- Solver negates Fy before passing to anastruct
- Multiple UDLs on same member: combined via `q_perp` parameter (not separate `q_load` calls — they overwrite!)
- Reactions: `node.Fy` from anastruct gives correct upward reaction directly

## Settings Persistence
- Two-tier: user defaults in `fem_app/settings.json` + per-model in `.fem.yaml`
- All 10 display settings: deform_scale, diagram_scale_M/V/N, arrow_scale, hinge_size, canvas_dark_mode, label_scale, label_offset_scale, line_thickness_scale

## Known Constraints
- `el.node_1.vertex` returns wrong coords after solve — use `el.vertex_1`/`el.vertex_2`
- `st.data_editor` empty rows cause TypeError — skip rows with None IDs
- Reactions "Sum" row: cast Node ID to str before concat (pyarrow error)
- anastruct `q_load()` overwrites previous calls on same element — use `q_perp` param for combined loads
