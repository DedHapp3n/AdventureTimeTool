from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
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

from ui_controls import create_step_button


def _signed(value):
    number = int(value)
    return f"+{number}" if number > 0 else str(number) if number < 0 else ""


class CompanionRollDialog(QDialog):
    def __init__(self, parent, companion_name, roll_options, rolls=None, on_change=None):
        super().__init__(parent)
        self.setWindowTitle(f"Companion-Würfe: {companion_name}")
        self.setModal(True)
        self.resize(600, 520)
        self._on_change = on_change
        self._loading = False
        self.setStyleSheet(
            "QDialog { background: #17130e; color: #eadfca; }"
            "QLabel { color: #f2d28b; font-weight: 700; }"
            "QTableWidget, QComboBox, QSpinBox { background: rgba(5,4,3,220); color: #ffffff; border: 1px solid rgba(242,210,139,110); padding: 4px; }"
            "QHeaderView::section { background: #24180c; color: #f2d28b; padding: 5px; border: 1px solid rgba(242,210,139,90); }"
            "QPushButton { background: #28190b; color: #f2d28b; border: 1px solid #8a6a32; padding: 6px 12px; font-weight: 700; }"
            "QPushButton:hover { color: #ffffff; border-color: #f2d28b; }"
        )

        root = QVBoxLayout(self)
        title = QLabel(str(companion_name or "Companion"), self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; color: #f2d28b;")
        root.addWidget(title)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Roll / Fertigkeit", "Wert", "Bonus/Malus"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnWidth(0, 340)
        self.table.setColumnWidth(1, 80)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._load_selected_roll)
        root.addWidget(self.table)

        root.addWidget(QLabel("Roll / Fertigkeit", self))
        self.roll_combo = QComboBox(self)
        for option in roll_options if isinstance(roll_options, list) else []:
            if not isinstance(option, dict):
                continue
            roll_id = str(option.get("roll_id", "") or "").strip()
            roll_name = str(option.get("roll_name", "") or "").strip()
            if roll_id or roll_name:
                self.roll_combo.addItem(roll_name or roll_id, {"roll_id": roll_id, "roll_name": roll_name})
        root.addWidget(self.roll_combo)

        self.value_spin = self._add_number_row(root, "Fertigkeitswert", "companionRollValue")
        self.modifier_spin = self._add_number_row(root, "Bonus / Malus", "companionRollModifier")
        self.preview = QLabel("Wurf: 1d20", self)
        self.preview.setObjectName("companionRollPreview")
        self.preview.setStyleSheet("font-size: 18px; color: #ffffff; padding: 6px 0px;")
        root.addWidget(self.preview)

        actions = QHBoxLayout()
        delete_button = QPushButton("Löschen", self)
        delete_button.setObjectName("companionRollDelete")
        close_button = QPushButton("Schließen", self)
        close_button.setObjectName("companionRollClose")
        actions.addWidget(delete_button)
        actions.addStretch()
        actions.addWidget(close_button)
        root.addLayout(actions)

        self._loading = True
        for roll in rolls if isinstance(rolls, list) else []:
            if isinstance(roll, dict):
                self._upsert_roll(roll)
        self._loading = False
        self.roll_combo.currentIndexChanged.connect(self._select_or_create_current_roll)
        self.value_spin.valueChanged.connect(self._editor_changed)
        self.modifier_spin.valueChanged.connect(self._editor_changed)
        delete_button.clicked.connect(self._delete_selected)
        close_button.clicked.connect(self.accept)
        if self.table.rowCount():
            self.table.selectRow(0)
        elif self.roll_combo.count():
            self._select_or_create_current_roll()
        self._update_preview()

    def _add_number_row(self, root, title, object_name):
        root.addWidget(QLabel(title, self))
        row = QHBoxLayout()
        minus = create_step_button(self, "-", f"{title} verringern")
        spin = QSpinBox(self)
        spin.setObjectName(object_name)
        spin.setRange(-999, 999)
        spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        spin.setAlignment(Qt.AlignCenter)
        spin.setFixedWidth(110)
        plus = create_step_button(self, "+", f"{title} erhöhen")
        minus.clicked.connect(lambda: spin.setValue(spin.value() - 1))
        plus.clicked.connect(lambda: spin.setValue(spin.value() + 1))
        row.addStretch()
        row.addWidget(minus)
        row.addWidget(spin)
        row.addWidget(plus)
        row.addStretch()
        root.addLayout(row)
        return spin

    def rolls(self):
        result = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            modifier_item = self.table.item(row, 2)
            data = name_item.data(Qt.UserRole) if name_item is not None else {}
            if isinstance(data, dict) and value_item is not None and modifier_item is not None:
                result.append({
                    "roll_id": str(data.get("roll_id", "") or ""),
                    "roll_name": str(data.get("roll_name", "") or name_item.text()),
                    "value": int(value_item.data(Qt.UserRole) or 0),
                    "modifier": int(modifier_item.data(Qt.UserRole) or 0),
                })
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
        try:
            value = int(roll.get("value", 0))
        except Exception:
            value = 0
        try:
            modifier = int(roll.get("modifier", 0))
        except Exception:
            modifier = 0
        row = self._find_row(identity)
        if row < 0:
            row = self.table.rowCount()
            self.table.insertRow(row)
        name_item = QTableWidgetItem(data["roll_name"] or data["roll_id"])
        name_item.setData(Qt.UserRole, data)
        self.table.setItem(row, 0, name_item)
        for column, number in ((1, value), (2, modifier)):
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
        identity = self._identity(data)
        row = self._find_row(identity)
        if row < 0:
            row = self._upsert_roll({**data, "value": 0, "modifier": 0})
            self._emit_change()
        self.table.selectRow(row)

    def _load_selected_roll(self):
        row = self.table.currentRow()
        if row < 0:
            return
        data = self.table.item(row, 0).data(Qt.UserRole)
        self._loading = True
        if isinstance(data, dict):
            identity = self._identity(data)
            for index in range(self.roll_combo.count()):
                option = self.roll_combo.itemData(index)
                if isinstance(option, dict) and self._identity(option) == identity:
                    self.roll_combo.setCurrentIndex(index)
                    break
        self.value_spin.setValue(int(self.table.item(row, 1).data(Qt.UserRole) or 0))
        self.modifier_spin.setValue(int(self.table.item(row, 2).data(Qt.UserRole) or 0))
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
        for column, number in ((1, self.value_spin.value()), (2, self.modifier_spin.value())):
            item = self.table.item(row, column)
            item.setText(str(number))
            item.setData(Qt.UserRole, number)
        self._update_preview()
        self._emit_change()

    def _update_preview(self):
        self.preview.setText(f"Wurf: 1d20{_signed(self.value_spin.value())}{_signed(self.modifier_spin.value())}")

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
            self.value_spin.setValue(0)
            self.modifier_spin.setValue(0)
            self._loading = False
            self._update_preview()

    def _emit_change(self):
        if not self._loading and callable(self._on_change):
            self._on_change(self.rolls())
