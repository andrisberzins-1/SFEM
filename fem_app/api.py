"""
api.py — FastAPI REST API for 2D FEM analysis.

Runs on port 8502 alongside the Streamlit frontend on port 8501.
All solver logic is in solver.py — this file does NOT import anastruct.

Endpoints:
    GET  /health           → {"status": "ok", "version": "1.0"}
    GET  /presets           → list of preset names and IDs
    GET  /presets/{id}      → full model definition JSON for that preset
    GET  /schema/input      → JSON schema for input model format
    GET  /schema/output     → JSON schema for result format
    POST /solve             → accepts model JSON, returns results JSON
    POST /solve/file        → accepts .fem.yaml file upload, returns results JSON

Usage:
    uvicorn api:app --host 0.0.0.0 --port 8502
"""

from __future__ import annotations

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

try:
    from fem_app.presets import get_preset_by_id, get_preset_names
    from fem_app.solver import (
        dict_to_model,
        model_to_dict,
        result_to_dict,
        solve,
        yaml_to_model,
    )
except ImportError:
    from presets import get_preset_by_id, get_preset_names
    from solver import (
        dict_to_model,
        model_to_dict,
        result_to_dict,
        solve,
        yaml_to_model,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_VERSION = "1.0"
API_PORT = 8502

# ---------------------------------------------------------------------------
# JSON Schemas (for /schema endpoints)
# ---------------------------------------------------------------------------

INPUT_SCHEMA = {
    "type": "object",
    "required": ["nodes", "members", "materials", "cross_sections", "supports", "loads"],
    "properties": {
        "format_version": {"type": "integer", "description": "Schema version (2)."},
        "structure_type": {
            "type": "string",
            "enum": ["beam", "truss", "frame", "custom"],
            "description": "Type of structure (metadata only).",
        },
        "materials": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "E_GPa": {"type": "number", "description": "Elastic modulus (GPa)."},
                },
            },
        },
        "cross_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "material_id"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "A_cm2": {"type": "number", "description": "Cross-section area (cm²)."},
                    "Iz_cm4": {"type": "number", "description": "Second moment of area (cm⁴)."},
                    "material_id": {"type": "integer", "description": "Reference to material ID."},
                },
            },
        },
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "x", "y"],
                "properties": {
                    "id": {"type": "integer", "description": "Unique node ID."},
                    "x": {"type": "number", "description": "X coordinate (m)."},
                    "y": {"type": "number", "description": "Y coordinate (m)."},
                },
            },
        },
        "members": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "start_node", "end_node"],
                "properties": {
                    "id": {"type": "integer"},
                    "start_node": {"type": "integer"},
                    "end_node": {"type": "integer"},
                    "section_id": {"type": "integer", "description": "Reference to cross-section ID."},
                },
            },
        },
        "supports": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["node_id", "type"],
                "properties": {
                    "node_id": {"type": "integer"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "fixed", "pinned", "roller_x", "roller_y",
                            "spring_linear_x", "spring_linear_y", "spring_rotational",
                        ],
                    },
                    "spring_stiffness": {
                        "type": ["number", "null"],
                        "description": "Spring stiffness (kN/m or kNm/rad). Required for spring types.",
                    },
                },
            },
        },
        "loads": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "node_or_member_id"],
                "properties": {
                    "id": {"type": "integer"},
                    "type": {
                        "type": "string",
                        "enum": ["point_force", "UDL", "point_moment", "settlement"],
                    },
                    "node_or_member_id": {"type": "integer"},
                    "direction": {"type": "string", "enum": ["Fx", "Fy", "Mz"]},
                    "magnitude": {"type": "number"},
                    "udl_start": {"type": ["number", "null"]},
                    "udl_end": {"type": ["number", "null"]},
                },
            },
        },
        "hinges": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["member_id"],
                "properties": {
                    "member_id": {"type": "integer"},
                    "start_release": {"type": "boolean", "description": "Moment release at start node."},
                    "end_release": {"type": "boolean", "description": "Moment release at end node."},
                },
            },
        },
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok", "error"]},
        "error": {"type": ["string", "null"]},
        "reactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "integer"},
                    "Rx_kN": {"type": "number"},
                    "Ry_kN": {"type": "number"},
                    "Mz_kNm": {"type": "number"},
                },
            },
        },
        "member_results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "member_id": {"type": "integer"},
                    "N_max_kN": {"type": "number"},
                    "V_max_kN": {"type": "number"},
                    "M_max_kNm": {"type": "number"},
                    "max_displacement_mm": {"type": "number"},
                    "M_max_location_m": {"type": "number"},
                    "V_max_location_m": {"type": "number"},
                },
            },
        },
        "nodes_displaced": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "integer"},
                    "dx_mm": {"type": "number"},
                    "dy_mm": {"type": "number"},
                    "rz_mrad": {"type": "number"},
                },
            },
        },
    },
}

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="2D FEM Analysis API",
    version=API_VERSION,
    description="REST API for 2D structural FEM analysis using anastruct.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": API_VERSION}


@app.get("/presets")
def list_presets():
    """Return list of all available preset names and IDs."""
    return get_preset_names()


@app.get("/presets/{preset_id}")
def get_preset(preset_id: int):
    """Return full model definition JSON for a specific preset."""
    try:
        model = get_preset_by_id(preset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return model_to_dict(model)


@app.get("/schema/input")
def schema_input():
    """Return JSON schema for the input model format."""
    return INPUT_SCHEMA


@app.get("/schema/output")
def schema_output():
    """Return JSON schema for the result format."""
    return OUTPUT_SCHEMA


@app.post("/solve")
def solve_model(model_data: dict):
    """
    Solve a structural model from JSON input.

    Accepts model definition JSON, returns analysis results.
    On error: HTTP 400 with {"error": "human readable message"}.
    """
    try:
        model = dict_to_model(model_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": f"Invalid model data: {str(e)}"})

    result = solve(model)
    result_dict = result_to_dict(result)

    if result.status == "error":
        raise HTTPException(status_code=400, detail={"error": result.error})

    return result_dict


@app.post("/solve/file")
async def solve_file(file: UploadFile = File(...)):
    """
    Solve a structural model from an uploaded .fem.yaml file.

    Accepts file upload, returns analysis results JSON.
    On error: HTTP 400 with {"error": "human readable message"}.
    """
    content = await file.read()
    text = content.decode("utf-8")

    try:
        yaml_dict = yaml.safe_load(text)
        model = yaml_to_model(yaml_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": f"Invalid YAML file: {str(e)}"})

    result = solve(model)
    result_dict = result_to_dict(result)

    if result.status == "error":
        raise HTTPException(status_code=400, detail={"error": result.error})

    return result_dict


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
