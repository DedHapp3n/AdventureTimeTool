import ast
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from data_loader import DataLoader
from ui_sections.companion_section import render_companion_screen
from ui_sections.inventory_section import render_inventory_screen


ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])


class CompanionRoutingTests(unittest.TestCase):
    def tearDown(self):
        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        APP.processEvents()

    def test_inventory_renderer_branches_before_inventory_content(self):
        source = (ROOT / "ui_sections" / "inventory_section.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        renderer = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "render_inventory_screen"
        )
        calls = [
            node.func.attr
            for node in ast.walk(renderer)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertIn("render_companion_screen", calls)
        self.assertIn("render_inventory_money_panel", calls)
        self.assertIn("render_inventory_category_tabs", calls)
        self.assertIn("render_inventory_active_category_table", calls)

        companion_call = source.index("window.render_companion_screen", renderer.lineno)
        inventory_data_call = source.index("window.get_inventory_display_data", renderer.lineno)
        self.assertLess(companion_call, inventory_data_call)

    def test_runtime_switch_uses_only_the_selected_view_renderer(self):
        calls = []
        content = QWidget()
        base = {
            "content_layer": content,
            "_inventory_loading": False,
            "_inventory_table_bindings": {},
            "current_inventory_category": "inventory_01",
            "_safe_int": lambda value, default: int(value if value is not None else default),
            "load_inventory_layout_config": lambda: {"inventory_screen": {"x": 0, "y": 0, "w": 800, "h": 600}},
            "load_companion_layout_config": lambda: {"companion_screen": {}},
            "render_companion_screen": lambda *_args: calls.append("companions"),
            "get_inventory_display_data": lambda: calls.append("inventory_data") or {"money": {}, "sections": []},
            "build_inventory_slot_categories": lambda _sections: [{"id": "inventory_01"}],
            "create_panel_text": lambda *_args, **_kwargs: None,
            "render_inventory_money_panel": lambda *_args: calls.append("money"),
            "render_inventory_category_tabs": lambda *_args: calls.append("tabs"),
            "render_inventory_active_category_table": lambda *_args: calls.append("table"),
            "on_inventory_view_clicked": lambda *_args: None,
        }
        companion_window = SimpleNamespace(**base, current_inventory_view="companions")
        render_inventory_screen(companion_window)
        self.assertEqual(calls, ["companions"])

        calls.clear()
        inventory_window = SimpleNamespace(**base, current_inventory_view="inventory")
        render_inventory_screen(inventory_window)
        self.assertEqual(calls, ["inventory_data", "money", "tabs", "table"])

    def test_real_renderer_shows_clickable_add_button_and_builds_three_cards(self):
        layout = json.loads(
            (ROOT / "assets" / "themes" / "diablo" / "companion_layout.json").read_text(encoding="utf-8")
        )
        loader = DataLoader.__new__(DataLoader)
        loader.app_meta = {}
        saves = []
        loader.save_active_character_json = lambda: saves.append(True) or True

        parent = QWidget()
        parent.resize(1420, 820)
        parent.show()

        def create_panel_text(container, rect, text, *_args, **_kwargs):
            label = QLabel(text, container)
            label.setGeometry(
                int(rect.get("x", 0)),
                int(rect.get("y", 0)),
                int(rect.get("w", 100)),
                int(rect.get("h", 30)),
            )
            label.show()
            return label

        window = SimpleNamespace(
            loader=loader,
            theme_asset_base_path=ROOT / "assets" / "themes" / "diablo",
            assets_dir=ROOT / "assets",
            create_panel_text=create_panel_text,
            get_inventory_roll_options=lambda: [],
        )

        def rerender(_section):
            for child in parent.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
                child.setParent(None)
                child.deleteLater()
            render_companion_screen(window, parent, layout)
            APP.processEvents()

        window.show_main_section = rerender
        render_companion_screen(window, parent, layout)
        APP.processEvents()

        def add_button():
            return next(
                button
                for button in parent.findChildren(QPushButton)
                if button.text() == "Companion hinzufügen"
            )

        first_add = add_button()
        self.assertTrue(first_add.isVisible())
        self.assertTrue(first_add.isEnabled())

        for expected_count in (1, 2, 3):
            add_button().click()
            APP.processEvents()
            self.assertEqual(len(loader.get_companions()), expected_count)
            self.assertEqual(len(parent.findChildren(QFrame, "companionCard")), expected_count)

        cards = parent.findChildren(QFrame, "companionCard")
        first_card = cards[0]
        placeholders = [editor.placeholderText() for editor in first_card.findChildren(QLineEdit)]
        self.assertIn("Name", placeholders)
        self.assertIn("Typ / Beschreibung", placeholders)
        self.assertEqual(placeholders.count("Feldname"), 3)
        self.assertEqual(placeholders.count("Wert"), 3)
        self.assertEqual(len(first_card.findChildren(QSpinBox)), 4)
        self.assertTrue(any(box.text() == "Kann würfeln" for box in first_card.findChildren(QCheckBox)))
        card_buttons = {button.text() for button in first_card.findChildren(QPushButton)}
        self.assertEqual(card_buttons, {"Würfe", "Duplizieren", "Löschen"})
        self.assertEqual(len(saves), 3)

        scroll_area = parent.findChild(QScrollArea)
        grid = scroll_area.widget().layout()
        positions = {}
        for index in range(grid.count()):
            item = grid.itemAt(index)
            if item.widget() in cards:
                row, column, _row_span, _column_span = grid.getItemPosition(index)
                positions[item.widget()] = (row, column)
        self.assertEqual(set(positions.values()), {(0, 0), (0, 1), (0, 2)})


if __name__ == "__main__":
    unittest.main()
