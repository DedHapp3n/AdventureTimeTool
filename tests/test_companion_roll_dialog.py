import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSpinBox, QPushButton, QSpinBox

from ui_dialogs.companion_roll_dialog import CompanionRollDialog
from ui_dialogs.roll_dialog_ui import RollAssetButton


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
            [{"roll_id": "skill/swim", "roll_name": "Schwimmen", "value": 5, "modifier": -2, "advantages": 1, "disadvantages": 0}],
            on_change=lambda rolls: changes.append(rolls),
        )
        dialog.show()
        APP.processEvents()

        self.assertEqual(dialog.table.columnCount(), 5)
        self.assertEqual(dialog.value_spin.buttonSymbols(), QAbstractSpinBox.NoButtons)
        self.assertEqual(dialog.modifier_spin.buttonSymbols(), QAbstractSpinBox.NoButtons)
        step_buttons = [button for button in dialog.findChildren(QPushButton) if "erh" in button.toolTip().lower() or "verring" in button.toolTip().lower()]
        self.assertEqual(len(step_buttons), 8)
        self.assertEqual(dialog.preview.text(), "Wurf: 2d20kh1+5-2")
        self.assertFalse(dialog._background.pixmap().isNull())
        self.assertTrue(dialog.windowFlags() & Qt.FramelessWindowHint)
        self.assertIsNotNone(dialog._frameless_drag_filter)
        self.assertIsInstance(dialog.delete_button, RollAssetButton)
        self.assertFalse(dialog.window_close_button.icon().isNull())
        self.assertEqual((dialog.width(), dialog.height()), (922, 622))
        self.assertGreater(dialog.width() / dialog.height(), 1.4)
        self.assertLess(dialog.table.x(), dialog.editor_panel.x())
        self.assertGreater(dialog.preview.y(), dialog.table.y())
        self.assertNotIn("QDialog {", dialog.styleSheet())
        button_texts = {button.text() for button in dialog.findChildren(QPushButton)}
        self.assertNotIn("Speichern", button_texts)
        self.assertNotIn("Abbrechen", button_texts)
        self.assertNotIn("Übernehmen", button_texts)
        self.assertNotIn("Schließen", button_texts)

        dialog.value_spin.setValue(6)
        self.assertEqual(changes[-1][0]["value"], 6)
        dialog.modifier_spin.setValue(-3)
        self.assertEqual(changes[-1][0]["modifier"], -3)
        dialog.advantages_spin.setValue(2)
        self.assertEqual(changes[-1][0]["advantages"], 2)
        dialog.disadvantages_spin.setValue(1)
        self.assertEqual(changes[-1][0]["disadvantages"], 1)
        self.assertEqual(dialog.preview.text(), "Wurf: 2d20kh1+6-3")
        dialog.advantages_spin.setValue(0)
        self.assertEqual(dialog.preview.text(), "Wurf: 2d20kl1+6-3")

        dialog.roll_combo.setCurrentIndex(1)
        self.assertEqual(dialog.table.rowCount(), 2)
        self.assertEqual(changes[-1][1], {"roll_id": "skill/climb", "roll_name": "Klettern", "value": 0, "modifier": 0, "advantages": 0, "disadvantages": 0})
        dialog.roll_combo.setCurrentIndex(0)
        dialog.roll_combo.setCurrentIndex(1)
        self.assertEqual(dialog.table.rowCount(), 2)

        dialog.findChild(QPushButton, "companionRollDelete").click()
        self.assertEqual(len(changes[-1]), 1)

        QTest.mouseClick(dialog.window_close_button, Qt.LeftButton)
        APP.processEvents()
        self.assertFalse(dialog.isVisible())

    def test_long_current_name_is_complete_and_shrinks_to_fit(self):
        name = "Sir Konstantin von der außerordentlich langen Companion-Gesellschaft zu Abenteuerstadt"
        dialog = CompanionRollDialog(None, name, [], [])
        self.assertEqual(dialog.title_label.text(), name)
        self.assertLess(dialog.title_label.font().pixelSize(), 22)
        self.assertGreaterEqual(dialog.title_label.font().pixelSize(), 5)
        self.assertLessEqual(dialog.title_label.fontMetrics().horizontalAdvance(name), dialog.title_label.width() - 8)


if __name__ == "__main__":
    unittest.main()
