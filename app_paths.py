from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from app_logger import DEFAULT_DEBUG_SETTINGS, normalize_debug_settings


DEFAULT_SETTINGS: dict[str, Any] = {
    "version": 1,
    "theme": "diablo",
    "themes": [],
    "last_character": "",
    "window": {
        "width": 1500,
        "height": 900,
    },
    "browser": {
        "last_url": "https://roll20.net/",
    },
    "debug": DEFAULT_DEBUG_SETTINGS,
}

DEFAULT_OVERRIDES: dict[str, Any] = {"version": 1, "overrides": {}}


def resource_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(relative_path: str) -> Path:
    return resource_base_dir() / Path(relative_path)


def user_data_dir() -> Path:
    data_dir = app_base_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def data_path(relative_path: str) -> Path:
    path = user_data_dir() / Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def config_path(relative_path: str) -> Path:
    path = user_data_dir() / "config" / Path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe_json_load(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_settings() -> tuple[dict[str, Any], bool]:
    settings_file = data_path("settings.json")
    loaded = _safe_json_load(settings_file)

    created = False
    settings = dict(DEFAULT_SETTINGS)
    settings["window"] = dict(DEFAULT_SETTINGS["window"])
    settings["browser"] = dict(DEFAULT_SETTINGS["browser"])
    settings["debug"] = {
        "enabled": DEFAULT_DEBUG_SETTINGS["enabled"],
        "categories": dict(DEFAULT_DEBUG_SETTINGS["categories"]),
    }

    if loaded is None:
        legacy_theme = resource_path("assets/config/theme_config.json")
        legacy = _safe_json_load(legacy_theme)
        if isinstance(legacy, dict):
            active_theme = legacy.get("active_theme")
            if isinstance(active_theme, str) and active_theme.strip():
                settings["theme"] = active_theme.strip()
        _write_json_atomic(settings_file, settings)
        created = True
        return settings, created

    changed = False
    settings["version"] = int(loaded.get("version", 1)) if str(loaded.get("version", "")).isdigit() else 1
    theme = loaded.get("theme", DEFAULT_SETTINGS["theme"])
    settings["theme"] = str(theme) if str(theme).strip() else DEFAULT_SETTINGS["theme"]
    loaded_themes = loaded.get("themes", [])
    if isinstance(loaded_themes, list):
        settings["themes"] = [str(item) for item in loaded_themes if str(item).strip()]
    else:
        settings["themes"] = []
    settings["last_character"] = str(loaded.get("last_character", "") or "")

    window_loaded = loaded.get("window", {})
    if isinstance(window_loaded, dict):
        width = window_loaded.get("width", DEFAULT_SETTINGS["window"]["width"])
        height = window_loaded.get("height", DEFAULT_SETTINGS["window"]["height"])
        try:
            settings["window"]["width"] = max(640, int(width))
        except Exception:
            settings["window"]["width"] = DEFAULT_SETTINGS["window"]["width"]
        try:
            settings["window"]["height"] = max(480, int(height))
        except Exception:
            settings["window"]["height"] = DEFAULT_SETTINGS["window"]["height"]

    browser_loaded = loaded.get("browser", {})
    if isinstance(browser_loaded, dict):
        last_url = str(browser_loaded.get("last_url", "") or "").strip()
        if last_url:
            settings["browser"]["last_url"] = last_url

    settings["debug"], debug_changed = normalize_debug_settings(loaded.get("debug"))
    changed = changed or debug_changed
    if changed:
        save_settings(settings)

    return settings, created


def save_settings(settings: dict[str, Any]) -> None:
    themes = settings.get("themes", [])
    if not isinstance(themes, list):
        themes = []
    payload = {
        "version": int(settings.get("version", 1)),
        "theme": str(settings.get("theme", DEFAULT_SETTINGS["theme"]) or DEFAULT_SETTINGS["theme"]),
        "themes": [str(item) for item in themes if str(item).strip()],
        "last_character": str(settings.get("last_character", "") or ""),
        "window": {
            "width": int(settings.get("window", {}).get("width", DEFAULT_SETTINGS["window"]["width"])),
            "height": int(settings.get("window", {}).get("height", DEFAULT_SETTINGS["window"]["height"])),
        },
        "browser": {
            "last_url": str(settings.get("browser", {}).get("last_url", DEFAULT_SETTINGS["browser"]["last_url"]) or DEFAULT_SETTINGS["browser"]["last_url"]),
        },
    }
    payload["debug"], _changed = normalize_debug_settings(settings.get("debug"))
    _write_json_atomic(data_path("settings.json"), payload)


def ensure_calculation_overrides_default() -> Path:
    target = config_path("calculation_overrides.json")
    if target.exists():
        return target
    source = resource_path("assets/config/calculation_overrides.json")
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    else:
        _write_json_atomic(target, DEFAULT_OVERRIDES)
    return target


def ensure_runtime_defaults() -> None:
    user_data_dir()
    (user_data_dir() / "cache").mkdir(parents=True, exist_ok=True)
    load_settings()
    ensure_calculation_overrides_default()

    current_character = data_path("current_character.json")
    if not current_character.exists():
        _write_json_atomic(
            current_character,
            {
                "active_cache": "",
                "character_name": "unknown_character",
                "source_file": "",
                "last_loaded": "",
            },
        )
