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
    return subprocess.call(cmd, cwd=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
