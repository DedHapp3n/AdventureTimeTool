import json
import tempfile
import unittest
from pathlib import Path

from data_loader import DataLoader


class CompanionModelTests(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader.__new__(DataLoader)
        self.loader.app_meta = {}

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


if __name__ == "__main__":
    unittest.main()
