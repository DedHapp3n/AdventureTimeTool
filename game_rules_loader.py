from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app_paths import data_path, resource_path


DEFAULT_PERK_CATALOG: dict[str, Any] = {
    "version": 1,
    "description": "Editable central perk and disadvantage catalog for Adventure Time Tool.",
    "categories": [
        {"id": "general", "name": "Allgemein"},
        {"id": "species", "name": "Spezies"},
        {"id": "combat", "name": "Kampf"},
        {"id": "magic", "name": "Magie"},
        {"id": "social", "name": "Sozial"},
        {"id": "craft", "name": "Handwerk"},
        {"id": "disadvantage", "name": "Nachteile"},
    ],
    "perks": [],
}

DEFAULT_PERK_ENTRY: dict[str, Any] = {
    "id": "",
    "name": "",
    "type": "perk",
    "category": "general",
    "bp": 0,
    "effect": "",
    "description": "",
    "species": [],
    "requirements": [],
    "tags": [],
    "source": "",
    "enabled": True,
}


def _empty_catalog() -> dict[str, Any]:
    return deepcopy(DEFAULT_PERK_CATALOG)


def load_perk_catalog() -> dict[str, Any]:
    loaded = None
    for catalog_path in (
        resource_path("assets/config/perk_catalog.json"),
        data_path("game_rules/perk_catalog.json"),
    ):
        try:
            if not catalog_path.exists():
                continue
            loaded = json.loads(catalog_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                loaded = None
                continue
            break
        except Exception:
            loaded = None

    if not isinstance(loaded, dict):
        return _empty_catalog()

    catalog = _empty_catalog()
    catalog.update(loaded)
    if not isinstance(catalog.get("categories"), list):
        catalog["categories"] = []
    if not isinstance(catalog.get("perks"), list):
        catalog["perks"] = []
    catalog["perks"] = [_normalize_perk_entry(perk) for perk in catalog["perks"] if isinstance(perk, dict)]
    return catalog


def _normalize_perk_entry(perk: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(DEFAULT_PERK_ENTRY)
    normalized.update(perk)
    for key in ("species", "requirements", "tags"):
        if not isinstance(normalized.get(key), list):
            normalized[key] = []
    normalized["enabled"] = bool(normalized.get("enabled", True))
    return normalized


def get_enabled_perks(catalog: dict) -> list:
    perks = catalog.get("perks", []) if isinstance(catalog, dict) else []
    if not isinstance(perks, list):
        return []
    return [perk for perk in perks if isinstance(perk, dict) and perk.get("enabled", True)]


def get_perks_by_type(catalog: dict, perk_type: str) -> list:
    normalized_type = str(perk_type or "").strip()
    return [perk for perk in get_enabled_perks(catalog) if perk.get("type") == normalized_type]
