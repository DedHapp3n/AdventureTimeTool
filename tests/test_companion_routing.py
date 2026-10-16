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
from PySide6.QtTest import QTest

from data_loader import DataLoader
from ui_sections.companion_section import render_companion_screen
from ui_sections.inventory_section import _render_inventory_view_selector, render_inventory_screen


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

    def test_real_renderer_uses_character_panel_size_and_builds_scrollable_grid(self):
        layout = json.loads(
            (ROOT / "assets" / "themes" / "diablo" / "companion_layout.json").read_text(encoding="utf-8")
        )
        ui_layout = json.loads(
            (ROOT / "assets" / "themes" / "diablo" / "ui_layout.json").read_text(encoding="utf-8")
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
            main_ui_layout_config=ui_layout,
            create_panel_text=create_panel_text,
            get_inventory_roll_options=lambda: [],
            _safe_int=lambda value, default=0: int(value if value is not None else default),
            _open_character_field_dialog=lambda _title, _value: ("Bearbeiteter Companion", True),
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

        for expected_count in (1, 2, 3, 4):
            add_button().click()
            APP.processEvents()
            self.assertEqual(len(loader.get_companions()), expected_count)
            self.assertEqual(len(parent.findChildren(QFrame, "companionCard")), expected_count)

        cards = parent.findChildren(QFrame, "companionCard")
        first_card = cards[0]
        self.assertEqual(first_card.size().width(), 360)
        self.assertEqual(first_card.size().height(), 600)
        background = first_card.findChild(QLabel, "companionCardBackground")
        self.assertEqual(background.size(), first_card.size())
        self.assertEqual(background.pixmap().size(), first_card.size())
        self.assertIn("background: transparent", first_card.styleSheet())
        self.assertIsNotNone(first_card.parentWidget().findChild(QLabel, "alphaPixmapShadow"))
        portrait = first_card.findChild(QLabel, "companionPortrait")
        portrait_cfg = ui_layout["character_screen"]["text_layout"]["character_info_panel"]["portrait"]
        self.assertEqual((portrait.x(), portrait.y(), portrait.width(), portrait.height()), tuple(portrait_cfg[key] for key in ("x", "y", "w", "h")))
        self.assertEqual(first_card.findChildren(QLineEdit), [])
        self.assertEqual(first_card.findChildren(QSpinBox), [])
        self.assertEqual(first_card.findChildren(QCheckBox), [])
        editable_labels = [label for label in first_card.findChildren(QLabel) if label.property("panel_text_editable")]
        self.assertEqual(len(editable_labels), 12)
        character_info = ui_layout["character_screen"]["text_layout"]["character_info_panel"]
        title_rect = character_info["title"]
        title_label = next(label for label in editable_labels if label.text().startswith("Neuer Companion"))
        self.assertEqual((title_label.x(), title_label.y(), title_label.width(), title_label.height()), tuple(title_rect[key] for key in ("x", "y", "w", "h")))
        rows = {row["id"]: row for row in character_info["fields"]["rows"]}
        for resource in ("hp", "mp"):
            label = next(label for label in first_card.findChildren(QLabel) if label.text() == resource.upper())
            expected = rows[resource]["label_rect"]
            self.assertEqual((label.x(), label.y(), label.width(), label.height()), tuple(expected[key] for key in ("x", "y", "w", "h")))
            for key in ("current_rect", "max_rect"):
                expected = rows[resource][key]
                self.assertTrue(any((item.x(), item.y(), item.width(), item.height()) == tuple(expected[name] for name in ("x", "y", "w", "h")) for item in editable_labels))
        roll_marker = first_card.findChild(QPushButton, "companionCanRollMarker")
        self.assertIsNotNone(roll_marker)
        self.assertIn("checkmark_false.png", roll_marker.styleSheet())
        card_buttons = {button.text() for button in first_card.findChildren(QPushButton) if button.objectName() != "companionCanRollMarker"}
        self.assertEqual(card_buttons, {"Würfe", "Duplizieren", "Löschen"})
        self.assertEqual(len(saves), 4)
        for child in first_card.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            self.assertTrue(first_card.rect().contains(child.geometry()), (type(child).__name__, child.geometry()))

        scroll_area = parent.findChild(QScrollArea)
        grid = scroll_area.widget().layout()
        positions = {}
        for index in range(grid.count()):
            item = grid.itemAt(index)
            card = item.widget().findChild(QFrame, "companionCard") if item.widget() else None
            if card in cards:
                row, column, _row_span, _column_span = grid.getItemPosition(index)
                positions[card] = (row, column)
        self.assertEqual(set(positions.values()), {(0, 0), (0, 1), (0, 2), (1, 0)})
        self.assertGreater(scroll_area.verticalScrollBar().maximum(), 0)

        QTest.mouseDClick(title_label, Qt.LeftButton)
        APP.processEvents()
        self.assertEqual(loader.get_companions()[0]["name"], "Bearbeiteter Companion")

    def test_inventory_view_selector_is_vertical_and_right_aligned(self):
        layout = json.loads(
            (ROOT / "assets" / "themes" / "diablo" / "inventory_layout.json").read_text(encoding="utf-8")
        )
        screen_cfg = layout["inventory_screen"]
        parent = QWidget()
        parent.resize(screen_cfg["w"], screen_cfg["h"])
        parent.show()
        window = SimpleNamespace(
            current_inventory_view="inventory",
            _safe_int=lambda value, default: int(value if value is not None else default),
            on_inventory_view_clicked=lambda _view: None,
        )
        _render_inventory_view_selector(window, parent, screen_cfg)
        APP.processEvents()
        buttons = {button.text(): button for button in parent.findChildren(QPushButton)}
        inventory = buttons["Inventar"]
        companions = buttons["Companions"]
        selector_cfg = screen_cfg["view_selector"]
        category_cfg = screen_cfg["category_tabs"]
        self.assertEqual(selector_cfg["orientation"], "vertical")
        self.assertEqual(selector_cfg["anchor"], "top_right")
        self.assertEqual(inventory.x(), parent.width() - inventory.width() - selector_cfg["right_margin"])
        self.assertEqual(companions.x(), inventory.x())
        self.assertEqual(companions.y(), inventory.y() + inventory.height() + selector_cfg["gap"])
        self.assertGreaterEqual(inventory.x(), category_cfg["x"] + category_cfg["w"])
        self.assertLessEqual(inventory.x() + inventory.width(), screen_cfg["w"])
        self.assertLessEqual(companions.geometry().bottom(), screen_cfg["view_selector"]["top"] + 2 * selector_cfg["button_h"] + selector_cfg["gap"])
        companion_layout = json.loads((ROOT / "assets" / "themes" / "diablo" / "companion_layout.json").read_text(encoding="utf-8"))
        self.assertLess(companions.geometry().bottom(), companion_layout["companion_screen"]["cards_area"]["y"])
        self.assertTrue(inventory.isVisible())
        self.assertTrue(companions.isVisible())


if __name__ == "__main__":
    unittest.main()
