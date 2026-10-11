"""Discovery and paths for optional external texture packs."""

import json
from pathlib import Path

from app_logger import log_warning_once
from app_paths import app_base_dir, resource_path
from version import APP_VERSION


def diablo_dir() -> Path:
    return resource_path("assets/themes/diablo")


def texturepacks_dir() -> Path:
    return app_base_dir() / "texturepacks"


def available_texturepacks() -> dict[str, Path]:
    packs = {"diablo": diablo_dir()}
    root = texturepacks_dir()
    if not root.is_dir():
        return packs
    try:
        children = list(root.iterdir())
    except OSError as exc:
        log_warning_once("theme", "texturepacks-enumeration", f"texturepack scan failed: {exc}")
        return packs
    for child in children:
        if not child.is_dir() or child.is_symlink():
            continue
        try:
            manifest = json.loads((child / "manifest.json").read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest must be an object")
            pack_id = manifest.get("id")
            if pack_id != child.name or pack_id == "diablo" or not pack_id.isascii() or not all(c.isalnum() or c in "_-" for c in pack_id):
                raise ValueError("invalid pack id")
            if not isinstance(manifest.get("name"), str) or not manifest["name"].strip():
                raise ValueError("missing name")
            if not isinstance(manifest.get("version"), str) or not manifest["version"].strip():
                raise ValueError("missing version")
            from update_manager import compare_versions
            minimum = manifest.get("min_app_version", "0.0.0")
            if compare_versions(APP_VERSION, minimum) < 0:
                continue
            if not (child / "ui_layout.json").is_file() or not (child / "ui").is_dir():
                raise ValueError("missing ui_layout.json or ui/")
            layout = json.loads((child / "ui_layout.json").read_text(encoding="utf-8"))
            if not isinstance(layout, dict) or not layout:
                raise ValueError("invalid ui_layout.json")
            packs[pack_id] = child
        except Exception as exc:
            log_warning_once("theme", f"texturepack:{child.name}", f"texturepack ignored: {child.name}: {exc}")
    return packs


def theme_dir(theme: str) -> Path:
    return available_texturepacks().get(str(theme), diablo_dir())


def layout_candidates(theme: str, filename: str, fallback_file: str | None = None) -> list[Path]:
    name = Path(filename).name
    return [theme_dir(theme) / name, diablo_dir() / (fallback_file or name)]
