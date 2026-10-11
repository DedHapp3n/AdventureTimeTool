import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QLabel

from ui_main import MainWindow


APP = QApplication.instance() or QApplication([])
ROOT = Path(__file__).resolve().parents[1]


class RecordingLoader:
    def __init__(self, cell_cache=None):
        self.cell_cache = cell_cache or {}
        self.writes = []

    def set_cell_value(self, sheet, cell, value):
        self.writes.append((sheet, cell, value))


class CharacterRegressionTests(unittest.TestCase):
    def tearDown(self):
        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        APP.processEvents()

    @staticmethod
    def _perk_label(table_type="perk"):
        label = QLabel()
        label.setProperty("character_perk_table_type", table_type)
        label.setProperty("character_perk_row", 5)
        label.setProperty("character_perk_sheet_name", "Charakterbogen")
        label.setProperty("character_perk_name_cell_ref", "A5")
        label.setProperty("character_perk_bp_cell_ref", "B5")
        label.setProperty("character_perk_effect_cell_ref", "C5")
        label.setProperty("character_perk_editable", True)
        return label

    def test_perk_and_disadvantage_single_click_info_is_read_only(self):
        for table_type in ("perk", "disadvantage"):
            values = {
                "A5": "Sehr langer Name",
                "B5": "12",
                "C5": "Vollständige Wirkung ohne Abschneiden",
            }
            loader = RecordingLoader()
            window = SimpleNamespace(
                loader=loader,
                get_cache_display_value=lambda _sheet, cell, _fallback: values.get(cell, ""),
            )
            window._character_perk_row_values = lambda widget: MainWindow._character_perk_row_values(
                window, widget
            )
            label = self._perk_label(table_type)
            with patch("ui_main.QToolTip.showText") as show_tooltip:
                shown = MainWindow._show_character_perk_row_info(window, label)
            self.assertTrue(shown)
            tooltip = show_tooltip.call_args.args[1]
            self.assertIn("Sehr langer Name", tooltip)
            self.assertIn("12", tooltip)
            self.assertIn("Vollständige Wirkung ohne Abschneiden", tooltip)
            self.assertEqual(loader.writes, [])

    def test_empty_perk_row_has_no_single_click_info(self):
        loader = RecordingLoader()
        window = SimpleNamespace(
            loader=loader,
            get_cache_display_value=lambda *_args: "",
        )
        window._character_perk_row_values = lambda widget: MainWindow._character_perk_row_values(
            window, widget
        )
        with patch("ui_main.QToolTip.showText") as show_tooltip:
            shown = MainWindow._show_character_perk_row_info(window, self._perk_label())
        self.assertFalse(shown)
        show_tooltip.assert_not_called()
        self.assertEqual(loader.writes, [])

    def test_double_click_cancels_pending_info(self):
        callbacks = []
        shown = []
        window = SimpleNamespace(
            _character_perk_info_click_token=0,
            _show_character_perk_row_info=lambda widget: shown.append(widget),
        )
        window._show_character_perk_row_info = lambda widget: shown.append(widget)
        label = self._perk_label()
        with patch("ui_main.QTimer.singleShot", side_effect=lambda _delay, callback: callbacks.append(callback)):
            MainWindow._schedule_character_perk_row_info(window, label)
        with patch("ui_main.QToolTip.hideText"):
            MainWindow._cancel_character_perk_row_info(window)
        callbacks[0]()
        self.assertEqual(shown, [])

    def test_perk_click_events_route_info_and_picker_separately(self):
        calls = []
        window = SimpleNamespace(
            _schedule_character_perk_row_info=lambda widget: calls.append(("info", widget)),
            _cancel_character_perk_row_info=lambda: calls.append(("cancel", None)),
            _open_character_perk_picker_for_widget=lambda widget: calls.append(("picker", widget)) or True,
        )
        label = self._perk_label()
        press = SimpleNamespace(
            type=lambda: QEvent.MouseButtonPress,
            button=lambda: Qt.LeftButton,
        )
        double_click = SimpleNamespace(
            type=lambda: QEvent.MouseButtonDblClick,
            button=lambda: Qt.LeftButton,
        )
        self.assertFalse(MainWindow._handle_character_perk_label_event(window, label, press))
        self.assertEqual(calls, [("info", label)])
        self.assertTrue(
            MainWindow._handle_character_perk_label_event(window, label, double_click)
        )
        self.assertEqual(calls, [("info", label), ("cancel", None), ("picker", label)])

    def test_perk_picker_select_and_delete_keep_existing_writes(self):
        label = self._perk_label("perk")
        for picker_result, expected in (
            (
                {"action": "select", "entry": {"name": "Flink", "bp": 8, "effect": "Initiative +4", "id": "flink"}},
                [("Charakterbogen", "A5", "Flink"), ("Charakterbogen", "B5", "8"), ("Charakterbogen", "C5", "Initiative +4")],
            ),
            (
                {"action": "delete"},
                [("Charakterbogen", "A5", ""), ("Charakterbogen", "B5", ""), ("Charakterbogen", "C5", "")],
            ),
        ):
            loader = RecordingLoader()
            recalculations = []
            window = SimpleNamespace(
                loader=loader,
                _character_edit_cfg={"save_on_change": True},
                _character_debug=lambda _message: None,
                _recalculate_after_user_edit=lambda **kwargs: recalculations.append(kwargs),
            )
            with patch("ui_main.open_perk_picker", return_value=picker_result):
                handled = MainWindow._open_character_perk_picker_for_widget(window, label)
            self.assertTrue(handled)
            self.assertEqual(loader.writes, expected)
            self.assertEqual(len(recalculations), 1)

    def test_body_and_mind_headers_are_read_only_but_attributes_are_not(self):
        source = (ROOT / "ui_sections" / "character_section.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        editor_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "_create_character_value_editor" or len(node.args) < 3:
                continue
            if isinstance(node.args[2], ast.Constant) and isinstance(node.args[2].value, str):
                editor_calls.append((node.args[2].value, {kw.arg: kw.value for kw in node.keywords}))
        header_calls = {name: keywords for name, keywords in editor_calls if name in ("body", "mind")}
        self.assertEqual(set(header_calls), {"body", "mind"})
        for keywords in header_calls.values():
            self.assertIsInstance(keywords.get("editable"), ast.Constant)
            self.assertFalse(keywords["editable"].value)
        self.assertTrue(
            any(name not in ("body", "mind") and "editable" not in keywords for name, keywords in editor_calls)
        )

    @staticmethod
    def _initiative_window(cell_cache, source_infos=None):
        loader = RecordingLoader(cell_cache)
        window = SimpleNamespace(
            loader=loader,
            skill_source_infos=source_infos or {},
            ensure_skill_source_infos_ready=lambda: None,
            get_skill_sheet_mapping_config=lambda: {
                "sheet": "Fertigkeiten",
                "name_col": "D",
                "attribute_cols": ["V", "X", "Z", "AB"],
                "value_formula_col": "AD",
                "specialization_col": "AG",
                "note_col": "BE",
            },
            get_skill_block_config_for_row=lambda _row: {"category_id": "allgemein"},
            format_character_display_value=lambda value, _kind: str(int(float(value))),
        )
        window.normalize_skill_name = lambda value: MainWindow.normalize_skill_name(window, value)
        window._is_initiative_text = lambda value: MainWindow._is_initiative_text(window, value)
        window.get_cache_cell_value = lambda sheet, cell, fallback=None: MainWindow.get_cache_cell_value(
            window, sheet, cell, fallback
        )
        window._extract_numeric_value = lambda value: MainWindow._extract_numeric_value(window, value)
        window._to_float_or_none = lambda value: MainWindow._to_float_or_none(window, value)
        window.get_skill_attribute_cells_for_row = lambda row, _block=None: [
            f"V{row}", f"X{row}", f"Z{row}", f"AB{row}"
        ]
        window.get_skill_attribute_slot_values_from_row = lambda row, _block=None: [
            str(MainWindow.get_cache_cell_value(window, "Fertigkeiten", f"{col}{row}", "") or "")
            for col in ("V", "X", "Z", "AB")
        ]
        window.get_clean_skill_cache_text = lambda sheet, cell: MainWindow.get_clean_skill_cache_text(
            window, sheet, cell
        )
        window.get_skill_lookup_value = lambda _block, letter: {"R": 4, "I": 3}.get(letter)
        window.get_skill_formula_text = lambda sheet, cell: MainWindow.get_skill_formula_text(
            window, sheet, cell
        )
        window.extract_skill_bonus_cell_from_formula = lambda formula, source="": MainWindow.extract_skill_bonus_cell_from_formula(
            window, formula, source
        )
        window.infer_skill_bonus_cell_from_array_formula = lambda sheet, row, cell: MainWindow.infer_skill_bonus_cell_from_array_formula(
            window, sheet, row, cell
        )
        window.get_numeric_cache_value = lambda sheet, cell: MainWindow.get_numeric_cache_value(
            window, sheet, cell
        )
        window._coerce_skill_numeric_value = lambda value: MainWindow._coerce_skill_numeric_value(
            window, value
        )
        window._calculate_initiative_skill_value_from_cache_row = lambda sheet, row, value_col, block, slots: MainWindow._calculate_initiative_skill_value_from_cache_row(
            window, sheet, row, value_col, block, slots
        )
        window._find_initiative_skill_cache_row = lambda: MainWindow._find_initiative_skill_cache_row(window)
        window._initiative_skill_source_from_fertigkeiten_cache = lambda: MainWindow._initiative_skill_source_from_fertigkeiten_cache(window)
        return window

    def test_initiative_falls_back_to_json_style_cache_row(self):
        cache = {
            "Fertigkeiten": {
                "D42": {"value": "Klettern / Athletik / Ini-Wurf"},
                "AD42": {"value": 9},
                "AG42": {"value": "Parcour"},
                "V42": {"value": "R"},
                "X42": {"value": "I"},
            }
        }
        missing_definition = {
            "allgemein/klettern_athletik_ini_wurf": {
                "skill_id": "klettern_athletik_ini_wurf",
                "display_name": "Klettern, Athletik, Ini-Wurf",
                "row": None,
            }
        }
        window = self._initiative_window(cache, missing_definition)
        source_key, info = MainWindow._get_initiative_skill_source_info(window)
        self.assertEqual(source_key, "cache/initiative-42")
        self.assertEqual(info["row"], 42)
        self.assertEqual(info["display_value"], "9")
        self.assertEqual(info["display_attribute_slots"][:2], ["R", "I"])

    def test_initiative_fallback_calculates_legacy_array_formula_import(self):
        cache = {
            "Fertigkeiten": {
                "D15": {"value": "Klettern, Athletik, Ini-Wurf"},
                "AD15": {"value": "<openpyxl.worksheet.formula.ArrayFormula object>"},
                "V15": {"value": "R"},
                "X15": {"value": "I"},
                "BW24": {"value": 2},
            }
        }
        window = self._initiative_window(cache)
        _source_key, info = MainWindow._get_initiative_skill_source_info(window)
        self.assertEqual(info["row"], 15)
        self.assertEqual(info["display_value"], "9")

    def test_legacy_klettern_athletik_name_is_recognized(self):
        window = self._initiative_window({"Fertigkeiten": {}})
        self.assertTrue(MainWindow._is_initiative_text(window, "Klettern, Athletik"))
        self.assertTrue(MainWindow._is_initiative_text(window, "Initiative"))
        self.assertTrue(MainWindow._is_initiative_text(window, "Ini_Wurf"))
        self.assertFalse(MainWindow._is_initiative_text(window, "Schwimmen"))

    def test_missing_initiative_message_has_explicit_readable_style(self):
        captured = {}

        class FakeMessageBox:
            Information = 1
            Ok = 2

            def __init__(self, _parent):
                captured["box"] = self

            def setIcon(self, value):
                captured["icon"] = value

            def setWindowTitle(self, value):
                captured["title"] = value

            def setText(self, value):
                captured["text"] = value

            def setStandardButtons(self, value):
                captured["buttons"] = value

            def setStyleSheet(self, value):
                captured["style"] = value

            def exec(self):
                captured["executed"] = True

        with patch("ui_main.QMessageBox", FakeMessageBox):
            MainWindow._show_initiative_missing_message(SimpleNamespace())
        self.assertEqual(captured["title"], "Initiative")
        self.assertIn("Ini-Wurf nicht gefunden", captured["text"])
        self.assertIn("color: #eadfca", captured["style"])
        self.assertIn("background-color: #17120e", captured["style"])
        self.assertTrue(captured["executed"])


if __name__ == "__main__":
    unittest.main()
