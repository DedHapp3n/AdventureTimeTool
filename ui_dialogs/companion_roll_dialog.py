import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QAbstractSpinBox, QComboBox, QDialog, QLabel, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem

from app_paths import resource_path
from ui_controls import create_step_button
from ui_roll_math import advantage_dice_expression
from ui_dialogs.window_chrome import install_frameless_dialog_chrome


def _int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _signed(value):
    number = int(value)
    return f"+{number}" if number > 0 else str(number) if number < 0 else ""


class CompanionRollDialog(QDialog):
    def __init__(self, parent, companion_name, roll_options, rolls=None, on_change=None):
        super().__init__(parent)
        self._on_change = on_change
        self._loading = False
        self._cfg = self._load_layout(parent)
        self._colors = self._cfg.get("colors", {})
        dialog_cfg = self._cfg.get("dialog", {})
        self.setWindowTitle(f"Companion-Würfe: {companion_name}")
        self.setModal(True)
        install_frameless_dialog_chrome(self)
        self.setFixedSize(_int(dialog_cfg.get("w", 720), 720), _int(dialog_cfg.get("h", 720), 720))
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(f"background: {dialog_cfg.get('background', 'transparent')};")
        self._background = self._add_frame(self, {"x": 0, "y": 0, "w": self.width(), "h": self.height()}, dialog_cfg.get("frame_asset", "panels/main_Frame.png"))
        self._background.lower()

        title_cfg = self._cfg.get("title", {})
        self.title_label = self._label(str(companion_name or "Companion"), title_cfg, bold=True, fit=True)
        self.title_label.installEventFilter(self._frameless_drag_filter)
        self._build_close_button()
        self._build_table()
        self._build_selector(roll_options)
        self._build_counters()
        self._build_preview()
        self._build_actions()

        self._loading = True
        for roll in rolls if isinstance(rolls, list) else []:
            if isinstance(roll, dict):
                self._upsert_roll(roll)
        self._loading = False
        self.roll_combo.currentIndexChanged.connect(self._select_or_create_current_roll)
        for spin in self._spins.values():
            spin.valueChanged.connect(self._editor_changed)
        self.delete_button.clicked.connect(self._delete_selected)
        if self.table.rowCount():
            self.table.selectRow(0)
        elif self.roll_combo.count():
            self._select_or_create_current_roll()
        self._update_preview()

    def _load_layout(self, parent):
        candidates = []
        base = getattr(parent, "theme_asset_base_path", None)
        if base is not None:
            candidates.extend((base / "companion_roll_layout.json", base.parent / "companion_roll_layout.json"))
        candidates.append(resource_path("assets/themes/diablo/companion_roll_layout.json"))
        for path in candidates:
            try:
                if path.exists():
                    return json.loads(path.read_text(encoding="utf-8")).get("companion_roll_dialog", {})
            except (OSError, ValueError, TypeError):
                continue
        return {}

    def _asset(self, relative):
        rel = str(relative or "").replace("\\", "/").lstrip("/")
        parent = self.parent()
        base = getattr(parent, "theme_asset_base_path", None)
        candidates = []
        if base is not None:
            candidates.extend((base / rel, base / "ui" / rel))
        candidates.append(resource_path(f"assets/themes/diablo/ui/{rel}"))
        candidates.append(resource_path(f"assets/{rel}"))
        return next((path for path in candidates if path.exists()), None)

    def _rect(self, cfg):
        return tuple(_int(cfg.get(key, 0), 0) for key in ("x", "y", "w", "h"))

    def _add_frame(self, parent, rect, asset):
        frame = QLabel(parent)
        frame.setGeometry(*self._rect(rect))
        path = self._asset(asset)
        pixmap = QPixmap(str(path)) if path else QPixmap()
        if not pixmap.isNull():
            frame.setPixmap(pixmap.scaled(frame.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        return frame

    def _label(self, text, cfg, bold=False, fit=False):
        label = QLabel(text, self)
        label.setGeometry(*self._rect(cfg))
        alignment = str(cfg.get("align", "left"))
        label.setAlignment(Qt.AlignVCenter | (Qt.AlignCenter if alignment == "center" else Qt.AlignRight if alignment == "right" else Qt.AlignLeft))
        font_size = _int(cfg.get("font_size", 14), 14)
        font = label.font()
        font.setPixelSize(font_size)
        font.setBold(bold)
        if fit:
            minimum = _int(cfg.get("min_font_size", font_size), font_size)
            while font.pixelSize() > minimum and QFontMetrics(font).horizontalAdvance(label.text()) > max(1, label.width() - 8):
                font.setPixelSize(font.pixelSize() - 1)
        label.setFont(font)
        label.setStyleSheet(f"background: transparent; color: {cfg.get('color', self._colors.get('accent', '#f2d28b'))};")
        return label

    def _build_close_button(self):
        cfg = self._cfg.get("close_button", {})
        self.window_close_button = None
        if not cfg.get("enabled", True):
            return
        width = _int(cfg.get("w", 28), 28)
        height = _int(cfg.get("h", 28), 28)
        x = self.width() - _int(cfg.get("right", 24), 24) - width
        y = _int(cfg.get("top", 22), 22)
        button = QPushButton("", self)
        button.setObjectName("companionRollWindowClose")
        button.setGeometry(x, y, width, height)
        path = self._asset(cfg.get("asset", "ui_elements/icons/x.jpg"))
        button.setStyleSheet(f"QPushButton {{ border: none; background: transparent; border-image: url({path.as_posix() if path else ''}) 0 0 0 0 stretch stretch; }}")
        button.clicked.connect(self.reject)
        self.window_close_button = button

    def _build_table(self):
        cfg = self._cfg.get("table", {})
        columns = cfg.get("columns", [])
        self.table = QTableWidget(0, len(columns), self)
        self.table.setGeometry(*self._rect(cfg))
        self.table.setHorizontalHeaderLabels([str(column.get("text", "")) for column in columns])
        for index, column in enumerate(columns):
            self.table.setColumnWidth(index, _int(column.get("w", 70), 70))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet(
            f"QTableWidget {{ background: {self._colors.get('field')}; color: {self._colors.get('text')}; gridline-color: {self._colors.get('grid')}; font-size: {_int(cfg.get('font_size', 14), 14)}px; border: none; selection-background-color: {self._colors.get('selection')}; }}"
            f"QHeaderView::section {{ background: transparent; color: {self._colors.get('accent')}; font-size: {_int(cfg.get('header_font_size', 14), 14)}px; border: 1px solid {self._colors.get('grid')}; padding: 4px; }}"
        )
        self.table.itemSelectionChanged.connect(self._load_selected_roll)

    def _build_selector(self, roll_options):
        cfg = self._cfg.get("selector", {})
        self._label(str(cfg.get("label", "Roll / Fertigkeit")), cfg.get("label_rect", {}), bold=True)
        rect = cfg.get("rect", {})
        self._add_frame(self, rect, cfg.get("frame_asset"))
        self.roll_combo = QComboBox(self)
        self.roll_combo.setGeometry(*self._rect(rect))
        self.roll_combo.setStyleSheet(f"QComboBox {{ background: transparent; color: {self._colors.get('text')}; border: none; padding: 5px 12px; font-size: {_int(cfg.get('font_size', 15), 15)}px; }} QComboBox QAbstractItemView {{ background: {self._colors.get('field')}; color: {self._colors.get('text')}; selection-background-color: {self._colors.get('selection')}; }}")
        for option in roll_options if isinstance(roll_options, list) else []:
            if isinstance(option, dict):
                roll_id = str(option.get("roll_id", "") or "").strip()
                roll_name = str(option.get("roll_name", "") or "").strip()
                if roll_id or roll_name:
                    self.roll_combo.addItem(roll_name or roll_id, {"roll_id": roll_id, "roll_name": roll_name})

    def _build_counters(self):
        common = self._cfg.get("counter", {})
        self._spins = {}
        for counter in self._cfg.get("counters", []):
            key = str(counter.get("id", ""))
            y = _int(counter.get("y", 0), 0)
            self._label(str(counter.get("label", key)), {"x": common.get("label_x"), "y": y, "w": common.get("label_w"), "h": common.get("h"), "font_size": common.get("font_size"), "color": self._colors.get("accent")}, bold=True)
            minus = create_step_button(self, "-", f"{counter.get('label', key)} verringern")
            minus.move(_int(common.get("minus_x", 340), 340), y + 2)
            value_rect = {"x": common.get("value_x"), "y": y, "w": common.get("value_w"), "h": common.get("h")}
            self._add_frame(self, value_rect, common.get("frame_asset"))
            spin = QSpinBox(self)
            spin.setObjectName(f"companionRoll{key.title()}")
            spin.setGeometry(*self._rect(value_rect))
            spin.setRange(_int(counter.get("min", 0), 0), _int(counter.get("max", 99), 99))
            spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spin.setAlignment(Qt.AlignCenter)
            spin.setStyleSheet(f"background: transparent; color: {self._colors.get('text')}; border: none; font-size: {_int(common.get('font_size', 15), 15)}px;")
            plus = create_step_button(self, "+", f"{counter.get('label', key)} erhöhen")
            plus.move(_int(common.get("plus_x", 482), 482), y + 2)
            minus.clicked.connect(lambda checked=False, editor=spin: editor.setValue(editor.value() - 1))
            plus.clicked.connect(lambda checked=False, editor=spin: editor.setValue(editor.value() + 1))
            self._spins[key] = spin
        self.value_spin = self._spins["value"]
        self.modifier_spin = self._spins["modifier"]
        self.advantages_spin = self._spins["advantages"]
        self.disadvantages_spin = self._spins["disadvantages"]

    def _build_preview(self):
        cfg = self._cfg.get("preview", {})
        self._add_frame(self, cfg, cfg.get("frame_asset"))
        self.preview = self._label("Wurf: 1d20", cfg, bold=True)
        self.preview.setObjectName("companionRollPreview")

    def _themed_button(self, cfg):
        common = self._cfg.get("buttons", {})
        button = QPushButton(str(cfg.get("text", "")), self)
        button.setGeometry(_int(cfg.get("x")), _int(cfg.get("y")), _int(cfg.get("w")), _int(common.get("h", 38), 38))
        path = self._asset(common.get("asset"))
        button.setStyleSheet(f"QPushButton {{ color: {self._colors.get('accent')}; font-size: {_int(common.get('font_size', 15), 15)}px; font-weight: 700; border: none; background: transparent; border-image: url({path.as_posix() if path else ''}) 0 0 0 0 stretch stretch; }} QPushButton:hover {{ color: #ffffff; }}")
        return button

    def _build_actions(self):
        cfg = self._cfg.get("buttons", {})
        self.delete_button = self._themed_button(cfg.get("delete", {}))
        self.delete_button.setObjectName("companionRollDelete")

    def rolls(self):
        result = []
        keys = ("value", "modifier", "advantages", "disadvantages")
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            data = name_item.data(Qt.UserRole) if name_item else {}
            if not isinstance(data, dict):
                continue
            numbers = {key: int(self.table.item(row, index + 1).data(Qt.UserRole) or 0) for index, key in enumerate(keys)}
            result.append({"roll_id": str(data.get("roll_id", "")), "roll_name": str(data.get("roll_name", "") or name_item.text()), **numbers})
        return result

    def _identity(self, data):
        return str(data.get("roll_id", "") or "").strip() or str(data.get("roll_name", "") or "").strip().casefold()

    def _find_row(self, identity):
        for row in range(self.table.rowCount()):
            data = self.table.item(row, 0).data(Qt.UserRole)
            if isinstance(data, dict) and self._identity(data) == identity:
                return row
        return -1

    def _upsert_roll(self, roll):
        data = {"roll_id": str(roll.get("roll_id", "") or "").strip(), "roll_name": str(roll.get("roll_name", "") or "").strip()}
        identity = self._identity(data)
        if not identity:
            return -1
        row = self._find_row(identity)
        if row < 0:
            row = self.table.rowCount()
            self.table.insertRow(row)
        name = QTableWidgetItem(data["roll_name"] or data["roll_id"])
        name.setData(Qt.UserRole, data)
        self.table.setItem(row, 0, name)
        for column, key in enumerate(("value", "modifier", "advantages", "disadvantages"), 1):
            number = _int(roll.get(key, 0), 0)
            if key in {"advantages", "disadvantages"}:
                number = max(0, number)
            item = QTableWidgetItem(str(number))
            item.setData(Qt.UserRole, number)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, column, item)
        return row

    def _select_or_create_current_roll(self):
        if self._loading:
            return
        data = self.roll_combo.currentData()
        if not isinstance(data, dict):
            return
        row = self._find_row(self._identity(data))
        if row < 0:
            row = self._upsert_roll({**data, "value": 0, "modifier": 0, "advantages": 0, "disadvantages": 0})
            self._emit_change()
        self.table.selectRow(row)

    def _load_selected_roll(self):
        row = self.table.currentRow()
        if row < 0:
            return
        data = self.table.item(row, 0).data(Qt.UserRole)
        self._loading = True
        identity = self._identity(data)
        for index in range(self.roll_combo.count()):
            option = self.roll_combo.itemData(index)
            if isinstance(option, dict) and self._identity(option) == identity:
                self.roll_combo.setCurrentIndex(index)
                break
        for column, key in enumerate(("value", "modifier", "advantages", "disadvantages"), 1):
            self._spins[key].setValue(int(self.table.item(row, column).data(Qt.UserRole) or 0))
        self._loading = False
        self._update_preview()

    def _editor_changed(self):
        if self._loading:
            return
        row = self.table.currentRow()
        if row < 0:
            self._select_or_create_current_roll()
            row = self.table.currentRow()
        if row < 0:
            return
        for column, key in enumerate(("value", "modifier", "advantages", "disadvantages"), 1):
            number = self._spins[key].value()
            item = self.table.item(row, column)
            item.setText(str(number))
            item.setData(Qt.UserRole, number)
        self._update_preview()
        self._emit_change()

    def _update_preview(self):
        dice = advantage_dice_expression(self.advantages_spin.value(), self.disadvantages_spin.value())
        self.preview.setText(f"Wurf: {dice}{_signed(self.value_spin.value())}{_signed(self.modifier_spin.value())}")

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        self._emit_change()
        if self.table.rowCount():
            self.table.selectRow(min(row, self.table.rowCount() - 1))
        else:
            self._loading = True
            for spin in self._spins.values():
                spin.setValue(0)
            self._loading = False
            self._update_preview()

    def _emit_change(self):
        if not self._loading and callable(self._on_change):
            self._on_change(self.rolls())
