from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path


APP_NAME = "AdventureTimeTool"


def _add_data_arg() -> str:
    sep = ";" if platform.system().lower().startswith("win") else ":"
    return f"assets{sep}assets"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except Exception:
        print("Bitte installieren: pip install pyinstaller")
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

    print("[BUILD]", " ".join(cmd))
    exit_code = subprocess.call(cmd, cwd=str(root))
    if exit_code != 0:
        return exit_code

    _post_build_theme_check(root)
    return 0


def _discover_themes(base: Path) -> list[str]:
    themes_dir = base / "assets" / "themes"
    if not themes_dir.exists():
        return []
    names: list[str] = []
    for child in themes_dir.iterdir():
        if child.is_dir() and (child / "ui_layout.json").exists():
            names.append(child.name)
    return sorted(set(names))


def _post_build_theme_check(root: Path) -> None:
    src_themes = _discover_themes(root)
    dist_base = root / "dist" / APP_NAME
    dist_themes = _discover_themes(dist_base)
    if dist_themes:
        print("[BUILD CHECK] themes copied:", ", ".join(dist_themes))
    else:
        print("[BUILD CHECK] themes copied: <none>")
    missing = [name for name in src_themes if name not in dist_themes]
    if missing:
        print("[BUILD CHECK][WARN] missing themes in dist:", ", ".join(missing))


if __name__ == "__main__":
    raise SystemExit(main())
