# SFEM Educational Platform

Multi-module educational platform for structural engineering students.
Each module is a **standalone Streamlit app** in its own directory.

## Architecture — Golden Rules

1. **Modules NEVER share Python imports.** No cross-module imports, ever.
2. **Solver file is single source of truth** for calculations — `app.py` NEVER implements math.
3. Modules exchange data via JSON files in `exchange/` directory (not Python imports).
4. Each module has: `app.py`, `*_solver.py`, `presets.py`, `tests/`, `requirements.txt`, `module.json`, `CLAUDE.md`.

## Port Assignments

| Module | Streamlit | FastAPI |
|---|---|---|
| Hub | 8500 | — |
| fem_app | 8501 | 8502 |
| section_app | 8503 | — |
| (future) buckling_app | 8504 | — |
| (future) strength_app | 8505 | — |

## Project Structure

```
C:\SFEM\
├── CLAUDE.md              # This file — platform-wide rules
├── hub/app.py             # Launcher — auto-discovers modules via module.json
├── fem_app/               # 2D FEM analysis (anastruct)
├── section_app/           # Cross-section properties calculator
├── exchange/              # JSON data exchange between modules
├── run_all.bat            # Launches hub + all modules
└── run_all.sh
```

## Common Patterns (ALL modules must follow)

- Python **dataclasses** for all input/output data structures
- **`st.data_editor`** for tabular input
- **Plotly** for all visualization
- Never expose Python tracebacks in UI — catch exceptions, show `st.error()` with human-readable message
- All defaults as named constants at top of file — no magic numbers

## Testing

- Every module has `tests/` that run WITHOUT any server: `pytest <module>/tests/ -v`
- Verify against known analytical/catalogue values with relative tolerance
- Run tests after ANY code change before declaring done

## When Modifying a Module

1. Read that module's `CLAUDE.md` first
2. NEVER modify files in other modules
3. NEVER add imports from other modules
4. Run that module's tests after changes
5. If adding a new module: create directory, add `module.json`, create `CLAUDE.md`, follow patterns above

## Hub Discovery

Modules register via `module.json` in their directory:
```json
{"name": "Module Name", "port": 8503, "icon": "...", "description": "..."}
```
Hub scans sibling directories for these files automatically.
