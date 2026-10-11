import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import texturepacks
import update_manager
import version
from build import (
    RELEASE_ZIP_NAME,
    TEXTUREPACK_RELEASES,
    _create_release_artifacts,
    _create_texturepack_artifacts,
)


class RuntimeTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(version.compare_versions("v1.3", "1.3.0"), 0)
        self.assertLess(version.compare_versions("1.3.0-rc.1", "1.3.0"), 0)
        self.assertGreater(version.compare_versions("1.10.0", "1.9.9"), 0)

    def test_texturepack_discovery_and_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(texturepacks, "app_base_dir", return_value=root):
                self.assertEqual(list(texturepacks.available_texturepacks()), ["diablo"])
                pack = root / "texturepacks" / "nature"
                (pack / "ui").mkdir(parents=True)
                (pack / "ui_layout.json").write_text('{"character_screen": {}}', encoding="utf-8")
                (pack / "manifest.json").write_text(json.dumps({"id": "nature", "name": "Nature", "version": "1.0.0", "min_app_version": "1.3.0"}), encoding="utf-8")
                self.assertIn("nature", texturepacks.available_texturepacks())
                self.assertEqual(texturepacks.theme_dir("missing"), texturepacks.diablo_dir())
                (pack / "manifest.json").write_text("{broken", encoding="utf-8")
                self.assertNotIn("nature", texturepacks.available_texturepacks())

    def test_texturepack_directory_is_created_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(texturepacks, "app_base_dir", return_value=root):
                created = texturepacks.ensure_texturepacks_dir()
            self.assertEqual(created, root / "texturepacks")
            self.assertTrue(created.is_dir())
            self.assertEqual(list(created.iterdir()), [])

    def test_release_artifacts_have_flat_root_and_exclude_user_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dist = root / "dist" / "AdventureTimeTool"
            (dist / "_internal").mkdir(parents=True)
            (dist / "data").mkdir()
            (dist / "texturepacks").mkdir()
            (dist / "_internal" / "data").mkdir()
            (dist / "AdventureTimeTool.exe").write_bytes(b"exe")
            (dist / "_internal" / "core.bin").write_bytes(b"core")
            (dist / "data" / "settings.json").write_text("private")
            (dist / "texturepacks" / "pack.txt").write_text("optional")
            (dist / "_internal" / "data" / "private.bin").write_bytes(b"private")
            (root / "release").mkdir()
            (root / "release" / "old.bin").write_bytes(b"old")

            archive, checksum = _create_release_artifacts(root)

            self.assertEqual(archive.name, RELEASE_ZIP_NAME)
            self.assertFalse((root / "release" / "old.bin").exists())
            with zipfile.ZipFile(archive) as zf:
                names = set(zf.namelist())
            self.assertIn("AdventureTimeTool.exe", names)
            self.assertIn("_internal/core.bin", names)
            self.assertFalse(any(name.startswith("AdventureTimeTool/") for name in names))
            self.assertFalse(
                any(
                    any(part.casefold() in {"data", "texturepacks"} for part in Path(name).parts)
                    for name in names
                )
            )
            expected = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(update_manager._expected_sha256(checksum.read_text()), expected)

    def test_texturepack_release_archives_have_installable_root_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release_dir = root / "release"
            release_dir.mkdir()
            for pack_id in TEXTUREPACK_RELEASES:
                source = root / "assets" / "themes" / pack_id
                (source / "ui").mkdir(parents=True)
                (source / "manifest.json").write_text(
                    json.dumps(
                        {
                            "id": pack_id,
                            "name": pack_id.title(),
                            "version": "1.0.0",
                        }
                    ),
                    encoding="utf-8",
                )
                (source / "ui_layout.json").write_text("{}", encoding="utf-8")
                (source / "ui" / "background.png").write_bytes(b"png")

            artifacts = _create_texturepack_artifacts(root, release_dir)

            self.assertEqual(
                {path.name for path in artifacts}, set(TEXTUREPACK_RELEASES.values())
            )
            for pack_id, archive_name in TEXTUREPACK_RELEASES.items():
                with zipfile.ZipFile(release_dir / archive_name) as zip_file:
                    names = set(zip_file.namelist())
                self.assertIn(f"{pack_id}/manifest.json", names)
                self.assertIn(f"{pack_id}/ui_layout.json", names)
                self.assertIn(f"{pack_id}/ui/background.png", names)

    def test_zip_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "package.zip"
            for hostile in ("../outside.txt", "data/settings.json", "_internal/data/cache.json"):
                with zipfile.ZipFile(path, "w") as zf:
                    zf.writestr("AdventureTimeTool.exe", "exe")
                    zf.writestr("_internal/core.txt", "core")
                    zf.writestr(hostile, "bad")
                with self.assertRaises(ValueError):
                    update_manager.validate_zip(path)

    def test_bad_checksum_never_extracts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("AdventureTimeTool.exe", "exe")
                zf.writestr("_internal/core.txt", "core")
            contents = {
                "https://example.com/app.zip": archive.getvalue(),
                "https://example.com/app.sha256": ("0" * 64).encode(),
            }
            def fake_download(url, target, limit):
                target.write_bytes(contents[url])
            with patch.object(update_manager, "data_path", return_value=root), patch.object(update_manager, "_download", side_effect=fake_download):
                with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                    update_manager.prepare_update({"version": "1.4.0", "zip_url": "https://example.com/app.zip", "sha_url": "https://example.com/app.sha256"})
                self.assertFalse((root / "1.4.0" / "payload").exists())

    def test_verified_archive_is_staged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("AdventureTimeTool.exe", "exe")
                zf.writestr("_internal/core.txt", "core")
            digest = hashlib.sha256(archive.getvalue()).hexdigest()
            contents = {"zip": archive.getvalue(), "sha": (digest + "  " + update_manager.ZIP_NAME).encode()}
            with patch.object(update_manager, "data_path", return_value=root), patch.object(update_manager, "_download", side_effect=lambda url, target, limit: target.write_bytes(contents[url])):
                payload = update_manager.prepare_update({"version": "1.4.0", "zip_url": "zip", "sha_url": "sha"})
            self.assertEqual((payload / "AdventureTimeTool.exe").read_text(), "exe")
            self.assertEqual((payload / "_internal" / "core.txt").read_text(), "core")

    def test_offline_release_check(self):
        with patch.object(update_manager, "_open", side_effect=OSError("offline")):
            self.assertIsNone(update_manager.check_latest_release())

    @unittest.skipUnless(sys.platform == "win32", "Windows updater")
    def test_worker_preserves_user_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "install"
            payload = root / "data" / "updates" / "1.4.0" / "payload"
            (root / "_internal").mkdir(parents=True)
            (root / "data" / "cache").mkdir(parents=True)
            (root / "texturepacks" / "nature").mkdir(parents=True)
            (payload / "_internal").mkdir(parents=True)
            (root / "AdventureTimeTool.exe").write_bytes(b"old")
            (root / "_internal" / "old.txt").write_text("old")
            (root / "data" / "settings.json").write_text("settings")
            (root / "data" / "cache" / "character.json").write_text("character")
            (root / "texturepacks" / "nature" / "manifest.json").write_text("pack")
            (payload / "AdventureTimeTool.exe").write_bytes(b"new")
            (payload / "_internal" / "new.txt").write_text("new")
            (payload.parent / update_manager.ZIP_NAME).write_bytes(b"zip")
            (payload.parent / update_manager.SHA_NAME).write_text("checksum")
            script = Path(__file__).resolve().parents[1] / "update_worker.ps1"
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ParentPid", "99999999", "-Payload", str(payload), "-InstallDir", str(root), "-SkipRestart"], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout + (payload.parent / "updater.log").read_text(errors="replace"))
            self.assertEqual((root / "AdventureTimeTool.exe").read_bytes(), b"new")
            self.assertEqual((root / "data" / "settings.json").read_text(), "settings")
            self.assertEqual((root / "data" / "cache" / "character.json").read_text(), "character")
            self.assertEqual((root / "texturepacks" / "nature" / "manifest.json").read_text(), "pack")
            self.assertFalse(payload.exists())
            self.assertFalse((payload.parent / "backup").exists())
            self.assertFalse((payload.parent / update_manager.ZIP_NAME).exists())
            self.assertFalse((payload.parent / update_manager.SHA_NAME).exists())


if __name__ == "__main__":
    unittest.main()
