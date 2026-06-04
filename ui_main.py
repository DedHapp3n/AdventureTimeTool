from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QSplitter,
    QLabel, QTextEdit, QStyledItemDelegate, QFrame, QDialog, QMessageBox, QComboBox, QMenu, QInputDialog, QGroupBox,
    QSpinBox, QRadioButton, QButtonGroup, QCheckBox, QGridLayout, QLineEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, QEvent, QRect, QPoint
from PySide6.QtGui import QColor, QPen, QPixmap, QIcon, QTextDocument, QFont, QFontMetrics, QBrush, QPainter, QPolygon, QLinearGradient
import re
import os
import json
import math
import html
from datetime import datetime, timezone
from pathlib import Path

from app_paths import (
    app_base_dir,
    ensure_runtime_defaults,
    load_settings,
    resource_path,
    save_settings,
)
from app_logger import log_debug, log_error, log_info, log_warning, set_debug_settings
from data_loader import DataLoader
from formula_parser import FormulaParser
from ui_tabs.sheet_tab import SheetTab
from calculation_center import CalculationCenterDialog
from ui_dialogs.resource_dialog import open_resource_dialog
from ui_dialogs.roll20_dialog import open_roll20_dialog
from ui_sections.equipment_section import render_equipment_section
from ui_sections import inventory_section
from ui_sections.magic_section import render_magic_section
from ui_sections.notes_section import notes_debug_enabled, render_notes_section
from ui_sections import settings_section
from ui_sections import skills_section
from ui_sections import character_section
from ui_sections import browser_section


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

        ensure_runtime_defaults()
        self.setWindowTitle("Adventure Time Tool")
        self.settings, _ = load_settings()
        set_debug_settings(self.settings.get("debug", {}) if isinstance(self.settings, dict) else {})
        window_settings = self.settings.get("window", {}) if isinstance(self.settings, dict) else {}
        self.resize(int(window_settings.get("width", 1500)), int(window_settings.get("height", 900)))
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)

        self.loader = DataLoader()
        self.parser = FormulaParser()
        self.base_dir = app_base_dir()
        self.assets_dir = resource_path("assets")
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
        self._skills_se_loading = False
        self.current_inventory_category = "inventory_01"
        self.skill_source_infos = {}
        self.skills_debug_sources = False
        self.skill_sheet_mapping_config = None
        self.settings_debug_on_start = False
        self.nav_buttons = {}
        self.debug_dialog = None
        self.content_layer = None
        self.settings_theme_label = None
        self.settings_checkbox_icon_label = None
        self.settings_checkbox_text_label = None
        self._settings_checkbox_asset_true = "icons/checkmark_true.png"
        self._settings_checkbox_asset_false = "icons/checkmark_false.png"
        self.settings_character_active_label = None
        self.settings_character_combo = None
        self.calculation_center_dialog = None
        self._inventory_loading = False
        self._inventory_table_bindings = {}
        self._inventory_money_fields = {}
        self._inventory_money_delta_fields = {}
        self.equipment_analysis = {}
        self.equipment_layout_config = {}
        self._equipment_table_bindings = {}
        self._equipment_rendering = False
        self._character_rendering = False
        self._recalc_in_progress = False
        self._character_edit_cfg = {}
        self.character_paradigm_analysis = {}
        self._notes_loading_text = False
        self.magic_analysis = {}
        self.magic_layout_config = {}
        self._magic_table_bindings = {}
        self._magic_rendering = False
        self._browser_container = None
        self._browser_web_view = None
        self._browser_url_edit = None
        self._browser_initialized = False
        self._browser_last_url = ""
        self._browser_popup_pages = []
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
        fallback = self.assets_dir / "themes" / "diablo" / "ui" / filename
        if fallback.exists():
            return fallback
        log_warning("theme", f"missing asset: {primary}")
        return primary

    def load_ui_pixmap(self, filename):
        if not filename:
            return None
        asset_path = self.resolve_ui_asset_path(filename)
        if asset_path is not None and asset_path.exists():
            pixmap = QPixmap(str(asset_path))
            log_debug("theme", f"pixmap null: {pixmap.isNull()} {pixmap.size()}")
            if not pixmap.isNull():
                return pixmap
        return None

    def create_d20_nav_pixmap(self, width, height, active=False, hover=False):
        pixmap = QPixmap(max(1, width), max(1, height))
        pixmap.fill(Qt.transparent)

        nav_style = self.theme_style.get("nav_button", {})
        color_text = str(nav_style.get("active_color" if active else "inactive_color", "#f2d28b"))
        if hover:
            color_text = str(nav_style.get("hover_color", "#ffffff"))
        edge_color = QColor(color_text)
        shadow_color = QColor(str(nav_style.get("shadow_color", "#000000")))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pad = max(3, min(width, height) // 9)
        cx = width // 2
        top = pad
        bottom = height - pad
        left = pad
        right = width - pad
        mid_y = height // 2
        upper_y = int(height * 0.32)
        lower_y = int(height * 0.69)

        outline = QPolygon([
            QPoint(cx, top),
            QPoint(right, upper_y),
            QPoint(int(width * 0.82), lower_y),
            QPoint(cx, bottom),
            QPoint(int(width * 0.18), lower_y),
            QPoint(left, upper_y),
        ])
        gradient = QLinearGradient(0, top, 0, bottom)
        gradient.setColorAt(0.0, QColor(80, 68, 50, 235))
        gradient.setColorAt(0.45, QColor(24, 22, 21, 235))
        gradient.setColorAt(1.0, QColor(8, 7, 7, 245))

        painter.setPen(QPen(shadow_color, 3))
        painter.setBrush(gradient)
        painter.drawPolygon(outline)
        painter.setPen(QPen(edge_color, 2))
        painter.drawPolygon(outline)

        painter.setPen(QPen(QColor(edge_color.red(), edge_color.green(), edge_color.blue(), 150), 1))
        painter.drawLine(cx, top, cx, bottom)
        painter.drawLine(left, upper_y, right, upper_y)
        painter.drawLine(left, upper_y, cx, bottom)
        painter.drawLine(right, upper_y, cx, bottom)
        painter.drawLine(int(width * 0.18), lower_y, int(width * 0.82), lower_y)
        painter.drawLine(left, upper_y, cx, mid_y)
        painter.drawLine(right, upper_y, cx, mid_y)

        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(10, min(width, height) // 3))
        painter.setFont(font)
        painter.setPen(QPen(shadow_color, 2))
        painter.drawText(QRect(1, 2, width, height), Qt.AlignCenter, "20")
        painter.setPen(edge_color)
        painter.drawText(QRect(0, 0, width, height), Qt.AlignCenter, "20")
        painter.end()
        return pixmap

    def load_main_ui_layout_config(self):
        layout_path = self.get_theme_layout_path()
        log_debug("theme", f"layout: {layout_path} {layout_path.exists()}")
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
        loaded, _ = load_settings()
        self.settings = loaded
        set_debug_settings(loaded.get("debug", {}) if isinstance(loaded, dict) else {})
        discovered_themes = self.discover_available_themes()

        saved_theme = str(loaded.get("theme", "") or "").strip()
        active_theme = saved_theme if saved_theme in discovered_themes else ""
        if not active_theme:
            active_theme = "diablo" if "diablo" in discovered_themes else (discovered_themes[0] if discovered_themes else "diablo")

        saved_themes = loaded.get("themes", [])
        normalized_saved = saved_themes if isinstance(saved_themes, list) else []
        normalized_saved = [str(item) for item in normalized_saved if str(item).strip()]
        if normalized_saved != discovered_themes or loaded.get("theme") != active_theme:
            self.settings["themes"] = discovered_themes
            self.settings["theme"] = active_theme
            save_settings(self.settings)

        log_debug("theme", f"discovered themes: {discovered_themes}")
        log_debug("theme", f"active theme: {active_theme}")
        return {"active_theme": active_theme, "themes": discovered_themes}

    def discover_available_themes(self):
        themes_dir = resource_path("assets/themes")
        discovered = []
        try:
            if themes_dir.exists():
                for child in themes_dir.iterdir():
                    if child.is_dir() and (child / "ui_layout.json").exists():
                        discovered.append(child.name)
        except Exception:
            pass
        discovered = sorted(set(discovered))
        if not discovered:
            discovered = ["diablo"]
        return discovered

    def save_theme_config(self):
        try:
            self.settings["theme"] = str(self.theme_config.get("active_theme", "diablo") or "diablo")
            save_settings(self.settings)
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
        layout_path = self.assets_dir / "themes" / active / "ui_layout.json"
        if layout_path.exists():
            return layout_path
        fallback = self.assets_dir / "themes" / "diablo" / "ui_layout.json"
        log_warning("theme", f"missing layout: {layout_path}, fallback: {fallback}")
        return fallback

    def get_theme_asset_base_path(self):
        active = self.get_active_theme()
        base = self.assets_dir / "themes" / active / "ui"
        if base.exists():
            return base
        fallback = self.assets_dir / "themes" / "diablo" / "ui"
        log_warning("theme", f"missing asset base: {base}, fallback: {fallback}")
        return fallback

    def reload_theme(self):
        self.theme_config = self.load_theme_config()
        self.active_theme = self.get_active_theme()
        self.theme_asset_base_path = self.get_theme_asset_base_path()
        self.main_ui_layout_config = self.load_main_ui_layout_config()
        self.theme_style = self.main_ui_layout_config.get("theme_style", {})
        self.nav_buttons = {}
        self.content_layer = None

        self.reset_browser_runtime_state(destroy_webview=True)
        for child in self.game_canvas.findChildren(QWidget):
            child.deleteLater()

        canvas_cfg = self.main_ui_layout_config.get("canvas", {})
        canvas_width = int(canvas_cfg.get("width", 1024))
        canvas_height = int(canvas_cfg.get("height", 768))
        log_debug("render", f"canvas: {canvas_width}x{canvas_height}")
        log_debug("render", f"canvas size: {canvas_width} {canvas_height}")
        self.setFixedSize(canvas_width, canvas_height)
        self.game_canvas.setFixedSize(canvas_width, canvas_height)

        frame_cfg = self.main_ui_layout_config.get("main_frame", {})
        frame_x = int(frame_cfg.get("x", 0))
        frame_y = int(frame_cfg.get("y", 0))
        frame_w = int(frame_cfg.get("w", canvas_width))
        frame_h = int(frame_cfg.get("h", canvas_height))
        frame_asset = frame_cfg.get("asset", "")
        log_debug("render", f"main_frame geometry: {frame_x} {frame_y} {frame_w} {frame_h}")
        frame_asset_path = self.resolve_ui_asset_path(frame_asset) if frame_asset else None
        log_debug(
            "theme",
            f"main_frame: {frame_asset_path} "
            f"{frame_asset_path.exists() if frame_asset_path else False}",
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
                nav_shape = str(nav_item.get("shape", "")).strip().lower()
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
                if nav_shape == "d20":
                    bg_label.setPixmap(self.create_d20_nav_pixmap(nav_w, nav_h))
                elif nav_asset_path is not None and nav_asset_path.exists():
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
                    "shape": nav_shape,
                }

        self.update_main_nav_button_styles()
        self.show_main_section(self.current_main_section)
        self.preload_browser_if_enabled()
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
        log_debug("render", "section changed: settings")

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
        if hasattr(self, "settings_theme_value_label") and self.settings_theme_value_label is not None and self.current_main_section == "settings":
            self.settings_theme_value_label.setText(self.get_active_theme())
        log_info("theme", f"switched to: {next_theme}")

    def on_settings_switch_theme_clicked(self):
        self.switch_to_next_theme()

    def on_settings_cache_reload_clicked(self):
        if hasattr(self.loader, "load_cache_from_json"):
            if hasattr(self.loader, "has_unsaved_changes") and self.loader.has_unsaved_changes():
                log_warning("character", "unsaved changes before switching character")
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
                elif self.current_main_section == "magic":
                    self.show_main_section("magic")
                elif self.current_main_section == "notes":
                    self.show_main_section("notes")
            log_debug("cache", "settings cache reload clicked")
            return
        log_debug("cache", "settings cache reload clicked")

    def on_settings_excel_import_clicked(self):
        try:
            self.load_excel()
        except Exception:
            log_debug("render", "settings excel import clicked")

    def on_main_nav_clicked(self, section_id):
        self.show_main_section(section_id)
        log_debug("render", f"section changed: {section_id}")

    def clear_content_layer(self):
        if self.content_layer is None:
            return
        for child in self.content_layer.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            if child is getattr(self, "_browser_container", None):
                child.hide()
                continue
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
        elif section_id == "magic":
            self.render_magic_screen()
        elif section_id == "notes":
            self.render_notes_screen()
        elif section_id in ("browser", "webbrowser"):
            self.render_browser_screen()
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
        text_color = str(cfg.get("color", nav_style.get("active_color", "#f2d28b")))
        font_size = int(cfg.get("font_size", 20))
        text_label = QLabel(container)
        text_label.setGeometry(0, 0, w, h)
        text_label.setText(text)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet(
            f"background: transparent; color: {text_color}; font-size: {font_size}px; font-weight: 700;"
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

    def create_dialog_asset_text_button(self, parent, text, callback, cfg=None):
        button_cfg = cfg if isinstance(cfg, dict) else {}
        result = self.create_asset_text_button(
            parent,
            {
                "x": 0,
                "y": 0,
                "w": int(button_cfg.get("w", 110)),
                "h": int(button_cfg.get("h", 32)),
                "text": text,
                "asset": str(button_cfg.get("asset", "buttons/menu_button_medium.png")),
                "font_size": int(button_cfg.get("font_size", 13)),
                "color": str(button_cfg.get("color", "#f2d28b")),
            },
            text,
            callback,
        )
        container = result.get("container") if isinstance(result, dict) else None
        if container is not None:
            container.setFixedSize(int(button_cfg.get("w", 110)), int(button_cfg.get("h", 32)))
        return container

    def render_settings_page(self):
        return settings_section.render_settings_section(self)

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
            self._character_debug(f'[WELLBEING] row={row} active={active} label="{label_text}"')
        return entries

    def load_skill_definitions(self):
        definitions_path = self.assets_dir / "config" / "skill_definitions.json"
        empty = {"attribute_map": {}, "categories": []}
        try:
            if not definitions_path.exists():
                log_warning("skills", "missing/invalid skill_definitions.json")
                return empty
            with open(definitions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                log_warning("skills", "missing/invalid skill_definitions.json")
                return empty
            if not isinstance(data.get("attribute_map"), dict):
                data["attribute_map"] = {}
            if not isinstance(data.get("categories"), list):
                data["categories"] = []
            return data
        except Exception as exc:
            log_warning("skills", f"missing/invalid skill_definitions.json: {exc}")
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
            self.assets_dir / "themes" / active_theme / layout_file,
            self.assets_dir / "themes" / "diablo" / "skills_layout.json",
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
            self.assets_dir / "themes" / active_theme / layout_file,
            self.assets_dir / "themes" / "diablo" / "inventory_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("inventory_screen"), dict):
                    log_debug("inventory", f"layout loaded: {layout_path}")
                    return data
            except Exception:
                continue
        log_debug("inventory", "layout fallback: internal default")
        return self.get_default_inventory_layout_config()

    def get_default_equipment_layout_config(self):
        return {
            "equipment_screen": {
                "x": 20,
                "y": 20,
                "w": 1420,
                "h": 820,
                "show_title": False,
                "show_debug_label": False,
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
                    "show_label": False,
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
            self.assets_dir / "themes" / active_theme / layout_file,
            self.assets_dir / "themes" / "diablo" / "equipment_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("equipment_screen"), dict):
                    self.equipment_layout_config = data
                    log_debug("equipment", f"layout loaded: {layout_path}")
                    return data
            except Exception:
                continue
        log_debug("equipment", "layout fallback: internal default")
        self.equipment_layout_config = self.get_default_equipment_layout_config()
        return self.equipment_layout_config

    def get_default_notes_layout_config(self):
        return {
            "notes_screen": {
                "x": 40,
                "y": 40,
                "w": 1380,
                "h": 790,
                "title": {
                    "enabled": True,
                    "text": "Notizen",
                    "x": 0,
                    "y": 0,
                    "w": 1380,
                    "h": 42,
                    "font_size": 24,
                    "color": "#f2d28b",
                    "align": "center",
                },
                "editor": {
                    "x": 20,
                    "y": 60,
                    "w": 1340,
                    "h": 620,
                    "font_size": 16,
                    "text_color": "#ffffff",
                    "background": "rgba(5, 5, 5, 120)",
                    "border_color": "rgba(242, 210, 139, 100)",
                    "placeholder": "Notizen...",
                },
                "save_button": {
                    "enabled": False,
                    "x": 1120,
                    "y": 700,
                    "w": 220,
                    "h": 44,
                    "text": "Speichern",
                },
                "status": {
                    "enabled": True,
                    "x": 20,
                    "y": 700,
                    "w": 700,
                    "h": 32,
                    "font_size": 14,
                    "color": "#e8e0c8",
                },
                "autosave": {"enabled": True, "delay_ms": 600},
                "debug": {"enabled": False},
            }
        }

    def load_notes_layout_config(self):
        active_theme = self.get_active_theme()
        layout_file = ""
        screen_cfg = self.main_ui_layout_config.get("notes_screen", {})
        if isinstance(screen_cfg, dict):
            layout_file = str(screen_cfg.get("layout_file", "")).strip()
        if not layout_file:
            layout_file = "notes_layout.json"

        candidates = [
            self.assets_dir / "themes" / active_theme / layout_file,
            self.assets_dir / "themes" / "diablo" / "notes_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("notes_screen"), dict):
                    debug_cfg = data.get("notes_screen", {}).get("debug", {})
                    if isinstance(debug_cfg, dict) and bool(debug_cfg.get("enabled", False)):
                        log_debug("notes", f"layout loaded: {layout_path}")
                    return data
            except Exception:
                continue
        log_debug("notes", "layout fallback: internal default")
        return self.get_default_notes_layout_config()

    def get_default_magic_layout_config(self):
        return {
            "magic_screen": {
                "x": 30,
                "y": 25,
                "w": 1400,
                "h": 820,
                "title": {
                    "enabled": True,
                    "text": "Magie",
                    "x": 0,
                    "y": 0,
                    "w": 1400,
                    "h": 38,
                    "font_size": 24,
                    "color": "#f2d28b",
                    "align": "center",
                },
                "debug": {"enabled": True, "print_mapping": True, "print_rows": True},
                "upgrade_table": {
                    "enabled": True,
                    "x": 20,
                    "y": 50,
                    "w": 760,
                    "h": 250,
                    "title": "Upgrade Tabelle",
                    "font_size": 14,
                    "title_font_size": 18,
                    "header_color": "#f2d28b",
                    "text_color": "#ffffff",
                    "value_color": "#7fd0ff",
                    "background": "rgba(5, 5, 5, 95)",
                    "border_color": "rgba(242, 210, 139, 90)",
                    "readonly": True,
                },
                "spell_table": {
                    "enabled": True,
                    "x": 20,
                    "y": 330,
                    "w": 1360,
                    "h": 450,
                    "title": "Magie",
                    "font_size": 14,
                    "title_font_size": 18,
                    "header_color": "#f2d28b",
                    "text_color": "#ffffff",
                    "value_color": "#7fd0ff",
                    "background": "rgba(5, 5, 5, 95)",
                    "border_color": "rgba(242, 210, 139, 90)",
                    "editable": True,
                    "min_rows": 14,
                    "max_scan_rows": 25,
                    "columns": {
                        "school": {"title": "Magieschule", "w": 180},
                        "info": {"title": "Info", "w": 330},
                        "prepared_spell": {"title": "Vorbereiteter Zauber", "w": 300},
                        "charge": {"title": "Ladung", "w": 80},
                        "duration": {"title": "Dauer", "w": 90},
                        "effect": {"title": "Effekt", "w": 360},
                    },
                },
            }
        }

    def load_magic_layout_config(self):
        active_theme = self.get_active_theme()
        layout_file = ""
        screen_cfg = self.main_ui_layout_config.get("magic_screen", {})
        if isinstance(screen_cfg, dict):
            layout_file = str(screen_cfg.get("layout_file", "")).strip()
        if not layout_file:
            layout_file = "magic_layout.json"

        candidates = [
            self.assets_dir / "themes" / active_theme / layout_file,
            self.assets_dir / "themes" / "diablo" / "magic_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("magic_screen"), dict):
                    debug_cfg = data.get("magic_screen", {}).get("debug", {})
                    if isinstance(debug_cfg, dict) and bool(debug_cfg.get("enabled", False)):
                        log_debug("magic", f"layout loaded: {layout_path}")
                    self.magic_layout_config = data
                    return data
            except Exception:
                continue
        log_debug("magic", "layout fallback: internal default")
        self.magic_layout_config = self.get_default_magic_layout_config()
        return self.magic_layout_config

    def _notes_debug_enabled(self, notes_layout):
        return notes_debug_enabled(notes_layout)

    def _get_notes_text_from_meta(self):
        app_meta = getattr(self.loader, "app_meta", {})
        if not isinstance(app_meta, dict):
            return ""
        custom_sections = app_meta.get("custom_sections", {})
        if not isinstance(custom_sections, dict):
            return ""
        notes_data = custom_sections.get("notes", {})
        if not isinstance(notes_data, dict):
            return ""
        return str(notes_data.get("text", "") or "")

    def _save_notes_text_to_meta(self, text_value):
        try:
            if not isinstance(self.loader.app_meta, dict):
                self.loader.app_meta = {}
            custom_sections = self.loader.app_meta.setdefault("custom_sections", {})
            if not isinstance(custom_sections, dict):
                custom_sections = {}
                self.loader.app_meta["custom_sections"] = custom_sections
            custom_sections["notes"] = {
                "text": str(text_value or ""),
                "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            self.loader.save_active_character_json()
            return True
        except Exception as exc:
            log_error("notes", f"save failed: {exc}")
            return False

    def _get_equipment_debug_config(self):
        layout_config = getattr(self, "equipment_layout_config", None)
        if not isinstance(layout_config, dict):
            layout_config = self.load_equipment_layout_config()
        screen_cfg = layout_config.get("equipment_screen", {}) if isinstance(layout_config, dict) else {}
        debug_cfg = screen_cfg.get("debug", {}) if isinstance(screen_cfg, dict) else {}
        if not isinstance(debug_cfg, dict):
            debug_cfg = {}
        return debug_cfg

    def _equipment_debug_enabled(self):
        return bool(self._get_equipment_debug_config().get("enabled", True))

    def _get_magic_debug_config(self):
        layout_config = getattr(self, "magic_layout_config", None)
        if not isinstance(layout_config, dict) or not layout_config:
            layout_config = self.load_magic_layout_config()
        screen_cfg = layout_config.get("magic_screen", {}) if isinstance(layout_config, dict) else {}
        debug_cfg = screen_cfg.get("debug", {}) if isinstance(screen_cfg, dict) else {}
        if not isinstance(debug_cfg, dict):
            return {}
        return debug_cfg

    def _magic_debug_enabled(self):
        return bool(self._get_magic_debug_config().get("enabled", True))

    def _magic_print_mapping_enabled(self):
        debug_cfg = self._get_magic_debug_config()
        return bool(debug_cfg.get("print_mapping", True)) and self._magic_debug_enabled()

    def _magic_print_rows_enabled(self):
        debug_cfg = self._get_magic_debug_config()
        return bool(debug_cfg.get("print_rows", True)) and self._magic_debug_enabled()

    def _equipment_print_mapping_enabled(self):
        debug_cfg = self._get_equipment_debug_config()
        return bool(debug_cfg.get("enabled", True) and debug_cfg.get("print_mapping", True))

    def _equipment_print_rows_enabled(self):
        debug_cfg = self._get_equipment_debug_config()
        return bool(debug_cfg.get("enabled", True) and debug_cfg.get("print_rows", True))

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
            self.assets_dir / "themes" / active_theme / "roll_dialog_layout.json",
            self.assets_dir / "themes" / "diablo" / "roll_dialog_layout.json",
        ]
        for layout_path in candidates:
            try:
                if not layout_path.exists():
                    continue
                with open(layout_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("dialog"), dict):
                    log_debug("roll20", f"layout loaded: {layout_path}")
                    return data
            except Exception:
                continue
        log_debug("roll20", "layout fallback: internal defaults")
        return default_config

    def load_perk_rules_config(self):
        rules_path = self.assets_dir / "config" / "perk_rules.json"
        empty = {"version": 1, "description": "", "rules": []}
        try:
            if not rules_path.exists():
                log_warning("roll20", "perk rules missing, using empty rules")
                return empty
            with open(rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                log_warning("roll20", "perk rules invalid, using empty rules")
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
            log_debug("roll20", f"perk rules loaded: {rules_path} rules={len(enabled_rules)}")
            return data
        except Exception:
            log_warning("roll20", "perk rules load failed, using empty rules")
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
        mapping_path = self.assets_dir / "config" / "skill_sheet_mapping.json"
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
            log_debug("skills", f'SKILLS FORMULA BONUS AMBIGUOUS {source_key} formula="{formula_text}"')
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
            log_debug("skills", f'SKILLS MAP AMBIGUOUS {category_id}/{skill_id} "{skill_name}" matches: {[m[0] for m in matches]}')
            result = (None, "ambiguous_row", matches)
            return result if return_info else None
        if len(matches) == 1:
            log_debug("skills", f'SKILLS MAP ROW {category_id}/{skill_id} "{skill_name}" -> {sheet_name}!{name_col}{matches[0][0]}')
            result = (matches[0][0], "ok", matches)
            return result if return_info else matches[0][0]
        log_debug("skills", f'SKILLS MAP MISSING {category_id}/{skill_id} "{skill_name}" no row found')
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
            log_debug("skills", f"SKILLS MAP BONUS RESOLVED {source_key} freie_wahl attrs={attribute_letters} -> {bonus_key} value={bonus_value if bonus_value is not None else 0}")
            return bonus_key, "attribute_group"
        if len(candidates) > 1:
            sorted_candidates = sorted(candidates)
            log_debug("skills", f"SKILLS MAP BONUS AMBIGUOUS {source_key} freie_wahl attrs={attribute_letters} candidates={sorted_candidates}")
            return None, "ambiguous"

        log_debug("skills", f"SKILLS MAP BONUS UNKNOWN {source_key} freie_wahl attrs={attribute_letters}")
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
                log_debug("skills", f'SKILLS MATCH AMBIGUOUS {source_key} ui="{ui_name}" matches={[m[0] for m in matches]}')
            else:
                log_debug("skills", f'SKILLS MATCH MISSING {source_key} ui="{ui_name}"')
            log_debug("skills", f"SKILLS STRUCTURE ONLY {source_key} no cache row, visible fields blank")
            self.skill_source_infos[source_key] = info
            self.log_skill_source_info(source_key, info)
            log_debug("skills", f'SKILLS VISIBLE SOURCE {source_key} visible_source={info.get("visible_source")} match={info.get("match_type")} display="{info.get("display_name")}"')
            return info

        cache_name = matches[0][1] if matches else ""
        match_quality = matches[0][2] if matches and len(matches[0]) > 2 else "exact"
        info["cache_name"] = cache_name
        info["match_quality"] = match_quality
        info["match_type"] = match_quality
        use_cache_display_fields = match_quality in ("exact", "legacy")
        field_fallback_used = False
        if match_quality == "legacy":
            log_debug("skills", f'SKILLS LEGACY MATCH {source_key} ui="{ui_name}" cache="{cache_name}" row={row} using cache-visible data')
        elif match_quality == "exact":
            log_debug("skills", f"SKILLS EXACT MATCH {source_key} row={row} using cache-visible data")

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
            log_debug("skills", f"SKILLS FALLBACK {ui_name} missing block, using attribute_sum: {attribute_sum}")
            self.skill_source_infos[source_key] = info
            self.log_skill_source_info(source_key, info)
            log_debug("skills", f'SKILLS VISIBLE SOURCE {source_key} visible_source={info.get("visible_source")} match={info.get("match_type")} display="{info.get("display_name")}"')
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
                log_debug("skills", f"SKILLS MAP LOOKUP MISSING {source_key} {letter} {info['lookup_key_range']}")
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
                log_debug("skills", f"SKILLS FORMULA BONUS {source_key} {formula_cell} -> {formula_bonus_cell} value={bonus_value}")
            else:
                log_debug("skills", f"SKILLS FORMULA BONUS {source_key} {formula_cell} -> none")
        else:
            log_debug("skills", f"SKILLS BONUS FALLBACK {source_key} no formula text, using note fallback")
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

    def ensure_skill_source_infos_ready(self):
        if isinstance(self.skill_source_infos, dict) and self.skill_source_infos:
            return
        skill_definitions = self.load_skill_definitions()
        categories = skill_definitions.get("categories", [])
        if not isinstance(categories, list):
            categories = []
        attribute_map = skill_definitions.get("attribute_map", {})
        if not isinstance(attribute_map, dict):
            attribute_map = {}
        self.build_skill_source_infos(categories, attribute_map)

    def open_character_initiative_roll(self):
        initiative_info = self.get_character_initiative_data()
        if not initiative_info or initiative_info.get("roll_value") is None:
            log_warning("character", "initiative value not found")
            QMessageBox.information(
                self,
                "Initiative",
                "Initiative-Wert nicht gefunden. Prüfe Charakterbogen-Initiative-Feld.",
            )
            return
        log_debug("roll20", f'CHARACTER INITIATIVE ROLL source={initiative_info.get("source", "-")} roll={initiative_info.get("roll_value", "-")} dialog=roll_dialog_layout')
        roll_info = {
            "source": "character_initiative",
            "display_name": "Initiative",
            "display_value": int(initiative_info.get("roll_value", 0) or 0),
            "raw_value": str(initiative_info.get("raw_value", "")),
            "bonus_value": int(initiative_info.get("bonus", 0) or 0),
            "slot_values": ["R", "I"],
            "specialization_text": "",
            "specializations_enabled": False,
            "perk_suggestions_enabled": False,
            "paradigm_enabled": False,
            "skill_value_allowed": True,
            "roll_context": "character_initiative",
            "wellbeing_context": {
                "display_name": "Initiative",
                "display_specialization": "",
                "display_attribute_slots": ["R", "I"],
            },
        }
        log_debug("roll20", "ROLL DIALOG source=character_initiative layout=roll_dialog_layout")
        self.open_skill_roll_dialog(roll_info=roll_info)

    def _parse_cell_ref(self, cell_ref):
        match = re.fullmatch(r"([A-Z]+)([0-9]+)", str(cell_ref or "").strip().upper())
        if not match:
            return None, None
        return match.group(1), int(match.group(2))

    def _get_character_initiative_panel_data_cfg(self):
        character_screen = self.main_ui_layout_config.get("character_screen", {})
        if not isinstance(character_screen, dict):
            return {}
        panel_cfg = character_screen.get("initiative_panel", {})
        if not isinstance(panel_cfg, dict):
            return {}
        data_cfg = panel_cfg.get("data", {})
        return data_cfg if isinstance(data_cfg, dict) else {}

    def _to_float_or_none(self, value):
        text = str(value if value is not None else "").strip()
        if not text:
            return None
        cleaned = text.replace(" ", "").replace(",", ".")
        try:
            return float(cleaned)
        except Exception:
            return None

    def _round_half_up(self, number):
        try:
            numeric = float(number)
        except Exception:
            return 0
        if numeric >= 0:
            return int(math.floor(numeric + 0.5))
        return int(math.ceil(numeric - 0.5))

    def _is_initiative_text(self, value):
        normalized = self._norm_match_text(value)
        if not normalized:
            return False
        compact = normalized.replace("-", " ").replace("_", " ")
        return ("ini wurf" in compact) or ("initiative" in compact)

    def _extract_numeric_value(self, raw_value):
        number = self._to_float_or_none(raw_value)
        if number is None:
            return None
        return number

    def _initiative_data_from_skill_sources(self):
        self.ensure_skill_source_infos_ready()
        if not isinstance(self.skill_source_infos, dict):
            return None
        for source_key, info in self.skill_source_infos.items():
            if not isinstance(info, dict):
                continue
            candidates = [
                info.get("display_name", ""),
                info.get("skill_name", ""),
                info.get("ui_name", ""),
                info.get("cache_name", ""),
            ]
            if not any(self._is_initiative_text(item) for item in candidates):
                continue
            raw_number = self._extract_numeric_value(info.get("calculated_value", None))
            raw_text = info.get("calculated_value", None)
            if raw_number is None:
                raw_text = str(info.get("display_value", "") or "").strip()
                raw_number = self._extract_numeric_value(raw_text)
            if raw_number is None:
                continue
            roll_value = self._round_half_up(raw_number)
            return {
                "source": f"skills:{source_key}",
                "raw_value": str(raw_text if raw_text is not None else raw_number),
                "value": raw_number,
                "bonus": 0,
                "roll_value": roll_value,
                "debug": f"skill_source_key={source_key}",
            }
        return None

    def _initiative_data_from_fertigkeiten_cache(self):
        mapping = self.get_skill_sheet_mapping_config()
        sheet_name = str(mapping.get("sheet", "Fertigkeiten"))
        name_col = str(mapping.get("name_col", "D")).strip().upper() or "D"
        value_col = str(mapping.get("value_formula_col", "AH")).strip().upper() or "AH"
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        if not isinstance(sheet_cache, dict) or not sheet_cache:
            return None

        row = None
        matched_name = ""
        for cell_ref in sorted(sheet_cache.keys()):
            match = re.fullmatch(rf"{name_col}([0-9]+)", str(cell_ref), flags=re.IGNORECASE)
            if not match:
                continue
            current_name = str(self.get_cache_cell_value(sheet_name, cell_ref, "") or "")
            if self._is_initiative_text(current_name):
                row = int(match.group(1))
                matched_name = current_name
                break
        if row is None:
            return None

        raw_text = self.get_cache_cell_value(sheet_name, f"{value_col}{row}", "")
        raw_number = self._extract_numeric_value(raw_text)
        if raw_number is None:
            base_index = self._col_letters_to_index(name_col)
            for offset in range(1, 12):
                col = self._col_index_to_letters(base_index + offset)
                candidate_cell = f"{col}{row}"
                candidate_raw = self.get_cache_cell_value(sheet_name, candidate_cell, "")
                candidate_number = self._extract_numeric_value(candidate_raw)
                if candidate_number is None:
                    continue
                raw_text = candidate_raw
                raw_number = candidate_number
                break
        if raw_number is None:
            return None
        roll_value = self._round_half_up(raw_number)
        return {
            "source": f"sheet:{sheet_name}:{name_col}{row}",
            "raw_value": str(raw_text if raw_text is not None else raw_number),
            "value": raw_number,
            "bonus": 0,
            "roll_value": roll_value,
            "debug": f'matched_name="{matched_name}"',
        }

    def _build_initiative_data_result(self, source, raw_value, raw_bonus, debug_text="", sheet="", value_cell="", bonus_cell=""):
        value_number = self._extract_numeric_value(raw_value)
        if value_number is None:
            return None
        bonus_number = self._extract_numeric_value(raw_bonus)
        rounded_bonus = self._round_half_up(bonus_number) if bonus_number is not None else 0
        roll_value = self._round_half_up(value_number + rounded_bonus)
        return {
            "source": source,
            "raw_value": str(raw_value if raw_value is not None else ""),
            "value": value_number,
            "bonus": rounded_bonus,
            "raw_bonus": str(raw_bonus if raw_bonus is not None else ""),
            "roll_value": roll_value,
            "debug": debug_text,
            "sheet": str(sheet or ""),
            "value_cell": str(value_cell or "").strip().upper(),
            "bonus_cell": str(bonus_cell or "").strip().upper(),
        }

    def _initiative_data_from_config_cells(self):
        data_cfg = self._get_character_initiative_panel_data_cfg()
        sheet_name = str(data_cfg.get("sheet", "Charakterbogen") or "Charakterbogen")
        value_cell = str(data_cfg.get("value_cell", "") or "").strip().upper()
        bonus_cell = str(data_cfg.get("bonus_cell", "") or "").strip().upper()
        if not value_cell:
            return None
        raw_value = self.get_cache_cell_value(sheet_name, value_cell, "")
        raw_bonus = self.get_cache_cell_value(sheet_name, bonus_cell, "") if bonus_cell else ""
        return self._build_initiative_data_result(
            f"character:{value_cell}",
            raw_value,
            raw_bonus,
            debug_text=f"config_cells value_cell={value_cell} bonus_cell={bonus_cell or '-'}",
            sheet=sheet_name,
            value_cell=value_cell,
            bonus_cell=bonus_cell,
        )

    def find_character_initiative_cells(self):
        data_cfg = self._get_character_initiative_panel_data_cfg()
        sheet_name = str(data_cfg.get("sheet", "Charakterbogen") or "Charakterbogen")
        if not bool(data_cfg.get("scan_enabled", True)):
            return None
        initiative_label = self._norm_match_text(data_cfg.get("label_text", "Initiative")).replace(":", "")
        bonus_label = self._norm_match_text(data_cfg.get("bonus_label_text", "Bonus")).replace(":", "")
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        if not isinstance(sheet_cache, dict) or not sheet_cache:
            return None

        candidates = []
        for cell_ref in sheet_cache.keys():
            col, row = self._parse_cell_ref(cell_ref)
            if not col or not row:
                continue
            cell_value = str(self.get_cache_cell_value(sheet_name, cell_ref, "") or "")
            normalized = self._norm_match_text(cell_value).replace(":", "")
            if initiative_label and normalized == initiative_label:
                candidates.append((str(cell_ref).strip().upper(), col, row))
            elif "initiative" in normalized and "ini-wurf" not in normalized and "athletik" not in normalized and "klettern" not in normalized:
                candidates.append((str(cell_ref).strip().upper(), col, row))

        best = None
        for label_cell, label_col, label_row in candidates:
            base_col_index = self._col_letters_to_index(label_col)
            found_value_cell = ""
            found_value = None
            for offset in range(1, 7):
                candidate_col = self._col_index_to_letters(base_col_index + offset)
                candidate_cell = f"{candidate_col}{label_row}"
                candidate_raw = self.get_cache_cell_value(sheet_name, candidate_cell, "")
                candidate_num = self._extract_numeric_value(candidate_raw)
                if candidate_num is None:
                    continue
                found_value_cell = candidate_cell
                found_value = candidate_num
                break
            if not found_value_cell:
                continue

            bonus_label_cell = ""
            bonus_cell = ""
            bonus_value = None
            for row_offset in range(0, 3):
                row = label_row + row_offset
                for col_offset in range(0, 3):
                    candidate_label_col = self._col_index_to_letters(base_col_index + col_offset)
                    candidate_label_cell = f"{candidate_label_col}{row}"
                    candidate_label_text = str(self.get_cache_cell_value(sheet_name, candidate_label_cell, "") or "")
                    normalized_bonus_label = self._norm_match_text(candidate_label_text).replace(":", "")
                    if normalized_bonus_label != bonus_label:
                        continue
                    bonus_label_cell = candidate_label_cell
                    bonus_col_index = self._col_letters_to_index(candidate_label_col)
                    for scan_offset in range(1, 7):
                        c_col = self._col_index_to_letters(bonus_col_index + scan_offset)
                        c_cell = f"{c_col}{row}"
                        c_raw = self.get_cache_cell_value(sheet_name, c_cell, "")
                        c_num = self._extract_numeric_value(c_raw)
                        if c_num is None:
                            continue
                        bonus_cell = c_cell
                        bonus_value = c_num
                        break
                    if bonus_cell:
                        break
                if bonus_cell:
                    break

            value_score = 1 if found_value is not None and 0 <= float(found_value) <= 50 else 0
            bonus_score = 1 if bonus_value is not None and 0 <= float(bonus_value) <= 50 else 0
            score = value_score * 2 + bonus_score
            log_debug(
                "character",
                f"CHARACTER INITIATIVE SCAN candidate label={label_cell} "
                f"value_cell={found_value_cell} value={found_value} "
                f"bonus_cell={bonus_cell or '-'} bonus={bonus_value if bonus_value is not None else '-'} "
                f"score={score}",
            )
            candidate = {
                "sheet": sheet_name,
                "label_cell": label_cell,
                "value_cell": found_value_cell,
                "bonus_label_cell": bonus_label_cell,
                "bonus_cell": bonus_cell,
                "_score": score,
            }
            if best is None or score > best["_score"]:
                best = candidate

        if best is None:
            return None
        best.pop("_score", None)
        return best

    def get_character_initiative_data(self):
        result = self._initiative_data_from_config_cells()
        if result is None:
            cell_info = self.find_character_initiative_cells()
            if isinstance(cell_info, dict):
                sheet_name = str(cell_info.get("sheet", "Charakterbogen"))
                value_cell = str(cell_info.get("value_cell", "") or "").strip().upper()
                bonus_cell = str(cell_info.get("bonus_cell", "") or "").strip().upper()
                if value_cell:
                    raw_value = self.get_cache_cell_value(sheet_name, value_cell, "")
                    raw_bonus = self.get_cache_cell_value(sheet_name, bonus_cell, "") if bonus_cell else ""
                    result = self._build_initiative_data_result(
                        f"character:{value_cell}",
                        raw_value,
                        raw_bonus,
                        debug_text=f"label_cell={cell_info.get('label_cell', '')}",
                        sheet=sheet_name,
                        value_cell=value_cell,
                        bonus_cell=bonus_cell,
                    )
        if result is None:
            result = self._initiative_data_from_skill_sources()
            if result is None:
                result = self._initiative_data_from_fertigkeiten_cache()
            if result is not None:
                log_debug("character", "CHARACTER INITIATIVE using skills fallback, character initiative field not found")

        if result is None:
            log_debug("character", "CHARACTER INITIATIVE DATA source=none raw=- value=- bonus=0 roll=-")
            return {
                "source": "none",
                "raw_value": "-",
                "value": None,
                "bonus": 0,
                "roll_value": None,
                "debug": "not_found",
            }

        log_debug(
            "character",
            f"CHARACTER INITIATIVE DATA source={result.get('source', '-')} "
            f"value_cell={result.get('value_cell', '-') or '-'} "
            f"bonus_cell={result.get('bonus_cell', '-') or '-'} "
            f"raw={result.get('raw_value', '-')} bonus={result.get('bonus', 0)} "
            f"roll={result.get('roll_value', '-')}",
        )
        if str(result.get("source", "")).startswith("character:"):
            fallback_skill = self._initiative_data_from_skill_sources()
            if isinstance(fallback_skill, dict):
                log_debug("character", f"CHARACTER INITIATIVE NOTE skill_ini_wurf={fallback_skill.get('raw_value', '-')} ignored because character initiative field exists")
        if "raw_bonus" not in result:
            result["raw_bonus"] = str(result.get("bonus", 0))
        return result

    def log_skill_source_info(self, source_key, info):
        if not self.skills_debug_sources:
            return
        log_debug(
            "skills",
            f"SKILLS SOURCE {source_key} row={info.get('row')} "
            f"attrs={info.get('resolved_attribute_letters')} "
            f"attr_values={info.get('resolved_attribute_values')} "
            f"bonus={info.get('resolved_bonus_key')}:{info.get('resolved_bonus_value')} "
            f"raw={info.get('calculated_value')} display={info.get('display_value')} "
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
        log_debug("skills", f'SKILLS EDIT ATTR MENU {sheet_name}!{cell_ref} selected="{selected_value}"')
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
            log_debug("skills", f'SKILLS EDIT ATTR {sheet_name}!{cell_ref} "{old_value}" -> "{normalized_new_value}"')
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
                    log_warning("skills", f'unexpected slot change {sheet_name}!{normalized_ref} "{before_values.get(normalized_ref, "")}" -> "{after_value}"')
            log_debug("skills", f"SKILLS EDIT SLOT SNAPSHOT row={source_info.get('row')} before={before_snapshot} after={after_snapshot}")
            self.loader.save_active_character_json()
            log_debug("save", "SKILLS EDIT SAVE active character saved")
            self.create_tabs_from_cache()
            self.show_main_section("skills")
        except Exception as exc:
            log_error("skills", f"edit attribute failed: {exc}")

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
            log_debug("skills", f'SKILLS EDIT SPEC {sheet_name}!{cell_ref} "{old_value}" -> "{normalized_new_value}"')
            self.loader.set_cell_value(sheet_name, cell_ref, normalized_new_value)
            self.loader.save_active_character_json()
            log_debug("save", "SKILLS EDIT SAVE active character saved")
            self.create_tabs_from_cache()
            self.show_main_section("skills")
        except Exception as exc:
            log_error("skills", f"edit specialization failed: {exc}")

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
            log_debug("skills", f'SKILLS EDIT {tag} {sheet_name}!{cell_ref} "{old_value}" -> "{normalized_new_value}"')
            self.loader.set_cell_value(sheet_name, cell_ref, normalized_new_value)
            self.loader.save_active_character_json()
            log_debug("save", "SKILLS EDIT SAVE active character saved")
            self.create_tabs_from_cache()
            self.show_main_section("skills")
        except Exception as exc:
            log_error("skills", f"edit text failed: {exc}")

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
                log_debug("character", f'PERK DATA {entry_type} row={row} name="{name}" effect="{effect}"')

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
                log_debug("roll20", f'PERK MATCH skill="{skill_name}" rule={rule_id} source="{entry_name}" label="{suggestion["label"]}"')

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
            log_debug("roll20", f'PERK MATCH skill="{skill_name}" none')
        return matches

    def filter_roll_suggestions_for_context(self, suggestions, roll_context=None):
        if not isinstance(suggestions, list):
            return []
        context = str(roll_context or "").strip().lower()
        if context != "initiative":
            return suggestions

        kept = []
        dropped = 0
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                dropped += 1
                continue
            rule_id = self._norm_match_text(suggestion.get("rule_id", ""))
            label = self._norm_match_text(suggestion.get("label", ""))
            effect = self._norm_match_text(suggestion.get("source_effect", ""))
            source_name = self._norm_match_text(suggestion.get("source_name", ""))
            reason = None
            if source_name == "flink":
                reason = "flink_handled_as_fixed_bonus"
            elif "balance" in rule_id:
                reason = "balance_not_for_initiative"
            elif rule_id == "flink_initiative_bonus":
                reason = "flink_rule_fixed_bonus"
            elif any(word in label for word in ("mobilität", "athletik", "bewegung", "parcour")):
                reason = "athletic_mobility_only"
            else:
                combined = " ".join([rule_id, label])
                if "initiative" in combined or "ini-wurf" in combined or "ini wurf" in combined:
                    kept.append(suggestion)
                else:
                    reason = "not_explicit_initiative"
            if reason is not None:
                dropped += 1
                log_debug("roll20", f"ROLL SUGGESTION FILTER context=initiative drop rule={rule_id or '-'} reason={reason}")
        log_debug("roll20", f"ROLL SUGGESTION FILTER context=initiative kept={len(kept)} dropped={dropped}")
        return kept

    def get_fixed_roll_bonuses_for_context(self, skill_info, roll_context=None):
        result = {"extra_bonuses": [], "lines": []}
        context = str(roll_context or "").strip().lower()
        if context != "initiative":
            return result
        try:
            perk_rules_config = self.load_perk_rules_config()
            rules = perk_rules_config.get("rules", [])
            character_entries = self.collect_character_perk_entries()
        except Exception:
            return result
        if not isinstance(rules, list) or not isinstance(character_entries, list):
            return result

        flink_rule = None
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rule_id = self._norm_match_text(rule.get("id", ""))
            label = self._norm_match_text(rule.get("label", ""))
            if rule_id == "flink_initiative_bonus" or ("flink" in label and "initiative" in label):
                flink_rule = rule
                break
        if not isinstance(flink_rule, dict):
            return result

        has_flink = False
        for entry in character_entries:
            if not isinstance(entry, dict):
                continue
            if self._norm_match_text(entry.get("type", "")) != "perk":
                continue
            if "flink" in self._norm_match_text(entry.get("name", "")):
                has_flink = True
                break
        if not has_flink:
            return result

        effect = flink_rule.get("suggested_effect", {})
        if not isinstance(effect, dict):
            effect = {}
        try:
            flat_bonus = int(effect.get("flat_bonus", effect.get("bonus", 0)) or 0)
        except Exception:
            flat_bonus = 0
        if flat_bonus == 0:
            return result

        result["extra_bonuses"].append(flat_bonus)
        result["lines"].append(f"Flink: Initiative +{flat_bonus} aktiv")
        log_debug("roll20", f"ROLL FIXED BONUS context=initiative source=Flink bonus={flat_bonus} auto=True")
        return result

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
            log_debug("roll20", "WELLBEING ROLL SUGGESTION none")
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
            log_debug("roll20", "WELLBEING ROLL SUGGESTION none")
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
                log_debug("roll20", f'WELLBEING ROLL SKIP movement label="{raw_label}"')
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
            log_debug("roll20", f'WELLBEING ROLL SUGGESTION label="{raw_label}" effect={compact_effect}')

        if not suggestions:
            log_debug("roll20", "WELLBEING ROLL SUGGESTION none")
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
        log_debug("roll20", f'ROLL SELECT {source_key} row={source_info.get("row")} name="{display_name}" value={value_number} attrs={attribute_letters} specialization="{specialization_text}"')
        self.open_skill_roll_dialog(source_key)

    def open_skill_roll_dialog(self, source_key=None, roll_context=None, roll_info=None):
        log_debug("roll20", f"ROLL DIALOG source={'character_initiative' if isinstance(roll_info, dict) else 'skill'} layout=roll_dialog_layout")
        source_info = None
        if isinstance(roll_info, dict):
            display_name = str(roll_info.get("display_name", ""))
            specialization_text = str(roll_info.get("specialization_text", "") or "")
            slot_values = roll_info.get("slot_values", [])
            if not isinstance(slot_values, list):
                slot_values = []
            slot_values = (slot_values + ["", "", "", ""])[:4]
            resolved_letters = [str(v).strip().upper() for v in slot_values if str(v).strip()]
            attrs_text = ", ".join(resolved_letters) if resolved_letters else "-"
            skill_value = self._safe_int(roll_info.get("display_value", 0), 0)
            skill_value_allowed = bool(roll_info.get("skill_value_allowed", True))
            roll_context = str(roll_info.get("roll_context", roll_context or "")).strip().lower() or None
        else:
            source_info = self.skill_source_infos.get(source_key)
            if not isinstance(source_info, dict) or source_info.get("row") is None:
                return
            roll_context = str(roll_context or "").strip().lower() or None
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
        is_initiative_context = roll_context in {"initiative", "character_initiative"}
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
        if is_initiative_context:
            specialization_items = []
        skill_info_for_perks = {
            "display_name": display_name,
            "display_specialization": specialization_text,
            "source_key": str(source_key or ""),
            "display_value": source_info.get("display_value", "0") if isinstance(source_info, dict) else str(skill_value),
        }
        if isinstance(roll_info, dict) and not bool(roll_info.get("perk_suggestions_enabled", True)):
            perk_suggestions = []
            fixed_bonus_data = {"extra_bonuses": [], "lines": []}
        else:
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
                log_warning("roll20", f"perk suggestions failed: {exc}")
            if not isinstance(perk_suggestions, list):
                perk_suggestions = []
            perk_suggestions = self.filter_roll_suggestions_for_context(perk_suggestions, roll_context=roll_context)
            fixed_bonus_data = self.get_fixed_roll_bonuses_for_context(skill_info_for_perks, roll_context=roll_context)
        if not isinstance(fixed_bonus_data, dict):
            fixed_bonus_data = {"extra_bonuses": [], "lines": []}
        fixed_bonus_lines = fixed_bonus_data.get("lines", [])
        fixed_extra_bonuses = fixed_bonus_data.get("extra_bonuses", [])
        if not isinstance(fixed_bonus_lines, list):
            fixed_bonus_lines = []
        if not isinstance(fixed_extra_bonuses, list):
            fixed_extra_bonuses = []
        if is_initiative_context:
            perk_suggestions = [
                s for s in perk_suggestions
                if self._norm_match_text(s.get("rule_id", "")) != "flink_initiative_bonus"
            ]
        wellbeing_context = {
            "display_name": display_name,
            "display_specialization": specialization_text,
            "display_attribute_slots": slot_values,
        }
        if isinstance(roll_info, dict) and isinstance(roll_info.get("wellbeing_context"), dict):
            wellbeing_context = roll_info.get("wellbeing_context")
        try:
            wellbeing_suggestions = self.get_active_wellbeing_roll_suggestions(wellbeing_context)
        except Exception as exc:
            wellbeing_suggestions = []
            log_warning("roll20", f"wellbeing suggestions failed: {exc}")
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

        theme_dir = self.assets_dir / "themes" / self.get_active_theme()
        fallback_theme_dir = self.assets_dir / "themes" / "diablo"

        def resolve_roll_asset_path(relative_path):
            rel = str(relative_path or "").strip()
            if not rel:
                return None
            candidate_paths = [
                theme_dir / rel,
                theme_dir / "ui" / rel,
                fallback_theme_dir / rel,
                fallback_theme_dir / "ui" / rel,
                self.assets_dir / rel,
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
                else:
                    if not bool(getattr(self, "_roll_checkbox_asset_warning_shown", False)):
                        log_warning("roll20", "missing checked/unchecked asset, using native checkbox")
                        self._roll_checkbox_asset_warning_shown = True
            return style

        checkbox_style = build_checkbox_style()
        return open_roll20_dialog(
            self,
            {
                "display_name": display_name,
                "specialization_text": specialization_text,
                "attrs_text": attrs_text,
                "skill_value": skill_value,
                "skill_value_allowed": skill_value_allowed,
                "is_initiative_context": is_initiative_context,
                "is_character_initiative": isinstance(roll_info, dict) and str(roll_info.get("source", "")) == "character_initiative",
                "dialog_title": str(roll_info.get("dialog_title", "") or "") if isinstance(roll_info, dict) else "",
                "raw_value": roll_info.get("raw_value", skill_value) if isinstance(roll_info, dict) else skill_value,
                "bonus_value": roll_info.get("bonus_value", 0) if isinstance(roll_info, dict) else 0,
                "specialization_items": specialization_items,
                "perk_suggestions": perk_suggestions,
                "wellbeing_suggestions": wellbeing_suggestions,
                "fixed_bonus_lines": fixed_bonus_lines,
                "fixed_extra_bonuses": fixed_extra_bonuses,
            },
            {
                "safe_int": self._safe_int,
                "build_command": self.build_roll20_command,
                "compact_text": self.build_compact_preview_text,
                "specialization_preview": self.build_specialization_preview_text,
                "resolve_roll_asset_path": resolve_roll_asset_path,
                "log_debug": log_debug,
                "log_info": log_info,
            },
            {
                "roll_layout": roll_layout,
                "checkbox_style": checkbox_style,
            },
        )

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
        log_debug(
            "inventory",
            f"INVENTORY money Gulden={money['gulden']} Schilling={money['schilling']} "
            f"Heller={money['heller']} Pfifferling={money['pfifferling']}",
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
                log_debug("inventory", f"INVENTORY MAP block not found: {section_id}")
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
            log_debug("inventory", f"INVENTORY MAP section {section_id} header={section['header']} rows={len(section['rows'])}")
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
            log_warning("inventory", "more dynamic sections found than slots")
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

    def _normalize_magic_text(self, value):
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

    def _magic_cell_sort_key(self, cell_ref):
        match = re.match(r"^([A-Z]+)(\d+)$", str(cell_ref).strip().upper())
        if not match:
            return (0, 0)
        return (int(match.group(2)), self._col_letters_to_index(match.group(1)))

    def _magic_cache_text(self, sheet_cache, cell_ref):
        cell_data = sheet_cache.get(cell_ref)
        value = cell_data.get("value") if isinstance(cell_data, dict) else cell_data
        if value is None:
            return ""
        return str(value).strip()

    def get_magic_sheet_cache(self):
        exact_candidates = {"magie", "magic"}
        cache = self.loader.cell_cache
        if not isinstance(cache, dict):
            log_warning("magic", "sheet not found")
            return "", {}

        for sheet_name, sheet_cache in cache.items():
            normalized = self._normalize_magic_text(sheet_name)
            if normalized in exact_candidates and isinstance(sheet_cache, dict):
                if self._magic_print_mapping_enabled():
                    log_debug("magic", f"sheet found: {sheet_name} cells={len(sheet_cache)}")
                return sheet_name, sheet_cache

        for sheet_name, sheet_cache in cache.items():
            normalized = self._normalize_magic_text(sheet_name)
            if ("magie" in normalized or "magic" in normalized) and isinstance(sheet_cache, dict):
                if self._magic_print_mapping_enabled():
                    log_debug("magic", f"sheet found: {sheet_name} cells={len(sheet_cache)}")
                return sheet_name, sheet_cache

        log_warning("magic", "sheet not found")
        return "", {}

    def _find_magic_row_with_label(self, entries, labels):
        expected = {self._normalize_magic_text(label) for label in labels}
        for entry in entries:
            if entry.get("norm", "") in expected:
                return int(entry.get("row", 0))
        return 0

    def _find_magic_header_column(self, header_entries, start_row, header_labels):
        candidates = [self._normalize_magic_text(v) for v in header_labels]
        for row in range(start_row, start_row + 4):
            for entry in header_entries:
                if int(entry.get("row", 0)) != row:
                    continue
                norm = str(entry.get("norm", ""))
                if norm in candidates:
                    return int(entry.get("col", 0)), row
        return 0, 0

    def analyze_magic_sheet(self):
        sheet_name, sheet_cache = self.get_magic_sheet_cache()
        empty = {"sheet": "", "upgrade_table": {"mapping": {}, "rows": []}, "spells": {"mapping": {}, "rows": []}}
        if not sheet_name or not isinstance(sheet_cache, dict) or not sheet_cache:
            self.magic_analysis = empty
            return self.magic_analysis

        entries = []
        for cell_ref in sheet_cache.keys():
            text = self._magic_cache_text(sheet_cache, cell_ref)
            row, col = self._magic_cell_sort_key(cell_ref)
            if row <= 0 or col <= 0:
                continue
            entries.append(
                {"cell": str(cell_ref).upper(), "row": row, "col": col, "text": text, "norm": self._normalize_magic_text(text)}
            )
        entries.sort(key=lambda item: (item["row"], item["col"]))

        upgrade_anchor_row = self._find_magic_row_with_label(entries, ["Upgrade Tabelle"])
        upgrade_mapping = {}
        upgrade_rows = []
        if upgrade_anchor_row > 0:
            if self._magic_print_mapping_enabled():
                log_debug("magic", f"MAGIC UPGRADE TABLE start={upgrade_anchor_row}")
            expected_labels = [
                "Base",
                "Dice Up I",
                "Dice Up II",
                "Dice Up III",
                "Dice Up IV",
                "Dice Up V",
                "Scale Up I",
                "Scale Up II",
                "Scale Up III",
                "Scale Up IV",
                "Scale Up V",
            ]
            label_to_row = {}
            for entry in entries:
                if entry["row"] <= upgrade_anchor_row:
                    continue
                normalized_text = self._normalize_magic_text(entry.get("text", ""))
                for label in expected_labels:
                    if normalized_text == self._normalize_magic_text(label) and label not in label_to_row:
                        label_to_row[label] = int(entry["row"])
            if label_to_row:
                data_cols = []
                for label in expected_labels:
                    row_index = label_to_row.get(label)
                    if not row_index:
                        continue
                    label_col = 0
                    for entry in entries:
                        if int(entry.get("row", 0)) == row_index and self._normalize_magic_text(entry.get("text", "")) == self._normalize_magic_text(label):
                            label_col = int(entry.get("col", 0))
                            break
                    row_values = []
                    row_cells = []
                    for col_index in range(label_col + 1, label_col + 16):
                        cell_ref = f"{self._col_index_to_letters(col_index)}{row_index}"
                        value = self._magic_cache_text(sheet_cache, cell_ref)
                        if value:
                            row_values.append(value)
                            row_cells.append(cell_ref)
                            data_cols.append(col_index)
                    upgrade_rows.append({"label": label, "row": row_index, "values": row_values, "cells": row_cells})
                    if self._magic_print_rows_enabled():
                        log_debug("magic", f'MAGIC UPGRADE ROW label="{label}" values={row_values}')
                if data_cols:
                    unique_cols = sorted(set(data_cols))
                    upgrade_mapping = {"start_row": upgrade_anchor_row, "value_columns": [self._col_index_to_letters(c) for c in unique_cols]}

        magic_anchor_row = self._find_magic_row_with_label(entries, ["Magie", "Magic"])
        spell_mapping = {}
        spell_rows = []
        if magic_anchor_row > 0:
            school_col, header_row = self._find_magic_header_column(entries, magic_anchor_row, ["Magieschule", "School"])
            info_col, _ = self._find_magic_header_column(entries, magic_anchor_row, ["Info"])
            prepared_col, _ = self._find_magic_header_column(entries, magic_anchor_row, ["Vorbereiteter Zauber", "Prepared Spell"])
            charge_col, _ = self._find_magic_header_column(entries, magic_anchor_row, ["Ladung", "Charge"])
            duration_col, _ = self._find_magic_header_column(entries, magic_anchor_row, ["Dauer", "Duration"])
            effect_col, _ = self._find_magic_header_column(entries, magic_anchor_row, ["Effekt", "Effect"])

            if header_row > 0 and all(c > 0 for c in [school_col, info_col, prepared_col, charge_col, duration_col, effect_col]):
                data_start_row = header_row + 1
                spell_mapping = {
                    "sheet": sheet_name,
                    "start_row": magic_anchor_row,
                    "header_row": header_row,
                    "data_start_row": data_start_row,
                    "columns": {
                        "school": self._col_index_to_letters(school_col),
                        "info": self._col_index_to_letters(info_col),
                        "prepared_spell": self._col_index_to_letters(prepared_col),
                        "charge": self._col_index_to_letters(charge_col),
                        "duration": self._col_index_to_letters(duration_col),
                        "effect": self._col_index_to_letters(effect_col),
                    },
                }
                if self._magic_print_mapping_enabled():
                    log_debug("magic", f"MAGIC SPELL MAP start_row={magic_anchor_row} data_start_row={data_start_row}")
                    for key, col_letters in spell_mapping["columns"].items():
                        log_debug("magic", f"MAGIC SPELL COLUMN {key}={col_letters}")
                max_scan_rows = 25
                try:
                    max_scan_rows = max(1, min(50, int(self.magic_layout_config.get("magic_screen", {}).get("spell_table", {}).get("max_scan_rows", 25))))
                except Exception:
                    max_scan_rows = 25
                for offset in range(max_scan_rows):
                    row_index = data_start_row + offset
                    row_data = {"row": row_index, "row_index": row_index, "values": {}, "cells": {}}
                    has_value = False
                    for key, col_letters in spell_mapping["columns"].items():
                        cell_ref = f"{col_letters}{row_index}"
                        value = self._magic_cache_text(sheet_cache, cell_ref)
                        row_data["values"][key] = value
                        # Keep mapped sheet coordinates writable even when currently empty.
                        row_data["cells"][key] = cell_ref
                        row_data[key] = value
                        if value:
                            has_value = True
                    spell_rows.append(row_data)
                    if self._magic_print_rows_enabled() and (has_value or offset < 3):
                        log_debug("magic", f'MAGIC SPELL ROW row={row_index} school="{row_data["values"].get("school", "")}" prepared_spell="{row_data["values"].get("prepared_spell", "")}" charge="{row_data["values"].get("charge", "")}" duration="{row_data["values"].get("duration", "")}"')

        self.magic_analysis = {"sheet": sheet_name, "upgrade_table": {"mapping": upgrade_mapping, "rows": upgrade_rows}, "spells": {"mapping": spell_mapping, "rows": spell_rows}}
        return self.magic_analysis

    def render_equipment_screen(self):
        if self.content_layer is None:
            return
        return render_equipment_section(
            self,
            self.content_layer,
            self.load_equipment_layout_config(),
        )
    def render_inventory_screen(self):
        return inventory_section.render_inventory_screen(self)
    def render_notes_screen(self):
        if self.content_layer is None:
            return
        layout_config = self.load_notes_layout_config()
        default_screen_cfg = self.get_default_notes_layout_config().get("notes_screen", {})
        return render_notes_section(
            self.content_layer,
            layout_config,
            default_screen_cfg,
            {
                "safe_int": self._safe_int,
                "create_panel_text": self.create_panel_text,
                "get_text": self._get_notes_text_from_meta,
                "save_text": self._save_notes_text_to_meta,
                "has_active_character": lambda: bool(str(getattr(self.loader, "active_cache_path", "") or "")),
                "log_debug": log_debug,
            },
        )

    def render_browser_screen(self):
        return browser_section.render_browser_section(self)

    def preload_browser_if_enabled(self):
        try:
            cfg = browser_section.load_browser_layout_config(self).get("browser_screen", {})
            if not isinstance(cfg, dict) or not bool(cfg.get("preload_on_start", False)):
                return
            if browser_section.ensure_browser_created(self):
                if self.current_main_section in ("browser", "webbrowser") or bool(cfg.get("show_on_start", False)):
                    browser_section.show_browser_section(self)
                else:
                    browser_section.hide_browser_section(self)
        except Exception as exc:
            log_warning("browser", f"browser preload failed: {exc}")

    def reset_browser_runtime_state(self, destroy_webview=True):
        for attr in (
            "_browser_url_edit",
            "_browser_web_view",
            "_browser_fallback_label",
            "_browser_container",
        ):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            try:
                if hasattr(widget, "url"):
                    current_url = widget.url()
                    if current_url is not None:
                        self._browser_last_url = current_url.toString()
            except RuntimeError:
                pass
            except Exception:
                pass
            if destroy_webview:
                try:
                    widget.hide()
                except RuntimeError:
                    pass
                except Exception:
                    pass
                try:
                    widget.setParent(None)
                    widget.deleteLater()
                except RuntimeError:
                    pass
                except Exception:
                    pass

        self._browser_container = None
        self._browser_web_view = None
        self._browser_url_edit = None
        self._browser_fallback_label = None
        self._browser_popup_pages = []
        self._browser_initialized = False

    def render_magic_screen(self):
        if self.content_layer is None:
            return
        layout_config = self.load_magic_layout_config()
        default_screen_cfg = self.get_default_magic_layout_config().get("magic_screen", {})

        def save_cell_value(sheet_name, cell_ref, new_value):
            self.loader.set_cell_value(str(sheet_name or "Magie"), cell_ref, new_value)
            self.loader.save_active_character_json()

        return render_magic_section(
            self.content_layer,
            layout_config,
            default_screen_cfg,
            {
                "safe_int": self._safe_int,
                "create_panel_text": self.create_panel_text,
                "analyze_magic_sheet": self.analyze_magic_sheet,
                "clear_table_bindings": self._magic_table_bindings.clear,
                "register_table_binding": lambda table, binding: self._magic_table_bindings.__setitem__(id(table), binding),
                "get_table_binding": lambda table: self._magic_table_bindings.get(id(table), {}),
                "set_rendering": lambda value: setattr(self, "_magic_rendering", bool(value)),
                "is_rendering": lambda: bool(self._magic_rendering),
                "print_mapping_enabled": self._magic_print_mapping_enabled,
                "save_cell_value": save_cell_value,
                "log_debug": log_debug,
            },
        )

    def on_inventory_category_clicked(self, category_id):
        return inventory_section.on_inventory_category_clicked(self, category_id)
    def rename_inventory_category(self, slot_id):
        return inventory_section.rename_inventory_category(self, slot_id)
    def render_inventory_category_tabs(self, parent, screen_cfg, categories):
        return inventory_section.render_inventory_category_tabs(self, parent, screen_cfg, categories)
    def render_inventory_active_category_table(self, parent, screen_cfg, categories):
        return inventory_section.render_inventory_active_category_table(self, parent, screen_cfg, categories)
    def render_inventory_single_table_widget(self, parent, table_cfg, category):
        return inventory_section.render_inventory_single_table_widget(self, parent, table_cfg, category)
    def render_inventory_money_panel(self, parent, money_cfg, money):
        return inventory_section.render_inventory_money_panel(self, parent, money_cfg, money)
    def on_inventory_money_edit_finished(self, field):
        return inventory_section.on_inventory_money_edit_finished(self, field)
    def _inventory_parse_non_negative_int(self, value):
        return inventory_section._inventory_parse_non_negative_int(self, value)
    def money_to_pfifferling(self, gulden, schilling, heller, pfifferling):
        return inventory_section.money_to_pfifferling(self, gulden, schilling, heller, pfifferling)
    def pfifferling_to_money(self, total_pfifferling):
        return inventory_section.pfifferling_to_money(self, total_pfifferling)
    def _inventory_get_wallet_money_values(self):
        return inventory_section._inventory_get_wallet_money_values(self)
    def on_inventory_money_delta_apply(self, op):
        return inventory_section.on_inventory_money_delta_apply(self, op)
    def get_inventory_wrapped_text_height(self, text, width, font_size, max_lines=0):
        return inventory_section.get_inventory_wrapped_text_height(self, text, width, font_size, max_lines)
    def build_inventory_text_block_html(self, rows, text_cfg):
        return inventory_section.build_inventory_text_block_html(self, rows, text_cfg)
    def render_inventory_text_block_tables(self, parent, tables_cfg, sections):
        return inventory_section.render_inventory_text_block_tables(self, parent, tables_cfg, sections)
    def render_inventory_table_widget_tables(self, parent, tables_cfg, sections):
        return inventory_section.render_inventory_table_widget_tables(self, parent, tables_cfg, sections)
    def _apply_inventory_row_heights(self, table, min_row_h, max_row_h):
        return inventory_section._apply_inventory_row_heights(self, table, min_row_h, max_row_h)
    def _is_inventory_row_empty(self, row):
        return inventory_section._is_inventory_row_empty(self, row)
    def _next_inventory_custom_row_index(self, rows, slot_id):
        return inventory_section._next_inventory_custom_row_index(self, rows, slot_id)
    def _append_inventory_visual_empty_rows(self, table, binding, count):
        return inventory_section._append_inventory_visual_empty_rows(self, table, binding, count)
    def on_inventory_table_cell_changed(self, table, row_index, column_index):
        return inventory_section.on_inventory_table_cell_changed(self, table, row_index, column_index)
    def render_skills_screen(self):
        return skills_section.render_skills_section(self)

    def _get_skills_se_rows_from_meta(self):
        app_meta = getattr(self.loader, "app_meta", {})
        if not isinstance(app_meta, dict):
            return []
        custom_sections = app_meta.get("custom_sections", {})
        if not isinstance(custom_sections, dict):
            return []
        se_data = custom_sections.get("skills_se", {})
        if not isinstance(se_data, dict):
            return []
        rows = se_data.get("rows", [])
        if not isinstance(rows, list):
            return []
        sanitized = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            sanitized.append(
                {
                    "text": str(row.get("text", "") or ""),
                    "skill_key": str(row.get("skill_key", "") or ""),
                    "skill_name": str(row.get("skill_name", "") or ""),
                    "value": str(row.get("value", "") or ""),
                }
            )
        return sanitized

    def _save_skills_se_rows_to_meta(self, rows):
        try:
            if not isinstance(self.loader.app_meta, dict):
                self.loader.app_meta = {}
            custom_sections = self.loader.app_meta.setdefault("custom_sections", {})
            if not isinstance(custom_sections, dict):
                custom_sections = {}
                self.loader.app_meta["custom_sections"] = custom_sections
            clean_rows = []
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    clean_rows.append(
                        {
                            "text": str(row.get("text", "") or ""),
                            "skill_key": str(row.get("skill_key", "") or ""),
                            "skill_name": str(row.get("skill_name", "") or ""),
                            "value": str(row.get("value", "") or ""),
                        }
                    )
            custom_sections["skills_se"] = {"rows": clean_rows}
            self.loader.save_active_character_json()
            if self.skills_debug_sources:
                log_debug("save", "SKILLS SE SAVE saved")
            return True
        except Exception as exc:
            log_error("save", f"SKILLS SE SAVE ERROR {exc}")
            return False

    def on_skills_se_table_cell_changed(self, table, min_rows, add_rows_when_last_filled):
        if self._skills_se_loading:
            return
        if table is None:
            return
        rows = []
        for row_index in range(table.rowCount()):
            text_item = table.item(row_index, 0)
            value_item = table.item(row_index, 1)
            text_value = str(text_item.text() if text_item is not None else "")
            skill_key = ""
            skill_name = text_value
            if text_item is not None:
                skill_key = str(text_item.data(Qt.UserRole) or "").strip()
                if skill_key:
                    skill_name = str(text_item.data(Qt.UserRole + 1) or text_value).strip() or text_value
            cell_value = str(value_item.text() if value_item is not None else "")
            rows.append(
                {
                    "text": text_value,
                    "skill_key": skill_key,
                    "skill_name": skill_name,
                    "value": cell_value,
                }
            )

        last_index = table.rowCount() - 1
        if last_index >= 0:
            last = rows[last_index]
            if str(last.get("text", "")).strip() or str(last.get("value", "")).strip():
                self._skills_se_loading = True
                try:
                    for _ in range(max(0, int(add_rows_when_last_filled))):
                        new_row = table.rowCount()
                        table.insertRow(new_row)
                        skill_item = QTableWidgetItem("")
                        skill_item.setFlags(
                            (skill_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled) & ~Qt.ItemIsEditable
                        )
                        value_item = QTableWidgetItem("")
                        value_item.setFlags(value_item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                        table.setItem(new_row, 0, skill_item)
                        table.setItem(new_row, 1, value_item)
                        rows.append({"text": "", "skill_key": "", "skill_name": "", "value": ""})
                finally:
                    self._skills_se_loading = False

        while len(rows) < max(0, int(min_rows)):
            rows.append({"text": "", "skill_key": "", "skill_name": "", "value": ""})

        table.blockSignals(True)
        try:
            for r in range(table.rowCount()):
                for c in (0, 1):
                    item = table.item(r, c)
                    if item is None:
                        item = QTableWidgetItem("")
                        if c == 0:
                            item.setFlags((item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled) & ~Qt.ItemIsEditable)
                        else:
                            item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                        table.setItem(r, c, item)
                    value = rows[r]["text"] if c == 0 else rows[r]["value"]
                    item.setToolTip(value if value else "")
        finally:
            table.blockSignals(False)

        self._save_skills_se_rows_to_meta(rows)
        if str(self.current_skill_category).strip().lower() == "se" and str(self.current_main_section) in ("skills", "fertigkeiten"):
            self.show_main_section("skills")

    def get_se_skill_choices(self):
        choices = []
        if not isinstance(self.skill_source_infos, dict):
            return choices
        category_titles = {}
        try:
            defs = self.load_skill_definitions()
            categories = defs.get("categories", []) if isinstance(defs, dict) else []
            if isinstance(categories, list):
                for cat in categories:
                    if not isinstance(cat, dict):
                        continue
                    cid = str(cat.get("id", "") or "")
                    title = str(cat.get("title", cid) or cid)
                    if cid:
                        category_titles[cid] = title
        except Exception:
            pass

        for source_key, info in self.skill_source_infos.items():
            if not isinstance(info, dict):
                continue
            if info.get("row") is None:
                continue
            name = str(info.get("display_name", "") or "").strip()
            if not name:
                continue
            category_id = str(info.get("category_id", "") or "")
            cat_title = category_titles.get(category_id, category_id or "-")
            display = f"{name} [{cat_title}]"
            choices.append(
                {
                    "skill_key": str(source_key),
                    "skill_name": name,
                    "display": display,
                }
            )
        choices.sort(key=lambda it: str(it.get("skill_name", "")).lower())
        return choices

    def open_skills_se_skill_picker(self, table, row):
        if table is None or row < 0:
            return
        skill_choices = self.get_se_skill_choices()
        if not skill_choices:
            return
        display_items = [str(it.get("display", "")) for it in skill_choices]
        current_item = table.item(row, 0)
        current_key = str(current_item.data(Qt.UserRole) or "").strip() if current_item is not None else ""
        current_index = 0
        for idx, it in enumerate(skill_choices):
            if str(it.get("skill_key", "")) == current_key:
                current_index = idx
                break
        selected_display, ok = QInputDialog.getItem(
            self,
            "Fertigkeit wählen",
            "Fertigkeit:",
            display_items,
            current_index,
            False,
        )
        if not ok:
            return
        selected = None
        for it in skill_choices:
            if str(it.get("display", "")) == str(selected_display):
                selected = it
                break
        if not isinstance(selected, dict):
            return

        self._skills_se_loading = True
        table.blockSignals(True)
        try:
            item = table.item(row, 0)
            if item is None:
                item = QTableWidgetItem("")
                table.setItem(row, 0, item)
            skill_name = str(selected.get("skill_name", "") or "")
            skill_key = str(selected.get("skill_key", "") or "")
            item.setText(skill_name)
            item.setToolTip(skill_name)
            item.setData(Qt.UserRole, skill_key)
            item.setData(Qt.UserRole + 1, skill_name)
            if self.skills_debug_sources:
                log_debug("skills", f'SKILLS SE SELECT row={row} skill_key="{skill_key}" skill_name="{skill_name}"')
        finally:
            table.blockSignals(False)
            self._skills_se_loading = False

        self.on_skills_se_table_cell_changed(table, table.rowCount(), 0)

    def _normalize_se_upgrade_text(self, value):
        text = str(value or "").strip().lower()
        text = (
            text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
        )
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _parse_int_for_se_upgrade(self, value):
        text = str(value or "").strip()
        if not text:
            return 0
        text = text.replace(",", ".")
        try:
            return int(float(text))
        except Exception:
            return 0

    def _extract_threshold_numbers_from_row(self, sheet_name, row, start_col_idx, max_col_idx):
        values = []
        blanks_after_values = 0
        for col_idx in range(start_col_idx, max_col_idx + 1):
            col_name = self._excel_col_name(col_idx)
            number = self.get_numeric_cache_value(sheet_name, f"{col_name}{row}")
            if number is None:
                if values:
                    blanks_after_values += 1
                    if blanks_after_values >= 3:
                        break
                continue
            values.append(int(number))
            blanks_after_values = 0
            if len(values) >= 4:
                break
        return values

    def _excel_col_name(self, idx):
        idx = int(idx)
        if idx < 1:
            return "A"
        name = []
        while idx > 0:
            idx, rem = divmod(idx - 1, 26)
            name.append(chr(65 + rem))
        return "".join(reversed(name))

    def _get_category_upgrade_costs(self, category_id, sheet_name):
        default_se = [1, 5, 25, 125]
        default_xp = [4, 20, 100, 375]
        block = self.get_skill_block_config_for_category(category_id)
        if not isinstance(block, dict):
            return default_se, default_xp, True

        row_min = self._safe_int(block.get("row_min", 0), 0)
        if row_min <= 0:
            return default_se, default_xp, True

        label_col = str(block.get("value_formula_col", "AD") or "AD")
        search_start = max(1, row_min - 14)
        search_end = max(search_start, row_min + 2)
        se_row = None
        xp_row = None
        for row in range(search_start, search_end + 1):
            label_text = self.get_clean_skill_cache_text(sheet_name, f"{label_col}{row}").lower()
            if not label_text:
                continue
            if "se benoetigt" in self._normalize_se_upgrade_text(label_text):
                se_row = row
            elif "exp benoetigt" in self._normalize_se_upgrade_text(label_text):
                xp_row = row

        if se_row is None or xp_row is None:
            return default_se, default_xp, True

        start_idx = self._excel_col_index(label_col) + 1
        end_idx = self._excel_col_index("BZ")
        se_values = self._extract_threshold_numbers_from_row(sheet_name, se_row, start_idx, end_idx)
        xp_values = self._extract_threshold_numbers_from_row(sheet_name, xp_row, start_idx, end_idx)
        if not se_values or not xp_values:
            return default_se, default_xp, True
        return se_values, xp_values, False

    def _excel_col_index(self, col_name):
        col_name = str(col_name or "").strip().upper()
        if not col_name:
            return 1
        value = 0
        for ch in col_name:
            if not ("A" <= ch <= "Z"):
                continue
            value = value * 26 + (ord(ch) - ord("A") + 1)
        return value or 1

    def build_se_upgrade_candidates(self, se_rows, available_xp):
        suggestions = []
        if not isinstance(se_rows, list):
            return {"status": "no_se_entries", "items": [], "groups": {}}
        bound_entries = {}
        for idx, row in enumerate(se_rows):
            if not isinstance(row, dict):
                continue
            skill_key = str(row.get("skill_key", "") or "").strip()
            skill_name = str(row.get("skill_name", "") or row.get("text", "")).strip()
            se_value = max(0, self._parse_int_for_se_upgrade(row.get("value", "")))
            if not skill_key:
                legacy_text = str(row.get("text", "") or "").strip()
                if legacy_text and self.skills_debug_sources:
                    log_debug("skills", f'SKILLS SE LEGACY row={idx} text="{legacy_text}" ignored_for_upgrade=no_skill_key')
                continue
            entry = bound_entries.setdefault(
                skill_key,
                {
                    "row_indices": [],
                    "skill_key": skill_key,
                    "skill_name": skill_name,
                    "value": 0,
                },
            )
            entry["row_indices"].append(idx)
            if skill_name:
                entry["skill_name"] = skill_name
            entry["value"] += int(se_value)
        if not bound_entries:
            return {"status": "no_bound_entries", "items": [], "groups": {}}

        if not isinstance(self.skill_source_infos, dict) or not self.skill_source_infos:
            return {"status": "no_upgrade_data", "items": [], "groups": {}}
        if self.skills_debug_sources:
            log_debug(
                "skills",
                f"SKILLS UPGRADE ROWS bound_rows={sum(len(v.get('row_indices', [])) for v in bound_entries.values())} "
                f"merged_skills={len(bound_entries)}",
            )
        for skill_key, merged in bound_entries.items():
            if len(merged.get("row_indices", [])) > 1 and self.skills_debug_sources:
                log_debug(
                    "skills",
                    f"SKILLS UPGRADE MERGE skill_key={skill_key} total_se={merged.get('value', 0)} "
                    f"rows={merged.get('row_indices', [])}",
                )

        mapping = self.get_skill_sheet_mapping_config()
        sheet_name = str(mapping.get("sheet", "Fertigkeiten"))
        costs_cache = {}
        missing_costs = False
        for entry in bound_entries.values():
            source_key = str(entry.get("skill_key", "") or "")
            info = self.skill_source_infos.get(source_key)
            if not isinstance(info, dict):
                suggestions.append(
                    {
                        "skill_name": str(entry.get("skill_name", "") or source_key),
                        "category_id": "",
                        "needed_se": 0,
                        "available_se": int(entry.get("value", 0)),
                        "needed_xp": 0,
                        "available_xp": int(available_xp),
                        "status": "broken_link",
                    }
                )
                if self.skills_debug_sources:
                    log_debug(
                        "skills",
                        f'SKILLS UPGRADE SE BROKEN_LINK rows={entry.get("row_indices")} skill_key={source_key}',
                    )
                continue
            if not isinstance(info, dict):
                continue
            row = info.get("row")
            if row is None:
                continue
            category_id = str(info.get("category_id", "") or "")
            skill_name = str(info.get("display_name", "") or entry.get("skill_name", "")).strip()
            if not category_id or not skill_name:
                continue

            if category_id not in costs_cache:
                se_costs, xp_costs, used_fallback = self._get_category_upgrade_costs(category_id, sheet_name)
                costs_cache[category_id] = (se_costs, xp_costs)
                if self.skills_debug_sources:
                    source = "fallback" if used_fallback else "sheet"
                    log_debug(
                        "skills",
                        f"SKILLS UPGRADE COSTS category={category_id} se={se_costs} exp={xp_costs} {source}",
                    )
            se_costs, xp_costs = costs_cache[category_id]
            if not se_costs or not xp_costs:
                missing_costs = True
                continue

            try:
                display_value = int(str(info.get("display_value", "") or "0"))
            except Exception:
                display_value = 0
            next_index = 1 if display_value > 0 else 0
            if next_index >= len(se_costs) or next_index >= len(xp_costs):
                suggestions.append(
                    {
                        "skill_name": skill_name,
                        "category_id": category_id,
                        "needed_se": 0,
                        "available_se": int(entry.get("value", 0)),
                        "needed_xp": 0,
                        "available_xp": int(available_xp),
                        "status": "unknown",
                        "skill_key": source_key,
                    }
                )
                continue

            needed_se = int(se_costs[next_index])
            needed_xp = int(xp_costs[next_index])
            available_se = int(entry.get("value", 0))
            if self.skills_debug_sources:
                log_debug(
                    "skills",
                    f'SKILLS UPGRADE SE LINK rows={entry.get("row_indices")} '
                    f'skill_key="{source_key}" skill="{skill_name}" se={available_se}',
                )

            xp_ok = int(available_xp) >= needed_xp
            se_ok = int(available_se) >= needed_se
            if se_ok and xp_ok:
                status = "possible"
            elif xp_ok and not se_ok:
                status = "missing_se"
            elif se_ok and not xp_ok:
                status = "missing_xp"
            else:
                status = "missing_both"

            if self.skills_debug_sources:
                log_debug(
                    "skills",
                    f'SKILLS UPGRADE RESULT skill="{skill_name}" needed_se={needed_se} '
                    f"available_se={available_se} needed_xp={needed_xp} available_xp={available_xp} status={status}",
                )

            suggestions.append(
                {
                    "skill_name": skill_name,
                    "category_id": category_id,
                    "needed_se": needed_se,
                    "available_se": available_se,
                    "needed_xp": needed_xp,
                    "available_xp": int(available_xp),
                    "status": status,
                    "skill_key": source_key,
                }
            )

        if not suggestions:
            if missing_costs:
                return {"status": "no_costs", "items": [], "groups": {}}
            return {"status": "no_upgrade_data", "items": [], "groups": {}}

        groups = {
            "possible": [],
            "missing_xp": [],
            "missing_se": [],
            "missing_both": [],
            "unknown": [],
            "broken_link": [],
        }
        for item in suggestions:
            groups.setdefault(item["status"], []).append(item)
        for key in groups:
            groups[key] = sorted(
                groups[key],
                key=lambda it: (it["skill_name"].lower(), it["needed_se"], it["needed_xp"]),
            )
        if self.skills_debug_sources:
            log_debug(
                "skills",
                f'SKILLS UPGRADE GROUPS possible={len(groups.get("possible", []))} '
                f'missing_xp={len(groups.get("missing_xp", []))} '
                f'missing_se={len(groups.get("missing_se", []))} '
                f'missing_both={len(groups.get("missing_both", []))} '
                f'unknown={len(groups.get("unknown", []))}',
            )
        return {"status": "ok", "items": suggestions, "groups": groups}

    def render_skills_se_table(self, parent, screen_cfg, se_cfg):
        return skills_section.render_skills_se_table(self, parent, screen_cfg, se_cfg)

    def on_skill_category_clicked(self, category_id):
        self.current_skill_category = str(category_id)
        section_id = self.current_main_section
        if section_id not in ("skills", "fertigkeiten"):
            section_id = "skills"
        self.show_main_section(section_id)

    def render_skills_table(self, parent, table_cfg, category, attribute_map):
        return skills_section.render_skills_table(self, parent, table_cfg, category, attribute_map)

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

    def _resolve_data_map_cell_ref(self, mapping_entry, default_sheet):
        sheet_name = str(default_sheet or "Charakterbogen")
        cell_ref = None
        if isinstance(mapping_entry, str):
            cell_ref = mapping_entry.strip()
        elif isinstance(mapping_entry, dict):
            sheet_name = str(mapping_entry.get("sheet", sheet_name))
            raw_cell = mapping_entry.get("cell")
            if isinstance(raw_cell, str):
                cell_ref = raw_cell.strip()
        if not cell_ref:
            return None, None
        return sheet_name, cell_ref

    def _on_character_field_edited(self, field_key, sheet_name, cell_ref, value, tag="CHARACTER EDIT"):
        if self._character_rendering:
            return
        if not sheet_name or not cell_ref:
            log_debug("character", f"CHARACTER EDIT SKIP field={field_key} reason=no_cell_ref")
            return
        new_value = "" if value is None else str(value)
        log_debug("character", f"{tag} field={field_key} cell={cell_ref} value={new_value}")
        self.loader.set_cell_value(sheet_name, cell_ref, new_value)
        self._recalculate_after_user_edit(
            reason=f"{sheet_name}!{cell_ref}",
            save=bool((self._character_edit_cfg or {}).get("save_on_change", True)),
            rerender=True,
        )

    def _character_resource_config(self):
        return {
            "hp": {
                "label": "HP",
                "title": "HP verwalten",
                "current_field": "hp_current",
                "max_field": "hp_max",
                "roll_title": "Regeneration",
            },
            "mp": {
                "label": "MP",
                "title": "MP verwalten",
                "current_field": "mp_current",
                "max_field": "mp_max",
                "roll_title": "Regeneration",
                "roll_command": "/r 1d4",
            },
            "lifeforce": {
                "label": "LifeForce",
                "title": "LifeForce verwalten",
                "current_field": "lifeforce_current",
                "max_field": "lifeforce_max",
                "roll_title": "LifeForce-Regeneration",
                "roll_command": "/r 1d20",
            },
            "sanity": {
                "label": "Sanity",
                "title": "Sanity verwalten",
                "current_field": "sanity_current",
                "max_field": "sanity_max",
                "roll_title": "Sanity",
                "roll_command": "/r 1d20",
            },
            "faith": {
                "label": "Faith",
                "title": "Faith verwalten",
                "current_field": "faith_current",
                "max_field": "faith_max",
                "roll_title": "Faith",
                "roll_command": "/r 1d20",
            },
        }

    def _character_basic_map(self):
        character_screen = self.main_ui_layout_config.get("character_screen", {})
        data_map = character_screen.get("data_map", {}) if isinstance(character_screen, dict) else {}
        basic_map = data_map.get("basic", {}) if isinstance(data_map, dict) else {}
        return basic_map if isinstance(basic_map, dict) else {}

    def _character_default_sheet(self):
        character_screen = self.main_ui_layout_config.get("character_screen", {})
        data_map = character_screen.get("data_map", {}) if isinstance(character_screen, dict) else {}
        if isinstance(data_map, dict):
            return str(data_map.get("sheet", "Charakterbogen") or "Charakterbogen")
        return "Charakterbogen"

    def _character_int_value(self, sheet_name, cell_ref, fallback=0):
        value = self.get_numeric_cache_value(sheet_name, cell_ref)
        if value is None:
            return int(fallback)
        return int(math.floor(float(value) + 0.5)) if float(value) >= 0 else int(math.ceil(float(value) - 0.5))

    def _get_character_resource_data(self, resource_id):
        cfg = self._character_resource_config().get(resource_id)
        if not cfg:
            return None
        basic_map = self._character_basic_map()
        default_sheet = self._character_default_sheet()
        current_src = basic_map.get(cfg["current_field"], "")
        max_src = basic_map.get(cfg["max_field"], "")
        current_sheet, current_cell = self._resolve_data_map_cell_ref(current_src, default_sheet)
        max_sheet, max_cell = self._resolve_data_map_cell_ref(max_src, default_sheet)
        if not current_sheet or not current_cell:
            return None
        current_value = self._character_int_value(current_sheet, current_cell, 0)
        max_value = self._character_int_value(max_sheet, max_cell, current_value) if max_sheet and max_cell else current_value
        max_value = max(0, max_value)
        return {
            "config": cfg,
            "current_sheet": current_sheet,
            "current_cell": current_cell,
            "max_sheet": max_sheet,
            "max_cell": max_cell,
            "current": max(0, current_value),
            "max": max_value,
        }

    def _character_body_value(self):
        character_screen = self.main_ui_layout_config.get("character_screen", {})
        data_map = character_screen.get("data_map", {}) if isinstance(character_screen, dict) else {}
        attributes_map = data_map.get("attributes", {}) if isinstance(data_map, dict) else {}
        body_map = attributes_map.get("body", {}) if isinstance(attributes_map, dict) else {}
        body_src = body_map.get("value", body_map.get("header", ""))
        sheet_name, cell_ref = self._resolve_data_map_cell_ref(body_src, self._character_default_sheet())
        if not sheet_name or not cell_ref:
            return 0
        return self._character_int_value(sheet_name, cell_ref, 0)

    def _character_resource_roll_command(self, resource_id, cfg):
        if resource_id == "hp":
            return f"/r 1d4+{self._character_body_value()}"
        return str(cfg.get("roll_command", "/r 1d20"))

    def _set_character_resource_values(self, updates, reason):
        changed = []
        for sheet_name, cell_ref, value in updates:
            if not sheet_name or not cell_ref:
                continue
            normalized = str(int(max(0, value)))
            self.loader.set_cell_value(sheet_name, cell_ref, normalized)
            changed.append(f"{sheet_name}!{cell_ref}")
        if changed:
            self._recalculate_after_user_edit(
                reason=reason or ", ".join(changed),
                save=bool((self._character_edit_cfg or {}).get("save_on_change", True)),
                rerender=True,
            )

    def _make_character_resource_label_clickable(self, label, resource_id):
        if resource_id not in self._character_resource_config():
            return label
        label.setCursor(Qt.PointingHandCursor)
        label.setProperty("character_resource_id", resource_id)
        label.installEventFilter(self)
        return label

    def open_character_resource_dialog(self, resource_id):
        resource_id = str(resource_id or "").strip().lower()
        data = self._get_character_resource_data(resource_id)
        if not data:
            QMessageBox.information(self, "Ressource", "Ressourcenfeld nicht gefunden.")
            return

        cfg = data["config"]
        label = str(cfg.get("label", resource_id.upper()))

        def save_current(new_value, reason, reduce_lifeforce=False):
            updates = [(data["current_sheet"], data["current_cell"], int(new_value))]
            if reduce_lifeforce:
                lifeforce_data = self._get_character_resource_data("lifeforce")
                if lifeforce_data:
                    updates.append(
                        (
                            lifeforce_data["current_sheet"],
                            lifeforce_data["current_cell"],
                            max(0, int(lifeforce_data["current"]) - 1),
                        )
                    )
            self._set_character_resource_values(updates, reason)

        return open_resource_dialog(
            self,
            {
                "resource_id": resource_id,
                "label": label,
                "title": str(cfg.get("title", f"{label} verwalten")),
                "current": int(data["current"]),
                "max": int(data["max"]),
                "roll_title": str(cfg.get("roll_title", "Roll")),
                "roll_command": self._character_resource_roll_command(resource_id, cfg),
            },
            {"save_current": save_current},
            {
                "width": 390,
                "height": 260,
                "roll_layout": self.load_roll_dialog_layout_config(),
                "ui_layout": self.main_ui_layout_config,
                "asset_button_factory": self.create_dialog_asset_text_button,
                "load_ui_pixmap": self.load_ui_pixmap,
            },
        )

    def _open_hp_regen_dialog(self):
        return self.open_character_resource_dialog("hp")

    def _open_mp_regen_dialog(self):
        return self.open_character_resource_dialog("mp")

    def _open_lifeforce_regen_dialog(self):
        return self.open_character_resource_dialog("lifeforce")

    def _recalculate_after_user_edit(self, reason="", save=True, rerender=True):
        if self._recalc_in_progress:
            return
        if not isinstance(self.loader.cell_cache, dict):
            return
        self._recalc_in_progress = True
        try:
            reason_text = str(reason or "").strip() or "unknown"
            log_debug("calculation", f"RECALC after user edit: {reason_text}")
            self.parser.recalculate_cache(self.loader.cell_cache)
            if save:
                self.loader.save_active_character_json()
                log_debug("calculation", "RECALC saved active character")
            if rerender:
                if self.current_main_section == "character":
                    self.show_main_section("character")
                    log_debug("calculation", "RECALC refreshed section: character")
                if (
                    hasattr(self, "calculation_center_dialog")
                    and self.calculation_center_dialog is not None
                    and self.calculation_center_dialog.isVisible()
                ):
                    try:
                        self.calculation_center_dialog.refresh_data()
                        log_debug("calculation", "RECALC refreshed calculation center")
                    except Exception:
                        pass
        finally:
            self._recalc_in_progress = False

    def _character_edit_config(self):
        cfg = self.main_ui_layout_config.get("character_screen", {})
        edit = cfg.get("edit", {}) if isinstance(cfg, dict) else {}
        if not isinstance(edit, dict):
            edit = {}
        return {
            "enabled": bool(edit.get("enabled", False)),
            "save_on_change": bool(edit.get("save_on_change", True)),
            "debug": bool(edit.get("debug", False)),
            "basic_fields": bool(edit.get("basic_fields", True)),
            "attributes": bool(edit.get("attributes", True)),
            "perks": bool(edit.get("perks", True)),
            "disadvantages": bool(edit.get("disadvantages", True)),
            "wellbeing": bool(edit.get("wellbeing", True)),
            "edit_on": str(edit.get("edit_on", "double_click")).strip().lower() or "double_click",
            "text_editor": str(edit.get("text_editor", "dialog")).strip().lower() or "dialog",
            "empty_value": str(edit.get("empty_value", "")),
        }

    def _character_edit_allowed(self, section_key):
        cfg = self._character_edit_cfg if isinstance(self._character_edit_cfg, dict) else {}
        if not cfg.get("enabled", False):
            return False
        return bool(cfg.get(section_key, False))

    def _character_debug(self, message):
        cfg = self._character_edit_cfg if isinstance(self._character_edit_cfg, dict) else {}
        if cfg.get("debug", False):
            log_debug("character", str(message))

    def _character_paradigm_debug(self, message):
        cfg = self.main_ui_layout_config.get("character_screen", {})
        panel = cfg.get("paradigm_panel", {}) if isinstance(cfg, dict) else {}
        edit_cfg = panel.get("edit", {}) if isinstance(panel, dict) else {}
        if isinstance(edit_cfg, dict) and bool(edit_cfg.get("debug", False)):
            log_debug("character", str(message))

    def _parse_generic_cell_ref(self, cell_ref):
        match = re.match(r"^([A-Z]+)(\d+)$", str(cell_ref or "").strip().upper())
        if not match:
            return None
        row = int(match.group(2))
        col = self._col_letters_to_index(match.group(1))
        return row, col

    def _analyze_character_paradigm_area(self, default_sheet="Charakterbogen"):
        sheet_name = str(default_sheet or "Charakterbogen")
        sheet_cache = self.loader.cell_cache.get(sheet_name, {})
        if not isinstance(sheet_cache, dict) or not sheet_cache:
            return {
                "sheet": sheet_name,
                "label_cell": "",
                "columns": [],
                "rows": {},
                "names_row": 0,
            }

        normalized_cells = []
        for cell_ref, cell_data in sheet_cache.items():
            parsed = self._parse_generic_cell_ref(cell_ref)
            if not parsed:
                continue
            row, col = parsed
            value = cell_data.get("value") if isinstance(cell_data, dict) else cell_data
            text = str(value or "").strip()
            normalized_cells.append((cell_ref, row, col, text, text.lower()))

        label_entry = next((entry for entry in normalized_cells if entry[4] == "paradigmen"), None)
        if not label_entry:
            return {
                "sheet": sheet_name,
                "label_cell": "",
                "columns": [],
                "rows": {},
                "names_row": 0,
            }
        label_cell, label_row, label_col, _, _ = label_entry
        self._character_paradigm_debug(f"[CHARACTER PARADIGM] label found cell={label_cell}")

        row_by_label = {}
        for key in ("grad", "brand", "daily"):
            found = next(
                (
                    entry
                    for entry in normalized_cells
                    if entry[4] == key and label_row <= entry[1] <= label_row + 12
                ),
                None,
            )
            row_by_label[key] = int(found[1]) if found else 0
            self._character_paradigm_debug(
                f"[CHARACTER PARADIGM] {key} row={row_by_label[key] if row_by_label[key] else '-'}"
            )

        candidate_rows = []
        row_min = label_row
        row_max = row_by_label.get("grad") - 1 if row_by_label.get("grad") else label_row + 4
        for row in range(row_min, max(row_min, row_max) + 1):
            entries = [
                entry
                for entry in normalized_cells
                if entry[1] == row
                and entry[2] > label_col
                and entry[2] <= label_col + 28
                and entry[3]
                and entry[4] not in {"grad", "brand", "daily", "paradigmen"}
            ]
            if entries:
                candidate_rows.append((row, entries))
        name_row = 0
        name_columns = []
        if candidate_rows:
            candidate_rows.sort(key=lambda item: (-len(item[1]), item[0]))
            name_row, entries = candidate_rows[0]
            entries.sort(key=lambda item: item[2])
            name_columns = entries[:3]
        self._character_paradigm_debug(f"[CHARACTER PARADIGM] names row={name_row if name_row else '-'}")

        columns = []
        marker_count = 3
        row_cells = {"grad": [], "brand": [], "daily": []}
        for idx, entry in enumerate(name_columns):
            _, _, base_col, name_text, _ = entry
            col_data = {
                "index": idx,
                "name_cell": f"{self._col_index_to_letters(base_col)}{name_row}" if name_row else "",
                "name": name_text,
                "grad_cells": [],
                "brand_cells": [],
                "daily_cells": [],
            }
            for key in ("grad", "brand", "daily"):
                target_row = row_by_label.get(key, 0)
                cells = []
                if target_row > 0:
                    for offset in range(marker_count):
                        cell_ref = f"{self._col_index_to_letters(base_col + offset)}{target_row}"
                        cells.append(cell_ref)
                        row_cells[key].append(cell_ref)
                col_data[f"{key}_cells"] = cells
            columns.append(col_data)

        return {
            "sheet": sheet_name,
            "label_cell": label_cell,
            "columns": columns,
            "rows": {
                "grad": {"row": row_by_label.get("grad", 0), "cells": row_cells.get("grad", [])},
                "brand": {"row": row_by_label.get("brand", 0), "cells": row_cells.get("brand", [])},
                "daily": {"row": row_by_label.get("daily", 0), "cells": row_cells.get("daily", [])},
            },
            "names_row": name_row,
        }

    def _paradigm_edit_allowed(self):
        cfg = self.main_ui_layout_config.get("character_screen", {})
        panel = cfg.get("paradigm_panel", {}) if isinstance(cfg, dict) else {}
        edit_cfg = panel.get("edit", {}) if isinstance(panel, dict) else {}
        panel_edit = bool(edit_cfg.get("enabled", False)) if isinstance(edit_cfg, dict) else False
        return self._character_edit_allowed("basic_fields") and panel_edit

    def _render_character_initiative_panel(self, character_screen, character_panel, attribute_panel, default_color):
        return character_section.render_character_initiative_panel(
            self,
            character_screen,
            character_panel,
            attribute_panel,
            default_color,
        )

    def _on_character_initiative_bonus_edit_finished(self, editor, sheet_name, bonus_cell, old_raw_text):
        if editor is None:
            return
        new_text = str(editor.text() or "").strip()
        old_text = str(old_raw_text if old_raw_text is not None else "").strip()
        normalized = new_text.replace(",", ".").strip()
        if normalized == "":
            normalized = "0"
        try:
            numeric = float(normalized)
        except Exception:
            log_warning("character", f'CHARACTER INITIATIVE BONUS EDIT ERROR invalid value="{new_text}"')
            editor.setText(old_text if old_text else "0")
            return

        if numeric.is_integer():
            normalized_value = str(int(numeric))
        else:
            normalized_value = f"{numeric:.6f}".rstrip("0").rstrip(".")
        cached_old = str(self.get_cache_cell_value(sheet_name, bonus_cell, "") or "").strip()
        if cached_old == normalized_value:
            editor.setText(normalized_value)
            return
        try:
            log_debug("character", f'CHARACTER INITIATIVE BONUS EDIT {sheet_name}!{bonus_cell} "{cached_old}" -> "{normalized_value}"')
            self.loader.set_cell_value(sheet_name, bonus_cell, normalized_value)
            self._recalculate_after_user_edit(reason=f"{sheet_name}!{bonus_cell}", save=True, rerender=True)
            log_debug("calculation", f"RECALC after user edit: {sheet_name}!{bonus_cell}")
        except Exception as exc:
            log_error("character", f"initiative bonus edit failed: {exc}")
            editor.setText(cached_old if cached_old else old_text if old_text else "0")

    def _render_character_paradigm_panel(self, character_screen, attribute_panel, default_color):
        return character_section.render_character_paradigm_panel(
            self,
            character_screen,
            attribute_panel,
            default_color,
        )

    def _open_large_text_dialog(self, title, value):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(640, 420)
        layout = QVBoxLayout(dialog)
        editor = QTextEdit(dialog)
        editor.setPlainText("" if value is None else str(value))
        layout.addWidget(editor)
        button_row = QHBoxLayout()
        ok_button = QPushButton("OK", dialog)
        cancel_button = QPushButton("Abbrechen", dialog)
        button_row.addStretch()
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        if dialog.exec() == QDialog.Accepted:
            return editor.toPlainText(), True
        return value, False

    def _open_character_field_dialog(self, title, initial_value, multiline=False):
        initial_text = "" if initial_value is None else str(initial_value)
        if multiline:
            return self._open_large_text_dialog(title, initial_text)
        text, ok = QInputDialog.getText(self, title, "Wert:", text=initial_text)
        return text, bool(ok)

    def _handle_character_widget_double_click(self, widget):
        field_key = str(widget.property("character_field_key") or "")
        sheet_name = str(widget.property("character_sheet_name") or "")
        cell_ref = str(widget.property("character_cell_ref") or "")
        current_value = str(widget.property("character_value") or "")
        if not field_key or not sheet_name or not cell_ref:
            self._character_debug(f"[CHARACTER EDIT SKIP] field={field_key or '-'} reason=no_cell_ref")
            return True
        multiline = bool(widget.property("character_multiline"))
        dialog_title = str(widget.property("character_dialog_title") or "Feld bearbeiten")
        new_value, ok = self._open_character_field_dialog(dialog_title, current_value, multiline=multiline)
        if not ok:
            return True
        section_key = str(widget.property("character_section_key") or "")
        tag = "CHARACTER BASIC EDIT" if section_key == "basic_fields" else "CHARACTER EDIT"
        self._on_character_field_edited(field_key, sheet_name, cell_ref, new_value, tag=tag)
        self.show_main_section("character")
        return True

    def _create_character_value_editor(
        self,
        parent,
        rect_cfg,
        field_key,
        mapping_entry,
        default_sheet,
        value_text,
        font_size,
        color,
        bold=True,
        align="left",
        editable=True,
        section_key="basic_fields",
    ):
        x = self._safe_int(rect_cfg.get("x", 0), 0)
        y = self._safe_int(rect_cfg.get("y", 0), 0)
        w = self._safe_int(rect_cfg.get("w", 160), 160)
        h = self._safe_int(rect_cfg.get("h", 28), 28)
        sheet_name, cell_ref = self._resolve_data_map_cell_ref(mapping_entry, default_sheet)
        if not sheet_name or not cell_ref:
            if section_key == "basic_fields":
                log_debug("character", f"CHARACTER BASIC EDIT SKIP field={field_key} reason=no_cell_ref")
            else:
                log_debug("character", f"CHARACTER EDIT SKIP field={field_key} reason=no_cell_ref")
            return self.create_panel_text(
                parent, rect_cfg, value_text, font_size, color, bold=bold, align=align
            )
        if not editable or not self._character_edit_allowed(section_key):
            return self.create_panel_text(
                parent, rect_cfg, value_text, font_size, color, bold=bold, align=align
            )

        edit_on = str((self._character_edit_cfg or {}).get("edit_on", "double_click"))
        if edit_on == "double_click":
            label = self.create_panel_text(
                parent, rect_cfg, value_text, font_size, color, bold=bold, align=align
            )
            label.setProperty("character_editable", True)
            label.setProperty("character_field_key", field_key)
            label.setProperty("character_sheet_name", sheet_name)
            label.setProperty("character_cell_ref", cell_ref)
            label.setProperty("character_value", "" if value_text is None else str(value_text))
            label.setProperty("character_section_key", section_key)
            label.setProperty("character_multiline", False)
            label.setProperty("character_dialog_title", f"{field_key} bearbeiten")
            label.installEventFilter(self)
            return label

        editor = QLineEdit(parent)
        editor.setGeometry(x, y, w, h)
        editor.setText("" if value_text is None else str(value_text))
        qt_align = Qt.AlignVCenter
        if align == "center":
            qt_align |= Qt.AlignHCenter
        elif align == "right":
            qt_align |= Qt.AlignRight
        else:
            qt_align |= Qt.AlignLeft
        editor.setAlignment(qt_align)
        weight = 700 if bold else 500
        editor.setStyleSheet(
            "QLineEdit {"
            "background: transparent;"
            "border: 1px solid rgba(216, 208, 176, 38);"
            f"color: {color};"
            f"font-size: {int(font_size)}px;"
            f"font-weight: {weight};"
            "padding: 0px 2px;"
            "}"
            "QLineEdit:focus { border: 1px solid rgba(216, 208, 176, 120); }"
        )
        editor.editingFinished.connect(
            lambda fk=field_key, sn=sheet_name, cr=cell_ref, e=editor, sk=section_key: self._on_character_field_edited(
                fk,
                sn,
                cr,
                e.text(),
                tag="CHARACTER BASIC EDIT" if sk == "basic_fields" else "CHARACTER EDIT",
            )
        )
        editor.raise_()
        editor.show()
        return editor

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
        return character_section.render_character_section(self)

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
        return settings_section.update_settings_checkbox_icon(self)

    def on_settings_debug_start_toggled(self):
        return settings_section.on_settings_debug_start_toggled(self)

    def refresh_character_cache_list(self):
        return settings_section.refresh_character_cache_list(self)

    def on_settings_load_character_clicked(self):
        return settings_section.on_settings_load_character_clicked(self)

    def on_settings_character_selection_changed(self, index):
        return settings_section.on_settings_character_selection_changed(self, index)

    def on_settings_refresh_character_list_clicked(self):
        return settings_section.on_settings_refresh_character_list_clicked(self)

    def open_calculation_center(self):
        if self.calculation_center_dialog is not None and self.calculation_center_dialog.isVisible():
            self.calculation_center_dialog.raise_()
            self.calculation_center_dialog.activateWindow()
            return
        self.calculation_center_dialog = CalculationCenterDialog(
            self,
            self.loader,
            self.parser,
        )
        self.calculation_center_dialog.show()
        self.calculation_center_dialog.raise_()
        self.calculation_center_dialog.activateWindow()

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
        self.character_paradigm_analysis = {}
        log_debug("character", "runtime state cleared")

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
                if nav.get("shape") == "d20":
                    nav["bg"].setPixmap(
                        self.create_d20_nav_pixmap(container.width(), container.height(), active=True)
                    )
                text_label.setStyleSheet(
                    f"background: transparent; color: {active_color}; font-weight: 700;"
                )
                container.setStyleSheet("border: 1px solid #b88a35; background: transparent;")
                click_button.setStyleSheet(
                    "QPushButton { border: none; background: transparent; padding: 0px; }"
                )
            else:
                if nav.get("shape") == "d20":
                    nav["bg"].setPixmap(
                        self.create_d20_nav_pixmap(container.width(), container.height(), active=False)
                    )
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
                nav = self.nav_buttons[section_id]
                if event.type() == QEvent.Enter and section_id != self.current_main_section:
                    if nav.get("shape") == "d20":
                        nav["bg"].setPixmap(
                            self.create_d20_nav_pixmap(
                                nav["container"].width(),
                                nav["container"].height(),
                                hover=True,
                            )
                        )
                    text_label.setStyleSheet(
                        f"background: transparent; color: {hover_color}; font-weight: 400;"
                    )
                elif event.type() == QEvent.Leave and section_id != self.current_main_section:
                    if nav.get("shape") == "d20":
                        nav["bg"].setPixmap(
                            self.create_d20_nav_pixmap(
                                nav["container"].width(),
                                nav["container"].height(),
                                active=False,
                            )
                        )
                    text_label.setStyleSheet(
                        f"background: transparent; color: {inactive_color}; font-weight: 400;"
                    )
        if isinstance(obj, QLabel):
            if event.type() == QEvent.MouseButtonPress:
                resource_id = str(obj.property("character_resource_id") or "")
                if resource_id:
                    self.open_character_resource_dialog(resource_id)
                    return True
            if event.type() == QEvent.MouseButtonDblClick:
                if bool(obj.property("character_editable")):
                    return self._handle_character_widget_double_click(obj)
                perk_table_type = str(obj.property("character_perk_table_type") or "")
                if perk_table_type in ("perk", "disadvantage"):
                    row = int(obj.property("character_perk_row") or 0)
                    field = str(obj.property("character_perk_field") or "")
                    cell_ref = str(obj.property("character_perk_cell_ref") or "")
                    sheet_name = str(obj.property("character_perk_sheet_name") or "")
                    old_value = str(obj.property("character_perk_value") or "")
                    if not cell_ref or not sheet_name:
                        self._character_debug(
                            f"[CHARACTER EDIT SKIP] field={perk_table_type}.{field} reason=no_cell_ref"
                        )
                        return True
                    multiline = field == "effect"
                    title = (
                        "Perk Effekt bearbeiten"
                        if perk_table_type == "perk" and multiline
                        else "Nachteil Effekt bearbeiten"
                        if perk_table_type == "disadvantage" and multiline
                        else "Perk bearbeiten"
                        if perk_table_type == "perk"
                        else "Nachteil bearbeiten"
                    )
                    new_value, ok = self._open_character_field_dialog(title, old_value, multiline=multiline)
                    if not ok:
                        return True
                    tag = "CHARACTER PERK EDIT" if perk_table_type == "perk" else "CHARACTER DISADVANTAGE EDIT"
                    self._character_debug(
                        f'[{tag}] row={row} field={field} cell={cell_ref} old="{old_value}" new="{new_value}"'
                    )
                    self.loader.set_cell_value(sheet_name, cell_ref, str(new_value))
                    self._recalculate_after_user_edit(
                        reason=f"{sheet_name}!{cell_ref}",
                        save=bool((self._character_edit_cfg or {}).get("save_on_change", True)),
                        rerender=True,
                    )
                    return True
                if bool(obj.property("character_paradigm_name_edit")):
                    cell_ref = str(obj.property("character_paradigm_cell_ref") or "")
                    sheet_name = str(obj.property("character_paradigm_sheet") or "Charakterbogen")
                    index = int(obj.property("character_paradigm_index") or 0)
                    old_value = str(obj.property("character_paradigm_old") or "")
                    if not self._paradigm_edit_allowed():
                        return True
                    if not cell_ref:
                        self._character_paradigm_debug("[CHARACTER PARADIGM EDIT SKIP] reason=no_cell_ref")
                        return True
                    new_value, ok = self._open_character_field_dialog("Paradigma bearbeiten", old_value, multiline=False)
                    if not ok:
                        return True
                    self._character_paradigm_debug(
                        f'[CHARACTER PARADIGM EDIT] field=name index={index} cell={cell_ref} old="{old_value}" new="{new_value}"'
                    )
                    self.loader.set_cell_value(sheet_name, cell_ref, str(new_value))
                    self._recalculate_after_user_edit(
                        reason=f"{sheet_name}!{cell_ref}",
                        save=bool((self._character_edit_cfg or {}).get("save_on_change", True)),
                        rerender=True,
                    )
                    return True
            if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
                if bool(obj.property("character_wellbeing_toggle")) and self._character_edit_allowed("wellbeing"):
                    row = int(obj.property("character_wellbeing_row") or 0)
                    marker_cell = str(obj.property("character_wellbeing_marker_cell") or "")
                    sheet_name = str(obj.property("character_wellbeing_sheet_name") or "")
                    active = bool(obj.property("character_wellbeing_active"))
                    if not marker_cell or not sheet_name:
                        self._character_debug("[CHARACTER EDIT SKIP] field=wellbeing reason=no_cell_ref")
                        return True
                    new_active = not active
                    new_value = "x" if new_active else ""
                    self.loader.set_cell_value(sheet_name, marker_cell, new_value)
                    self._recalculate_after_user_edit(
                        reason=f"{sheet_name}!{marker_cell}",
                        save=bool((self._character_edit_cfg or {}).get("save_on_change", True)),
                        rerender=True,
                    )
                    self._character_debug(
                        f"[CHARACTER WELLBEING EDIT] row={row} marker_cell={marker_cell} active={new_active}"
                    )
                    return True
                if (
                    event.type() == QEvent.MouseButtonPress
                    and bool(obj.property("character_paradigm_marker_toggle"))
                    and self._paradigm_edit_allowed()
                ):
                    cell_ref = str(obj.property("character_paradigm_cell_ref") or "")
                    sheet_name = str(obj.property("character_paradigm_sheet") or "Charakterbogen")
                    row_id = str(obj.property("character_paradigm_row") or "")
                    index = int(obj.property("character_paradigm_index") or 0)
                    marker_index = int(obj.property("character_paradigm_marker_index") or 0)
                    active = bool(obj.property("character_paradigm_active"))
                    if not cell_ref:
                        self._character_paradigm_debug("[CHARACTER PARADIGM EDIT SKIP] reason=no_cell_ref")
                        return True
                    new_active = not active
                    self.loader.set_cell_value(sheet_name, cell_ref, "X" if new_active else "")
                    self._recalculate_after_user_edit(
                        reason=f"{sheet_name}!{cell_ref}",
                        save=bool((self._character_edit_cfg or {}).get("save_on_change", True)),
                        rerender=True,
                    )
                    self._character_paradigm_debug(
                        f"[CHARACTER PARADIGM TOGGLE] row={row_id} index={index} marker={marker_index} cell={cell_ref} active={new_active}"
                    )
                    return True
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
            log_warning("character", "unsaved changes before switching character")
        try:
            self.loader.load_file(file_path)
        except ValueError as exc:
            log_error("cache", f"load failed: {exc}")
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
