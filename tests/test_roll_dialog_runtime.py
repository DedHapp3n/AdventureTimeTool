import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QLineEdit, QPushButton, QSpinBox

from ui_dialogs.roll20_dialog import open_roll20_dialog
from ui_main import MainWindow


APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]


class RollDialogRuntimeTests(unittest.TestCase):
    def tearDown(self):
        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        APP.processEvents()

    def _open_dialog(self, model):
        captured = {}

        def capture_dialog(dialog):
            captured["dialog"] = dialog
            return QDialog.Rejected

        callbacks = {
            "build_command": lambda dice, keep, skill, manual, extras: MainWindow.build_roll20_command(
                None, dice, keep, skill, manual, extras
            ),
            "resolve_roll_asset_path": lambda _path: None,
        }
        style_context = {
            "roll_layout": {
                "counter": {
                    "value_text_color": "#f2d28b",
                    "selection_background": "#5f451e",
                    "selection_text_color": "#ffffff",
                    "value_frame": {"render_mode": "css"},
                },
                "paradigm": {"bonus": 10},
            }
        }
        with patch.object(QDialog, "exec", capture_dialog):
            open_roll20_dialog(None, model, callbacks, style_context)
        return captured["dialog"]

    @staticmethod
    def _paradigm_checkbox(dialog):
        return next(
            (
                checkbox
                for checkbox in dialog.findChildren(QCheckBox)
                if "Paradigma / Brennen" in checkbox.text()
            ),
            None,
        )

    @staticmethod
    def _command_edit(dialog):
        return next(
            line_edit
            for line_edit in dialog.findChildren(QLineEdit)
            if line_edit.placeholderText() == "/r 1d20"
        )

    def test_paradigm_is_available_for_normal_and_initiative_rolls(self):
        normal_dialog = self._open_dialog({"display_name": "Klettern", "skill_value": 7})
        self.assertIsNotNone(self._paradigm_checkbox(normal_dialog))

        initiative_dialog = self._open_dialog(
            {
                "display_name": "Klettern, Athletik, Ini-Wurf",
                "skill_value": 7,
                "is_initiative_context": True,
                "is_character_initiative": True,
                "fixed_extra_bonuses": [3],
                "paradigm_enabled": True,
            }
        )
        paradigm = self._paradigm_checkbox(initiative_dialog)
        command = self._command_edit(initiative_dialog)
        self.assertIsNotNone(paradigm)
        self.assertEqual(command.text(), "/r 1d20+7+3")
        paradigm.setChecked(True)
        self.assertEqual(command.text(), "/r 1d20+7+10+3")

    def test_character_initiative_model_enables_paradigm(self):
        captured = {}
        fake_window = SimpleNamespace(
            get_character_initiative_data=lambda: {"bonus": 3},
            _get_initiative_skill_source_info=lambda: (
                "initiative",
                {
                    "row": 12,
                    "display_value": 7,
                    "display_name": "Klettern, Athletik, Ini-Wurf",
                    "display_specialization": "",
                    "display_attribute_slots": ["G", "R", "", ""],
                },
            ),
            open_skill_roll_dialog=lambda **kwargs: captured.update(kwargs),
        )
        MainWindow.open_character_initiative_roll(fake_window)
        self.assertTrue(captured["roll_info"]["paradigm_enabled"])
        self.assertEqual(captured["roll_info"]["fixed_extra_bonuses"], [3])

    def test_paradigm_can_only_be_disabled_explicitly(self):
        dialog = self._open_dialog(
            {"display_name": "Spezialwurf", "skill_value": 4, "paradigm_enabled": False}
        )
        self.assertIsNone(self._paradigm_checkbox(dialog))

    def test_counter_line_edits_are_explicitly_styled_and_editable(self):
        dialog = self._open_dialog({"display_name": "Klettern", "skill_value": 7})
        spins = {
            spinbox.objectName(): spinbox
            for spinbox in dialog.findChildren(QSpinBox)
        }
        self.assertEqual(
            set(spins),
            {"rollAdvantages", "rollDisadvantages", "rollManualBonus"},
        )
        for spinbox in spins.values():
            style = spinbox.lineEdit().styleSheet()
            self.assertIn("color: #f2d28b", style)
            self.assertIn("background: transparent", style)
            self.assertIn("border: none", style)
            self.assertIn("selection-background-color: #5f451e", style)
            self.assertEqual(spinbox.lineEdit().alignment(), Qt.AlignCenter)

        manual = spins["rollManualBonus"]
        for value in (0, 1, 10, -1, -99):
            manual.lineEdit().setText(str(value))
            manual.interpretText()
            self.assertEqual(manual.value(), value)
            self.assertEqual(manual.lineEdit().text(), str(value))

        plus_buttons = [
            button
            for button in dialog.findChildren(QPushButton)
            if button.accessibleName() == "Erhöhen"
        ]
        minus_buttons = [
            button
            for button in dialog.findChildren(QPushButton)
            if button.accessibleName() == "Verringern"
        ]
        self.assertEqual(len(plus_buttons), 3)
        self.assertEqual(len(minus_buttons), 3)
        spins["rollAdvantages"].setValue(0)
        plus_buttons[0].click()
        self.assertEqual(spins["rollAdvantages"].value(), 1)
        minus_buttons[0].click()
        self.assertEqual(spins["rollAdvantages"].value(), 0)

    def test_attribute_slot_menu_has_all_values_and_stable_style(self):
        layout = json.loads(
            (ROOT / "assets/themes/diablo/skills_layout.json").read_text(encoding="utf-8")
        )
        fake_window = SimpleNamespace(
            load_skills_layout_config=lambda: layout,
            get_skill_attribute_slot_options=lambda: MainWindow.get_skill_attribute_slot_options(None),
            _safe_int=lambda value, default: MainWindow._safe_int(None, value, default),
        )
        slot = QPushButton()
        slot.setProperty("source_key", "skill")
        slot.setProperty("slot_index", 0)
        slot.setProperty("cell_ref", "V1")
        slot.setProperty("sheet_name", "Fertigkeiten")
        menu = MainWindow._create_skill_attribute_slot_menu(fake_window, slot, "K")
        self.assertEqual([action.text() for action in menu.actions()], ["Leer", "K", "G", "Z", "R", "I", "W", "C", "S"])
        self.assertGreaterEqual(menu.minimumWidth(), 120)
        self.assertIn("QMenu::item:selected", menu.styleSheet())
        self.assertIn("min-height: 30px", menu.styleSheet())

    def test_companion_actor_uses_only_companion_and_manual_values(self):
        dialog = self._open_dialog(
            {
                "display_name": "Klettern",
                "roll_label": "Klettern",
                "skill_value": 7,
                "fixed_extra_bonuses": [9],
                "fixed_advantages": 2,
                "inventory_modifiers": [{"label": "Seil +4", "modifier": 4}],
                "roll_actors": [
                    {"id": "companion_001", "name": "Gertrude", "type": "companion", "skill_value": 3}
                ],
            }
        )
        actor = dialog.findChild(QComboBox, "rollActorSelect")
        command = self._command_edit(dialog)
        self.assertIsNotNone(actor)
        self.assertEqual(command.text(), "/r 3d20kh1+7+9")
        actor.setCurrentIndex(1)
        self.assertEqual(command.text(), "/r 1d20+3")
        manual = dialog.findChild(QSpinBox, "rollManualBonus")
        manual.setValue(2)
        self.assertEqual(command.text(), "/r 1d20+3+2")

    def test_actor_selector_is_absent_without_roll_capable_companions(self):
        dialog = self._open_dialog({"display_name": "Klettern", "skill_value": 7, "roll_actors": []})
        self.assertIsNone(dialog.findChild(QComboBox, "rollActorSelect"))


if __name__ == "__main__":
    unittest.main()
