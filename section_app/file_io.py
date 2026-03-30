"""
file_io.py — Unified file I/O for section_app.

Handles the SFEM envelope format for model files (templates / saves)
and result files (exchange).  No module-specific logic — dataclass ↔ dict
conversion stays in app.py / section_solver.py.
"""

from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Module constants (customise per module)
# ---------------------------------------------------------------------------

MODULE_NAME = "section_app"
FORMAT_MODEL = "section"
FORMAT_RESULT = "section_result"
FORMAT_VERSION = 1
MODEL_EXT = "section.json"
RESULT_EXT = "section_result.json"

TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
SAVES_DIR = pathlib.Path(__file__).parent / "saves"
EXCHANGE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / "exchange" / "sections"
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
    """Wrap module data in a model envelope."""
    env: dict = {"sfem": _sfem_block(FORMAT_MODEL, "model", name), "data": data}
    if display_settings:
        env["display_settings"] = display_settings
    return env


def make_result_envelope(name: str, data: dict) -> dict:
    """Wrap computed results in a result envelope."""
    return {"sfem": _sfem_block(FORMAT_RESULT, "result", name), "data": data}


# ---------------------------------------------------------------------------
# Parse (with backward-compat for old format)
# ---------------------------------------------------------------------------

def parse_envelope(raw: dict) -> tuple[dict, dict, dict | None]:
    """Parse an envelope dict.

    Returns (sfem_meta, data, display_settings).
    Handles the old format (``metadata`` key instead of ``sfem``) transparently.
    """
    if "sfem" in raw:
        # New envelope
        sfem = raw["sfem"]
        data = raw.get("data", {})
        ds = raw.get("display_settings")
        return sfem, data, ds

    # --- Old format compat ---------------------------------------------------
    meta = raw.get("metadata", {})
    sfem = {
        "module": MODULE_NAME,
        "format": FORMAT_MODEL,
        "type": "model",
        "format_version": meta.get("format_version", 1),
        "created": meta.get("created", ""),
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
    }
    # Old format stores parts at top level
    data = {"parts": raw.get("parts", [])}
    return sfem, data, None


# ---------------------------------------------------------------------------
# Serialize / deserialize
# ---------------------------------------------------------------------------

def serialize(envelope: dict) -> str:
    """Envelope → JSON string."""
    return json.dumps(envelope, indent=2)


def deserialize(text: str) -> dict:
    """JSON string → envelope dict."""
    return json.loads(text)


# ---------------------------------------------------------------------------
# File naming helpers
# ---------------------------------------------------------------------------

_SANITIZE_RE = re.compile(r"[^\w\-]+")


def _sanitize_name(name: str) -> str:
    """Lowercase, spaces → underscores, strip special chars."""
    return _SANITIZE_RE.sub("_", name.strip().lower()).strip("_") or "unnamed"


def _next_available_path(directory: pathlib.Path, base: str, ext: str) -> pathlib.Path:
    """Return ``base.ext``, or ``base_2.ext``, ``base_3.ext``, … if the file exists."""
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
    """Scan ``templates/`` and return ``[{name, path}, …]``."""
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
    """Load a template file and return ``(sfem_meta, data, display_settings)``."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return parse_envelope(raw)


def save_template(envelope: dict, name: str) -> pathlib.Path:
    """Write *envelope* to ``templates/{name}.section.json``.

    Overwrites existing file with the same sanitised name (updating a template).
    Returns the path written.
    """
    TEMPLATES_DIR.mkdir(exist_ok=True)
    fname = f"{_sanitize_name(name)}.{MODEL_EXT}"
    path = TEMPLATES_DIR / fname
    path.write_text(serialize(envelope), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Case saves I/O
# ---------------------------------------------------------------------------

def save_case(envelope: dict, name: str) -> pathlib.Path:
    """Write a model envelope to ``saves/``.

    Uses auto-incrementing counter to avoid overwriting existing files.
    Returns the path written.
    """
    SAVES_DIR.mkdir(exist_ok=True)
    base = _sanitize_name(name)
    path = _next_available_path(SAVES_DIR, base, MODEL_EXT)
    path.write_text(serialize(envelope), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Exchange I/O
# ---------------------------------------------------------------------------

def save_to_exchange(envelope: dict, name: str) -> pathlib.Path:
    """Write a result envelope to ``exchange/sections/``.

    Uses auto-incrementing counter to avoid overwriting existing files.
    Returns the path written.
    """
    EXCHANGE_DIR.mkdir(parents=True, exist_ok=True)
    base = _sanitize_name(name)
    path = _next_available_path(EXCHANGE_DIR, base, RESULT_EXT)
    path.write_text(serialize(envelope), encoding="utf-8")
    return path


def load_exchange_list(exchange_dir: pathlib.Path | None = None) -> list[dict]:
    """Scan an exchange directory for result files.

    Returns ``[{name, path, data}, …]``.
    Handles both new envelope and old flat format.
    """
    d = exchange_dir or EXCHANGE_DIR
    if not d.is_dir():
        return []
    items: list[dict] = []
    for fp in sorted(d.glob("*.json")):
        try:
            raw = json.loads(fp.read_text(encoding="utf-8"))
            # New envelope?
            if "sfem" in raw:
                name = raw["sfem"].get("name", fp.stem)
                data = raw.get("data", {})
            else:
                # Old flat format (section_app v1)
                name = raw.get("name", fp.stem)
                data = {"properties": raw.get("properties", {})}
            items.append({"name": name, "path": fp, "data": data})
        except Exception:
            continue
    return items
