"""
test_api.py — API endpoint tests for the FEM REST API.

REQUIRES: FastAPI server running on port 8502.
    Start with: python api.py
    Or:         uvicorn api:app --port 8502

Run with: pytest tests/test_api.py -v
"""

import sys
import os

import pytest
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8502"
REL_TOL = 0.005  # 0.5% relative tolerance


def assert_close(actual, expected, name="value"):
    """Assert that actual is within REL_TOL of expected."""
    if expected == 0:
        assert abs(actual) < 0.01, f"{name}: expected ~0, got {actual}"
    else:
        rel_err = abs(actual - expected) / abs(expected)
        assert rel_err < REL_TOL, (
            f"{name}: expected {expected}, got {actual} "
            f"(relative error {rel_err:.4%} exceeds {REL_TOL:.1%})"
        )


@pytest.fixture(scope="session", autouse=True)
def check_server():
    """Check that the API server is running before tests start."""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        r.raise_for_status()
    except requests.ConnectionError:
        pytest.skip(
            "FastAPI server not running on port 8502. "
            "Start with: python api.py"
        )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self):
        r = requests.get(f"{BASE_URL}/health")
        assert r.status_code == 200

    def test_health_response(self):
        r = requests.get(f"{BASE_URL}/health")
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------


class TestPresets:
    def test_list_presets_returns_6(self):
        r = requests.get(f"{BASE_URL}/presets")
        assert r.status_code == 200
        presets = r.json()
        assert len(presets) == 6

    def test_preset_names(self):
        r = requests.get(f"{BASE_URL}/presets")
        presets = r.json()
        names = [p["name"] for p in presets]
        assert any("simply supported" in n.lower() for n in names)
        assert any("truss" in n.lower() for n in names)
        assert any("frame" in n.lower() or "portal" in n.lower() for n in names)

    @pytest.mark.parametrize("preset_id", [1, 2, 3, 4, 5, 6])
    def test_get_preset_valid(self, preset_id):
        r = requests.get(f"{BASE_URL}/presets/{preset_id}")
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert "members" in data
        assert "supports" in data
        assert "loads" in data
        assert len(data["nodes"]) > 0
        assert len(data["members"]) > 0

    def test_get_preset_invalid(self):
        r = requests.get(f"{BASE_URL}/presets/99")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_input_schema(self):
        r = requests.get(f"{BASE_URL}/schema/input")
        assert r.status_code == 200
        schema = r.json()
        assert "properties" in schema
        assert "nodes" in schema["properties"]
        assert "members" in schema["properties"]

    def test_output_schema(self):
        r = requests.get(f"{BASE_URL}/schema/output")
        assert r.status_code == 200
        schema = r.json()
        assert "properties" in schema
        assert "reactions" in schema["properties"]
        assert "member_results" in schema["properties"]


# ---------------------------------------------------------------------------
# Solve
# ---------------------------------------------------------------------------


class TestSolve:
    @pytest.mark.parametrize("preset_id", [1, 2, 3, 4, 5, 6])
    def test_solve_each_preset(self, preset_id):
        """Each preset should solve successfully via API."""
        # Get the preset model
        r = requests.get(f"{BASE_URL}/presets/{preset_id}")
        model = r.json()

        # Solve it
        r = requests.post(f"{BASE_URL}/solve", json=model)
        assert r.status_code == 200, f"Preset {preset_id} solve failed: {r.text}"
        result = r.json()
        assert result["status"] == "ok"
        assert len(result["reactions"]) > 0
        assert len(result["member_results"]) > 0

    def test_solve_ss_beam_udl_analytical(self):
        """Verify SS beam UDL results match analytical values via API."""
        r = requests.get(f"{BASE_URL}/presets/2")
        model = r.json()

        r = requests.post(f"{BASE_URL}/solve", json=model)
        assert r.status_code == 200
        result = r.json()

        # R_A = R_B = wL/2 = 30 kN
        for reaction in result["reactions"]:
            assert_close(reaction["Ry_kN"], 30.0, f"R_{reaction['node_id']}")

        # M_max = wL²/8 = 45 kNm
        m1 = result["member_results"][0]
        assert_close(m1["M_max_kNm"], 45.0, "M_max")

    def test_solve_ss_beam_point_load_analytical(self):
        """Verify SS beam point load results via API."""
        r = requests.get(f"{BASE_URL}/presets/1")
        model = r.json()

        r = requests.post(f"{BASE_URL}/solve", json=model)
        assert r.status_code == 200
        result = r.json()

        # R_A = R_B = P/2 = 10 kN
        total_ry = sum(rx["Ry_kN"] for rx in result["reactions"])
        assert_close(total_ry, 20.0, "ΣRy")


# ---------------------------------------------------------------------------
# Solve — Error Cases
# ---------------------------------------------------------------------------


class TestSolveErrors:
    def test_empty_model(self):
        """Empty model should return 400."""
        r = requests.post(f"{BASE_URL}/solve", json={
            "nodes": [],
            "members": [],
            "supports": [],
            "loads": [],
        })
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "error" in detail

    def test_missing_supports(self):
        r = requests.post(f"{BASE_URL}/solve", json={
            "nodes": [{"id": 1, "x": 0, "y": 0}, {"id": 2, "x": 6, "y": 0}],
            "members": [{"id": 1, "start_node": 1, "end_node": 2}],
            "supports": [],
            "loads": [{"id": 1, "type": "point_force", "node_or_member_id": 1,
                       "direction": "Fy", "magnitude": -10}],
        })
        assert r.status_code == 400

    def test_zero_length_member(self):
        r = requests.post(f"{BASE_URL}/solve", json={
            "nodes": [{"id": 1, "x": 0, "y": 0}, {"id": 2, "x": 6, "y": 0}],
            "members": [{"id": 1, "start_node": 1, "end_node": 1}],
            "supports": [{"node_id": 1, "type": "pinned"}],
            "loads": [{"id": 1, "type": "point_force", "node_or_member_id": 1,
                       "direction": "Fy", "magnitude": -10}],
        })
        assert r.status_code == 400

    def test_missing_node_reference(self):
        r = requests.post(f"{BASE_URL}/solve", json={
            "nodes": [{"id": 1, "x": 0, "y": 0}],
            "members": [{"id": 1, "start_node": 1, "end_node": 99}],
            "supports": [{"node_id": 1, "type": "pinned"}],
            "loads": [{"id": 1, "type": "point_force", "node_or_member_id": 1,
                       "direction": "Fy", "magnitude": -10}],
        })
        assert r.status_code == 400

    def test_mechanism(self):
        """Two rollers in same direction — mechanism."""
        r = requests.post(f"{BASE_URL}/solve", json={
            "nodes": [{"id": 1, "x": 0, "y": 0}, {"id": 2, "x": 6, "y": 0}],
            "members": [{"id": 1, "start_node": 1, "end_node": 2}],
            "supports": [
                {"node_id": 1, "type": "roller_x"},
                {"node_id": 2, "type": "roller_x"},
            ],
            "loads": [{"id": 1, "type": "point_force", "node_or_member_id": 1,
                       "direction": "Fx", "magnitude": 10}],
        })
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Solve File
# ---------------------------------------------------------------------------


class TestSolveFile:
    def test_solve_yaml_file(self):
        """Upload a valid .fem.yaml file and get results."""
        from solver import model_to_yaml
        from presets import preset_ss_beam_udl

        model = preset_ss_beam_udl()
        yaml_str = model_to_yaml(model)

        r = requests.post(
            f"{BASE_URL}/solve/file",
            files={"file": ("test.fem.yaml", yaml_str.encode("utf-8"), "text/yaml")},
        )
        assert r.status_code == 200
        result = r.json()
        assert result["status"] == "ok"
        assert len(result["reactions"]) > 0

    def test_solve_invalid_yaml(self):
        """Invalid YAML should return 400."""
        r = requests.post(
            f"{BASE_URL}/solve/file",
            files={"file": ("bad.yaml", b"not: valid: yaml: [[[", "text/yaml")},
        )
        # Should get either 400 or 422
        assert r.status_code in (400, 422)
