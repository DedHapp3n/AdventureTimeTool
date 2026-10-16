import json
import unittest

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

    def test_roll_capability_filter(self):
        disabled = self.loader.add_companion({"name": "Packtier", "can_roll": False})
        enabled = self.loader.add_companion({"name": "Späher", "can_roll": True})
        self.assertEqual([item["id"] for item in self.loader.get_roll_capable_companions()], [enabled["id"]])
        self.assertNotEqual(disabled["id"], enabled["id"])


if __name__ == "__main__":
    unittest.main()
