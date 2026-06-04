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
    "warnings": {
        "browser": True,
        "theme": True,
        "cache": True,
        "character": True,
        "skills": True,
        "inventory": True,
        "equipment": True,
        "magic": True,
        "notes": True,
        "calculation": True,
        "roll20": True,
        "parser": True,
        "build": True,
    },
}

_debug_settings: dict[str, Any] = {
    "enabled": DEFAULT_DEBUG_SETTINGS["enabled"],
    "categories": dict(DEFAULT_DEBUG_SETTINGS["categories"]),
    "warnings": dict(DEFAULT_DEBUG_SETTINGS["warnings"]),
}
_warning_once_keys: set[tuple[str, str]] = set()


def normalize_debug_settings(settings: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
    changed = False
    source = settings if isinstance(settings, dict) else {}
    if not isinstance(settings, dict):
        changed = True

    normalized = {
        "enabled": bool(source.get("enabled", DEFAULT_DEBUG_SETTINGS["enabled"])),
        "categories": {},
        "warnings": {},
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

    warnings = source.get("warnings", {})
    if not isinstance(warnings, dict):
        warnings = {}
        changed = True
    for category, default_value in DEFAULT_DEBUG_SETTINGS["warnings"].items():
        if category in warnings:
            normalized["warnings"][category] = bool(warnings.get(category))
        else:
            normalized["warnings"][category] = bool(default_value)
            changed = True
    for category, value in warnings.items():
        category_name = str(category).strip()
        if not category_name:
            changed = True
            continue
        if category_name not in normalized["warnings"]:
            normalized["warnings"][category_name] = bool(value)

    if source.get("enabled") != normalized["enabled"]:
        changed = True
    if source.get("categories") != normalized["categories"]:
        changed = True
    if source.get("warnings") != normalized["warnings"]:
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
        "warnings": dict(_debug_settings.get("warnings", {})),
    }


def _category_enabled(category: str) -> bool:
    categories = _debug_settings.get("categories", {})
    if not isinstance(categories, dict):
        return False
    return bool(categories.get(str(category), False))


def _warning_enabled(category: str) -> bool:
    warnings = _debug_settings.get("warnings", {})
    if not isinstance(warnings, dict):
        return True
    return bool(warnings.get(str(category), True))


def _emit(level: str, category: str, message: str) -> None:
    print(f"[{level}][{category}] {message}")


def log_debug(category: str, message: str) -> None:
    if bool(_debug_settings.get("enabled", False)) and _category_enabled(category):
        _emit("DEBUG", category, message)


def log_info(category: str, message: str) -> None:
    if bool(_debug_settings.get("enabled", False)) or _category_enabled(category):
        _emit("INFO", category, message)


def log_warning(category: str, message: str) -> None:
    if _warning_enabled(category):
        _emit("WARNING", category, message)


def log_warning_once(category: str, key: str, message: str) -> None:
    normalized_key = (str(category), str(key))
    if normalized_key in _warning_once_keys:
        return
    _warning_once_keys.add(normalized_key)
    log_warning(category, message)


def log_error(category: str, message: str) -> None:
    _emit("ERROR", category, message)
