from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from app_logger import log_info, log_warning


APP_NAME = "AdventureTimeTool"


def _add_data_arg() -> str:
    sep = ";" if platform.system().lower().startswith("win") else ":"
    return f"assets{sep}assets"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except Exception:
        log_warning("build", "Bitte installieren: pip install pyinstaller")
        return 1

    root = Path(__file__).resolve().parent
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--add-data",
        _add_data_arg(),
        "main.py",
    ]

    log_info("build", " ".join(cmd))
    exit_code = subprocess.call(cmd, cwd=str(root))
    if exit_code != 0:
        return exit_code

    _post_build_theme_check(root)
    return 0


def _discover_themes(base: Path) -> list[str]:
    themes_dir = _assets_dir(base) / "themes"
    if not themes_dir.exists():
        return []
    names: list[str] = []
    for child in themes_dir.iterdir():
        if child.is_dir() and (child / "ui_layout.json").exists():
            names.append(child.name)
    return sorted(set(names))


def _assets_dir(base: Path) -> Path:
    direct = base / "assets"
    if direct.exists():
        return direct
    return base / "_internal" / "assets"


def _post_build_theme_check(root: Path) -> None:
    src_themes = _discover_themes(root)
    dist_base = root / "dist" / APP_NAME
    dist_themes = _discover_themes(dist_base)
    if dist_themes:
        log_info("build", f"themes copied: {', '.join(dist_themes)}")
    else:
        log_info("build", "themes copied: <none>")
    missing = [name for name in src_themes if name not in dist_themes]
    if missing:
        log_warning("build", f"missing themes in dist: {', '.join(missing)}")


if __name__ == "__main__":
    raise SystemExit(main())
