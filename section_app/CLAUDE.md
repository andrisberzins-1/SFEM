# section_app — Cross-Section Properties Calculator

Analytical calculator for composite cross-section properties.
Students define sections as collections of rectangles, see step-by-step calculation.

## Critical Rules

- **No external solver dependencies.** Pure Python + numpy only.
- **`section_solver.py` is the single source of truth** for all math — `app.py` does NOT implement any calculations.
- All calculations MUST produce step-by-step `PartResult` records — never just a final number.
- Formulas shown to students must match standard textbook notation (parallel axis theorem / Steiner's theorem).

## Units

- All internal calculations in **mm** (mm², mm⁴, mm³).
- Display shows both mm-based and cm-based equivalents (cm², cm⁴).
- Input table columns: `Name`, `b (mm)`, `h (mm)` — positions via snap system.

## Axis Convention

- Internally always store as `y_bot` (vertical coord) / `z_left` (horizontal coord).
- Solver: `Iy` = moment about horizontal axis (uses dy), `Iz` = moment about vertical axis (uses dz).
- UI toggle lets students choose between:
  - y = horizontal, z = vertical (Eurocode EN 1993, default) → I_y = strong axis for I-beams
  - x = horizontal, y = vertical (basic math convention)
- The toggle only affects display labels and plot axis titles, NOT internal storage or geometry.
- Convention mapping: `I_vert` label → solver's Iy, `I_horiz` label → solver's Iz.
- Product of inertia label: I_yz (Eurocode) / I_xy (basic) — always `yz` order, never `zy`.

## Calculated Properties

Solver computes all of these with step-by-step intermediate values:
- **A** — total area
- **Centroid** — yc, zc
- **Iy, Iz** — moments of inertia (parallel axis theorem / Steiner)
- **Iyz** — product of inertia (centrifugal moment). Always 0 for axis-aligned rectangles' local term.
- **I_max, I_min** — principal moments of inertia
- **alpha_rad, alpha_deg** — principal axis rotation angle
- **axes_coincide** — bool, True if Iyz ≈ 0 (principal axes = centroidal axes)
- **Wy, Wz** — governing (minimum) section moduli: Wy = min(Wy_top, Wy_bot)
- **iy, iz** — radii of gyration

## Cross-Section View

- Plotly chart with **explicit width** (not container-stretch) sized to section aspect ratio
- **Initial axes** (Yi, Zi) — gray lines at origin (0,0)
- **Centroidal axes** (Y, Z) — green/blue dashed through centroid
- **Principal axes** (1, 2) — orange/magenta dash-dot, shown only when axes don't coincide
- **Grid labels** — 14px bold black, with black leader lines
  - Tier system (0, 1, 2) prevents overlapping labels when edges are close
  - **Cluster rule**: if ANY label in a cluster needs a leader, ALL labels in that cluster get leaders
  - **Spread**: cluster labels fan out to avoid leader/text crossings — bottom labels spread left/right, left labels spread up/down
  - Leaders use `axref="x", ayref="y"` for data-coordinate positioning; `x,y` = arrowhead at gridline end, `ax,ay` = text position
  - View range: `pad * 1.3` on label sides (left/bottom), `pad * 1.1` on right/top to accommodate tiered labels
- **Display toggles** in sidebar: Centroid, Centroidal axes, Principal axes

## Section Input — Three-Table Snap System

Sections are defined via three linked tables:
1. **Rectangles** — name + dimensions (b, h)
2. **Snap points** — positioning references (absolute coords or edge-relative)
3. **Joints** — connect pairs of snap points to resolve positions

Edge snap: `edge` (bottom/right/top/left), `position` (0.0–1.0 along edge), `offset` (perpendicular).
Optional `offset_ref` + `offset_dim` for parametric sections.

## File Structure

```
section_app/
├── app.py              # Streamlit frontend (port 8503)
├── section_solver.py   # Pure analytical calculator
├── file_io.py          # SFEM envelope file I/O (templates, saves, exchange)
├── templates/          # .section.json template files (auto-discovered)
├── saves/              # User case saves (auto-created)
├── requirements.txt
├── tests/
│   ├── test_section_calc.py
│   └── test_snap_resolution.py
└── CLAUDE.md           # This file
```

## File Format — SFEM Envelope

Model files use the standard SFEM envelope:
```json
{
  "sfem": { "module": "section_app", "format": "section", "type": "model", ... },
  "data": { "parts": [ { "name": "...", "b": 200.0, "h": 10.0, "y_bot": 0.0, "z_left": 0.0 } ] }
}
```
Result files (exchange):
```json
{
  "sfem": { "module": "section_app", "format": "section_result", "type": "result", ... },
  "data": { "A_mm2": ..., "Iy_mm4": ..., ... }
}
```
Backward-compatible: loads old format files (`metadata` key instead of `sfem`).

## UI Layout

- **Sidebar**: File expander (New / Load: Browse+Templates / Save: Template+Case+Export Results), Section name, Settings (axis convention), Display toggles
- **Main area**: Cross-section view → Section components (3 collapsible tables + Apply button) → Section properties summary → Step-by-step calculation
- **CSS overrides**: Left-aligned LaTeX (`margin-left: 0` on Streamlit's auto-centered wrapper), fit-content table width

## Testing

```bash
pytest section_app/tests/ -v
```

- 41 tests in `test_section_calc.py` — verify against known steel catalogue values (HEA 200, IPE 300), I_yz, principal axes, governing W
- 28 tests in `test_snap_resolution.py` — edge snaps, preset roundtrips, resolution, offset_ref
- Expected tolerance: 1–2% (fillet radii excluded in rectangular decomposition)

## Port

- Streamlit: 8503
