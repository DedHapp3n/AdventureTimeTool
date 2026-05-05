from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit, QStyledItemDelegate, QFrame, QDialog, QMessageBox, QComboBox
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
            self.loader.load_cache_from_json()
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
        self.settings_character_combo.clear()
        caches = self.loader.list_character_caches()
        active_cache = self.loader.active_cache_path
        active_index = -1
        for i, entry in enumerate(caches):
            display_text = f"{entry['name']}  ({entry['file']})"
            self.settings_character_combo.addItem(display_text, entry["path"])
            if entry["path"] == active_cache:
                active_index = i
        if active_index >= 0:
            self.settings_character_combo.setCurrentIndex(active_index)

    def on_settings_load_character_clicked(self):
        if self.settings_character_combo is None:
            return
        cache_path = self.settings_character_combo.currentData()
        if not isinstance(cache_path, str) or not cache_path:
            QMessageBox.warning(self, "Charakter laden", "Bitte zuerst einen Charakter auswählen.")
            return
        ok = self.loader.load_character_cache(cache_path)
        if not ok:
            QMessageBox.warning(self, "Charakter laden", "Charakter-Cache konnte nicht geladen werden.")
            return
        if self.settings_character_active_label is not None:
            self.settings_character_active_label.setText(self.loader.current_character_name)
        self.create_tabs_from_cache()
        print("[CHARACTER] loaded:", cache_path)

    def on_settings_refresh_character_list_clicked(self):
        self.refresh_character_cache_list()
        print("[CHARACTER] cache list refreshed")

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
            self, "Excel auswählen", "", "Excel Dateien (*.xlsx *.xlsm);;Alle Dateien (*)"
        )

        if not file_path:
            return

        self.tabs.clear()
        self.clear_reference_highlights()
        self.sheet_tabs = {}

        try:
            self.loader.load_file(file_path)
        except ValueError as exc:
            print("[LOAD ERROR]", str(exc))
            message_text = str(exc)
            if "ODS wird aktuell nicht unterstützt" in message_text:
                message_text = (
                    "ODS wird aktuell nicht unterstützt. Bitte die Datei in LibreOffice "
                    "oder Excel als .xlsx speichern."
                )
            QMessageBox.warning(
                self,
                "Dateiformat nicht unterstützt",
                message_text,
            )
            return
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
