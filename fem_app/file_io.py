"""
file_io.py — Unified file I/O for fem_app.

Handles the SFEM envelope format for model files (templates / saves)
and result files (exchange).  Uses YAML for model files (human-readable,
supports comments) and JSON for result files.

Backward-compatible: loads old-format .fem.yaml files transparently.
"""

from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

MODULE_NAME = "fem_app"
FORMAT_MODEL = "fem"
FORMAT_RESULT = "fem_result"
FORMAT_VERSION = 2
MODEL_EXT = "fem.yaml"
RESULT_EXT = "fem_result.json"

TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
SAVES_DIR = pathlib.Path(__file__).parent / "saves"
EXCHANGE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "exchange" / "fem_results"
)

# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------

def _sfem_block(fmt: str, file_type: str, name: str, description: str = "") -> dict:
    return {
        "module": MODULE_NAME,
        "format": fmt,
        "type": file_type,
        "format_version": FORMAT_VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "name": name,
        "description": description,
    }


def make_model_envelope(
    name: str,
    data: dict,
    display_settings: dict | None = None,
) -> dict:
    env: dict = {"sfem": _sfem_block(FORMAT_MODEL, "model", name), "data": data}
    if display_settings:
        env["display_settings"] = display_settings
    return env


def make_result_envelope(name: str, data: dict) -> dict:
    return {"sfem": _sfem_block(FORMAT_RESULT, "result", name), "data": data}


# ---------------------------------------------------------------------------
# Parse (with backward-compat for old .fem.yaml format)
# ---------------------------------------------------------------------------

def parse_envelope(raw: dict) -> tuple[dict, dict, dict | None]:
    """Parse a dict (from YAML or JSON).

    Returns (sfem_meta, data, display_settings).
    Handles old format (``metadata`` key with model fields at top level).
    """
    if "sfem" in raw:
        sfem = raw["sfem"]
        data = raw.get("data", {})
        ds = raw.get("display_settings")
        return sfem, data, ds

    # --- Old .fem.yaml format compat ---
    meta = raw.get("metadata", {})
    sfem = {
        "module": MODULE_NAME,
        "format": FORMAT_MODEL,
        "type": "model",
        "format_version": meta.get("format_version", 2),
        "created": meta.get("created", ""),
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
    }
    # Old format has model data at top level alongside metadata
    data: dict[str, Any] = {}
    for key in ("materials", "cross_sections", "nodes", "members",
                "supports", "loads", "hinges"):
        if key in raw:
            data[key] = raw[key]
    # Structure type and mesh_size are in metadata in old format
    data["structure_type"] = meta.get("structure_type", "custom")
    data["mesh_size"] = meta.get("mesh_size", 50)

    ds = raw.get("display_settings")
    return sfem, data, ds


# ---------------------------------------------------------------------------
# Serialize / deserialize (YAML for models, JSON for results)
# ---------------------------------------------------------------------------

def serialize_model(envelope: dict) -> str:
    """Envelope → YAML string for model files."""
    return yaml.dump(envelope, default_flow_style=False, sort_keys=False,
                     allow_unicode=True)


def serialize_result(envelope: dict) -> str:
    """Envelope → JSON string for result files."""
    return json.dumps(envelope, indent=2)


def deserialize(text: str) -> dict:
    """Auto-detect YAML or JSON and parse."""
    text = text.strip()
    # Try JSON first (starts with { )
    if text.startswith("{"):
        return json.loads(text)
    # Otherwise YAML
    return yaml.safe_load(text)


# ---------------------------------------------------------------------------
# File naming
# ---------------------------------------------------------------------------

_SANITIZE_RE = re.compile(r"[^\w\-]+")


def _sanitize_name(name: str) -> str:
    return _SANITIZE_RE.sub("_", name.strip().lower()).strip("_") or "unnamed"


def _next_available_path(directory: pathlib.Path, base: str, ext: str) -> pathlib.Path:
    candidate = directory / f"{base}.{ext}"
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = directory / f"{base}_{counter}.{ext}"
        if not candidate.exists():
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# Template I/O
# ---------------------------------------------------------------------------

def load_template_list() -> list[dict]:
    if not TEMPLATES_DIR.is_dir():
        return []
    templates: list[dict] = []
    for fp in sorted(TEMPLATES_DIR.glob(f"*.{MODEL_EXT}")):
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
            sfem, _, _ = parse_envelope(raw)
            name = sfem.get("name") or fp.stem.replace("_", " ")
        except Exception:
            name = fp.stem.replace("_", " ")
        templates.append({"name": name, "path": fp})
    return templates


def load_template(path: pathlib.Path) -> tuple[dict, dict, dict | None]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parse_envelope(raw)


def save_template(envelope: dict, name: str) -> pathlib.Path:
    TEMPLATES_DIR.mkdir(exist_ok=True)
    fname = f"{_sanitize_name(name)}.{MODEL_EXT}"
    path = TEMPLATES_DIR / fname
    path.write_text(serialize_model(envelope), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Case saves I/O
# ---------------------------------------------------------------------------

def save_case(envelope: dict, name: str) -> pathlib.Path:
    """Write a model envelope to ``saves/``.

    Uses auto-incrementing counter to avoid overwriting existing files.
    """
    SAVES_DIR.mkdir(exist_ok=True)
    base = _sanitize_name(name)
    path = _next_available_path(SAVES_DIR, base, MODEL_EXT)
    path.write_text(serialize_model(envelope), encoding="utf-8")
    return path


def save_case_overwrite(envelope: dict, name: str) -> pathlib.Path:
    """Write a model envelope to ``saves/``, overwriting the most recent
    file with the same sanitized base name if it exists."""
    SAVES_DIR.mkdir(exist_ok=True)
    base = _sanitize_name(name)
    # Find the most recent existing file with matching base name
    candidates = sorted(
        SAVES_DIR.glob(f"{base}*.{MODEL_EXT}"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if candidates:
        path = candidates[0]
    else:
        path = SAVES_DIR / f"{base}.{MODEL_EXT}"
    path.write_text(serialize_model(envelope), encoding="utf-8")
    return path


def load_save_display_settings(name: str) -> dict | None:
    """Load display_settings from the most recent save matching *name*."""
    if not SAVES_DIR.is_dir():
        return None
    base = _sanitize_name(name)
    candidates = sorted(
        SAVES_DIR.glob(f"{base}*.{MODEL_EXT}"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    for fp in candidates:
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
            ds = raw.get("display_settings")
            if ds:
                return ds
        except Exception:
            continue
    return None


def load_saves_list() -> list[dict]:
    """Return list of saved model files from ``saves/``."""
    if not SAVES_DIR.is_dir():
        return []
    saves: list[dict] = []
    for fp in sorted(SAVES_DIR.glob(f"*.{MODEL_EXT}"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            raw = yaml.safe_load(fp.read_text(encoding="utf-8"))
            sfem, _, _ = parse_envelope(raw)
            name = sfem.get("name") or fp.stem.replace("_", " ")
        except Exception:
            name = fp.stem.replace("_", " ")
        saves.append({"name": name, "path": fp})
    return saves


def save_result_case(envelope: dict, name: str) -> pathlib.Path:
    """Write a result envelope to ``saves/`` as JSON."""
    SAVES_DIR.mkdir(exist_ok=True)
    base = _sanitize_name(name)
    path = _next_available_path(SAVES_DIR, base, RESULT_EXT)
    path.write_text(serialize_result(envelope), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Exchange I/O (JSON for results)
# ---------------------------------------------------------------------------

def save_to_exchange(envelope: dict, name: str) -> pathlib.Path:
    EXCHANGE_DIR.mkdir(parents=True, exist_ok=True)
    base = _sanitize_name(name)
    path = _next_available_path(EXCHANGE_DIR, base, RESULT_EXT)
    path.write_text(serialize_result(envelope), encoding="utf-8")
    return path


def load_exchange_list(exchange_dir: pathlib.Path | None = None) -> list[dict]:
    d = exchange_dir or EXCHANGE_DIR
    if not d.is_dir():
        return []
    items: list[dict] = []
    for fp in sorted(d.glob("*.json")):
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            if "sfem" in raw:
                name = raw["sfem"].get("name", fp.stem)
                data = raw.get("data", {})
            else:
                name = raw.get("name", fp.stem)
                data = raw
            items.append({"name": name, "path": fp, "data": data})
        except Exception:
            continue
    return items
