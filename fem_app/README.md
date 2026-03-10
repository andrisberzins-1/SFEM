# 2D FEM Web Application

A locally-run web application for 2D structural FEM analysis, designed for
bachelor-level structural engineering students verifying hand calculations.

## Quick Start

### Install

```bash
pip install -r requirements.txt
```

### Launch

```bash
bash run.sh
```

This starts both servers:
- **Streamlit UI**: http://localhost:8501
- **FastAPI API**: http://localhost:8502 (API docs at http://localhost:8502/docs)

Or start individually:

```bash
# Streamlit only
streamlit run app.py --server.port 8501

# FastAPI only
uvicorn api:app --port 8502
```

### CLI Solver

```bash
python solve_file.py input.json output.json
python solve_file.py model.fem.yaml output.json
```

## File Structure

| File | Description |
|------|-------------|
| `app.py` | Streamlit frontend — UI, tables, diagrams |
| `api.py` | FastAPI REST API — all endpoints |
| `solver.py` | anastruct wrapper — single source of truth for FEM |
| `presets.py` | 6 preset model definitions |
| `solve_file.py` | CLI file-based solver |
| `run.sh` | Launches both servers |
| `requirements.txt` | Python dependencies |
| `tests/` | pytest test suite |

**Important:** Neither `app.py` nor `api.py` imports anastruct directly.
All FEM interactions go through `solver.py`.

## Units

SI throughout (fixed, non-selectable):
- Forces: kN
- Lengths: m
- Moments: kNm
- Distributed loads: kN/m
- Elastic modulus: GPa
- Area: cm²
- Inertia: cm⁴
- Displacements: mm (results only)

## Save/Load

Models are saved as `.fem.yaml` files — human-readable YAML.
Results are never saved to file; they are always recomputed fresh from the model.

## Running Tests

```bash
# Core solver tests (no server needed)
pytest tests/test_analytical.py tests/test_robustness.py -v

# API tests (requires FastAPI running on port 8502)
pytest tests/test_api.py -v

# UI tests (requires Streamlit on 8501, install Playwright first)
playwright install chromium
pytest tests/test_ui.py -v
```
