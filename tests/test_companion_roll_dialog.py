import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QAbstractSpinBox, QPushButton, QSpinBox

from ui_dialogs.companion_roll_dialog import CompanionRollDialog


APP = QApplication.instance() or QApplication([])


class CompanionRollDialogTests(unittest.TestCase):
    def tearDown(self):
        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        APP.processEvents()

    def test_shared_steppers_preview_and_auto_save(self):
        changes = []
        dialog = CompanionRollDialog(
            None,
            "Scout",
            [
                {"roll_id": "skill/swim", "roll_name": "Schwimmen"},
                {"roll_id": "skill/climb", "roll_name": "Klettern"},
            ],
            [{"roll_id": "skill/swim", "roll_name": "Schwimmen", "value": 5, "modifier": -2}],
            on_change=lambda rolls: changes.append(rolls),
        )
        dialog.show()
        APP.processEvents()

        self.assertEqual(dialog.table.columnCount(), 3)
        self.assertEqual(dialog.value_spin.buttonSymbols(), QAbstractSpinBox.NoButtons)
        self.assertEqual(dialog.modifier_spin.buttonSymbols(), QAbstractSpinBox.NoButtons)
        step_buttons = [button for button in dialog.findChildren(QPushButton) if "erh" in button.toolTip().lower() or "verring" in button.toolTip().lower()]
        self.assertEqual(len(step_buttons), 4)
        self.assertEqual(dialog.preview.text(), "Wurf: 1d20+5-2")
        button_texts = {button.text() for button in dialog.findChildren(QPushButton)}
        self.assertNotIn("Speichern", button_texts)
        self.assertNotIn("Abbrechen", button_texts)
        self.assertNotIn("Übernehmen", button_texts)
        self.assertIn("Schließen", button_texts)

        dialog.value_spin.setValue(6)
        self.assertEqual(changes[-1][0]["value"], 6)
        dialog.modifier_spin.setValue(-3)
        self.assertEqual(changes[-1][0]["modifier"], -3)
        self.assertEqual(dialog.preview.text(), "Wurf: 1d20+6-3")

        dialog.roll_combo.setCurrentIndex(1)
        self.assertEqual(dialog.table.rowCount(), 2)
        self.assertEqual(changes[-1][1], {"roll_id": "skill/climb", "roll_name": "Klettern", "value": 0, "modifier": 0})
        dialog.roll_combo.setCurrentIndex(0)
        dialog.roll_combo.setCurrentIndex(1)
        self.assertEqual(dialog.table.rowCount(), 2)

        dialog.findChild(QPushButton, "companionRollDelete").click()
        self.assertEqual(len(changes[-1]), 1)


if __name__ == "__main__":
    unittest.main()
