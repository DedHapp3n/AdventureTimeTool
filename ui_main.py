from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit, QStyledItemDelegate, QFrame, QDialog, QMessageBox, QComboBox, QMenu, QInputDialog,
    QSpinBox, QRadioButton, QButtonGroup, QCheckBox, QGridLayout, QLineEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, QEvent, QRect
from PySide6.QtGui import QColor, QPen, QPixmap, QIcon, QTextDocument, QFont, QFontMetrics, QBrush
import re
import os
import json
import math
import html
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


class InlineTextEdit(QTextEdit):
    def __init__(self, on_commit=None, parent=None):
        super().__init__(parent)
        self._on_commit = on_commit
        self._initial_text = ""

    def set_initial_text(self, text):
        value = str(text or "")
        self._initial_text = value
        self.setPlainText(value)

    def focusOutEvent(self, event):
        if callable(self._on_commit):
            try:
                self._on_commit(self.toPlainText(), self._initial_text)
            except Exception:
                pass
        super().focusOutEvent(event)
        self._initial_text = self.toPlainText()


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
        self.current_skill_category = "allgemein"
        self.current_inventory_category = "inventory_01"
        self.skill_source_infos = {}
        self.skills_debug_sources = True
        self.skill_sheet_mapping_config = None
        self.settings_debug_on_start = False
        self.nav_buttons = {}
        self.settings_dialog = None
        self.debug_dialog = None
        self.theme_name_value_label = None
        self.content_layer = None
        self.settings_theme_label = None
        self.settings_checkbox_icon_label = None
        self.settings_checkbox_text_label = None
        self._settings_checkbox_asset_true = "icons/checkmark_true.png"
        self._settings_checkbox_asset_false = "icons/checkmark_false.png"
        self.settings_character_active_label = None
        self.settings_character_combo = None
        self._inventory_loading = False
        self._inventory_table_bindings = {}
        self._inventory_money_fields = {}
        self._inventory_money_delta_fields = {}
        self.equipment_analysis = {}
        self.game_canvas = QWidget()
        self.game_canvas.setStyleSheet("background-color: #101010;")
        self.setCentralWidget(self.game_canvas)
        self.reload_theme()

        self.settings_tab = QWidget()
        self.settings_layout = QVBoxLayout(self.settings_tab)

        # Button
        self.load_button = QPushButton("Tabelle laden")
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
        self.content_layer = None

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

        content_cfg = self.main_ui_layout_config.get("content_area", {})
        content_x = int(content_cfg.get("x", 32))
        content_y = int(content_cfg.get("y", 128))
        content_w = int(content_cfg.get("w", 1460))
        content_h = int(content_cfg.get("h", 870))
        self.content_layer = QWidget(self.game_canvas)
        self.content_layer.setGeometry(content_x, content_y, content_w, content_h)
        self.content_layer.setStyleSheet("background: transparent;")
        self.content_layer.show()

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
        self.show_main_section(self.current_main_section)
        self.window_close_button.raise_()
        self.settings_button.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F3:
            self.switch_to_next_theme()
            event.accept()
            return
        super().keyPressEvent(event)

    def on_settings_button_clicked(self):
        self.show_main_section("settings")
        print("[UI] section changed: settings")

    def open_settings_dialog(self):
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return

        if self.settings_dialog is None:
            self.settings_dialog = QDialog(self)
            self.settings_dialog.setWindowTitle("Settings")
            self.settings_dialog.resize(500, 420)
            dialog_layout = QVBoxLayout(self.settings_dialog)
            dialog_layout.setContentsMargins(8, 8, 8, 8)
            dialog_layout.setSpacing(8)
            header = QLabel("Adventure Time Tool - Settings")
            header.setStyleSheet("font-size: 16px; font-weight: 700;")
            dialog_layout.addWidget(header)

            theme_row = QWidget()
            theme_row_layout = QHBoxLayout(theme_row)
            theme_row_layout.setContentsMargins(0, 0, 0, 0)
            theme_row_layout.addWidget(QLabel("Aktuelles Theme:"))
            self.theme_name_value_label = QLabel(self.get_active_theme())
            theme_row_layout.addWidget(self.theme_name_value_label)
            theme_row_layout.addStretch()
            dialog_layout.addWidget(theme_row)

            theme_switch_button = QPushButton("Theme wechseln (F3)")
            theme_switch_button.clicked.connect(self.on_settings_switch_theme_clicked)
            dialog_layout.addWidget(theme_switch_button)

            cache_reload_button = QPushButton("Cache neu laden")
            cache_reload_button.clicked.connect(self.on_settings_cache_reload_clicked)
            dialog_layout.addWidget(cache_reload_button)

            excel_import_button = QPushButton("Excel / Charakterbogen laden")
            excel_import_button.clicked.connect(self.on_settings_excel_import_clicked)
            dialog_layout.addWidget(excel_import_button)

            debug_open_button = QPushButton("Debug öffnen")
            debug_open_button.clicked.connect(self.open_debug_dialog)
            dialog_layout.addWidget(debug_open_button)

            close_button = QPushButton("Schließen")
            close_button.clicked.connect(self.settings_dialog.close)
            dialog_layout.addWidget(close_button)
            dialog_layout.addStretch()
        else:
            self.settings_dialog.show()
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return

        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def open_debug_dialog(self):
        if self.debug_dialog is not None and self.debug_dialog.isVisible():
            self.debug_dialog.raise_()
            self.debug_dialog.activateWindow()
            return

        if self.debug_dialog is None:
            self.debug_dialog = QDialog(self)
            self.debug_dialog.setWindowTitle("Settings / Debug")
            self.debug_dialog.resize(1200, 800)
            dialog_layout = QVBoxLayout(self.debug_dialog)
            dialog_layout.setContentsMargins(8, 8, 8, 8)
            dialog_layout.setSpacing(8)
            dialog_layout.addWidget(self.settings_tab)

        self.debug_dialog.show()
        self.debug_dialog.raise_()
        self.debug_dialog.activateWindow()

    def switch_to_next_theme(self):
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
        if self.theme_name_value_label is not None:
            self.theme_name_value_label.setText(self.get_active_theme())
        if hasattr(self, "settings_theme_value_label") and self.settings_theme_value_label is not None and self.current_main_section == "settings":
            self.settings_theme_value_label.setText(self.get_active_theme())
        print("[THEME] switched to:", next_theme)

    def on_settings_switch_theme_clicked(self):
        self.switch_to_next_theme()

    def on_settings_cache_reload_clicked(self):
        if hasattr(self.loader, "load_cache_from_json"):
            if hasattr(self.loader, "has_unsaved_changes") and self.loader.has_unsaved_changes():
                print("[CHARACTER WARNING] unsaved changes before switching character")
            if self.loader.load_cache_from_json():
                self.reset_character_runtime_state()
                self.create_tabs_from_cache()
                if self.settings_character_active_label is not None:
                    self.settings_character_active_label.setText(self.loader.current_character_name)
                if self.current_main_section == "character":
                    self.show_main_section("character")
                elif self.current_main_section in ("skills", "fertigkeiten"):
                    self.show_main_section("skills")
                elif self.current_main_section == "inventory":
                    self.show_main_section("inventory")
                elif self.current_main_section in ("equipment", "ausruestung", "ausrüstung"):
                    self.show_main_section("equipment")
            print("[SETTINGS] Cache reload clicked")
            return
        print("[SETTINGS] Cache reload clicked")

    def on_settings_excel_import_clicked(self):
        try:
            self.load_excel()
        except Exception:
            print("[SETTINGS] Excel import clicked")

    def on_main_nav_clicked(self, section_id):
        self.show_main_section(section_id)
        print("[UI] section changed:", section_id)

    def clear_content_layer(self):
        if self.content_layer is None:
            return
        for child in self.content_layer.findChildren(QWidget):
            child.setParent(None)
            child.deleteLater()

    def show_main_section(self, section_id):
        self.current_main_section = section_id
        self.update_main_nav_button_styles()
        self.clear_content_layer()
        if section_id == "settings":
            self.render_settings_page()
        elif section_id == "character":
            self.render_character_screen()
        elif section_id in ("skills", "fertigkeiten"):
            self.render_skills_screen()
        elif section_id == "inventory":
            self.render_inventory_screen()
        elif section_id in ("equipment", "ausruestung", "ausrüstung"):
            self.render_equipment_screen()
        self.window_close_button.raise_()
        self.settings_button.raise_()

    def create_asset_text_button(self, parent, cfg, default_text, callback):
        x = int(cfg.get("x", 0))
        y = int(cfg.get("y", 0))
        w = int(cfg.get("w", 300))
        h = int(cfg.get("h", 58))
        text = str(cfg.get("text", default_text))
        asset = str(cfg.get("asset", "")).strip()

        container = QWidget(parent)
        container.setGeometry(x, y, w, h)

        bg_label = QLabel(container)
        bg_label.setGeometry(0, 0, w, h)
        bg_label.setStyleSheet("background: transparent;")
        asset_path = self.resolve_ui_asset_path(asset) if asset else None
        if asset_path is not None and asset_path.exists():
            pixmap = QPixmap(str(asset_path))
            if not pixmap.isNull():
                bg_label.setPixmap(
                    pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                )
        bg_label.lower()

        nav_style = self.theme_style.get("nav_button", {})
        text_color = str(nav_style.get("active_color", "#f2d28b"))
        text_label = QLabel(container)
        text_label.setGeometry(0, 0, w, h)
        text_label.setText(text)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet(
            f"background: transparent; color: {text_color}; font-size: 20px; font-weight: 700;"
        )
        text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        click_button = QPushButton(container)
        click_button.setGeometry(0, 0, w, h)
        click_button.setText("")
        click_button.setCursor(Qt.PointingHandCursor)
        click_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; padding: 0px; }"
        )
        click_button.clicked.connect(callback)
        click_button.raise_()
        container.show()
        return {"container": container, "bg": bg_label, "text": text_label, "button": click_button}

    def render_settings_page(self):
        if self.content_layer is None:
            return
        settings_page = self.main_ui_layout_config.get("settings_page", {})
        default_text_style = self.theme_style.get("default_text", {})
        default_color = str(default_text_style.get("color", "#e8e0c8"))

        title_cfg = settings_page.get("title", {})
        title_text = str(title_cfg.get("text", "Settings"))
        title_x = int(title_cfg.get("x", 60))
        title_y = int(title_cfg.get("y", 40))
        title_w = int(title_cfg.get("w", 400))
        title_h = int(title_cfg.get("h", 50))
        title_font = int(title_cfg.get("font_size", 32))
        title_label = QLabel(self.content_layer)
        title_label.setGeometry(title_x, title_y, title_w, title_h)
        title_label.setText(title_text)
        title_label.setStyleSheet(
            f"background: transparent; color: {default_color}; font-size: {title_font}px; font-weight: 700;"
        )
        title_label.show()

        # 1) Theme Bereich
        theme_section_title_cfg = settings_page.get("theme_section_title", {})
        theme_section_title = QLabel(self.content_layer)
        theme_section_title.setGeometry(
            int(theme_section_title_cfg.get("x", 100)),
            int(theme_section_title_cfg.get("y", 145)),
            int(theme_section_title_cfg.get("w", 300)),
            int(theme_section_title_cfg.get("h", 35)),
        )
        theme_section_title.setText(str(theme_section_title_cfg.get("text", "Theme")))
        theme_section_title.setStyleSheet(
            f"background: transparent; color: {default_color}; "
            f"font-size: {int(theme_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
        )
        theme_section_title.show()

        theme_label_cfg = settings_page.get("theme_label", {})
        theme_label_x = int(theme_label_cfg.get("x", 80))
        theme_label_y = int(theme_label_cfg.get("y", 120))
        theme_label_w = int(theme_label_cfg.get("w", 420))
        theme_label_h = int(theme_label_cfg.get("h", 40))
        theme_label_font = int(theme_label_cfg.get("font_size", 22))
        theme_text_prefix = str(theme_label_cfg.get("text", "Aktuelles Theme"))
        self.settings_theme_label = QLabel(self.content_layer)
        self.settings_theme_label.setGeometry(
            theme_label_x, theme_label_y, theme_label_w, theme_label_h
        )
        self.settings_theme_label.setText(theme_text_prefix)
        self.settings_theme_label.setStyleSheet(
            f"background: transparent; color: {default_color}; font-size: {theme_label_font}px; font-weight: 500;"
        )
        self.settings_theme_label.show()

        theme_value_cfg = settings_page.get("theme_value", {})
        theme_value_x = int(theme_value_cfg.get("x", theme_label_x + 210))
        theme_value_y = int(theme_value_cfg.get("y", theme_label_y))
        theme_value_w = int(theme_value_cfg.get("w", 260))
        theme_value_h = int(theme_value_cfg.get("h", theme_label_h))
        self.settings_theme_value_label = QLabel(self.content_layer)
        self.settings_theme_value_label.setGeometry(
            theme_value_x, theme_value_y, theme_value_w, theme_value_h
        )
        self.settings_theme_value_label.setText(self.get_active_theme())
        self.settings_theme_value_label.setStyleSheet(
            f"background: transparent; color: {default_color}; "
            f"font-size: {int(theme_value_cfg.get('font_size', theme_label_font))}px; font-weight: 600;"
        )
        self.settings_theme_value_label.show()

        self.create_asset_text_button(
            self.content_layer,
            settings_page.get("theme_switch_button", {}),
            "Theme wechseln",
            self.on_settings_switch_theme_clicked,
        )

        # 2) Charakter Bereich
        character_section_title_cfg = settings_page.get("character_section_title", {})
        character_section_y = int(character_section_title_cfg.get("y", 330))
        character_title = QLabel(self.content_layer)
        character_title.setGeometry(
            int(character_section_title_cfg.get("x", 100)),
            character_section_y,
            int(character_section_title_cfg.get("w", 300)),
            int(character_section_title_cfg.get("h", 35)),
        )
        character_title.setText(str(character_section_title_cfg.get("text", "Charakter")))
        character_title.setStyleSheet(
            f"background: transparent; color: {default_color}; "
            f"font-size: {int(character_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
        )
        character_title.show()

        active_character_label_cfg = settings_page.get("active_character_label", {})
        active_prefix = QLabel(self.content_layer)
        active_prefix.setGeometry(
            int(active_character_label_cfg.get("x", 110)),
            int(active_character_label_cfg.get("y", character_section_y + 44)),
            int(active_character_label_cfg.get("w", 220)),
            int(active_character_label_cfg.get("h", 32)),
        )
        active_prefix.setText(str(active_character_label_cfg.get("text", "Aktiver Charakter:")))
        active_prefix.setStyleSheet(
            f"background: transparent; color: {default_color}; "
            f"font-size: {int(active_character_label_cfg.get('font_size', 18))}px; font-weight: 500;"
        )
        active_prefix.show()

        active_character_value_cfg = settings_page.get("active_character_value", {})
        self.settings_character_active_label = QLabel(self.content_layer)
        self.settings_character_active_label.setGeometry(
            int(active_character_value_cfg.get("x", 320)),
            int(active_character_value_cfg.get("y", character_section_y + 44)),
            int(active_character_value_cfg.get("w", 420)),
            int(active_character_value_cfg.get("h", 32)),
        )
        self.settings_character_active_label.setText(self.loader.current_character_name)
        self.settings_character_active_label.setStyleSheet(
            f"background: transparent; color: {default_color}; "
            f"font-size: {int(active_character_value_cfg.get('font_size', 18))}px; font-weight: 600;"
        )
        self.settings_character_active_label.show()

        character_select_cfg = settings_page.get("character_select", {})
        select_x = int(character_select_cfg.get("x", 80))
        select_y = int(character_select_cfg.get("y", character_section_y + 88))
        select_w = int(character_select_cfg.get("w", 620))
        select_h = int(character_select_cfg.get("h", 36))
        nav_style = self.theme_style.get("nav_button", {})
        combo_text_color = str(nav_style.get("active_color", default_color))

        self.settings_character_combo = QComboBox(self.content_layer)
        self.settings_character_combo.setGeometry(select_x, select_y, select_w, select_h)
        self.settings_character_combo.setStyleSheet(
            "QComboBox {"
            "background-color: rgba(10, 10, 10, 180);"
            f"color: {combo_text_color};"
            "border: 1px solid #8a6a32;"
            "padding-left: 8px;"
            "padding-right: 24px;"
            "}"
            "QComboBox::drop-down {"
            "subcontrol-origin: padding;"
            "subcontrol-position: top right;"
            "width: 20px;"
            "border-left: 1px solid #8a6a32;"
            "background: rgba(30, 20, 10, 180);"
            "}"
            "QComboBox QAbstractItemView {"
            "background-color: rgba(10, 10, 10, 220);"
            f"color: {combo_text_color};"
            "selection-background-color: rgba(80, 60, 30, 180);"
            "border: 1px solid #8a6a32;"
            "}"
        )
        self.settings_character_combo.show()
        self.settings_character_combo.currentIndexChanged.connect(
            self.on_settings_character_selection_changed
        )
        self.refresh_character_cache_list()

        self.create_asset_text_button(
            self.content_layer,
            settings_page.get("character_load_button", {}),
            "Charakter laden",
            self.on_settings_load_character_clicked,
        )

        self.create_asset_text_button(
            self.content_layer,
            settings_page.get("character_refresh_button", {}),
            "Liste aktualisieren",
            self.on_settings_refresh_character_list_clicked,
        )

        # 3) Debug Bereich
        debug_section_title_cfg = settings_page.get("debug_section_title", {})
        debug_section_title = QLabel(self.content_layer)
        debug_section_title.setGeometry(
            int(debug_section_title_cfg.get("x", 100)),
            int(debug_section_title_cfg.get("y", 570)),
            int(debug_section_title_cfg.get("w", 300)),
            int(debug_section_title_cfg.get("h", 35)),
        )
        debug_section_title.setText(str(debug_section_title_cfg.get("text", "Debug")))
        debug_section_title.setStyleSheet(
            f"background: transparent; color: {default_color}; "
            f"font-size: {int(debug_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
        )
        debug_section_title.show()

        self.create_asset_text_button(
            self.content_layer,
            settings_page.get("debug_button", {}),
            "Debug öffnen",
            self.open_debug_dialog,
        )

        checkbox_cfg = settings_page.get("checkbox_debug_start", {})
        cb_x = int(checkbox_cfg.get("x", 80))
        cb_y = int(checkbox_cfg.get("y", 300))
        cb_w = int(checkbox_cfg.get("w", 50))
        cb_h = int(checkbox_cfg.get("h", 50))
        cb_text = str(checkbox_cfg.get("text", "Debug beim Start anzeigen"))
        self._settings_checkbox_asset_true = str(
            checkbox_cfg.get("asset_true", "icons/checkmark_true.png")
        )
        self._settings_checkbox_asset_false = str(
            checkbox_cfg.get("asset_false", "icons/checkmark_false.png")
        )

        checkbox_container = QWidget(self.content_layer)
        checkbox_container.setGeometry(cb_x, cb_y, 700, max(50, cb_h))

        self.settings_checkbox_icon_label = QLabel(checkbox_container)
        self.settings_checkbox_icon_label.setGeometry(0, 0, cb_w, cb_h)
        self.settings_checkbox_icon_label.setStyleSheet("background: transparent;")

        self.settings_checkbox_text_label = QLabel(checkbox_container)
        self.settings_checkbox_text_label.setGeometry(cb_w + 16, 0, 620, cb_h)
        self.settings_checkbox_text_label.setText(cb_text)
        self.settings_checkbox_text_label.setStyleSheet(
            f"background: transparent; color: {default_color}; font-size: 20px; font-weight: 500;"
        )

        click_overlay = QPushButton(checkbox_container)
        click_overlay.setGeometry(0, 0, 700, max(50, cb_h))
        click_overlay.setText("")
        click_overlay.setCursor(Qt.PointingHandCursor)
        click_overlay.setStyleSheet(
            "QPushButton { border: none; background: transparent; padding: 0px; }"
        )
        click_overlay.clicked.connect(self.on_settings_debug_start_toggled)
        click_overlay.raise_()
        checkbox_container.show()

        # 4) Daten/Cache Bereich
        data_section_title_cfg = settings_page.get("data_section_title", {})
        data_section_title = QLabel(self.content_layer)
        data_section_title.setGeometry(
            int(data_section_title_cfg.get("x", 100)),
            int(data_section_title_cfg.get("y", 785)),
            int(data_section_title_cfg.get("w", 300)),
            int(data_section_title_cfg.get("h", 35)),
        )
        data_section_title.setText(str(data_section_title_cfg.get("text", "Daten")))
        data_section_title.setStyleSheet(
            f"background: transparent; color: {default_color}; "
            f"font-size: {int(data_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
        )
        data_section_title.show()

        self.create_asset_text_button(
            self.content_layer,
            settings_page.get("reload_cache_button", {}),
            "Cache neu laden",
            self.on_settings_cache_reload_clicked,
        )

        self.update_settings_checkbox_icon()

    def _get_cache_value_for_front_parser(self, sheet_name, cell_ref):
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        cell_data = sheet_cache.get(cell_ref)
        if not isinstance(cell_data, dict):
            return None
        formula = cell_data.get("formula")
        if isinstance(formula, str) and formula.startswith("="):
            return formula
        return cell_data.get("value")

    def _get_character_front_value(self, sheet_name, cell_ref, fallback="-"):
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        cell_data = sheet_cache.get(cell_ref)
        if not isinstance(cell_data, dict):
            return fallback

        value = cell_data.get("value")
        if value is None:
            return fallback
        text = str(value).strip()
        if text.startswith("="):
            return fallback
        return text if text else fallback

    def get_cache_display_value(self, sheet_name, cell_ref, fallback="-"):
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        cell_data = sheet_cache.get(cell_ref)
        if isinstance(cell_data, dict):
            value = cell_data.get("value")
        else:
            value = cell_data
        if value is None:
            return fallback
        text = str(value).strip()
        if not text or text.startswith("="):
            return fallback
        return text

    def format_character_display_value(self, value, mode="auto"):
        if value is None:
            return "-"
        text = str(value).strip()
        if not text or text.startswith("="):
            return "-"
        if mode == "raw":
            return text

        normalized = text.replace(",", ".")
        try:
            number = float(normalized)
        except Exception:
            return text

        if mode == "int":
            rounded = math.floor(number + 0.5) if number >= 0 else math.ceil(number - 0.5)
            return str(int(rounded))

        if mode == "decimal":
            return f"{number:.10f}".rstrip("0").rstrip(".")

        if number.is_integer():
            return str(int(number))
        return f"{number:.10f}".rstrip("0").rstrip(".")

    def get_wellbeing_entries(self, cfg=None):
        data_cfg = cfg if isinstance(cfg, dict) else {}
        sheet_name = str(data_cfg.get("sheet", "Charakterbogen"))
        marker_col = str(data_cfg.get("marker_col", "AA")).strip() or "AA"
        label_col = str(data_cfg.get("label_col", "AB")).strip() or "AB"
        start_row = self._safe_int(data_cfg.get("start_row", 23), 23)
        end_row = self._safe_int(data_cfg.get("end_row", 44), 44)
        if end_row < start_row:
            start_row, end_row = end_row, start_row
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        entries = []

        def read_cached_text(cell_ref):
            cell_data = sheet_cache.get(cell_ref)
            if isinstance(cell_data, dict):
                value = cell_data.get("value")
            else:
                value = cell_data
            if value is None:
                return ""
            return str(value).strip()

        for row in range(start_row, end_row + 1):
            marker_cell = f"{marker_col}{row}"
            label_cell = f"{label_col}{row}"
            marker_text = read_cached_text(marker_cell)
            label_text = read_cached_text(label_cell)
            active = marker_text.lower() == "x"
            entries.append(
                {
                    "row": row,
                    "marker_cell": marker_cell,
                    "label_cell": label_cell,
                    "active": active,
                    "label": label_text,
                }
            )
            print(f'[WELLBEING] row={row} active={active} label="{label_text}"')
        return entries

    def load_skill_definitions(self):
        definitions_path = self.base_dir / "assets" / "config" / "skill_definitions.json"
        empty = {"attribute_map": {}, "categories": []}
        try:
            if not definitions_path.exists():
                print("[SKILLS] missing/invalid skill_definitions.json")
                return empty
            with open(definitions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                print("[SKILLS] missing/invalid skill_definitions.json")
                return empty
            if not isinstance(data.get("attribute_map"), dict):
                data["attribute_map"] = {}
            if not isinstance(data.get("categories"), list):
                data["categories"] = []
            return data
        except Exception:
            print("[SKILLS] missing/invalid skill_definitions.json")
            return empty

    def get_default_skills_layout_config(self):
        return {
            "skills_screen": {
                "x": 20,
                "y": 20,
                "w": 1420,
                "h": 820,
                "category_tabs": {
                    "x": 20,
                    "y": 10,
                    "w": 1380,
                    "h": 50,
                    "button_w": 220,
                    "button_h": 42,
                    "gap": 18,
                    "font_size": 20,
                    "active_color": "#f2d28b",
                    "inactive_color": "#9a8560",
                },
                "table": {
                    "x": 20,
                    "y": 80,
                    "w": 1380,
                    "h": 700,
                    "header_h": 42,
                    "row_h": 42,
                    "max_visible_rows": 15,
                    "font_size": 17,
                    "header_font_size": 19,
                    "header_color": "#f2d28b",
                    "skill_name_color": "#f2d28b",
                    "attribute_color": "#ffffff",
                    "value_color": "#7fd0ff",
                    "specialization_color": "#ffffff",
                    "note_color": "#d8d0b0",
                    "columns": {
                        "skill": {"title": "Fertigkeiten", "x": 0, "w": 360},
                        "attributes": {
                            "title": "Attribute",
                            "x": 370,
                            "w": 220,
                            "slot_w": 42,
                            "slot_gap": 8,
                        },
                        "value": {"title": "Wert", "x": 600, "w": 80},
                        "specialization": {
                            "title": "Spezialisierung",
                            "x": 690,
                            "w": 470,
                        },
                        "note": {"title": "Notiz", "x": 1170, "w": 210},
                    },
                },
            }
        }

    def load_skills_layout_config(self):
        active_theme = self.get_active_theme()
        layout_file = ""
        screen_cfg = self.main_ui_layout_config.get("skills_screen", {})
        if isinstance(screen_cfg, dict):
            layout_file = str(screen_cfg.get("layout_file", "")).strip()
        if not layout_file:
            layout_file = "skills_layout.json"

        candidates = [
            self.base_dir / "assets" / "themes" / active_theme / layout_file,
            self.base_dir / "assets" / "themes" / "diablo" / "skills_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("skills_screen"), dict):
                    return data
            except Exception:
                continue
        return self.get_default_skills_layout_config()

    def get_default_inventory_layout_config(self):
        return {
            "inventory_screen": {
                "x": 20,
                "y": 20,
                "w": 1420,
                "h": 820,
                "title": {
                    "text": "Inventar",
                    "x": 0,
                    "y": 0,
                    "w": 1380,
                    "h": 42,
                    "font_size": 24,
                    "color": "#f2d28b",
                    "align": "center",
                },
                "money": {
                    "x": 20,
                    "y": 60,
                    "w": 420,
                    "h": 110,
                    "title": "Geldbeutel",
                    "font_size": 18,
                    "label_font_size": 14,
                    "value_font_size": 20,
                    "title_color": "#f2d28b",
                    "label_color": "#f2d28b",
                    "value_color": "#ffffff",
                    "columns": [
                        {"id": "gulden", "label": "Gulden"},
                        {"id": "schilling", "label": "Schilling"},
                        {"id": "heller", "label": "Heller"},
                        {"id": "pfifferling", "label": "Pfifferling"},
                    ],
                },
                "tables": {
                    "y": 200,
                    "h": 600,
                    "row_mode": "table_widget",
                    "min_row_h": 28,
                    "max_row_h": 72,
                    "row_h": 42,
                    "name_max_lines": 3,
                    "name_line_h": 22,
                    "meta_line_h": 16,
                    "row_gap": 4,
                    "item_padding_x": 8,
                    "item_padding_y": 4,
                    "item_border_enabled": False,
                    "separator_enabled": True,
                    "wrap_text": True,
                    "meta_format": "PL: {pl}    Anzahl: {count}",
                    "header_h": 38,
                    "font_size": 14,
                    "meta_font_size": 11,
                    "header_font_size": 16,
                    "header_color": "#f2d28b",
                    "text_color": "#ffffff",
                    "muted_text_color": "#c8c0aa",
                    "value_color": "#7fd0ff",
                    "meta_text_color": "#7fd0ff",
                    "border_color": "rgba(242, 210, 139, 90)",
                    "row_background": "rgba(0, 0, 0, 18)",
                    "separator_color": "rgba(255, 255, 255, 22)",
                    "max_visible_rows": 15,
                    "sections": [
                        {
                            "id": "inventory_left",
                            "title": "Inventar",
                            "x": 20,
                            "w": 430,
                            "columns": {
                                "name": {"title": "Inventar", "x": 0, "w": 330},
                                "pl": {"title": "PL", "x": 335, "w": 45},
                                "count": {"title": "Anzahl", "x": 385, "w": 45},
                            },
                        },
                        {
                            "id": "inventory_middle",
                            "title": "Inventar",
                            "x": 480,
                            "w": 430,
                            "columns": {
                                "name": {"title": "Inventar", "x": 0, "w": 330},
                                "pl": {"title": "PL", "x": 335, "w": 45},
                                "count": {"title": "Anzahl", "x": 385, "w": 45},
                            },
                        },
                        {
                            "id": "books",
                            "title": "Bücher",
                            "x": 940,
                            "w": 430,
                            "columns": {
                                "name": {"title": "Bücher", "x": 0, "w": 330},
                                "pl": {"title": "PL", "x": 335, "w": 45},
                                "count": {"title": "Anzahl", "x": 385, "w": 45},
                            },
                        },
                    ],
                },
            }
        }

    def load_inventory_layout_config(self):
        active_theme = self.get_active_theme()
        layout_file = ""
        screen_cfg = self.main_ui_layout_config.get("inventory_screen", {})
        if isinstance(screen_cfg, dict):
            layout_file = str(screen_cfg.get("layout_file", "")).strip()
        if not layout_file:
            layout_file = "inventory_layout.json"

        candidates = [
            self.base_dir / "assets" / "themes" / active_theme / layout_file,
            self.base_dir / "assets" / "themes" / "diablo" / "inventory_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("inventory_screen"), dict):
                    print(f"[INVENTORY LAYOUT] loaded: {layout_path}")
                    return data
            except Exception:
                continue
        print("[INVENTORY LAYOUT] fallback: internal default")
        return self.get_default_inventory_layout_config()

    def get_default_equipment_layout_config(self):
        return {
            "equipment_screen": {
                "x": 20,
                "y": 20,
                "w": 1420,
                "h": 820,
                "title": {
                    "text": "Ausrüstung",
                    "x": 0,
                    "y": 0,
                    "w": 1380,
                    "h": 42,
                    "font_size": 24,
                    "color": "#f2d28b",
                    "align": "center",
                },
                "debug": {
                    "enabled": True,
                    "print_mapping": True,
                    "print_rows": True,
                },
            }
        }

    def load_equipment_layout_config(self):
        active_theme = self.get_active_theme()
        layout_file = ""
        screen_cfg = self.main_ui_layout_config.get("equipment_screen", {})
        if isinstance(screen_cfg, dict):
            layout_file = str(screen_cfg.get("layout_file", "")).strip()
        if not layout_file:
            layout_file = "equipment_layout.json"

        candidates = [
            self.base_dir / "assets" / "themes" / active_theme / layout_file,
            self.base_dir / "assets" / "themes" / "diablo" / "equipment_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("equipment_screen"), dict):
                    print(f"[EQUIPMENT LAYOUT] loaded: {layout_path}")
                    return data
            except Exception:
                continue
        print("[EQUIPMENT LAYOUT] fallback: internal default")
        return self.get_default_equipment_layout_config()

    def get_default_roll_dialog_layout_config(self):
        return {
            "dialog": {
                "title": "Roll20 Wurf-Assistent",
                "w": 700,
                "h": 620,
                "background": "#202426",
                "text_color": "#f2f2f2",
                "muted_text_color": "#c8c0aa",
                "accent_color": "#f2d28b",
                "border_color": "#8a6a32",
                "font_size": 13,
                "title_font_size": 18,
            },
            "sections": {
                "spacing": 12,
                "label_height": 24,
                "box_height": 56,
            },
            "specialization_box": {
                "background": "#141618",
                "border_color": "#3a3a3a",
                "text_color": "#ffffff",
                "font_size": 13,
                "height": 64,
            },
            "counter": {
                "button_w": 30,
                "button_h": 26,
                "value_w": 42,
                "button_background": "#34383c",
                "button_text_color": "#ffffff",
                "button_border_color": "#5c6268",
            },
            "keep_options": {
                "kh_text": "Höchsten behalten (kh1)",
                "kl_text": "Niedrigsten behalten (kl1)",
                "none_text": "Kein Keep",
            },
            "roll_preview": {
                "label": "Roll20-Befehl:",
                "background": "#101214",
                "border_color": "#8a6a32",
                "text_color": "#f2d28b",
                "font_size": 22,
                "height": 58,
            },
            "direct_send": {
                "enabled": True,
                "text": "Direkt an Roll20 senden",
                "tooltip": "Noch nicht implementiert. Aktuell wird nur kopiert.",
            },
            "buttons": {
                "copy_text": "Kopieren",
                "close_text": "Schließen",
            },
            "perk_suggestions": {
                "title": "Perk-/Nachteil-Vorschläge:",
                "empty_text": "Keine passenden Perk-/Nachteil-Vorschläge",
                "hint": "Angehakte Vorschläge wirken nur manuell auf diesen Wurf.",
                "max_visible": 4,
            },
        }

    def load_roll_dialog_layout_config(self):
        active_theme = self.get_active_theme()
        default_config = self.get_default_roll_dialog_layout_config()
        candidates = [
            self.base_dir / "assets" / "themes" / active_theme / "roll_dialog_layout.json",
            self.base_dir / "assets" / "themes" / "diablo" / "roll_dialog_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("dialog"), dict):
                    print(f"[ROLL LAYOUT] loaded: {layout_path}")
                    return data
            except Exception:
                continue
        print("[ROLL LAYOUT] fallback: internal defaults")
        return default_config

    def load_perk_rules_config(self):
        rules_path = self.base_dir / "assets" / "config" / "perk_rules.json"
        empty = {"version": 1, "description": "", "rules": []}
        try:
            if not rules_path.exists():
                print("[PERK RULES] missing, using empty rules")
                return empty
            with open(rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                print("[PERK RULES] missing, using empty rules")
                return empty
            rules = data.get("rules", [])
            if not isinstance(rules, list):
                rules = []
            enabled_rules = []
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                if not bool(rule.get("enabled", False)):
                    continue
                enabled_rules.append(rule)
            data["rules"] = enabled_rules
            print(f"[PERK RULES] loaded: {rules_path} rules={len(enabled_rules)}")
            return data
        except Exception:
            print("[PERK RULES] missing, using empty rules")
            return empty

    def get_default_skill_sheet_mapping_config(self):
        return {
            "sheet": "Fertigkeiten",
            "name_col": "D",
            "attribute_cols": ["V", "X", "Z", "AB"],
            "value_formula_col": "AD",
            "specialization_col": "AG",
            "note_col": "BE",
            "blocks": [
                self.get_default_skill_sheet_mapping_block("allgemein", 15, 35),
                self.get_default_skill_sheet_mapping_block("kampf", 49, 61),
                self.get_default_skill_sheet_mapping_block("wissen", 75, 87),
                self.get_default_skill_sheet_mapping_block("handwerk", 101, 125),
            ],
        }

    def get_default_skill_sheet_mapping_block(self, category_id, row_min, row_max):
        return {
            "category_id": category_id,
            "row_min": row_min,
            "row_max": row_max,
            "lookup_source": "shared_attribute_bonus_table",
            "lookup_key_col": "BW",
            "lookup_value_col": "BX",
            "lookup_start_row": 15,
            "lookup_end_row": 22,
            "bonus_rows": [
                {"key_cell": "BY24", "value_cell": "BW24"},
                {"key_cell": "BY26", "value_cell": "BW26"},
                {"key_cell": "BY28", "value_cell": "BW28"},
            ],
        }

    def load_skill_sheet_mapping_config(self):
        mapping_path = self.base_dir / "assets" / "config" / "skill_sheet_mapping.json"
        default = self.get_default_skill_sheet_mapping_config()
        try:
            if not mapping_path.exists():
                return default
            with open(mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return default
            if not isinstance(data.get("blocks"), list):
                data["blocks"] = default["blocks"]
            for key, value in default.items():
                if key not in data:
                    data[key] = value
            return data
        except Exception:
            return default

    def get_attribute_value_by_key(self, attribute_key):
        attribute_cells = {
            "kraft": "AG7",
            "geschick": "AG9",
            "zaehigkeit": "AG11",
            "reflex": "AG13",
            "intelligenz": "AR7",
            "willenskraft": "AR9",
            "charisma": "AR11",
            "sinne": "AR13",
        }
        cell_ref = attribute_cells.get(str(attribute_key))
        if not cell_ref:
            return 0
        raw_value = self.get_cache_display_value("Charakterbogen", cell_ref, "0")
        display_value = self.format_character_display_value(raw_value, "int")
        try:
            return int(display_value)
        except Exception:
            return 0

    def calculate_skill_attribute_sum(self, skill, attribute_map):
        if not isinstance(skill, dict) or not isinstance(attribute_map, dict):
            return 0
        attributes = skill.get("attributes", [])
        if not isinstance(attributes, list):
            return 0
        total = 0
        for attribute_letter in attributes[:4]:
            attribute_key = attribute_map.get(str(attribute_letter))
            if not attribute_key:
                continue
            total += self.get_attribute_value_by_key(attribute_key)
        return int(total)

    def calculate_skill_value(self, skill, attribute_map):
        return self.calculate_skill_attribute_sum(skill, attribute_map)

    def normalize_skill_name(self, text):
        normalized = str(text or "").strip().lower()
        normalized = (
            normalized.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _skill_name_matches(self, wanted_name, cached_name):
        return self.get_skill_name_match_quality(wanted_name, cached_name) in ("exact", "legacy")

    def get_skill_name_match_quality(self, wanted_name, cached_name):
        wanted = self.normalize_skill_name(wanted_name)
        cached = self.normalize_skill_name(cached_name)
        if not wanted or not cached:
            return "none"
        if wanted == cached:
            return "exact"

        wanted_tokens = wanted.split()
        cached_tokens = cached.split()
        if len(cached_tokens) >= 2 and cached_tokens == wanted_tokens[: len(cached_tokens)]:
            return "legacy"
        if len(wanted_tokens) >= 2 and wanted_tokens == cached_tokens[: len(wanted_tokens)]:
            return "legacy"
        return "none"

    def _coerce_skill_numeric_value(self, value):
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if not text or text.startswith("="):
            return None
        lowered = text.lower()
        if "arrayformula" in lowered or "openpyxl.worksheet.formula" in lowered:
            return None
        normalized = text.replace(",", ".")
        if not re.fullmatch(r"-?\d+(\.\d+)?", normalized):
            return None
        try:
            number = float(normalized)
        except Exception:
            return None
        return int(number) if number.is_integer() else number

    def get_cache_cell_value(self, sheet_name, cell_ref, fallback=None):
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        cell_data = sheet_cache.get(cell_ref)
        if isinstance(cell_data, dict):
            return cell_data.get("value")
        return fallback if cell_data is None else cell_data

    def get_numeric_cache_value(self, sheet_name, cell_ref):
        return self._coerce_skill_numeric_value(
            self.get_cache_cell_value(sheet_name, cell_ref, None)
        )

    def get_skill_formula_text(self, sheet_name, formula_cell):
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        cell_data = sheet_cache.get(formula_cell)
        if not isinstance(cell_data, dict):
            return None
        for key in ("formula", "value"):
            value = cell_data.get(key)
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text or not text.startswith("="):
                continue
            lowered = text.lower()
            if "arrayformula object" in lowered or "openpyxl.worksheet.formula" in lowered:
                continue
            return text
        return None

    def extract_skill_bonus_cell_from_formula(self, formula_text, source_key=""):
        if not isinstance(formula_text, str) or not formula_text.strip():
            return None
        normalized = formula_text.strip().replace("$", "").upper()
        last_paren = normalized.rfind(")")
        if last_paren < 0:
            return None
        tail = normalized[last_paren + 1 :]
        candidates = re.findall(r"\+([A-Z]{1,3}[0-9]+)", tail)
        if len(candidates) > 1:
            print("[SKILLS FORMULA BONUS AMBIGUOUS]", source_key, f'formula="{formula_text}"')
            return None
        return candidates[0] if candidates else None

    def infer_skill_bonus_cell_from_array_formula(self, sheet_name, row, formula_cell):
        raw_value = self.get_cache_cell_value(sheet_name, formula_cell, None)
        lowered = str(raw_value or "").lower()
        if "arrayformula object" not in lowered and "openpyxl.worksheet.formula" not in lowered:
            return None, False

        profile_name = self.normalize_skill_name(self.get_cache_cell_value(sheet_name, "D15", ""))
        if profile_name != "klettern athletik":
            return None, False

        # Old imported sheets store only ArrayFormula objects in AD. This mirrors the
        # known visible AD formula structure for that sheet profile without evaluating Excel.
        old_general_bonus_cells = {
            15: "BW24",
            17: "BW24",
            19: None,
            21: None,
            23: "BW24",
            25: "BW26",
            27: "BW26",
            29: "BW24",
            31: "BW24",
            33: "BW24",
            35: "BW36",
        }
        if row not in old_general_bonus_cells:
            return None, False
        return old_general_bonus_cells[row], True

    def get_skill_sheet_mapping_config(self):
        if not isinstance(self.skill_sheet_mapping_config, dict):
            self.skill_sheet_mapping_config = self.load_skill_sheet_mapping_config()
        return self.skill_sheet_mapping_config

    def get_skill_fertigkeiten_blocks(self):
        mapping = self.get_skill_sheet_mapping_config()
        blocks = mapping.get("blocks", [])
        return blocks if isinstance(blocks, list) else []

    def get_skill_block_config_for_category(self, category_id):
        wanted = str(category_id or "").strip()
        if not wanted:
            return None
        for block in self.get_skill_fertigkeiten_blocks():
            if not isinstance(block, dict):
                continue
            if str(block.get("category_id", "")).strip() == wanted:
                return self._merge_skill_block_config(block)
        return None

    def _merge_skill_block_config(self, block):
        mapping = self.get_skill_sheet_mapping_config()
        config = dict(block)
        for key in (
            "sheet",
            "name_col",
            "attribute_cols",
            "value_formula_col",
            "specialization_col",
            "note_col",
        ):
            if key not in config:
                config[key] = mapping.get(key)
        return config

    def get_skill_block_config_for_row(self, row, category_id=None):
        try:
            row = int(row)
        except Exception:
            return None
        if category_id:
            block = self.get_skill_block_config_for_category(category_id)
            if block and self._safe_int(block.get("row_min", 0), 0) <= row <= self._safe_int(block.get("row_max", 0), 0):
                return block
            return None
        for block in self.get_skill_fertigkeiten_blocks():
            if not isinstance(block, dict):
                continue
            row_min = self._safe_int(block.get("row_min", 0), 0)
            row_max = self._safe_int(block.get("row_max", 0), 0)
            if row_min <= row <= row_max:
                return self._merge_skill_block_config(block)
        return None

    def find_skill_row_in_fertigkeiten(self, skill_name, category_id=None, skill_id=None, return_info=False):
        mapping = self.get_skill_sheet_mapping_config()
        sheet_name = str(mapping.get("sheet", "Fertigkeiten"))
        name_col = str(mapping.get("name_col", "D"))
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        if not isinstance(sheet_cache, dict):
            result = (None, "missing_row", [])
            return result if return_info else None

        category_block = self.get_skill_block_config_for_category(category_id)
        matches = []
        for cell_ref, cell_data in sheet_cache.items():
            match = re.fullmatch(rf"{name_col}([0-9]+)", str(cell_ref), flags=re.IGNORECASE)
            if not match:
                continue
            row = int(match.group(1))
            if category_block:
                row_min = self._safe_int(category_block.get("row_min", 0), 0)
                row_max = self._safe_int(category_block.get("row_max", 0), 0)
                if row < row_min or row > row_max:
                    continue
            cached_name = cell_data.get("value") if isinstance(cell_data, dict) else cell_data
            match_quality = self.get_skill_name_match_quality(skill_name, cached_name)
            if match_quality == "none":
                continue
            matches.append((row, str(cached_name).strip(), match_quality))

        if len(matches) > 1:
            print(
                "[SKILLS MAP AMBIGUOUS]",
                f"{category_id}/{skill_id}",
                f'"{skill_name}"',
                "matches:",
                [m[0] for m in matches],
            )
            result = (None, "ambiguous_row", matches)
            return result if return_info else None
        if len(matches) == 1:
            print(
                "[SKILLS MAP ROW]",
                f"{category_id}/{skill_id}",
                f'"{skill_name}"',
                "->",
                f"{sheet_name}!{name_col}{matches[0][0]}",
            )
            result = (matches[0][0], "ok", matches)
            return result if return_info else matches[0][0]
        print(
            "[SKILLS MAP MISSING]",
            f"{category_id}/{skill_id}",
            f'"{skill_name}"',
            "no row found",
        )
        result = (None, "missing_row", [])
        return result if return_info else None

    def get_skill_attribute_cells_for_row(self, row, block=None):
        if block is None:
            block = self.get_skill_block_config_for_row(row)
        mapping = self.get_skill_sheet_mapping_config()
        attr_cols = block.get("attribute_cols") if isinstance(block, dict) else mapping.get("attribute_cols", [])
        if not isinstance(attr_cols, list):
            attr_cols = []
        return [f"{str(col)}{row}" for col in attr_cols[:4]]

    def get_skill_attribute_slot_values_from_row(self, row, block=None):
        if block is None:
            block = self.get_skill_block_config_for_row(row)
        sheet_name = str((block or {}).get("sheet", self.get_skill_sheet_mapping_config().get("sheet", "Fertigkeiten")))
        valid_values = {"", "K", "G", "Z", "R", "I", "W", "C", "S"}
        slot_values = []
        for cell_ref in self.get_skill_attribute_cells_for_row(row, block)[:4]:
            raw_value = self.get_cache_cell_value(sheet_name, cell_ref, "")
            value = str(raw_value or "").strip().upper()
            if value not in valid_values:
                value = ""
            slot_values.append(value)
        while len(slot_values) < 4:
            slot_values.append("")
        return slot_values[:4]

    def get_skill_attribute_letters_from_row(self, row, block=None):
        slot_values = self.get_skill_attribute_slot_values_from_row(row, block)
        return [value for value in slot_values if value][:4]

    def get_skill_lookup_value(self, block, attribute_letter):
        letter = str(attribute_letter or "").strip().upper()
        if not letter:
            return None
        sheet_name = block.get("sheet", "Fertigkeiten")
        key_col = block.get("lookup_key_col", "BW")
        value_col = block.get("lookup_value_col", "BX")
        for row in range(
            self._safe_int(block.get("lookup_start_row", 15), 15),
            self._safe_int(block.get("lookup_end_row", 22), 22) + 1,
        ):
            key = str(self.get_cache_cell_value(sheet_name, f"{key_col}{row}", "") or "").strip().upper()
            if key != letter:
                continue
            return self.get_numeric_cache_value(sheet_name, f"{value_col}{row}")
        return None

    def get_skill_bonus_key_from_note(self, note_text, attribute_letters):
        note = self.normalize_skill_name(note_text)
        has_attributes = any(str(letter).strip() for letter in attribute_letters)
        if "freie wahl" in note:
            return None
        if "charisma" in note:
            return "CH"
        if "geist" in note:
            return "M"
        if "koerper" in note:
            if not has_attributes and "oder" in note:
                return None
            return "B"
        return None

    def get_skill_bonus_value_for_key(self, block, bonus_key):
        key_wanted = str(bonus_key or "").strip().upper()
        if not key_wanted or not block:
            return None
        for bonus in block.get("bonus_rows", []):
            key = str(
                self.get_cache_cell_value(block["sheet"], bonus.get("key_cell", ""), "") or ""
            ).strip().upper()
            if key != key_wanted:
                continue
            value = self.get_numeric_cache_value(block["sheet"], bonus.get("value_cell", ""))
            return value if value is not None else 0
        return None

    def resolve_skill_bonus_key(self, skill, row, block, attribute_letters, note_text, source_key):
        note = self.normalize_skill_name(note_text)
        direct_key = self.get_skill_bonus_key_from_note(note_text, attribute_letters)
        if direct_key:
            return direct_key, "note"

        if "freie wahl" not in note:
            return None, "unknown"

        body_letters = {"K", "G", "Z", "R"}
        mind_letters = {"I", "W", "S"}
        candidates = set()
        for letter in attribute_letters:
            clean_letter = str(letter or "").strip().upper()
            if clean_letter in body_letters:
                candidates.add("B")
            elif clean_letter == "C":
                candidates.add("CH" if self.get_skill_bonus_value_for_key(block, "CH") is not None else "M")
            elif clean_letter in mind_letters:
                candidates.add("M")

        if len(candidates) == 1:
            bonus_key = next(iter(candidates))
            bonus_value = self.get_skill_bonus_value_for_key(block, bonus_key)
            print(
                "[SKILLS MAP BONUS RESOLVED]",
                source_key,
                "freie_wahl",
                f"attrs={attribute_letters}",
                "->",
                bonus_key,
                f"value={bonus_value if bonus_value is not None else 0}",
            )
            return bonus_key, "attribute_group"
        if len(candidates) > 1:
            sorted_candidates = sorted(candidates)
            print(
                "[SKILLS MAP BONUS AMBIGUOUS]",
                source_key,
                "freie_wahl",
                f"attrs={attribute_letters}",
                f"candidates={sorted_candidates}",
            )
            return None, "ambiguous"

        print(
            "[SKILLS MAP BONUS UNKNOWN]",
            source_key,
            "freie_wahl",
            f"attrs={attribute_letters}",
        )
        return None, "unknown"

    def get_skill_base_bonus_from_row_or_note(self, row, skill, block=None, note_text=None, source_key=""):
        if block is None:
            block = self.get_skill_block_config_for_row(row)
        if not block:
            return None, 0, "missing_block"
        attribute_letters = self.get_skill_attribute_letters_from_row(row, block)
        if note_text is None and isinstance(skill, dict):
            note_text = skill.get("note", "")
        bonus_key, resolve_status = self.resolve_skill_bonus_key(
            skill,
            row,
            block,
            attribute_letters,
            note_text,
            source_key,
        )
        if not bonus_key:
            return None, 0, resolve_status
        value = self.get_skill_bonus_value_for_key(block, bonus_key)
        return bonus_key, value if value is not None else 0, resolve_status

    def get_clean_skill_cache_text(self, sheet_name, cell_ref):
        value = self.get_cache_cell_value(sheet_name, cell_ref, None)
        if value is None:
            return ""
        text = str(value).strip()
        if not text or text.startswith("="):
            return ""
        lowered = text.lower()
        if "arrayformula" in lowered or "openpyxl.worksheet.formula" in lowered:
            return ""
        return text

    def get_skill_source_key(self, category_id, skill):
        skill = skill if isinstance(skill, dict) else {}
        skill_id = str(skill.get("id", self.normalize_skill_name(skill.get("name", "")))).strip()
        return f"{category_id}/{skill_id}"

    def build_skill_source_infos(self, categories, attribute_map):
        self.skill_source_infos = {}
        if not isinstance(categories, list):
            return
        for category in categories:
            if not isinstance(category, dict):
                continue
            category_id = str(category.get("id", "")).strip()
            skills = category.get("skills", [])
            if not category_id or not isinstance(skills, list):
                continue
            for skill in skills:
                if isinstance(skill, dict):
                    self.build_skill_source_info(skill, category_id, attribute_map)

    def build_skill_source_info(self, skill, category_id, attribute_map):
        skill = skill if isinstance(skill, dict) else {}
        skill_id = str(skill.get("id", self.normalize_skill_name(skill.get("name", "")))).strip()
        ui_name = str(skill.get("name", ""))
        mapping = self.get_skill_sheet_mapping_config()
        sheet_name = str(mapping.get("sheet", "Fertigkeiten"))
        name_col = str(mapping.get("name_col", "D"))
        value_formula_col = str(mapping.get("value_formula_col", "AD"))
        spec_col = str(mapping.get("specialization_col", "AG"))
        note_col = str(mapping.get("note_col", "BE"))
        attribute_sum = self.calculate_skill_attribute_sum(skill, attribute_map)
        source_key = self.get_skill_source_key(category_id, skill)
        info = {
            "category_id": category_id,
            "skill_id": skill_id,
            "ui_name": ui_name,
            "sheet_name": sheet_name,
            "row": None,
            "name_cell": None,
            "attribute_cells": [],
            "value_formula_cell": None,
            "specialization_cell": None,
            "note_cell": None,
            "lookup_key_range": None,
            "lookup_value_range": None,
            "bonus_cells": [],
            "resolved_attribute_letters": [],
            "resolved_attribute_values": [],
            "resolved_bonus_key": None,
            "resolved_bonus_value": 0,
            "calculated_value": None,
            "display_value": "",
            "source_status": "fallback",
            "attribute_sum": attribute_sum,
            "cache_name": "",
            "display_name": ui_name,
            "match_type": "missing",
            "visible_source": "structure",
            "display_attributes": [],
            "display_attribute_slots": ["", "", "", ""],
            "resolved_attribute_slots": ["", "", "", ""],
            "display_specialization": "",
            "display_note": "",
        }

        row, row_status, matches = self.find_skill_row_in_fertigkeiten(
            ui_name,
            category_id=category_id,
            skill_id=skill_id,
            return_info=True,
        )
        if row is None:
            info["source_status"] = row_status
            info["match_type"] = "ambiguous" if row_status == "ambiguous_row" else "missing"
            if row_status == "ambiguous_row":
                print(
                    "[SKILLS MATCH AMBIGUOUS]",
                    source_key,
                    f'ui="{ui_name}"',
                    f"matches={[m[0] for m in matches]}",
                )
            else:
                print("[SKILLS MATCH MISSING]", source_key, f'ui="{ui_name}"')
            print(
                "[SKILLS STRUCTURE ONLY]",
                source_key,
                "no cache row, visible fields blank",
            )
            self.skill_source_infos[source_key] = info
            self.log_skill_source_info(source_key, info)
            print(
                "[SKILLS VISIBLE SOURCE]",
                source_key,
                f"visible_source={info.get('visible_source')}",
                f"match={info.get('match_type')}",
                f'display="{info.get("display_name")}"',
            )
            return info

        cache_name = matches[0][1] if matches else ""
        match_quality = matches[0][2] if matches and len(matches[0]) > 2 else "exact"
        info["cache_name"] = cache_name
        info["match_quality"] = match_quality
        info["match_type"] = match_quality
        use_cache_display_fields = match_quality in ("exact", "legacy")
        field_fallback_used = False
        if match_quality == "legacy":
            print(
                "[SKILLS LEGACY MATCH]",
                source_key,
                f'ui="{ui_name}"',
                f'cache="{cache_name}"',
                f"row={row}",
                "using cache-visible data",
            )
        elif match_quality == "exact":
            print("[SKILLS EXACT MATCH]", source_key, f"row={row}", "using cache-visible data")

        block = self.get_skill_block_config_for_row(row, category_id)
        info["row"] = row
        info["name_cell"] = f"{name_col}{row}"
        info["attribute_cells"] = self.get_skill_attribute_cells_for_row(row, block)
        info["value_formula_cell"] = f"{value_formula_col}{row}"
        info["specialization_cell"] = f"{spec_col}{row}"
        info["note_cell"] = f"{note_col}{row}"

        cache_name_text = self.get_clean_skill_cache_text(sheet_name, info["name_cell"])
        cache_specialization = self.get_clean_skill_cache_text(sheet_name, info["specialization_cell"])
        cache_note = self.get_clean_skill_cache_text(sheet_name, info["note_cell"])
        if use_cache_display_fields:
            if cache_name_text:
                info["display_name"] = cache_name_text
            else:
                field_fallback_used = True
            info["display_specialization"] = cache_specialization
            info["display_note"] = cache_note

        if not block:
            cache_slots = self.get_skill_attribute_slot_values_from_row(row, None)
            cache_letters = [value for value in cache_slots if value]
            info["resolved_attribute_slots"] = cache_slots
            info["resolved_attribute_letters"] = cache_letters
            if use_cache_display_fields:
                info["display_attribute_slots"] = cache_slots
                info["display_attributes"] = cache_slots
                info["visible_source"] = "mixed_field_fallback" if field_fallback_used else "cache"
            info["source_status"] = "missing_block"
            info["display_value"] = "0"
            print("[SKILLS FALLBACK]", ui_name, "missing block, using attribute_sum:", attribute_sum)
            self.skill_source_infos[source_key] = info
            self.log_skill_source_info(source_key, info)
            print(
                "[SKILLS VISIBLE SOURCE]",
                source_key,
                f"visible_source={info.get('visible_source')}",
                f"match={info.get('match_type')}",
                f'display="{info.get("display_name")}"',
            )
            return info

        lookup_start = self._safe_int(block.get("lookup_start_row", 0), 0)
        lookup_end = self._safe_int(block.get("lookup_end_row", 0), 0)
        lookup_key_col = str(block.get("lookup_key_col", ""))
        lookup_value_col = str(block.get("lookup_value_col", ""))
        if lookup_start and lookup_end and lookup_key_col and lookup_value_col:
            info["lookup_key_range"] = f"{lookup_key_col}{lookup_start}:{lookup_key_col}{lookup_end}"
            info["lookup_value_range"] = f"{lookup_value_col}{lookup_start}:{lookup_value_col}{lookup_end}"
        info["bonus_cells"] = block.get("bonus_rows", []) if isinstance(block.get("bonus_rows"), list) else []

        slot_values = self.get_skill_attribute_slot_values_from_row(row, block)
        letters = [value for value in slot_values if value]
        info["resolved_attribute_slots"] = slot_values
        info["resolved_attribute_letters"] = letters
        if use_cache_display_fields:
            info["display_attribute_slots"] = slot_values
            info["display_attributes"] = slot_values
            info["visible_source"] = "mixed_field_fallback" if field_fallback_used else "cache"
        total = 0
        status = "ok"
        for letter in letters:
            lookup_value = self.get_skill_lookup_value(block, letter)
            if lookup_value is None:
                print("[SKILLS MAP LOOKUP MISSING]", source_key, letter, info["lookup_key_range"])
                status = "missing_lookup"
                continue
            info["resolved_attribute_values"].append(lookup_value)
            total += lookup_value

        formula_cell = info["value_formula_cell"]
        formula_text = self.get_skill_formula_text(sheet_name, formula_cell)
        formula_bonus_cell = None
        formula_bonus_known = False
        if formula_text:
            info["formula_text"] = formula_text
            formula_bonus_cell = self.extract_skill_bonus_cell_from_formula(formula_text, source_key)
            formula_bonus_known = True
        else:
            formula_bonus_cell, formula_bonus_known = self.infer_skill_bonus_cell_from_array_formula(
                sheet_name,
                row,
                formula_cell,
            )

        bonus_key = None
        bonus_value = 0
        if formula_bonus_known:
            if formula_bonus_cell:
                bonus_value = self.get_numeric_cache_value(sheet_name, formula_bonus_cell)
                if bonus_value is None:
                    bonus_value = 0
                bonus_key = formula_bonus_cell
                info["formula_bonus_cell"] = formula_bonus_cell
                print(
                    "[SKILLS FORMULA BONUS]",
                    source_key,
                    formula_cell,
                    "->",
                    formula_bonus_cell,
                    f"value={bonus_value}",
                )
            else:
                print("[SKILLS FORMULA BONUS]", source_key, formula_cell, "->", "none")
        else:
            print("[SKILLS BONUS FALLBACK]", source_key, "no formula text, using note fallback")
            bonus_key, bonus_value, bonus_status = self.get_skill_base_bonus_from_row_or_note(
                row,
                skill,
                block=block,
                note_text=info["display_note"],
                source_key=source_key,
            )
            if bonus_key is None and bonus_status in ("unknown", "ambiguous"):
                status = "fallback" if status == "ok" else status
        total += bonus_value
        info["resolved_bonus_key"] = bonus_key
        info["resolved_bonus_value"] = bonus_value
        info["calculated_value"] = total
        info["display_value"] = self.format_character_display_value(total, "int")
        info["source_status"] = status

        formula_raw = self.get_cache_cell_value(sheet_name, info["value_formula_cell"], None)
        if isinstance(formula_raw, str):
            lowered = formula_raw.lower()
            if formula_raw.startswith("=") or "arrayformula" in lowered or "openpyxl.worksheet.formula" in lowered:
                if status == "ok":
                    info["ignored_formula_cell_value"] = formula_raw

        self.skill_source_infos[source_key] = info
        self.log_skill_source_info(source_key, info)
        print(
            "[SKILLS VISIBLE SOURCE]",
            source_key,
            f"visible_source={info.get('visible_source')}",
            f"match={info.get('match_type')}",
            f'display="{info.get("display_name")}"',
        )
        return info

    def log_skill_source_info(self, source_key, info):
        if not self.skills_debug_sources:
            return
        print(
            "[SKILLS SOURCE]",
            source_key,
            f"row={info.get('row')}",
            f"attrs={info.get('resolved_attribute_letters')}",
            f"attr_values={info.get('resolved_attribute_values')}",
            f"bonus={info.get('resolved_bonus_key')}:{info.get('resolved_bonus_value')}",
            f"raw={info.get('calculated_value')}",
            f"display={info.get('display_value')}",
            f"status={info.get('source_status')}",
        )

    def calculate_skill_value_from_fertigkeiten_sheet(self, skill, category_id=None, attribute_map=None):
        if not isinstance(skill, dict):
            return None
        if attribute_map is None:
            attribute_map = {}
        info = self.build_skill_source_info(skill, category_id or "", attribute_map)
        return info.get("calculated_value")

    def get_skill_cache_value(self, skill):
        return self.calculate_skill_value_from_fertigkeiten_sheet(skill)

    def get_skill_attribute_slot_options(self):
        return [
            ("Leer", ""),
            ("K", "K"),
            ("G", "G"),
            ("Z", "Z"),
            ("R", "R"),
            ("I", "I"),
            ("W", "W"),
            ("C", "C"),
            ("S", "S"),
        ]

    def is_skill_attribute_slot_editable(self, source_info, slot_index):
        if not isinstance(source_info, dict):
            return False
        if source_info.get("row") is None:
            return False
        attribute_cells = source_info.get("attribute_cells", [])
        if not isinstance(attribute_cells, list) or slot_index >= len(attribute_cells):
            return False
        cell_ref = str(attribute_cells[slot_index] or "").strip().upper()
        if not re.fullmatch(r"(V|X|Z|AB)[0-9]+", cell_ref):
            return False
        return str(source_info.get("sheet_name", "")) == "Fertigkeiten"

    def open_skill_attribute_slot_menu(self, slot_widget):
        if slot_widget is None:
            return
        source_key = str(slot_widget.property("source_key") or "")
        slot_index = slot_widget.property("slot_index")
        cell_ref = str(slot_widget.property("cell_ref") or "").strip().upper()
        sheet_name = str(slot_widget.property("sheet_name") or "")
        source_info = self.skill_source_infos.get(source_key)
        if not isinstance(slot_index, int):
            try:
                slot_index = int(slot_index)
            except Exception:
                return
        if sheet_name != "Fertigkeiten" or not cell_ref:
            return
        if not self.is_skill_attribute_slot_editable(source_info, slot_index):
            return

        current_value = str(self.get_cache_cell_value(sheet_name, cell_ref, "") or "").strip().upper()
        valid_values = {"", "K", "G", "Z", "R", "I", "W", "C", "S"}
        if current_value not in valid_values:
            current_value = ""

        menu = QMenu(slot_widget)
        selected_value = None
        for label, value in self.get_skill_attribute_slot_options():
            action = menu.addAction(label)
            action.setData(value)
            if value == current_value:
                action.setEnabled(False)

        chosen_action = menu.exec(slot_widget.mapToGlobal(slot_widget.rect().bottomLeft()))
        if chosen_action is None:
            return
        selected_value = str(chosen_action.data() or "").strip().upper()
        if selected_value not in valid_values:
            selected_value = ""
        print(f'[SKILLS EDIT ATTR MENU] {sheet_name}!{cell_ref} selected="{selected_value}"')
        self.save_skill_attribute_slot_value(source_key, slot_index, selected_value)

    def save_skill_attribute_slot_value(self, source_key, slot_index, new_value):
        source_info = self.skill_source_infos.get(source_key)
        if not self.is_skill_attribute_slot_editable(source_info, slot_index):
            return
        attribute_cells = source_info.get("attribute_cells", [])
        cell_ref = str(attribute_cells[slot_index]).strip().upper()
        sheet_name = str(source_info.get("sheet_name", "Fertigkeiten"))
        valid_values = {"", "K", "G", "Z", "R", "I", "W", "C", "S"}
        old_value = str(self.get_cache_cell_value(sheet_name, cell_ref, "") or "").strip().upper()
        if old_value not in valid_values:
            old_value = ""
        normalized_new_value = str(new_value or "").strip().upper()
        if normalized_new_value not in valid_values:
            normalized_new_value = ""

        if normalized_new_value == old_value:
            return

        before_values = {}
        for other_cell_ref in attribute_cells[:4]:
            normalized_ref = str(other_cell_ref or "").strip().upper()
            before_values[normalized_ref] = str(
                self.get_cache_cell_value(sheet_name, normalized_ref, "") or ""
            ).strip().upper()
        before_snapshot = [before_values.get(str(ref or "").strip().upper(), "") for ref in attribute_cells[:4]]

        try:
            print(f'[SKILLS EDIT ATTR] {sheet_name}!{cell_ref} "{old_value}" -> "{normalized_new_value}"')
            self.loader.set_cell_value(sheet_name, cell_ref, normalized_new_value)
            after_snapshot = []
            for other_cell_ref in attribute_cells[:4]:
                normalized_ref = str(other_cell_ref or "").strip().upper()
                after_value = str(
                    self.get_cache_cell_value(sheet_name, normalized_ref, "") or ""
                ).strip().upper()
                after_snapshot.append(after_value)
                if normalized_ref == cell_ref:
                    continue
                if after_value != before_values.get(normalized_ref, ""):
                    print(
                        "[SKILLS EDIT ERROR]",
                        f"unexpected slot change {sheet_name}!{normalized_ref}",
                        f'"{before_values.get(normalized_ref, "")}" -> "{after_value}"',
                    )
            print(
                "[SKILLS EDIT SLOT SNAPSHOT]",
                f"row={source_info.get('row')}",
                f"before={before_snapshot}",
                f"after={after_snapshot}",
            )
            self.loader.save_active_character_json()
            print("[SKILLS EDIT SAVE] active character saved")
            self.create_tabs_from_cache()
            self.show_main_section("skills")
        except Exception as exc:
            print("[SKILLS EDIT ERROR]", str(exc))

    def is_skill_specialization_editable(self, source_info):
        if not isinstance(source_info, dict):
            return False
        if source_info.get("row") is None:
            return False
        if str(source_info.get("sheet_name", "")) != "Fertigkeiten":
            return False
        cell_ref = str(source_info.get("specialization_cell", "") or "").strip().upper()
        return bool(re.fullmatch(r"AG[0-9]+", cell_ref))

    def on_skill_specialization_clicked(self, source_key):
        source_info = self.skill_source_infos.get(source_key)
        if not self.is_skill_specialization_editable(source_info):
            return
        sheet_name = str(source_info.get("sheet_name", "Fertigkeiten"))
        cell_ref = str(source_info.get("specialization_cell", "") or "").strip().upper()
        old_value = str(self.get_cache_cell_value(sheet_name, cell_ref, "") or "")

        new_value, ok = QInputDialog.getText(
            self,
            "Spezialisierung bearbeiten",
            "Spezialisierung:",
            text=old_value,
        )
        if not ok:
            return

        normalized_new_value = str(new_value).strip()
        if normalized_new_value == old_value:
            return

        try:
            print(f'[SKILLS EDIT SPEC] {sheet_name}!{cell_ref} "{old_value}" -> "{normalized_new_value}"')
            self.loader.set_cell_value(sheet_name, cell_ref, normalized_new_value)
            self.loader.save_active_character_json()
            print("[SKILLS EDIT SAVE] active character saved")
            self.create_tabs_from_cache()
            self.show_main_section("skills")
        except Exception as exc:
            print("[SKILLS EDIT ERROR]", str(exc))

    def is_skill_note_editable(self, source_info):
        if not isinstance(source_info, dict):
            return False
        if source_info.get("row") is None:
            return False
        if str(source_info.get("sheet_name", "")) != "Fertigkeiten":
            return False
        cell_ref = str(source_info.get("note_cell", "") or "").strip().upper()
        return bool(re.fullmatch(r"BE[0-9]+", cell_ref))

    def save_skill_text_cell_value(self, source_key, field_type, new_text, initial_text):
        source_info = self.skill_source_infos.get(source_key)
        if not isinstance(source_info, dict):
            return
        if field_type == "specialization":
            if not self.is_skill_specialization_editable(source_info):
                return
            cell_ref = str(source_info.get("specialization_cell", "") or "").strip().upper()
        elif field_type == "note":
            if not self.is_skill_note_editable(source_info):
                return
            cell_ref = str(source_info.get("note_cell", "") or "").strip().upper()
        else:
            return

        sheet_name = str(source_info.get("sheet_name", "Fertigkeiten"))
        old_value = str(initial_text if initial_text is not None else self.get_cache_cell_value(sheet_name, cell_ref, "") or "")
        normalized_new_value = str(new_text if new_text is not None else "").strip()
        if normalized_new_value == old_value:
            return
        try:
            tag = "SPEC" if field_type == "specialization" else "NOTE"
            print(f'[SKILLS EDIT {tag}] {sheet_name}!{cell_ref} "{old_value}" -> "{normalized_new_value}"')
            self.loader.set_cell_value(sheet_name, cell_ref, normalized_new_value)
            self.loader.save_active_character_json()
            print("[SKILLS EDIT SAVE] active character saved")
            self.create_tabs_from_cache()
            self.show_main_section("skills")
        except Exception as exc:
            print("[SKILLS EDIT ERROR]", str(exc))

    def _estimate_skill_text_height(self, text, width, font_size, min_row_h, max_row_h=0, max_lines=0):
        safe_width = max(20, int(width) - 8)
        font = self.font()
        font.setPointSize(max(8, int(font_size)))
        metrics = QFontMetrics(font)
        rect = metrics.boundingRect(QRect(0, 0, safe_width, 5000), int(Qt.TextWordWrap), str(text or ""))
        text_height = max(metrics.lineSpacing() + 6, rect.height() + 10)
        if int(max_lines) > 0:
            line_cap = (metrics.lineSpacing() * int(max_lines)) + 10
            text_height = min(text_height, line_cap)
        row_height = max(int(min_row_h), text_height)
        if int(max_row_h) > 0:
            row_height = min(row_height, int(max_row_h))
        return row_height

    def build_roll20_command(self, dice_count, keep_mode, skill_bonus, manual_bonus, extra_bonuses=None):
        try:
            dice_count = int(dice_count)
        except Exception:
            dice_count = 1
        if dice_count <= 1:
            dice_count = 1
        dice_part = "1d20"
        if dice_count > 1:
            if keep_mode == "kh1":
                dice_part = f"{dice_count}d20kh1"
            elif keep_mode == "kl1":
                dice_part = f"{dice_count}d20kl1"
            else:
                dice_part = f"{dice_count}d20"

        bonus_parts = []
        values_to_add = [skill_bonus]
        if isinstance(extra_bonuses, list):
            values_to_add.extend(extra_bonuses)
        values_to_add.append(manual_bonus)
        for value in values_to_add:
            try:
                number = int(value)
            except Exception:
                continue
            if number == 0:
                continue
            if number > 0:
                bonus_parts.append(f"+{number}")
            else:
                bonus_parts.append(str(number))
        return f"/r {dice_part}{''.join(bonus_parts)}"

    def split_specialization_text(self, text):
        raw = str(text or "")
        if not raw.strip():
            return []
        parts = []
        for item in raw.split(","):
            value = str(item).strip()
            if value:
                parts.append(value)
        return parts

    def _norm_match_text(self, value):
        return str(value or "").strip().lower()

    def _contains_any_keyword(self, text, keywords):
        if not isinstance(keywords, list):
            return False
        normalized_text = self._norm_match_text(text)
        if not normalized_text:
            return False
        for keyword in keywords:
            needle = self._norm_match_text(keyword)
            if needle and needle in normalized_text:
                return True
        return False

    def collect_character_perk_entries(self):
        entries = []
        character_screen = self.main_ui_layout_config.get("character_screen", {})
        if not isinstance(character_screen, dict):
            return entries
        data_map = character_screen.get("data_map", {})
        if not isinstance(data_map, dict):
            return entries

        def collect_section(section_key, entry_type):
            section_map = data_map.get(section_key, {})
            if not isinstance(section_map, dict):
                return
            start_row = self._safe_int(section_map.get("start_row", 0), 0)
            end_row = self._safe_int(section_map.get("end_row", -1), -1)
            if start_row <= 0 or end_row < start_row:
                return
            sheet_name = str(section_map.get("sheet", data_map.get("sheet", "Charakterbogen")))
            name_col = str(section_map.get("name_col", "A"))
            bp_col = str(section_map.get("bp_col", "B"))
            effect_col = str(section_map.get("effect_col", "C"))

            for row in range(start_row, end_row + 1):
                name = str(self.get_cache_cell_value(sheet_name, f"{name_col}{row}", "") or "").strip()
                bp = str(self.get_cache_cell_value(sheet_name, f"{bp_col}{row}", "") or "").strip()
                effect = str(self.get_cache_cell_value(sheet_name, f"{effect_col}{row}", "") or "").strip()
                if not name and not effect:
                    continue
                entry = {
                    "type": entry_type,
                    "name": name,
                    "bp": bp,
                    "effect": effect,
                    "row": row,
                }
                entries.append(entry)
                print(
                    "[PERK DATA]",
                    entry_type,
                    f"row={row}",
                    f'name="{name}"',
                    f'effect="{effect}"',
                )

        collect_section("perks", "perk")
        collect_section("disadvantages", "disadvantage")
        return entries

    def find_matching_roll_suggestions(self, skill_info, character_entries, rules):
        matches = []
        if not isinstance(skill_info, dict) or not isinstance(character_entries, list) or not isinstance(rules, list):
            return matches

        skill_name = str(skill_info.get("display_name", "") or "")
        specialization_text = str(skill_info.get("display_specialization", "") or "")
        specialization_items = self.split_specialization_text(specialization_text)
        source_key = str(skill_info.get("source_key", "") or "")

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rule_type = str(rule.get("type", "")).strip().lower()
            rule_id = str(rule.get("id", "")).strip()
            name_keywords = rule.get("name_keywords", [])
            effect_keywords = rule.get("effect_keywords", [])
            skill_keywords = rule.get("skill_keywords", [])
            specialization_keywords = rule.get("specialization_keywords", [])
            context_keywords = rule.get("context_keywords", [])

            for entry in character_entries:
                if not isinstance(entry, dict):
                    continue
                entry_type = str(entry.get("type", "")).strip().lower()
                if rule_type and entry_type != rule_type:
                    continue

                entry_name = str(entry.get("name", "") or "")
                entry_effect = str(entry.get("effect", "") or "")

                if isinstance(name_keywords, list) and name_keywords:
                    name_match = self._contains_any_keyword(entry_name, name_keywords)
                else:
                    name_match = False

                if isinstance(effect_keywords, list) and effect_keywords:
                    effect_match = self._contains_any_keyword(entry_effect, effect_keywords)
                else:
                    effect_match = False

                if not (name_match or effect_match):
                    continue

                skill_match = self._contains_any_keyword(skill_name, skill_keywords)
                spec_match = any(
                    self._contains_any_keyword(item, specialization_keywords) for item in specialization_items
                )
                context_match = (
                    self._contains_any_keyword(skill_name, context_keywords)
                    or self._contains_any_keyword(specialization_text, context_keywords)
                )
                all_context_lists_empty = not (skill_keywords or specialization_keywords or context_keywords)
                if not (skill_match or spec_match or context_match or all_context_lists_empty):
                    continue

                suggestion = {
                    "rule_id": rule_id,
                    "type": rule_type,
                    "label": str(rule.get("label", rule_id or "Regelvorschlag")),
                    "source_name": entry_name,
                    "source_effect": entry_effect,
                    "source_type": entry_type,
                    "suggested_effect": rule.get("suggested_effect", {}),
                }
                matches.append(suggestion)
                print(
                    "[PERK MATCH]",
                    f'skill="{skill_name}"',
                    f"rule={rule_id}",
                    f'source="{entry_name}"',
                    f'label="{suggestion["label"]}"',
                )

        grouped = {}
        for suggestion in matches:
            rule_id = str(suggestion.get("rule_id", "") or "")
            label = str(suggestion.get("label", "") or "")
            group_key = (rule_id, label)
            grouped.setdefault(group_key, []).append(suggestion)

        deduped = []
        for _, group in grouped.items():
            named = [s for s in group if str(s.get("source_name", "") or "").strip()]
            candidates = named if named else group
            seen_source = set()
            for suggestion in candidates:
                source_key = (
                    str(suggestion.get("source_type", "") or ""),
                    str(suggestion.get("source_name", "") or ""),
                )
                if source_key in seen_source:
                    continue
                seen_source.add(source_key)
                deduped.append(suggestion)

        matches = deduped
        if not matches:
            print("[PERK MATCH]", f'skill="{skill_name}"', "none")
        return matches

    def build_specialization_preview_text(self, full_text, max_chars):
        text = str(full_text or "").strip()
        if not text:
            return "-"
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        preview = text[:max_chars].rstrip(" ,")
        if not preview:
            return "..."
        return f"{preview} ..."

    def build_compact_preview_text(self, text, max_chars=60):
        value = str(text or "").strip()
        if not value:
            return ""
        if max_chars <= 0 or len(value) <= max_chars:
            return value
        return value[:max_chars].rstrip(" ,") + "..."

    def get_active_wellbeing_roll_suggestions(self, skill_info):
        suggestions = []
        if not isinstance(skill_info, dict):
            print("[WELLBEING ROLL SUGGESTION] none")
            return suggestions

        entries = self.get_wellbeing_entries(
            {
                "sheet": "Charakterbogen",
                "marker_col": "AA",
                "label_col": "AB",
                "start_row": 23,
                "end_row": 44,
            }
        )
        if not isinstance(entries, list):
            print("[WELLBEING ROLL SUGGESTION] none")
            return suggestions

        skill_name = self._norm_match_text(skill_info.get("display_name", ""))
        specialization_text = self._norm_match_text(skill_info.get("display_specialization", ""))
        slots = skill_info.get("display_attribute_slots", [])
        if not isinstance(slots, list):
            slots = []
        attr_letters = [str(v).strip().upper() for v in slots if str(v).strip()]

        has_initiative_context = (
            "initiative" in skill_name
            or "ini-wurf" in skill_name
            or "initiative" in specialization_text
            or "ini-wurf" in specialization_text
        )
        has_body_attr = any(letter in {"K", "G", "Z", "R"} for letter in attr_letters)
        has_mind_attr = any(letter in {"I", "W", "C", "S"} for letter in attr_letters)
        has_any_attr = bool(attr_letters)

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if not bool(entry.get("active", False)):
                continue
            raw_label = str(entry.get("label", "") or "").strip()
            if not raw_label:
                continue
            normalized = self._norm_match_text(raw_label)
            if "bewegung" in normalized:
                print(f'[WELLBEING ROLL SKIP] movement label="{raw_label}"')
                continue
            if normalized in {"+/- 0", "+ / - 0", "+- 0", "+ - 0"}:
                continue

            suggestion = None
            if normalized == "+1 würfel":
                suggestion = {
                    "label": "Wohlbefinden: +1 Würfel",
                    "source_label": raw_label,
                    "suggested_effect": {"advantage": 1},
                }
            elif normalized == "-1 würfel":
                suggestion = {
                    "label": "Wohlbefinden: -1 Würfel",
                    "source_label": raw_label,
                    "suggested_effect": {"disadvantage": 1},
                }
            elif normalized == "-1 vorteil":
                suggestion = {
                    "label": "Wohlbefinden: -1 Vorteil",
                    "source_label": raw_label,
                    "suggested_effect": {"disadvantage": 1},
                }
            elif normalized == "+1 wurf körper/geist":
                if has_any_attr:
                    suggestion = {
                        "label": "Wohlbefinden: +1 Wurf Körper/Geist",
                        "source_label": raw_label,
                        "suggested_effect": {"advantage": 1},
                    }
            elif normalized == "-1 wurf geist":
                if has_mind_attr:
                    suggestion = {
                        "label": "Wohlbefinden: -1 Wurf Geist",
                        "source_label": raw_label,
                        "suggested_effect": {"disadvantage": 1},
                    }
            elif normalized == "-1 wurf körper":
                if has_body_attr:
                    suggestion = {
                        "label": "Wohlbefinden: -1 Wurf Körper",
                        "source_label": raw_label,
                        "suggested_effect": {"disadvantage": 1},
                    }
            elif normalized == "initiative im vorteil":
                if has_initiative_context:
                    suggestion = {
                        "label": "Wohlbefinden: Initiative im Vorteil",
                        "source_label": raw_label,
                        "suggested_effect": {"advantage": 1},
                    }
            elif normalized == "initiative im nachteil":
                if has_initiative_context:
                    suggestion = {
                        "label": "Wohlbefinden: Initiative im Nachteil",
                        "source_label": raw_label,
                        "suggested_effect": {"disadvantage": 1},
                    }
            if suggestion is None:
                continue
            suggestions.append(suggestion)
            compact_effect = json.dumps(suggestion.get("suggested_effect", {}), ensure_ascii=False, separators=(",", ":"))
            print(
                f'[WELLBEING ROLL SUGGESTION] label="{raw_label}" effect={compact_effect}'
            )

        if not suggestions:
            print("[WELLBEING ROLL SUGGESTION] none")
        return suggestions

    def on_skill_row_roll_clicked(self, source_key):
        source_info = self.skill_source_infos.get(source_key)
        if not isinstance(source_info, dict):
            return
        if source_info.get("row") is None:
            return

        display_name = str(source_info.get("display_name", ""))
        display_value = str(source_info.get("display_value", "0"))
        specialization_text = str(source_info.get("display_specialization", "") or "")
        slot_values = source_info.get("display_attribute_slots", [])
        if not isinstance(slot_values, list):
            slot_values = []
        attribute_letters = [str(v).strip().upper() for v in slot_values if str(v).strip()]
        try:
            value_number = int(display_value) if display_value else 0
        except Exception:
            value_number = 0
        print(
            "[ROLL SELECT]",
            source_key,
            f"row={source_info.get('row')}",
            f'name="{display_name}"',
            f"value={value_number}",
            f"attrs={attribute_letters}",
            f'specialization="{specialization_text}"',
        )
        self.open_skill_roll_dialog(source_key)

    def open_skill_roll_dialog(self, source_key):
        source_info = self.skill_source_infos.get(source_key)
        if not isinstance(source_info, dict) or source_info.get("row") is None:
            return

        display_name = str(source_info.get("display_name", ""))
        specialization_text = str(source_info.get("display_specialization", "") or "")
        slot_values = source_info.get("display_attribute_slots", [])
        if not isinstance(slot_values, list):
            slot_values = []
        slot_values = (slot_values + ["", "", "", ""])[:4]
        resolved_letters = [str(v).strip().upper() for v in slot_values if str(v).strip()]
        attrs_text = ", ".join(resolved_letters) if resolved_letters else "-"
        try:
            skill_value = int(source_info.get("display_value", "0") or 0)
        except Exception:
            skill_value = 0
        skill_value_allowed = bool(resolved_letters) or bool(specialization_text.strip())
        roll_layout = self.load_roll_dialog_layout_config()
        dialog_cfg = roll_layout.get("dialog", {})
        sections_cfg = roll_layout.get("sections", {})
        spec_cfg = roll_layout.get("specialization_box", {})
        counter_cfg = roll_layout.get("counter", {})
        keep_cfg = roll_layout.get("keep_options", {})
        preview_cfg = roll_layout.get("roll_preview", {})
        direct_send_cfg = roll_layout.get("direct_send", {})
        buttons_cfg = roll_layout.get("buttons", {})
        spec_options_cfg = roll_layout.get("specialization_options", {})
        paradigm_cfg = roll_layout.get("paradigm", {})
        perk_suggestions_cfg = roll_layout.get("perk_suggestions", {})
        labels_cfg = roll_layout.get("labels", {})
        checkbox_cfg = roll_layout.get("checkbox", {})
        debug_cfg = roll_layout.get("debug", {})

        dialog_title = str(dialog_cfg.get("title", "Roll20 Wurf-Assistent"))
        dialog_w = self._safe_int(dialog_cfg.get("w", 700), 700)
        dialog_h = self._safe_int(dialog_cfg.get("h", 620), 620)
        text_color = str(dialog_cfg.get("text_color", "#f2f2f2"))
        muted_text_color = str(dialog_cfg.get("muted_text_color", "#c8c0aa"))
        accent_color = str(dialog_cfg.get("accent_color", "#f2d28b"))
        border_color = str(dialog_cfg.get("border_color", "#8a6a32"))
        base_font_size = self._safe_int(dialog_cfg.get("font_size", 13), 13)
        title_font_size = self._safe_int(dialog_cfg.get("title_font_size", 18), 18)
        dialog_bg = str(dialog_cfg.get("background", "#202426"))
        spacing = self._safe_int(sections_cfg.get("spacing", 12), 12)
        spec_height = self._safe_int(spec_cfg.get("height", 64), 64)
        spec_font_size = self._safe_int(spec_cfg.get("font_size", 13), 13)
        preview_label_text = str(preview_cfg.get("label", "Roll20-Befehl:"))
        preview_font_size = self._safe_int(preview_cfg.get("font_size", 22), 22)
        preview_height = self._safe_int(preview_cfg.get("height", 58), 58)
        section_title_color = str(labels_cfg.get("section_title_color", accent_color))
        section_title_font_size = self._safe_int(
            labels_cfg.get("section_title_font_size", base_font_size), base_font_size
        )
        normal_text_color = str(labels_cfg.get("normal_text_color", text_color))
        normal_text_font_size = self._safe_int(
            labels_cfg.get("normal_text_font_size", base_font_size), base_font_size
        )
        muted_text_cfg_color = str(labels_cfg.get("muted_text_color", muted_text_color))
        muted_text_font_size = self._safe_int(
            labels_cfg.get("muted_text_font_size", max(10, base_font_size - 1)),
            max(10, base_font_size - 1),
        )
        hint_text_color = str(labels_cfg.get("hint_text_color", muted_text_cfg_color))
        hint_text_font_size = self._safe_int(
            labels_cfg.get("hint_text_font_size", muted_text_font_size), muted_text_font_size
        )
        debug_preview_enabled = bool(debug_cfg.get("preview", False))
        debug_toggles_enabled = bool(debug_cfg.get("toggles", True))
        debug_info_only_enabled = bool(debug_cfg.get("info_only", False))
        debug_paradigm_enabled = bool(debug_cfg.get("paradigm", False))
        perk_suggestions_title = str(
            perk_suggestions_cfg.get("title", "Perk-/Nachteil-Vorschläge:")
        )
        perk_suggestions_empty_text = str(
            perk_suggestions_cfg.get("empty_text", "Keine passenden Perk-/Nachteil-Vorschläge")
        )
        perk_suggestions_hint = str(
            perk_suggestions_cfg.get(
                "hint",
                "Angehakte Vorschläge wirken nur manuell auf diesen Wurf.",
            )
        )
        perk_suggestions_max_visible = self._safe_int(
            perk_suggestions_cfg.get("max_visible", 4), 4
        )
        if perk_suggestions_max_visible <= 0:
            perk_suggestions_max_visible = 4
        paradigm_text = str(paradigm_cfg.get("text", "Paradigma / Brennen verwenden (+10)"))
        paradigm_bonus = self._safe_int(paradigm_cfg.get("bonus", 10), 10)
        paradigm_tooltip = str(
            paradigm_cfg.get(
                "tooltip",
                "Manueller Schalter. Es wird kein Paradigma automatisch verbraucht.",
            )
        )

        specialization_items = self.split_specialization_text(specialization_text)
        skill_info_for_perks = {
            "display_name": display_name,
            "display_specialization": specialization_text,
            "source_key": source_key,
        }
        try:
            perk_rules_config = self.load_perk_rules_config()
            perk_rules = perk_rules_config.get("rules", [])
            character_perk_entries = self.collect_character_perk_entries()
            perk_suggestions = self.find_matching_roll_suggestions(
                skill_info_for_perks,
                character_perk_entries,
                perk_rules,
            )
        except Exception as exc:
            perk_suggestions = []
            print("[ROLL PERK SUGGESTIONS ERROR]", str(exc))
        if not isinstance(perk_suggestions, list):
            perk_suggestions = []
        try:
            wellbeing_suggestions = self.get_active_wellbeing_roll_suggestions(
                {
                    "display_name": display_name,
                    "display_specialization": specialization_text,
                    "display_attribute_slots": slot_values,
                }
            )
        except Exception as exc:
            wellbeing_suggestions = []
            print("[ROLL WELLBEING SUGGESTIONS ERROR]", str(exc))
        if not isinstance(wellbeing_suggestions, list):
            wellbeing_suggestions = []

        dynamic_extra = 0
        dynamic_extra += max(0, len(specialization_items) - 6) * 14
        dynamic_extra += max(0, len(perk_suggestions) - 2) * 18
        dynamic_extra += max(0, len(wellbeing_suggestions) - 2) * 18

        checkbox_text_color = str(checkbox_cfg.get("text_color", normal_text_color))
        checkbox_font_size = self._safe_int(checkbox_cfg.get("font_size", normal_text_font_size), normal_text_font_size)
        checkbox_spacing = self._safe_int(checkbox_cfg.get("spacing", 6), 6)
        checkbox_use_assets = bool(checkbox_cfg.get("use_assets", False))
        checkbox_asset_checked = str(checkbox_cfg.get("asset_checked", "") or "")
        checkbox_asset_unchecked = str(checkbox_cfg.get("asset_unchecked", "") or "")

        counter_use_assets = bool(counter_cfg.get("use_assets", False))
        counter_minus_asset = str(counter_cfg.get("minus_asset", "") or "")
        counter_plus_asset = str(counter_cfg.get("plus_asset", "") or "")

        theme_dir = self.base_dir / "assets" / "themes" / self.get_active_theme()
        fallback_theme_dir = self.base_dir / "assets" / "themes" / "diablo"

        def resolve_roll_asset_path(relative_path):
            rel = str(relative_path or "").strip()
            if not rel:
                return None
            candidate_paths = [
                theme_dir / rel,
                theme_dir / "ui" / rel,
                fallback_theme_dir / rel,
                fallback_theme_dir / "ui" / rel,
            ]
            for path in candidate_paths:
                if path.exists():
                    return path
            return None

        def build_checkbox_style():
            style = (
                f"QCheckBox {{ color: {checkbox_text_color}; font-size: {checkbox_font_size}px; spacing: {checkbox_spacing}px; }}"
            )
            if checkbox_use_assets:
                checked_path = resolve_roll_asset_path(checkbox_asset_checked)
                unchecked_path = resolve_roll_asset_path(checkbox_asset_unchecked)
                if checked_path is not None and unchecked_path is not None:
                    checked_url = checked_path.as_posix()
                    unchecked_url = unchecked_path.as_posix()
                    style += (
                        "QCheckBox::indicator { width: 16px; height: 16px; }"
                        f"QCheckBox::indicator:checked {{ image: url({checked_url}); }}"
                        f"QCheckBox::indicator:unchecked {{ image: url({unchecked_url}); }}"
                    )
            return style

        checkbox_style = build_checkbox_style()
        dialog = QDialog(self)
        dialog.setWindowTitle(dialog_title)
        dialog.setModal(True)
        dialog.resize(dialog_w, min(980, dialog_h + dynamic_extra))
        dialog.setStyleSheet(
            f"QDialog {{ background: {dialog_bg}; color: {text_color}; font-size: {base_font_size}px; }}"
        )
        layout = QVBoxLayout(dialog)
        layout.setSpacing(spacing)

        header = QLabel(f"Fertigkeit: {display_name}")
        header.setStyleSheet(f"font-size: {title_font_size}px; font-weight: 700; color: {accent_color};")
        layout.addWidget(header)
        value_label = QLabel(f"Wert: {skill_value}")
        value_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
        layout.addWidget(value_label)
        attrs_label = QLabel(f"Attribute: {attrs_text}")
        attrs_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
        layout.addWidget(attrs_label)

        spec_title = QLabel("Spezialisierung:")
        spec_title.setStyleSheet(
            f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;"
        )
        layout.addWidget(spec_title)
        spec_options_max_rows_per_column = self._safe_int(
            spec_options_cfg.get("max_rows_per_column", 6), 6
        )
        if spec_options_max_rows_per_column <= 0:
            spec_options_max_rows_per_column = 6
        spec_options_column_spacing = self._safe_int(spec_options_cfg.get("column_spacing", 24), 24)
        spec_options_row_spacing = self._safe_int(spec_options_cfg.get("row_spacing", 8), 8)
        spec_preview_max_chars = self._safe_int(spec_options_cfg.get("preview_max_chars", 48), 48)
        specialization_preview_text = self.build_specialization_preview_text(
            specialization_text,
            spec_preview_max_chars,
        )

        spec_value = QLabel(specialization_preview_text)
        spec_value.setWordWrap(True)
        spec_value.setStyleSheet(
            f"background: {str(spec_cfg.get('background', '#141618'))}; "
            f"border: 1px solid {str(spec_cfg.get('border_color', '#3a3a3a'))}; "
            f"padding: 8px; color: {str(spec_cfg.get('text_color', '#ffffff'))}; "
            f"font-size: {spec_font_size}px;"
        )
        spec_value.setMinimumHeight(spec_height)
        layout.addWidget(spec_value)

        spec_options_title = str(spec_options_cfg.get("title", "Spezialisierungen:"))
        spec_options_hint = str(
            spec_options_cfg.get("hint", "Spezialisierungen: +1 Vorteil je Auswahl")
        )
        spec_options_empty_text = str(
            spec_options_cfg.get("empty_text", "Keine Spezialisierung vorhanden")
        )
        spec_options_text_color = str(spec_options_cfg.get("text_color", text_color))
        spec_options_hint_color = str(spec_options_cfg.get("hint_color", muted_text_color))
        spec_options_font_size = self._safe_int(spec_options_cfg.get("font_size", base_font_size), base_font_size)

        spec_options_title_label = QLabel(spec_options_title)
        spec_options_title_label.setStyleSheet(
            f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;"
        )
        layout.addWidget(spec_options_title_label)

        specialization_checkboxes = []
        if specialization_items:
            checkboxes_grid_widget = QWidget(dialog)
            checkboxes_grid_layout = QGridLayout(checkboxes_grid_widget)
            checkboxes_grid_layout.setContentsMargins(0, 0, 0, 0)
            checkboxes_grid_layout.setHorizontalSpacing(spec_options_column_spacing)
            checkboxes_grid_layout.setVerticalSpacing(spec_options_row_spacing)
            for index, item in enumerate(specialization_items):
                checkbox = QCheckBox(item, dialog)
                checkbox.setChecked(False)
                checkbox.setStyleSheet(checkbox_style)
                row = index % spec_options_max_rows_per_column
                col = index // spec_options_max_rows_per_column
                checkboxes_grid_layout.addWidget(checkbox, row, col)
                specialization_checkboxes.append(checkbox)
            checkboxes_grid_layout.setColumnStretch(99, 1)
            layout.addWidget(checkboxes_grid_widget)
            spec_hint_label = QLabel(spec_options_hint)
            spec_hint_label.setStyleSheet(
                f"color: {hint_text_color}; font-size: {hint_text_font_size}px;"
            )
            layout.addWidget(spec_hint_label)
        else:
            spec_empty_label = QLabel(spec_options_empty_text)
            spec_empty_label.setStyleSheet(
                f"color: {hint_text_color}; font-size: {hint_text_font_size}px;"
            )
            layout.addWidget(spec_empty_label)

        perk_suggestion_checkboxes = []
        if perk_suggestions:
            perk_title_label = QLabel(perk_suggestions_title)
            perk_title_label.setStyleSheet(
                f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;"
            )
            layout.addWidget(perk_title_label)
            visible_suggestions = perk_suggestions[:perk_suggestions_max_visible]
            for suggestion in visible_suggestions:
                label_text = str(suggestion.get("label", "Regelvorschlag"))
                source_type = "Perk" if str(suggestion.get("source_type", "")) == "perk" else "Nachteil"
                source_name = str(suggestion.get("source_name", "") or "")
                source_effect = str(suggestion.get("source_effect", "") or "")
                source_text = f"{source_type} {source_name}".strip()
                compact_effect = self.build_compact_preview_text(source_effect, 60)
                compact_source_line = source_text if not compact_effect else f"{source_text} · {compact_effect}"
                compact_source_line = self.build_compact_preview_text(compact_source_line, 70)
                checkbox = QCheckBox(label_text, dialog)
                checkbox.setChecked(False)
                checkbox.setStyleSheet(checkbox_style)
                checkbox.setProperty("rule_id", str(suggestion.get("rule_id", "")))
                checkbox.setProperty("suggested_effect", suggestion.get("suggested_effect", {}))
                checkbox.setToolTip(
                    source_text if not source_effect else f"{source_text}\nEffekt: {source_effect}"
                )
                layout.addWidget(checkbox)
                source_label = QLabel(compact_source_line)
                source_label.setStyleSheet(
                    f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;"
                )
                source_label.setToolTip(
                    source_text if not source_effect else f"{source_text}\nEffekt: {source_effect}"
                )
                layout.addWidget(source_label)
                perk_suggestion_checkboxes.append(checkbox)

            remaining = len(perk_suggestions) - len(visible_suggestions)
            if remaining > 0:
                more_label = QLabel(f"... +{remaining} weitere Vorschläge")
                more_label.setStyleSheet(
                    f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;"
                )
                layout.addWidget(more_label)
            perk_hint_label = QLabel(perk_suggestions_hint)
            perk_hint_label.setStyleSheet(
                f"color: {hint_text_color}; font-size: {hint_text_font_size}px;"
            )
            layout.addWidget(perk_hint_label)

        wellbeing_suggestion_checkboxes = []
        if wellbeing_suggestions:
            wellbeing_title_label = QLabel("Wohlbefinden-Vorschläge:")
            wellbeing_title_label.setStyleSheet(
                f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;"
            )
            layout.addWidget(wellbeing_title_label)
            for suggestion in wellbeing_suggestions:
                label_text = str(suggestion.get("label", "Wohlbefinden-Vorschlag"))
                source_label = str(suggestion.get("source_label", "") or "")
                source_text = f"Quelle: {source_label}" if source_label else "Quelle: Wohlbefinden"
                checkbox = QCheckBox(label_text, dialog)
                checkbox.setChecked(False)
                checkbox.setStyleSheet(checkbox_style)
                checkbox.setProperty("wellbeing_label", source_label)
                checkbox.setProperty("suggested_effect", suggestion.get("suggested_effect", {}))
                checkbox.setToolTip(source_text)
                layout.addWidget(checkbox)
                source_row = QLabel(source_text)
                source_row.setStyleSheet(
                    f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;"
                )
                source_row.setToolTip(source_text)
                layout.addWidget(source_row)
                wellbeing_suggestion_checkboxes.append(checkbox)

        skill_usage_text = (
            f"Skillwert wird verwendet: Ja (+{skill_value})"
            if skill_value_allowed
            else "Skillwert wird verwendet: Nein (keine Attribute/Spezialisierung)"
        )
        skill_usage_label = QLabel(skill_usage_text)
        skill_usage_label.setStyleSheet(
            f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;"
        )
        layout.addWidget(skill_usage_label)

        controls = QHBoxLayout()
        advantages_spin = QSpinBox(dialog)
        advantages_spin.setRange(0, 99)
        advantages_spin.setValue(0)
        advantages_spin.setButtonSymbols(QSpinBox.NoButtons)
        advantages_spin.setFixedWidth(self._safe_int(counter_cfg.get("value_w", 42), 42))
        disadvantages_spin = QSpinBox(dialog)
        disadvantages_spin.setRange(0, 99)
        disadvantages_spin.setValue(0)
        disadvantages_spin.setButtonSymbols(QSpinBox.NoButtons)
        disadvantages_spin.setFixedWidth(self._safe_int(counter_cfg.get("value_w", 42), 42))
        manual_bonus_spin = QSpinBox(dialog)
        manual_bonus_spin.setRange(-999, 999)
        manual_bonus_spin.setValue(0)

        adv_minus = QPushButton("-", dialog)
        adv_plus = QPushButton("+", dialog)
        dis_minus = QPushButton("-", dialog)
        dis_plus = QPushButton("+", dialog)
        for button in (adv_minus, adv_plus, dis_minus, dis_plus):
            button.setFixedSize(
                self._safe_int(counter_cfg.get("button_w", 30), 30),
                self._safe_int(counter_cfg.get("button_h", 26), 26),
            )
            button.setStyleSheet(
                f"background: {str(counter_cfg.get('button_background', '#34383c'))}; "
                f"color: {str(counter_cfg.get('button_text_color', '#ffffff'))}; "
                f"border: 1px solid {str(counter_cfg.get('button_border_color', '#5c6268'))};"
            )

        if counter_use_assets:
            minus_icon_path = resolve_roll_asset_path(counter_minus_asset)
            plus_icon_path = resolve_roll_asset_path(counter_plus_asset)
            if minus_icon_path is not None and plus_icon_path is not None:
                minus_icon = QIcon(str(minus_icon_path))
                plus_icon = QIcon(str(plus_icon_path))
                for button in (adv_minus, dis_minus):
                    button.setIcon(minus_icon)
                    button.setText("")
                for button in (adv_plus, dis_plus):
                    button.setIcon(plus_icon)
                    button.setText("")

        advantages_label = QLabel("Vorteile:")
        advantages_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
        disadvantages_label = QLabel("Nachteile:")
        disadvantages_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
        manual_label = QLabel("Manueller Bonus/Malus:")
        manual_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
        controls.addWidget(advantages_label)
        controls.addWidget(adv_minus)
        controls.addWidget(advantages_spin)
        controls.addWidget(adv_plus)
        controls.addWidget(disadvantages_label)
        controls.addWidget(dis_minus)
        controls.addWidget(disadvantages_spin)
        controls.addWidget(dis_plus)
        controls.addSpacing(10)
        controls.addWidget(manual_label)
        controls.addWidget(manual_bonus_spin)
        controls.addStretch()
        layout.addLayout(controls)

        keep_layout = QHBoxLayout()
        keep_group = QButtonGroup(dialog)
        keep_high = QRadioButton(str(keep_cfg.get("kh_text", "Höchsten behalten (kh1)")), dialog)
        keep_low = QRadioButton(str(keep_cfg.get("kl_text", "Niedrigsten behalten (kl1)")), dialog)
        keep_group.addButton(keep_high)
        keep_group.addButton(keep_low)
        keep_high.setChecked(True)
        keep_title = QLabel("Keep:")
        keep_title.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
        keep_high.setStyleSheet(checkbox_style)
        keep_low.setStyleSheet(checkbox_style)
        keep_layout.addWidget(keep_title)
        keep_layout.addWidget(keep_high)
        keep_layout.addWidget(keep_low)
        keep_layout.addStretch()
        layout.addLayout(keep_layout)

        paradigm_checkbox = QCheckBox(paradigm_text, dialog)
        paradigm_checkbox.setChecked(False)
        paradigm_checkbox.setToolTip(paradigm_tooltip)
        paradigm_checkbox.setStyleSheet(checkbox_style)
        layout.addWidget(paradigm_checkbox)

        preview_title = QLabel(preview_label_text)
        preview_title.setStyleSheet(
            f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;"
        )
        layout.addWidget(preview_title)

        roll_command_edit = QLineEdit(dialog)
        roll_command_edit.setPlaceholderText("/r 1d20")
        roll_command_edit.setStyleSheet(
            f"font-size: {preview_font_size}px; font-weight: 700; "
            f"color: {str(preview_cfg.get('text_color', '#f2d28b'))}; "
            f"background: {str(preview_cfg.get('background', '#101214'))}; "
            f"border: 1px solid {str(preview_cfg.get('border_color', '#8a6a32'))}; padding: 10px;"
        )
        roll_command_edit.setMinimumHeight(preview_height)
        layout.addWidget(roll_command_edit)

        direct_send_checkbox = None
        if bool(direct_send_cfg.get("enabled", True)):
            direct_send_checkbox = QCheckBox(str(direct_send_cfg.get("text", "Direkt an Roll20 senden")), dialog)
            direct_send_checkbox.setToolTip(
                str(direct_send_cfg.get("tooltip", "Noch nicht implementiert. Aktuell wird nur kopiert."))
            )
            direct_send_checkbox.setStyleSheet(checkbox_style)
            layout.addWidget(direct_send_checkbox)

        buttons_layout = QHBoxLayout()
        copy_button = QPushButton(str(buttons_cfg.get("copy_text", "Kopieren")), dialog)
        close_button = QPushButton(str(buttons_cfg.get("close_text", "Schließen")), dialog)
        buttons_layout.addStretch()
        buttons_layout.addWidget(copy_button)
        buttons_layout.addWidget(close_button)
        layout.addLayout(buttons_layout)

        def current_keep_mode():
            if keep_high.isChecked():
                return "kh1"
            if keep_low.isChecked():
                return "kl1"
            return ""

        def adjust_spin(spinbox, delta):
            spinbox.setValue(max(spinbox.minimum(), min(spinbox.maximum(), spinbox.value() + delta)))

        def collect_checked_suggestion_effects(checkboxes, source_label):
            collected = {
                "advantage": 0,
                "disadvantage": 0,
                "extra_bonuses": [],
                "info_only": [],
            }
            if not isinstance(checkboxes, list):
                return collected
            for checkbox in checkboxes:
                if checkbox is None or not checkbox.isChecked():
                    continue
                effect = checkbox.property("suggested_effect")
                if not isinstance(effect, dict):
                    effect = {}
                label = str(
                    checkbox.property("rule_id")
                    or checkbox.property("wellbeing_label")
                    or checkbox.text()
                    or ""
                )

                if bool(effect.get("info_only", False)):
                    collected["info_only"].append(label)
                    continue

                try:
                    advantage = int(effect.get("advantage", 0) or 0)
                except Exception:
                    advantage = 0
                try:
                    disadvantage = int(effect.get("disadvantage", 0) or 0)
                except Exception:
                    disadvantage = 0
                try:
                    flat_bonus = int(effect.get("flat_bonus", 0) or 0)
                except Exception:
                    flat_bonus = 0
                try:
                    flat_malus = int(effect.get("flat_malus", 0) or 0)
                except Exception:
                    flat_malus = 0

                collected["advantage"] += max(0, advantage)
                collected["disadvantage"] += max(0, disadvantage)
                if flat_bonus != 0:
                    collected["extra_bonuses"].append(flat_bonus)
                if flat_malus != 0:
                    collected["extra_bonuses"].append(-abs(flat_malus))

            if debug_info_only_enabled:
                for info_label in collected["info_only"]:
                    print(f'[ROLL EFFECT INFO_ONLY] source={source_label} label="{info_label}"')
            return collected

        def update_roll_preview():
            specialization_advantages = sum(
                1 for checkbox in specialization_checkboxes if checkbox.isChecked()
            )
            perk_effects = collect_checked_suggestion_effects(perk_suggestion_checkboxes, "perk")
            wellbeing_effects = collect_checked_suggestion_effects(
                wellbeing_suggestion_checkboxes, "wellbeing"
            )

            dice_count = (
                1
                + advantages_spin.value()
                + specialization_advantages
                + perk_effects["advantage"]
                + wellbeing_effects["advantage"]
                - disadvantages_spin.value()
                - perk_effects["disadvantage"]
                - wellbeing_effects["disadvantage"]
            )
            if dice_count <= 0:
                dice_count = 1
            skill_bonus = skill_value if skill_value_allowed else 0
            manual_bonus = manual_bonus_spin.value()
            extra_bonuses = []
            if paradigm_checkbox.isChecked():
                extra_bonuses.append(paradigm_bonus)
                if debug_paradigm_enabled:
                    print(f"[ROLL PARADIGM] active=True bonus={paradigm_bonus}")
            extra_bonuses.extend(perk_effects["extra_bonuses"])
            extra_bonuses.extend(wellbeing_effects["extra_bonuses"])
            command = self.build_roll20_command(
                dice_count,
                current_keep_mode(),
                skill_bonus,
                manual_bonus,
                extra_bonuses,
            )
            roll_command_edit.setText(command)
            if debug_preview_enabled:
                print(
                    "[ROLL PREVIEW]",
                    f"dice={dice_count}",
                    f"skill={skill_bonus}",
                    f"manual={manual_bonus}",
                    f"extras={extra_bonuses}",
                    f'command="{command}"',
                )

        def copy_roll_command():
            command = roll_command_edit.text().strip()
            QApplication.clipboard().setText(command)
            print("[ROLL COPY]", command)
            if direct_send_checkbox is not None and direct_send_checkbox.isChecked():
                print("[ROLL SEND PLACEHOLDER] direct Roll20 send requested but not implemented")
            dialog.accept()

        def on_perk_suggestion_toggled(checkbox, checked):
            if checkbox is None:
                return
            rule_id = str(checkbox.property("rule_id") or "")
            effect = checkbox.property("suggested_effect")
            if not isinstance(effect, dict):
                effect = {}
            compact_effect = json.dumps(effect, ensure_ascii=False, separators=(",", ":"))
            if debug_toggles_enabled:
                print(
                    f"[PERK SUGGESTION TOGGLE] rule={rule_id} checked={bool(checked)} effect={compact_effect}"
                )
            update_roll_preview()

        def on_wellbeing_suggestion_toggled(checkbox, checked):
            if checkbox is None:
                return
            label = str(checkbox.property("wellbeing_label") or "")
            effect = checkbox.property("suggested_effect")
            if not isinstance(effect, dict):
                effect = {}
            compact_effect = json.dumps(effect, ensure_ascii=False, separators=(",", ":"))
            if debug_toggles_enabled:
                print(
                    f'[WELLBEING SUGGESTION TOGGLE] label="{label}" checked={bool(checked)} effect={compact_effect}'
                )
            update_roll_preview()

        advantages_spin.valueChanged.connect(update_roll_preview)
        disadvantages_spin.valueChanged.connect(update_roll_preview)
        manual_bonus_spin.valueChanged.connect(update_roll_preview)
        keep_high.toggled.connect(update_roll_preview)
        keep_low.toggled.connect(update_roll_preview)
        paradigm_checkbox.toggled.connect(update_roll_preview)
        adv_minus.clicked.connect(lambda: adjust_spin(advantages_spin, -1))
        adv_plus.clicked.connect(lambda: adjust_spin(advantages_spin, 1))
        dis_minus.clicked.connect(lambda: adjust_spin(disadvantages_spin, -1))
        dis_plus.clicked.connect(lambda: adjust_spin(disadvantages_spin, 1))
        for checkbox in specialization_checkboxes:
            checkbox.toggled.connect(update_roll_preview)
        for checkbox in perk_suggestion_checkboxes:
            checkbox.toggled.connect(
                lambda checked=False, cb=checkbox: on_perk_suggestion_toggled(cb, checked)
            )
        for checkbox in wellbeing_suggestion_checkboxes:
            checkbox.toggled.connect(
                lambda checked=False, cb=checkbox: on_wellbeing_suggestion_toggled(cb, checked)
            )
        copy_button.clicked.connect(copy_roll_command)
        close_button.clicked.connect(dialog.close)
        update_roll_preview()
        dialog.exec()

    def _inventory_cache_text(self, sheet_cache, cell_ref):
        cell_data = sheet_cache.get(cell_ref)
        value = cell_data.get("value") if isinstance(cell_data, dict) else cell_data
        if value is None:
            return ""
        return str(value).strip()

    def _inventory_cell_ref(self, col_index, row_index):
        return f"{self._col_index_to_letters(col_index)}{row_index}"

    def _inventory_cell_sort_key(self, cell_ref):
        match = re.match(r"^([A-Z]+)(\d+)$", str(cell_ref).strip().upper())
        if not match:
            return (0, 0)
        return (int(match.group(2)), self._col_letters_to_index(match.group(1)))

    def _normalize_inventory_header(self, value):
        text = str(value or "").strip().lower()
        return text.replace("ü", "ue")

    def _get_inventory_sheet_cache(self):
        sheet_cache = self.loader.cell_cache.get("Inventar", {})
        return sheet_cache if isinstance(sheet_cache, dict) else {}

    def _find_inventory_title_left_of_pair(self, row_values, row, pl_col, title_kind):
        if title_kind == "books":
            accepted = {"buecher"}
        else:
            accepted = {"inventar", "im inventar"}
        for col in range(pl_col - 1, max(0, pl_col - 21), -1):
            normalized = self._normalize_inventory_header(row_values.get((row, col), ""))
            if normalized in accepted:
                return col
        return None

    def _build_inventory_section_from_columns(
        self, sheet_cache, section_id, title, header_row, name_col, pl_col, count_col
    ):
        max_row = header_row + 20
        data_cols = {name_col, pl_col, count_col}
        for cell_ref in sheet_cache.keys():
            row, col = self._inventory_cell_sort_key(cell_ref)
            if col not in data_cols:
                continue
            value = self._inventory_cache_text(sheet_cache, cell_ref)
            if row > header_row and value and row > max_row:
                max_row = row

        rows = []
        for row_index in range(header_row + 1, max_row + 1):
            name_cell_ref = self._inventory_cell_ref(name_col, row_index)
            pl_cell_ref = self._inventory_cell_ref(pl_col, row_index)
            count_cell_ref = self._inventory_cell_ref(count_col, row_index)
            name = self._inventory_cache_text(
                sheet_cache, name_cell_ref
            )
            pl = self._inventory_cache_text(sheet_cache, pl_cell_ref)
            count = self._inventory_cache_text(
                sheet_cache, count_cell_ref
            )
            rows.append(
                {
                    "name": name,
                    "pl": pl,
                    "count": count,
                    "name_cell": name_cell_ref,
                    "pl_cell": pl_cell_ref,
                    "count_cell": count_cell_ref,
                    "is_empty_slot": not bool(name or pl or count),
                    "storage": "sheet",
                }
            )

        header = (
            f"{self._inventory_cell_ref(name_col, header_row)}:"
            f"{self._inventory_cell_ref(count_col, header_row)}"
        )
        data_range = (
            f"{self._inventory_cell_ref(name_col, header_row + 1)}:"
            f"{self._inventory_cell_ref(count_col, max_row)}"
        )
        return {
            "id": section_id,
            "title": title,
            "header": header,
            "range": data_range,
            "rows": rows,
        }

    def get_inventory_display_data(self):
        sheet_cache = self._get_inventory_sheet_cache()
        money = {
            "gulden": self.format_character_display_value(
                self.get_cache_cell_value("Inventar", "B9", None), "auto"
            ),
            "schilling": self.format_character_display_value(
                self.get_cache_cell_value("Inventar", "E9", None), "auto"
            ),
            "heller": self.format_character_display_value(
                self.get_cache_cell_value("Inventar", "H9", None), "auto"
            ),
            "pfifferling": self.format_character_display_value(
                self.get_cache_cell_value("Inventar", "K9", None), "auto"
            ),
        }
        print(
            "[INVENTORY] money "
            f"Gulden={money['gulden']} Schilling={money['schilling']} "
            f"Heller={money['heller']} Pfifferling={money['pfifferling']}"
        )

        row_values = {}
        for cell_ref, cell_data in sheet_cache.items():
            row, col = self._inventory_cell_sort_key(cell_ref)
            if row <= 0 or col <= 0:
                continue
            row_values[(row, col)] = cell_data.get("value") if isinstance(cell_data, dict) else cell_data

        header_pairs = []
        for (row, col), value in row_values.items():
            if self._normalize_inventory_header(value) != "pl":
                continue
            next_value = row_values.get((row, col + 1), "")
            if self._normalize_inventory_header(next_value) == "anzahl":
                header_pairs.append({"row": row, "pl_col": col, "count_col": col + 1})
        header_pairs.sort(key=lambda item: (item["row"], item["pl_col"]))

        books_pairs = []
        inventory_pairs = []
        for pair in header_pairs:
            book_col = self._find_inventory_title_left_of_pair(
                row_values, pair["row"], pair["pl_col"], "books"
            )
            if book_col is not None:
                pair["name_col"] = book_col
                books_pairs.append(pair)
                continue
            inv_col = self._find_inventory_title_left_of_pair(
                row_values, pair["row"], pair["pl_col"], "inventory"
            )
            if inv_col is not None:
                pair["name_col"] = inv_col
            inventory_pairs.append(pair)

        previous_count_col = None
        for pair in inventory_pairs:
            if pair.get("name_col") is None and previous_count_col is not None:
                candidate = previous_count_col + 3
                if candidate < pair["pl_col"]:
                    pair["name_col"] = candidate
            previous_count_col = pair["count_col"]

        sections = []
        expected = [
            ("inventory_left", "Inventar", inventory_pairs[0] if len(inventory_pairs) > 0 else None),
            ("inventory_middle", "Inventar", inventory_pairs[1] if len(inventory_pairs) > 1 else None),
            ("books", "Bücher", books_pairs[0] if books_pairs else None),
        ]
        for section_id, title, pair in expected:
            if not pair or pair.get("name_col") is None:
                print(f"[INVENTORY MAP] block not found: {section_id}")
                sections.append({"id": section_id, "title": title, "header": "-", "range": "-", "rows": []})
                continue
            section = self._build_inventory_section_from_columns(
                sheet_cache,
                section_id,
                title,
                pair["row"],
                pair["name_col"],
                pair["pl_col"],
                pair["count_col"],
            )
            sections.append(section)
            print(
                f"[INVENTORY MAP] section {section_id} "
                f"header={section['header']} rows={len(section['rows'])}"
            )
        return {"money": money, "sections": sections}

    def _sanitize_inventory_category_id(self, text):
        normalized = re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized or "inventory_extra"

    def _is_inventory_subsection_header_row(self, row):
        if not isinstance(row, dict):
            return False
        name = str(row.get("name", "") or "").strip()
        pl = str(row.get("pl", "") or "").strip().lower()
        count = str(row.get("count", "") or "").strip().lower()
        if not name:
            return False
        return pl == "pl" and count == "anzahl"

    def build_inventory_categories(self, sections):
        ordered_categories = []
        by_id = {}

        def ensure_category(cat_id, title, header_title, always_show=False):
            existing = by_id.get(cat_id)
            if existing is not None:
                return existing
            category = {
                "id": cat_id,
                "title": title,
                "header_title": header_title,
                "rows": [],
                "always_show": bool(always_show),
            }
            by_id[cat_id] = category
            ordered_categories.append(category)
            return category

        section_title_map = {
            "inventory_left": ("Inventar 01", "Inventar", True),
            "inventory_middle": ("Inventar 02", "Inventar", True),
            "books": ("Bücher", "Bücher", False),
        }

        for section in sections:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id", "") or "")
            default = section_title_map.get(
                section_id,
                (str(section.get("title", "Inventar")), str(section.get("title", "Inventar")), False),
            )
            category = ensure_category(section_id, default[0], default[1], always_show=default[2])
            rows = section.get("rows", [])
            if not isinstance(rows, list):
                rows = []

            dynamic_category = None
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if self._is_inventory_subsection_header_row(row):
                    subsection_title = str(row.get("name", "") or "").strip()
                    dynamic_id = f"sub_{self._sanitize_inventory_category_id(subsection_title)}"
                    dynamic_category = ensure_category(
                        dynamic_id,
                        subsection_title.title(),
                        subsection_title.title(),
                        always_show=False,
                    )
                    continue
                if dynamic_category is not None:
                    dynamic_category["rows"].append(row)
                else:
                    category["rows"].append(row)

        visible_categories = []
        for category in ordered_categories:
            if category.get("always_show"):
                visible_categories.append(category)
                continue
            rows = category.get("rows", [])
            if isinstance(rows, list) and rows:
                visible_categories.append(category)
        return visible_categories

    def get_inventory_tab_label(self, slot_id, default_label):
        try:
            labels = self.loader.get_inventory_tab_labels()
            if isinstance(labels, dict):
                value = labels.get(str(slot_id))
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except Exception:
            pass
        return str(default_label)

    def get_inventory_custom_rows(self, slot_id):
        try:
            rows = self.loader.get_inventory_custom_rows(slot_id)
        except Exception:
            rows = []
        if not isinstance(rows, list):
            return []
        result = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                row = {}
            result.append(
                {
                    "name": str(row.get("name", "") or ""),
                    "pl": str(row.get("pl", "") or ""),
                    "count": str(row.get("count", "") or ""),
                    "storage": "custom",
                    "custom_slot_id": str(slot_id),
                    "custom_row_index": index,
                    "is_empty_slot": not bool(
                        str(row.get("name", "") or "")
                        or str(row.get("pl", "") or "")
                        or str(row.get("count", "") or "")
                    ),
                }
            )
        return result

    def _has_inventory_sheet_mapping(self, row):
        if not isinstance(row, dict):
            return False
        return bool(
            str(row.get("name_cell", "") or "").strip()
            or str(row.get("pl_cell", "") or "").strip()
            or str(row.get("count_cell", "") or "").strip()
        )

    def build_inventory_table_rows(self, category, min_rows):
        slot_id = str(category.get("id", "") if isinstance(category, dict) else "")
        rows = list(category.get("rows", []) if isinstance(category, dict) else [])
        normalized_rows = []
        has_sheet_mapping = False
        for row in rows:
            if not isinstance(row, dict):
                row = {}
            row = dict(row)
            if self._has_inventory_sheet_mapping(row):
                row["storage"] = "sheet"
                has_sheet_mapping = True
            else:
                row.setdefault("storage", "custom")
                row.setdefault("custom_slot_id", slot_id)
            row["is_empty_slot"] = not bool(
                str(row.get("name", "") or "")
                or str(row.get("pl", "") or "")
                or str(row.get("count", "") or "")
            )
            normalized_rows.append(row)

        custom_rows = self.get_inventory_custom_rows(slot_id)
        if not has_sheet_mapping:
            normalized_rows = custom_rows
        else:
            for row in custom_rows:
                if not isinstance(row, dict):
                    continue
                if str(row.get("name", "") or "") or str(row.get("pl", "") or "") or str(row.get("count", "") or ""):
                    normalized_rows.append(row)

        min_rows = max(0, int(min_rows or 0))
        next_custom_index = 0
        for row in custom_rows:
            if not isinstance(row, dict):
                continue
            try:
                next_custom_index = max(next_custom_index, int(row.get("custom_row_index", -1)) + 1)
            except Exception:
                continue
        while len(normalized_rows) < min_rows:
            normalized_rows.append(
                {
                    "name": "",
                    "pl": "",
                    "count": "",
                    "storage": "custom",
                    "custom_slot_id": slot_id,
                    "custom_row_index": next_custom_index,
                    "is_empty_slot": True,
                }
            )
            next_custom_index += 1
        return normalized_rows

    def build_inventory_slot_categories(self, sections):
        section_map = {}
        base_rows_map = {}
        dynamic_sections = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id", "") or "")
            section_map[section_id] = section
            base_rows_map[section_id] = []

        for section in sections:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id", "") or "")
            rows = section.get("rows", [])
            if not isinstance(rows, list):
                continue
            current_dynamic = None
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if self._is_inventory_subsection_header_row(row):
                    dynamic_title = str(row.get("name", "") or "").strip()
                    current_dynamic = {"title": dynamic_title.title(), "rows": []}
                    dynamic_sections.append(current_dynamic)
                    continue
                if current_dynamic is not None:
                    current_dynamic["rows"].append(row)
                    continue
                base_rows_map.setdefault(section_id, []).append(row)

        if len(dynamic_sections) > 2:
            print("[INVENTORY WARNING] more dynamic sections found than slots")
        dynamic_sections = dynamic_sections[:2]

        slots = [
            {
                "id": "inventory_01",
                "default_label": "Inventar 01",
                "header_title": "Inventar",
                "rows": list(base_rows_map.get("inventory_left", [])),
            },
            {
                "id": "inventory_02",
                "default_label": "Inventar 02",
                "header_title": "Inventar",
                "rows": list(base_rows_map.get("inventory_middle", [])),
            },
            {
                "id": "inventory_03",
                "default_label": "Inventar 03",
                "header_title": "Bücher",
                "rows": list(base_rows_map.get("books", [])),
            },
            {
                "id": "inventory_04",
                "default_label": "Inventar 04",
                "header_title": dynamic_sections[0]["title"] if len(dynamic_sections) > 0 else "Inventar",
                "rows": list(dynamic_sections[0]["rows"]) if len(dynamic_sections) > 0 else [],
            },
            {
                "id": "inventory_05",
                "default_label": "Inventar 05",
                "header_title": dynamic_sections[1]["title"] if len(dynamic_sections) > 1 else "Inventar",
                "rows": list(dynamic_sections[1]["rows"]) if len(dynamic_sections) > 1 else [],
            },
        ]

        for slot in slots:
            slot["title"] = self.get_inventory_tab_label(slot["id"], slot["default_label"])
        return slots

    def _normalize_equipment_text(self, value):
        text = str(value or "").strip().lower()
        if not text:
            return ""
        replacements = {
            "ä": "ae",
            "ö": "oe",
            "ü": "ue",
            "ß": "ss",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = text.replace("-", " ").replace("/", " ").replace("_", " ")
        text = re.sub(r"[^a-z0-9 ]+", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _equipment_cache_text(self, sheet_cache, cell_ref):
        cell_data = sheet_cache.get(cell_ref)
        value = cell_data.get("value") if isinstance(cell_data, dict) else cell_data
        if value is None:
            return ""
        return str(value).strip()

    def _equipment_cell_sort_key(self, cell_ref):
        match = re.match(r"^([A-Z]+)(\d+)$", str(cell_ref).strip().upper())
        if not match:
            return (0, 0)
        return (int(match.group(2)), self._col_letters_to_index(match.group(1)))

    def get_equipment_sheet_cache(self):
        exact_candidates = {"ausrüstung", "ausruestung"}
        cache = self.loader.cell_cache
        if not isinstance(cache, dict):
            print("[EQUIPMENT ERROR] sheet not found")
            return "", {}

        for sheet_name, sheet_cache in cache.items():
            normalized = self._normalize_equipment_text(sheet_name)
            if normalized in exact_candidates and isinstance(sheet_cache, dict):
                print(f"[EQUIPMENT] sheet found: {sheet_name} cells={len(sheet_cache)}")
                return sheet_name, sheet_cache

        for sheet_name, sheet_cache in cache.items():
            normalized = self._normalize_equipment_text(sheet_name)
            if "ausruestung" in normalized and isinstance(sheet_cache, dict):
                print(f"[EQUIPMENT] sheet found: {sheet_name} cells={len(sheet_cache)}")
                return sheet_name, sheet_cache

        print("[EQUIPMENT ERROR] sheet not found")
        return "", {}

    def _find_equipment_column(
        self,
        header_entries,
        header_rows,
        include_tokens,
        exclude_tokens=None,
        min_col=1,
    ):
        if exclude_tokens is None:
            exclude_tokens = []
        candidates = []
        for entry in header_entries:
            row = entry.get("row", 0)
            col = entry.get("col", 0)
            norm = entry.get("norm", "")
            if row not in header_rows or col < min_col:
                continue
            if not all(token in norm for token in include_tokens):
                continue
            if any(token in norm for token in exclude_tokens):
                continue
            score = len(norm)
            candidates.append((score, row, col))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return candidates[0][2]

    def _extract_equipment_rows(self, sheet_cache, mapping, kind, max_rows=30):
        if not isinstance(mapping, dict):
            return []
        data_start_row = int(mapping.get("data_start_row", 0) or 0)
        if data_start_row <= 0:
            return []
        columns = mapping.get("columns", {})
        if not isinstance(columns, dict):
            columns = {}
        rows = []
        empty_streak = 0
        for offset in range(max_rows):
            row_index = data_start_row + offset
            row_data = {"row": row_index}
            non_empty = False
            for key, col_letters in columns.items():
                if not isinstance(col_letters, str) or not col_letters:
                    row_data[key] = ""
                    continue
                cell_ref = f"{col_letters}{row_index}"
                value = self._equipment_cache_text(sheet_cache, cell_ref)
                row_data[key] = value
                if value:
                    non_empty = True

            if kind == "armor":
                is_data = self._is_valid_armor_data_core(
                    row_data.get("slot", ""),
                    row_data.get("name", ""),
                    row_data.get("pl", ""),
                )
            else:
                is_data = self._is_valid_weapon_data_core(
                    row_data.get("name", ""),
                    row_data.get("weapon_type", ""),
                    row_data.get("pl", ""),
                    row_data.get("physical_dice", ""),
                    row_data.get("attributes", ""),
                )

            if is_data:
                rows.append(row_data)
                empty_streak = 0
            else:
                empty_streak = empty_streak + 1 if not non_empty else 0
                if empty_streak >= 6:
                    break
        return rows

    def _find_equipment_first_data_row(self, sheet_cache, start_row, key_columns):
        if not isinstance(sheet_cache, dict):
            return start_row + 3
        normalized_cols = [str(col).strip().upper() for col in key_columns if isinstance(col, str) and col]
        for row_index in range(start_row + 1, start_row + 30):
            row_values = [
                self._equipment_cache_text(sheet_cache, f"{col_letters}{row_index}")
                for col_letters in normalized_cols
            ]
            if self._is_valid_armor_data_core(
                row_values[0] if len(row_values) > 0 else "",
                row_values[1] if len(row_values) > 1 else "",
                row_values[2] if len(row_values) > 2 else "",
            ):
                return row_index
        return start_row + 3

    def _is_equipment_header_value(self, value):
        normalized = self._normalize_equipment_text(value)
        if not normalized:
            return False
        known_headers = {
            "wo getragen",
            "name",
            "pl",
            "kopf",
            "brust",
            "arme",
            "beine",
            "feuer",
            "wasser",
            "erde",
            "wind",
            "blitz",
            "eis",
            "saeure",
            "licht",
            "dunkel",
            "haltbarkeit",
            "attribute sonderfertigkeiten",
            "ruestung",
            "physische resistenzen",
            "elementare resistenzen",
            "summe",
        }
        return normalized in known_headers

    def _is_valid_armor_data_core(self, slot_value, name_value, pl_value):
        slot_text = str(slot_value or "").strip()
        name_text = str(name_value or "").strip()
        pl_text = str(pl_value or "").strip()
        if name_text and self._normalize_equipment_text(name_text) != "name":
            if not self._is_equipment_header_value(name_text):
                return True
        if slot_text and self._normalize_equipment_text(slot_text) != "wo getragen":
            if not self._is_equipment_header_value(slot_text):
                return True
        if pl_text and self._normalize_equipment_text(pl_text) != "pl":
            if not self._is_equipment_header_value(pl_text):
                return True
        return False

    def _is_valid_weapon_data_core(
        self, name_value, weapon_type_value, pl_value, physical_dice_value="", attributes_value=""
    ):
        header_values = {
            "name",
            "waffentyp",
            "pl",
            "schnitt",
            "stoss",
            "stich",
            "wuerfel",
            "bonus",
            "elemente",
            "haltbarkeit",
            "attribute sonderfertigkeiten",
            "waffe",
            "schadensart",
            "physisch",
            "elementar",
        }
        for value in (
            name_value,
            weapon_type_value,
            pl_value,
            physical_dice_value,
            attributes_value,
        ):
            text = str(value or "").strip()
            normalized = self._normalize_equipment_text(text)
            if text and normalized and normalized not in header_values:
                return True
        return False

    def _find_armor_header_columns(self, header_entries, anchor_row):
        header_rows = [anchor_row + i for i in range(0, 8)]
        slot_col = self._find_equipment_column(header_entries, header_rows, ["wo", "getragen"])
        name_col = self._find_equipment_column(
            header_entries, header_rows, ["name"], exclude_tokens=["waffe", "waffentyp"]
        )
        pl_col = self._find_equipment_column(header_entries, header_rows, ["pl"])
        if slot_col is None or name_col is None or pl_col is None:
            return None
        return {"slot_col": slot_col, "name_col": name_col, "pl_col": pl_col}

    def _find_equipment_slash_column(self, sheet_cache, base_col, data_start_row):
        if not isinstance(sheet_cache, dict) or base_col <= 0:
            return None
        counts = {}
        for row_index in range(data_start_row, data_start_row + 30):
            for col in range(base_col + 1, base_col + 5):
                value = self._equipment_cache_text(
                    sheet_cache, f"{self._col_index_to_letters(col)}{row_index}"
                )
                if value == "/":
                    counts[col] = counts.get(col, 0) + 1
        if not counts:
            return None
        return max(counts.items(), key=lambda item: item[1])[0]

    def _build_armor_mapping(self, header_entries, anchor_row, sheet_cache):
        if anchor_row <= 0:
            return {}
        header_cols = self._find_armor_header_columns(header_entries, anchor_row)
        if not isinstance(header_cols, dict):
            return {}

        slot_col = int(header_cols["slot_col"])
        name_col = int(header_cols["name_col"])
        pl_col = int(header_cols["pl_col"])
        header_row = 0
        for entry in header_entries:
            if int(entry.get("col", 0)) == slot_col and "wo getragen" == entry.get("norm", ""):
                header_row = int(entry.get("row", 0))
                break
        if header_row <= 0:
            header_row = anchor_row + 2
        header_rows = [header_row]

        phys_head_col = pl_col + 2
        phys_chest_col = pl_col + 4
        phys_arms_col = pl_col + 6
        phys_legs_col = pl_col + 8
        fire_col = pl_col + 10
        water_col = pl_col + 12
        earth_col = pl_col + 14
        wind_col = pl_col + 16
        lightning_col = pl_col + 18
        ice_col = pl_col + 20
        acid_col = pl_col + 22
        light_col = pl_col + 24
        dark_col = pl_col + 26
        durability_current_col = pl_col + 28
        slash_col = pl_col + 30
        durability_max_col = pl_col + 31
        attributes_col = pl_col + 35

        slot_letters = self._col_index_to_letters(slot_col)
        name_letters = self._col_index_to_letters(name_col)
        pl_letters = self._col_index_to_letters(pl_col)
        data_start_row = self._find_equipment_first_data_row(
            sheet_cache,
            header_row,
            [slot_letters, name_letters, pl_letters],
        )

        mapping = {
            "start_row": header_row,
            "header_rows": header_rows,
            "data_start_row": data_start_row,
            "columns": {
                "slot": slot_letters,
                "name": name_letters,
                "pl": pl_letters,
                "phys_head": self._col_index_to_letters(phys_head_col),
                "phys_chest": self._col_index_to_letters(phys_chest_col),
                "phys_arms": self._col_index_to_letters(phys_arms_col),
                "phys_legs": self._col_index_to_letters(phys_legs_col),
                "fire": self._col_index_to_letters(fire_col),
                "water": self._col_index_to_letters(water_col),
                "earth": self._col_index_to_letters(earth_col),
                "wind": self._col_index_to_letters(wind_col),
                "lightning": self._col_index_to_letters(lightning_col),
                "ice": self._col_index_to_letters(ice_col),
                "acid": self._col_index_to_letters(acid_col),
                "light": self._col_index_to_letters(light_col),
                "dark": self._col_index_to_letters(dark_col),
                "durability_current": self._col_index_to_letters(durability_current_col),
                "durability_max": self._col_index_to_letters(durability_max_col),
                "attributes": self._col_index_to_letters(attributes_col),
            },
        }
        slash_value = self._equipment_cache_text(
            sheet_cache,
            f"{self._col_index_to_letters(slash_col)}{data_start_row}",
        )
        print(
            f"[EQUIPMENT ARMOR COLUMN CHECK] durability_slash="
            f"{self._col_index_to_letters(slash_col)}{data_start_row} sample={slash_value}"
        )
        return mapping

    def _build_weapon_mapping(self, header_entries, anchor_row):
        if anchor_row <= 0:
            return {}
        header_rows = [anchor_row + i for i in range(0, 5)]
        name_col = self._find_equipment_column(
            header_entries, header_rows, ["name"], exclude_tokens=["wo", "getragen"]
        )
        weapon_type_col = self._find_equipment_column(
            header_entries, header_rows, ["waffentyp"]
        )
        pl_col = self._find_equipment_column(header_entries, header_rows, ["pl"])
        if name_col is None or pl_col is None:
            return {}

        header_row = 0
        for entry in header_entries:
            if int(entry.get("col", 0)) == name_col and entry.get("norm", "") == "name":
                header_row = int(entry.get("row", 0))
                break
        if header_row <= 0:
            header_row = anchor_row + 2

        if weapon_type_col is None:
            weapon_type_col = name_col + 4

        damage_cut_col = pl_col + 2
        damage_blunt_col = pl_col + 4
        damage_pierce_col = pl_col + 6
        physical_dice_col = pl_col + 9
        physical_bonus_col = pl_col + 13
        elemental_dice_col = pl_col + 16
        elemental_elements_col = pl_col + 20
        elemental_bonus_col = pl_col + 24
        durability_current_col = pl_col + 27
        slash_col = pl_col + 29
        durability_max_col = pl_col + 30
        attributes_col = pl_col + 32
        data_start_row = header_row + 2

        mapping = {
            "start_row": header_row,
            "header_rows": [header_row],
            "data_start_row": data_start_row,
            "columns": {
                "name": self._col_index_to_letters(name_col),
                "weapon_type": self._col_index_to_letters(weapon_type_col),
                "pl": self._col_index_to_letters(pl_col),
                "damage_cut": self._col_index_to_letters(damage_cut_col),
                "damage_blunt": self._col_index_to_letters(damage_blunt_col),
                "damage_pierce": self._col_index_to_letters(damage_pierce_col),
                "physical_dice": self._col_index_to_letters(physical_dice_col),
                "physical_bonus": self._col_index_to_letters(physical_bonus_col),
                "elemental_dice": self._col_index_to_letters(elemental_dice_col),
                "elemental_elements": self._col_index_to_letters(elemental_elements_col),
                "elemental_bonus": self._col_index_to_letters(elemental_bonus_col),
                "durability_current": self._col_index_to_letters(durability_current_col),
                "durability_max": self._col_index_to_letters(durability_max_col),
                "attributes": self._col_index_to_letters(attributes_col),
            },
        }
        print(
            f"[EQUIPMENT WEAPON COLUMN CHECK] durability_current="
            f"{self._col_index_to_letters(durability_current_col)}{data_start_row} "
            f"slash={self._col_index_to_letters(slash_col)}{data_start_row} "
            f"durability_max={self._col_index_to_letters(durability_max_col)}{data_start_row}"
        )
        return mapping

    def analyze_equipment_sheet(self):
        sheet_name, sheet_cache = self.get_equipment_sheet_cache()
        if not sheet_name or not isinstance(sheet_cache, dict) or not sheet_cache:
            self.equipment_analysis = {"sheet": "", "armor": {"mapping": {}, "rows": []}, "weapons": {"mapping": {}, "rows": []}}
            return self.equipment_analysis

        entries = []
        for cell_ref, cell_data in sheet_cache.items():
            text = self._equipment_cache_text(sheet_cache, cell_ref)
            if not text:
                continue
            row, col = self._equipment_cell_sort_key(cell_ref)
            if row <= 0 or col <= 0:
                continue
            entries.append(
                {
                    "cell": str(cell_ref).upper(),
                    "row": row,
                    "col": col,
                    "text": text,
                    "norm": self._normalize_equipment_text(text),
                }
            )

        entries.sort(key=lambda item: (item["row"], item["col"]))
        target_headers = {
            "ruestung",
            "waffe",
            "wo getragen",
            "name",
            "pl",
            "physische resistenzen",
            "elementare resistenzen",
            "haltbarkeit",
            "attribute sonderfertigkeiten",
            "waffentyp",
            "schadensart",
            "physisch",
            "elementar",
        }
        for entry in entries:
            if entry["norm"] in target_headers:
                print(f'[EQUIPMENT HEADER] text="{entry["text"]}" cell={entry["cell"]}')

        armor_anchor = 0
        weapon_anchor = 0
        for entry in entries:
            if entry["norm"] == "ruestung" and armor_anchor == 0:
                armor_anchor = entry["row"]
            if entry["norm"] == "waffe" and weapon_anchor == 0:
                weapon_anchor = entry["row"]
        if armor_anchor > 0:
            print(f"[EQUIPMENT TABLE] armor start_row={armor_anchor}")
        else:
            print("[EQUIPMENT TABLE] armor not found")
        if weapon_anchor > 0:
            print(f"[EQUIPMENT TABLE] weapon start_row={weapon_anchor}")
        else:
            print("[EQUIPMENT TABLE] weapon not found")

        armor_mapping = self._build_armor_mapping(entries, armor_anchor, sheet_cache)
        weapon_mapping = self._build_weapon_mapping(entries, weapon_anchor)

        if armor_mapping:
            print(
                f"[EQUIPMENT ARMOR MAP] start_row={armor_mapping['start_row']} "
                f"data_start_row={armor_mapping['data_start_row']}"
            )
            for key, col_letters in armor_mapping.get("columns", {}).items():
                if col_letters:
                    print(f"[EQUIPMENT ARMOR COLUMN] {key}={col_letters}")
            sample_row = int(armor_mapping.get("data_start_row", 0) or 0)
            if sample_row > 0:
                for check_key in ("phys_chest", "durability_current", "durability_max"):
                    col_letters = str(armor_mapping.get("columns", {}).get(check_key, "") or "")
                    if not col_letters:
                        continue
                    sample_value = self._equipment_cache_text(sheet_cache, f"{col_letters}{sample_row}")
                    print(
                        f"[EQUIPMENT ARMOR COLUMN CHECK] {check_key}="
                        f"{col_letters}{sample_row} sample={sample_value}"
                    )
        if weapon_mapping:
            print(
                f"[EQUIPMENT WEAPON MAP] start_row={weapon_mapping['start_row']} "
                f"data_start_row={weapon_mapping['data_start_row']}"
            )
            for key, col_letters in weapon_mapping.get("columns", {}).items():
                if col_letters:
                    print(f"[EQUIPMENT WEAPON COLUMN] {key}={col_letters}")

        armor_rows = self._extract_equipment_rows(sheet_cache, armor_mapping, "armor")
        weapon_rows = self._extract_equipment_rows(sheet_cache, weapon_mapping, "weapon")

        if armor_mapping:
            data_start_row = int(armor_mapping.get("data_start_row", 0) or 0)
            debug_fields = [
                ("slot", "slot"),
                ("name", "name"),
                ("pl", "pl"),
                ("phys_chest", "phys_chest"),
                ("phys_arms", "phys_arms"),
                ("phys_legs", "phys_legs"),
                ("durability_current", "durability_current"),
                ("durability_max", "durability_max"),
            ]
            for row_index in range(data_start_row, data_start_row + 3):
                for field_key, label in debug_fields:
                    col_letters = str(armor_mapping.get("columns", {}).get(field_key, "") or "")
                    if not col_letters:
                        continue
                    cell_ref = f"{col_letters}{row_index}"
                    value = self._equipment_cache_text(sheet_cache, cell_ref)
                    print(
                        f"[EQUIPMENT ARMOR DEBUG CELL] row={row_index} field={label} "
                        f"cell={cell_ref} value={value}"
                    )

        expected_found = False
        for row_data in armor_rows:
            name_norm = self._normalize_equipment_text(row_data.get("name", ""))
            slot_norm = self._normalize_equipment_text(row_data.get("slot", ""))
            if name_norm == "leder ruestung" and slot_norm == "brust arme beine":
                expected_found = True
                break
        if not expected_found and armor_rows:
            print("[EQUIPMENT ARMOR ERROR] expected armor row not found")
        elif not armor_rows:
            print("[EQUIPMENT ARMOR ERROR] expected armor row not found")

        for row_data in armor_rows:
            print(
                f'[EQUIPMENT ARMOR ROW] row={row_data["row"]} '
                f'slot="{row_data.get("slot", "")}" name="{row_data.get("name", "")}" '
                f'pl="{row_data.get("pl", "")}"'
            )
        for row_data in weapon_rows:
            durability_summary = ""
            current_value = str(row_data.get("durability_current", "") or "").strip()
            max_value = str(row_data.get("durability_max", "") or "").strip()
            if current_value or max_value:
                durability_summary = f"{current_value}/{max_value}".strip("/")
            print(
                f'[EQUIPMENT WEAPON ROW] row={row_data["row"]} '
                f'name="{row_data.get("name", "")}" type="{row_data.get("weapon_type", "")}" '
                f'pl="{row_data.get("pl", "")}" phys_dice="{row_data.get("physical_dice", "")}" '
                f'phys_bonus="{row_data.get("physical_bonus", "")}" durability="{durability_summary}"'
            )
        if not weapon_rows:
            print("[EQUIPMENT WEAPON] no rows found")

        self.equipment_analysis = {
            "sheet": sheet_name,
            "armor": {
                "mapping": armor_mapping,
                "rows": armor_rows,
            },
            "weapons": {
                "mapping": weapon_mapping,
                "rows": weapon_rows,
            },
        }
        return self.equipment_analysis

    def render_equipment_armor_table(self, parent, armor_cfg, armor_rows):
        if not isinstance(armor_cfg, dict) or not armor_cfg.get("enabled", True):
            return

        table_x = self._safe_int(armor_cfg.get("x", 20), 20)
        table_y = self._safe_int(armor_cfg.get("y", 70), 70)
        table_w = self._safe_int(armor_cfg.get("w", 1380), 1380)
        table_h = self._safe_int(armor_cfg.get("h", 330), 330)
        title_text = str(armor_cfg.get("title", "Rüstung"))
        title_font_size = self._safe_int(armor_cfg.get("title_font_size", 20), 20)
        title_color = str(armor_cfg.get("title_color", "#f2d28b"))
        font_size = self._safe_int(armor_cfg.get("font_size", 14), 14)
        header_font_size = self._safe_int(armor_cfg.get("header_font_size", 14), 14)
        header_color = str(armor_cfg.get("header_color", "#f2d28b"))
        text_color = str(armor_cfg.get("text_color", "#ffffff"))
        value_color = str(armor_cfg.get("value_color", "#7fd0ff"))
        border_color = str(armor_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
        background = str(armor_cfg.get("background", "rgba(5, 5, 5, 95)"))
        min_row_h = self._safe_int(armor_cfg.get("min_row_h", 32), 32)
        max_row_h = self._safe_int(armor_cfg.get("max_row_h", 120), 120)
        min_rows = self._safe_int(armor_cfg.get("min_rows", 10), 10)

        panel = QFrame(parent)
        panel.setGeometry(table_x, table_y, table_w, table_h)
        panel.setStyleSheet(
            f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
        )
        panel.show()

        self.create_panel_text(
            panel,
            {"x": 10, "y": 8, "w": table_w - 20, "h": 28},
            title_text,
            title_font_size,
            title_color,
            bold=True,
            align="left",
        )

        columns_cfg = armor_cfg.get("columns", {})
        if not isinstance(columns_cfg, dict):
            columns_cfg = {}

        column_order = [
            ("slot", "Wo getragen"),
            ("name", "Name"),
            ("pl", "PL"),
            ("phys_head", "Kopf"),
            ("phys_chest", "Brust"),
            ("phys_arms", "Arme"),
            ("phys_legs", "Beine"),
            ("fire", "Feuer"),
            ("water", "Wasser"),
            ("earth", "Erde"),
            ("wind", "Wind"),
            ("lightning", "Blitz"),
            ("ice", "Eis"),
            ("acid", "Säure"),
            ("light", "Licht"),
            ("dark", "Dunkel"),
            ("durability_current", "Haltb."),
            ("durability_max", "Max"),
            ("attributes", "Attribute / Sonderfertigkeiten"),
        ]

        table = QTableWidget(panel)
        table.setGeometry(10, 42, table_w - 20, table_h - 52)
        table.setColumnCount(len(column_order))
        table_row_count = max(len(armor_rows), min_rows)
        table.setRowCount(table_row_count)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(True)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)

        field_to_col_index = {}
        header_labels = []
        for col_index, (field_key, fallback_title) in enumerate(column_order):
            field_to_col_index[field_key] = col_index
            col_cfg = columns_cfg.get(field_key, {})
            if not isinstance(col_cfg, dict):
                col_cfg = {}
            header_title = str(col_cfg.get("title", fallback_title))
            col_width = self._safe_int(col_cfg.get("w", 70), 70)
            header_labels.append(header_title)
            table.setColumnWidth(col_index, col_width)
        table.setHorizontalHeaderLabels(header_labels)

        table.setStyleSheet(
            "QTableWidget {"
            f"background: {background};"
            f"color: {text_color};"
            f"gridline-color: {border_color};"
            "border: none;"
            f"font-size: {font_size}px;"
            "}"
            "QHeaderView::section {"
            "background: rgba(0,0,0,0);"
            f"color: {header_color};"
            f"font-size: {header_font_size}px; font-weight: 700;"
            f"border: 1px solid {border_color};"
            "padding: 4px;"
            "}"
            "QTableWidget::item { padding: 4px; }"
        )

        group_styles = {}
        column_groups = armor_cfg.get("column_groups", {})
        if not isinstance(column_groups, dict):
            column_groups = {}
        for group_cfg in column_groups.values():
            if not isinstance(group_cfg, dict):
                continue
            group_columns = group_cfg.get("columns", [])
            if not isinstance(group_columns, list):
                group_columns = []
            for field_key in group_columns:
                field_name = str(field_key or "").strip()
                if field_name:
                    group_styles[field_name] = group_cfg

        element_header_colors = armor_cfg.get("element_header_colors", {})
        if not isinstance(element_header_colors, dict):
            element_header_colors = {}
        column_backgrounds = armor_cfg.get("column_backgrounds", {})
        if not isinstance(column_backgrounds, dict):
            column_backgrounds = {}
        header_backgrounds = armor_cfg.get("header_backgrounds", {})
        if not isinstance(header_backgrounds, dict):
            header_backgrounds = {}
        cell_text_colors = armor_cfg.get("cell_text_colors", {})
        if not isinstance(cell_text_colors, dict):
            cell_text_colors = {}

        value_fields = {
            "pl",
            "phys_head",
            "phys_chest",
            "phys_arms",
            "phys_legs",
            "fire",
            "water",
            "earth",
            "wind",
            "lightning",
            "ice",
            "acid",
            "light",
            "dark",
            "durability_current",
            "durability_max",
        }
        center_fields = value_fields

        column_background_brushes = {}
        header_background_brushes = {}
        for field_key, _ in column_order:
            col_bg_raw = column_backgrounds.get(field_key, "")
            if not col_bg_raw:
                group_cfg = group_styles.get(field_key, {})
                if isinstance(group_cfg, dict):
                    col_bg_raw = group_cfg.get("background", "")
            col_color, col_ok = self.parse_layout_color(col_bg_raw, "rgba(0,0,0,0)")
            column_background_brushes[field_key] = QBrush(col_color)

            header_bg_raw = header_backgrounds.get(field_key, "")
            if not header_bg_raw:
                group_cfg = group_styles.get(field_key, {})
                if isinstance(group_cfg, dict):
                    header_bg_raw = group_cfg.get("background", "")
            header_color_parsed, header_ok = self.parse_layout_color(header_bg_raw, "rgba(0,0,0,0)")
            header_background_brushes[field_key] = QBrush(header_color_parsed)

            print(
                f"[EQUIPMENT ARMOR STYLE TEST] column={field_key} "
                f"cell_bg={col_bg_raw} header_bg={header_bg_raw}"
            )
            if field_key == "durability_current":
                title_text_current = header_labels[field_to_col_index[field_key]]
                print(f"[EQUIPMENT ARMOR STYLE TEST] column=durability_current title={title_text_current}")
            if not col_ok:
                print(
                    f"[EQUIPMENT ARMOR STYLE ERROR] column={field_key} value={col_bg_raw} parsed=False"
                )
            if not header_ok:
                print(
                    f"[EQUIPMENT ARMOR STYLE ERROR] column={field_key} value={header_bg_raw} parsed=False"
                )

        for field_key, _ in column_order:
            col_index = field_to_col_index.get(field_key)
            if col_index is None:
                continue
            header_item = table.horizontalHeaderItem(col_index)
            if header_item is None:
                continue
            header_item.setToolTip(header_item.text())
            header_item.setBackground(header_background_brushes.get(field_key, QBrush()))
            header_item.setForeground(QBrush(QColor("#f2d28b")))

        for field_key, color_value in element_header_colors.items():
            col_index = field_to_col_index.get(str(field_key or "").strip())
            if col_index is None:
                continue
            header_item = table.horizontalHeaderItem(col_index)
            if header_item is None:
                continue
            element_color = QColor(str(color_value))
            if element_color.isValid():
                header_item.setForeground(QBrush(element_color))

        for row_index in range(table_row_count):
            row_data = armor_rows[row_index] if row_index < len(armor_rows) and isinstance(armor_rows[row_index], dict) else {}
            row_has_data = any(str(row_data.get(key, "") or "").strip() for key, _ in column_order)
            for col_index, (field_key, _) in enumerate(column_order):
                raw_value = str(row_data.get(field_key, "") or "").strip()
                display_value = raw_value if raw_value else ""
                item = QTableWidgetItem(display_value)
                if field_key in center_fields:
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                custom_text_color = str(cell_text_colors.get(field_key, "") or "").strip()
                if custom_text_color:
                    item.setForeground(QBrush(QColor(custom_text_color)))
                elif raw_value and field_key in value_fields:
                    item.setForeground(QColor(value_color))
                else:
                    item.setForeground(QColor(text_color))
                item.setBackground(column_background_brushes.get(field_key, QBrush()))
                if raw_value:
                    item.setToolTip(raw_value)
                elif not row_has_data:
                    item.setToolTip("")
                table.setItem(row_index, col_index, item)
            table.setRowHeight(row_index, min_row_h)

        table.resizeRowsToContents()
        for row_index in range(table_row_count):
            current_h = table.rowHeight(row_index)
            if current_h < min_row_h:
                table.setRowHeight(row_index, min_row_h)
            elif current_h > max_row_h:
                table.setRowHeight(row_index, max_row_h)

        table.show()

    def render_equipment_weapons_table(self, parent, weapons_cfg, weapon_rows):
        if not isinstance(weapons_cfg, dict) or not weapons_cfg.get("enabled", True):
            return

        table_x = self._safe_int(weapons_cfg.get("x", 20), 20)
        table_y = self._safe_int(weapons_cfg.get("y", 470), 470)
        table_w = self._safe_int(weapons_cfg.get("w", 1380), 1380)
        table_h = self._safe_int(weapons_cfg.get("h", 300), 300)
        title_text = str(weapons_cfg.get("title", "Waffen"))
        title_font_size = self._safe_int(weapons_cfg.get("title_font_size", 20), 20)
        title_color = str(weapons_cfg.get("title_color", "#f2d28b"))
        font_size = self._safe_int(weapons_cfg.get("font_size", 14), 14)
        header_font_size = self._safe_int(weapons_cfg.get("header_font_size", 14), 14)
        header_color = str(weapons_cfg.get("header_color", "#f2d28b"))
        text_color = str(weapons_cfg.get("text_color", "#ffffff"))
        value_color = str(weapons_cfg.get("value_color", "#7fd0ff"))
        border_color = str(weapons_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
        background = str(weapons_cfg.get("background", "rgba(5, 5, 5, 95)"))
        min_row_h = self._safe_int(weapons_cfg.get("min_row_h", 32), 32)
        max_row_h = self._safe_int(weapons_cfg.get("max_row_h", 72), 72)
        min_rows = self._safe_int(weapons_cfg.get("min_rows", 8), 8)

        panel = QFrame(parent)
        panel.setGeometry(table_x, table_y, table_w, table_h)
        panel.setStyleSheet(
            f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
        )
        panel.show()

        self.create_panel_text(
            panel,
            {"x": 10, "y": 8, "w": table_w - 20, "h": 28},
            title_text,
            title_font_size,
            title_color,
            bold=True,
            align="left",
        )

        columns_cfg = weapons_cfg.get("columns", {})
        if not isinstance(columns_cfg, dict):
            columns_cfg = {}

        column_order = [
            ("name", "Name"),
            ("weapon_type", "Waffentyp"),
            ("pl", "PL"),
            ("damage_cut", "Schnitt"),
            ("damage_blunt", "Stoß"),
            ("damage_pierce", "Stich"),
            ("physical_dice", "Phys. Würfel"),
            ("physical_bonus", "Phys. Bonus"),
            ("elemental_dice", "Elem. Würfel"),
            ("elemental_elements", "Element(e)"),
            ("elemental_bonus", "Elem. Bonus"),
            ("durability_current", "Haltb."),
            ("durability_max", "Max"),
            ("attributes", "Attribute / Sonderfertigkeiten"),
        ]

        table = QTableWidget(panel)
        table.setGeometry(10, 42, table_w - 20, table_h - 52)
        table.setColumnCount(len(column_order))
        table_row_count = max(len(weapon_rows), min_rows)
        table.setRowCount(table_row_count)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(True)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setAlternatingRowColors(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(False)

        field_to_col_index = {}
        header_labels = []
        for col_index, (field_key, fallback_title) in enumerate(column_order):
            field_to_col_index[field_key] = col_index
            col_cfg = columns_cfg.get(field_key, {})
            if not isinstance(col_cfg, dict):
                col_cfg = {}
            header_title = str(col_cfg.get("title", fallback_title))
            col_width = self._safe_int(col_cfg.get("w", 70), 70)
            header_labels.append(header_title)
            table.setColumnWidth(col_index, col_width)
        table.setHorizontalHeaderLabels(header_labels)

        table.setStyleSheet(
            "QTableWidget {"
            f"background: {background};"
            f"color: {text_color};"
            f"gridline-color: {border_color};"
            "border: none;"
            f"font-size: {font_size}px;"
            "}"
            "QHeaderView::section {"
            "background: rgba(0,0,0,0);"
            f"color: {header_color};"
            f"font-size: {header_font_size}px; font-weight: 700;"
            f"border: 1px solid {border_color};"
            "padding: 4px;"
            "}"
            "QTableWidget::item { padding: 4px; }"
        )

        column_backgrounds = weapons_cfg.get("column_backgrounds", {})
        if not isinstance(column_backgrounds, dict):
            column_backgrounds = {}
        header_backgrounds = weapons_cfg.get("header_backgrounds", {})
        if not isinstance(header_backgrounds, dict):
            header_backgrounds = {}
        cell_text_colors = weapons_cfg.get("cell_text_colors", {})
        if not isinstance(cell_text_colors, dict):
            cell_text_colors = {}

        value_fields = {
            "pl",
            "damage_cut",
            "damage_blunt",
            "damage_pierce",
            "physical_dice",
            "physical_bonus",
            "elemental_dice",
            "elemental_bonus",
            "durability_current",
            "durability_max",
        }
        center_fields = value_fields | {"weapon_type", "elemental_elements"}

        column_background_brushes = {}
        header_background_brushes = {}
        for field_key, _ in column_order:
            col_bg_raw = str(column_backgrounds.get(field_key, "") or "")
            col_color, _ = self.parse_layout_color(col_bg_raw, "rgba(0,0,0,0)")
            column_background_brushes[field_key] = QBrush(col_color)

            header_bg_raw = str(header_backgrounds.get(field_key, "") or col_bg_raw)
            header_color_parsed, _ = self.parse_layout_color(header_bg_raw, "rgba(0,0,0,0)")
            header_background_brushes[field_key] = QBrush(header_color_parsed)

        for field_key, _ in column_order:
            col_index = field_to_col_index.get(field_key)
            if col_index is None:
                continue
            header_item = table.horizontalHeaderItem(col_index)
            if header_item is None:
                continue
            header_item.setToolTip(header_item.text())
            header_item.setBackground(header_background_brushes.get(field_key, QBrush()))
            header_item.setForeground(QBrush(QColor("#f2d28b")))

        for row_index in range(table_row_count):
            row_data = (
                weapon_rows[row_index]
                if row_index < len(weapon_rows) and isinstance(weapon_rows[row_index], dict)
                else {}
            )
            for col_index, (field_key, _) in enumerate(column_order):
                raw_value = str(row_data.get(field_key, "") or "").strip()
                item = QTableWidgetItem(raw_value)
                if field_key in center_fields:
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                custom_text_color = str(cell_text_colors.get(field_key, "") or "").strip()
                if custom_text_color:
                    item.setForeground(QBrush(QColor(custom_text_color)))
                elif raw_value and field_key in value_fields:
                    item.setForeground(QColor(value_color))
                else:
                    item.setForeground(QColor(text_color))
                item.setBackground(column_background_brushes.get(field_key, QBrush()))
                if raw_value:
                    item.setToolTip(raw_value)
                table.setItem(row_index, col_index, item)
            table.setRowHeight(row_index, min_row_h)

        table.resizeRowsToContents()
        for row_index in range(table_row_count):
            current_h = table.rowHeight(row_index)
            if current_h < min_row_h:
                table.setRowHeight(row_index, min_row_h)
            elif current_h > max_row_h:
                table.setRowHeight(row_index, max_row_h)

        table.show()

    def render_equipment_screen(self):
        if self.content_layer is None:
            return

        layout_config = self.load_equipment_layout_config()
        screen_cfg = layout_config.get("equipment_screen", {})
        screen = QFrame(self.content_layer)
        screen.setGeometry(
            self._safe_int(screen_cfg.get("x", 20), 20),
            self._safe_int(screen_cfg.get("y", 20), 20),
            self._safe_int(screen_cfg.get("w", 1420), 1420),
            self._safe_int(screen_cfg.get("h", 820), 820),
        )
        screen.setStyleSheet("background: transparent;")
        screen.show()

        title_cfg = screen_cfg.get("title", {})
        self.create_panel_text(
            screen,
            title_cfg,
            str(title_cfg.get("text", "Ausrüstung")),
            self._safe_int(title_cfg.get("font_size", 24), 24),
            str(title_cfg.get("color", "#f2d28b")),
            bold=True,
            align=str(title_cfg.get("align", "center")),
        )
        self.create_panel_text(
            screen,
            {"x": 20, "y": 70, "w": 700, "h": 30},
            "Ausrüstung Analyse - siehe Terminal",
            16,
            "#e8e0c8",
            bold=False,
            align="left",
        )
        analysis = self.analyze_equipment_sheet()
        if not isinstance(analysis, dict):
            analysis = {}
        armor_block = analysis.get("armor", {}) if isinstance(analysis, dict) else {}
        armor_rows = armor_block.get("rows", []) if isinstance(armor_block, dict) else []
        if not isinstance(armor_rows, list):
            armor_rows = []
        weapons_block = analysis.get("weapons", {}) if isinstance(analysis, dict) else {}
        weapon_rows = weapons_block.get("rows", []) if isinstance(weapons_block, dict) else []
        if not isinstance(weapon_rows, list):
            weapon_rows = []

        try:
            self.render_equipment_armor_table(screen, screen_cfg.get("armor", {}), armor_rows)
        except Exception as exc:
            print(f"[EQUIPMENT ARMOR RENDER ERROR] {exc}")
            self.create_panel_text(
                screen,
                {"x": 20, "y": 150, "w": 760, "h": 32},
                "Rüstung konnte nicht gerendert werden - siehe Terminal",
                16,
                "#e8e0c8",
                bold=False,
                align="left",
            )

        if not armor_rows:
            self.create_panel_text(
                screen,
                {"x": 20, "y": 410, "w": 700, "h": 30},
                "Keine Rüstungsdaten gefunden",
                16,
                "#e8e0c8",
                bold=False,
                align="left",
            )
        try:
            self.render_equipment_weapons_table(screen, screen_cfg.get("weapons", {}), weapon_rows)
        except Exception as exc:
            print(f"[EQUIPMENT WEAPON RENDER ERROR] {exc}")
            self.create_panel_text(
                screen,
                {"x": 20, "y": 470, "w": 760, "h": 32},
                "Waffen konnten nicht gerendert werden - siehe Terminal",
                16,
                "#e8e0c8",
                bold=False,
                align="left",
            )

    def render_inventory_screen(self):
        if self.content_layer is None:
            return

        self._inventory_loading = True
        self._inventory_table_bindings = {}
        try:
            layout_config = self.load_inventory_layout_config()
            screen_cfg = layout_config.get("inventory_screen", {})
            inventory_data = self.get_inventory_display_data()
            inventory_categories = self.build_inventory_slot_categories(inventory_data.get("sections", []))
            available_ids = [str(cat.get("id", "")) for cat in inventory_categories if isinstance(cat, dict)]
            if self.current_inventory_category not in available_ids:
                self.current_inventory_category = "inventory_01"

            screen = QFrame(self.content_layer)
            screen.setGeometry(
                self._safe_int(screen_cfg.get("x", 20), 20),
                self._safe_int(screen_cfg.get("y", 20), 20),
                self._safe_int(screen_cfg.get("w", 1420), 1420),
                self._safe_int(screen_cfg.get("h", 820), 820),
            )
            screen.setStyleSheet("background: transparent;")
            screen.show()

            title_cfg = screen_cfg.get("title", {})
            self.create_panel_text(
                screen,
                title_cfg,
                str(title_cfg.get("text", "Inventar")),
                self._safe_int(title_cfg.get("font_size", 24), 24),
                str(title_cfg.get("color", "#f2d28b")),
                bold=True,
                align=str(title_cfg.get("align", "center")),
            )

            self.render_inventory_money_panel(screen, screen_cfg.get("money", {}), inventory_data["money"])
            self.render_inventory_category_tabs(screen, screen_cfg, inventory_categories)
            self.render_inventory_active_category_table(screen, screen_cfg, inventory_categories)
        finally:
            self._inventory_loading = False

    def on_inventory_category_clicked(self, category_id):
        self.current_inventory_category = str(category_id or "")
        self.show_main_section("inventory")

    def rename_inventory_category(self, slot_id):
        slot_id = str(slot_id or "").strip()
        if not slot_id:
            return
        default_labels = {
            "inventory_01": "Inventar 01",
            "inventory_02": "Inventar 02",
            "inventory_03": "Inventar 03",
            "inventory_04": "Inventar 04",
            "inventory_05": "Inventar 05",
        }
        current_label = self.get_inventory_tab_label(slot_id, default_labels.get(slot_id, slot_id))
        new_label, ok = QInputDialog.getText(
            self,
            "Inventar-Tab umbenennen",
            "Name:",
            text=current_label,
        )
        if not ok:
            return
        normalized_label = str(new_label).strip()
        if not normalized_label:
            normalized_label = default_labels.get(slot_id, current_label)
        if normalized_label == current_label:
            return
        try:
            self.loader.set_inventory_tab_label(slot_id, normalized_label)
            self.loader.save_active_character_json()
            print(f'[INVENTORY TAB RENAME] {slot_id} = "{normalized_label}"')
            self.show_main_section("inventory")
        except Exception as exc:
            print("[INVENTORY TAB RENAME ERROR]", str(exc))

    def render_inventory_category_tabs(self, parent, screen_cfg, categories):
        tabs_cfg = screen_cfg.get("category_tabs", {})
        if not isinstance(tabs_cfg, dict):
            tabs_cfg = {}
        tabs_container = QFrame(parent)
        tabs_container.setGeometry(
            self._safe_int(tabs_cfg.get("x", 20), 20),
            self._safe_int(tabs_cfg.get("y", 175), 175),
            self._safe_int(tabs_cfg.get("w", 1380), 1380),
            self._safe_int(tabs_cfg.get("h", 50), 50),
        )
        tabs_container.setStyleSheet("background: transparent;")
        tabs_container.show()

        button_w = self._safe_int(tabs_cfg.get("button_w", 220), 220)
        button_h = self._safe_int(tabs_cfg.get("button_h", 42), 42)
        button_gap = self._safe_int(tabs_cfg.get("gap", 18), 18)
        tab_font_size = self._safe_int(tabs_cfg.get("font_size", 20), 20)
        active_color = str(tabs_cfg.get("active_color", "#f2d28b"))
        inactive_color = str(tabs_cfg.get("inactive_color", "#9a8560"))
        hover_color = str(tabs_cfg.get("hover_color", "#ffffff"))
        use_asset_buttons = bool(tabs_cfg.get("use_asset_buttons", False))
        default_asset = str(tabs_cfg.get("asset", "buttons/menu_button_small.png") or "").strip()
        active_asset = str(tabs_cfg.get("active_asset", default_asset) or "").strip()
        inactive_asset = str(tabs_cfg.get("inactive_asset", default_asset) or "").strip()

        for index, category in enumerate(categories):
            if not isinstance(category, dict):
                continue
            category_id = str(category.get("id", "") or "")
            if not category_id:
                continue
            title = str(category.get("title", category_id))
            is_active = category_id == self.current_inventory_category
            button = QPushButton(tabs_container)
            button.setGeometry(index * (button_w + button_gap), 0, button_w, button_h)
            button.setText(title)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("inventory_category_id", category_id)
            button.installEventFilter(self)
            color = active_color if is_active else inactive_color
            border = "#b88a35" if is_active else "rgba(180, 140, 70, 90)"
            bg = "rgba(35, 24, 12, 185)" if is_active else "rgba(8, 8, 8, 125)"
            asset_for_state = active_asset if is_active else inactive_asset
            asset_path = self.resolve_ui_asset_path(asset_for_state) if asset_for_state else None
            has_asset = bool(use_asset_buttons and asset_path is not None and asset_path.exists())
            if has_asset:
                button.setStyleSheet(
                    "QPushButton {"
                    f"color: {color};"
                    f"font-size: {tab_font_size}px;"
                    "font-weight: 700;"
                    "padding: 0px;"
                    "border: none;"
                    f"border-image: url({asset_path.as_posix()}) 0 0 0 0 stretch stretch;"
                    "background: transparent;"
                    "}"
                    "QPushButton:hover {"
                    f"color: {hover_color};"
                    "}"
                )
            else:
                button.setStyleSheet(
                    "QPushButton {"
                    f"background-color: {bg};"
                    f"color: {color};"
                    f"border: 1px solid {border};"
                    "border-radius: 4px;"
                    f"font-size: {tab_font_size}px;"
                    "font-weight: 700;"
                    "padding: 0px;"
                    "}"
                    f"QPushButton:hover {{ border: 1px solid #f2d28b; color: {hover_color}; }}"
                )
            button.clicked.connect(
                lambda checked=False, cid=category_id: self.on_inventory_category_clicked(cid)
            )
            button.show()

    def render_inventory_active_category_table(self, parent, screen_cfg, categories):
        table_cfg = screen_cfg.get("table", {})
        if not isinstance(table_cfg, dict):
            table_cfg = {}
        active_category = None
        for category in categories:
            if isinstance(category, dict) and str(category.get("id", "")) == self.current_inventory_category:
                active_category = category
                break
        if active_category is None and categories:
            active_category = categories[0]
        if active_category is None:
            active_category = {"id": "inventory_left", "title": "Inventar 01", "header_title": "Inventar", "rows": []}
        self.render_inventory_single_table_widget(parent, table_cfg, active_category)

    def render_inventory_single_table_widget(self, parent, table_cfg, category):
        table_frame = QFrame(parent)
        table_frame.setGeometry(
            self._safe_int(table_cfg.get("x", 20), 20),
            self._safe_int(table_cfg.get("y", 235), 235),
            self._safe_int(table_cfg.get("w", 1380), 1380),
            self._safe_int(table_cfg.get("h", 560), 560),
        )
        border_color = str(table_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
        background = str(table_cfg.get("background", "rgba(5, 5, 5, 95)"))
        table_frame.setStyleSheet(
            f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
        )
        table_frame.show()

        columns = table_cfg.get("columns", {})
        if not isinstance(columns, dict):
            columns = {}
        name_col = columns.get("name", {})
        pl_col = columns.get("pl", {})
        count_col = columns.get("count", {})
        if not isinstance(name_col, dict):
            name_col = {}
        if not isinstance(pl_col, dict):
            pl_col = {}
        if not isinstance(count_col, dict):
            count_col = {}

        header_title = str(category.get("title", "") or category.get("header_title", "Inventar"))
        table = QTableWidget(table_frame)
        table.setGeometry(6, 6, max(1, table_frame.width() - 12), max(1, table_frame.height() - 12))
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(
            [
                header_title,
                str(pl_col.get("title", "PL")),
                str(count_col.get("title", "Anzahl")),
            ]
        )
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setFocusPolicy(Qt.StrongFocus)
        table.setWordWrap(True)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)

        font_size = self._safe_int(table_cfg.get("font_size", 15), 15)
        header_font_size = self._safe_int(table_cfg.get("header_font_size", 18), 18)
        header_color = str(table_cfg.get("header_color", "#f2d28b"))
        text_color = str(table_cfg.get("text_color", "#ffffff"))
        value_color = str(table_cfg.get("value_color", "#7fd0ff"))
        table.setStyleSheet(
            "QTableWidget {"
            f"background: {background};"
            f"color: {text_color};"
            f"gridline-color: {border_color};"
            f"font-size: {font_size}px;"
            "border: none;"
            "selection-background-color: rgba(242, 210, 139, 30);"
            "selection-color: #ffffff;"
            "}"
            "QHeaderView::section {"
            "background: rgba(24, 16, 8, 175);"
            f"color: {header_color};"
            f"font-size: {header_font_size}px;"
            "font-weight: 700;"
            f"border: 1px solid {border_color};"
            "padding: 3px;"
            "}"
        )

        rows = category.get("rows", [])
        if not isinstance(rows, list):
            rows = []
        min_table_rows = self._safe_int(table_cfg.get("min_rows", 0), 0)
        rows = self.build_inventory_table_rows(category, min_table_rows)
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                row = {}
            is_empty_slot = bool(row.get("is_empty_slot"))
            display_values = [
                "" if is_empty_slot else (str(row.get("name", "")).strip() or "(ohne Name)"),
                "" if is_empty_slot else (str(row.get("pl", "")).strip() or "-"),
                "" if is_empty_slot else (str(row.get("count", "")).strip() or "-"),
            ]
            raw_values = [
                str(row.get("name", "") or ""),
                str(row.get("pl", "") or ""),
                str(row.get("count", "") or ""),
            ]
            for column_index, value in enumerate(display_values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, raw_values[column_index])
                item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                item.setBackground(QColor(0, 0, 0, 0))
                item.setForeground(QColor(value_color if column_index in (1, 2) else text_color))
                item.setTextAlignment(
                    Qt.AlignCenter if column_index in (1, 2) else Qt.AlignLeft | Qt.AlignVCenter
                )
                table.setItem(row_index, column_index, item)

        column_widths = [
            self._safe_int(name_col.get("w", 1140), 1140),
            self._safe_int(pl_col.get("w", 80), 80),
            self._safe_int(count_col.get("w", 120), 120),
        ]
        available_width = max(1, table.width() - 4)
        configured_width = sum(column_widths)
        if configured_width > available_width:
            overflow = configured_width - available_width
            column_widths[0] = max(120, column_widths[0] - overflow)
        for column_index, width in enumerate(column_widths):
            table.setColumnWidth(column_index, max(1, width))

        table.resizeRowsToContents()
        min_row_h = self._safe_int(table_cfg.get("min_row_h", 34), 34)
        max_row_h = self._safe_int(table_cfg.get("max_row_h", 90), 90)
        self._apply_inventory_row_heights(table, min_row_h, max_row_h)
        table.blockSignals(False)

        self._inventory_table_bindings[id(table)] = {
            "section_id": str(category.get("id", "")),
            "rows": rows,
            "min_row_h": min_row_h,
            "max_row_h": max_row_h,
        }
        table.cellChanged.connect(
            lambda row_index, column_index, widget=table: self.on_inventory_table_cell_changed(
                widget, row_index, column_index
            )
        )
        table.show()

    def render_inventory_money_panel(self, parent, money_cfg, money):
        self._inventory_money_fields = {}
        self._inventory_money_delta_fields = {}
        panel = QFrame(parent)
        panel.setGeometry(
            self._safe_int(money_cfg.get("x", 20), 20),
            self._safe_int(money_cfg.get("y", 60), 60),
            self._safe_int(money_cfg.get("w", 420), 420),
            self._safe_int(money_cfg.get("h", 110), 110),
        )
        panel.setStyleSheet(
            "background: rgba(5, 5, 5, 95);"
            "border: 1px solid rgba(242, 210, 139, 70);"
            "border-radius: 4px;"
        )
        panel.show()

        title_color = str(money_cfg.get("title_color", "#f2d28b"))
        label_color = str(money_cfg.get("label_color", "#f2d28b"))
        value_color = str(money_cfg.get("value_color", "#ffffff"))
        title_font = self._safe_int(money_cfg.get("font_size", 18), 18)
        label_font = self._safe_int(money_cfg.get("label_font_size", 14), 14)
        value_font = self._safe_int(money_cfg.get("value_font_size", 20), 20)

        self.create_panel_text(
            panel,
            {"x": 12, "y": 8, "w": max(1, panel.width() - 24), "h": 26},
            str(money_cfg.get("title", "Geldbeutel")),
            title_font,
            title_color,
            bold=True,
            align="left",
        )

        columns = money_cfg.get("columns", [])
        if not isinstance(columns, list) or not columns:
            columns = self.get_default_inventory_layout_config()["inventory_screen"]["money"]["columns"]
        money_cells = {
            "gulden": "B9",
            "schilling": "E9",
            "heller": "H9",
            "pfifferling": "K9",
        }
        column_w = max(1, (panel.width() - 24) // max(1, len(columns)))
        for index, column in enumerate(columns):
            if not isinstance(column, dict):
                continue
            x = 12 + index * column_w
            value_id = str(column.get("id", ""))
            self.create_panel_text(
                panel,
                {"x": x, "y": 44, "w": column_w - 8, "h": 22},
                str(column.get("label", value_id)),
                label_font,
                label_color,
                bold=True,
                align="center",
            )
            money_edit = QLineEdit(panel)
            money_edit.setGeometry(x, 68, max(1, column_w - 8), 30)
            money_edit.setAlignment(Qt.AlignCenter)
            money_edit.setStyleSheet(
                "QLineEdit {"
                "background: rgba(8, 8, 8, 165);"
                "border: 1px solid rgba(242, 210, 139, 70);"
                f"color: {value_color};"
                f"font-size: {value_font}px;"
                "font-weight: 700;"
                "padding: 0px 4px;"
                "}"
            )
            money_edit.setProperty("inventory_money_cell", money_cells.get(value_id, ""))
            money_edit.blockSignals(True)
            money_edit.setText(str(money.get(value_id, "")))
            money_edit.blockSignals(False)
            money_edit.editingFinished.connect(
                lambda field=money_edit: self.on_inventory_money_edit_finished(field)
            )
            self._inventory_money_fields[value_id] = money_edit
            money_edit.show()

        delta_row_cfg = money_cfg.get("delta_row", {})
        if not isinstance(delta_row_cfg, dict):
            delta_row_cfg = {}
        delta_buttons_cfg = money_cfg.get("delta_buttons", {})
        if not isinstance(delta_buttons_cfg, dict):
            delta_buttons_cfg = {}

        delta_label = str(delta_row_cfg.get("label", "Änderung"))
        label_x = self._safe_int(delta_row_cfg.get("label_x", 12), 12)
        label_y = self._safe_int(delta_row_cfg.get("label_y", 101), 101)
        label_w = self._safe_int(delta_row_cfg.get("label_w", 100), 100)
        label_h = self._safe_int(delta_row_cfg.get("label_h", 22), 22)
        field_y = self._safe_int(delta_row_cfg.get("field_y", 124), 124)
        field_h = self._safe_int(delta_row_cfg.get("field_h", 26), 26)
        field_gap = self._safe_int(delta_row_cfg.get("field_gap", 10), 10)
        reserve_button_space = bool(delta_row_cfg.get("reserve_button_space", False))

        self.create_panel_text(
            panel,
            {"x": label_x, "y": label_y, "w": label_w, "h": label_h},
            delta_label,
            label_font,
            label_color,
            bold=True,
            align="left",
        )

        button_w = self._safe_int(delta_row_cfg.get("buttons_w", delta_buttons_cfg.get("w", 32)), 32)
        button_h = self._safe_int(delta_row_cfg.get("buttons_h", delta_buttons_cfg.get("h", 28)), 28)
        button_gap = self._safe_int(delta_row_cfg.get("buttons_gap", delta_buttons_cfg.get("gap", 6)), 6)
        button_font_size = self._safe_int(delta_row_cfg.get("font_size", delta_buttons_cfg.get("font_size", 16)), 16)
        buttons_y = self._safe_int(delta_row_cfg.get("buttons_y", delta_buttons_cfg.get("y", field_y)), field_y)
        buttons_right_margin = self._safe_int(delta_row_cfg.get("buttons_right_margin", 12), 12)

        fields_left = label_x
        fields_right = panel.width() - 12
        if reserve_button_space:
            button_space = (button_w * 2) + button_gap + buttons_right_margin + 12
            fields_right = max(fields_left + 40, panel.width() - button_space)
        available_field_w = max(40, fields_right - fields_left)
        if len(columns) > 0:
            delta_column_w = max(20, available_field_w // len(columns))
        else:
            delta_column_w = available_field_w
        delta_field_w_cfg = delta_row_cfg.get("delta_field_w", None)
        delta_field_w = self._safe_int(delta_field_w_cfg, delta_column_w - field_gap) if delta_field_w_cfg is not None else (delta_column_w - field_gap)

        for index, column in enumerate(columns):
            if not isinstance(column, dict):
                continue
            x = fields_left + index * delta_column_w
            value_id = str(column.get("id", ""))
            delta_edit = QLineEdit(panel)
            delta_edit.setGeometry(x, field_y, max(1, delta_field_w), max(1, field_h))
            delta_edit.setAlignment(Qt.AlignCenter)
            delta_edit.setText("0")
            delta_edit.setStyleSheet(
                "QLineEdit {"
                "background: rgba(8, 8, 8, 165);"
                "border: 1px solid rgba(242, 210, 139, 70);"
                f"color: {value_color};"
                f"font-size: {value_font}px;"
                "font-weight: 700;"
                "padding: 0px 4px;"
                "}"
            )
            self._inventory_money_delta_fields[value_id] = delta_edit
            delta_edit.show()

        if "minus_x" in delta_buttons_cfg:
            minus_x = self._safe_int(delta_buttons_cfg.get("minus_x"), panel.width() - buttons_right_margin - ((button_w * 2) + button_gap))
        else:
            minus_x = panel.width() - buttons_right_margin - ((button_w * 2) + button_gap)
        if "plus_x" in delta_buttons_cfg:
            plus_x = self._safe_int(delta_buttons_cfg.get("plus_x"), minus_x + button_w + button_gap)
        else:
            plus_x = minus_x + button_w + button_gap
        minus_button = QPushButton("-", panel)
        plus_button = QPushButton("+", panel)
        minus_button.setGeometry(max(0, minus_x), max(0, buttons_y), max(1, button_w), max(1, button_h))
        plus_button.setGeometry(max(0, plus_x), max(0, buttons_y), max(1, button_w), max(1, button_h))
        for button in (minus_button, plus_button):
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton {"
                "background: rgba(35, 24, 12, 185);"
                f"color: {title_color};"
                "border: 1px solid rgba(242, 210, 139, 90);"
                "border-radius: 4px;"
                f"font-size: {button_font_size}px;"
                "font-weight: 700;"
                "padding: 0px;"
                "}"
                "QPushButton:hover { border: 1px solid #f2d28b; color: #ffffff; }"
            )
        minus_button.clicked.connect(lambda: self.on_inventory_money_delta_apply("-"))
        plus_button.clicked.connect(lambda: self.on_inventory_money_delta_apply("+"))
        minus_button.show()
        plus_button.show()

    def on_inventory_money_edit_finished(self, field):
        if self._inventory_loading:
            return
        if field is None:
            return
        cell_ref = str(field.property("inventory_money_cell") or "").strip().upper()
        if not cell_ref:
            return
        new_value = str(field.text())
        old_value = str(self.get_cache_cell_value("Inventar", cell_ref, "") or "")
        if new_value == old_value:
            return
        try:
            self.loader.set_cell_value("Inventar", cell_ref, new_value)
            self.loader.save_active_character_json()
            print(f'[INVENTORY MONEY EDIT] Inventar!{cell_ref} = "{new_value}"')
            print("[INVENTORY SAVE] active character saved")
        except Exception as exc:
            print("[INVENTORY EDIT ERROR]", str(exc))

    def _inventory_parse_non_negative_int(self, value):
        text = str(value or "").strip()
        if not text:
            return 0
        try:
            number = int(float(text))
        except Exception:
            return 0
        return max(0, number)

    def money_to_pfifferling(self, gulden, schilling, heller, pfifferling):
        return (
            int(gulden) * 1000
            + int(schilling) * 100
            + int(heller) * 10
            + int(pfifferling)
        )

    def pfifferling_to_money(self, total_pfifferling):
        total = max(0, int(total_pfifferling))
        gulden = total // 1000
        rest = total % 1000
        schilling = rest // 100
        rest = rest % 100
        heller = rest // 10
        pfifferling = rest % 10
        return {
            "gulden": gulden,
            "schilling": schilling,
            "heller": heller,
            "pfifferling": pfifferling,
        }

    def _inventory_get_wallet_money_values(self):
        values = {}
        for key in ("gulden", "schilling", "heller", "pfifferling"):
            field = self._inventory_money_fields.get(key)
            if field is not None:
                values[key] = self._inventory_parse_non_negative_int(field.text())
            else:
                values[key] = self._inventory_parse_non_negative_int(
                    self.get_cache_cell_value(
                        "Inventar",
                        {"gulden": "B9", "schilling": "E9", "heller": "H9", "pfifferling": "K9"}[key],
                        0,
                    )
                )
        return values

    def on_inventory_money_delta_apply(self, op):
        if self._inventory_loading:
            return
        op = str(op or "").strip()
        if op not in {"+", "-"}:
            return
        wallet = self._inventory_get_wallet_money_values()
        delta = {}
        for key in ("gulden", "schilling", "heller", "pfifferling"):
            field = self._inventory_money_delta_fields.get(key)
            delta[key] = self._inventory_parse_non_negative_int(field.text() if field is not None else 0)
        current_total = self.money_to_pfifferling(
            wallet["gulden"], wallet["schilling"], wallet["heller"], wallet["pfifferling"]
        )
        delta_total = self.money_to_pfifferling(
            delta["gulden"], delta["schilling"], delta["heller"], delta["pfifferling"]
        )
        result_total = current_total + delta_total if op == "+" else current_total - delta_total
        if result_total < 0:
            result_total = 0
        result_money = self.pfifferling_to_money(result_total)
        save_map = {
            "gulden": "B9",
            "schilling": "E9",
            "heller": "H9",
            "pfifferling": "K9",
        }
        try:
            for key, cell_ref in save_map.items():
                value = str(int(result_money.get(key, 0)))
                self.loader.set_cell_value("Inventar", cell_ref, value)
                field = self._inventory_money_fields.get(key)
                if field is not None:
                    field.blockSignals(True)
                    field.setText(value)
                    field.blockSignals(False)
            self.loader.save_active_character_json()
            print(
                "[INVENTORY MONEY DELTA] "
                f"op={op} input={delta['gulden']}/{delta['schilling']}/{delta['heller']}/{delta['pfifferling']} "
                f"result={result_money.get('gulden', 0)}/{result_money.get('schilling', 0)}/"
                f"{result_money.get('heller', 0)}/{result_money.get('pfifferling', 0)}"
            )
            print("[INVENTORY SAVE] active character saved")
            for field in self._inventory_money_delta_fields.values():
                if field is None:
                    continue
                field.setText("0")
        except Exception as exc:
            print("[INVENTORY MONEY DELTA ERROR]", str(exc))

    def get_inventory_wrapped_text_height(self, text, width, font_size, max_lines=0):
        font = QFont()
        font.setPixelSize(max(1, int(font_size)))
        document = QTextDocument()
        document.setDocumentMargin(0)
        document.setDefaultFont(font)
        document.setTextWidth(max(1, int(width)))
        document.setPlainText(str(text or " "))
        height = int(math.ceil(document.size().height()))
        if max_lines and max_lines > 0:
            line_height = QFontMetrics(font).lineSpacing()
            height = min(height, max(1, line_height * int(max_lines)))
        return max(1, height)

    def build_inventory_text_block_html(self, rows, text_cfg):
        font_size = self._safe_int(text_cfg.get("font_size", 14), 14)
        meta_font_size = self._safe_int(text_cfg.get("meta_font_size", 12), 12)
        line_spacing = self._safe_int(text_cfg.get("line_spacing", 4), 4)
        item_spacing = self._safe_int(text_cfg.get("item_spacing", 10), 10)
        text_color = str(text_cfg.get("text_color", "#ffffff"))
        meta_text_color = str(text_cfg.get("meta_text_color", "#7fd0ff"))
        muted_text_color = str(text_cfg.get("muted_text_color", "#c8c0aa"))

        item_html = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "")).strip() or "(ohne Name)"
            pl = str(row.get("pl", "")).strip() or "-"
            count = str(row.get("count", "")).strip() or "-"
            item_html.append(
                "<div class=\"item\">"
                f"<div class=\"name\">{html.escape(name)}</div>"
                f"<div class=\"meta\">PL: {html.escape(pl)}&nbsp;&nbsp;&nbsp;&nbsp;Anzahl: {html.escape(count)}</div>"
                "</div>"
            )
        if not item_html:
            item_html.append('<div class="empty">(keine Einträge)</div>')

        return (
            "<html><head><style>"
            "body { margin: 0; padding: 0; }"
            f".item {{ margin: 0 0 {item_spacing}px 0; }}"
            f".name {{ color: {text_color}; font-size: {font_size}px; line-height: {font_size + line_spacing}px; }}"
            f".meta {{ color: {meta_text_color}; font-size: {meta_font_size}px; line-height: {meta_font_size + line_spacing}px; }}"
            f".empty {{ color: {muted_text_color}; font-size: {font_size}px; }}"
            "</style></head><body>"
            + "".join(item_html)
            + "</body></html>"
        )

    def render_inventory_text_block_tables(self, parent, tables_cfg, sections):
        section_by_id = {
            str(section.get("id", "")): section
            for section in sections
            if isinstance(section, dict)
        }
        table_y = self._safe_int(tables_cfg.get("y", 200), 200)
        default_h = max(1, parent.height() - table_y - 20)
        table_h = self._safe_int(tables_cfg.get("h", default_h), default_h)
        header_h = self._safe_int(tables_cfg.get("header_h", 38), 38)
        header_font_size = self._safe_int(tables_cfg.get("header_font_size", 16), 16)
        header_color = str(tables_cfg.get("header_color", "#f2d28b"))
        text_cfg = tables_cfg.get("text_block", {})
        if not isinstance(text_cfg, dict):
            text_cfg = {}
        background = str(text_cfg.get("background", "rgba(0, 0, 0, 35)"))
        border_color = str(
            text_cfg.get("border_color", tables_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
        )
        text_color = str(text_cfg.get("text_color", "#ffffff"))

        sections_cfg = tables_cfg.get("sections", [])
        if not isinstance(sections_cfg, list):
            sections_cfg = []
        for section_cfg in sections_cfg:
            if not isinstance(section_cfg, dict):
                continue
            section_id = str(section_cfg.get("id", ""))
            section_data = section_by_id.get(section_id, {"rows": [], "title": section_id})
            table_w = self._safe_int(section_cfg.get("w", 430), 430)

            table = QFrame(parent)
            table.setGeometry(
                self._safe_int(section_cfg.get("x", 20), 20),
                table_y,
                table_w,
                table_h,
            )
            table.setStyleSheet(
                f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
            )
            table.show()

            columns = section_cfg.get("columns", {})
            if not isinstance(columns, dict):
                columns = {}
            name_col = columns.get("name", {})
            if not isinstance(name_col, dict):
                name_col = {}
            self.create_panel_text(
                table,
                {"x": 8, "y": 0, "w": max(1, table_w - 16), "h": header_h},
                str(name_col.get("title", section_cfg.get("title", section_data.get("title", "Inventar")))),
                header_font_size,
                header_color,
                bold=True,
                align="left",
            )

            text_edit = QTextEdit(table)
            text_edit.setGeometry(6, header_h, max(1, table_w - 12), max(1, table_h - header_h - 6))
            text_edit.setReadOnly(True)
            text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            text_edit.setStyleSheet(
                "QTextEdit {"
                "background: transparent;"
                "border: none;"
                f"color: {text_color};"
                "padding: 4px;"
                "}"
            )
            rows = section_data.get("rows", [])
            if not isinstance(rows, list):
                rows = []
            text_edit.setHtml(self.build_inventory_text_block_html(rows, text_cfg))
            text_edit.show()

    def render_inventory_table_widget_tables(self, parent, tables_cfg, sections):
        section_by_id = {
            str(section.get("id", "")): section
            for section in sections
            if isinstance(section, dict)
        }
        table_y = self._safe_int(tables_cfg.get("y", 200), 200)
        default_h = max(1, parent.height() - table_y - 20)
        table_h = self._safe_int(tables_cfg.get("h", default_h), default_h)
        title_h = self._safe_int(tables_cfg.get("header_h", 38), 38)
        font_size = self._safe_int(tables_cfg.get("font_size", 14), 14)
        header_font_size = self._safe_int(tables_cfg.get("header_font_size", 16), 16)
        min_row_h = self._safe_int(tables_cfg.get("min_row_h", 28), 28)
        max_row_h = self._safe_int(tables_cfg.get("max_row_h", 72), 72)
        header_color = str(tables_cfg.get("header_color", "#f2d28b"))
        text_color = str(tables_cfg.get("text_color", "#ffffff"))
        value_color = str(tables_cfg.get("value_color", "#7fd0ff"))
        border_color = str(tables_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
        row_background = str(tables_cfg.get("row_background", "rgba(0, 0, 0, 18)"))
        background = str(tables_cfg.get("background", "rgba(5, 5, 5, 95)"))

        sections_cfg = tables_cfg.get("sections", [])
        if not isinstance(sections_cfg, list):
            sections_cfg = []
        for section_cfg in sections_cfg:
            if not isinstance(section_cfg, dict):
                continue
            section_id = str(section_cfg.get("id", ""))
            section_data = section_by_id.get(section_id, {"rows": [], "title": section_id})
            table_w = self._safe_int(section_cfg.get("w", 430), 430)

            container = QFrame(parent)
            container.setGeometry(
                self._safe_int(section_cfg.get("x", 20), 20),
                table_y,
                table_w,
                table_h,
            )
            container.setStyleSheet(
                f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
            )
            container.show()

            columns = section_cfg.get("columns", {})
            if not isinstance(columns, dict):
                columns = {}
            name_col = columns.get("name", {})
            pl_col = columns.get("pl", {})
            count_col = columns.get("count", {})
            if not isinstance(name_col, dict):
                name_col = {}
            if not isinstance(pl_col, dict):
                pl_col = {}
            if not isinstance(count_col, dict):
                count_col = {}

            section_title = str(
                name_col.get("title", section_cfg.get("title", section_data.get("title", "Inventar")))
            )
            self.create_panel_text(
                container,
                {"x": 8, "y": 0, "w": max(1, table_w - 16), "h": title_h},
                section_title,
                header_font_size,
                header_color,
                bold=True,
                align="left",
            )

            table = QTableWidget(container)
            table.setGeometry(6, title_h, max(1, table_w - 12), max(1, table_h - title_h - 6))
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(
                [
                    str(name_col.get("title", section_title)),
                    str(pl_col.get("title", "PL")),
                    str(count_col.get("title", "Anzahl")),
                ]
            )
            table.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.EditKeyPressed
                | QAbstractItemView.SelectedClicked
            )
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            table.setSelectionBehavior(QAbstractItemView.SelectItems)
            table.setFocusPolicy(Qt.StrongFocus)
            table.setWordWrap(True)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(False)
            table.setShowGrid(True)
            table.setStyleSheet(
                "QTableWidget {"
                f"background: {background};"
                f"color: {text_color};"
                f"gridline-color: {border_color};"
                f"font-size: {font_size}px;"
                "border: none;"
                "selection-background-color: rgba(242, 210, 139, 30);"
                "selection-color: #ffffff;"
                "}"
                "QHeaderView::section {"
                "background: rgba(24, 16, 8, 175);"
                f"color: {header_color};"
                f"font-size: {header_font_size}px;"
                "font-weight: 700;"
                f"border: 1px solid {border_color};"
                "padding: 3px;"
                "}"
            )

            rows = section_data.get("rows", [])
            if not isinstance(rows, list):
                rows = []
            table.blockSignals(True)
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                if not isinstance(row, dict):
                    row = {}
                display_values = [
                    str(row.get("name", "")).strip() or "(ohne Name)",
                    str(row.get("pl", "")).strip() or "-",
                    str(row.get("count", "")).strip() or "-",
                ]
                raw_values = [
                    str(row.get("name", "") or ""),
                    str(row.get("pl", "") or ""),
                    str(row.get("count", "") or ""),
                ]
            for column_index, value in enumerate(display_values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, raw_values[column_index])
                item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                item.setBackground(QColor(0, 0, 0, 0))
                item.setForeground(QColor(value_color if column_index in (1, 2) else text_color))
                item.setTextAlignment(
                    Qt.AlignCenter if column_index in (1, 2) else Qt.AlignLeft | Qt.AlignVCenter
                )
                table.setItem(row_index, column_index, item)

            column_widths = [
                self._safe_int(name_col.get("w", 320), 320),
                self._safe_int(pl_col.get("w", 45), 45),
                self._safe_int(count_col.get("w", 60), 60),
            ]
            available_width = max(1, table.width() - 4)
            configured_width = sum(column_widths)
            if configured_width > available_width:
                overflow = configured_width - available_width
                column_widths[0] = max(80, column_widths[0] - overflow)
            for column_index, width in enumerate(column_widths):
                table.setColumnWidth(column_index, max(1, width))

            table.resizeRowsToContents()
            for row_index in range(table.rowCount()):
                height = table.rowHeight(row_index)
                height = max(min_row_h, height)
                if max_row_h > 0:
                    height = min(max_row_h, height)
                table.setRowHeight(row_index, height)
            table.blockSignals(False)

            self._inventory_table_bindings[id(table)] = {
                "section_id": section_id,
                "rows": rows,
            }
            table.cellChanged.connect(
                lambda row_index, column_index, widget=table: self.on_inventory_table_cell_changed(
                    widget, row_index, column_index
                )
            )

            table.show()

    def _apply_inventory_row_heights(self, table, min_row_h, max_row_h):
        for row_index in range(table.rowCount()):
            height = table.rowHeight(row_index)
            height = max(min_row_h, height)
            if max_row_h > 0:
                height = min(max_row_h, height)
            table.setRowHeight(row_index, height)

    def _is_inventory_row_empty(self, row):
        if not isinstance(row, dict):
            return True
        return not bool(
            str(row.get("name", "") or "")
            or str(row.get("pl", "") or "")
            or str(row.get("count", "") or "")
        )

    def _next_inventory_custom_row_index(self, rows, slot_id):
        max_index = -1
        slot_id = str(slot_id or "").strip()
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_slot = str(row.get("custom_slot_id", "") or "").strip()
            if row_slot and slot_id and row_slot != slot_id:
                continue
            if str(row.get("storage", "")).strip() != "custom":
                continue
            try:
                max_index = max(max_index, int(row.get("custom_row_index", -1)))
            except Exception:
                continue
        return max_index + 1

    def _append_inventory_visual_empty_rows(self, table, binding, count):
        if table is None or not isinstance(binding, dict):
            return
        rows = binding.get("rows", [])
        if not isinstance(rows, list):
            return
        slot_id = str(binding.get("section_id", "") or "").strip()
        next_index = self._next_inventory_custom_row_index(rows, slot_id)
        table.blockSignals(True)
        try:
            for _ in range(max(0, int(count))):
                row_data = {
                    "name": "",
                    "pl": "",
                    "count": "",
                    "storage": "custom",
                    "custom_slot_id": slot_id,
                    "custom_row_index": next_index,
                    "is_empty_slot": True,
                }
                rows.append(row_data)
                qt_row = table.rowCount()
                table.insertRow(qt_row)
                for column_index in range(3):
                    item = QTableWidgetItem("")
                    item.setData(Qt.UserRole, "")
                    item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    if column_index in (1, 2):
                        item.setTextAlignment(Qt.AlignCenter)
                    else:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    table.setItem(qt_row, column_index, item)
                next_index += 1
        finally:
            table.blockSignals(False)

    def on_inventory_table_cell_changed(self, table, row_index, column_index):
        if self._inventory_loading:
            return
        binding = self._inventory_table_bindings.get(id(table))
        if not isinstance(binding, dict):
            return
        rows = binding.get("rows", [])
        if not isinstance(rows, list) or row_index < 0 or row_index >= len(rows):
            return
        row = rows[row_index]
        if not isinstance(row, dict):
            return

        column_map = {
            0: ("name", "name_cell"),
            1: ("pl", "pl_cell"),
            2: ("count", "count_cell"),
        }
        if column_index not in column_map:
            return
        value_key, cell_key = column_map[column_index]
        cell_ref = str(row.get(cell_key, "") or "").strip().upper()

        item = table.item(row_index, column_index)
        if item is None:
            return
        new_value = str(item.text())
        old_value = str(item.data(Qt.UserRole) or "")
        if new_value == old_value:
            return
        was_row_empty = self._is_inventory_row_empty(row)
        row_count_before = table.rowCount()

        try:
            if cell_ref:
                self.loader.set_cell_value("Inventar", cell_ref, new_value)
                self.loader.save_active_character_json()
                item.setData(Qt.UserRole, new_value)
                row[value_key] = new_value
                row["is_empty_slot"] = not bool(
                    str(row.get("name", "") or "")
                    or str(row.get("pl", "") or "")
                    or str(row.get("count", "") or "")
                )
                print(f'[INVENTORY EDIT] Inventar!{cell_ref} = "{new_value}"')
                print("[INVENTORY SAVE] active character saved")
            else:
                slot_id = str(row.get("custom_slot_id", binding.get("section_id", "")) or "").strip()
                custom_index = row.get("custom_row_index", row_index)
                if not slot_id:
                    return
                self.loader.set_inventory_custom_row_value(slot_id, custom_index, value_key, new_value)
                self.loader.save_active_character_json()
                item.setData(Qt.UserRole, new_value)
                row[value_key] = new_value
                row["storage"] = "custom"
                row["custom_slot_id"] = slot_id
                try:
                    row["custom_row_index"] = int(custom_index)
                except Exception:
                    row["custom_row_index"] = row_index
                row["is_empty_slot"] = not bool(
                    str(row.get("name", "") or "")
                    or str(row.get("pl", "") or "")
                    or str(row.get("count", "") or "")
                )
                print(f'[INVENTORY CUSTOM EDIT] {slot_id}[{custom_index}].{value_key} = "{new_value}"')
                print("[INVENTORY SAVE] active character saved")

            table.blockSignals(True)
            try:
                table.resizeRowToContents(row_index)
                min_row_h = self._safe_int(binding.get("min_row_h", 34), 34)
                max_row_h = self._safe_int(binding.get("max_row_h", 90), 90)
                height = max(min_row_h, table.rowHeight(row_index))
                if max_row_h > 0:
                    height = min(max_row_h, height)
                table.setRowHeight(row_index, height)
            finally:
                table.blockSignals(False)

            is_row_empty_now = self._is_inventory_row_empty(row)
            row_is_near_end = row_index >= max(0, row_count_before - 3)
            if was_row_empty and not is_row_empty_now and row_is_near_end:
                self._append_inventory_visual_empty_rows(table, binding, 3)
                table.blockSignals(True)
                try:
                    table.resizeRowsToContents()
                    self._apply_inventory_row_heights(
                        table,
                        self._safe_int(binding.get("min_row_h", 34), 34),
                        self._safe_int(binding.get("max_row_h", 90), 90),
                    )
                finally:
                    table.blockSignals(False)
        except Exception as exc:
            print("[INVENTORY EDIT ERROR]", str(exc))
            table.blockSignals(True)
            item.setText(old_value)
            table.blockSignals(False)

    def render_inventory_tables(self, parent, tables_cfg, sections):
        section_by_id = {
            str(section.get("id", "")): section
            for section in sections
            if isinstance(section, dict)
        }
        table_y = self._safe_int(tables_cfg.get("y", 200), 200)
        row_mode = str(tables_cfg.get("row_mode", "")).strip().lower()
        if row_mode == "table_widget":
            self.render_inventory_table_widget_tables(parent, tables_cfg, sections)
            return
        if row_mode == "text_block":
            self.render_inventory_text_block_tables(parent, tables_cfg, sections)
            return
        stacked_mode = row_mode in ("stacked", "stacked_compact", "stacked_dynamic")
        compact_mode = row_mode == "stacked_compact"
        dynamic_mode = row_mode == "stacked_dynamic"
        row_h = self._safe_int(tables_cfg.get("row_h", 34), 34)
        min_row_h = self._safe_int(tables_cfg.get("min_row_h", row_h), row_h)
        name_line_h = self._safe_int(tables_cfg.get("name_line_h", max(20, row_h - 22)), max(20, row_h - 22))
        name_max_lines = self._safe_int(tables_cfg.get("name_max_lines", 0), 0)
        meta_line_h = self._safe_int(tables_cfg.get("meta_line_h", 18), 18)
        row_gap = self._safe_int(tables_cfg.get("row_gap", 0), 0) if stacked_mode else 0
        item_padding_x = self._safe_int(tables_cfg.get("item_padding_x", 8), 8)
        item_padding_y = self._safe_int(tables_cfg.get("item_padding_y", 3), 3)
        header_h = self._safe_int(tables_cfg.get("header_h", 38), 38)
        font_size = self._safe_int(tables_cfg.get("font_size", 14), 14)
        meta_font_size = self._safe_int(tables_cfg.get("meta_font_size", 12), 12)
        header_font_size = self._safe_int(tables_cfg.get("header_font_size", 16), 16)
        max_rows = self._safe_int(tables_cfg.get("max_visible_rows", 16), 16)
        wrap_text = bool(tables_cfg.get("wrap_text", False))
        meta_format = str(tables_cfg.get("meta_format", "PL: {pl}    Anzahl: {count}"))
        header_color = str(tables_cfg.get("header_color", "#f2d28b"))
        text_color = str(tables_cfg.get("text_color", "#ffffff"))
        muted_text_color = str(tables_cfg.get("muted_text_color", "#c8c0aa"))
        value_color = str(tables_cfg.get("value_color", "#7fd0ff"))
        meta_text_color = str(tables_cfg.get("meta_text_color", value_color))
        border_color = str(tables_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
        row_background = str(tables_cfg.get("row_background", "rgba(0, 0, 0, 45)"))
        separator_color = str(tables_cfg.get("separator_color", "rgba(255, 255, 255, 22)"))
        item_border_enabled = bool(tables_cfg.get("item_border_enabled", not compact_mode))
        separator_enabled = bool(tables_cfg.get("separator_enabled", True))

        sections_cfg = tables_cfg.get("sections", [])
        if not isinstance(sections_cfg, list):
            sections_cfg = []
        for section_cfg in sections_cfg:
            if not isinstance(section_cfg, dict):
                continue
            section_id = str(section_cfg.get("id", ""))
            section_data = section_by_id.get(section_id, {"rows": [], "title": section_id})
            table_w = self._safe_int(section_cfg.get("w", 430), 430)
            base_row_h = min_row_h if dynamic_mode else row_h
            table_h = header_h + base_row_h * max_rows + max(0, max_rows - 1) * row_gap
            table = QFrame(parent)
            table.setGeometry(
                self._safe_int(section_cfg.get("x", 20), 20),
                table_y,
                table_w,
                table_h,
            )
            table.setStyleSheet(
                f"background: rgba(5, 5, 5, 95); border: 1px solid {border_color}; border-radius: 4px;"
            )
            table.show()

            header_bg = QFrame(table)
            header_bg.setGeometry(0, 0, table_w, header_h)
            header_bg.setStyleSheet(
                "background: rgba(24, 16, 8, 175);"
                f"border-bottom: 1px solid {border_color};"
            )
            header_bg.show()

            columns = section_cfg.get("columns", {})
            if not isinstance(columns, dict):
                columns = {}
            if stacked_mode:
                name_col = columns.get("name", {})
                if not isinstance(name_col, dict):
                    name_col = {}
                self.create_panel_text(
                    table,
                    {
                        "x": 8,
                        "y": 0,
                        "w": max(1, table_w - 16),
                        "h": header_h,
                    },
                    str(name_col.get("title", section_cfg.get("title", section_data.get("title", "Inventar")))),
                    header_font_size,
                    header_color,
                    bold=True,
                    align="left",
                )
            else:
                for column_id, default_title, align in (
                    ("name", str(section_cfg.get("title", section_data.get("title", "Inventar"))), "left"),
                    ("pl", "PL", "center"),
                    ("count", "Anzahl", "center"),
                ):
                    col_cfg = columns.get(column_id, {})
                    if not isinstance(col_cfg, dict):
                        col_cfg = {}
                    self.create_panel_text(
                        table,
                        {
                            "x": self._safe_int(col_cfg.get("x", 0), 0) + (8 if align == "left" else 0),
                            "y": 0,
                            "w": max(1, self._safe_int(col_cfg.get("w", 80), 80) - (12 if align == "left" else 0)),
                            "h": header_h,
                        },
                        str(col_cfg.get("title", default_title)),
                        header_font_size,
                        header_color,
                        bold=True,
                        align=align,
                    )

            rows = section_data.get("rows", [])
            if not isinstance(rows, list):
                rows = []
            current_y = header_h
            rendered_rows = 0
            content_bottom = table_h
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if rendered_rows >= max_rows:
                    break
                y = current_y
                item_h = row_h
                name_text = str(row.get("name", ""))
                name_h = name_line_h
                if stacked_mode and dynamic_mode:
                    text_w = max(1, table_w - item_padding_x * 2)
                    name_h = self.get_inventory_wrapped_text_height(
                        name_text,
                        text_w,
                        font_size,
                        name_max_lines,
                    )
                    item_h = max(
                        min_row_h,
                        name_h + meta_line_h + item_padding_y * 2,
                    )
                if y + item_h > content_bottom:
                    remaining_count = len(rows) - rendered_rows
                    if remaining_count > 0 and y + 24 <= content_bottom:
                        self.create_panel_text(
                            table,
                            {"x": 8, "y": y, "w": max(1, table_w - 16), "h": 22},
                            "... weitere Einträge",
                            meta_font_size,
                            muted_text_color,
                            bold=False,
                            align="left",
                        )
                    break
                row_bg = QFrame(table)
                row_bg.setGeometry(0, y, table_w, item_h)
                row_border = f"border-bottom: 1px solid {separator_color};" if item_border_enabled else "border: none;"
                row_bg.setStyleSheet(f"background: {row_background}; {row_border}")
                row_bg.lower()
                row_bg.show()

                if stacked_mode:
                    name_label = self.create_panel_text(
                        table,
                        {
                            "x": item_padding_x,
                            "y": y + item_padding_y,
                            "w": max(1, table_w - item_padding_x * 2),
                            "h": max(1, name_h),
                        },
                        name_text,
                        font_size,
                        text_color if name_text.strip() else muted_text_color,
                        bold=False,
                        align="left",
                    )
                    name_label.setWordWrap(wrap_text)
                    name_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                    pl_text = str(row.get("pl", ""))
                    count_text = str(row.get("count", ""))
                    meta_text = meta_format.format(pl=pl_text, count=count_text)
                    meta_label = self.create_panel_text(
                        table,
                        {
                            "x": item_padding_x,
                            "y": y + item_padding_y + name_h,
                            "w": max(1, table_w - item_padding_x * 2),
                            "h": meta_line_h,
                        },
                        meta_text,
                        meta_font_size,
                        meta_text_color,
                        bold=False,
                        align="left",
                    )
                    meta_label.setWordWrap(False)
                    if separator_enabled:
                        separator = QFrame(table)
                        separator.setGeometry(0, y + item_h - 1, table_w, 1)
                        separator.setStyleSheet(f"background: {separator_color}; border: none;")
                        separator.show()
                    current_y += item_h + row_gap
                    rendered_rows += 1
                    continue

                for column_id, key, color, align in (
                    ("name", "name", text_color, "left"),
                    ("pl", "pl", value_color, "center"),
                    ("count", "count", value_color, "center"),
                ):
                    col_cfg = columns.get(column_id, {})
                    if not isinstance(col_cfg, dict):
                        col_cfg = {}
                    left_pad = 8 if align == "left" else 0
                    label = self.create_panel_text(
                        table,
                        {
                            "x": self._safe_int(col_cfg.get("x", 0), 0) + left_pad,
                            "y": y,
                            "w": max(1, self._safe_int(col_cfg.get("w", 80), 80) - left_pad - 4),
                            "h": item_h,
                        },
                        str(row.get(key, "")),
                        font_size,
                        color if str(row.get(key, "")).strip() else muted_text_color,
                        bold=False,
                        align=align,
                    )
                    label.setWordWrap(False)
                current_y += item_h + row_gap
                rendered_rows += 1

    def render_skills_screen(self):
        if self.content_layer is None:
            return

        layout_config = self.load_skills_layout_config()
        skill_definitions = self.load_skill_definitions()
        screen_cfg = layout_config.get("skills_screen", {})
        categories = skill_definitions.get("categories", [])
        if not isinstance(categories, list):
            categories = []
        attribute_map = skill_definitions.get("attribute_map", {})
        if not isinstance(attribute_map, dict):
            attribute_map = {}

        category_ids = [
            str(category.get("id", ""))
            for category in categories
            if isinstance(category, dict) and str(category.get("id", "")).strip()
        ]
        print("[SKILLS] render category:", self.current_skill_category)
        print("[SKILLS] loaded categories:", category_ids)
        has_skills_cache = bool(self.loader.cell_cache) and isinstance(
            self.loader.cell_cache.get("Fertigkeiten"),
            dict,
        )
        if has_skills_cache:
            self.build_skill_source_infos(categories, attribute_map)
        else:
            self.skill_source_infos = {}
            print("[SKILLS NO CACHE] no Fertigkeiten sheet loaded")

        if self.current_skill_category not in category_ids and category_ids:
            self.current_skill_category = category_ids[0]

        screen = QFrame(self.content_layer)
        screen.setGeometry(
            self._safe_int(screen_cfg.get("x", 20), 20),
            self._safe_int(screen_cfg.get("y", 20), 20),
            self._safe_int(screen_cfg.get("w", 1420), 1420),
            self._safe_int(screen_cfg.get("h", 820), 820),
        )
        screen.setStyleSheet("background: transparent;")
        screen.show()

        tabs_cfg = screen_cfg.get("category_tabs", {})
        tabs_container = QFrame(screen)
        tabs_container.setGeometry(
            self._safe_int(tabs_cfg.get("x", 20), 20),
            self._safe_int(tabs_cfg.get("y", 10), 10),
            self._safe_int(tabs_cfg.get("w", 1380), 1380),
            self._safe_int(tabs_cfg.get("h", 50), 50),
        )
        tabs_container.setStyleSheet("background: transparent;")
        tabs_container.show()

        button_w = self._safe_int(tabs_cfg.get("button_w", 220), 220)
        button_h = self._safe_int(tabs_cfg.get("button_h", 42), 42)
        button_gap = self._safe_int(tabs_cfg.get("gap", 18), 18)
        tab_font_size = self._safe_int(tabs_cfg.get("font_size", 20), 20)
        active_color = str(tabs_cfg.get("active_color", "#f2d28b"))
        inactive_color = str(tabs_cfg.get("inactive_color", "#9a8560"))

        for index, category in enumerate(categories):
            if not isinstance(category, dict):
                continue
            category_id = str(category.get("id", "")).strip()
            if not category_id:
                continue
            title = str(category.get("title", category_id))
            is_active = category_id == self.current_skill_category
            button = QPushButton(tabs_container)
            button.setGeometry(index * (button_w + button_gap), 0, button_w, button_h)
            button.setText(title)
            button.setCursor(Qt.PointingHandCursor)
            color = active_color if is_active else inactive_color
            border = "#b88a35" if is_active else "rgba(180, 140, 70, 90)"
            bg = "rgba(35, 24, 12, 185)" if is_active else "rgba(8, 8, 8, 125)"
            button.setStyleSheet(
                "QPushButton {"
                f"background-color: {bg};"
                f"color: {color};"
                f"border: 1px solid {border};"
                "border-radius: 4px;"
                f"font-size: {tab_font_size}px;"
                "font-weight: 700;"
                "padding: 0px;"
                "}"
                "QPushButton:hover { border: 1px solid #f2d28b; color: #ffffff; }"
            )
            button.clicked.connect(
                lambda checked=False, cid=category_id: self.on_skill_category_clicked(cid)
            )
            button.show()

        active_category = None
        for category in categories:
            if isinstance(category, dict) and category.get("id") == self.current_skill_category:
                active_category = category
                break
        if active_category is None:
            active_category = {"id": self.current_skill_category, "skills": []}

        self.render_skills_table(screen, screen_cfg.get("table", {}), active_category, attribute_map)

    def on_skill_category_clicked(self, category_id):
        self.current_skill_category = str(category_id)
        section_id = self.current_main_section
        if section_id not in ("skills", "fertigkeiten"):
            section_id = "skills"
        self.show_main_section(section_id)

    def render_skills_table(self, parent, table_cfg, category, attribute_map):
        table = QFrame(parent)
        table.setGeometry(
            self._safe_int(table_cfg.get("x", 20), 20),
            self._safe_int(table_cfg.get("y", 80), 80),
            self._safe_int(table_cfg.get("w", 1380), 1380),
            self._safe_int(table_cfg.get("h", 700), 700),
        )
        table.setStyleSheet(
            "background: rgba(5, 5, 5, 95);"
            "border: 1px solid rgba(242, 210, 139, 70);"
            "border-radius: 4px;"
        )
        table.show()

        header_h = self._safe_int(table_cfg.get("header_h", 42), 42)
        row_h = self._safe_int(table_cfg.get("row_h", 42), 42)
        max_rows = self._safe_int(table_cfg.get("max_visible_rows", 15), 15)
        font_size = self._safe_int(table_cfg.get("font_size", 17), 17)
        header_font_size = self._safe_int(table_cfg.get("header_font_size", 19), 19)
        header_color = str(table_cfg.get("header_color", "#f2d28b"))
        columns = table_cfg.get("columns", {})
        if not isinstance(columns, dict):
            columns = {}

        header_bg = QFrame(table)
        header_bg.setGeometry(0, 0, table.width(), header_h)
        header_bg.setStyleSheet(
            "background: rgba(24, 16, 8, 175); border-bottom: 1px solid rgba(242, 210, 139, 85);"
        )
        header_bg.show()

        for column_id in ("skill", "attributes", "value", "specialization", "note"):
            col_cfg = columns.get(column_id, {})
            self.create_panel_text(
                table,
                {
                    "x": self._safe_int(col_cfg.get("x", 0), 0),
                    "y": 0,
                    "w": self._safe_int(col_cfg.get("w", 120), 120),
                    "h": header_h,
                },
                str(col_cfg.get("title", column_id)),
                header_font_size,
                header_color,
                bold=True,
                align="center" if column_id in ("attributes", "value") else "left",
            )

        if not self.loader.cell_cache:
            self.create_panel_text(
                table,
                {"x": 0, "y": header_h, "w": table.width(), "h": row_h * 2},
                "Kein Charaktercache geladen",
                font_size,
                str(table_cfg.get("note_color", "#d8d0b0")),
                bold=True,
                align="center",
            )
            print("[SKILLS NO CACHE] no Fertigkeiten sheet loaded")
            return
        if not isinstance(self.loader.cell_cache.get("Fertigkeiten"), dict):
            self.create_panel_text(
                table,
                {"x": 0, "y": header_h, "w": table.width(), "h": row_h * 2},
                "Keine Fertigkeiten-Daten gefunden",
                font_size,
                str(table_cfg.get("note_color", "#d8d0b0")),
                bold=True,
                align="center",
            )
            print("[SKILLS NO CACHE] no Fertigkeiten sheet loaded")
            return

        skills = category.get("skills", []) if isinstance(category, dict) else []
        if not isinstance(skills, list):
            skills = []
        category_id = str(category.get("id", "")) if isinstance(category, dict) else ""
        visible_skills = skills[:max_rows]
        print("[SKILLS RENDER]", f"category={category_id}")
        print("[SKILLS RENDER]", f"source rows={len(skills)}")
        print("[SKILLS RENDER]", f"visible rows={len(visible_skills)}")
        if len(skills) > max_rows:
            print("[SKILLS] rows truncated:", category_id)

        row_colors = ("rgba(8, 8, 8, 125)", "rgba(20, 20, 20, 105)")
        current_y = header_h
        for index, skill in enumerate(visible_skills):
            if not isinstance(skill, dict):
                continue
            y = current_y
            row_bg = QFrame(table)
            row_bg.setGeometry(0, y, table.width(), row_h)
            row_bg.setStyleSheet(
                f"background: {row_colors[index % 2]};"
                "border-bottom: 1px solid rgba(255, 255, 255, 24);"
            )
            row_bg.lower()
            row_bg.show()

            skill_name = str(skill.get("name", ""))
            attributes = skill.get("attributes", [])
            if not isinstance(attributes, list):
                attributes = []
            attribute_sum = self.calculate_skill_attribute_sum(skill, attribute_map)
            source_key = self.get_skill_source_key(category_id, skill)
            source_info = self.skill_source_infos.get(source_key)
            if not isinstance(source_info, dict):
                source_info = self.build_skill_source_info(skill, category_id, attribute_map)
            display_name = source_info.get("display_name", skill_name)
            if not isinstance(display_name, str) or not display_name.strip():
                display_name = skill_name
            sheet_value = source_info.get("calculated_value")
            if sheet_value is None:
                display_value = "0" if source_info.get("row") is not None else ""
                print(
                    "[SKILLS FALLBACK]",
                    display_name,
                    "no sheet value, using:",
                    display_value if display_value else "blank",
                )
            else:
                display_value = self.format_character_display_value(sheet_value, "int")
                try:
                    sheet_int_value = int(display_value)
                except Exception:
                    sheet_int_value = sheet_value
                if sheet_int_value != attribute_sum:
                    print(
                        "[SKILLS DIFF]",
                        display_name,
                        "sheet:",
                        sheet_value,
                        "attribute_sum:",
                        attribute_sum,
                        "display:",
                        display_value,
                    )
                else:
                    print(
                        "[SKILLS OK]",
                        display_name,
                        "sheet:",
                        sheet_value,
                        "attribute_sum:",
                        attribute_sum,
                        "display:",
                        display_value,
                    )
            print("[SKILLS] skill value:", display_name, attributes[:4], "->", display_value)
            print(
                "[SKILLS ROW]",
                f"row={source_info.get('row')}",
                f"name={display_name}",
                f"value={display_value}",
            )
            slot_values = source_info.get("display_attribute_slots", [])
            if not isinstance(slot_values, list) or len(slot_values) < 4:
                row_value = source_info.get("row")
                block = self.get_skill_block_config_for_row(row_value, category_id) if row_value is not None else None
                slot_values = self.get_skill_attribute_slot_values_from_row(row_value, block) if row_value is not None else ["", "", "", ""]
            slot_values = (slot_values + ["", "", "", ""])[:4]
            display_specialization = source_info.get("display_specialization", "")
            display_note = source_info.get("display_note", "")

            skill_col = columns.get("skill", {})
            attr_col = columns.get("attributes", {})
            value_col = columns.get("value", {})
            spec_col = columns.get("specialization", {})
            note_col = columns.get("note", {})
            spec_x = self._safe_int(spec_col.get("x", 690), 690) + 8
            spec_w = max(1, self._safe_int(spec_col.get("w", 470), 470) - 12)
            note_x = self._safe_int(note_col.get("x", 1170), 1170) + 8
            note_w = max(1, self._safe_int(note_col.get("w", 210), 210) - 12)
            row_height = row_h
            row_bg.setGeometry(0, y, table.width(), row_height)

            skill_x = self._safe_int(skill_col.get("x", 0), 0) + 8
            skill_w = max(1, self._safe_int(skill_col.get("w", 360), 360) - 12)
            skill_button = QPushButton(table)
            skill_button.setGeometry(skill_x, y, skill_w, row_height)
            skill_button.setText(display_name)
            skill_button.setFlat(True)
            skill_button.setCursor(Qt.PointingHandCursor)
            skill_button.setStyleSheet(
                "QPushButton {"
                "background: transparent;"
                "border: none;"
                f"color: {str(table_cfg.get('skill_name_color', '#f2d28b'))};"
                f"font-size: {font_size}px;"
                "font-weight: 700;"
                "text-align: left;"
                "padding: 0px;"
                "}"
                "QPushButton:hover { border: 1px solid rgba(242, 210, 139, 60); }"
            )
            skill_button.clicked.connect(
                lambda checked=False, sk=source_key: self.on_skill_row_roll_clicked(sk)
            )
            skill_button.setToolTip(display_name if display_name else "")
            skill_button.show()

            slot_w = self._safe_int(attr_col.get("slot_w", 42), 42)
            slot_gap = self._safe_int(attr_col.get("slot_gap", 8), 8)
            attr_x = self._safe_int(attr_col.get("x", 370), 370)
            attribute_cells = source_info.get("attribute_cells", [])
            if not isinstance(attribute_cells, list):
                attribute_cells = []
            for slot_index in range(4):
                letter = str(slot_values[slot_index] or "")
                slot_x = attr_x + slot_index * (slot_w + slot_gap)
                slot_h = max(1, row_height - 10)
                slot_y = y + 5
                slot = QPushButton(table)
                slot.setGeometry(
                    slot_x,
                    slot_y,
                    slot_w,
                    slot_h,
                )
                slot.setStyleSheet(
                    "QPushButton {"
                    "background: rgba(0, 0, 0, 105);"
                    "border: 1px solid rgba(255, 255, 255, 42);"
                    "border-radius: 3px;"
                    f"color: {str(table_cfg.get('attribute_color', '#ffffff'))};"
                    f"font-size: {font_size}px;"
                    "font-weight: 700;"
                    "padding: 0px;"
                    "}"
                    "QPushButton:hover { border: 1px solid rgba(242, 210, 139, 140); }"
                )
                slot.setText(letter)
                slot.setFlat(True)
                slot.setProperty("source_key", source_key)
                slot.setProperty("slot_index", slot_index)
                slot.setProperty("sheet_name", "Fertigkeiten")
                slot.setProperty(
                    "cell_ref",
                    str(attribute_cells[slot_index]).strip().upper()
                    if slot_index < len(attribute_cells)
                    else "",
                )
                if self.is_skill_attribute_slot_editable(source_info, slot_index):
                    slot.setCursor(Qt.PointingHandCursor)
                    slot.setToolTip("Attribut ändern")
                    slot.clicked.connect(
                        lambda checked=False, widget=slot: self.open_skill_attribute_slot_menu(widget)
                    )
                else:
                    slot.setCursor(Qt.ArrowCursor)
                slot.show()

            value_x = self._safe_int(value_col.get("x", 600), 600)
            value_w = self._safe_int(value_col.get("w", 80), 80)
            value_button = QPushButton(table)
            value_button.setGeometry(value_x, y, value_w, row_height)
            value_button.setText(display_value)
            value_button.setFlat(True)
            value_button.setCursor(Qt.PointingHandCursor)
            value_button.setStyleSheet(
                "QPushButton {"
                "background: transparent;"
                "border: none;"
                f"color: {str(table_cfg.get('value_color', '#7fd0ff'))};"
                f"font-size: {font_size}px;"
                "font-weight: 700;"
                "text-align: center;"
                "padding: 0px;"
                "}"
                "QPushButton:hover { border: 1px solid rgba(127, 208, 255, 60); }"
            )
            value_button.clicked.connect(
                lambda checked=False, sk=source_key: self.on_skill_row_roll_clicked(sk)
            )
            value_button.show()
            spec_text = str(display_specialization)
            if self.is_skill_specialization_editable(source_info):
                spec_editor = InlineTextEdit(
                    on_commit=lambda new_text, old_text, sk=source_key: self.save_skill_text_cell_value(
                        sk, "specialization", new_text, old_text
                    ),
                    parent=table,
                )
                spec_editor.setGeometry(spec_x, y + 2, spec_w, max(24, row_height - 4))
                spec_editor.set_initial_text(spec_text)
                spec_editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                spec_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                spec_editor.setStyleSheet(
                    "QTextEdit {"
                    "background: transparent;"
                    "border: 1px solid rgba(242, 210, 139, 40);"
                    f"color: {str(table_cfg.get('specialization_color', '#ffffff'))};"
                    f"font-size: {font_size}px;"
                    "font-weight: 500;"
                    "padding: 0px;"
                    "}"
                    "QTextEdit:focus { border: 1px solid rgba(242, 210, 139, 120); }"
                )
                spec_editor.setToolTip(spec_text if spec_text else "Spezialisierung bearbeiten")
                spec_editor.show()
            else:
                spec_label = self.create_panel_text(
                    table,
                    {
                        "x": spec_x,
                        "y": y,
                        "w": spec_w,
                        "h": row_height,
                    },
                    spec_text,
                    font_size,
                    str(table_cfg.get("specialization_color", "#ffffff")),
                )
                spec_label.setToolTip(spec_text if spec_text else "")
            note_text = str(display_note)
            if self.is_skill_note_editable(source_info):
                note_editor = InlineTextEdit(
                    on_commit=lambda new_text, old_text, sk=source_key: self.save_skill_text_cell_value(
                        sk, "note", new_text, old_text
                    ),
                    parent=table,
                )
                note_editor.setGeometry(note_x, y + 2, note_w, max(24, row_height - 4))
                note_editor.set_initial_text(note_text)
                note_editor.setLineWrapMode(QTextEdit.NoWrap)
                note_editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                note_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                note_editor.setStyleSheet(
                    "QTextEdit {"
                    "background: transparent;"
                    "border: 1px solid rgba(216, 208, 176, 35);"
                    f"color: {str(table_cfg.get('note_color', '#d8d0b0'))};"
                    f"font-size: {font_size}px;"
                    "font-weight: 400;"
                    "padding: 0px;"
                    "}"
                    "QTextEdit:focus { border: 1px solid rgba(216, 208, 176, 100); }"
                )
                note_editor.setToolTip(note_text if note_text else "Notiz bearbeiten")
                note_editor.show()
            else:
                note_label = self.create_panel_text(
                    table,
                    {
                        "x": note_x,
                        "y": y,
                        "w": note_w,
                        "h": row_height,
                    },
                    note_text,
                    font_size,
                    str(table_cfg.get("note_color", "#d8d0b0")),
                )
                note_label.setToolTip(note_text if note_text else "")
            current_y += row_height

    def _read_data_map_cell(self, mapping_entry, default_sheet, fallback="-"):
        sheet_name = default_sheet
        cell_ref = None
        if isinstance(mapping_entry, str):
            cell_ref = mapping_entry
        elif isinstance(mapping_entry, dict):
            sheet_name = str(mapping_entry.get("sheet", default_sheet))
            raw_cell = mapping_entry.get("cell")
            if isinstance(raw_cell, str):
                cell_ref = raw_cell
        if not isinstance(cell_ref, str) or not cell_ref:
            return fallback
        return self.get_cache_display_value(sheet_name, cell_ref, fallback)

    def _create_content_panel(self, parent, cfg):
        x = int(cfg.get("x", 0))
        y = int(cfg.get("y", 0))
        w = int(cfg.get("w", 300))
        h = int(cfg.get("h", 300))
        panel = QFrame(parent)
        panel.setGeometry(x, y, w, h)
        asset = str(cfg.get("asset", "")).strip()
        pixmap = self.load_ui_pixmap(asset) if asset else None
        if pixmap is not None:
            bg = QLabel(panel)
            bg.setGeometry(0, 0, w, h)
            bg.setPixmap(pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
            bg.lower()
        else:
            panel.setStyleSheet(
                "background: rgba(12, 12, 12, 170); border: 1px solid rgba(200, 200, 200, 70); border-radius: 6px;"
            )
        panel.show()
        return panel

    def _col_letters_to_index(self, col_letters):
        col = 0
        for letter in col_letters.upper():
            if "A" <= letter <= "Z":
                col = col * 26 + (ord(letter) - ord("A") + 1)
        return col

    def _col_index_to_letters(self, index):
        if index < 1:
            return "A"
        letters = ""
        number = index
        while number > 0:
            number, remainder = divmod(number - 1, 26)
            letters = chr(ord("A") + remainder) + letters
        return letters

    def _safe_int(self, value, default):
        try:
            return int(value)
        except Exception:
            return int(default)

    def parse_layout_color(self, value, fallback=None):
        text = str(value or "").strip()
        if text:
            rgba_match = re.match(
                r"rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)",
                text,
                flags=re.IGNORECASE,
            )
            if rgba_match:
                r_val = max(0, min(255, int(rgba_match.group(1))))
                g_val = max(0, min(255, int(rgba_match.group(2))))
                b_val = max(0, min(255, int(rgba_match.group(3))))
                a_val = max(0, min(255, int(rgba_match.group(4))))
                return QColor(r_val, g_val, b_val, a_val), True

            rgb_match = re.match(
                r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)",
                text,
                flags=re.IGNORECASE,
            )
            if rgb_match:
                r_val = max(0, min(255, int(rgb_match.group(1))))
                g_val = max(0, min(255, int(rgb_match.group(2))))
                b_val = max(0, min(255, int(rgb_match.group(3))))
                return QColor(r_val, g_val, b_val), True

            color = QColor(text)
            if color.isValid():
                return color, True

        fallback_color = QColor(fallback) if fallback else QColor()
        if not fallback_color.isValid():
            fallback_color = QColor(0, 0, 0, 0)
        return fallback_color, False

    def get_text_font_size(self, cfg, fallback):
        if isinstance(cfg, dict) and cfg.get("font_size") is not None:
            return self._safe_int(cfg.get("font_size"), fallback)
        return self._safe_int(fallback, 14)

    def get_text_color(self, cfg, fallback):
        if isinstance(cfg, dict) and cfg.get("color") is not None:
            return str(cfg.get("color"))
        return str(fallback)

    def get_text_bold(self, cfg, fallback=False):
        if isinstance(cfg, dict) and cfg.get("bold") is not None:
            return bool(cfg.get("bold"))
        return bool(fallback)

    def get_text_align(self, cfg, fallback="left"):
        if isinstance(cfg, dict) and cfg.get("align") is not None:
            return str(cfg.get("align"))
        return str(fallback)

    def create_panel_text(
        self, parent, rect_cfg, text, font_size, color, bold=False, align="left"
    ):
        x = self._safe_int(rect_cfg.get("x", 0), 0)
        y = self._safe_int(rect_cfg.get("y", 0), 0)
        w = self._safe_int(rect_cfg.get("w", 160), 160)
        h = self._safe_int(rect_cfg.get("h", 28), 28)
        label = QLabel(parent)
        label.setGeometry(x, y, w, h)
        label.setText(str(text))
        if align == "center":
            alignment = Qt.AlignCenter
        elif align == "right":
            alignment = Qt.AlignRight | Qt.AlignVCenter
        else:
            alignment = Qt.AlignLeft | Qt.AlignVCenter
        label.setAlignment(alignment)
        weight = 700 if bold else 500
        label.setStyleSheet(
            f"background: transparent; color: {color}; font-size: {int(font_size)}px; font-weight: {weight};"
        )
        label.raise_()
        label.show()
        return label

    def render_character_screen(self):
        if self.content_layer is None:
            return
        character_screen = self.main_ui_layout_config.get("character_screen")
        if not isinstance(character_screen, dict):
            self.render_character_front()
            return

        default_text_style = self.theme_style.get("default_text", {})
        default_color = str(default_text_style.get("color", "#e8e0c8"))
        data_map = character_screen.get("data_map", {})
        text_layout = character_screen.get("text_layout", {})
        panels_cfg = character_screen.get("panels", {})

        character_panel_cfg = panels_cfg.get("character_info_panel", {})
        attribute_panel_cfg = panels_cfg.get("attribute_panel", {})
        perk_panel_cfg = panels_cfg.get("perk_panel", {})

        character_panel = self._create_content_panel(self.content_layer, character_panel_cfg)
        attribute_panel = self._create_content_panel(self.content_layer, attribute_panel_cfg)
        perk_panel = self._create_content_panel(self.content_layer, perk_panel_cfg)

        default_sheet = "Charakterbogen"
        basic_map = data_map.get("basic", {})
        name_value = self._read_data_map_cell(basic_map.get("name", "G1"), default_sheet, "Unbekannter Charakter")
        race_value = self._read_data_map_cell(basic_map.get("race", "G3"), default_sheet)
        size_value = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("size", "G5"), default_sheet),
            "auto",
        )
        weight_value = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("weight", "G7"), default_sheet),
            "auto",
        )
        hp_current = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("hp_current", "B10"), default_sheet),
            "int",
        )
        hp_max = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("hp_max", "F10"), default_sheet),
            "int",
        )
        mp_current = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("mp_current", "B13"), default_sheet),
            "int",
        )
        mp_max = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("mp_max", "F13"), default_sheet),
            "int",
        )
        exp_current = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("exp_current", "B16"), default_sheet),
            "int",
        )
        exp_max = self.format_character_display_value(
            self._read_data_map_cell(basic_map.get("exp_max", "F16"), default_sheet),
            "int",
        )

        info_layout = text_layout.get("character_info_panel", text_layout.get("info", {}))
        title_cfg = info_layout.get("title", {})
        self.create_panel_text(
            character_panel,
            title_cfg if isinstance(title_cfg, dict) else {},
            name_value if name_value != "-" else "Unbekannter Charakter",
            self.get_text_font_size(title_cfg, 30),
            self.get_text_color(title_cfg, default_color),
            bold=self.get_text_bold(title_cfg, True),
            align=self.get_text_align(title_cfg, "left"),
        )

        fields_cfg = info_layout.get("fields", {})
        field_rows = fields_cfg.get("rows", []) if isinstance(fields_cfg, dict) else []
        if isinstance(field_rows, list) and field_rows:
            portrait_cfg = info_layout.get("portrait", {})
            if isinstance(portrait_cfg, dict) and bool(portrait_cfg.get("enabled", False)):
                portrait = QFrame(character_panel)
                portrait.setGeometry(
                    self._safe_int(portrait_cfg.get("x", 0), 0),
                    self._safe_int(portrait_cfg.get("y", 0), 0),
                    self._safe_int(portrait_cfg.get("w", 120), 120),
                    self._safe_int(portrait_cfg.get("h", 160), 160),
                )
                portrait.setStyleSheet(
                    f"background: {str(portrait_cfg.get('fallback_color', 'rgba(0, 0, 0, 90)'))};"
                    "border: 1px solid rgba(255, 255, 255, 35);"
                )
                portrait.lower()
                portrait.show()

            field_single_sources = {
                "race": basic_map.get("race", "G3"),
                "size": basic_map.get("size", "G5"),
                "weight": basic_map.get("weight", "G7"),
            }
            field_pair_sources = {
                "hp": (basic_map.get("hp_current", "B10"), basic_map.get("hp_max", "F10")),
                "mp": (basic_map.get("mp_current", "B13"), basic_map.get("mp_max", "F13")),
                "exp": (basic_map.get("exp_current", "B16"), basic_map.get("exp_max", "F16")),
                "lifeforce": (
                    basic_map.get("lifeforce_current", ""),
                    basic_map.get("lifeforce_max", ""),
                ),
                "sanity": (
                    basic_map.get("sanity_current", ""),
                    basic_map.get("sanity_max", ""),
                ),
                "faith": (
                    basic_map.get("faith_current", ""),
                    basic_map.get("faith_max", ""),
                ),
            }
            label_font_default = self._safe_int(fields_cfg.get("label_font_size", 18), 18)
            value_font_default = self._safe_int(fields_cfg.get("value_font_size", 18), 18)
            label_color_default = str(fields_cfg.get("label_color", default_color))
            value_color_default = str(fields_cfg.get("value_color", "#ffffff"))
            bold_values_default = bool(fields_cfg.get("bold_values", True))

            for row in field_rows:
                if not isinstance(row, dict):
                    continue
                row_id = str(row.get("id", "")).strip().lower()
                if not row_id:
                    continue
                mode = str(row.get("mode", "raw" if row_id in ("race",) else "auto"))
                label_text = str(row.get("label", row_id.capitalize()))
                if row_id in field_pair_sources:
                    current_src, max_src = field_pair_sources[row_id]
                    current = self.format_character_display_value(
                        self._read_data_map_cell(current_src, default_sheet),
                        mode,
                    )
                    maximum = self.format_character_display_value(
                        self._read_data_map_cell(max_src, default_sheet),
                        mode,
                    )
                    value_text = str(row.get("format", "{current} / {max}")).format(
                        current=current,
                        max=maximum,
                    )
                else:
                    source = field_single_sources.get(row_id)
                    value_text = self.format_character_display_value(
                        self._read_data_map_cell(source, default_sheet),
                        mode,
                    )

                self.create_panel_text(
                    character_panel,
                    row.get("label_rect", {}),
                    label_text,
                    self._safe_int(row.get("label_font_size", row.get("font_size", label_font_default)), 14),
                    str(row.get("label_color", row.get("color", label_color_default))),
                    bold=bool(row.get("label_bold", False)),
                    align=str(row.get("label_align", "left")),
                )
                self.create_panel_text(
                    character_panel,
                    row.get("value_rect", {}),
                    value_text,
                    self._safe_int(row.get("value_font_size", row.get("font_size", value_font_default)), 15),
                    str(row.get("value_color", row.get("color", value_color_default))),
                    bold=bool(row.get("bold_value", bold_values_default)),
                    align=str(row.get("value_align", "left")),
                )
        else:
            basic_rows_cfg = info_layout.get("basic_rows", {})
            basic_rows = basic_rows_cfg.get("rows", [])
            basic_values = {"race": race_value, "size": size_value, "weight": weight_value}
            if isinstance(basic_rows, list) and basic_rows:
                for row in basic_rows:
                    if not isinstance(row, dict):
                        continue
                    row_id = str(row.get("id", "")).strip().lower()
                    label_text = str(row.get("label", row_id.capitalize() if row_id else ""))
                    value_text = basic_values.get(row_id, "-")
                    self.create_panel_text(
                        character_panel,
                        row.get("label_rect", {}),
                        label_text,
                        self._safe_int(row.get("label_font_size", basic_rows_cfg.get("label_font_size", 18)), 18),
                        str(row.get("label_color", basic_rows_cfg.get("label_color", default_color))),
                        bold=False,
                        align=str(row.get("label_align", "left")),
                    )
                    self.create_panel_text(
                        character_panel,
                        row.get("value_rect", {}),
                        value_text,
                        self._safe_int(row.get("value_font_size", basic_rows_cfg.get("value_font_size", 18)), 18),
                        str(row.get("value_color", basic_rows_cfg.get("value_color", "#ffffff"))),
                        bold=True,
                        align=str(row.get("value_align", "left")),
                    )
            else:
                rows_cfg = info_layout.get("rows", {})
                rows_x_label = self._safe_int(rows_cfg.get("label_x", 24), 24)
                rows_x_value = self._safe_int(rows_cfg.get("value_x", 210), 210)
                rows_start_y = self._safe_int(rows_cfg.get("start_y", 90), 90)
                rows_gap = self._safe_int(rows_cfg.get("row_gap", 34), 34)
                rows_font = self._safe_int(rows_cfg.get("font_size", 18), 18)
                rows_values = [("Rasse", race_value), ("Größe", size_value), ("Gewicht", weight_value)]
                for i, (label_text, value_text) in enumerate(rows_values):
                    y = rows_start_y + i * rows_gap
                    self.create_panel_text(
                        character_panel,
                        {"x": rows_x_label, "y": y, "w": 180, "h": 30},
                        f"{label_text}:",
                        rows_font,
                        str(rows_cfg.get("label_color", default_color)),
                    )
                    self.create_panel_text(
                        character_panel,
                        {"x": rows_x_value, "y": y, "w": max(120, character_panel.width() - rows_x_value - 20), "h": 30},
                        value_text,
                        rows_font,
                        str(rows_cfg.get("value_color", "#ffffff")),
                        bold=True,
                    )

            stats_rows_cfg = info_layout.get("stat_rows", {})
            stats_rows = stats_rows_cfg.get("rows", [])
            stats_values = {
                "hp": f"{hp_current} / {hp_max}",
                "mp": f"{mp_current} / {mp_max}",
                "exp": f"{exp_current} / {exp_max}",
            }
            if isinstance(stats_rows, list) and stats_rows:
                for row in stats_rows:
                    if not isinstance(row, dict):
                        continue
                    row_id = str(row.get("id", "")).strip().lower()
                    label_text = str(row.get("label", row_id.upper() if row_id else ""))
                    value_text = stats_values.get(row_id, "-")
                    self.create_panel_text(
                        character_panel,
                        row.get("label_rect", {}),
                        label_text,
                        self._safe_int(row.get("label_font_size", stats_rows_cfg.get("label_font_size", 20)), 20),
                        str(row.get("label_color", stats_rows_cfg.get("label_color", default_color))),
                        bold=True,
                        align=str(row.get("label_align", "left")),
                    )
                    self.create_panel_text(
                        character_panel,
                        row.get("value_rect", {}),
                        value_text,
                        self._safe_int(row.get("value_font_size", stats_rows_cfg.get("value_font_size", 26)), 26),
                        str(row.get("value_color", stats_rows_cfg.get("value_color", "#ffffff"))),
                        bold=True,
                        align=str(row.get("value_align", "left")),
                    )
            else:
                stats_cfg = info_layout.get("stats", {})
                stats_x_label = self._safe_int(stats_cfg.get("label_x", 24), 24)
                stats_x_value = self._safe_int(stats_cfg.get("value_x", 210), 210)
                stats_start_y = self._safe_int(stats_cfg.get("start_y", 230), 230)
                stats_gap = self._safe_int(stats_cfg.get("row_gap", 52), 52)
                hp_label_font = self._safe_int(stats_cfg.get("hp_label_font_size", 22), 22)
                hp_value_font = self._safe_int(stats_cfg.get("hp_value_font_size", 30), 30)
                mp_label_font = self._safe_int(stats_cfg.get("mp_label_font_size", 20), 20)
                mp_value_font = self._safe_int(stats_cfg.get("mp_value_font_size", 28), 28)
                exp_label_font = self._safe_int(stats_cfg.get("exp_label_font_size", 18), 18)
                exp_value_font = self._safe_int(stats_cfg.get("exp_value_font_size", 22), 22)
                stat_rows = [
                    ("HP", f"{hp_current} / {hp_max}", hp_label_font, hp_value_font),
                    ("MP", f"{mp_current} / {mp_max}", mp_label_font, mp_value_font),
                    ("EXP", f"{exp_current} / {exp_max}", exp_label_font, exp_value_font),
                ]
                for i, (label_text, value_text, lf, vf) in enumerate(stat_rows):
                    y = stats_start_y + i * stats_gap
                    self.create_panel_text(
                        character_panel,
                        {"x": stats_x_label, "y": y, "w": 140, "h": 34},
                        f"{label_text}:",
                        lf,
                        str(stats_cfg.get("label_color", default_color)),
                        bold=True,
                    )
                    self.create_panel_text(
                        character_panel,
                        {"x": stats_x_value, "y": y - 8, "w": max(160, character_panel.width() - stats_x_value - 20), "h": max(34, vf + 10)},
                        value_text,
                        vf,
                        str(stats_cfg.get("value_color", "#ffffff")),
                        bold=True,
                    )

            for bar_key, default_y, bar_color in (("hp_bar", 276, "#cc4444"), ("mp_bar", 328, "#4477cc")):
                bar_cfg = info_layout.get(bar_key, {})
                if bool(bar_cfg.get("enabled", True)):
                    bar_bg = QFrame(character_panel)
                    bar_x = self._safe_int(bar_cfg.get("x", 24), 24)
                    bar_y = self._safe_int(bar_cfg.get("y", default_y), default_y)
                    bar_w = self._safe_int(bar_cfg.get("w", 260), 260)
                    bar_h = self._safe_int(bar_cfg.get("h", 12), 12)
                    bar_bg.setGeometry(bar_x, bar_y, bar_w, bar_h)
                    bar_bg.setStyleSheet("background: rgba(10, 10, 10, 180); border: 1px solid rgba(0,0,0,120);")
                    bar_fill = QFrame(bar_bg)
                    bar_fill.setGeometry(0, 0, bar_w, bar_h)
                    bar_fill.setStyleSheet(f"background: {str(bar_cfg.get('color', bar_color))};")
                    bar_bg.show()

        attr_layout = text_layout.get("attribute_panel", text_layout.get("attributes", {}))
        attr_map = data_map.get("attributes", {})
        body_map = attr_map.get("body", {})
        mind_map = attr_map.get("mind", {})

        panel_title_cfg = attr_layout.get("panel_title", {})
        if isinstance(panel_title_cfg, dict):
            panel_title_text = str(panel_title_cfg.get("text", "Attribute")).strip() or "Attribute"
            panel_title_rect = panel_title_cfg.get("rect", panel_title_cfg)
            self.create_panel_text(
                attribute_panel,
                panel_title_rect if isinstance(panel_title_rect, dict) else {},
                panel_title_text,
                self.get_text_font_size(panel_title_cfg, 24),
                self.get_text_color(panel_title_cfg, default_color),
                bold=self.get_text_bold(panel_title_cfg, True),
                align=self.get_text_align(panel_title_cfg, "center"),
            )

        body_header_layout = attr_layout.get("body_header", {})
        mind_header_layout = attr_layout.get("mind_header", {})
        header_style = attr_layout.get("header", {})
        rows_style = attr_layout.get("rows", {})
        value_font_size = self._safe_int(
            attr_layout.get("value_font_size", rows_style.get("font_size", 18)),
            18,
        )

        body_header_label = str(body_map.get("label", body_header_layout.get("label", "Körper"))).strip() + ":"
        mind_header_label = str(mind_map.get("label", mind_header_layout.get("label", "Geist"))).strip() + ":"

        def resolve_cell_value(mapping, fallback="-"):
            if isinstance(mapping, str):
                return self.get_cache_display_value(default_sheet, mapping, fallback)
            if isinstance(mapping, dict):
                sheet = str(mapping.get("sheet", default_sheet))
                cell = mapping.get("cell")
                if isinstance(cell, str):
                    return self.get_cache_display_value(sheet, cell, fallback)
            return fallback

        body_header_cell = body_map.get("value", body_map.get("header", "-"))
        mind_header_cell = mind_map.get("value", mind_map.get("header", "-"))
        body_header_raw_value = resolve_cell_value(body_header_cell, "-")
        mind_header_raw_value = resolve_cell_value(mind_header_cell, "-")
        body_header_value = self.format_character_display_value(body_header_raw_value, "int")
        mind_header_value = self.format_character_display_value(mind_header_raw_value, "int")
        body_header_cell_txt = (
            body_header_cell
            if isinstance(body_header_cell, str)
            else str(body_header_cell.get("cell", "-")) if isinstance(body_header_cell, dict) else "-"
        )
        mind_header_cell_txt = (
            mind_header_cell
            if isinstance(mind_header_cell, str)
            else str(mind_header_cell.get("cell", "-")) if isinstance(mind_header_cell, dict) else "-"
        )
        print("[ATTR]", "body.header", body_header_cell_txt, "->", body_header_value)
        print("[ATTR]", "mind.header", mind_header_cell_txt, "->", mind_header_value)
        print("[DISPLAY ATTR]", "body.header", body_header_raw_value, "->", body_header_value)
        print("[DISPLAY ATTR]", "mind.header", mind_header_raw_value, "->", mind_header_value)

        self.create_panel_text(
            attribute_panel,
            body_header_layout.get("label_rect", {"x": 24, "y": 24, "w": 120, "h": 30}),
            body_header_label,
            self._safe_int(
                body_header_layout.get(
                    "label_font_size",
                    body_header_layout.get(
                        "font_size",
                        header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                    ),
                ),
                22,
            ),
            str(
                body_header_layout.get(
                    "label_color",
                    body_header_layout.get(
                        "color",
                        header_style.get("label_color", attr_layout.get("header_color", default_color)),
                    ),
                )
            ),
            bold=True,
            align=str(body_header_layout.get("label_align", "center")),
        )
        self.create_panel_text(
            attribute_panel,
            body_header_layout.get("value_rect", {"x": 150, "y": 24, "w": 80, "h": 30}),
            body_header_value,
            self._safe_int(
                body_header_layout.get(
                    "value_font_size",
                    body_header_layout.get(
                        "font_size",
                        header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                    ),
                ),
                22,
            ),
            str(
                body_header_layout.get(
                    "value_color",
                    body_header_layout.get(
                        "color",
                        header_style.get("value_color", attr_layout.get("header_color", "#ffffff")),
                    ),
                )
            ),
            bold=True,
            align=str(body_header_layout.get("value_align", "center")),
        )
        self.create_panel_text(
            attribute_panel,
            mind_header_layout.get("label_rect", {"x": 320, "y": 24, "w": 120, "h": 30}),
            mind_header_label,
            self._safe_int(
                mind_header_layout.get(
                    "label_font_size",
                    mind_header_layout.get(
                        "font_size",
                        header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                    ),
                ),
                22,
            ),
            str(
                mind_header_layout.get(
                    "label_color",
                    mind_header_layout.get(
                        "color",
                        header_style.get("label_color", attr_layout.get("header_color", default_color)),
                    ),
                )
            ),
            bold=True,
            align=str(mind_header_layout.get("label_align", "center")),
        )
        self.create_panel_text(
            attribute_panel,
            mind_header_layout.get("value_rect", {"x": 446, "y": 24, "w": 80, "h": 30}),
            mind_header_value,
            self._safe_int(
                mind_header_layout.get(
                    "value_font_size",
                    mind_header_layout.get(
                        "font_size",
                        header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                    ),
                ),
                22,
            ),
            str(
                mind_header_layout.get(
                    "value_color",
                    mind_header_layout.get(
                        "color",
                        header_style.get("value_color", attr_layout.get("header_color", "#ffffff")),
                    ),
                )
            ),
            bold=True,
            align=str(mind_header_layout.get("value_align", "center")),
        )

        body_rows_layout = attr_layout.get("body_rows", {})
        mind_rows_layout = attr_layout.get("mind_rows", {})

        def render_attr_rows(group_name, items, rows_layout):
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id", "")).strip()
                if not item_id:
                    continue
                row_cfg = rows_layout.get(item_id)
                if not isinstance(row_cfg, dict):
                    print(f"[ATTR] missing layout for {group_name}: {item_id}")
                    continue
                label_text = str(item.get("label", item_id))
                cell_ref = item.get("value")
                raw_value_text = resolve_cell_value(cell_ref, "-")
                value_text = self.format_character_display_value(raw_value_text, "int")
                cell_txt = (
                    cell_ref
                    if isinstance(cell_ref, str)
                    else str(cell_ref.get("cell", "-")) if isinstance(cell_ref, dict) else "-"
                )
                print("[ATTR]", group_name, item_id, cell_txt, "->", value_text)
                print("[DISPLAY ATTR]", item_id, raw_value_text, "->", value_text)

                self.create_panel_text(
                    attribute_panel,
                    row_cfg.get("label_rect", {}),
                    label_text,
                    self._safe_int(
                        row_cfg.get(
                            "label_font_size",
                            row_cfg.get(
                                "font_size",
                                rows_style.get("font_size", attr_layout.get("label_font_size", 18)),
                            ),
                        ),
                        18,
                    ),
                    str(
                        row_cfg.get(
                            "label_color",
                            row_cfg.get("color", rows_style.get("label_color", default_color)),
                        )
                    ),
                    bold=False,
                    align=str(row_cfg.get("label_align", "left")),
                )
                self.create_panel_text(
                    attribute_panel,
                    row_cfg.get("value_rect", {}),
                    value_text,
                    self._safe_int(
                        row_cfg.get(
                            "value_font_size",
                            row_cfg.get(
                                "font_size",
                                rows_style.get("font_size", attr_layout.get("value_font_size", value_font_size)),
                            ),
                        ),
                        18,
                    ),
                    str(
                        row_cfg.get(
                            "value_color",
                            row_cfg.get("color", rows_style.get("value_color", "#ffffff")),
                        )
                    ),
                    bold=True,
                    align=str(row_cfg.get("value_align", "center")),
                )

        render_attr_rows("body", body_map.get("items", []), body_rows_layout)
        render_attr_rows("mind", mind_map.get("items", []), mind_rows_layout)

        def render_wellbeing_block():
            wellbeing_cfg = character_screen.get("wellbeing_panel", {})
            if not isinstance(wellbeing_cfg, dict):
                wellbeing_cfg = {}
            if wellbeing_cfg.get("enabled") is False:
                return

            fallback_x = attribute_panel.x()
            fallback_y = attribute_panel.y() + attribute_panel.height() + 8
            fallback_w = attribute_panel.width()
            fallback_h = max(430, min(450, self.content_layer.height() - fallback_y - 8))
            panel_x = self._safe_int(wellbeing_cfg.get("x", fallback_x), fallback_x)
            panel_y = self._safe_int(wellbeing_cfg.get("y", fallback_y), fallback_y)
            panel_w = self._safe_int(wellbeing_cfg.get("w", fallback_w), fallback_w)
            panel_h = self._safe_int(wellbeing_cfg.get("h", fallback_h), fallback_h)
            style_cfg = wellbeing_cfg.get("style", {})
            if not isinstance(style_cfg, dict):
                style_cfg = {}
            background = str(style_cfg.get("background", "rgba(12, 12, 12, 150)"))
            border_color = str(style_cfg.get("border_color", "rgba(242, 210, 139, 95)"))
            border_radius = self._safe_int(style_cfg.get("border_radius", 6), 6)

            panel = QFrame(self.content_layer)
            panel.setGeometry(panel_x, panel_y, panel_w, panel_h)
            panel.setStyleSheet(
                "QFrame {"
                f"background: {background};"
                f"border: 1px solid {border_color};"
                f"border-radius: {border_radius}px;"
                "}"
            )
            panel.show()

            title_cfg = wellbeing_cfg.get("title", {})
            if not isinstance(title_cfg, dict):
                title_cfg = {}
            self.create_panel_text(
                panel,
                title_cfg or {"x": 16, "y": 8, "w": panel_w - 32, "h": 24},
                str(title_cfg.get("text", "Wohlbefinden")),
                self.get_text_font_size(title_cfg, 18),
                self.get_text_color(title_cfg, default_color),
                bold=self.get_text_bold(title_cfg, True),
                align=self.get_text_align(title_cfg, "center"),
            )

            def elide_label(text, max_chars=36):
                value = str(text or "").strip()
                if len(value) <= max_chars:
                    return value
                return value[: max(0, max_chars - 3)] + "..."

            entries = self.get_wellbeing_entries(wellbeing_cfg.get("data", {}))
            default_color_ranges = [
                {"start_row": 23, "end_row": 24, "color": "#7d1f20"},
                {"start_row": 25, "end_row": 28, "color": "#b74335"},
                {"start_row": 29, "end_row": 32, "color": "#d18a26"},
                {"start_row": 33, "end_row": 34, "color": "#8a877f"},
                {"start_row": 35, "end_row": 38, "color": "#8fbf5a"},
                {"start_row": 39, "end_row": 42, "color": "#4f9b45"},
                {"start_row": 43, "end_row": 44, "color": "#1f6f37"},
            ]
            color_ranges = wellbeing_cfg.get("color_ranges", default_color_ranges)
            if not isinstance(color_ranges, list) or not color_ranges:
                color_ranges = default_color_ranges

            def wellbeing_bar_color(row):
                for color_range in color_ranges:
                    if not isinstance(color_range, dict):
                        continue
                    start = self._safe_int(color_range.get("start_row", 0), 0)
                    end = self._safe_int(color_range.get("end_row", start), start)
                    if start <= row <= end:
                        return str(color_range.get("color", "#777777"))
                return "#777777"

            def entry_tooltip(entry, full_label, active):
                marker_cell = str(entry.get("marker_cell", ""))
                label_cell = str(entry.get("label_cell", ""))
                label_for_tooltip = full_label if full_label else "(leer)"
                active_text = "ja" if active else "nein"
                return (
                    f"{marker_cell} / {label_cell}\n"
                    f"{label_cell}: {label_for_tooltip}\n"
                    f"Aktiv: {active_text}"
                )

            def render_vertical_mode():
                vertical_cfg = wellbeing_cfg.get("vertical", {})
                if not isinstance(vertical_cfg, dict):
                    vertical_cfg = {}
                margin_x = self._safe_int(vertical_cfg.get("margin_x", 14), 14)
                row_y_start = self._safe_int(vertical_cfg.get("row_y_start", 38), 38)
                row_h = self._safe_int(vertical_cfg.get("row_h", 17), 17)
                row_gap = self._safe_int(vertical_cfg.get("row_gap", 1), 1)
                color_bar_w = self._safe_int(vertical_cfg.get("color_bar_w", 18), 18)
                grouped_color_bars = bool(vertical_cfg.get("grouped_color_bars", True))
                group_bar_w = self._safe_int(vertical_cfg.get("group_bar_w", color_bar_w), color_bar_w)
                group_bar_radius = self._safe_int(vertical_cfg.get("group_bar_radius", 3), 3)
                row_background_enabled = bool(vertical_cfg.get("row_background_enabled", True))
                x_field_w = self._safe_int(vertical_cfg.get("x_field_w", 28), 28)
                gap = self._safe_int(vertical_cfg.get("gap", 7), 7)
                font_size = self._safe_int(vertical_cfg.get("font_size", 11), 11)
                active_font_size = self._safe_int(vertical_cfg.get("active_font_size", font_size), font_size)
                max_label_chars = self._safe_int(vertical_cfg.get("max_label_chars", 38), 38)
                row_x = margin_x + color_bar_w + gap
                text_x = x_field_w + gap
                text_w = max(80, panel_w - row_x - text_x - margin_x)

                inactive_row_background = str(style_cfg.get("inactive_row_background", "rgba(255, 255, 255, 6)"))
                active_row_background = str(style_cfg.get("active_row_background", "rgba(242, 210, 139, 36)"))
                inactive_border = str(style_cfg.get("inactive_border", "rgba(232, 224, 200, 24)"))
                active_border = str(style_cfg.get("active_border", "rgba(242, 210, 139, 170)"))
                text_color = str(style_cfg.get("text_color", "rgba(232, 224, 200, 175)"))
                active_text_color = str(style_cfg.get("active_text_color", "#ffffff"))
                x_inactive_background = str(style_cfg.get("x_inactive_background", "rgba(0, 0, 0, 85)"))
                x_active_background = str(style_cfg.get("x_active_background", "rgba(242, 210, 139, 72)"))
                x_inactive_border = str(style_cfg.get("x_inactive_border", "rgba(232, 224, 200, 55)"))
                x_active_border = str(style_cfg.get("x_active_border", "rgba(242, 210, 139, 220)"))
                data_cfg = wellbeing_cfg.get("data", {})
                if not isinstance(data_cfg, dict):
                    data_cfg = {}
                data_start_row = self._safe_int(data_cfg.get("start_row", 23), 23)
                data_end_row = self._safe_int(data_cfg.get("end_row", 44), 44)
                if data_end_row < data_start_row:
                    data_start_row, data_end_row = data_end_row, data_start_row

                if grouped_color_bars:
                    for color_range in color_ranges:
                        if not isinstance(color_range, dict):
                            continue
                        start_row = self._safe_int(color_range.get("start_row", data_start_row), data_start_row)
                        end_row = self._safe_int(color_range.get("end_row", start_row), start_row)
                        start_row = max(data_start_row, start_row)
                        end_row = min(data_end_row, end_row)
                        if end_row < start_row:
                            continue
                        start_index = start_row - data_start_row
                        end_index = end_row - data_start_row
                        group_y = row_y_start + start_index * (row_h + row_gap)
                        group_h = (end_index - start_index + 1) * row_h + (end_index - start_index) * row_gap
                        group_bar = QLabel(panel)
                        group_bar.setGeometry(margin_x, group_y, group_bar_w, max(1, group_h))
                        group_bar.setStyleSheet(
                            "QLabel {"
                            f"background: {str(color_range.get('color', '#777777'))};"
                            "border: none;"
                            f"border-radius: {group_bar_radius}px;"
                            "}"
                        )
                        group_bar.show()

                for index, entry in enumerate(entries):
                    y = row_y_start + index * (row_h + row_gap)
                    active = bool(entry.get("active"))
                    full_label = str(entry.get("label", "") or "")
                    tooltip = entry_tooltip(entry, full_label, active)

                    row_frame = QFrame(panel)
                    row_frame.setGeometry(row_x, y, panel_w - row_x - margin_x, row_h)
                    row_frame.setStyleSheet(
                        "QFrame {"
                        f"background: {active_row_background if active else inactive_row_background if row_background_enabled else 'transparent'};"
                        f"border: 1px solid {active_border if active else inactive_border};"
                        "border-radius: 3px;"
                        "}"
                    )
                    row_frame.show()

                    if not grouped_color_bars:
                        color_bar = QLabel(panel)
                        color_bar.setGeometry(margin_x, y + 2, color_bar_w, max(1, row_h - 4))
                        color_bar.setStyleSheet(
                            "QLabel {"
                            f"background: {wellbeing_bar_color(int(entry.get('row', 0)))};"
                            "border: none;"
                            f"border-radius: {group_bar_radius}px;"
                            "}"
                        )
                        color_bar.setToolTip(tooltip)
                        color_bar.show()

                    x_field = QLabel(row_frame)
                    x_field.setGeometry(0, 1, x_field_w, max(1, row_h - 2))
                    x_field.setText("X" if active else "")
                    x_field.setAlignment(Qt.AlignCenter)
                    x_field.setStyleSheet(
                        "QLabel {"
                        f"background: {x_active_background if active else x_inactive_background};"
                        f"border: 1px solid {x_active_border if active else x_inactive_border};"
                        "border-radius: 2px;"
                        f"color: {active_text_color if active else text_color};"
                        "font-size: 10px;"
                        "font-weight: 700;"
                        "}"
                    )
                    x_field.setToolTip(tooltip)
                    x_field.show()

                    text_label = QLabel(row_frame)
                    text_label.setGeometry(text_x, 0, text_w, row_h)
                    text_label.setText(elide_label(full_label, max_label_chars))
                    text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    text_label.setStyleSheet(
                        "QLabel {"
                        "background: transparent;"
                        "border: none;"
                        f"color: {active_text_color if active else text_color};"
                        f"font-size: {active_font_size if active else font_size}px;"
                        f"font-weight: {'700' if active else '500'};"
                        "}"
                    )
                    text_label.setToolTip(tooltip)
                    text_label.show()

            render_vertical_mode()

            panel.raise_()

        render_wellbeing_block()

        perks_layout = text_layout.get("perk_panel", text_layout.get("perks", {}))
        disadv_layout = text_layout.get("disadvantages", perks_layout.get("disadvantage_table", {}))
        perks_map = data_map.get("perks", {})
        disadv_map = data_map.get("disadvantages", {})
        self.current_perks = []
        self.current_disadvantages = []

        def elide_fixed_text(text, max_chars):
            value = str(text)
            if len(value) <= max_chars:
                return value
            return value[: max(0, max_chars - 3)] + "..."

        def render_side_table(parent, table_cfg, map_cfg, collection):
            header_y = self._safe_int(table_cfg.get("header_y", 0), 0)
            start_y = self._safe_int(table_cfg.get("start_y", header_y + 24), header_y + 24)
            row_h = self._safe_int(table_cfg.get("row_h", 24), 24)
            max_rows = self._safe_int(table_cfg.get("max_rows", 8), 8)
            header_font_size = self._safe_int(table_cfg.get("header_font_size", 15), 15)
            row_font_size = self._safe_int(table_cfg.get("row_font_size", table_cfg.get("font_size", 14)), 14)
            header_color = str(table_cfg.get("header_color", table_cfg.get("color", default_color)))
            name_color = str(table_cfg.get("name_color", table_cfg.get("row_color", "#f2d28b")))
            bp_color = str(table_cfg.get("bp_color", table_cfg.get("row_color", "#d6b35a")))
            effect_color = str(table_cfg.get("effect_color", table_cfg.get("row_color", "#ffffff")))
            name_x = self._safe_int(table_cfg.get("name_x", 0), 0)
            name_w = self._safe_int(table_cfg.get("name_w", 130), 130)
            bp_x = self._safe_int(table_cfg.get("bp_x", name_x + name_w + 8), name_x + name_w + 8)
            bp_w = self._safe_int(table_cfg.get("bp_w", 40), 40)
            effect_x = self._safe_int(table_cfg.get("effect_x", bp_x + bp_w + 8), bp_x + bp_w + 8)
            effect_w = self._safe_int(table_cfg.get("effect_w", 180), 180)

            self.create_panel_text(
                parent,
                {"x": name_x, "y": header_y, "w": name_w, "h": row_h},
                str(table_cfg.get("name_header", "Name")),
                header_font_size,
                header_color,
                bold=True,
            )
            self.create_panel_text(
                parent,
                {"x": bp_x, "y": header_y, "w": bp_w, "h": row_h},
                str(table_cfg.get("bp_header", "BP")),
                header_font_size,
                header_color,
                bold=True,
                align="center",
            )
            self.create_panel_text(
                parent,
                {"x": effect_x, "y": header_y, "w": effect_w, "h": row_h},
                str(table_cfg.get("effect_header", "Effekt")),
                header_font_size,
                header_color,
                bold=True,
            )

            start_row = self._safe_int(map_cfg.get("start_row", 0), 0)
            end_row = self._safe_int(map_cfg.get("end_row", -1), -1)
            if start_row <= 0 or end_row < start_row:
                return

            sheet_name = str(map_cfg.get("sheet", default_sheet))
            name_col = str(map_cfg.get("name_col", "A"))
            bp_col = str(map_cfg.get("bp_col", "B"))
            effect_col = str(map_cfg.get("effect_col", "C"))
            name_max_chars = self._safe_int(table_cfg.get("name_max_chars", 22), 22)
            effect_max_chars = self._safe_int(table_cfg.get("effect_max_chars", 34), 34)

            rendered = 0
            for row in range(start_row, end_row + 1):
                if rendered >= max_rows:
                    break
                name = self.get_cache_display_value(sheet_name, f"{name_col}{row}", "")
                raw_bp = self.get_cache_display_value(sheet_name, f"{bp_col}{row}", "")
                effect = self.get_cache_display_value(sheet_name, f"{effect_col}{row}", "")
                if not (name or raw_bp or effect):
                    continue

                bp = self.format_character_display_value(raw_bp, "int") if raw_bp else ""
                if name and name != "-":
                    collection.append(name)
                y = start_y + rendered * row_h
                rendered += 1

                self.create_panel_text(
                    parent,
                    {"x": name_x, "y": y, "w": name_w, "h": row_h},
                    elide_fixed_text(name, name_max_chars) if name else "",
                    row_font_size,
                    name_color,
                )
                self.create_panel_text(
                    parent,
                    {"x": bp_x, "y": y, "w": bp_w, "h": row_h},
                    bp,
                    row_font_size,
                    bp_color,
                    align="center",
                )
                self.create_panel_text(
                    parent,
                    {"x": effect_x, "y": y, "w": effect_w, "h": row_h},
                    elide_fixed_text(effect, effect_max_chars) if effect else "",
                    row_font_size,
                    effect_color,
                )

        if isinstance(perks_layout, dict) and "perk_table" in perks_layout and "disadvantage_table" in perks_layout:
            left_title = perks_layout.get("left_title", {})
            right_title = perks_layout.get("right_title", {})
            self.create_panel_text(
                perk_panel,
                left_title.get("rect", left_title if isinstance(left_title, dict) else {}),
                str(left_title.get("text", "Perks")) if isinstance(left_title, dict) else "Perks",
                self.get_text_font_size(left_title, 22),
                self.get_text_color(left_title, default_color),
                bold=self.get_text_bold(left_title, True),
                align=self.get_text_align(left_title, "center"),
            )
            self.create_panel_text(
                perk_panel,
                right_title.get("rect", right_title if isinstance(right_title, dict) else {}),
                str(right_title.get("text", "Nachteile")) if isinstance(right_title, dict) else "Nachteile",
                self.get_text_font_size(right_title, 22),
                self.get_text_color(right_title, default_color),
                bold=self.get_text_bold(right_title, True),
                align=self.get_text_align(right_title, "center"),
            )
            render_side_table(
                perk_panel,
                perks_layout.get("perk_table", {}),
                perks_map if isinstance(perks_map, dict) else {},
                self.current_perks,
            )
            render_side_table(
                perk_panel,
                perks_layout.get("disadvantage_table", {}),
                disadv_map if isinstance(disadv_map, dict) else {},
                self.current_disadvantages,
            )
            print("[PERKS]", self.current_perks)
            print("[DISADVANTAGES]", self.current_disadvantages)
            return

        def render_table_block(parent, table_cfg, map_cfg, title_cfg, section_title, start_y_default):
            title_rect = title_cfg.get("rect", {"x": 24, "y": start_y_default, "w": 280, "h": 30})
            self.create_panel_text(
                parent,
                title_rect,
                str(title_cfg.get("text", section_title)),
                self.get_text_font_size(title_cfg, 22),
                self.get_text_color(title_cfg, default_color),
                bold=self.get_text_bold(title_cfg, True),
            )

            header_cfg = table_cfg.get("header", {})
            header_y = self._safe_int(header_cfg.get("y", self._safe_int(title_rect.get("y", start_y_default), start_y_default) + 34), start_y_default + 34)
            name_x = self._safe_int(table_cfg.get("name_x", 24), 24)
            name_w = self._safe_int(table_cfg.get("name_w", 200), 200)
            bp_x = self._safe_int(table_cfg.get("bp_x", 250), 250)
            bp_w = self._safe_int(table_cfg.get("bp_w", 60), 60)
            effect_x = self._safe_int(table_cfg.get("effect_x", 330), 330)
            effect_w = self._safe_int(table_cfg.get("effect_w", 280), 280)
            row_h = self._safe_int(table_cfg.get("row_h", 28), 28)
            max_rows = self._safe_int(table_cfg.get("max_rows", 8), 8)
            font_size = self._safe_int(table_cfg.get("font_size", 16), 16)
            header_font_size = self._safe_int(
                table_cfg.get("header_font_size", header_cfg.get("font_size", font_size)),
                font_size,
            )
            header_color = str(
                table_cfg.get("header_color", header_cfg.get("color", default_color))
            )
            row_color = str(table_cfg.get("row_color", table_cfg.get("color", "#ffffff")))

            self.create_panel_text(
                parent,
                {"x": name_x, "y": header_y, "w": name_w, "h": row_h},
                str(header_cfg.get("name", "Name")),
                header_font_size,
                header_color,
                bold=True,
            )
            self.create_panel_text(
                parent,
                {"x": bp_x, "y": header_y, "w": bp_w, "h": row_h},
                str(header_cfg.get("bp", "BP")),
                header_font_size,
                header_color,
                bold=True,
            )
            self.create_panel_text(
                parent,
                {"x": effect_x, "y": header_y, "w": effect_w, "h": row_h},
                str(header_cfg.get("effect", "Effekt")),
                header_font_size,
                header_color,
                bold=True,
            )

            start_row = self._safe_int(map_cfg.get("start_row", 0), 0)
            end_row = self._safe_int(map_cfg.get("end_row", -1), -1)
            if start_row <= 0 or end_row < start_row:
                return header_y + row_h
            sheet_name = str(map_cfg.get("sheet", default_sheet))
            name_col = str(map_cfg.get("name_col", "A"))
            bp_col = str(map_cfg.get("bp_col", "B"))
            effect_col = str(map_cfg.get("effect_col", "C"))
            row_start_y = self._safe_int(table_cfg.get("start_y", header_y + row_h + 2), header_y + row_h + 2)

            rendered = 0
            for row in range(start_row, end_row + 1):
                if rendered >= max_rows:
                    break
                n = self.get_cache_display_value(sheet_name, f"{name_col}{row}", "")
                raw_b = self.get_cache_display_value(sheet_name, f"{bp_col}{row}", "")
                b = self.format_character_display_value(raw_b, "int") if raw_b else ""
                e = self.get_cache_display_value(sheet_name, f"{effect_col}{row}", "")
                if not (n or b or e):
                    continue
                y = row_start_y + rendered * row_h
                rendered += 1
                self.create_panel_text(
                    parent,
                    {"x": name_x, "y": y, "w": name_w, "h": row_h},
                    n or "-",
                    font_size,
                    row_color,
                    align="left",
                )
                self.create_panel_text(
                    parent,
                    {"x": bp_x, "y": y, "w": bp_w, "h": row_h},
                    b or "-",
                    font_size,
                    row_color,
                    align="left",
                )
                effect_text = (e or "-")
                if len(effect_text) > 140:
                    effect_text = effect_text[:137] + "..."
                self.create_panel_text(
                    parent,
                    {"x": effect_x, "y": y, "w": effect_w, "h": row_h},
                    effect_text,
                    font_size,
                    row_color,
                    align="left",
                )
            return row_start_y + rendered * row_h

        perks_title_cfg = perks_layout.get("title", {"text": "Perks", "rect": {"x": 24, "y": 22, "w": 200, "h": 30}})
        perks_table_cfg = perks_layout.get("table", perks_layout)
        end_y = render_table_block(perk_panel, perks_table_cfg, perks_map, perks_title_cfg, "Perks", 22)

        dis_title_cfg = perks_layout.get(
            "disadvantage_title",
            {"text": "Nachteile", "rect": {"x": 24, "y": end_y + 20, "w": 220, "h": 30}},
        )
        dis_table_cfg = perks_layout.get("disadvantage_table", disadv_layout if isinstance(disadv_layout, dict) else {})
        if isinstance(dis_title_cfg, dict) and isinstance(dis_title_cfg.get("rect"), dict):
            dis_title_cfg["rect"]["y"] = self._safe_int(dis_title_cfg["rect"].get("y", end_y + 20), end_y + 20)
        render_table_block(perk_panel, dis_table_cfg, disadv_map, dis_title_cfg, "Nachteile", end_y + 20)

    def render_character_front(self):
        if self.content_layer is None:
            return

        cfg = self.main_ui_layout_config.get("character_front", {})
        default_text_style = self.theme_style.get("default_text", {})
        default_color = str(default_text_style.get("color", "#e8e0c8"))
        title_theme_style = self.theme_style.get("title", {})

        panel_x = int(cfg.get("x", 80))
        panel_y = int(cfg.get("y", 180))
        panel_w = int(cfg.get("w", 420))
        panel_h = int(cfg.get("h", 520))
        panel = QFrame(self.content_layer)
        panel.setGeometry(panel_x, panel_y, panel_w, panel_h)
        panel_bg = str(cfg.get("panel_background", "rgba(8, 8, 10, 178)"))
        panel_border_color = str(cfg.get("panel_border_color", "rgba(240, 210, 140, 96)"))
        panel_border_width = int(cfg.get("panel_border_width", 1))
        panel_radius = int(cfg.get("panel_border_radius", 10))
        panel.setStyleSheet(
            f"background: {panel_bg};"
            f"border: {panel_border_width}px solid {panel_border_color};"
            f"border-radius: {panel_radius}px;"
        )
        panel.show()

        sheet_name = "Charakterbogen"
        character_name = self._get_character_front_value(
            sheet_name, "G1", "Unbekannter Charakter"
        )
        race = self._get_character_front_value(sheet_name, "G3")
        size = self._get_character_front_value(sheet_name, "G5")
        weight = self._get_character_front_value(sheet_name, "G7")
        hp = self._get_character_front_value(sheet_name, "F10")
        mp = self._get_character_front_value(sheet_name, "F13")
        exp = self._get_character_front_value(sheet_name, "F16")

        title_cfg = cfg.get("title", {})
        title_label = QLabel(panel)
        title_label.setGeometry(
            int(title_cfg.get("x", 30)),
            int(title_cfg.get("y", 25)),
            panel_w - int(title_cfg.get("x", 30)) - 20,
            50,
        )
        title_label.setText(character_name)
        title_label.setStyleSheet(
            "background: transparent; "
            f"color: {str(title_cfg.get('color', title_theme_style.get('color', default_color)))}; "
            f"font-size: {int(title_cfg.get('font_size', 28))}px; font-weight: 700;"
        )
        title_label.show()

        info_label_cfg = cfg.get("info_labels", {})
        info_value_cfg = cfg.get("info_values", {})
        info_labels = ["Rasse", "Größe", "Gewicht"]
        info_values = [race, size, weight]
        info_label_x = int(info_label_cfg.get("x", 30))
        info_value_x = int(info_value_cfg.get("x", 220))
        info_start_y = int(info_label_cfg.get("start_y", 110))
        info_row_gap = int(info_label_cfg.get("row_gap", 36))

        for i, label_text in enumerate(info_labels):
            y = info_start_y + (i * info_row_gap)
            label = QLabel(panel)
            label.setGeometry(info_label_x, y, 170, 30)
            label.setText(label_text)
            label.setStyleSheet(
                "background: transparent; "
                f"color: {str(info_label_cfg.get('color', default_color))}; "
                f"font-size: {int(info_label_cfg.get('font_size', 18))}px; font-weight: 500;"
            )
            label.show()

            value = QLabel(panel)
            value.setGeometry(info_value_x, y, panel_w - info_value_x - 20, 30)
            value.setText(info_values[i])
            value.setStyleSheet(
                "background: transparent; "
                f"color: {str(info_value_cfg.get('color', '#ffffff'))}; "
                f"font-size: {int(info_value_cfg.get('font_size', 18))}px; font-weight: 600;"
            )
            value.show()

        stats_label_cfg = cfg.get("stats_labels", {})
        stats_value_cfg = cfg.get("stats_values", {})
        stats_labels = ["HP", "MP", "EXP"]
        stats_values = [hp, mp, exp]
        stats_label_x = int(stats_label_cfg.get("x", 30))
        stats_value_x = int(stats_value_cfg.get("x", 260))
        stats_start_y = int(stats_label_cfg.get("start_y", 260))
        stats_row_gap = int(stats_label_cfg.get("row_gap", 58))

        hp_style = cfg.get("hp_text", {})
        mp_style = cfg.get("mp_text", {})
        exp_style = cfg.get("exp_text", {})
        for i, label_text in enumerate(stats_labels):
            y = stats_start_y + (i * stats_row_gap)
            if label_text == "HP":
                label_font = int(hp_style.get("label_font_size", stats_label_cfg.get("font_size", 18)))
                value_font = int(hp_style.get("value_font_size", stats_value_cfg.get("font_size", 26)))
            elif label_text == "MP":
                label_font = int(mp_style.get("label_font_size", stats_label_cfg.get("font_size", 18)))
                value_font = int(mp_style.get("value_font_size", stats_value_cfg.get("font_size", 26)))
            else:
                label_font = int(exp_style.get("label_font_size", stats_label_cfg.get("font_size", 18)))
                value_font = int(exp_style.get("value_font_size", stats_value_cfg.get("font_size", 26)))
            label = QLabel(panel)
            label.setGeometry(stats_label_x, y, 170, 36)
            label.setText(label_text)
            label.setStyleSheet(
                "background: transparent; "
                f"color: {str(stats_label_cfg.get('color', default_color))}; "
                f"font-size: {label_font}px; font-weight: 600;"
            )
            label.show()

            value = QLabel(panel)
            value_y_offset = int(stats_value_cfg.get("y_offset", 8))
            value.setGeometry(
                stats_value_x,
                y - value_y_offset,
                panel_w - stats_value_x - 20,
                max(48, value_font + 16),
            )
            value.setText(stats_values[i])
            value.setStyleSheet(
                "background: transparent; "
                f"color: {str(stats_value_cfg.get('color', '#ffffff'))}; "
                f"font-size: {value_font}px; font-weight: 700;"
            )
            value.show()

        hp_bar_cfg = cfg.get("hp_bar", {})
        if bool(hp_bar_cfg.get("enabled", True)):
            hp_bar = QFrame(panel)
            hp_bar.setGeometry(
                int(hp_bar_cfg.get("x", 30)),
                int(hp_bar_cfg.get("y", 320)),
                int(hp_bar_cfg.get("w", 260)),
                int(hp_bar_cfg.get("h", 12)),
            )
            hp_bar.setStyleSheet(
                "background-color: rgba(20, 20, 20, 180); border: 1px solid rgba(0, 0, 0, 120);"
            )
            hp_fill = QFrame(hp_bar)
            hp_fill.setGeometry(0, 0, hp_bar.width(), hp_bar.height())
            hp_fill.setStyleSheet(f"background-color: {str(hp_bar_cfg.get('color', '#cc4444'))};")
            hp_bar.show()

        mp_bar_cfg = cfg.get("mp_bar", {})
        if bool(mp_bar_cfg.get("enabled", True)):
            mp_bar = QFrame(panel)
            mp_bar.setGeometry(
                int(mp_bar_cfg.get("x", 30)),
                int(mp_bar_cfg.get("y", 378)),
                int(mp_bar_cfg.get("w", 260)),
                int(mp_bar_cfg.get("h", 12)),
            )
            mp_bar.setStyleSheet(
                "background-color: rgba(20, 20, 20, 180); border: 1px solid rgba(0, 0, 0, 120);"
            )
            mp_fill = QFrame(mp_bar)
            mp_fill.setGeometry(0, 0, mp_bar.width(), mp_bar.height())
            mp_fill.setStyleSheet(f"background-color: {str(mp_bar_cfg.get('color', '#4477cc'))};")
            mp_bar.show()

    def update_settings_checkbox_icon(self):
        if self.settings_checkbox_icon_label is None:
            return
        asset = (
            self._settings_checkbox_asset_true
            if self.settings_debug_on_start
            else self._settings_checkbox_asset_false
        )
        pixmap = self.load_ui_pixmap(asset)
        if pixmap is not None:
            w = self.settings_checkbox_icon_label.width()
            h = self.settings_checkbox_icon_label.height()
            self.settings_checkbox_icon_label.setPixmap(
                pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            )
        else:
            fallback = "☑" if self.settings_debug_on_start else "☐"
            self.settings_checkbox_icon_label.setText(fallback)
            self.settings_checkbox_icon_label.setStyleSheet(
                "background: transparent; color: #ffffff; font-size: 28px;"
            )

    def on_settings_debug_start_toggled(self):
        self.settings_debug_on_start = not self.settings_debug_on_start
        self.update_settings_checkbox_icon()
        print("[SETTINGS] debug on start:", self.settings_debug_on_start)

    def refresh_character_cache_list(self):
        if self.settings_character_combo is None:
            return
        active_character_name = self.loader.current_character_name
        self.settings_character_combo.blockSignals(True)
        try:
            self.settings_character_combo.clear()
            caches = self.loader.list_character_caches()
            active_cache = self.loader.active_cache_path
            active_index = -1
            for i, entry in enumerate(caches):
                display_text = f"{entry['name']}  ({entry['file']})"
                self.settings_character_combo.addItem(display_text, entry["path"])
                if entry["path"] == active_cache:
                    active_index = i
                    active_character_name = entry["name"]
                    self.loader.current_character_name = active_character_name
            if active_index >= 0:
                self.settings_character_combo.setCurrentIndex(active_index)
        finally:
            self.settings_character_combo.blockSignals(False)
        if self.settings_character_active_label is not None:
            self.settings_character_active_label.setText(active_character_name)

    def on_settings_load_character_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Charakter-Datei auswählen",
            "",
            "Charakter-Dateien (*.xlsx *.xlsm *.ods);;Excel Dateien (*.xlsx *.xlsm);;ODS Dateien (*.ods);;Alle Dateien (*)",
        )

        if not file_path:
            return

        print("[CHARACTER IMPORT] selected:", file_path)
        if hasattr(self.loader, "has_unsaved_changes") and self.loader.has_unsaved_changes():
            print("[CHARACTER WARNING] unsaved changes before switching character")
        try:
            self.loader.load_file(file_path)
        except ValueError as exc:
            print("[LOAD ERROR]", str(exc))
            QMessageBox.warning(
                self,
                "Dateiformat nicht unterstützt",
                str(exc),
            )
            return

        self.reset_character_runtime_state()
        self.create_tabs_from_cache()
        self.refresh_character_cache_list()
        if self.settings_character_active_label is not None:
            self.settings_character_active_label.setText(self.loader.current_character_name)
        print("[CHARACTER IMPORT] loaded:", self.loader.current_character_name)
        self.show_main_section("character")

    def load_selected_character_cache(self):
        if self.settings_character_combo is None:
            return
        self.on_settings_character_selection_changed(self.settings_character_combo.currentIndex())

    def on_settings_character_selection_changed(self, index):
        if self.settings_character_combo is None:
            return
        if index < 0:
            return
        cache_path = self.settings_character_combo.currentData()
        if not isinstance(cache_path, str) or not cache_path:
            return
        active_cache_path = self.loader.active_cache_path
        if active_cache_path and Path(cache_path) == Path(active_cache_path):
            return
        if hasattr(self.loader, "has_unsaved_changes") and self.loader.has_unsaved_changes():
            print("[CHARACTER WARNING] unsaved changes before switching character")
        ok = self.loader.load_character_cache(cache_path)
        if not ok:
            QMessageBox.warning(self, "Charakter laden", "Charakter-Cache konnte nicht geladen werden.")
            return
        self.reset_character_runtime_state()
        if self.settings_character_active_label is not None:
            self.settings_character_active_label.setText(self.loader.current_character_name)
        self.create_tabs_from_cache()
        if self.current_main_section == "character":
            self.show_main_section("character")
        elif self.current_main_section in ("skills", "fertigkeiten"):
            self.show_main_section("skills")
        elif self.current_main_section == "inventory":
            self.show_main_section("inventory")
        print("[CHARACTER CACHE] loaded:", cache_path)

    def on_settings_refresh_character_list_clicked(self):
        self.refresh_character_cache_list()
        print("[CHARACTER] cache list refreshed")

    def reset_character_runtime_state(self):
        if hasattr(self, "tabs") and self.tabs is not None:
            self.tabs.clear()
        if hasattr(self, "formula_table") and self.formula_table is not None:
            self.formula_table.setRowCount(0)
        if hasattr(self, "formula_editor") and self.formula_editor is not None:
            self.formula_editor.setPlainText("")
        if hasattr(self, "cell_label") and self.cell_label is not None:
            self.cell_label.setText('Zelle: <span style="color:#666666">-</span>')
        if hasattr(self, "references_label") and self.references_label is not None:
            self.references_label.setText("Referenzen: -")
        if hasattr(self, "result_label") and self.result_label is not None:
            self.result_label.setText("Ergebnis: -")

        self.sheet_tabs = {}
        self.formula_changes = {}
        self.formula_data = {}
        self.current_formula_cell = None
        self.highlighted_borders = {}
        self.current_highlight_table = None
        self.current_active_grid_cell = None
        self.current_reference_color_map = {}
        self.current_indirect_references = []
        self.skill_source_infos = {}
        self.skill_sheet_mapping_config = None
        print("[CHARACTER RESET] runtime state cleared")

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
            inventory_category_id = obj.property("inventory_category_id")
            if isinstance(inventory_category_id, str) and inventory_category_id.startswith("inventory_"):
                if event.type() == QEvent.MouseButtonDblClick:
                    self.rename_inventory_category(inventory_category_id)
                    return True
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
            self,
            "Tabelle auswählen",
            "",
            "Tabellen (*.xlsx *.xlsm *.ods);;Excel Dateien (*.xlsx *.xlsm);;OpenDocument Tabellen (*.ods);;Alle Dateien (*)",
        )

        if not file_path:
            return

        self.tabs.clear()
        self.clear_reference_highlights()
        self.sheet_tabs = {}

        if hasattr(self.loader, "has_unsaved_changes") and self.loader.has_unsaved_changes():
            print("[CHARACTER WARNING] unsaved changes before switching character")
        try:
            self.loader.load_file(file_path)
        except ValueError as exc:
            print("[LOAD ERROR]", str(exc))
            QMessageBox.warning(
                self,
                "Dateiformat nicht unterstützt",
                str(exc),
            )
            return
        self.reset_character_runtime_state()
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
                text = self.format_debug_grid_value(value)
                item = QTableWidgetItem(text)
                table.setItem(i, j, item)

        tab_layout.addWidget(table)
        self.tabs.addTab(tab, sheet_name)

    def format_debug_grid_value(self, value):
        if value is None:
            return ""
        text = str(value)
        lowered = text.lower()
        if "openpyxl.worksheet.formula.arrayformula" in lowered or "arrayformula object" in lowered:
            return "[ArrayFormula: unsupported]"
        return text

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
