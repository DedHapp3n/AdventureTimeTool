from __future__ import annotations

from typing import Any


DEFAULT_DEBUG_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "categories": {
        "paths": False,
        "theme": False,
        "cache": False,
        "save": False,
        "render": False,
        "character": False,
        "skills": False,
        "inventory": False,
        "equipment": False,
        "magic": False,
        "notes": False,
        "calculation": False,
        "roll20": False,
        "parser": False,
        "build": True,
    },
}

_debug_settings: dict[str, Any] = {
    "enabled": DEFAULT_DEBUG_SETTINGS["enabled"],
    "categories": dict(DEFAULT_DEBUG_SETTINGS["categories"]),
}


def normalize_debug_settings(settings: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    changed = False
    source = settings if isinstance(settings, dict) else {}
    if not isinstance(settings, dict):
        changed = True

    normalized = {
        "enabled": bool(source.get("enabled", DEFAULT_DEBUG_SETTINGS["enabled"])),
        "categories": {},
    }
    categories = source.get("categories", {})
    if not isinstance(categories, dict):
        categories = {}
        changed = True

    for category, default_value in DEFAULT_DEBUG_SETTINGS["categories"].items():
        if category in categories:
            normalized["categories"][category] = bool(categories.get(category))
        else:
            normalized["categories"][category] = bool(default_value)
            changed = True

    for category, value in categories.items():
        category_name = str(category).strip()
        if not category_name:
            changed = True
            continue
        if category_name not in normalized["categories"]:
            normalized["categories"][category_name] = bool(value)

    if source.get("enabled") != normalized["enabled"]:
        changed = True
    if source.get("categories") != normalized["categories"]:
        changed = True

    return normalized, changed


def set_debug_settings(settings: dict) -> None:
    global _debug_settings
    normalized, _changed = normalize_debug_settings(settings)
    _debug_settings = normalized


def get_debug_settings() -> dict:
    return {
        "enabled": bool(_debug_settings.get("enabled", False)),
        "categories": dict(_debug_settings.get("categories", {})),
    }


def _category_enabled(category: str) -> bool:
    categories = _debug_settings.get("categories", {})
    if not isinstance(categories, dict):
        return False
    return bool(categories.get(str(category), False))


def _emit(level: str, category: str, message: str) -> None:
    print(f"[{level}][{category}] {message}")


def log_debug(category: str, message: str) -> None:
    if bool(_debug_settings.get("enabled", False)) and _category_enabled(category):
        _emit("DEBUG", category, message)


def log_info(category: str, message: str) -> None:
    if bool(_debug_settings.get("enabled", False)) or _category_enabled(category):
        _emit("INFO", category, message)


def log_warning(category: str, message: str) -> None:
    _emit("WARNING", category, message)


def log_error(category: str, message: str) -> None:
    _emit("ERROR", category, message)
