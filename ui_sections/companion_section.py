from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
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
    card = QFrame(parent)
    card.setObjectName("companionCard")
    card.setFixedSize(card_w, card_h)
    card.setStyleSheet("QFrame#companionCard { background: rgba(6,5,4,120); border: none; }")

    panel_path = _asset_path(window, str(card_cfg.get("asset", "panels/character_info_panel.png")))
    if panel_path is not None:
        background = QLabel(card)
        background.setObjectName("companionCardBackground")
        background.setGeometry(0, 0, card_w, card_h)
        pixmap = QPixmap(str(panel_path))
        background.setPixmap(pixmap.scaled(background.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        background.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    data = deepcopy(companion)
    field_style = "QLineEdit, QSpinBox { background: rgba(5,4,3,190); color: #ffffff; border: 1px solid rgba(242,210,139,90); padding: 3px; }"
    card.setStyleSheet(card.styleSheet() + field_style + "QLabel, QCheckBox { color: #eadfca; }")

    name = QLineEdit(str(data.get("name", "")), card)
    name.setPlaceholderText("Name")
    name.setAlignment(Qt.AlignCenter)
    name.setStyleSheet(name.styleSheet() + "font-size: 19px; font-weight: 700; color: #f2d28b;")
    name.setGeometry(*_rect(content_cfg, "name", (38, 50, 285, 38)))
    type_edit = QLineEdit(str(data.get("type", "")), card)
    type_edit.setPlaceholderText("Typ / Beschreibung")
    type_edit.setGeometry(*_rect(content_cfg, "type", (55, 94, 250, 28)))

    hp_label = QLabel("HP", card)
    hp_label.setAlignment(Qt.AlignCenter)
    hp_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #f71937;")
    hp_label.setGeometry(*_rect(content_cfg, "hp_label", (145, 130, 45, 30)))
    hp_current = _spin(data.get("hp", {}).get("current", 0), card)
    hp_max = _spin(data.get("hp", {}).get("max", 0), card)
    hp_current.setGeometry(*_rect(content_cfg, "hp_current", (195, 130, 58, 30)))
    hp_max.setGeometry(*_rect(content_cfg, "hp_max", (267, 130, 58, 30)))
    hp_separator = QLabel("/", card)
    hp_separator.setAlignment(Qt.AlignCenter)
    hp_separator.setGeometry(*_rect(content_cfg, "hp_separator", (253, 130, 14, 30)))

    mp_label = QLabel("MP", card)
    mp_label.setAlignment(Qt.AlignCenter)
    mp_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #0f95f5;")
    mp_label.setGeometry(*_rect(content_cfg, "mp_label", (145, 180, 45, 30)))
    mp_current = _spin(data.get("mp", {}).get("current", 0), card)
    mp_max = _spin(data.get("mp", {}).get("max", 0), card)
    mp_current.setGeometry(*_rect(content_cfg, "mp_current", (195, 180, 58, 30)))
    mp_max.setGeometry(*_rect(content_cfg, "mp_max", (267, 180, 58, 30)))
    mp_separator = QLabel("/", card)
    mp_separator.setAlignment(Qt.AlignCenter)
    mp_separator.setGeometry(*_rect(content_cfg, "mp_separator", (253, 180, 14, 30)))

    custom_edits = []
    custom_rows = content_cfg.get("custom_rows", []) if isinstance(content_cfg.get("custom_rows"), list) else []
    default_y_values = (315, 370, 425)
    for index, custom in enumerate(data.get("custom_fields", [])[:3]):
        row_cfg = custom_rows[index] if index < len(custom_rows) and isinstance(custom_rows[index], dict) else {}
        row_y = _safe_int(row_cfg.get("y", default_y_values[index]), default_y_values[index])
        label_edit = QLineEdit(str(custom.get("label", "")), card)
        value_edit = QLineEdit(str(custom.get("value", "")), card)
        label_edit.setPlaceholderText("Feldname")
        value_edit.setPlaceholderText("Wert")
        label_edit.setGeometry(
            _safe_int(row_cfg.get("label_x", 35), 35), row_y,
            _safe_int(row_cfg.get("label_w", 125), 125), _safe_int(row_cfg.get("h", 30), 30),
        )
        value_edit.setGeometry(
            _safe_int(row_cfg.get("value_x", 170), 170), row_y,
            _safe_int(row_cfg.get("value_w", 155), 155), _safe_int(row_cfg.get("h", 30), 30),
        )
        custom_edits.append((label_edit, value_edit))

    can_roll = QCheckBox("Kann würfeln", card)
    can_roll.setChecked(bool(data.get("can_roll", False)))
    can_roll.setGeometry(*_rect(content_cfg, "can_roll", (35, 475, 180, 30)))
    button_path = _asset_path(window, str(card_cfg.get("button_asset", "buttons/menu_button_small.png")))
    asset_url = button_path.as_posix() if button_path else ""
    rolls_button = _button("Würfe", card, asset_url)
    duplicate_button = _button("Duplizieren", card, asset_url)
    delete_button = _button("Löschen", card, asset_url)
    rolls_button.setGeometry(*_rect(content_cfg, "rolls_button", (30, 525, 92, 34)))
    duplicate_button.setGeometry(*_rect(content_cfg, "duplicate_button", (134, 525, 96, 34)))
    delete_button.setGeometry(*_rect(content_cfg, "delete_button", (242, 525, 88, 34)))

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
    return card


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
