from html import escape

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
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter

from ui_controls import create_step_button

from ui_dialogs.window_chrome import install_frameless_dialog_chrome


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
    resource_cfg = roll_layout.get("resource_dialog", {})
    value_cfg = resource_cfg.get("value", {})
    command_cfg = resource_cfg.get("command", {})
    buttons_cfg = {**roll_layout.get("buttons", {}), **resource_cfg.get("buttons", {})}
    close_button_cfg = resource_cfg.get("close_button", ui_layout.get("window_close_button", {}))
    load_ui_pixmap = style_context.get("load_ui_pixmap")

    resource_id = str(model.get("resource_id", "") or "").strip().lower()
    label = str(model.get("label", resource_id.upper()) or resource_id.upper())
    title = str(model.get("title", f"{label} verwalten") or f"{label} verwalten")
    current_value = int(model.get("current", 0) or 0)
    max_value = int(model.get("max", current_value) or 0)
    roll_title_text = str(model.get("roll_title", "Roll") or "Roll")
    roll_command = str(model.get("roll_command", "/r 1d20") or "/r 1d20")
    text_color = str(resource_cfg.get("text_color", "#eadfca"))
    accent_color = str(resource_cfg.get("accent_color", dialog_cfg.get("accent_color", "#f2d28b")))
    value_color = str(resource_cfg.get("value_color", "#7fd0ff"))
    base_font_size = int(resource_cfg.get("font_size", 13))
    title_font_size = int(resource_cfg.get("title_font_size", 20))
    spacing = int(resource_cfg.get("spacing", 8))

    dialog = _ResourceDialog(parent, resource_cfg, load_ui_pixmap)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    install_frameless_dialog_chrome(dialog)
    dialog.resize(int(resource_cfg.get("w", 430)), int(resource_cfg.get("h", 350)))
    dialog.setStyleSheet(
        f"QDialog {{ background: transparent; color: {text_color}; font-size: {base_font_size}px; }}"
        f"QLabel {{ background: transparent; color: {text_color}; }}"
    )

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(*resource_cfg.get("margins", [26, 10, 26, 24]))
    layout.setSpacing(spacing)

    title_row = QHBoxLayout()
    title_label = QLabel(title, dialog)
    title_label.setStyleSheet(f"font-size: {title_font_size}px; font-weight: 700; color: {accent_color};")
    title_label.setAlignment(Qt.AlignCenter)
    title_label.installEventFilter(dialog._frameless_drag_filter)
    title_row.addWidget(title_label, 1)

    exit_button = QPushButton(dialog)
    exit_button.setText("")
    exit_button.setCursor(Qt.PointingHandCursor)
    exit_button.setFixedSize(int(close_button_cfg.get("w", 28)), int(close_button_cfg.get("h", 28)))
    title_label.setFixedHeight(exit_button.height())
    title_row.setSpacing(spacing)
    title_row.insertSpacing(0, exit_button.width())
    exit_button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
    close_asset = str(close_button_cfg.get("asset", "ui_elements/icons/x.jpg") or "")
    if close_asset and callable(load_ui_pixmap):
        close_pixmap = load_ui_pixmap(close_asset)
        if close_pixmap is not None:
            exit_button.setIcon(QIcon(close_pixmap))
            exit_button.setIconSize(exit_button.size())
    if exit_button.icon().isNull():
        exit_button.setText("X")
    exit_button.clicked.connect(dialog.reject)
    title_row.addWidget(exit_button, 0)
    layout.addLayout(title_row)

    info_label = QLabel(dialog)
    info_label.setAlignment(Qt.AlignCenter)
    info_label.setTextFormat(Qt.RichText)
    info_label.setStyleSheet(f"color: {text_color}; font-weight: 600; font-size: {base_font_size}px;")
    layout.addWidget(info_label)

    value_row = QHBoxLayout()
    value_row.addWidget(QLabel("Wert:", dialog))
    value_row.setSpacing(spacing)
    minus_step_button = create_step_button(dialog, "-", "Wert verringern")
    plus_step_button = create_step_button(dialog, "+", "Wert erhöhen")
    amount_input = QSpinBox(dialog)
    amount_input.setRange(0, 9999)
    amount_input.setValue(1)
    amount_input.setButtonSymbols(QSpinBox.NoButtons)
    amount_input.setFixedSize(int(value_cfg.get("w", 64)), int(value_cfg.get("h", 34)))
    amount_input.setAlignment(_field_alignment(value_cfg))
    amount_input.setStyleSheet(
        "QSpinBox {" + _field_style(parent, value_cfg, value_color, "frames/256x122_box.png") + "}"
        "QSpinBox QLineEdit { background: transparent; border: none; border-image: none; padding: 0px; }"
    )
    value_row.addWidget(minus_step_button)
    value_row.addWidget(amount_input)
    value_row.addWidget(plus_step_button)
    value_row.addStretch()
    layout.addLayout(value_row)

    state = {"current": current_value, "max": max_value}

    def refresh_info():
        info_label.setText(
            f'Aktuell {escape(label)}: <span style="color: {value_color};">'
            f'{state["current"]} / {state["max"]}</span>'
        )

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

    def make_action_button(text, callback, width=None):
        factory = style_context.get("asset_button_factory")
        button_cfg = {
            "w": int(width if width is not None else buttons_cfg.get("w", 110)),
            "h": int(buttons_cfg.get("h", 34)),
            "asset": str(buttons_cfg.get("asset", "buttons/menu_button_medium.png")),
            "font_size": int(buttons_cfg.get("font_size", base_font_size) or base_font_size),
            "color": accent_color,
        }
        if callable(factory):
            widget = factory(dialog, text, callback, button_cfg)
            if widget is not None:
                return widget
        button = QPushButton(text, dialog)
        button.setFixedSize(button_cfg["w"], button_cfg["h"])
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(_field_style(parent, {
            "frame": button_cfg["asset"], "font_size": button_cfg["font_size"], "padding": 0,
        }, accent_color, "buttons/menu_button_medium.png"))
        button.clicked.connect(callback)
        return button

    action_row = QHBoxLayout()
    action_row.setSpacing(spacing)
    action_row.addWidget(QLabel("Anwenden:", dialog))
    add_button = create_step_button(dialog, "+", f"{label} hinzufügen")
    subtract_button = create_step_button(dialog, "-", f"{label} abziehen")
    add_button.clicked.connect(add_resource)
    subtract_button.clicked.connect(subtract_resource)
    action_row.addWidget(add_button)
    action_row.addWidget(subtract_button)
    action_row.addStretch()
    action_row.addWidget(make_action_button("Setzen", set_resource))
    layout.addLayout(action_row)

    utility_row = QHBoxLayout()
    utility_row.setSpacing(spacing)
    utility_row.addWidget(make_action_button("Auf 0", zero_resource))
    utility_row.addWidget(make_action_button(str(buttons_cfg.get("copy_text", "Kopieren")), lambda: QApplication.clipboard().setText(str(state["current"]))))
    utility_row.addWidget(make_action_button(str(buttons_cfg.get("close_text", "Schließen")), dialog.reject))
    layout.addLayout(utility_row)

    roll_title = QLabel(roll_title_text, dialog)
    roll_title.setStyleSheet(f"color: {accent_color}; font-weight: 700;")
    layout.addWidget(roll_title)
    roll_preview = QLineEdit(roll_command, dialog)
    roll_preview.setReadOnly(True)
    roll_preview.setMinimumHeight(int(command_cfg.get("h", 40)))
    roll_preview.setAlignment(_field_alignment(command_cfg))
    roll_preview.setStyleSheet(_field_style(parent, command_cfg, value_color, "frames/1024x122_box.png"))
    layout.addWidget(roll_preview)
    layout.addWidget(make_action_button("Roll kopieren", lambda: QApplication.clipboard().setText(roll_preview.text()), int(buttons_cfg.get("roll_copy_w", 150))), 0, Qt.AlignHCenter)

    minus_step_button.clicked.connect(lambda: amount_input.setValue(max(0, amount_input.value() - 1)))
    plus_step_button.clicked.connect(lambda: amount_input.setValue(amount_input.value() + 1))

    refresh_info()
    return dialog.exec()


class _ResourceDialog(QDialog):
    """Paint the existing themed dialog artwork at the current window size."""

    def __init__(self, parent, cfg, load_pixmap):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._background = None
        self._fallback = QColor(str(cfg.get("fallback_background", "#140f0c")))
        if callable(load_pixmap):
            self._background = load_pixmap(str(cfg.get("background_asset", "panels/main_Frame.png")))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self._background is not None and not self._background.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap(self.rect(), self._background)
        else:
            painter.fillRect(self.rect(), self._fallback)
        painter.end()


def _field_alignment(cfg):
    return {"left": Qt.AlignLeft | Qt.AlignVCenter, "right": Qt.AlignRight | Qt.AlignVCenter}.get(
        str(cfg.get("align", "center")), Qt.AlignCenter
    )


def _field_style(window, cfg, color, default_frame):
    resolver = getattr(window, "resolve_ui_asset_path", None)
    asset = resolver(str(cfg.get("frame", default_frame))) if callable(resolver) else None
    background = (
        f'border-image: url("{asset.as_posix()}") 0 0 0 0 stretch stretch;'
        if asset is not None and asset.exists()
        else "background: rgba(0, 0, 0, 145);"
    )
    return (
        f"{background} border: none; color: {color}; font-weight: 700; "
        f"font-size: {int(cfg.get('font_size', 16))}px; padding: {int(cfg.get('padding', 0))}px;"
    )
