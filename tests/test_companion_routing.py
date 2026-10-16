import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

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


if __name__ == "__main__":
    unittest.main()
