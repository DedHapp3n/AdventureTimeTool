from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit, QStyledItemDelegate, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen, QPixmap, QIcon
import re
import os
import json
from pathlib import Path

from data_loader import DataLoader
from formula_parser import FormulaParser
from ui_tabs.sheet_tab import SheetTab


class ReferenceBorderDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.border_cells = {}
        self.active_cell = None

    def set_border_cells(self, border_cells):
        self.border_cells = border_cells

    def set_active_cell(self, active_cell):
        self.active_cell = active_cell

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        border_info = self.border_cells.get((index.row(), index.column()))
        if border_info is not None:
            color = border_info["color"]
            indirect = border_info["indirect"]
            painter.save()
            pen = QPen(color, 2 if not indirect else 1)
            if indirect:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            rect = option.rect.adjusted(1, 1, -1, -1)
            painter.drawRect(rect)
            painter.restore()

        if self.active_cell == (index.row(), index.column()):
            painter.save()
            pen = QPen(QColor(212, 175, 55), 2)
            painter.setPen(pen)
            rect = option.rect.adjusted(3, 3, -3, -3)
            painter.drawRect(rect)
            painter.restore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Adventure Time Tool")
        self.resize(800, 600)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)

        self.loader = DataLoader()
        self.parser = FormulaParser()
        self.base_dir = Path(__file__).resolve().parent
        self.sheet_tabs = {}
        self.formula_changes = {}
        self.formula_data = {}
        self.current_formula_cell = None
        self.debug_visible = False
        self.reference_border_colors = [
            QColor(220, 53, 69),   # red
            QColor(13, 110, 253),  # blue
            QColor(25, 135, 84),   # green
            QColor(255, 128, 0),   # orange
            QColor(111, 66, 193),  # violet
            QColor(32, 201, 151),  # teal
            QColor(214, 51, 132),  # pink
            QColor(102, 16, 242),  # indigo
        ]
        self.highlighted_borders = {}
        self.current_highlight_table = None
        self.current_active_grid_cell = None
        self.current_reference_color_map = {}
        self.current_indirect_references = []

        self.main_ui_layout_config = self.load_main_ui_layout_config()

        canvas_cfg = self.main_ui_layout_config.get("canvas", {})
        canvas_width = int(canvas_cfg.get("width", 1024))
        canvas_height = int(canvas_cfg.get("height", 768))
        print(f"[UI_LAYOUT] canvas: {canvas_width}x{canvas_height}")
        print(f"[UI] canvas size: {canvas_width} {canvas_height}")
        self.setFixedSize(canvas_width, canvas_height)

        self.game_canvas = QWidget()
        self.game_canvas.setFixedSize(canvas_width, canvas_height)
        self.game_canvas.setStyleSheet("background-color: #101010;")
        self.setCentralWidget(self.game_canvas)

        frame_cfg = self.main_ui_layout_config.get("main_frame", {})
        frame_x = int(frame_cfg.get("x", 0))
        frame_y = int(frame_cfg.get("y", 0))
        frame_w = int(frame_cfg.get("w", canvas_width))
        frame_h = int(frame_cfg.get("h", canvas_height))
        frame_asset = frame_cfg.get("asset", "")
        print(f"[UI] main_frame geometry: {frame_x} {frame_y} {frame_w} {frame_h}")
        frame_asset_path = self.resolve_ui_asset_path(frame_asset) if frame_asset else None
        print(
            f"[UI_ASSET] main_frame: {frame_asset_path} "
            f"{frame_asset_path.exists() if frame_asset_path else False}"
        )

        self.main_frame_label = QLabel(self.game_canvas)
        self.main_frame_label.setGeometry(frame_x, frame_y, frame_w, frame_h)
        self.main_frame_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        frame_pixmap = self.load_ui_pixmap(frame_asset) if frame_asset else None
        if frame_pixmap is not None:
            if frame_pixmap.width() == frame_w and frame_pixmap.height() == frame_h:
                self.main_frame_label.setPixmap(frame_pixmap)
            else:
                self.main_frame_label.setPixmap(
                    frame_pixmap.scaled(
                        frame_w,
                        frame_h,
                        Qt.IgnoreAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
            self.main_frame_label.lower()
            self.main_frame_label.show()
            print(f"[UI] main_frame geometry: {self.main_frame_label.geometry()}")
            print(f"[UI] main_frame pixmap size: {frame_pixmap.size()}")
        else:
            self.main_frame_label.setStyleSheet("background-color: #1a1a1a;")
            missing_path = str(frame_asset_path) if frame_asset_path is not None else "(kein asset in JSON)"
            self.main_frame_error_label = QLabel(self.game_canvas)
            self.main_frame_error_label.setGeometry(frame_x + 10, frame_y + 10, max(220, frame_w - 20), 120)
            self.main_frame_error_label.setStyleSheet(
                "color: #ff4d4d; background: transparent; font-size: 14px; font-weight: bold;"
            )
            self.main_frame_error_label.setWordWrap(True)
            self.main_frame_error_label.setText(f"main_Frame.jpg nicht geladen\n{missing_path}")
            self.main_frame_error_label.raise_()
            self.main_frame_error_label.show()

        title_cfg = self.main_ui_layout_config.get("title_text", {})
        if title_cfg:
            title_text = str(title_cfg.get("text", ""))
            title_x = int(title_cfg.get("x", 0))
            title_y = int(title_cfg.get("y", 0))
            title_w = int(title_cfg.get("w", 320))
            title_h = int(title_cfg.get("h", 48))
            title_font_size = int(title_cfg.get("font_size", 28))
            title_color = str(title_cfg.get("color", "#f2d28b"))
            title_shadow_color = str(title_cfg.get("shadow_color", "#000000"))

            self.title_shadow_label = QLabel(self.game_canvas)
            self.title_shadow_label.setGeometry(title_x + 2, title_y + 2, title_w, title_h)
            self.title_shadow_label.setText(title_text)
            self.title_shadow_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.title_shadow_label.setStyleSheet(
                f"background: transparent; color: {title_shadow_color}; "
                f"font-size: {title_font_size}px; font-weight: 700;"
            )
            self.title_shadow_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.title_shadow_label.show()

            self.title_label = QLabel(self.game_canvas)
            self.title_label.setGeometry(title_x, title_y, title_w, title_h)
            self.title_label.setText(title_text)
            self.title_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.title_label.setStyleSheet(
                f"background: transparent; color: {title_color}; "
                f"font-size: {title_font_size}px; font-weight: 700;"
            )
            self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            self.title_shadow_label.raise_()
            self.title_label.raise_()
            self.title_label.show()

        close_cfg = self.main_ui_layout_config.get("window_close_button", {})
        close_x = int(close_cfg.get("x", 0))
        close_y = int(close_cfg.get("y", 0))
        close_w = int(close_cfg.get("w", 32))
        close_h = int(close_cfg.get("h", 32))
        close_asset = close_cfg.get("asset", "")
        close_asset_path = self.resolve_ui_asset_path(close_asset) if close_asset else None

        self.window_close_button = QPushButton(self.game_canvas)
        self.window_close_button.setGeometry(close_x, close_y, close_w, close_h)
        self.window_close_button.setText("")
        self.window_close_button.setCursor(Qt.PointingHandCursor)
        self.window_close_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; padding: 0px; }"
        )

        if close_asset_path is not None and close_asset_path.exists():
            close_pixmap = QPixmap(str(close_asset_path))
            if not close_pixmap.isNull():
                button_icon = QIcon(
                    close_pixmap.scaled(
                        close_w,
                        close_h,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self.window_close_button.setIcon(button_icon)
                self.window_close_button.setIconSize(self.window_close_button.size())
            else:
                print(f"[UI_ASSET] close button pixmap invalid: {close_asset_path}")
        else:
            print(f"[UI_ASSET] close button asset missing: {close_asset_path}")

        self.window_close_button.clicked.connect(self.close)
        self.window_close_button.raise_()
        self.window_close_button.show()

        settings_cfg = self.main_ui_layout_config.get("settings_button", {})
        settings_x = int(settings_cfg.get("x", 0))
        settings_y = int(settings_cfg.get("y", 0))
        settings_w = int(settings_cfg.get("w", 64))
        settings_h = int(settings_cfg.get("h", 64))
        settings_asset = settings_cfg.get("asset", "")
        settings_asset_path = self.resolve_ui_asset_path(settings_asset) if settings_asset else None

        self.settings_button = QPushButton(self.game_canvas)
        self.settings_button.setGeometry(settings_x, settings_y, settings_w, settings_h)
        self.settings_button.setText("")
        self.settings_button.setCursor(Qt.PointingHandCursor)
        self.settings_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; padding: 0px; }"
        )

        if settings_asset_path is not None and settings_asset_path.exists():
            settings_pixmap = QPixmap(str(settings_asset_path))
            if not settings_pixmap.isNull():
                settings_icon = QIcon(
                    settings_pixmap.scaled(
                        settings_w,
                        settings_h,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
                self.settings_button.setIcon(settings_icon)
                self.settings_button.setIconSize(self.settings_button.size())
            else:
                print(f"[UI_ASSET] settings button pixmap invalid: {settings_asset_path}")
        else:
            print(f"[UI_ASSET] settings button asset missing: {settings_asset_path}")

        self.settings_button.clicked.connect(self.on_settings_button_clicked)
        self.settings_button.raise_()
        self.settings_button.show()

        self.settings_tab = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_tab)

        # Button
        self.load_button = QPushButton("Excel laden")
        self.load_button.clicked.connect(self.load_excel)
        self.debug_button = QPushButton("Debug anzeigen")
        self.debug_button.clicked.connect(self.toggle_debug_panel)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.update_formula_list_for_current_tab)

        # Formula list (right side)
        self.formula_table = QTableWidget()
        self.formula_table.setColumnCount(2)
        self.formula_table.setHorizontalHeaderLabels(["ZELLE", "FORMEL"])
        self.formula_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.formula_table.currentItemChanged.connect(self.on_formula_selection_changed)

        # Formula editor (right bottom)
        self.cell_label = QLabel("Zelle: -")
        self.formula_editor = QTextEdit()
        self.references_label = QLabel("Referenzen: -")
        self.result_label = QLabel("Ergebnis: -")
        self.apply_button = QPushButton("Übernehmen")
        self.apply_button.clicked.connect(self.apply_formula_change)

        self.editor_widget = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_widget)
        self.editor_layout.addWidget(self.cell_label)
        self.editor_layout.addWidget(self.formula_editor)
        self.editor_layout.addWidget(self.references_label)
        self.editor_layout.addWidget(self.result_label)
        self.editor_layout.addWidget(self.apply_button)

        # Right side split: formula list (top) + editor (bottom)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.addWidget(self.formula_table)
        self.right_splitter.addWidget(self.editor_widget)
        self.right_splitter.setSizes([320, 220])

        # Split view: left tabs, right panel
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self.right_splitter)
        self.splitter.setSizes([600, 200])

        self.settings_layout.addWidget(self.load_button)
        self.settings_layout.addWidget(self.debug_button)
        self.settings_layout.addWidget(self.splitter)

        self.right_splitter.setVisible(False)

        if self.loader.cell_cache:
            self.create_tabs_from_cache()

    def resolve_ui_asset_path(self, filename):
        if not filename:
            return None
        return self.base_dir / "assets" / "ui" / filename

    def load_ui_pixmap(self, filename):
        if not filename:
            return None
        asset_path = self.resolve_ui_asset_path(filename)
        if asset_path is not None and asset_path.exists():
            pixmap = QPixmap(str(asset_path))
            print(f"[UI_ASSET] pixmap null: {pixmap.isNull()} {pixmap.size()}")
            if not pixmap.isNull():
                return pixmap
        return None

    def load_main_ui_layout_config(self):
        layout_path = self.base_dir / "assets" / "config" / "ui_layout.json"
        print(f"[UI_LAYOUT] layout: {layout_path} {layout_path.exists()}")
        try:
            if not layout_path.exists():
                return {}
            with open(layout_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}

    def on_settings_button_clicked(self):
        print("[UI] Settings clicked")

    def load_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Excel auswählen", "", "Excel Files (*.xlsx)"
        )

        if not file_path:
            return

        self.tabs.clear()
        self.clear_reference_highlights()
        self.sheet_tabs = {}

        self.loader.load_file(file_path)
        sheets = self.loader.get_sheets()

        for sheet_name in sheets:
            sheet = self.loader.get_sheet_object(sheet_name)
            self.sheet_tabs[sheet_name] = SheetTab(
                sheet_name,
                sheet,
                self.parser,
                lambda: self.sheet_tabs,
            )

        for sheet_tab in self.sheet_tabs.values():
            sheet_tab.evaluate_formulas()

        if self.sheet_tabs:
            first_tab = next(iter(self.sheet_tabs.values()))
            first_tab.export_to_json("data/character_cache.json")

        for sheet_name in sheets:
            data = self.sheet_tabs[sheet_name].get_data()
            self._create_tab_with_data(sheet_name, data)

        self.update_formula_list_for_current_tab(self.tabs.currentIndex())

    def create_tabs_from_cache(self):
        self.tabs.clear()
        self.clear_reference_highlights()
        self.sheet_tabs = {}

        for sheet_name in self.loader.get_sheets():
            data = self.loader.get_sheet_data(sheet_name)
            self._create_tab_with_data(sheet_name, data)

        self.update_formula_list_for_current_tab(self.tabs.currentIndex())

    def _create_tab_with_data(self, sheet_name, data):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        table = QTableWidget()
        table.setItemDelegate(ReferenceBorderDelegate(table))

        rows = len(data)
        cols = max(len(r) for r in data) if data else 0

        table.setRowCount(rows)
        table.setColumnCount(cols)
        table.setHorizontalHeaderLabels(
            [self.convert_column_index_to_excel_name(i) for i in range(cols)]
        )

        for i, row in enumerate(data):
            for j, value in enumerate(row):
                text = str(value) if value is not None else ""
                item = QTableWidgetItem(text)
                table.setItem(i, j, item)

        tab_layout.addWidget(table)
        self.tabs.addTab(tab, sheet_name)

    def update_formula_list_for_current_tab(self, index):
        self.formula_table.setRowCount(0)
        self.current_formula_cell = None
        self.cell_label.setText('Zelle: <span style="color:#666666">-</span>')
        self.formula_editor.setPlainText("")
        self.references_label.setText("Referenzen: -")
        self.result_label.setText("Ergebnis: -")
        self.clear_reference_highlights()

        if index < 0:
            return

        sheet_name = self.tabs.tabText(index)
        sheet_tab = self.sheet_tabs.get(sheet_name)
        self.formula_data[sheet_name] = {}

        formulas = []
        if sheet_tab is not None:
            sheet_cache = sheet_tab.get_cell_cache().get(sheet_name, {})
            for cell_ref, cell_info in sheet_cache.items():
                formula = cell_info.get("formula")
                if formula:
                    formulas.append((cell_ref, formula))
                    self.formula_data[sheet_name][cell_ref] = {
                        "formula": formula,
                        "references": cell_info.get("references", []),
                    }
        else:
            sheet_cache = self.loader.cell_cache.get(sheet_name, {})
            for cell_ref, cell_info in sheet_cache.items():
                formula = cell_info.get("formula")
                if formula:
                    formulas.append((cell_ref, formula))
                    self.formula_data[sheet_name][cell_ref] = {
                        "formula": formula,
                        "references": cell_info.get("references", []),
                    }

        self.formula_table.setRowCount(len(formulas))
        for i, (cell_ref, formula) in enumerate(formulas):
            self.formula_table.setItem(i, 0, QTableWidgetItem(cell_ref))
            self.formula_table.setItem(i, 1, QTableWidgetItem(formula))

    def on_formula_selection_changed(self, current, previous):
        if current is None:
            return

        row = current.row()
        cell_item = self.formula_table.item(row, 0)
        formula_item = self.formula_table.item(row, 1)

        if cell_item is None or formula_item is None:
            return

        cell_ref = cell_item.text()
        formula = formula_item.text()

        self.current_formula_cell = cell_ref
        self.cell_label.setText(f'Zelle: <span style="color:#d4af37">{cell_ref}</span>')
        self.formula_editor.setPlainText(formula)
        self.result_label.setText(f"Ergebnis: {self.evaluate_simple_formula(formula)}")
        sheet_index = self.tabs.currentIndex()
        if sheet_index >= 0:
            sheet_name = self.tabs.tabText(sheet_index)
            info = self.formula_data.get(sheet_name, {}).get(cell_ref)
            if info:
                self.highlight_references_in_grid(sheet_name, info["references"], cell_ref)
                self.references_label.setText(
                    self.build_colored_references_text(
                        info["references"],
                        self.current_indirect_references,
                    )
                )
            else:
                self.references_label.setText("Referenzen: -")
                self.clear_reference_highlights()

    def apply_formula_change(self):
        if self.current_formula_cell is None:
            return

        sheet_index = self.tabs.currentIndex()
        if sheet_index < 0:
            return

        sheet_name = self.tabs.tabText(sheet_index)
        new_formula = self.formula_editor.toPlainText()

        if sheet_name not in self.formula_changes:
            self.formula_changes[sheet_name] = {}

        new_references = self.extract_references(new_formula)
        self.formula_changes[sheet_name][self.current_formula_cell] = {
            "formula": new_formula,
            "references": new_references,
        }
        if sheet_name not in self.formula_data:
            self.formula_data[sheet_name] = {}
        self.formula_data[sheet_name][self.current_formula_cell] = {
            "formula": new_formula,
            "references": new_references,
        }
        sheet_tab = self.sheet_tabs.get(sheet_name)
        if sheet_tab is not None:
            sheet_tab.update_formula(self.current_formula_cell, new_formula)
            sheet_tab.evaluate_formulas()
        self.highlight_references_in_grid(sheet_name, new_references, self.current_formula_cell)
        self.references_label.setText(
            self.build_colored_references_text(
                new_references,
                self.current_indirect_references,
            )
        )
        self.result_label.setText(f"Ergebnis: {self.evaluate_simple_formula(new_formula)}")

        current_row = self.formula_table.currentRow()
        if current_row >= 0:
            self.formula_table.setItem(current_row, 1, QTableWidgetItem(new_formula))

    def toggle_debug_panel(self):
        self.debug_visible = not self.debug_visible
        self.right_splitter.setVisible(self.debug_visible)
        if self.debug_visible:
            self.debug_button.setText("Debug ausblenden")
        else:
            self.debug_button.setText("Debug anzeigen")

    def extract_references(self, formula):
        matches = re.findall(r"[A-Z]+[0-9]+", formula.upper())
        unique_matches = []
        seen = set()
        for match in matches:
            if match not in seen:
                seen.add(match)
                unique_matches.append(match)
        return unique_matches

    def highlight_references_in_grid(self, sheet_name, references, active_cell_ref=None):
        self.clear_reference_highlights()

        sheet_index = self.tabs.currentIndex()
        if sheet_index < 0:
            return

        current_tab = self.tabs.widget(sheet_index)
        if current_tab is None or current_tab.layout() is None:
            return

        table = current_tab.layout().itemAt(0).widget()
        if table is None:
            return

        border_cells = {}
        reference_color_map = {}
        indirect_references = []
        for i, cell_ref in enumerate(references):
            grid_pos = self.cell_ref_to_grid_pos(cell_ref)
            if grid_pos is None:
                continue

            row, col = grid_pos
            if row < 0 or col < 0 or row >= table.rowCount() or col >= table.columnCount():
                continue

            item = table.item(row, col)
            if item is None:
                continue

            color = self.reference_border_colors[i % len(self.reference_border_colors)]
            border_cells[(row, col)] = {"color": color, "indirect": False}
            reference_color_map[cell_ref] = color

            recursive_refs = self.get_all_references(sheet_name, cell_ref, {cell_ref})
            for recursive_ref in recursive_refs:
                rec_pos = self.cell_ref_to_grid_pos(recursive_ref)
                if rec_pos is None:
                    continue
                rec_row, rec_col = rec_pos
                if (
                    rec_row < 0
                    or rec_col < 0
                    or rec_row >= table.rowCount()
                    or rec_col >= table.columnCount()
                ):
                    continue
                rec_item = table.item(rec_row, rec_col)
                if rec_item is None:
                    continue
                if (rec_row, rec_col) not in border_cells:
                    weak_color = QColor(color)
                    weak_color.setAlpha(150)
                    border_cells[(rec_row, rec_col)] = {"color": weak_color, "indirect": True}
                    reference_color_map[recursive_ref] = weak_color
                    if recursive_ref not in indirect_references:
                        indirect_references.append(recursive_ref)

        self.highlighted_borders = border_cells
        self.current_reference_color_map = reference_color_map
        self.current_indirect_references = indirect_references
        self.current_highlight_table = table
        self.current_active_grid_cell = None

        if active_cell_ref is not None:
            active_pos = self.cell_ref_to_grid_pos(active_cell_ref)
            if active_pos is not None:
                a_row, a_col = active_pos
                if 0 <= a_row < table.rowCount() and 0 <= a_col < table.columnCount():
                    self.current_active_grid_cell = active_pos

        delegate = table.itemDelegate()
        if isinstance(delegate, ReferenceBorderDelegate):
            delegate.set_border_cells(self.highlighted_borders)
            delegate.set_active_cell(self.current_active_grid_cell)
        table.viewport().update()

    def clear_reference_highlights(self):
        if self.current_highlight_table is None:
            self.highlighted_borders = {}
            self.current_reference_color_map = {}
            self.current_indirect_references = []
            self.current_active_grid_cell = None
            return

        delegate = self.current_highlight_table.itemDelegate()
        if isinstance(delegate, ReferenceBorderDelegate):
            delegate.set_border_cells({})
            delegate.set_active_cell(None)
        self.current_highlight_table.viewport().update()

        self.highlighted_borders = {}
        self.current_reference_color_map = {}
        self.current_indirect_references = []
        self.current_active_grid_cell = None
        self.current_highlight_table = None

    def cell_ref_to_grid_pos(self, cell_ref):
        match = re.fullmatch(r"([A-Z]+)([0-9]+)", cell_ref.upper())
        if not match:
            return None

        col_letters, row_str = match.groups()
        row = int(row_str) - 1

        col = 0
        for letter in col_letters:
            col = col * 26 + (ord(letter) - ord("A") + 1)
        col -= 1

        return (row, col)

    def convert_column_index_to_excel_name(self, index):
        name = ""
        number = index + 1
        while number > 0:
            number, remainder = divmod(number - 1, 26)
            name = chr(ord("A") + remainder) + name
        return name

    def build_colored_references_text(self, direct_references, indirect_references):
        if not direct_references and not indirect_references:
            return "Referenzen: -"

        colored = []
        for cell_ref in direct_references:
            color = self.current_reference_color_map.get(cell_ref)
            if color is None:
                colored.append(cell_ref)
            else:
                colored.append(
                    f'<span style="color:{color.name()}">{cell_ref}</span>'
                )
        for cell_ref in indirect_references:
            color = self.current_reference_color_map.get(cell_ref)
            if color is None:
                colored.append(f"{cell_ref} (indirekt)")
            else:
                colored.append(
                    f'<span style="color:{color.name()}">{cell_ref} (indirekt)</span>'
                )
        return "Referenzen: " + ", ".join(colored)

    def get_all_references(self, sheet_name, cell_ref, visited):
        all_refs = []
        cell_info = self.formula_data.get(sheet_name, {}).get(cell_ref)
        if not cell_info:
            return all_refs

        for ref in cell_info.get("references", []):
            if ref in visited:
                continue
            visited.add(ref)
            all_refs.append(ref)
            all_refs.extend(self.get_all_references(sheet_name, ref, visited))
        return all_refs

    def evaluate_simple_formula(self, formula):
        sheet_index = self.tabs.currentIndex()
        if sheet_index < 0:
            return "Fehler: Kein aktives Sheet"

        sheet_name = self.tabs.tabText(sheet_index)
        sheet_tab = self.sheet_tabs.get(sheet_name)
        if sheet_tab is None:
            if self.current_formula_cell is None:
                return "Nicht unterstützt"
            cell_data = self.loader.cell_cache.get(sheet_name, {}).get(self.current_formula_cell)
            if not cell_data:
                return "Nicht unterstützt"
            cached_value = cell_data.get("value")
            return str(cached_value) if cached_value is not None else "Nicht unterstützt"
        result = sheet_tab.parser.evaluate_formula(
            sheet_name,
            formula,
            sheet_tab.get_cell_value_for_parser,
            cell_ref=self.current_formula_cell,
        )
        if result == "Nicht unterstützt":
            return result
        try:
            rounded = round(float(result))
        except Exception:
            return result
        if self.current_formula_cell and re.search(r"(HP|MP)", self.current_formula_cell.upper()):
            return str(int(rounded))
        return str(rounded)

    def get_cell_value_for_parser(self, sheet_name, cell_ref):
        normalized_sheet_name = self.resolve_sheet_name(sheet_name)
        if normalized_sheet_name is None:
            return None
        sheet_tab = self.sheet_tabs.get(normalized_sheet_name)
        if sheet_tab is None:
            return None
        cell_data = sheet_tab.get_cell_cache().get(normalized_sheet_name, {}).get(cell_ref)
        if not cell_data:
            return None
        if cell_data.get("formula"):
            return cell_data["formula"]
        return cell_data.get("value")

    def get_table_for_sheet(self, sheet_name):
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == sheet_name:
                tab = self.tabs.widget(i)
                if tab is None or tab.layout() is None:
                    return None
                return tab.layout().itemAt(0).widget()
        return None

    def resolve_sheet_name(self, sheet_name):
        for i in range(self.tabs.count()):
            tab_name = self.tabs.tabText(i)
            if tab_name == sheet_name:
                return tab_name
        for i in range(self.tabs.count()):
            tab_name = self.tabs.tabText(i)
            if tab_name.upper() == str(sheet_name).upper():
                return tab_name
        return None
