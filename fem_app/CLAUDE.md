# fem_app — 2D FEM Analysis Module

Streamlit + FastAPI wrapper around anastruct for 2D structural FEM analysis.
Target audience: bachelor-level structural engineering students verifying hand calculations.

## Critical Rules

- **Only `solver.py` imports anastruct.** Neither `app.py` nor `api.py` may import it.
- Data flow: `app.py` -> `solver.py` -> anastruct. Never bypass.
- `solver.py` is the single source of truth for all FEM operations.

## Units (SI, fixed, non-selectable)

| Quantity | Unit | Internal conversion |
|---|---|---|
| Forces | kN | — |
| Lengths | m | — |
| Moments | kNm | — |
| Distributed loads | kN/m | — |
| Elastic modulus | GPa | 1 GPa = 1e6 kN/m^2 |
| Area | cm^2 | 1 cm^2 = 1e-4 m^2 |
| Inertia | cm^4 | 1 cm^4 = 1e-8 m^4 |
| Displacements (results) | mm | — |

## File Structure

```
fem_app/
├── app.py           # Streamlit frontend (port 8501)
├── api.py           # FastAPI REST API (port 8502)
├── solver.py        # anastruct wrapper — single source of truth
├── presets.py       # 6 preset model definitions
├── library.py       # Material & section library loader
├── solve_file.py    # CLI file-based solver
├── library/         # JSON data: materials, HEA/HEB/IPE sections
├── templates/       # .fem.yaml template files
├── tests/           # pytest test suite
└── BUILD_SPEC.md    # Original detailed build specification (reference)
```

## Testing

```bash
pytest fem_app/tests/test_analytical.py fem_app/tests/test_robustness.py -v
```

Tests run WITHOUT any server. API tests (`test_api.py`) require FastAPI on port 8502.

## Ports

- Streamlit: 8501
- FastAPI: 8502
