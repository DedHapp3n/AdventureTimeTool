from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui_dialogs.window_chrome import install_frameless_dialog_chrome


GOLD = "#f2d28b"
GOLD_DARK = "#d8aa4c"
TEXT = "#eadfca"
MUTED = "#c8c0aa"
VALUE_BLUE = "#7fd0ff"
DARK_PANEL = "rgba(5, 4, 3, 185)"


class InventoryRollBonusDialog(QDialog):
    def __init__(self, parent, item_name, roll_options, modifiers=None):
        super().__init__(parent)
        self.setWindowTitle("Inventar Rollbonus")
        self.setModal(True)
        self._roll_options = roll_options if isinstance(roll_options, list) else []
        self._result_modifiers = []
        install_frameless_dialog_chrome(self)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.resize(500, 360)
        self.setStyleSheet(_dialog_stylesheet(parent))
        _add_dialog_background(self, parent, 500, 360)

        close_button = _make_close_button(self, parent)
        if close_button is not None:
            close_button.clicked.connect(self.reject)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(8)

        title = QLabel(str(item_name or "(ohne Name)"))
        title.setObjectName("DialogTitle")
        title.setAlignment(Qt.AlignCenter)
        title.installEventFilter(self._frameless_drag_filter)
        root.addWidget(title)

        self.table = QTableWidget(self)
        self.table.setObjectName("AssignmentTable")
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Roll / Fertigkeit", "Bonus"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 80)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)
        root.addWidget(self.table)

        edit_row = QHBoxLayout()
        edit_row.setSpacing(8)
        self.roll_combo = QComboBox(self)
        self.roll_combo.setObjectName("RollSelect")
        for option in self._roll_options:
            if not isinstance(option, dict):
                continue
            roll_id = str(option.get("roll_id", "") or "").strip()
            roll_name = str(option.get("roll_name", "") or "").strip()
            if not roll_id and not roll_name:
                continue
            self.roll_combo.addItem(roll_name or roll_id, {"roll_id": roll_id, "roll_name": roll_name})
        self.modifier_spin = QSpinBox(self)
        self.modifier_spin.setObjectName("BonusInput")
        self.modifier_spin.setRange(-999, 999)
        self.modifier_spin.setValue(0)
        self.modifier_spin.setFixedWidth(78)
        add_button = QPushButton("Hinzufügen", self)
        delete_button = QPushButton("Löschen", self)
        add_button.setObjectName("UtilityButton")
        delete_button.setObjectName("UtilityButton")
        add_button.setCursor(Qt.PointingHandCursor)
        delete_button.setCursor(Qt.PointingHandCursor)
        edit_row.addWidget(self.roll_combo, 1)
        edit_row.addWidget(self.modifier_spin)
        edit_row.addWidget(add_button)
        edit_row.addWidget(delete_button)
        root.addLayout(edit_row)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        save_button = QPushButton("Speichern", self)
        cancel_button = QPushButton("Abbrechen", self)
        save_button.setObjectName("ActionButton")
        cancel_button.setObjectName("ActionButton")
        save_button.setCursor(Qt.PointingHandCursor)
        cancel_button.setCursor(Qt.PointingHandCursor)
        save_button.setFixedHeight(36)
        cancel_button.setFixedHeight(36)
        save_button.setMinimumWidth(130)
        cancel_button.setMinimumWidth(130)
        buttons_row.addStretch()
        buttons_row.addWidget(save_button)
        buttons_row.addWidget(cancel_button)
        root.addLayout(buttons_row)

        self.setMinimumSize(500, 360)
        self._load_modifiers(modifiers)

        add_button.clicked.connect(self._add_assignment)
        delete_button.clicked.connect(self._delete_selected_assignment)
        save_button.clicked.connect(self._save)
        cancel_button.clicked.connect(self.reject)
        if close_button is not None:
            close_button.raise_()

    def modifiers(self):
        return list(self._result_modifiers)

    def _load_modifiers(self, modifiers):
        self.table.setRowCount(0)
        if not isinstance(modifiers, list):
            return
        for modifier in modifiers:
            if not isinstance(modifier, dict):
                continue
            self._append_assignment(
                str(modifier.get("roll_id", "") or "").strip(),
                str(modifier.get("roll_name", "") or "").strip(),
                modifier.get("modifier", 0),
            )

    def _append_assignment(self, roll_id, roll_name, modifier):
        try:
            modifier_value = int(modifier)
        except Exception:
            return
        if not roll_id and not roll_name:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)
        roll_item = QTableWidgetItem(roll_name or roll_id)
        roll_item.setData(Qt.UserRole, {"roll_id": roll_id, "roll_name": roll_name})
        bonus_item = QTableWidgetItem(f"{modifier_value:+d}")
        bonus_item.setData(Qt.UserRole, modifier_value)
        bonus_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        roll_item.setForeground(QColor(TEXT))
        bonus_item.setForeground(QColor(VALUE_BLUE))
        self.table.setItem(row, 0, roll_item)
        self.table.setItem(row, 1, bonus_item)

    def _add_assignment(self):
        data = self.roll_combo.currentData()
        if not isinstance(data, dict):
            return
        self._append_assignment(
            str(data.get("roll_id", "") or "").strip(),
            str(data.get("roll_name", "") or "").strip(),
            self.modifier_spin.value(),
        )

    def _delete_selected_assignment(self):
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return
        for index in sorted(selected, key=lambda item: item.row(), reverse=True):
            self.table.removeRow(index.row())

    def _save(self):
        result = []
        for row in range(self.table.rowCount()):
            roll_item = self.table.item(row, 0)
            bonus_item = self.table.item(row, 1)
            if roll_item is None or bonus_item is None:
                continue
            data = roll_item.data(Qt.UserRole)
            if not isinstance(data, dict):
                data = {}
            try:
                modifier_value = int(bonus_item.data(Qt.UserRole))
            except Exception:
                continue
            roll_id = str(data.get("roll_id", "") or "").strip()
            roll_name = str(data.get("roll_name", "") or roll_item.text() or "").strip()
            if not roll_id and not roll_name:
                continue
            result.append({"roll_id": roll_id, "roll_name": roll_name, "modifier": modifier_value})
        self._result_modifiers = result
        self.accept()


def _asset_path(window, relative_path):
    rel = str(relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not rel:
        return None
    candidates = []
    try:
        theme_base = window.theme_asset_base_path
        assets_dir = window.assets_dir
        candidates.extend(
            [
                theme_base / rel,
                theme_base / "ui" / rel,
                assets_dir / "themes" / "diablo" / rel,
                assets_dir / "themes" / "diablo" / "ui" / rel,
                assets_dir / rel,
            ]
        )
    except Exception:
        return None
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue
    return None


def _asset_url(window, relative_path):
    path = _asset_path(window, relative_path)
    return path.as_posix() if path is not None else ""


def _add_dialog_background(dialog, window, width, height):
    path = _asset_path(window, "panels/main_Frame.png")
    if path is None:
        path = _asset_path(window, "panels/shared_skils_panel_frame.png")
    if path is None:
        return
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return
    label = QLabel(dialog)
    label.setGeometry(0, 0, width, height)
    label.setPixmap(pixmap.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    label.lower()


def _make_close_button(dialog, window):
    path = _asset_path(window, "ui_elements/icons/x.jpg") or _asset_path(window, "icons/x.jpg")
    if path is None:
        return None
    button = QPushButton(dialog)
    button.setGeometry(dialog.width() - 42, 14, 24, 24)
    button.setIcon(QIcon(str(path)))
    button.setIconSize(button.size())
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
    button.raise_()
    return button


def _dialog_stylesheet(window):
    button_asset = _asset_url(window, "buttons/menu_button_medium.png")
    small_button_asset = _asset_url(window, "buttons/menu_button_small.png")
    value_frame = _asset_url(window, "frames/256x122_box.png")
    table_frame = _asset_url(window, "frames/1024x122_box.png")
    button_background = (
        f"border-image: url({button_asset}) 0 0 0 0 stretch stretch;"
        if button_asset
        else "background: rgba(30, 22, 14, 230); border: 1px solid rgba(216, 170, 76, 130);"
    )
    small_button_background = (
        f"border-image: url({small_button_asset}) 0 0 0 0 stretch stretch;"
        if small_button_asset
        else button_background
    )
    input_background = (
        f"border-image: url({value_frame}) 0 0 0 0 stretch stretch;"
        if value_frame
        else "background: rgba(0, 0, 0, 150); border: 1px solid rgba(242, 210, 139, 90);"
    )
    table_background = (
        f"border-image: url({table_frame}) 0 0 0 0 stretch stretch;"
        if table_frame
        else f"background: {DARK_PANEL}; border: 1px solid rgba(242, 210, 139, 90);"
    )
    return f"""
QDialog {{
    background: transparent;
    color: {TEXT};
    border: none;
    font-size: 13px;
}}
QLabel {{
    color: {TEXT};
}}
QLabel#DialogTitle {{
    color: {GOLD};
    font-size: 18px;
    font-weight: 700;
    padding: 0px 34px 2px 34px;
}}
QTableWidget#AssignmentTable {{
    {table_background}
    color: {TEXT};
    gridline-color: rgba(242, 210, 139, 75);
    selection-background-color: rgba(242, 210, 139, 34);
    selection-color: #ffffff;
    padding: 4px;
    border: none;
}}
QTableWidget#AssignmentTable::item {{
    background: rgba(0, 0, 0, 18);
    padding: 3px 6px;
}}
QTableWidget#AssignmentTable::item:selected {{
    background: rgba(64, 45, 18, 170);
    color: #ffffff;
}}
QHeaderView::section {{
    background: rgba(24, 16, 8, 190);
    color: {GOLD};
    font-weight: 700;
    border: 1px solid rgba(242, 210, 139, 85);
    padding: 4px;
}}
QComboBox#RollSelect, QSpinBox#BonusInput {{
    {input_background}
    border: none;
    color: {VALUE_BLUE};
    padding: 4px 8px;
    min-height: 28px;
    selection-background-color: rgba(242, 210, 139, 45);
    selection-color: #ffffff;
}}
QComboBox#RollSelect QAbstractItemView {{
    background: #211812;
    color: {TEXT};
    border: 1px solid rgba(242, 210, 139, 95);
    selection-background-color: rgba(64, 45, 18, 190);
    selection-color: #ffffff;
}}
QComboBox#RollSelect::drop-down {{
    border: none;
    width: 24px;
}}
QSpinBox#BonusInput::up-button, QSpinBox#BonusInput::down-button {{
    width: 0px;
    height: 0px;
    border: none;
}}
QPushButton#UtilityButton {{
    {small_button_background}
    border: none;
    color: {GOLD};
    font-weight: 700;
    min-width: 92px;
    min-height: 30px;
    padding: 2px 8px;
}}
QPushButton#ActionButton {{
    {button_background}
    border: none;
    color: {GOLD};
    font-weight: 700;
    padding: 3px 14px;
}}
QPushButton#UtilityButton:hover, QPushButton#ActionButton:hover {{
    color: #fff3d6;
}}
QPushButton#UtilityButton:pressed, QPushButton#ActionButton:pressed {{
    color: #ffffff;
}}
QScrollBar:vertical {{
    background: rgba(0, 0, 0, 120);
    width: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: rgba(242, 210, 139, 120);
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}
QScrollBar:horizontal {{
    background: rgba(0, 0, 0, 120);
    height: 10px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(242, 210, 139, 120);
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
}}
"""
