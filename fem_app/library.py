"""
library.py — Material and cross-section library for the FEM app.

Loads standard structural engineering data from JSON files in the
``library/`` folder. Library items are templates (no ``id`` field);
IDs are assigned only when items are added to a model.
"""

import json
import os
from pathlib import Path

_LIB_DIR = Path(__file__).parent / "library"


def _load_json(filename: str) -> list[dict]:
    """Load a JSON array from the library folder."""
    path = _LIB_DIR / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Materials ────────────────────────────────────────────────────────────

def load_materials_library() -> list[dict]:
    """Return all library materials (no ``id`` field)."""
    return _load_json("materials.json")


# ── Sections ─────────────────────────────────────────────────────────────

def get_section_families() -> list[str]:
    """Return available profile families, e.g. ``['HEA', 'HEB', 'IPE']``."""
    families = []
    for f in sorted(_LIB_DIR.glob("sections_*.json")):
        # sections_HEA.json → HEA
        name = f.stem.replace("sections_", "")
        families.append(name)
    return families


def load_sections_library(family: str | None = None) -> list[dict]:
    """Load section profiles.

    Parameters
    ----------
    family : str or None
        If given (e.g. ``'HEA'``), load only that file.
        If ``None``, load and merge all families.
    """
    if family:
        return _load_json(f"sections_{family}.json")
    # merge all
    all_sections: list[dict] = []
    for fam in get_section_families():
        all_sections.extend(_load_json(f"sections_{fam}.json"))
    return all_sections
