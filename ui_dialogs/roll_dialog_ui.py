from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox

from ui_controls import create_step_button


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def asset_pixmap(relative_path, resolve_asset_path):
    path = resolve_asset_path(str(relative_path or "")) if callable(resolve_asset_path) else None
    pixmap = QPixmap(str(path)) if path else QPixmap()
    return pixmap if not pixmap.isNull() else None


def add_roll_main_frame(dialog, dialog_cfg, resolve_asset_path):
    frame_cfg = dict(dialog_cfg.get("main_frame", {}) or {})
    if not frame_cfg.get("enabled", False):
        return None
    frame = QLabel(dialog)
    frame.setGeometry(0, 0, dialog.width(), dialog.height())
    frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    pixmap = asset_pixmap(frame_cfg.get("asset"), resolve_asset_path)
    if pixmap is not None:
        frame.setPixmap(pixmap.scaled(frame.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    frame.lower()
    return frame


def create_roll_close_button(parent, cfg, resolve_asset_path):
    if not cfg.get("enabled", False):
        return None
    width = safe_int(cfg.get("w", 22), 22)
    height = safe_int(cfg.get("h", 22), 22)
    x = parent.width() - safe_int(cfg.get("right", 8), 8) - width
    y = safe_int(cfg.get("top", 12), 12)
    button = QPushButton(parent)
    button.setGeometry(x, y, width, height)
    path = resolve_asset_path(str(cfg.get("asset", "") or "")) if callable(resolve_asset_path) else None
    if path:
        button.setIcon(QIcon(str(path)))
        button.setIconSize(button.size())
    button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
    button.setCursor(Qt.PointingHandCursor)
    return button


def border_image_style(frame_cfg, resolve_asset_path):
    path = resolve_asset_path(str(frame_cfg.get("asset", "") or "")) if callable(resolve_asset_path) else None
    if not path:
        return ""
    slices = dict(frame_cfg.get("slice", {}) or {})
    values = [safe_int(slices.get(key, 10), 10) for key in ("top", "right", "bottom", "left")]
    return f"border-image: url({str(path).replace(chr(92), '/')}) {' '.join(map(str, values))} stretch stretch;"


def framed_box_style(background, border_color, text_color, font_size, frame_cfg, resolve_asset_path, padding=8, bold=False):
    image_style = border_image_style(frame_cfg, resolve_asset_path) if frame_cfg.get("enabled", False) else ""
    border = f"{safe_int(frame_cfg.get('border_width', 6), 6)}px solid transparent" if image_style else f"1px solid {border_color}"
    return f"font-size: {font_size}px; font-weight: {700 if bold else 500}; color: {text_color}; background: {background}; border: {border}; padding: {max(0, int(padding))}px; {image_style}"


def spinbox_style(preview_cfg, counter_cfg, font_size, resolve_asset_path):
    frame_cfg = dict(counter_cfg.get("value_frame", {}) or {})
    if str(frame_cfg.get("render_mode", "image")).strip().lower() == "css":
        return (
            "QSpinBox {"
            f"background: {counter_cfg.get('value_background', preview_cfg.get('background', '#101214'))}; "
            f"color: {counter_cfg.get('value_text_color', preview_cfg.get('text_color', '#f2d28b'))}; "
            f"border: 1px solid {counter_cfg.get('value_border_color', '#8a6a32')}; border-radius: 3px; "
            f"font-size: {font_size}px; font-weight: 700; padding: 2px 6px;"
            "} QSpinBox::up-button, QSpinBox::down-button { width: 0px; height: 0px; border: none; }"
        )
    box = framed_box_style(counter_cfg.get("value_background", preview_cfg.get("background", "#101214")), counter_cfg.get("value_border_color", "#8a6a32"), counter_cfg.get("value_text_color", preview_cfg.get("text_color", "#f2d28b")), font_size, frame_cfg, resolve_asset_path, frame_cfg.get("padding", 0), True)
    return f"QSpinBox {{{box}}} QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; height: 0px; border: none; }}"


def create_roll_counter(parent, label_text, minimum, maximum, counter_cfg, preview_cfg, labels_cfg, resolve_asset_path, object_name="", value_width=None, connect_steps=True):
    font_size = safe_int(labels_cfg.get("normal_text_font_size", 13), 13)
    label = QLabel(label_text, parent)
    label.setFixedWidth(safe_int(counter_cfg.get("label_w", 150), 150))
    label.setStyleSheet(f"color: {labels_cfg.get('normal_text_color', '#f2f2f2')}; font-size: {font_size}px;")
    minus = create_step_button(parent, "-", f"{label_text} verringern")
    plus = create_step_button(parent, "+", f"{label_text} erhöhen")
    spin = QSpinBox(parent)
    spin.setObjectName(object_name)
    spin.setRange(minimum, maximum)
    spin.setButtonSymbols(QSpinBox.NoButtons)
    spin.setFixedSize(value_width or safe_int(counter_cfg.get("value_w", 48), 48), safe_int(counter_cfg.get("value_h", 36), 36))
    spin.setAlignment(Qt.AlignCenter)
    spin.setStyleSheet(spinbox_style(preview_cfg, counter_cfg, font_size, resolve_asset_path))
    spin.lineEdit().setFrame(False)
    spin.lineEdit().setContentsMargins(0, 0, 0, 0)
    spin.lineEdit().setTextMargins(0, 0, 0, 0)
    spin.lineEdit().setStyleSheet(
        "QLineEdit { background: transparent; border: none; margin: 0px; padding: 0px; font-weight: 700; "
        f"color: {counter_cfg.get('value_text_color', preview_cfg.get('text_color', '#f2d28b'))}; font-size: {font_size}px; "
        f"selection-background-color: {counter_cfg.get('selection_background', '#5f451e')}; "
        f"selection-color: {counter_cfg.get('selection_text_color', '#ffffff')}; }}"
    )
    if connect_steps:
        minus.clicked.connect(lambda: spin.setValue(spin.value() - 1))
        plus.clicked.connect(lambda: spin.setValue(spin.value() + 1))
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    for widget in (label, minus, spin, plus):
        row.addWidget(widget)
    row.addStretch()
    return row, spin, minus, plus


class RollAssetButton(QPushButton):
    def __init__(self, text, pixmap, cfg, parent=None):
        super().__init__(text, parent)
        self._pixmap = pixmap
        self._cfg = cfg
        self._hovered = self._pressed = False
        self.setStyleSheet(f"QPushButton {{ background: transparent; border: none; padding: 0px; font-size: {safe_int(cfg.get('font_size', 13), 13)}px; font-weight: 700; color: {cfg.get('text_color', '#f2d28b')}; }}")
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event): self._hovered = True; self.update(); super().enterEvent(event)
    def leaveEvent(self, event): self._hovered = self._pressed = False; self.update(); super().leaveEvent(event)
    def mousePressEvent(self, event): self._pressed = True; self.update(); super().mousePressEvent(event)
    def mouseReleaseEvent(self, event): self._pressed = False; self.update(); super().mouseReleaseEvent(event)
    def paintEvent(self, event):
        painter = QPainter(self)
        pixmap = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap((self.width() - pixmap.width()) // 2, (self.height() - pixmap.height()) // 2, pixmap)
        color = self._cfg.get("pressed_text_color", "#fff") if self._pressed else self._cfg.get("hover_text_color", "#fff") if self._hovered else self._cfg.get("text_color", "#f2d28b")
        painter.setPen(QColor(color)); painter.setFont(self.font()); painter.drawText(self.rect(), Qt.AlignCenter, self.text())


def create_roll_menu_button(text, parent, buttons_cfg, resolve_asset_path, button_key="copy"):
    pixmap = asset_pixmap(buttons_cfg.get("asset"), resolve_asset_path)
    button = RollAssetButton(text, pixmap, buttons_cfg, parent) if pixmap is not None else QPushButton(text, parent)
    button.setFixedSize(safe_int(buttons_cfg.get(f"{button_key}_w", buttons_cfg.get("w", 190)), 190), safe_int(buttons_cfg.get("h", 42), 42))
    return button
