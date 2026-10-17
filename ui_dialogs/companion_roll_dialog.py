import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app_paths import resource_path
from ui_roll_math import advantage_dice_expression
from ui_dialogs.window_chrome import install_frameless_dialog_chrome
from ui_dialogs.roll_dialog_ui import add_roll_main_frame, create_roll_close_button, create_roll_counter, create_roll_menu_button, framed_box_style


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
        self._roll_cfg, self._cfg = self._load_layout(parent)
        dialog_cfg = self._roll_cfg.get("dialog", {})
        self._resolve_asset = lambda relative: self._asset_path(parent, relative)
        self.setWindowTitle(f"Companion-Würfe: {companion_name}")
        self.setModal(True)
        install_frameless_dialog_chrome(self)
        self.setFixedSize(_int(dialog_cfg.get("w", 922), 922), _int(dialog_cfg.get("h", 622), 622))
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self._background = add_roll_main_frame(self, dialog_cfg, self._resolve_asset)

        title_cfg = {**self._roll_cfg.get("title", {}), **self._cfg.get("title", {})}
        self.title_label = QLabel(str(companion_name or "Companion"), self)
        self.title_label.setGeometry(*self._rect(title_cfg))
        self.title_label.setAlignment(Qt.AlignCenter)
        self._fit_title(title_cfg)
        self.title_label.installEventFilter(self._frameless_drag_filter)
        self.window_close_button = create_roll_close_button(self, self._roll_cfg.get("close_button", {}), self._resolve_asset)
        self.window_close_button.setObjectName("companionRollWindowClose")
        self.window_close_button.clicked.connect(self.reject)
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
        companion_cfg = {}
        for path in candidates:
            try:
                if path.exists():
                    companion_cfg = json.loads(path.read_text(encoding="utf-8")).get("companion_roll_dialog", {})
                    break
            except (OSError, ValueError, TypeError):
                continue
        roll_path = resource_path("assets/themes/diablo/roll_dialog_layout.json")
        base = getattr(parent, "theme_asset_base_path", None)
        if base is not None:
            roll_path = next((path for path in (base / "roll_dialog_layout.json", base.parent / "roll_dialog_layout.json") if path.exists()), roll_path)
        return json.loads(roll_path.read_text(encoding="utf-8")), companion_cfg

    def _asset_path(self, parent, relative):
        rel = str(relative or "").replace("\\", "/").lstrip("/")
        base = getattr(parent, "theme_asset_base_path", None)
        candidates = []
        if base is not None:
            candidates.extend((base / rel, base / "ui" / rel))
        candidates.append(resource_path(f"assets/themes/diablo/ui/{rel}"))
        candidates.append(resource_path(f"assets/{rel}"))
        return next((path for path in candidates if path.exists()), None)

    def _rect(self, cfg):
        return tuple(_int(cfg.get(key, 0), 0) for key in ("x", "y", "w", "h"))

    def _fit_title(self, cfg):
        label = self.title_label
        font_size = _int(cfg.get("font_size", 14), 14)
        font = label.font()
        font.setPixelSize(font_size)
        font.setBold(True)
        minimum = _int(cfg.get("min_font_size", font_size), font_size)
        while font.pixelSize() > minimum and QFontMetrics(font).horizontalAdvance(label.text()) > max(1, label.width() - 8):
            font.setPixelSize(font.pixelSize() - 1)
        label.setFont(font)
        label.setStyleSheet(f"background: transparent; color: {cfg.get('color', '#f2d28b')};")

    def _build_table(self):
        cfg = self._cfg.get("table", {})
        panel = QLabel(self)
        panel.setGeometry(*self._rect(cfg))
        panel.setStyleSheet(framed_box_style("rgba(0, 0, 0, 70)", "rgba(242, 210, 139, 75)", "#ffffff", 13, self._roll_cfg.get("boxes", {}).get("info_frame", {}), self._resolve_asset, 4))
        columns = cfg.get("columns", [])
        self.table = QTableWidget(0, len(columns), self)
        x, y, w, h = self._rect(cfg)
        self.table.setGeometry(x + 8, y + 8, w - 16, h - 16)
        self.table.setHorizontalHeaderLabels([str(column.get("text", "")) for column in columns])
        for index, column in enumerate(columns):
            self.table.setColumnWidth(index, _int(column.get("w", 70), 70))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setStyleSheet(
            "QTableWidget { background: rgba(5, 4, 3, 180); color: #f2f2f2; gridline-color: rgba(242, 210, 139, 75); font-size: 13px; border: none; selection-background-color: rgba(242, 210, 139, 45); }"
            "QHeaderView::section { background: transparent; color: #f2d28b; font-size: 13px; border: 1px solid rgba(242, 210, 139, 75); padding: 4px; }"
        )
        self.table.itemSelectionChanged.connect(self._load_selected_roll)

    def _build_selector(self, roll_options):
        cfg = self._cfg.get("selector", {})
        editor_cfg = self._cfg.get("editor", {})
        self.editor_panel = QWidget(self)
        self.editor_panel.setGeometry(*self._rect(editor_cfg))
        self.editor_layout = QVBoxLayout(self.editor_panel)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(_int(editor_cfg.get("spacing", 12), 12))
        label = QLabel(str(cfg.get("label", "Roll / Fertigkeit")), self.editor_panel)
        label.setStyleSheet("color: #f2d28b; font-size: 13px; font-weight: 700;")
        self.editor_layout.addWidget(label)
        self.roll_combo = QComboBox(self.editor_panel)
        frame_cfg = self._roll_cfg.get("boxes", {}).get("info_frame", {})
        style = framed_box_style("rgba(0, 0, 0, 70)", "#8a6a32", "#f2f2f2", 13, frame_cfg, self._resolve_asset, 5)
        self.roll_combo.setStyleSheet(f"QComboBox {{{style}}}")
        self.roll_combo.setFixedHeight(40)
        self.editor_layout.addWidget(self.roll_combo)
        for option in roll_options if isinstance(roll_options, list) else []:
            if isinstance(option, dict):
                roll_id = str(option.get("roll_id", "") or "").strip()
                roll_name = str(option.get("roll_name", "") or "").strip()
                if roll_id or roll_name:
                    self.roll_combo.addItem(roll_name or roll_id, {"roll_id": roll_id, "roll_name": roll_name})

    def _build_counters(self):
        common = self._roll_cfg.get("counter", {})
        self._spins = {}
        for counter in self._cfg.get("counters", []):
            key = str(counter.get("id", ""))
            row, spin, _minus, _plus = create_roll_counter(self.editor_panel, str(counter.get("label", key)), _int(counter.get("min", 0)), _int(counter.get("max", 99)), common, self._roll_cfg.get("roll_preview", {}), self._roll_cfg.get("labels", {}), self._resolve_asset, f"companionRoll{key.title()}")
            self.editor_layout.addLayout(row)
            self._spins[key] = spin
        self.editor_layout.addStretch()
        self.value_spin = self._spins["value"]
        self.modifier_spin = self._spins["modifier"]
        self.advantages_spin = self._spins["advantages"]
        self.disadvantages_spin = self._spins["disadvantages"]

    def _build_preview(self):
        cfg = self._cfg.get("preview", {})
        preview_cfg = self._roll_cfg.get("roll_preview", {})
        frame_cfg = self._roll_cfg.get("boxes", {}).get("preview_frame", {})
        self.preview = QLineEdit("Wurf: 1d20", self)
        self.preview.setReadOnly(True)
        self.preview.setGeometry(*self._rect(cfg))
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet(framed_box_style(preview_cfg.get("background", "#101214"), preview_cfg.get("border_color", "#8a6a32"), preview_cfg.get("text_color", "#f2d28b"), _int(preview_cfg.get("font_size", 22), 22), frame_cfg, self._resolve_asset, frame_cfg.get("padding", 4), True))
        self.preview.setObjectName("companionRollPreview")

    def _build_actions(self):
        cfg = self._cfg.get("delete_button", {})
        self.delete_button = create_roll_menu_button(str(cfg.get("text", "Löschen")), self, self._roll_cfg.get("buttons", {}), self._resolve_asset, str(cfg.get("button_key", "close")))
        self.delete_button.move(_int(cfg.get("x", 783)), _int(cfg.get("y", 527)))
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
