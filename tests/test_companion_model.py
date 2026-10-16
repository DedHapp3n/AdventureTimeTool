import json
import tempfile
import unittest
from pathlib import Path

from data_loader import DataLoader


class CompanionModelTests(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader.__new__(DataLoader)
        self.loader.app_meta = {}
        self.loader.active_cache_path = ""
        self.loader.current_character_name = "Companion Test"

    def test_crud_duplicate_and_normalization(self):
        created = self.loader.add_companion(
            {
                "name": "Gertrude",
                "type": "Zombie",
                "can_roll": True,
                "rolls": [
                    {"roll_id": "allgemein/athletik", "roll_name": "Athletik", "value": "3"},
                    {"roll_id": "allgemein/athletik", "roll_name": "Athletik", "value": 9},
                ],
            }
        )
        self.assertEqual(created["id"], "companion_001")
        self.assertEqual(created["rolls"][0]["value"], 3)
        self.assertEqual(len(created["rolls"]), 1)

        created["hp"] = {"current": 18, "max": 24}
        self.assertTrue(self.loader.update_companion(created["id"], created))
        duplicate = self.loader.duplicate_companion(created["id"])
        self.assertEqual(duplicate["id"], "companion_002")
        self.assertEqual(duplicate["name"], "Gertrude (Kopie)")
        self.assertEqual(duplicate["hp"], {"current": 18, "max": 24})
        self.assertTrue(self.loader.delete_companion(created["id"]))
        self.assertEqual([item["id"] for item in self.loader.get_companions()], ["companion_002"])

    def test_persistence_roundtrip_and_character_isolation(self):
        companion = self.loader.add_companion(
            {
                "name": "Scout",
                "can_roll": True,
                "rolls": [{"roll_id": "allgemein/klettern", "roll_name": "Klettern", "value": 5}],
            }
        )
        payload = json.loads(json.dumps(self.loader.app_meta))
        other = DataLoader.__new__(DataLoader)
        other.app_meta = payload
        self.assertEqual(other.get_companion_roll_value(companion["id"], "allgemein/klettern"), 5)

        other.app_meta = {}
        self.assertEqual(other.get_companions(), [])

    def test_character_cache_file_roundtrip_preserves_companions(self):
        self.loader.cell_cache = {"Charakterbogen": {"G1": {"value": "Companion Test"}}}
        self.loader.active_cache_path = ""
        self.loader.current_character_name = "Companion Test"
        self.loader.source_file_path = ""
        self.loader._write_current_character_metadata = lambda *_args, **_kwargs: None
        self.loader._remember_clean_snapshot = lambda: None
        self.loader.add_companion({"name": "Gertrude", "type": "Zombie"})
        self.loader.add_companion({"name": "Scout", "can_roll": True})

        with tempfile.TemporaryDirectory() as directory:
            cache_path = Path(directory) / "character.json"
            self.assertTrue(self.loader.save_active_character_json(cache_path))
            payload = json.loads(cache_path.read_text(encoding="utf-8"))

        reloaded = DataLoader.__new__(DataLoader)
        reloaded._load_cache_payload(payload)
        self.assertEqual([item["name"] for item in reloaded.get_companions()], ["Gertrude", "Scout"])

    def test_roll_capability_filter(self):
        disabled = self.loader.add_companion({"name": "Packtier", "can_roll": False})
        enabled = self.loader.add_companion({"name": "Späher", "can_roll": True})
        self.assertEqual([item["id"] for item in self.loader.get_roll_capable_companions()], [enabled["id"]])
        self.assertNotEqual(disabled["id"], enabled["id"])

    def test_managed_portrait_normalize_duplicate_and_delete_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "external.png"
            source.write_bytes(b"portrait-data")
            cache_dir = root / "characters"
            cache_dir.mkdir()
            self.loader.active_cache_path = str(cache_dir / "Ferris.json")
            companion = self.loader.add_companion({"name": "Scout"})

            self.assertTrue(self.loader.set_companion_portrait_file(companion["id"], str(source)))
            stored = self.loader.get_companions()[0]
            self.assertEqual(stored["portrait"], "Ferris__companion_001__portrait.png")
            managed = Path(self.loader.get_companion_portrait_path(stored))
            self.assertEqual(managed.parent, cache_dir)
            self.assertEqual(managed.read_bytes(), b"portrait-data")

            reloaded = DataLoader.__new__(DataLoader)
            reloaded.app_meta = json.loads(json.dumps(self.loader.app_meta))
            reloaded.active_cache_path = self.loader.active_cache_path
            reloaded.current_character_name = self.loader.current_character_name
            self.assertEqual(Path(reloaded.get_companion_portrait_path(reloaded.get_companions()[0])), managed)

            normalized = self.loader._normalize_companion({**stored, "portrait": f"../{stored['portrait']}"}, 0)
            self.assertEqual(normalized["portrait"], stored["portrait"])
            duplicate = self.loader.duplicate_companion(companion["id"])
            duplicate_path = Path(self.loader.get_companion_portrait_path(duplicate))
            self.assertNotEqual(duplicate_path, managed)
            self.assertEqual(duplicate_path.read_bytes(), managed.read_bytes())

            self.assertTrue(self.loader.delete_companion(companion["id"]))
            self.assertFalse(managed.exists())
            self.assertTrue(duplicate_path.exists())
            self.assertTrue(source.exists())

            protected = cache_dir / "Ferris.json"
            protected.write_text("character", encoding="utf-8")
            self.assertEqual(self.loader.get_companion_portrait_path({"id": "companion_999", "portrait": "Ferris.json"}), "")


if __name__ == "__main__":
    unittest.main()
