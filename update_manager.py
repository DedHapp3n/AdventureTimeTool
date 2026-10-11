"""Download and verify Windows releases before handing them to the updater."""

import hashlib
import json
import re
import shutil
import stat
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from app_logger import log_warning
from app_paths import data_path
from version import APP_VERSION


LATEST_URL = "https://api.github.com/repos/DedHapp3n/AdventureTimeTool/releases/latest"
ZIP_NAME = "AdventureTimeTool-Windows-x64.zip"
SHA_NAME = ZIP_NAME + ".sha256"
MAX_ZIP_BYTES = 1_500_000_000
MAX_EXTRACTED_BYTES = 3_000_000_000


def _version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?", str(value).strip())
    if not match:
        raise ValueError(f"invalid version: {value!r}")
    parts = tuple(int(match.group(i) or 0) for i in (1, 2, 3))
    pre = match.group(4)
    identifiers = [] if pre is None else pre.split(".")
    if any(not item or (item.isdigit() and len(item) > 1 and item.startswith("0")) for item in identifiers):
        raise ValueError("invalid prerelease")
    return parts, identifiers


def compare_versions(left, right):
    a, ap = _version(left)
    b, bp = _version(right)
    if a != b:
        return (a > b) - (a < b)
    if not ap or not bp:
        return (not ap) - (not bp)
    for x, y in zip(ap, bp):
        xn, yn = x.isdigit(), y.isdigit()
        if xn and yn:
            difference = (int(x) > int(y)) - (int(x) < int(y))
        elif xn != yn:
            difference = -1 if xn else 1
        else:
            difference = (x > y) - (x < y)
        if difference:
            return difference
    return (len(ap) > len(bp)) - (len(ap) < len(bp))


def _open(url, timeout=8):
    if not url.startswith("https://"):
        raise ValueError("HTTPS required")
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "AdventureTimeTool-Updater", "Accept": "application/vnd.github+json"}), timeout=timeout)


def check_latest_release():
    """Return release metadata or None on offline/invalid releases."""
    try:
        with _open(LATEST_URL) as response:
            release = json.load(response)
        tag = release["tag_name"]
        if compare_versions(tag, APP_VERSION) <= 0:
            return None
        assets = {asset["name"]: asset["browser_download_url"] for asset in release.get("assets", []) if isinstance(asset, dict) and asset.get("state", "uploaded") == "uploaded"}
        if ZIP_NAME not in assets or SHA_NAME not in assets:
            log_warning("update", f"release {tag} missing ZIP or SHA256 asset")
            return None
        return {"version": tag, "zip_url": assets[ZIP_NAME], "sha_url": assets[SHA_NAME]}
    except Exception as exc:
        log_warning("update", f"release check failed: {exc}")
        return None


def _download(url, target, limit):
    with _open(url, timeout=20) as response, target.open("wb") as output:
        size = 0
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError("download exceeds size limit")
            output.write(chunk)


def _expected_sha256(text):
    match = re.fullmatch(r"\s*([0-9a-fA-F]{64})(?:\s+\*?" + re.escape(ZIP_NAME) + r")?\s*", text)
    if not match:
        raise ValueError("invalid SHA256 file")
    return match.group(1).lower()


def validate_zip(archive: Path):
    files = []
    names = set()
    total = 0
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename
            raw_parts = name.rstrip("/").split("/")
            path = PurePosixPath(name)
            parts = path.parts
            if not parts or name.startswith(("/", "\\")) or "\\" in name or ":" in name or any(part in ("", ".", "..") or part.endswith((" ", ".")) for part in raw_parts):
                raise ValueError(f"unsafe ZIP path: {name}")
            if any(part.casefold() in {"data", "texturepacks"} for part in parts):
                raise ValueError(f"protected path in ZIP: {name}")
            if any(part.split(".")[0].casefold() in {"con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"} for part in parts):
                raise ValueError(f"reserved Windows path in ZIP: {name}")
            if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("ZIP symlinks are not allowed")
            key = name.rstrip("/").casefold()
            if key in names:
                raise ValueError("duplicate ZIP path")
            names.add(key)
            total += info.file_size
            if total > MAX_EXTRACTED_BYTES:
                raise ValueError("ZIP expands beyond size limit")
            if not info.is_dir():
                files.append(info)
        if "adventuretimetool.exe" not in names or not any(name.startswith("_internal/") for name in names):
            raise ValueError("ZIP must contain AdventureTimeTool.exe and _internal/")
    return files


def prepare_update(release):
    """Return an extracted, verified payload path. No installed files are touched."""
    version = release["version"]
    _version(version)
    updates_root = data_path("updates").resolve()
    stage = updates_root / re.sub(r"[^A-Za-z0-9._-]", "_", version)
    if stage.resolve().parent != updates_root:
        raise ValueError("unsafe staging path")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    archive = stage / ZIP_NAME
    checksum = stage / SHA_NAME
    try:
        _download(release["sha_url"], checksum, 1024)
        expected = _expected_sha256(checksum.read_text(encoding="utf-8-sig"))
        _download(release["zip_url"], archive, MAX_ZIP_BYTES)
        digest = hashlib.sha256()
        with archive.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("SHA256 mismatch")
        files = validate_zip(archive)
        payload = stage / "payload"
        payload.mkdir()
        with zipfile.ZipFile(archive) as zf:
            for info in files:
                target = payload.joinpath(*PurePosixPath(info.filename).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
        return payload
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
