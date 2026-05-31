from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


def open_resource_dialog(parent, model, callbacks=None, style_context=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    style_context = style_context if isinstance(style_context, dict) else {}

    resource_id = str(model.get("resource_id", "") or "").strip().lower()
    label = str(model.get("label", resource_id.upper()) or resource_id.upper())
    title = str(model.get("title", f"{label} verwalten") or f"{label} verwalten")
    current_value = int(model.get("current", 0) or 0)
    max_value = int(model.get("max", current_value) or 0)
    roll_title_text = str(model.get("roll_title", "Roll") or "Roll")
    roll_command = str(model.get("roll_command", "/r 1d20") or "/r 1d20")

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.resize(
        int(style_context.get("width", 390) or 390),
        int(style_context.get("height", 260) or 260),
    )

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)

    title_label = QLabel(title, dialog)
    title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #f2d28b;")
    layout.addWidget(title_label)

    info_label = QLabel(dialog)
    info_label.setStyleSheet("color: #e8e0c8; font-weight: 600;")
    layout.addWidget(info_label)

    value_row = QHBoxLayout()
    value_row.addWidget(QLabel("Wert:", dialog))
    minus_step_button = QPushButton("-", dialog)
    plus_step_button = QPushButton("+", dialog)
    amount_input = QSpinBox(dialog)
    amount_input.setRange(0, 9999)
    amount_input.setValue(1)
    value_row.addWidget(minus_step_button)
    value_row.addWidget(amount_input, 1)
    value_row.addWidget(plus_step_button)
    layout.addLayout(value_row)

    action_row = QHBoxLayout()
    add_button = QPushButton(f"+ {label}", dialog)
    subtract_button = QPushButton(f"- {label}", dialog)
    set_button = QPushButton("Setzen", dialog)
    action_row.addWidget(add_button)
    action_row.addWidget(subtract_button)
    action_row.addWidget(set_button)
    layout.addLayout(action_row)

    utility_row = QHBoxLayout()
    zero_button = QPushButton("Auf 0", dialog)
    copy_button = QPushButton("Kopieren", dialog)
    close_button = QPushButton("Schließen", dialog)
    utility_row.addWidget(zero_button)
    utility_row.addWidget(copy_button)
    utility_row.addWidget(close_button)
    layout.addLayout(utility_row)

    roll_title = QLabel(roll_title_text, dialog)
    roll_title.setStyleSheet("color: #f2d28b; font-weight: 700;")
    layout.addWidget(roll_title)
    roll_preview = QLineEdit(roll_command, dialog)
    roll_preview.setReadOnly(True)
    layout.addWidget(roll_preview)
    roll_copy_button = QPushButton("Roll kopieren", dialog)
    layout.addWidget(roll_copy_button)

    dialog.setStyleSheet(
        "QDialog { background: #1d1a16; color: #e8e0c8; }"
        "QPushButton { background: #3a2d20; border: 1px solid #8a6a35; color: #f4ead0; padding: 6px 10px; }"
        "QPushButton:hover { background: #4b3926; }"
        "QLineEdit, QSpinBox { background: #12100d; border: 1px solid #6e5831; color: #ffffff; padding: 4px; }"
    )

    state = {"current": current_value, "max": max_value}

    def refresh_info():
        info_label.setText(f"Aktuell {label}: {state['current']} / {state['max']}")

    def clamp(value):
        return max(0, min(int(value), state["max"]))

    def save_current(new_value, reason, reduce_lifeforce=False):
        save_callback = callbacks.get("save_current")
        if callable(save_callback):
            save_callback(clamp(new_value), reason, reduce_lifeforce=reduce_lifeforce)
        dialog.accept()

    def add_resource():
        save_current(state["current"] + amount_input.value(), f"{label} add")

    def subtract_resource():
        amount = amount_input.value()
        raw_new = state["current"] - amount
        reduce_lifeforce = resource_id == "hp" and amount > 0 and state["current"] > 0 and raw_new <= 0
        save_current(raw_new, f"{label} subtract", reduce_lifeforce=reduce_lifeforce)

    def set_resource():
        save_current(amount_input.value(), f"{label} set")

    def zero_resource():
        save_current(0, f"{label} zero")

    minus_step_button.clicked.connect(lambda: amount_input.setValue(max(0, amount_input.value() - 1)))
    plus_step_button.clicked.connect(lambda: amount_input.setValue(amount_input.value() + 1))
    add_button.clicked.connect(add_resource)
    subtract_button.clicked.connect(subtract_resource)
    set_button.clicked.connect(set_resource)
    zero_button.clicked.connect(zero_resource)
    copy_button.clicked.connect(lambda: QApplication.clipboard().setText(str(state["current"])))
    roll_copy_button.clicked.connect(lambda: QApplication.clipboard().setText(roll_preview.text()))
    close_button.clicked.connect(dialog.reject)

    refresh_info()
    return dialog.exec()
