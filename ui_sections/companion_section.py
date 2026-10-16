from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from ui_dialogs.companion_roll_dialog import CompanionRollDialog
from ui_sections.pixmap_shadow import alpha_shadow_padding, create_alpha_pixmap_shadow


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _asset_path(window, relative_path):
    rel = str(relative_path or "").replace("\\", "/").lstrip("/")
    for candidate in (
        window.theme_asset_base_path / rel,
        window.theme_asset_base_path / "ui" / rel,
        window.assets_dir / "themes" / "diablo" / rel,
        window.assets_dir / "themes" / "diablo" / "ui" / rel,
    ):
        if candidate.exists():
            return candidate
    return None


def _button(text, parent, asset_url=""):
    button = QPushButton(text, parent)
    background = f"border-image: url({asset_url}) 8 20 8 20 stretch stretch;" if asset_url else "background: rgba(35,24,12,210); border: 1px solid #8a6a32;"
    button.setStyleSheet(
        "QPushButton {"
        f"{background} color: #f2d28b; font-weight: 700; padding: 5px 10px;"
        "} QPushButton:hover { color: #ffffff; }"
    )
    button.setCursor(Qt.PointingHandCursor)
    return button


def _character_panel_size(window):
    try:
        panel_cfg = window.main_ui_layout_config["character_screen"]["panels"]["character_info_panel"]
    except (AttributeError, KeyError, TypeError):
        panel_cfg = {}
    width = _safe_int(panel_cfg.get("w", 360), 360) if isinstance(panel_cfg, dict) else 360
    height = _safe_int(panel_cfg.get("h", 600), 600) if isinstance(panel_cfg, dict) else 600
    return (width if width > 0 else 360, height if height > 0 else 600)


def _rect(cfg, key, fallback):
    value = cfg.get(key, {}) if isinstance(cfg, dict) else {}
    if not isinstance(value, dict):
        value = {}
    x, y, width, height = fallback
    return (
        _safe_int(value.get("x", x), x),
        _safe_int(value.get("y", y), y),
        _safe_int(value.get("w", width), width),
        _safe_int(value.get("h", height), height),
    )


def _control_cfg(content_cfg, key, fallback):
    cfg = content_cfg.get(key, {}) if isinstance(content_cfg, dict) else {}
    return cfg if isinstance(cfg, dict) else {"x": fallback[0], "y": fallback[1], "w": fallback[2], "h": fallback[3]}


def _apply_control(widget, cfg, fallback, *, bold=False):
    widget.setGeometry(*_rect({"control": cfg}, "control", fallback))
    color = str(cfg.get("color", "#ffffff"))
    size = _safe_int(cfg.get("font_size", 14), 14)
    declarations = f"font-size: {size}px; color: {color};" + ("font-weight: 700;" if bold else "")
    current_style = widget.styleSheet()
    if "{" in current_style:
        declarations = f"{widget.metaObject().className()} {{ {declarations} }}"
    widget.setStyleSheet(current_style + declarations)
    align = str(cfg.get("align", "")).lower()
    if align and hasattr(widget, "setAlignment"):
        widget.setAlignment(Qt.AlignCenter if align == "center" else Qt.AlignRight if align == "right" else Qt.AlignLeft)


class CompanionPortraitLabel(QLabel):
    def __init__(self, parent, choose_callback, paste_callback):
        super().__init__(parent)
        self._choose_callback = choose_callback
        self._paste_callback = paste_callback
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setFocus()
            self._choose_callback()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            self._paste_callback()
            event.accept()
            return
        super().keyPressEvent(event)


def _set_portrait_pixmap(label, path):
    pixmap = QPixmap(str(path)) if path else QPixmap()
    if pixmap.isNull():
        label.setText("Bild")
        return
    scaled = pixmap.scaled(label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - label.width()) // 2)
    y = max(0, (scaled.height() - label.height()) // 2)
    label.setPixmap(scaled.copy(x, y, label.width(), label.height()))


def _portrait_cfg(window, content_cfg):
    cfg = content_cfg.get("portrait", {}) if isinstance(content_cfg.get("portrait"), dict) else {}
    if cfg:
        return cfg
    try:
        return window.main_ui_layout_config["character_screen"]["text_layout"]["character_info_panel"]["portrait"]
    except (AttributeError, KeyError, TypeError):
        return {"x": 34, "y": 94, "w": 92, "h": 135}


def render_companion_screen(window, parent, layout_config):
    cfg = layout_config.get("companion_screen", {}) if isinstance(layout_config, dict) else {}
    title_cfg = cfg.get("title", {}) if isinstance(cfg.get("title"), dict) else {}
    window.create_panel_text(
        parent,
        title_cfg,
        str(title_cfg.get("text", "Companions")),
        _safe_int(title_cfg.get("font_size", 24), 24),
        str(title_cfg.get("color", "#f2d28b")),
        bold=True,
        align=str(title_cfg.get("align", "center")),
    )

    add_cfg = cfg.get("add_button", {}) if isinstance(cfg.get("add_button"), dict) else {}
    button_asset = _asset_path(window, str(add_cfg.get("asset", "buttons/menu_button_medium.png")))
    add_button = _button(str(add_cfg.get("text", "Companion hinzufügen")), parent, button_asset.as_posix() if button_asset else "")
    add_button.setGeometry(
        _safe_int(add_cfg.get("x", 20), 20),
        _safe_int(add_cfg.get("y", 54), 54),
        _safe_int(add_cfg.get("w", 220), 220),
        _safe_int(add_cfg.get("h", 38), 38),
    )
    add_button.clicked.connect(lambda: _add_companion(window))
    add_button.show()

    area_cfg = cfg.get("cards_area", {}) if isinstance(cfg.get("cards_area"), dict) else {}
    area = QScrollArea(parent)
    area.setGeometry(
        _safe_int(area_cfg.get("x", 18), 18),
        _safe_int(area_cfg.get("y", 102), 102),
        _safe_int(area_cfg.get("w", 1380), 1380),
        _safe_int(area_cfg.get("h", 690), 690),
    )
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setStyleSheet("QScrollArea { background: transparent; border: none; } QWidget { background: transparent; }")
    content = QWidget(area)
    grid = QGridLayout(content)
    grid.setContentsMargins(4, 4, 12, 12)
    grid.setHorizontalSpacing(_safe_int(area_cfg.get("column_gap", 18), 18))
    grid.setVerticalSpacing(_safe_int(area_cfg.get("row_gap", 18), 18))
    columns = max(1, _safe_int(area_cfg.get("columns", 3), 3))
    companions = window.loader.get_companions()
    if not companions:
        empty = QLabel(str(cfg.get("empty_text", "Noch keine Companions vorhanden.")), content)
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet("color: #c8c0aa; font-size: 18px; padding: 60px;")
        grid.addWidget(empty, 0, 0, 1, columns)
    for index, companion in enumerate(companions):
        card = _create_companion_card(window, content, companion, cfg)
        grid.addWidget(card, index // columns, index % columns)
    for column in range(columns):
        grid.setColumnStretch(column, 1)
    grid.setRowStretch(max(1, (len(companions) + columns - 1) // columns), 1)
    area.setWidget(content)
    area.show()


def _create_companion_card(window, parent, companion, cfg):
    card_cfg = cfg.get("card", {}) if isinstance(cfg.get("card"), dict) else {}
    content_cfg = card_cfg.get("content", {}) if isinstance(card_cfg.get("content"), dict) else {}
    card_w, card_h = _character_panel_size(window)
    panel_path = _asset_path(window, str(card_cfg.get("asset", "panels/character_info_panel.png")))
    panel_pixmap = QPixmap(str(panel_path)) if panel_path is not None else QPixmap()
    try:
        shadow_cfg = dict(window.main_ui_layout_config["character_screen"]["panel_shadow"])
    except (AttributeError, KeyError, TypeError):
        shadow_cfg = {"enabled": True, "offset_x": 3, "offset_y": 4, "blur_radius": 18, "color": "rgba(0, 0, 0, 160)"}
    if isinstance(card_cfg.get("shadow"), dict):
        shadow_cfg.update(card_cfg["shadow"])
    safe_int = getattr(window, "_safe_int", _safe_int)
    left, top, right, bottom = alpha_shadow_padding(safe_int, shadow_cfg)
    wrapper = QWidget(parent)
    wrapper.setObjectName("companionCardContainer")
    wrapper.setFixedSize(card_w + left + right, card_h + top + bottom)
    wrapper.setAttribute(Qt.WA_TranslucentBackground, True)
    wrapper.setStyleSheet("background: transparent; border: none;")
    create_alpha_pixmap_shadow(window, wrapper, panel_pixmap, {"x": left, "y": top, "w": card_w, "h": card_h}, shadow_cfg)
    card = QFrame(wrapper)
    card.setObjectName("companionCard")
    card.move(left, top)
    card.setFixedSize(card_w, card_h)
    card.setAttribute(Qt.WA_TranslucentBackground, True)
    card.setAutoFillBackground(False)
    card.setStyleSheet("QFrame#companionCard { background: transparent; border: none; }")

    if not panel_pixmap.isNull():
        background = QLabel(card)
        background.setObjectName("companionCardBackground")
        background.setGeometry(0, 0, card_w, card_h)
        background.setPixmap(panel_pixmap.scaled(background.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        background.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    data = deepcopy(companion)
    field_style = "QLineEdit, QSpinBox { background: rgba(5,4,3,190); color: #ffffff; border: 1px solid rgba(242,210,139,90); padding: 3px; }"
    card.setStyleSheet(card.styleSheet() + field_style + "QLabel, QCheckBox { color: #eadfca; }")

    name = QLineEdit(str(data.get("name", "")), card)
    name.setPlaceholderText("Name")
    _apply_control(name, _control_cfg(content_cfg, "name", (38, 50, 285, 38)), (38, 50, 285, 38), bold=True)
    type_edit = QLineEdit(str(data.get("type", "")), card)
    type_edit.setPlaceholderText("Typ / Beschreibung")
    _apply_control(type_edit, _control_cfg(content_cfg, "type", (35, 440, 290, 30)), (35, 440, 290, 30))

    def refresh_after_portrait():
        window.loader.save_active_character_json()
        window.show_main_section("inventory")

    def choose_portrait():
        path, _ = QFileDialog.getOpenFileName(window, "Companion-Bild auswählen", "", "Bilder (*.png *.jpg *.jpeg *.webp)")
        if path and window.loader.set_companion_portrait_file(data["id"], path):
            refresh_after_portrait()

    def paste_portrait():
        image = QApplication.clipboard().image()
        target = window.loader.get_companion_portrait_target_path(data["id"], ".png")
        if not image.isNull() and target and image.save(target, "PNG") and window.loader.set_companion_portrait_reference(data["id"], target):
            refresh_after_portrait()

    portrait = CompanionPortraitLabel(card, choose_portrait, paste_portrait)
    portrait.setObjectName("companionPortrait")
    portrait.setAlignment(Qt.AlignCenter)
    portrait.setStyleSheet("background: transparent; border: none;")
    _apply_control(portrait, _portrait_cfg(window, content_cfg), (34, 94, 92, 135))
    _set_portrait_pixmap(portrait, window.loader.get_companion_portrait_path(data))

    hp_label = QLabel("HP", card)
    _apply_control(hp_label, _control_cfg(content_cfg, "hp_label", (136, 130, 38, 30)), (136, 130, 38, 30), bold=True)
    hp_current = _spin(data.get("hp", {}).get("current", 0), card)
    hp_max = _spin(data.get("hp", {}).get("max", 0), card)
    _apply_control(hp_current, _control_cfg(content_cfg, "hp_current", (174, 130, 72, 30)), (174, 130, 72, 30))
    _apply_control(hp_max, _control_cfg(content_cfg, "hp_max", (260, 130, 72, 30)), (260, 130, 72, 30))
    hp_separator = QLabel("/", card)
    _apply_control(hp_separator, _control_cfg(content_cfg, "hp_separator", (246, 130, 14, 30)), (246, 130, 14, 30))

    mp_label = QLabel("MP", card)
    _apply_control(mp_label, _control_cfg(content_cfg, "mp_label", (136, 180, 38, 30)), (136, 180, 38, 30), bold=True)
    mp_current = _spin(data.get("mp", {}).get("current", 0), card)
    mp_max = _spin(data.get("mp", {}).get("max", 0), card)
    _apply_control(mp_current, _control_cfg(content_cfg, "mp_current", (174, 180, 72, 30)), (174, 180, 72, 30))
    _apply_control(mp_max, _control_cfg(content_cfg, "mp_max", (260, 180, 72, 30)), (260, 180, 72, 30))
    mp_separator = QLabel("/", card)
    _apply_control(mp_separator, _control_cfg(content_cfg, "mp_separator", (246, 180, 14, 30)), (246, 180, 14, 30))

    custom_edits = []
    custom_rows = content_cfg.get("custom_rows", []) if isinstance(content_cfg.get("custom_rows"), list) else []
    default_y_values = (315, 370, 425)
    for index, custom in enumerate(data.get("custom_fields", [])[:3]):
        row_cfg = custom_rows[index] if index < len(custom_rows) and isinstance(custom_rows[index], dict) else {}
        label_edit = QLineEdit(str(custom.get("label", "")), card)
        value_edit = QLineEdit(str(custom.get("value", "")), card)
        label_edit.setPlaceholderText("Feldname")
        value_edit.setPlaceholderText("Wert")
        label_cfg = row_cfg.get("label", {}) if isinstance(row_cfg.get("label"), dict) else {"x": 35, "y": default_y_values[index], "w": 125, "h": 30}
        value_cfg = row_cfg.get("value", {}) if isinstance(row_cfg.get("value"), dict) else {"x": 170, "y": default_y_values[index], "w": 155, "h": 30}
        _apply_control(label_edit, label_cfg, (35, default_y_values[index], 125, 30))
        _apply_control(value_edit, value_cfg, (170, default_y_values[index], 155, 30))
        custom_edits.append((label_edit, value_edit))

    can_roll = QCheckBox("Kann würfeln", card)
    can_roll.setChecked(bool(data.get("can_roll", False)))
    _apply_control(can_roll, _control_cfg(content_cfg, "can_roll", (35, 480, 180, 30)), (35, 480, 180, 30))
    button_path = _asset_path(window, str(card_cfg.get("button_asset", "buttons/menu_button_small.png")))
    asset_url = button_path.as_posix() if button_path else ""
    rolls_button = _button("Würfe", card, asset_url)
    duplicate_button = _button("Duplizieren", card, asset_url)
    delete_button = _button("Löschen", card, asset_url)
    for button, key, fallback in (
        (rolls_button, "rolls_button", (30, 530, 92, 34)),
        (duplicate_button, "duplicate_button", (134, 530, 96, 34)),
        (delete_button, "delete_button", (242, 530, 88, 34)),
    ):
        button_cfg = _control_cfg(content_cfg, key, fallback)
        button.setText(str(button_cfg.get("text", button.text())))
        _apply_control(button, button_cfg, fallback, bold=True)

    def collect_and_save():
        data["name"] = name.text()
        data["type"] = type_edit.text()
        data["hp"] = {"current": hp_current.value(), "max": hp_max.value()}
        data["mp"] = {"current": mp_current.value(), "max": mp_max.value()}
        data["custom_fields"] = [
            {"label": label_edit.text(), "value": value_edit.text()}
            for label_edit, value_edit in custom_edits
        ]
        data["can_roll"] = can_roll.isChecked()
        window.loader.update_companion(data["id"], data)
        window.loader.save_active_character_json()

    for editor in (name, type_edit, hp_current, hp_max, mp_current, mp_max):
        editor.editingFinished.connect(collect_and_save)
    for label_edit, value_edit in custom_edits:
        label_edit.editingFinished.connect(collect_and_save)
        value_edit.editingFinished.connect(collect_and_save)
    can_roll.toggled.connect(lambda _checked: collect_and_save())
    rolls_button.clicked.connect(lambda: _edit_rolls(window, data, collect_and_save))
    duplicate_button.clicked.connect(lambda: _duplicate_companion(window, data["id"]))
    delete_button.clicked.connect(lambda: _delete_companion(window, data["id"], name.text()))
    card.show()
    return wrapper


def _spin(value, parent):
    spin = QSpinBox(parent)
    spin.setRange(-99999, 99999)
    spin.setValue(_safe_int(value, 0))
    return spin


def _add_companion(window):
    window.loader.add_companion()
    window.loader.save_active_character_json()
    window.show_main_section("inventory")


def _duplicate_companion(window, companion_id):
    window.loader.duplicate_companion(companion_id)
    window.loader.save_active_character_json()
    window.show_main_section("inventory")


def _delete_companion(window, companion_id, name):
    answer = QMessageBox.question(
        window,
        "Companion löschen",
        f'Companion "{name or "Ohne Name"}" wirklich löschen?',
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if answer != QMessageBox.Yes:
        return
    window.loader.delete_companion(companion_id)
    window.loader.save_active_character_json()
    window.show_main_section("inventory")


def _edit_rolls(window, data, save_callback):
    dialog = CompanionRollDialog(window, data.get("name", "Companion"), window.get_inventory_roll_options(), data.get("rolls", []))
    if dialog.exec() != QDialog.Accepted:
        return
    data["rolls"] = dialog.rolls()
    save_callback()
