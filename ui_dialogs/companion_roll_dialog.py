from PySide6.QtCore import Qt
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


class CompanionRollDialog(QDialog):
    def __init__(self, parent, companion_name, roll_options, rolls=None):
        super().__init__(parent)
        self.setWindowTitle(f"Companion-Würfe: {companion_name}")
        self.setModal(True)
        self.resize(560, 390)
        self._result_rolls = []
        self.setStyleSheet(
            "QDialog { background: #17130e; color: #eadfca; }"
            "QLabel { color: #f2d28b; font-weight: 700; }"
            "QTableWidget, QComboBox, QSpinBox { background: rgba(5,4,3,220); color: #ffffff; "
            "border: 1px solid rgba(242,210,139,110); }"
            "QHeaderView::section { background: #24180c; color: #f2d28b; padding: 5px; "
            "border: 1px solid rgba(242,210,139,90); }"
            "QPushButton { background: #28190b; color: #f2d28b; border: 1px solid #8a6a32; "
            "padding: 6px 12px; font-weight: 700; }"
            "QPushButton:hover { color: #ffffff; border-color: #f2d28b; }"
        )

        root = QVBoxLayout(self)
        title = QLabel(str(companion_name or "Companion"), self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; color: #f2d28b;")
        root.addWidget(title)

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Roll / Fertigkeit", "Wert"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnWidth(0, 390)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._load_selected_roll)
        root.addWidget(self.table)

        edit_row = QHBoxLayout()
        self.roll_combo = QComboBox(self)
        for option in roll_options if isinstance(roll_options, list) else []:
            if not isinstance(option, dict):
                continue
            roll_id = str(option.get("roll_id", "") or "").strip()
            roll_name = str(option.get("roll_name", "") or "").strip()
            if roll_id or roll_name:
                self.roll_combo.addItem(roll_name or roll_id, {"roll_id": roll_id, "roll_name": roll_name})
        self.value_spin = QSpinBox(self)
        self.value_spin.setRange(-999, 999)
        self.value_spin.setFixedWidth(80)
        apply_button = QPushButton("Übernehmen", self)
        delete_button = QPushButton("Löschen", self)
        edit_row.addWidget(self.roll_combo, 1)
        edit_row.addWidget(self.value_spin)
        edit_row.addWidget(apply_button)
        edit_row.addWidget(delete_button)
        root.addLayout(edit_row)

        actions = QHBoxLayout()
        save_button = QPushButton("Speichern", self)
        cancel_button = QPushButton("Abbrechen", self)
        actions.addStretch()
        actions.addWidget(save_button)
        actions.addWidget(cancel_button)
        root.addLayout(actions)

        for roll in rolls if isinstance(rolls, list) else []:
            if isinstance(roll, dict):
                self._upsert_roll(roll)
        apply_button.clicked.connect(self._apply_roll)
        delete_button.clicked.connect(self._delete_selected)
        save_button.clicked.connect(self._save)
        cancel_button.clicked.connect(self.reject)

    def rolls(self):
        return list(self._result_rolls)

    def _upsert_roll(self, roll):
        roll_id = str(roll.get("roll_id", "") or "").strip()
        roll_name = str(roll.get("roll_name", "") or "").strip()
        if not roll_id and not roll_name:
            return
        try:
            value = int(roll.get("value", 0))
        except Exception:
            value = 0
        identity = roll_id or roll_name.casefold()
        target_row = -1
        for row in range(self.table.rowCount()):
            data = self.table.item(row, 0).data(Qt.UserRole)
            if isinstance(data, dict) and (data.get("roll_id") or str(data.get("roll_name", "")).casefold()) == identity:
                target_row = row
                break
        if target_row < 0:
            target_row = self.table.rowCount()
            self.table.insertRow(target_row)
        name_item = QTableWidgetItem(roll_name or roll_id)
        name_item.setData(Qt.UserRole, {"roll_id": roll_id, "roll_name": roll_name})
        value_item = QTableWidgetItem(str(value))
        value_item.setData(Qt.UserRole, value)
        value_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(target_row, 0, name_item)
        self.table.setItem(target_row, 1, value_item)

    def _apply_roll(self):
        data = self.roll_combo.currentData()
        if isinstance(data, dict):
            self._upsert_roll({**data, "value": self.value_spin.value()})

    def _load_selected_roll(self):
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        value_item = self.table.item(row, 1)
        data = item.data(Qt.UserRole) if item is not None else {}
        if isinstance(data, dict):
            identity = data.get("roll_id") or data.get("roll_name")
            for index in range(self.roll_combo.count()):
                option = self.roll_combo.itemData(index)
                if isinstance(option, dict) and (option.get("roll_id") or option.get("roll_name")) == identity:
                    self.roll_combo.setCurrentIndex(index)
                    break
        if value_item is not None:
            self.value_spin.setValue(int(value_item.data(Qt.UserRole) or 0))

    def _delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def _save(self):
        result = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            data = name_item.data(Qt.UserRole) if name_item is not None else {}
            if not isinstance(data, dict) or value_item is None:
                continue
            result.append(
                {
                    "roll_id": str(data.get("roll_id", "") or ""),
                    "roll_name": str(data.get("roll_name", "") or name_item.text()),
                    "value": int(value_item.data(Qt.UserRole) or 0),
                }
            )
        self._result_rolls = result
        self.accept()
