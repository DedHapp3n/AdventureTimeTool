from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit, QStyledItemDelegate, QFrame, QDialog
)
from PySide6.QtCore import Qt, QEvent
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
        self.theme_config_path = self.base_dir / "assets" / "config" / "theme_config.json"
        self.theme_config = self.load_theme_config()
        self.active_theme = self.get_active_theme()
        self.theme_asset_base_path = self.get_theme_asset_base_path()
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
        self.current_main_section = "character"
        self.nav_buttons = {}
        self.settings_dialog = None
        self.game_canvas = QWidget()
        self.game_canvas.setStyleSheet("background-color: #101010;")
        self.setCentralWidget(self.game_canvas)
        self.reload_theme()

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
        primary = self.get_theme_asset_base_path() / filename
        if primary.exists():
            return primary
        fallback = self.base_dir / "assets" / "themes" / "diablo" / "ui" / filename
        if fallback.exists():
            return fallback
        print(f"[THEME] missing asset: {primary}")
        return primary

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
        layout_path = self.get_theme_layout_path()
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

    def load_theme_config(self):
        default = {"active_theme": "diablo", "themes": ["diablo", "nature"]}
        try:
            if not self.theme_config_path.exists():
                return default
            content = self.theme_config_path.read_text(encoding="utf-8").strip()
            if not content:
                return default
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return default
            themes = parsed.get("themes")
            if not isinstance(themes, list) or not themes:
                parsed["themes"] = default["themes"]
            if not isinstance(parsed.get("active_theme"), str):
                parsed["active_theme"] = parsed["themes"][0]
            return parsed
        except Exception:
            return default

    def save_theme_config(self):
        try:
            self.theme_config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.theme_config_path, "w", encoding="utf-8") as f:
                json.dump(self.theme_config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_active_theme(self):
        themes = self.theme_config.get("themes", [])
        if not isinstance(themes, list) or not themes:
            themes = ["diablo"]
            self.theme_config["themes"] = themes
        active = self.theme_config.get("active_theme", themes[0])
        if active not in themes:
            active = themes[0]
            self.theme_config["active_theme"] = active
        return str(active)

    def get_theme_layout_path(self):
        active = self.get_active_theme()
        layout_path = self.base_dir / "assets" / "themes" / active / "ui_layout.json"
        if layout_path.exists():
            return layout_path
        fallback = self.base_dir / "assets" / "themes" / "diablo" / "ui_layout.json"
        print(f"[THEME] missing layout: {layout_path}, fallback: {fallback}")
        return fallback

    def get_theme_asset_base_path(self):
        active = self.get_active_theme()
        base = self.base_dir / "assets" / "themes" / active / "ui"
        if base.exists():
            return base
        fallback = self.base_dir / "assets" / "themes" / "diablo" / "ui"
        print(f"[THEME] missing asset base: {base}, fallback: {fallback}")
        return fallback

    def reload_theme(self):
        self.theme_config = self.load_theme_config()
        self.active_theme = self.get_active_theme()
        self.theme_asset_base_path = self.get_theme_asset_base_path()
        self.main_ui_layout_config = self.load_main_ui_layout_config()
        self.theme_style = self.main_ui_layout_config.get("theme_style", {})
        self.nav_buttons = {}

        for child in self.game_canvas.findChildren(QWidget):
            child.deleteLater()

        canvas_cfg = self.main_ui_layout_config.get("canvas", {})
        canvas_width = int(canvas_cfg.get("width", 1024))
        canvas_height = int(canvas_cfg.get("height", 768))
        print(f"[UI_LAYOUT] canvas: {canvas_width}x{canvas_height}")
        print(f"[UI] canvas size: {canvas_width} {canvas_height}")
        self.setFixedSize(canvas_width, canvas_height)
        self.game_canvas.setFixedSize(canvas_width, canvas_height)

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
        else:
            self.main_frame_label.setStyleSheet("background-color: #1a1a1a;")

        title_cfg = self.main_ui_layout_config.get("title_text", {})
        if title_cfg:
            title_style = self.theme_style.get("title", {})
            title_text = str(title_cfg.get("text", ""))
            title_x = int(title_cfg.get("x", 0))
            title_y = int(title_cfg.get("y", 0))
            title_w = int(title_cfg.get("w", 320))
            title_h = int(title_cfg.get("h", 48))
            title_font_size = int(title_cfg.get("font_size", 28))
            title_color = str(
                title_style.get("color", title_cfg.get("color", "#f2d28b"))
            )
            title_shadow_color = str(
                title_style.get("shadow_color", title_cfg.get("shadow_color", "#000000"))
            )

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
        self.settings_button.clicked.connect(self.on_settings_button_clicked)
        self.settings_button.raise_()
        self.settings_button.show()

        nav_cfg = self.main_ui_layout_config.get("main_nav_buttons", [])
        if isinstance(nav_cfg, list):
            for nav_item in nav_cfg:
                if not isinstance(nav_item, dict):
                    continue
                section_id = str(nav_item.get("id", "")).strip()
                if not section_id:
                    continue
                nav_text = str(nav_item.get("text", ""))
                nav_asset = str(nav_item.get("asset", "")).strip()
                nav_x = int(nav_item.get("x", 0))
                nav_y = int(nav_item.get("y", 0))
                nav_w = int(nav_item.get("w", 120))
                nav_h = int(nav_item.get("h", 34))

                nav_container = QWidget(self.game_canvas)
                nav_container.setGeometry(nav_x, nav_y, nav_w, nav_h)
                bg_label = QLabel(nav_container)
                bg_label.setGeometry(0, 0, nav_w, nav_h)
                bg_label.setStyleSheet("background: transparent;")

                nav_asset_path = self.resolve_ui_asset_path(nav_asset) if nav_asset else None
                if nav_asset_path is not None and nav_asset_path.exists():
                    nav_pixmap = QPixmap(str(nav_asset_path))
                    if not nav_pixmap.isNull():
                        bg_label.setPixmap(
                            nav_pixmap.scaled(
                                nav_w, nav_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                            )
                        )

                bg_label.lower()
                text_label = QLabel(nav_container)
                text_label.setGeometry(0, 0, nav_w, nav_h)
                text_label.setText(nav_text)
                text_label.setAlignment(Qt.AlignCenter)
                text_label.setStyleSheet("background: transparent;")
                text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

                click_button = QPushButton(nav_container)
                click_button.setGeometry(0, 0, nav_w, nav_h)
                click_button.setText("")
                click_button.setCursor(Qt.PointingHandCursor)
                click_button.setStyleSheet(
                    "QPushButton { border: none; background: transparent; padding: 0px; }"
                )
                click_button.clicked.connect(
                    lambda checked=False, sid=section_id: self.on_main_nav_clicked(sid)
                )
                click_button.setProperty("section_id", section_id)
                click_button.installEventFilter(self)
                click_button.raise_()
                nav_container.raise_()
                nav_container.show()
                self.nav_buttons[section_id] = {
                    "container": nav_container,
                    "bg": bg_label,
                    "text": text_label,
                    "button": click_button,
                }

        self.update_main_nav_button_styles()
        self.window_close_button.raise_()
        self.settings_button.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F3:
            themes = self.theme_config.get("themes", ["diablo"])
            if not isinstance(themes, list) or not themes:
                themes = ["diablo"]
                self.theme_config["themes"] = themes
            active = self.get_active_theme()
            try:
                idx = themes.index(active)
            except ValueError:
                idx = 0
            next_theme = themes[(idx + 1) % len(themes)]
            self.theme_config["active_theme"] = next_theme
            self.save_theme_config()
            self.reload_theme()
            print("[THEME] switched to:", next_theme)
            event.accept()
            return
        super().keyPressEvent(event)

    def on_settings_button_clicked(self):
        self.open_settings_dialog()
        print("[UI] Settings opened")

    def open_settings_dialog(self):
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return

        if self.settings_dialog is None:
            self.settings_dialog = QDialog(self)
            self.settings_dialog.setWindowTitle("Settings / Debug")
            self.settings_dialog.resize(1200, 800)
            dialog_layout = QVBoxLayout(self.settings_dialog)
            dialog_layout.setContentsMargins(8, 8, 8, 8)
            dialog_layout.setSpacing(8)
            dialog_layout.addWidget(self.settings_tab)
        else:
            self.settings_dialog.show()
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return

        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def on_main_nav_clicked(self, section_id):
        self.current_main_section = section_id
        self.update_main_nav_button_styles()
        print("[UI] section changed:", section_id)

    def update_main_nav_button_styles(self):
        nav_style = self.theme_style.get("nav_button", {})
        active_color = str(nav_style.get("active_color", "#f2d28b"))
        inactive_color = str(nav_style.get("inactive_color", "#9a8560"))
        hover_color = str(nav_style.get("hover_color", "#ffffff"))
        for section_id, nav in self.nav_buttons.items():
            container = nav["container"]
            text_label = nav["text"]
            click_button = nav["button"]
            if section_id == self.current_main_section:
                text_label.setStyleSheet(
                    f"background: transparent; color: {active_color}; font-weight: 700;"
                )
                container.setStyleSheet("border: 1px solid #b88a35; background: transparent;")
                click_button.setStyleSheet(
                    "QPushButton { border: none; background: transparent; padding: 0px; }"
                )
            else:
                text_label.setStyleSheet(
                    f"background: transparent; color: {inactive_color}; font-weight: 400;"
                )
                container.setStyleSheet("border: 1px solid transparent; background: transparent;")
                click_button.setStyleSheet(
                    "QPushButton { border: none; background: transparent; padding: 0px; } "
                    f"QPushButton:hover {{ border: 1px solid transparent; color: {hover_color}; }}"
                )

    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton):
            section_id = obj.property("section_id")
            if isinstance(section_id, str) and section_id in self.nav_buttons:
                nav_style = self.theme_style.get("nav_button", {})
                hover_color = str(nav_style.get("hover_color", "#ffffff"))
                inactive_color = str(nav_style.get("inactive_color", "#9a8560"))
                text_label = self.nav_buttons[section_id]["text"]
                if event.type() == QEvent.Enter and section_id != self.current_main_section:
                    text_label.setStyleSheet(
                        f"background: transparent; color: {hover_color}; font-weight: 400;"
                    )
                elif event.type() == QEvent.Leave and section_id != self.current_main_section:
                    text_label.setStyleSheet(
                        f"background: transparent; color: {inactive_color}; font-weight: 400;"
                    )
        return super().eventFilter(obj, event)

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
