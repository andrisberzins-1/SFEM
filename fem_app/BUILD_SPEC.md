# Claude Code Prompt: 2D FEM Web Application
---

## PROJECT OVERVIEW

Build a locally-run web application for 2D structural FEM analysis.
Primary audience: bachelor-level structural engineering students 
verifying hand calculations.
Secondary use: quick analysis tool for teaching and demonstration.

All code must be production-quality, well-commented, and maintainable
by someone with basic Python knowledge.

---

## TASK LIST — WORK THROUGH IN ORDER

Complete each task fully and confirm it works before starting the next.
State clearly when each task is complete and what was built.

### PHASE 1 — Core Solver (no UI)
- [ ] Task 1: Create project file structure
- [ ] Task 2: Build solver.py — anastruct wrapper with all element types
- [ ] Task 3: Build presets.py — all 6 preset model definitions
- [ ] Task 4: Build solve_file.py — CLI file-based solver
- [ ] Task 5: Write tests/test_analytical.py and verify all pass
- [ ] Task 6: Write tests/test_robustness.py edge case tests

**CHECKPOINT 1: python solve_file.py works on all presets, all analytical tests pass**

### PHASE 2 — REST API
- [ ] Task 7: Build api.py — FastAPI with all endpoints
- [ ] Task 8: Build run.sh to launch both servers
- [ ] Task 9: Write tests/test_api.py and verify all pass

**CHECKPOINT 2: All API endpoints return correct results, error cases handled**

### PHASE 3 — Streamlit UI (tables only, no canvas)
- [ ] Task 10: Build app.py — layout, sidebar, session state structure
- [ ] Task 11: Add node, member, support, load input tables
- [ ] Task 12: Add solve button and reaction forces table
- [ ] Task 13: Add Plotly result diagrams (all 4 diagram types)
- [ ] Task 14: Add save/load YAML functionality

**CHECKPOINT 3: Full working app without canvas — test all presets, save/load round-trip**

### PHASE 4 — Canvas
- [ ] Task 15: Add Plotly canvas showing model (display only, no interaction)
- [ ] Task 16: Add canvas click interaction — place nodes, assign members
- [ ] Task 17: Add canvas support and load assignment by clicking
- [ ] Task 18: Synchronise canvas ↔ tables bidirectionally

**CHECKPOINT 4: Full app — test canvas workflow end to end**

### PHASE 5 — Polish and testing
- [ ] Task 19: Write tests/test_ui.py (Playwright)
- [ ] Task 20: Final review — error messages, unit labels, helper text, README

**CHECKPOINT 5: All tests pass, README complete**

---

## TECHNOLOGY STACK

- Web framework: Streamlit (port 8501)
- REST API: FastAPI + Uvicorn (port 8502)
- FEM solver backend: anastruct
- Visualisation: Plotly (all diagrams and canvas)
- Input tables: pandas DataFrames with st.data_editor
- File format: YAML (.fem.yaml)
- Testing: pytest, requests, playwright
- Launch: single run.sh script starts both servers

All dependencies installable with pip.
Provide requirements.txt and README.md.

---

## FILE STRUCTURE

```
fem_app/
├── app.py              # Streamlit frontend
├── api.py              # FastAPI REST API
├── solver.py           # anastruct wrapper — single source of truth
├── presets.py          # all preset model definitions
├── solve_file.py       # CLI file-based solver
├── requirements.txt
├── run.sh              # launches Streamlit + FastAPI together
├── README.md
└── tests/
    ├── test_analytical.py
    ├── test_api.py
    ├── test_robustness.py
    └── test_ui.py
```

**Critical rule:** Neither app.py nor api.py may import anastruct directly.
All anastruct interactions go through solver.py only.

---

## STRUCTURE TYPES

User selects one structure type from a dropdown before building model:
- Simply supported beam (single span)
- Continuous beam (multiple spans)
- 2D Truss
- 2D Frame
- Custom geometry (free node and member placement, mixed element types)

Each type preselects sensible defaults for element properties and supports.

---

## MODEL INPUT — TWO PARALLEL METHODS

Both methods must stay synchronised — editing one updates the other in real time.

### Method 1: Data Tables (st.data_editor)

Separate editable tables for:

**Nodes table:** node_id, x (m), y (m)

**Members table:** member_id, start_node, end_node, E (GPa), A (cm²),
Iz (cm⁴), element_type (beam/truss), material (display only)

**Supports table:** node_id, support_type
(fixed / pinned / roller_x / roller_y / free /
spring_linear_x / spring_linear_y / spring_rotational),
spring_stiffness (kN/m or kNm/rad, only active for spring types, else null)

**Loads table:** load_id, type (point_force / UDL / point_moment / settlement),
node_or_member_id, direction (Fx / Fy / Mz), magnitude,
udl_start (m from start node, null = full span start),
udl_end (m from start node, null = full span end)

### Method 2: Interactive Plotly Canvas

- Click canvas to place new node at clicked coordinates
- Grid snap enabled by default, grid spacing configurable (default 1.0 m)
- After two nodes placed, member is proposed and user confirms
- Click existing node to assign support type from dropdown
- Click existing member to assign load from form
- Canvas shows: node IDs, member IDs, support symbols
  (standard structural engineering notation), load arrows with magnitude labels
- All canvas actions update data tables in real time

---

## SECTION AND MATERIAL PROPERTIES

Dropdown library of common profiles:
- Custom (manual input of E, A, Iz)
- Steel S275: E = 210 GPa
- Concrete C25: E = 30 GPa
- HEA 200: A = 53.8 cm², Iz = 3690 cm⁴
- HEA 300: A = 112.5 cm², Iz = 18260 cm⁴
- HEB 200: A = 78.1 cm², Iz = 5700 cm⁴
- HEB 300: A = 149.1 cm², Iz = 25170 cm⁴

Selecting a profile prefills E, A, Iz — user can still override manually.

---

## PRESET EXAMPLES

App starts with blank model on launch.
Sidebar dropdown loads presets — replaces current model after confirmation if
model has unsaved content.

Required presets (all defined in presets.py):

1. Simply supported beam — central point load
   L=6m, P=20kN at midspan, Steel S275, HEA 200

2. Simply supported beam — full span UDL
   L=6m, w=10 kN/m, Steel S275, HEA 200

3. Fixed-fixed beam — full span UDL
   L=6m, w=10 kN/m, Steel S275, HEA 300

4. Two-span continuous beam — point load at midspan each span
   L1=6m, L2=6m, P=20kN at midspan of each, pinned left,
   roller middle, roller right, Steel S275, HEA 300

5. Simple portal frame — horizontal point load at top
   Column height=4m, beam span=6m, pinned bases,
   H=10kN at top-left node, Steel S275, HEB 200

6. Warren truss — 3 panels, midspan point load
   Panel width=2m, height=2m, P=10kN at midspan bottom chord,
   pinned left, roller right, Steel S275, custom A=20cm²

---

## SOLVE AND RESULTS

Solve button triggers anastruct analysis.
Show specific st.error message if model is ill-defined — never show Python traceback.

Results section:

### Diagrams (Plotly, interactive, hover shows exact values)
Four tabs, one diagram per tab:

1. **Deformed shape**
   Undeformed structure in grey, deformed in blue.
   Scale factor shown above diagram, adjustable with slider.
   Node IDs and member IDs labelled.

2. **Bending moment diagram**
   Plotted on tension side (standard structural engineering convention).
   Filled area. Values on hover. Sign convention noted on diagram.

3. **Shear force diagram**
   Filled area. Values on hover.

4. **Axial force diagram**
   Filled area. Tension positive convention noted.

All diagrams show member and node IDs for reference.

### Reaction Forces Table
Columns: node_id, Rx (kN), Ry (kN), Mz (kNm)
Final row: sum of all reactions as equilibrium check.

### Element Results Table
Columns: member_id, N_max (kN), V_max (kN), M_max (kNm),
max_displacement (mm), location of max values (m from start node)

---

## UI LAYOUT

Two-column Streamlit layout:
- Left column (40%): all inputs, tables, solve button
- Right column (60%): canvas and results

Tab structure:
- Tab 1 — Model: canvas + input tables
- Tab 2 — Results: diagrams + result tables (only active after solving)

Sidebar contains:
1. Load preset dropdown
2. Divider
3. Load from file (st.file_uploader, accepts .yaml and .fem.yaml)
4. Save to file (st.download_button)
5. Model name field (st.text_input)
6. Description field (st.text_area, 2 rows)

Use clear section headers and brief helper text for each input section.
Helper text written for students who understand structural mechanics
but may be new to software.

---

## UNITS

SI throughout. Fixed, non-selectable.
Display units explicitly next to every input field and result value:
kN, m, kNm, kN/m, GPa, cm², cm⁴
Use mm for displacements only.

---

## SAVE AND LOAD

### File Format: YAML

Extension: .fem.yaml
Human readable and human editable.
Add a comment header block at top of every saved file explaining format and units.

### Example File Structure

```yaml
# -----------------------------------------------
# 2D FEM Model File
# Generated by FEM App v1.0
# Units: kN, m, kNm, GPa, cm2, cm4
# Edit this file directly or load it in the app
# -----------------------------------------------

metadata:
  name: "Simply supported beam - UDL"
  structure_type: beam          # beam | truss | frame | custom
  created: "2024-03-07 14:32"
  description: "Introductory example for lecture 3"

nodes:
  - id: 1
    x: 0.0       # m
    y: 0.0       # m
  - id: 2
    x: 6.0       # m
    y: 0.0       # m

members:
  - id: 1
    start_node: 1
    end_node: 2
    element_type: beam          # beam | truss
    material: Steel S275
    E_GPa: 210.0
    A_cm2: 100.0
    Iz_cm4: 10000.0

supports:
  - node_id: 1
    type: pinned                # fixed | pinned | roller_x | roller_y |
                                # spring_linear_x | spring_linear_y | spring_rotational
    spring_stiffness: null      # kN/m or kNm/rad, null if not spring
  - node_id: 2
    type: roller_y
    spring_stiffness: null

loads:
  - id: 1
    type: UDL                   # point_force | UDL | point_moment | settlement
    member_id: 1
    direction: Fy
    magnitude: -10.0            # kN/m, negative = downward
    udl_start: null             # null = full span
    udl_end: null
```

### Save Behaviour

Generate YAML in memory and trigger browser download immediately.
Filename: {model_name}_{date}.fem.yaml (spaces → underscores)
If model name empty: fem_model_{date}.fem.yaml
Never save results — results are always recomputed fresh from the model.

### Load Behaviour

On upload:
- Parse YAML
- Validate all required keys present
- Validate all node IDs referenced in members, supports and loads exist
- Validate no duplicate node IDs or member IDs
- Validate member start_node != end_node
- On validation error: show specific st.error naming the failing field
- On success: populate all tables and canvas, switch to Model tab,
  show st.success message
- If current model has unsaved nodes/members: show st.warning
  and require confirmation before replacing

### Utility Functions in solver.py

```python
yaml_to_model(yaml_dict) -> ModelDefinition
model_to_yaml(ModelDefinition) -> yaml_dict
```

These allow solve_file.py CLI to also accept .fem.yaml input files.

---

## AI AGENT REST API

FastAPI on port 8502, parallel to Streamlit on 8501.
All solver logic shared via solver.py.
API code in api.py.

### Endpoints

```
GET  /health              → {"status": "ok", "version": "1.0"}
GET  /presets             → list of preset names and IDs
GET  /presets/{id}        → full model definition JSON for that preset
GET  /schema/input        → JSON schema for input model format
GET  /schema/output       → JSON schema for result format
POST /solve               → accepts model JSON, returns results JSON
POST /solve/file          → accepts .fem.yaml file upload, returns results.json
```

On solve error: HTTP 400 with {"error": "human readable message"}

### Input JSON Schema

```json
{
  "structure_type": "beam|truss|frame|custom",
  "nodes": [
    {"id": 1, "x": 0.0, "y": 0.0}
  ],
  "members": [
    {
      "id": 1,
      "start_node": 1,
      "end_node": 2,
      "element_type": "beam|truss",
      "E_GPa": 210.0,
      "A_cm2": 100.0,
      "Iz_cm4": 10000.0
    }
  ],
  "supports": [
    {
      "node_id": 1,
      "type": "fixed|pinned|roller_x|roller_y|spring_linear_x|spring_linear_y|spring_rotational",
      "spring_stiffness": null
    }
  ],
  "loads": [
    {
      "id": 1,
      "type": "point_force|UDL|point_moment|settlement",
      "node_or_member_id": 1,
      "direction": "Fx|Fy|Mz",
      "magnitude": -10.0,
      "udl_start": null,
      "udl_end": null
    }
  ]
}
```

### Output JSON Schema

```json
{
  "status": "ok|error",
  "error": null,
  "reactions": [
    {"node_id": 1, "Rx_kN": 0.0, "Ry_kN": 30.0, "Mz_kNm": 0.0}
  ],
  "member_results": [
    {
      "member_id": 1,
      "N_max_kN": 0.0,
      "V_max_kN": 15.0,
      "M_max_kNm": 45.0,
      "max_displacement_mm": 12.3,
      "M_max_location_m": 3.0,
      "V_max_location_m": 0.0
    }
  ],
  "nodes_displaced": [
    {"node_id": 1, "dx_mm": 0.0, "dy_mm": 0.0, "rz_mrad": 0.0}
  ]
}
```

### CLI File Interface

solve_file.py — standalone script for file-based AI agent workflow:
```bash
python solve_file.py input.json output.json
python solve_file.py model.fem.yaml output.json
```
Exit code 0 on success, 1 on error.
Print human-readable summary to stdout.

---

## TESTING REQUIREMENTS

Test runner: pytest
All tests in /tests directory.
Run with: pytest tests/ -v

### tests/test_analytical.py — Analytical Verification

Tolerance: 0.5% relative error for all numerical checks.
Use solver.py directly (no HTTP, no Streamlit).

**Simply supported beam, L=6m, UDL w=10 kN/m:**
- M_max = wL²/8 = 45.0 kNm at midspan
- R_A = R_B = wL/2 = 30.0 kN
- δ_max = 5wL⁴/384EI at midspan

**Simply supported beam, L=6m, central point load P=20 kN:**
- M_max = PL/4 = 30.0 kNm at midspan
- R_A = R_B = P/2 = 10.0 kN

**Fixed-fixed beam, L=6m, UDL w=10 kN/m:**
- M_end = wL²/12 = 30.0 kNm (hogging)
- M_midspan = wL²/24 = 15.0 kNm (sagging)
- R_A = R_B = wL/2 = 30.0 kN

**Propped cantilever, L=6m, UDL w=10 kN/m:**
- R_prop = 3wL/8 = 22.5 kN
- M_fixed = wL²/8 = 45.0 kNm

**Warren truss, 3 panels, panel width=2m, height=2m, P=10 kN at midspan:**
- Verify all member forces by method of sections
- Top chord: compression
- Bottom chord: tension
- Global equilibrium: ΣFy = 0, ΣFx = 0

**Simple portal frame, column height=4m, beam span=6m,
pinned bases, H=10 kN horizontal at top-left:**
- ΣFx reactions = H = 10.0 kN
- Verify moment diagram shape and sign

### tests/test_robustness.py — Edge Cases

Each case must return a clear error message dict, not raise a Python exception.
Assert response contains "error" key with non-empty string.

Required cases:
- Free-floating node (defined but not connected to any member)
- Free-floating member (no path to any support)
- Mechanism (roller at both ends of beam)
- Unstable frame (insufficient supports for load direction)
- Duplicate node coordinates
- Zero-length member (start node == end node)
- Member referencing non-existent node ID
- Load on non-existent node or member ID
- Empty model (no nodes, no members)
- Single node with load but no members
- Collinear truss (all nodes on same line — mechanism)
- Over-constrained system (should solve successfully, not error)

### tests/test_api.py — API Endpoint Tests

Requires server running on port 8502. Document this clearly at top of file.
Use requests library.

Required tests:
- GET /health returns 200 and {"status": "ok"}
- GET /presets returns all 6 preset names
- GET /presets/{id} returns valid model JSON for each preset
- POST /solve returns 200 with valid result JSON for each preset
- POST /solve results match analytical tolerances from test_analytical.py
- POST /solve returns 400 with "error" key for each robustness edge case
- GET /schema/input returns valid JSON schema
- GET /schema/output returns valid JSON schema

### tests/test_ui.py — UI Tests

Uses Playwright. Document requirement: "playwright install chromium" after pip install.
Requires Streamlit running on port 8501.

Required tests:
- App loads at localhost:8501 without console errors
- Each of 6 presets loads and populates tables without error
- Solve button produces Results tab for each preset
- Results tab shows all four diagram tabs
- Reaction forces table visible after solving
- Element results table visible after solving
- Error message appears when solving empty model
- Save button triggers file download
- Uploaded valid .fem.yaml populates model correctly
- Unit labels visible next to input fields

---

## CODE QUALITY REQUIREMENTS

- All defaults defined as named constants at top of each file — no magic numbers
- All anastruct calls wrapped in try/except in solver.py
- Error messages written for students — no Python internals exposed to UI
- Session state used correctly — model not reset on every widget interaction
- Coordinate transformation between canvas pixel space and model space
  documented with comments explaining the mapping
- solver.py functions have docstrings with units for all parameters and return values
- README includes:
  - One-command install: pip install -r requirements.txt
  - One-command launch: bash run.sh
  - Note: results are never saved to file — always recomputed from model
  - Brief description of each file
  - How to run tests: pytest tests/ -v
  - Note that test_api.py and test_ui.py require servers to be running first
```
