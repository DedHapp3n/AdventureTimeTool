from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QFrame, QGridLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QWidget

from ui_dialogs.companion_roll_dialog import CompanionRollDialog
from ui_sections.editable_panel_text import create_editable_panel_text
from ui_sections.pixmap_shadow import alpha_shadow_padding, create_alpha_pixmap_shadow


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _asset_path(window, relative_path):
    rel = str(relative_path or "").replace("\\", "/").lstrip("/")
    for candidate in (window.theme_asset_base_path / rel, window.theme_asset_base_path / "ui" / rel, window.assets_dir / rel, window.assets_dir / "themes" / "diablo" / rel, window.assets_dir / "themes" / "diablo" / "ui" / rel):
        if candidate.exists():
            return candidate
    return None


def _rect(cfg, fallback):
    return tuple(_safe_int(cfg.get(key, value), value) for key, value in zip(("x", "y", "w", "h"), fallback))


def _button(text, parent, asset_url=""):
    button = QPushButton(text, parent)
    background = f"border-image: url({asset_url}) 8 20 8 20 stretch stretch;" if asset_url else "background: rgba(35,24,12,210); border: 1px solid #8a6a32;"
    button.setStyleSheet(f"QPushButton {{{background} color: #f2d28b; font-weight: 700; padding: 5px 10px;}} QPushButton:hover {{ color: #ffffff; }}")
    button.setCursor(Qt.PointingHandCursor)
    return button


def _character_layout(window):
    try:
        return window.main_ui_layout_config["character_screen"]["text_layout"]["character_info_panel"]
    except (AttributeError, KeyError, TypeError):
        return {}


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


def _set_portrait_pixmap(label, path, fit_mode="contain"):
    pixmap = QPixmap(str(path)) if path else QPixmap()
    if pixmap.isNull():
        label.setText("Bild")
        return
    aspect_mode = Qt.KeepAspectRatioByExpanding if str(fit_mode).lower() == "cover" else Qt.KeepAspectRatio
    scaled = pixmap.scaled(label.size(), aspect_mode, Qt.SmoothTransformation)
    if aspect_mode == Qt.KeepAspectRatioByExpanding:
        scaled = scaled.copy(max(0, (scaled.width() - label.width()) // 2), max(0, (scaled.height() - label.height()) // 2), label.width(), label.height())
    label.setPixmap(scaled)


def render_companion_screen(window, parent, layout_config):
    cfg = layout_config.get("companion_screen", {}) if isinstance(layout_config, dict) else {}
    title_cfg = cfg.get("title", {})
    window.create_panel_text(parent, title_cfg, str(title_cfg.get("text", "Companions")), _safe_int(title_cfg.get("font_size", 24), 24), str(title_cfg.get("color", "#f2d28b")), bold=True, align=str(title_cfg.get("align", "center")))
    add_cfg = cfg.get("add_button", {})
    asset = _asset_path(window, add_cfg.get("asset", "buttons/menu_button_medium.png"))
    add_button = _button(str(add_cfg.get("text", "Companion hinzufügen")), parent, asset.as_posix() if asset else "")
    add_button.setGeometry(*_rect(add_cfg, (20, 54, 230, 38)))
    add_button.clicked.connect(lambda: _add_companion(window))
    add_button.show()

    area_cfg = cfg.get("cards_area", {})
    area = QScrollArea(parent)
    area.setGeometry(*_rect(area_cfg, (18, 102, 1380, 690)))
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setStyleSheet("QScrollArea { background: transparent; border: none; } QWidget { background: transparent; }")
    content = QWidget(area)
    grid = QGridLayout(content)
    grid.setContentsMargins(4, 4, 12, 12)
    grid.setHorizontalSpacing(_safe_int(area_cfg.get("column_gap", 8), 8))
    grid.setVerticalSpacing(_safe_int(area_cfg.get("row_gap", 8), 8))
    columns = max(1, _safe_int(area_cfg.get("columns", 3), 3))
    companions = window.loader.get_companions()
    if not companions:
        empty = QLabel(str(cfg.get("empty_text", "Noch keine Companions vorhanden.")), content)
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet("color: #c8c0aa; font-size: 18px; padding: 60px;")
        grid.addWidget(empty, 0, 0, 1, columns)
    for index, companion in enumerate(companions):
        grid.addWidget(_create_companion_card(window, content, companion, cfg), index // columns, index % columns)
    for column in range(columns):
        grid.setColumnStretch(column, 1)
    grid.setRowStretch(max(1, (len(companions) + columns - 1) // columns), 1)
    area.setWidget(content)
    area.show()


def _create_companion_card(window, parent, companion, cfg):
    card_cfg = cfg.get("card", {})
    content_cfg = card_cfg.get("content", {})
    try:
        panel_cfg = window.main_ui_layout_config["character_screen"]["panels"]["character_info_panel"]
    except (AttributeError, KeyError, TypeError):
        panel_cfg = {}
    card_w, card_h = _safe_int(panel_cfg.get("w", 360), 360), _safe_int(panel_cfg.get("h", 600), 600)
    panel_path = _asset_path(window, str(panel_cfg.get("asset", card_cfg.get("asset", "panels/character_info_panel.png"))))
    panel_pixmap = QPixmap(str(panel_path)) if panel_path else QPixmap()
    try:
        shadow_cfg = dict(window.main_ui_layout_config["character_screen"]["panel_shadow"])
    except (AttributeError, KeyError, TypeError):
        shadow_cfg = {"enabled": True, "offset_x": 3, "offset_y": 4, "blur_radius": 18, "color": "rgba(0, 0, 0, 160)"}
    left, top, right, bottom = alpha_shadow_padding(getattr(window, "_safe_int", _safe_int), shadow_cfg)
    wrapper = QWidget(parent)
    wrapper.setObjectName("companionCardContainer")
    wrapper.setFixedSize(card_w + left + right, card_h + top + bottom)
    wrapper.setStyleSheet("background: transparent; border: none;")
    create_alpha_pixmap_shadow(window, wrapper, panel_pixmap, {"x": left, "y": top, "w": card_w, "h": card_h}, shadow_cfg)
    card = QFrame(wrapper)
    card.setObjectName("companionCard")
    card.setGeometry(left, top, card_w, card_h)
    card.setAttribute(Qt.WA_TranslucentBackground, True)
    card.setAutoFillBackground(False)
    card.setStyleSheet("QFrame#companionCard { background: transparent; border: none; }")
    background = QLabel(card)
    background.setObjectName("companionCardBackground")
    background.setGeometry(0, 0, card_w, card_h)
    background.setPixmap(panel_pixmap.scaled(card_w, card_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    background.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    data = deepcopy(companion)
    character_layout = _character_layout(window)

    def persist(field, value):
        if field in {"name", "type", "can_roll"}:
            data[field] = value
        elif field.startswith(("hp_", "mp_")):
            group, key = field.split("_", 1)
            data.setdefault(group, {})[key] = _safe_int(value, data.get(group, {}).get(key, 0))
        else:
            _, index, key = field.split("_", 2)
            data["custom_fields"][int(index)][key] = value
        window.loader.update_companion(data["id"], data)
        window.loader.save_active_character_json()
        window.show_main_section("inventory")

    title_cfg = character_layout.get("title", {})
    create_editable_panel_text(window, card, title_cfg, data.get("name", ""), _safe_int(title_cfg.get("font_size", 28), 28), str(title_cfg.get("color", "#f2d28b")), lambda value: persist("name", value), title="Name bearbeiten", bold=bool(title_cfg.get("bold", True)), align=str(title_cfg.get("align", "center")))

    def refresh_portrait():
        window.loader.save_active_character_json()
        window.show_main_section("inventory")

    def choose_portrait():
        path, _ = QFileDialog.getOpenFileName(window, "Companion-Bild auswählen", "", "Bilder (*.png *.jpg *.jpeg *.webp)")
        if path and window.loader.set_companion_portrait_file(data["id"], path):
            refresh_portrait()

    def paste_portrait():
        image = QApplication.clipboard().image()
        target = window.loader.get_companion_portrait_target_path(data["id"], ".png")
        if not image.isNull() and target and image.save(target, "PNG") and window.loader.set_companion_portrait_reference(data["id"], target):
            refresh_portrait()

    portrait_cfg = character_layout.get("portrait", {})
    portrait_display_cfg = content_cfg.get("portrait", {})
    inset = portrait_display_cfg.get("inset", {}) if isinstance(portrait_display_cfg.get("inset"), dict) else {}
    outer_x, outer_y, outer_w, outer_h = _rect(portrait_cfg, (34, 94, 92, 135))
    inset_left = _safe_int(inset.get("left", 0), 0)
    inset_top = _safe_int(inset.get("top", 0), 0)
    inset_right = _safe_int(inset.get("right", 0), 0)
    inset_bottom = _safe_int(inset.get("bottom", 0), 0)
    portrait = CompanionPortraitLabel(card, choose_portrait, paste_portrait)
    portrait.setObjectName("companionPortrait")
    portrait.setGeometry(outer_x + inset_left, outer_y + inset_top, max(1, outer_w - inset_left - inset_right), max(1, outer_h - inset_top - inset_bottom))
    portrait.setProperty("portrait_fit_mode", str(portrait_display_cfg.get("fit_mode", "contain")))
    portrait.setProperty("portrait_frame_rect", (outer_x, outer_y, outer_w, outer_h))
    portrait.setAlignment(Qt.AlignCenter)
    portrait.setStyleSheet("background: transparent; border: none; color: #9d9585; font-size: 12px;")
    _set_portrait_pixmap(portrait, window.loader.get_companion_portrait_path(data), portrait.property("portrait_fit_mode"))

    fields_cfg = character_layout.get("fields", {})
    rows = {str(row.get("id", "")): row for row in fields_cfg.get("rows", []) if isinstance(row, dict)}
    for resource in ("hp", "mp"):
        row = rows.get(resource, {})
        font_size = _safe_int(row.get("font_size", 22), 22)
        color = str(row.get("color", "#ffffff"))
        window.create_panel_text(card, row.get("label_rect", {}), resource.upper(), font_size, color, bold=bool(row.get("label_bold", False)), align=str(row.get("label_align", "left")))
        for key in ("current", "max"):
            create_editable_panel_text(window, card, row.get(f"{key}_rect", {}), data.get(resource, {}).get(key, 0), _safe_int(row.get("value_font_size", font_size), font_size), str(row.get("value_color", color)), lambda value, field=f"{resource}_{key}": persist(field, value), title=f"{resource.upper()} {key} bearbeiten", bold=bool(row.get("bold_value", fields_cfg.get("bold_values", True))), align=str(row.get("value_align", "left")))

    custom_fields = data.get("custom_fields", [])
    for row_cfg in content_cfg.get("custom_slots", []):
        index = _safe_int(row_cfg.get("field_index", -1), -1)
        if index < 0 or index >= len(custom_fields):
            continue
        custom = custom_fields[index]
        for key in ("label", "value"):
            text_cfg = row_cfg.get(key, {})
            create_editable_panel_text(window, card, text_cfg, custom.get(key, ""), _safe_int(text_cfg.get("font_size", 17), 17), str(text_cfg.get("color", "#f0e6c8")), lambda value, field=f"custom_{index}_{key}": persist(field, value), title=f"{custom.get('label', 'Feld')} bearbeiten", bold=bool(text_cfg.get("bold", key == "value")), align=str(text_cfg.get("align", "left")))

    type_cfg = content_cfg.get("type", {})
    create_editable_panel_text(window, card, type_cfg, data.get("type", ""), _safe_int(type_cfg.get("font_size", 15), 15), str(type_cfg.get("color", "#f0e6c8")), lambda value: persist("type", value), title="Typ / Beschreibung bearbeiten", bold=True, align=str(type_cfg.get("align", "center")))

    roll_cfg = content_cfg.get("can_roll", {})
    window.create_panel_text(card, roll_cfg.get("label", {}), str(roll_cfg.get("text", "Kann würfeln")), _safe_int(roll_cfg.get("font_size", 15), 15), str(roll_cfg.get("color", "#eadfca")), bold=True, align="left")
    marker_cfg = roll_cfg.get("marker", {})
    marker = QPushButton(card)
    marker.setObjectName("companionCanRollMarker")
    marker.setGeometry(*_rect(marker_cfg, (292, 480, 28, 28)))
    marker_path = _asset_path(window, "ui_elements/icons/checkmark_true.png" if data.get("can_roll", False) else "ui_elements/icons/checkmark_false.png")
    marker.setStyleSheet(f"border: none; background: transparent; border-image: url({marker_path.as_posix() if marker_path else ''}) 0 0 0 0 stretch stretch;")
    marker.clicked.connect(lambda: persist("can_roll", not bool(data.get("can_roll", False))))

    button_path = _asset_path(window, str(card_cfg.get("button_asset", "buttons/menu_button_small.png")))
    buttons = []
    for key, fallback_text, fallback in (("rolls_button", "Würfe", (30, 530, 92, 34)), ("duplicate_button", "Duplizieren", (134, 530, 96, 34)), ("delete_button", "Löschen", (242, 530, 88, 34))):
        button_cfg = content_cfg.get(key, {})
        button = _button(str(button_cfg.get("text", fallback_text)), card, button_path.as_posix() if button_path else "")
        button.setGeometry(*_rect(button_cfg, fallback))
        buttons.append(button)
    rolls_button, duplicate_button, delete_button = buttons
    rolls_button.clicked.connect(lambda: _edit_rolls(window, data, lambda: persist("name", data.get("name", ""))))
    duplicate_button.clicked.connect(lambda: _duplicate_companion(window, data["id"]))
    delete_button.clicked.connect(lambda: _delete_companion(window, data["id"], str(data.get("name", ""))))
    card.show()
    return wrapper


def _add_companion(window):
    window.loader.add_companion()
    window.loader.save_active_character_json()
    window.show_main_section("inventory")


def _duplicate_companion(window, companion_id):
    window.loader.duplicate_companion(companion_id)
    window.loader.save_active_character_json()
    window.show_main_section("inventory")


def _delete_companion(window, companion_id, name):
    answer = QMessageBox.question(window, "Companion löschen", f'Companion "{name or "Ohne Name"}" wirklich löschen?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if answer == QMessageBox.Yes:
        window.loader.delete_companion(companion_id)
        window.loader.save_active_character_json()
        window.show_main_section("inventory")


def _edit_rolls(window, data, save_callback):
    def rolls_changed(rolls):
        data["rolls"] = rolls
        save_callback()

    dialog = CompanionRollDialog(
        window,
        data.get("name", "Companion"),
        window.get_inventory_roll_options(),
        data.get("rolls", []),
        on_change=rolls_changed,
    )
    dialog.exec()
