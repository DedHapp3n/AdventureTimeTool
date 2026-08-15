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


class InventoryRollBonusDialog(QDialog):
    def __init__(self, parent, item_name, roll_options, modifiers=None):
        super().__init__(parent)
        self.setWindowTitle("Inventar Rollbonus")
        self.setModal(True)
        self._roll_options = roll_options if isinstance(roll_options, list) else []
        self._result_modifiers = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel(str(item_name or "(ohne Name)"))
        title.setStyleSheet("font-weight: 700;")
        root.addWidget(title)

        self.table = QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Roll / Fertigkeit", "Bonus"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 80)
        root.addWidget(self.table)

        edit_row = QHBoxLayout()
        self.roll_combo = QComboBox(self)
        for option in self._roll_options:
            if not isinstance(option, dict):
                continue
            roll_id = str(option.get("roll_id", "") or "").strip()
            roll_name = str(option.get("roll_name", "") or "").strip()
            if not roll_id and not roll_name:
                continue
            self.roll_combo.addItem(roll_name or roll_id, {"roll_id": roll_id, "roll_name": roll_name})
        self.modifier_spin = QSpinBox(self)
        self.modifier_spin.setRange(-999, 999)
        self.modifier_spin.setValue(0)
        add_button = QPushButton("Hinzufügen", self)
        delete_button = QPushButton("Löschen", self)
        edit_row.addWidget(self.roll_combo, 1)
        edit_row.addWidget(self.modifier_spin)
        edit_row.addWidget(add_button)
        edit_row.addWidget(delete_button)
        root.addLayout(edit_row)

        buttons_row = QHBoxLayout()
        save_button = QPushButton("Speichern", self)
        cancel_button = QPushButton("Abbrechen", self)
        buttons_row.addStretch()
        buttons_row.addWidget(save_button)
        buttons_row.addWidget(cancel_button)
        root.addLayout(buttons_row)

        self.setMinimumSize(460, 320)
        self._load_modifiers(modifiers)

        add_button.clicked.connect(self._add_assignment)
        delete_button.clicked.connect(self._delete_selected_assignment)
        save_button.clicked.connect(self._save)
        cancel_button.clicked.connect(self.reject)

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
