"""
file_io.py — Unified file I/O for buckling_app.

Handles the SFEM envelope format for model files (templates / saves)
and result files (exchange).  No module-specific logic — dataclass ↔ dict
conversion stays in app.py / buckling_solver.py.
"""

from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

MODULE_NAME = "buckling_app"
FORMAT_MODEL = "buckling"
FORMAT_RESULT = "buckling_result"
FORMAT_VERSION = 1
MODEL_EXT = "buckling.json"
RESULT_EXT = "buckling_result.json"

TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
SAVES_DIR = pathlib.Path(__file__).parent / "saves"
EXCHANGE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "exchange" / "buckling_results"
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
# Parse (with backward-compat)
# ---------------------------------------------------------------------------

def parse_envelope(raw: dict) -> tuple[dict, dict, dict | None]:
    """Parse an envelope dict.

    Returns (sfem_meta, data, display_settings).
    Handles old format (``metadata`` + ``member`` at top level).
    """
    if "sfem" in raw:
        sfem = raw["sfem"]
        data = raw.get("data", {})
        ds = raw.get("display_settings")
        return sfem, data, ds

    # Old format compat
    meta = raw.get("metadata", {})
    sfem = {
        "module": MODULE_NAME,
        "format": FORMAT_MODEL,
        "type": "model",
        "format_version": meta.get("format_version", 1),
        "created": meta.get("created", ""),
        "name": meta.get("name", ""),
        "description": "",
    }
    data = {"member": raw.get("member", {})}
    return sfem, data, None


# ---------------------------------------------------------------------------
# Serialize / deserialize
# ---------------------------------------------------------------------------

def serialize(envelope: dict) -> str:
    return json.dumps(envelope, indent=2)


def deserialize(text: str) -> dict:
    return json.loads(text)


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
            raw = json.loads(fp.read_text(encoding="utf-8"))
            sfem, _, _ = parse_envelope(raw)
            name = sfem.get("name") or fp.stem.replace("_", " ")
        except Exception:
            name = fp.stem.replace("_", " ")
        templates.append({"name": name, "path": fp})
    return templates


def load_template(path: pathlib.Path) -> tuple[dict, dict, dict | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return parse_envelope(raw)


def save_template(envelope: dict, name: str) -> pathlib.Path:
    TEMPLATES_DIR.mkdir(exist_ok=True)
    fname = f"{_sanitize_name(name)}.{MODEL_EXT}"
    path = TEMPLATES_DIR / fname
    path.write_text(serialize(envelope), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Case saves I/O
# ---------------------------------------------------------------------------

def save_case(envelope: dict, name: str) -> pathlib.Path:
    """Write a model envelope to ``saves/``. Auto-incrementing counter."""
    SAVES_DIR.mkdir(exist_ok=True)
    base = _sanitize_name(name)
    path = _next_available_path(SAVES_DIR, base, MODEL_EXT)
    path.write_text(serialize(envelope), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Exchange I/O
# ---------------------------------------------------------------------------

def save_to_exchange(envelope: dict, name: str) -> pathlib.Path:
    EXCHANGE_DIR.mkdir(parents=True, exist_ok=True)
    base = _sanitize_name(name)
    path = _next_available_path(EXCHANGE_DIR, base, RESULT_EXT)
    path.write_text(serialize(envelope), encoding="utf-8")
    return path


def load_exchange_list(exchange_dir: pathlib.Path | None = None) -> list[dict]:
    """Scan exchange dir for result files (handles both old + new formats)."""
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
                # Old flat format
                name = raw.get("name", fp.stem)
                data = {"properties": raw.get("properties", {})}
            items.append({"name": name, "path": fp, "data": data})
        except Exception:
            continue
    return items
