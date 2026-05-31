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
from PySide6.QtGui import QIcon


def open_resource_dialog(parent, model, callbacks=None, style_context=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    style_context = style_context if isinstance(style_context, dict) else {}
    roll_layout = style_context.get("roll_layout", {})
    if not isinstance(roll_layout, dict):
        roll_layout = {}
    ui_layout = style_context.get("ui_layout", {})
    if not isinstance(ui_layout, dict):
        ui_layout = {}
    dialog_cfg = roll_layout.get("dialog", {})
    if not isinstance(dialog_cfg, dict):
        dialog_cfg = {}
    counter_cfg = roll_layout.get("counter", {})
    if not isinstance(counter_cfg, dict):
        counter_cfg = {}
    roll_preview_cfg = roll_layout.get("roll_preview", {})
    if not isinstance(roll_preview_cfg, dict):
        roll_preview_cfg = {}
    buttons_cfg = roll_layout.get("buttons", {})
    if not isinstance(buttons_cfg, dict):
        buttons_cfg = {}
    sections_cfg = roll_layout.get("sections", {})
    if not isinstance(sections_cfg, dict):
        sections_cfg = {}
    menu_button_cfg = ui_layout.get("menu_button_medium", {})
    if not isinstance(menu_button_cfg, dict):
        menu_button_cfg = {}

    resource_id = str(model.get("resource_id", "") or "").strip().lower()
    label = str(model.get("label", resource_id.upper()) or resource_id.upper())
    title = str(model.get("title", f"{label} verwalten") or f"{label} verwalten")
    current_value = int(model.get("current", 0) or 0)
    max_value = int(model.get("max", current_value) or 0)
    roll_title_text = str(model.get("roll_title", "Roll") or "Roll")
    roll_command = str(model.get("roll_command", "/r 1d20") or "/r 1d20")
    text_color = str(dialog_cfg.get("text_color", "#e8e0c8"))
    accent_color = str(dialog_cfg.get("accent_color", "#f2d28b"))
    border_color = str(dialog_cfg.get("border_color", "#8a6a32"))
    dialog_bg = str(dialog_cfg.get("background", "#1d1a16"))
    base_font_size = int(dialog_cfg.get("font_size", 13) or 13)
    title_font_size = int(dialog_cfg.get("title_font_size", 18) or 18)
    spacing = int(sections_cfg.get("spacing", 10) or 10)
    preview_bg = str(roll_preview_cfg.get("background", "#101214"))
    preview_border = str(roll_preview_cfg.get("border_color", border_color))
    preview_text = str(roll_preview_cfg.get("text_color", accent_color))
    preview_font_size = int(roll_preview_cfg.get("font_size", 22) or 22)
    counter_button_bg = str(counter_cfg.get("button_background", "#34383c"))
    counter_button_text = str(counter_cfg.get("button_text_color", "#ffffff"))
    counter_button_border = str(counter_cfg.get("button_border_color", "#5c6268"))

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.resize(
        int(style_context.get("width", 390) or 390),
        int(style_context.get("height", 260) or 260),
    )

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(spacing)

    title_label = QLabel(title, dialog)
    title_label.setStyleSheet(f"font-size: {title_font_size}px; font-weight: 700; color: {accent_color};")
    layout.addWidget(title_label)

    info_label = QLabel(dialog)
    info_label.setStyleSheet(f"color: {text_color}; font-weight: 600; font-size: {base_font_size}px;")
    layout.addWidget(info_label)

    value_row = QHBoxLayout()
    value_row.addWidget(QLabel("Wert:", dialog))
    minus_step_button = QPushButton("-", dialog)
    plus_step_button = QPushButton("+", dialog)
    for step_button in (minus_step_button, plus_step_button):
        step_button.setFixedSize(
            int(counter_cfg.get("button_w", 30) or 30),
            int(counter_cfg.get("button_h", 26) or 26),
        )
        step_button.setStyleSheet(
            f"background: {counter_button_bg}; color: {counter_button_text}; "
            f"border: 1px solid {counter_button_border};"
        )
    if bool(counter_cfg.get("use_assets", False)):
        load_ui_pixmap = style_context.get("load_ui_pixmap")
        if callable(load_ui_pixmap):
            minus_pixmap = load_ui_pixmap(str(counter_cfg.get("minus_asset", "") or ""))
            plus_pixmap = load_ui_pixmap(str(counter_cfg.get("plus_asset", "") or ""))
            if minus_pixmap is not None:
                minus_step_button.setText("")
                minus_step_button.setIcon(QIcon(minus_pixmap))
            if plus_pixmap is not None:
                plus_step_button.setText("")
                plus_step_button.setIcon(QIcon(plus_pixmap))
    amount_input = QSpinBox(dialog)
    amount_input.setRange(0, 9999)
    amount_input.setValue(1)
    value_row.addWidget(minus_step_button)
    value_row.addWidget(amount_input, 1)
    value_row.addWidget(plus_step_button)
    layout.addLayout(value_row)

    dialog.setStyleSheet(
        f"QDialog {{ background: {dialog_bg}; color: {text_color}; font-size: {base_font_size}px; }}"
        f"QPushButton {{ background: {counter_button_bg}; border: 1px solid {counter_button_border}; "
        f"color: {counter_button_text}; padding: 6px 10px; }}"
        f"QPushButton:hover {{ background: {preview_bg}; }}"
        f"QLineEdit, QSpinBox {{ background: {preview_bg}; border: 1px solid {preview_border}; "
        f"color: {preview_text}; padding: 4px; }}"
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

    def make_action_button(text, callback, width=110):
        factory = style_context.get("asset_button_factory")
        button_cfg = {
            "w": width,
            "h": 32,
            "asset": str(menu_button_cfg.get("asset", "buttons/menu_button_medium.png")),
            "font_size": int(menu_button_cfg.get("font_size", base_font_size) or base_font_size),
            "color": accent_color,
        }
        if callable(factory):
            widget = factory(dialog, text, callback, button_cfg)
            if widget is not None:
                return widget
        button = QPushButton(text, dialog)
        button.clicked.connect(callback)
        return button

    action_row = QHBoxLayout()
    action_row.addWidget(make_action_button(f"+ {label}", add_resource))
    action_row.addWidget(make_action_button(f"- {label}", subtract_resource))
    action_row.addWidget(make_action_button("Setzen", set_resource))
    layout.addLayout(action_row)

    utility_row = QHBoxLayout()
    utility_row.addWidget(make_action_button("Auf 0", zero_resource))
    utility_row.addWidget(make_action_button(str(buttons_cfg.get("copy_text", "Kopieren")), lambda: QApplication.clipboard().setText(str(state["current"]))))
    utility_row.addWidget(make_action_button(str(buttons_cfg.get("close_text", "Schließen")), dialog.reject))
    layout.addLayout(utility_row)

    roll_title = QLabel(roll_title_text, dialog)
    roll_title.setStyleSheet(f"color: {accent_color}; font-weight: 700;")
    layout.addWidget(roll_title)
    roll_preview = QLineEdit(roll_command, dialog)
    roll_preview.setReadOnly(True)
    roll_preview.setStyleSheet(
        f"font-size: {preview_font_size}px; font-weight: 700; color: {preview_text}; "
        f"background: {preview_bg}; border: 1px solid {preview_border}; padding: 4px;"
    )
    layout.addWidget(roll_preview)
    layout.addWidget(make_action_button("Roll kopieren", lambda: QApplication.clipboard().setText(roll_preview.text()), 150))

    minus_step_button.clicked.connect(lambda: amount_input.setValue(max(0, amount_input.value() - 1)))
    plus_step_button.clicked.connect(lambda: amount_input.setValue(amount_input.value() + 1))

    refresh_info()
    return dialog.exec()
