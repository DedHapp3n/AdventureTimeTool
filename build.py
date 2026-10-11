from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from app_logger import log_info, log_warning


APP_NAME = "AdventureTimeTool"
RELEASE_ZIP_NAME = "AdventureTimeTool-Windows-x64.zip"
PROTECTED_RELEASE_ENTRIES = {"data", "texturepacks"}
TEXTUREPACK_RELEASES = {
    "nature": "AdventureTimeTool-TexturePack-Nature.zip",
    "necro": "AdventureTimeTool-TexturePack-Necro.zip",
    "shadow": "AdventureTimeTool-TexturePack-Shadow.zip",
}


def _add_data_args() -> list[str]:
    sep = ";" if platform.system().lower().startswith("win") else ":"
    return [
        f"assets/config{sep}assets/config",
        f"assets/ui_elements{sep}assets/ui_elements",
        f"assets/themes/diablo{sep}assets/themes/diablo",
        f"update_worker.ps1{sep}.",
    ]


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
        "--windowed",
        "--name",
        APP_NAME,
        "main.py",
    ]
    for entry in _add_data_args():
        cmd[-1:-1] = ["--add-data", entry]

    log_info("build", " ".join(cmd))
    exit_code = subprocess.call(cmd, cwd=str(root))
    if exit_code != 0:
        return exit_code

    _post_build_theme_check(root)
    _archive, _checksum = _create_release_artifacts(root)
    _create_texturepack_artifacts(root, _archive.parent)
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
    dist_base = root / "dist" / APP_NAME
    dist_themes = _discover_themes(dist_base)
    if dist_themes != ["diablo"]:
        log_warning("build", f"unexpected packaged themes: {dist_themes}")
    else:
        log_info("build", "only Diablo fallback bundled")


def _create_release_artifacts(root: Path) -> tuple[Path, Path]:
    root = root.resolve()
    dist_dir = (root / "dist" / APP_NAME).resolve()
    release_dir = (root / "release").resolve()
    if release_dir.parent != root:
        raise RuntimeError("unsafe release directory")
    if not (dist_dir / f"{APP_NAME}.exe").is_file() or not (dist_dir / "_internal").is_dir():
        raise RuntimeError(f"incomplete PyInstaller output: {dist_dir}")

    if release_dir.is_symlink() or release_dir.is_file():
        release_dir.unlink()
    elif release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir()

    archive = release_dir / RELEASE_ZIP_NAME
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zip_file:
        for source in sorted(dist_dir.rglob("*")):
            relative = source.relative_to(dist_dir)
            if not relative.parts or any(
                part.casefold() in PROTECTED_RELEASE_ENTRIES for part in relative.parts
            ):
                continue
            if source.is_symlink():
                raise RuntimeError(f"symlink not allowed in release: {relative}")
            if source.is_file():
                zip_file.write(source, relative.as_posix())

    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="ascii")
    log_info("build", f"release archive: {archive}")
    log_info("build", f"release checksum: {checksum}")
    return archive, checksum


def _create_texturepack_artifacts(root: Path, release_dir: Path) -> list[Path]:
    root = root.resolve()
    release_dir = release_dir.resolve()
    if release_dir.parent != root:
        raise RuntimeError("unsafe release directory")
    artifacts: list[Path] = []
    for pack_id, archive_name in TEXTUREPACK_RELEASES.items():
        source_dir = (root / "assets" / "themes" / pack_id).resolve()
        if source_dir.parent != (root / "assets" / "themes").resolve():
            raise RuntimeError(f"unsafe texturepack source: {source_dir}")
        if not (source_dir / "manifest.json").is_file() or not (
            source_dir / "ui_layout.json"
        ).is_file() or not (source_dir / "ui").is_dir():
            raise RuntimeError(f"incomplete texturepack source: {source_dir}")
        archive = release_dir / archive_name
        with zipfile.ZipFile(
            archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zip_file:
            for source in sorted(source_dir.rglob("*")):
                if source.is_symlink():
                    raise RuntimeError(
                        f"symlink not allowed in texturepack release: {source}"
                    )
                if source.is_file():
                    relative = Path(pack_id) / source.relative_to(source_dir)
                    zip_file.write(source, relative.as_posix())
        artifacts.append(archive)
        log_info("build", f"texturepack archive: {archive}")
    return artifacts


if __name__ == "__main__":
    raise SystemExit(main())
