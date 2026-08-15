import json
import re

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_dialogs.attack_roll_logic import build_attack_roll_command, parse_weapon_row, safe_int, weapon_roll_components
from ui_dialogs.window_chrome import install_frameless_dialog_chrome
from app_paths import ui_icon_path


def open_attack_roll_dialog(window, weapon_data: dict):
    config = _load_attack_roll_config(window)
    weapon = parse_weapon_row(weapon_data)
    dialog = QDialog(window)
    dialog.setWindowTitle("Attacke")
    install_frameless_dialog_chrome(dialog)
    dialog.setAttribute(Qt.WA_TranslucentBackground, True)
    dialog.setAutoFillBackground(False)
    dialog.resize(760, 620)
    dialog.setModal(False)
    dialog.setStyleSheet(_dialog_stylesheet(window))
    _add_dialog_background(dialog, window, 760, 620)

    state = {
        "components": weapon_roll_components(weapon),
        "active_component": "physical",
        "component_widgets": {},
        "dice_buttons": {},
    }

    title = QLabel(weapon.get("name") or "Unbenannte Waffe", dialog)
    title.setObjectName("Title")
    title.setAlignment(Qt.AlignCenter)
    title.setGeometry(64, 10, 632, 34)
    title.installEventFilter(dialog._frameless_drag_filter)
    title.raise_()

    root = QHBoxLayout(dialog)
    root.setContentsMargins(16, 52, 16, 16)
    root.setSpacing(14)

    dice_panel = QWidget(dialog)
    dice_panel.setObjectName("Panel")
    dice_layout = QVBoxLayout(dice_panel)
    dice_layout.setContentsMargins(10, 10, 10, 10)
    dice_layout.setSpacing(8)
    dice_title = QLabel("Würfel", dice_panel)
    dice_title.setObjectName("SectionTitle")
    dice_layout.addWidget(dice_title)
    dice_buttons = QVBoxLayout()
    dice_buttons.setSpacing(7)
    dice_layout.addLayout(dice_buttons)
    dice_layout.addStretch(1)
    root.addWidget(dice_panel, 0)

    main_panel = QWidget(dialog)
    main_panel.setObjectName("Panel")
    main_layout = QVBoxLayout(main_panel)
    main_layout.setContentsMargins(14, 12, 14, 12)
    main_layout.setSpacing(10)
    root.addWidget(main_panel, 1)

    weapon_type = QLabel(_weapon_subtitle(weapon), main_panel)
    weapon_type.setObjectName("Muted")
    weapon_type.setAlignment(Qt.AlignCenter)
    main_layout.addWidget(weapon_type)

    info = QLabel(_detected_text(weapon), main_panel)
    info.setObjectName("InfoText")
    info.setWordWrap(True)
    main_layout.addWidget(info)

    component_area = QVBoxLayout()
    component_area.setSpacing(8)
    main_layout.addLayout(component_area)

    def set_active_component(component_key):
        state["active_component"] = component_key
        for key, widgets in state["component_widgets"].items():
            _set_component_row_active(widgets["panel"], key == component_key)
        for sides, button in state["dice_buttons"].items():
            active = sides == safe_int(state["components"].get(component_key, {}).get("sides", 0), 0)
            if hasattr(button, "set_active"):
                button.set_active(active)
            else:
                button.setIcon(QIcon(_dice_button_pixmap(f"d{sides}", 64, 64, active=active)))

    def set_count(component_key, delta):
        set_active_component(component_key)
        component = state["components"].get(component_key, {})
        component["count"] = max(0, safe_int(component.get("count", 0), 0) + delta)
        _refresh_component_widgets(component_key)
        refresh_preview()

    def set_die_type(sides):
        component_key = state["active_component"]
        component = state["components"].get(component_key, {})
        component["sides"] = sides
        if safe_int(component.get("count", 0), 0) <= 0:
            component["count"] = 1
        _refresh_component_widgets(component_key)
        set_active_component(component_key)
        refresh_preview()

    def on_bonus_changed(component_key, text):
        set_active_component(component_key)
        state["components"].get(component_key, {})["bonus"] = safe_int(text, 0)
        refresh_preview()

    def _refresh_component_widgets(component_key):
        component = state["components"].get(component_key, {})
        widgets = state["component_widgets"].get(component_key, {})
        count_label = widgets.get("count")
        die_label = widgets.get("die")
        bonus_edit = widgets.get("bonus")
        if count_label is not None:
            count_label.setText(str(max(0, safe_int(component.get("count", 0), 0))))
        if die_label is not None:
            die_label.setText(f"d{safe_int(component.get('sides', 6), 6)}")
        if bonus_edit is not None and bonus_edit.text() != str(safe_int(component.get("bonus", 0), 0)):
            bonus_edit.blockSignals(True)
            bonus_edit.setText(str(safe_int(component.get("bonus", 0), 0)))
            bonus_edit.blockSignals(False)

    component_labels = [
        ("physical", "Physisch"),
        ("elemental", "Elementar"),
        ("extra", "Zusatz"),
    ]
    for component_key, label_text in component_labels:
        widgets = _make_component_row(
            main_panel,
            label_text,
            state["components"].get(component_key, {}),
            lambda checked=False, key=component_key: set_active_component(key),
            lambda checked=False, key=component_key: set_count(key, -1),
            lambda checked=False, key=component_key: set_count(key, 1),
            lambda text, key=component_key: on_bonus_changed(key, text),
        )
        state["component_widgets"][component_key] = widgets
        component_area.addWidget(widgets["panel"])

    main_layout.addWidget(_make_element_row(main_panel, _element_display_text(weapon)))

    manual_bonus = QLineEdit(main_panel)
    manual_bonus.setPlaceholderText("Globaler Bonus/Malus")
    manual_bonus.setText("0")
    manual_bonus.setObjectName("ValueInput")
    manual_bonus.setFixedWidth(74)
    manual_bonus.textChanged.connect(lambda text: _set_manual_bonus(state, text, refresh_preview))
    main_layout.addWidget(_compact_field_with_label("Globaler Bonus/Malus", manual_bonus))

    preview_label = QLabel("Roll20-Befehl", main_panel)
    preview_label.setObjectName("SectionTitle")
    main_layout.addWidget(preview_label)

    preview = QLineEdit(main_panel)
    preview.setReadOnly(True)
    preview.setObjectName("Preview")
    main_layout.addWidget(preview)

    no_dice = QLabel("", main_panel)
    no_dice.setObjectName("Muted")
    main_layout.addWidget(no_dice)

    button_row = QHBoxLayout()
    copy_button = _make_button("Kopieren", main_panel, window)
    copy_open_button = _make_button("Kopieren & Browser öffnen", main_panel, window)
    close_button = _make_button("Schließen", main_panel, window)
    button_row.addStretch(1)
    button_row.addWidget(copy_button)
    button_row.addWidget(copy_open_button)
    button_row.addWidget(close_button)
    button_row.addStretch(1)
    main_layout.addLayout(button_row)

    def refresh_preview():
        command = build_attack_roll_command(
            weapon,
            {
                "components": state["components"],
                "roll20_prefix": config.get("roll20_prefix", "/r"),
                "fallback_dice": "1d20",
            },
        )
        preview.setText(command)
        if not any(safe_int(state["components"].get(key, {}).get("count", 0), 0) > 0 for key in ("physical", "elemental", "extra")):
            no_dice.setText("Kein Schadenswürfel erkannt. Vorschau nutzt 1d20.")
        else:
            no_dice.setText("")

    def set_manual_die(die_id):
        sides = safe_int(str(die_id).lower().replace("d", ""), 0)
        if sides > 0:
            set_die_type(sides)

    dice_entries = config.get("dice", [])
    if not isinstance(dice_entries, list):
        dice_entries = []
    for index, entry in enumerate(dice_entries):
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", entry.get("id", "")) or "")
        die_id = str(entry.get("id", label) or "")
        button = _make_dice_button(label, dice_panel)
        button.clicked.connect(lambda checked=False, did=die_id: set_manual_die(did))
        state["dice_buttons"][safe_int(die_id.lower().replace("d", ""), 0)] = button
        dice_buttons.addWidget(button)

    def copy_command():
        QApplication.clipboard().setText(preview.text())

    def copy_and_open_browser():
        copy_command()
        open_browser = getattr(window, "open_roll20_browser_section", None)
        if callable(open_browser):
            open_browser()

    copy_button.clicked.connect(copy_command)
    copy_open_button.clicked.connect(copy_and_open_browser)
    close_button.clicked.connect(dialog.close)
    close_x = _make_close_button(dialog, window)
    if close_x is not None:
        close_x.clicked.connect(dialog.close)
        close_x.raise_()
    for component_key, _ in component_labels:
        _refresh_component_widgets(component_key)
    set_active_component("physical")
    refresh_preview()
    dialog.show()
    return dialog


def _load_attack_roll_config(window):
    try:
        config_path = window.assets_dir / "config" / "attack_roll_config.json"
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"roll20_prefix": "/r", "dice": []}


def _weapon_subtitle(weapon):
    parts = []
    for key in ("weapon_type", "pl"):
        text = str(weapon.get(key, "") or "").strip()
        if text:
            parts.append(f"PL {text}" if key == "pl" else text)
    durability = str(weapon.get("durability", "") or "").strip()
    max_durability = str(weapon.get("max_durability", "") or "").strip()
    if durability or max_durability:
        parts.append(f"Haltbarkeit {durability}/{max_durability}".strip("/"))
    return "  |  ".join(parts) if parts else "Waffe"


def _detected_text(weapon):
    lines = []
    dice_1 = str(weapon.get("dice_1", "") or "").strip()
    bonus_1 = str(weapon.get("bonus_1", "") or "").strip()
    dice_2 = str(weapon.get("dice_2", "") or "").strip()
    bonus_2 = str(weapon.get("bonus_2", "") or "").strip()
    if dice_1 or bonus_1:
        lines.append(f"Physisch: {dice_1 or '-'}  Bonus: {bonus_1 or '0'}")
    if dice_2 or bonus_2:
        lines.append(f"Elementar: {dice_2 or '-'}  Bonus: {bonus_2 or '0'}")
    if weapon.get("attributes_special"):
        lines.append(f"Attribute / Sonderfertigkeiten: {weapon.get('attributes_special')}")
    return "\n".join(lines) if lines else "Kein Schadenswürfel erkannt"


def _element_display_text(weapon):
    seen = set()
    values = []
    for raw in (weapon.get("elements", ""), weapon.get("dice_2_note", "")):
        for part in re.split(r"[,;/|+]+|\s+[·•]\s+", str(raw or "")):
            text = part.strip()
            if not text:
                continue
            display = text.title() if text.isupper() else text
            key = display.casefold()
            if key in seen:
                continue
            seen.add(key)
            values.append(display)
    return ", ".join(values) if values else "-"


def _set_manual_bonus(state, text, refresh_callback):
    state["components"]["manual_bonus"] = safe_int(text, 0)
    refresh_callback()


def _make_component_row(parent, label_text, component, activate_callback, minus_callback, plus_callback, bonus_callback):
    panel = QWidget(parent)
    panel.setObjectName("ComponentRow")
    layout = QHBoxLayout(panel)
    layout.setContentsMargins(10, 7, 10, 7)
    layout.setSpacing(8)

    select_button = QPushButton(label_text, panel)
    select_button.setObjectName("ComponentSelect")
    select_button.setCursor(Qt.PointingHandCursor)
    select_button.clicked.connect(activate_callback)
    layout.addWidget(select_button, 0)

    minus_button = _make_tiny_button("-", panel)
    minus_button.clicked.connect(minus_callback)
    layout.addWidget(minus_button, 0)

    count_label = QLabel(str(max(0, safe_int(component.get("count", 0), 0))), panel)
    count_label.setObjectName("CountValue")
    count_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(count_label, 0)

    plus_button = _make_tiny_button("+", panel)
    plus_button.clicked.connect(plus_callback)
    layout.addWidget(plus_button, 0)

    die_label = QLabel(f"d{safe_int(component.get('sides', 6), 6)}", panel)
    die_label.setObjectName("DieValue")
    die_label.setAlignment(Qt.AlignCenter)
    layout.addWidget(die_label, 0)

    bonus_label = QLabel("Bonus", panel)
    bonus_label.setObjectName("Muted")
    layout.addWidget(bonus_label, 0)

    bonus_edit = QLineEdit(panel)
    bonus_edit.setObjectName("ValueInput")
    bonus_edit.setFixedWidth(54)
    bonus_edit.setText(str(safe_int(component.get("bonus", 0), 0)))
    bonus_edit.textChanged.connect(bonus_callback)
    layout.addWidget(bonus_edit, 0)

    layout.addStretch(1)

    return {
        "panel": panel,
        "select": select_button,
        "count": count_label,
        "die": die_label,
        "bonus": bonus_edit,
        "note": None,
    }


def _set_component_row_active(panel, active):
    panel.setProperty("active", bool(active))
    panel.style().unpolish(panel)
    panel.style().polish(panel)


def _make_tiny_button(text, parent):
    button = QPushButton(text, parent)
    button.setObjectName("TinyButton")
    button.setFixedSize(28, 26)
    button.setCursor(Qt.PointingHandCursor)
    return button


def _field_with_label(label_text, field):
    wrapper = QWidget(field.parent())
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    label = QLabel(label_text, wrapper)
    label.setObjectName("Muted")
    layout.addWidget(label)
    layout.addWidget(field)
    return wrapper


def _compact_field_with_label(label_text, field):
    wrapper = QWidget(field.parent())
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    label = QLabel(label_text, wrapper)
    label.setObjectName("ElementLabel")
    layout.addWidget(label, 0)
    layout.addWidget(field, 0)
    layout.addStretch(1)
    return wrapper


def _make_element_row(parent, value_text):
    row = QWidget(parent)
    row.setObjectName("ElementRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(10, 7, 10, 7)
    layout.setSpacing(10)
    label = QLabel("Elemente", row)
    label.setObjectName("ElementLabel")
    label.setMinimumWidth(86)
    layout.addWidget(label, 0)
    value = QLabel(value_text, row)
    value.setObjectName("ElementValue")
    value.setWordWrap(True)
    layout.addWidget(value, 1)
    return row


def _asset_path(window, asset_rel_path):
    asset_name = str(asset_rel_path or "").strip()
    if not asset_name:
        return None
    normalized_asset_name = asset_name.replace("\\", "/").lstrip("/")
    if normalized_asset_name.startswith("icons/") or normalized_asset_name.startswith("ui_elements/icons/"):
        path = ui_icon_path(asset_name)
        return path if path.exists() else None
    try:
        primary = window.theme_asset_base_path / asset_name
        if primary.exists():
            return primary
        fallback = window.assets_dir / "themes" / "diablo" / "ui" / asset_name
        if fallback.exists():
            return fallback
    except Exception:
        return None
    return None


def _asset_pixmap(window, asset_rel_path):
    path = _asset_path(window, asset_rel_path)
    if path is None:
        return None
    pixmap = QPixmap(str(path))
    return None if pixmap.isNull() else pixmap


def _add_dialog_background(dialog, window, w, h):
    frame = _asset_pixmap(window, "panels/main_Frame.png")
    if frame is None:
        frame = _asset_pixmap(window, "panels/character_info_panel.png")
    if frame is None:
        return
    label = QLabel(dialog)
    label.setGeometry(0, 0, w, h)
    label.setPixmap(frame.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    label.lower()


def _make_close_button(dialog, window):
    path = _asset_path(window, "ui_elements/icons/x.jpg")
    if path is None:
        return None
    button = QPushButton(dialog)
    button.setGeometry(dialog.width() - 42, 12, 26, 26)
    button.setIcon(QIcon(str(path)))
    button.setIconSize(button.size())
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
    return button


class _DiceButton(QPushButton):
    def __init__(self, text, parent):
        super().__init__(parent)
        self._text = str(text)
        self._active = False
        self._hover = False

    def set_active(self, active):
        self._active = bool(active)
        self._refresh_icon()

    def enterEvent(self, event):
        self._hover = True
        self._refresh_icon()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._refresh_icon()
        super().leaveEvent(event)

    def _refresh_icon(self):
        self.setIcon(QIcon(_dice_button_pixmap(self._text, 64, 64, active=self._active, hover=self._hover)))


def _make_dice_button(text, parent):
    button = _DiceButton(text, parent)
    button.setFixedSize(64, 64)
    button.setCursor(Qt.PointingHandCursor)
    button.set_active(False)
    button.setIconSize(button.size())
    button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
    return button


def _dice_button_pixmap(text, width, height, active=False, hover=False):
    pixmap = QPixmap(max(1, width), max(1, height))
    pixmap.fill(Qt.transparent)
    edge_color = QColor("#f2d28b" if active else "#c6a15c")
    text_color = QColor("#9fe6ff" if hover else "#8fdcff" if active else "#7fd0ff")
    shadow_color = QColor("#000000")

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pad = max(3, min(width, height) // 9)
    cx = width // 2
    top = pad
    bottom = height - pad
    left = pad
    right = width - pad
    mid_y = height // 2
    upper_y = int(height * 0.32)
    lower_y = int(height * 0.69)

    outline = QPolygon([
        QPoint(cx, top),
        QPoint(right, upper_y),
        QPoint(int(width * 0.82), lower_y),
        QPoint(cx, bottom),
        QPoint(int(width * 0.18), lower_y),
        QPoint(left, upper_y),
    ])
    gradient = QLinearGradient(0, top, 0, bottom)
    gradient.setColorAt(0.0, QColor(80, 68, 50, 235))
    gradient.setColorAt(0.45, QColor(24, 22, 21, 235))
    gradient.setColorAt(1.0, QColor(8, 7, 7, 245))

    painter.setPen(QPen(shadow_color, 3))
    painter.setBrush(gradient)
    painter.drawPolygon(outline)
    painter.setPen(QPen(edge_color, 2))
    painter.drawPolygon(outline)
    painter.setPen(QPen(QColor(edge_color.red(), edge_color.green(), edge_color.blue(), 150), 1))
    painter.drawLine(cx, top, cx, bottom)
    painter.drawLine(left, upper_y, right, upper_y)
    painter.drawLine(left, upper_y, cx, bottom)
    painter.drawLine(right, upper_y, cx, bottom)
    painter.drawLine(int(width * 0.18), lower_y, int(width * 0.82), lower_y)
    painter.drawLine(left, upper_y, cx, mid_y)
    painter.drawLine(right, upper_y, cx, mid_y)

    font = painter.font()
    font.setBold(True)
    font.setPixelSize(max(10, min(width, height) // 3))
    painter.setFont(font)
    painter.setPen(QPen(shadow_color, 2))
    painter.drawText(QRect(1, 2, width, height), Qt.AlignCenter, str(text))
    painter.setPen(text_color)
    painter.drawText(QRect(0, 0, width, height), Qt.AlignCenter, str(text))
    painter.end()
    return pixmap


def _make_button(text, parent, window, compact=False):
    button = QPushButton(text, parent)
    button.setCursor(Qt.PointingHandCursor)
    button.setMinimumHeight(35 if compact else 39)
    asset_path = _asset_path(window, "buttons/menu_button_medium.png")
    background = (
        f"border-image: url({asset_path.as_posix()}) 0 0 0 0 stretch stretch;"
        if asset_path is not None
        else "background: rgba(30, 22, 14, 230);"
    )
    button.setStyleSheet(
        "QPushButton {"
        f"{background}"
        "border: none;"
        "color: #f2d28b;"
        "font-weight: 700;"
        "padding: 5px 13px;"
        "}"
        "QPushButton:hover { color: #fff1be; }"
        "QPushButton:disabled { color: #7a6a50; }"
    )
    return button


def _dialog_stylesheet(window):
    value_frame = _asset_path(window, "frames/256x122_box.png")
    preview_frame = _asset_path(window, "frames/1024x122_box.png")
    value_background = (
        f"border-image: url({value_frame.as_posix()}) 0 0 0 0 stretch stretch;"
        if value_frame is not None
        else "background: rgba(0, 0, 0, 145);"
    )
    preview_background = (
        f"border-image: url({preview_frame.as_posix()}) 0 0 0 0 stretch stretch;"
        if preview_frame is not None
        else "background: rgba(0, 0, 0, 170);"
    )
    return """
QDialog {
    background: transparent;
    color: #eadfca;
    border: none;
    font-size: 13px;
}
QWidget#Panel {
    background: rgba(5, 4, 3, 185);
    border: none;
}
QLabel#Title {
    color: #f2d28b;
    font-size: 23px;
    font-weight: 700;
    qproperty-alignment: AlignCenter;
}
QLabel#SectionTitle {
    color: #d8aa4c;
    font-weight: 700;
}
QLabel#Muted {
    color: #c8bda5;
}
QLabel#InfoText {
    color: #eadfca;
    padding: 4px 0px;
}
QWidget#ComponentRow {
    background: rgba(0, 0, 0, 105);
    border: none;
}
QWidget#ComponentRow[active="true"] {
    background: rgba(56, 40, 18, 165);
}
QWidget#ElementRow {
    background: rgba(0, 0, 0, 105);
    border: none;
}
QLabel#ElementLabel {
    color: #f2d28b;
    font-weight: 700;
}
QLabel#ElementValue {
    color: #7fd0ff;
    font-weight: 700;
}
QPushButton#ComponentSelect {
    background: transparent;
    border: none;
    color: #f2d28b;
    font-weight: 700;
    text-align: left;
    min-width: 86px;
}
QPushButton#TinyButton {
    background: rgba(30, 22, 14, 210);
    border: 1px solid rgba(216, 170, 76, 120);
    color: #f2d28b;
    font-weight: 700;
}
QPushButton#TinyButton:hover {
    color: #fff1be;
    background: rgba(58, 40, 22, 220);
}
QLabel#CountValue, QLabel#DieValue {
    background: rgba(0, 0, 0, 145);
    color: #f7ead0;
    min-width: 42px;
    padding: 5px;
    font-weight: 700;
}
QLineEdit {
    __VALUE_BACKGROUND__
    border: none;
    color: #f7ead0;
    padding: 6px;
}
QLineEdit#ValueInput {
    __VALUE_BACKGROUND__
    border: none;
    color: #f7ead0;
}
QLineEdit#Preview {
    __PREVIEW_BACKGROUND__
    color: #7fd0ff;
    font-size: 20px;
    font-weight: 700;
}
""".replace("__VALUE_BACKGROUND__", value_background).replace("__PREVIEW_BACKGROUND__", preview_background)
