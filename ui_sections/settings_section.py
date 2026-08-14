import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QComboBox, QFrame, QPushButton, QWidget

from app_logger import log_debug, log_error, log_warning
from app_paths import load_settings, save_settings


START_TAB_LABELS = {
    "character": "Charakter",
    "skills": "Fertigkeiten",
    "inventory": "Inventar",
    "equipment": "Ausrüstung",
    "magic": "Magie",
    "notes": "Notizen",
}

SCALE_LABELS = {
    0.9: "90 %",
    1.0: "100 %",
    1.1: "110 %",
    1.25: "125 %",
}

CATEGORIES = [
    ("general", "Allgemein"),
    ("appearance", "Darstellung"),
    ("character", "Charakter"),
    ("roll20", "Roll20 / Browser"),
    ("debug", "Debug & Daten"),
]


def render_settings_section(window):
    if window.content_layer is None:
        return

    window.settings, _created = load_settings()
    if not hasattr(window, "_settings_active_category"):
        window._settings_active_category = "general"
    if window._settings_active_category not in {key for key, _label in CATEGORIES}:
        window._settings_active_category = "general"

    window._settings_checkbox_widgets = {}
    window._settings_category_buttons = {}
    window._settings_category_pages = {}

    style = _settings_style(window)
    layer_w = window.content_layer.width()
    layer_h = window.content_layer.height()
    title = _label(window.content_layer, 60, 34, 420, 46, "Einstellungen", style, size=31, weight=700)
    title.show()

    nav_x = 58
    nav_y = 102
    nav_w = 230
    nav_h = max(420, layer_h - nav_y - 56)
    content_x = nav_x + nav_w + 22
    content_y = nav_y
    content_w = max(620, layer_w - content_x - 62)
    content_h = nav_h

    nav_panel = QFrame(window.content_layer)
    nav_panel.setGeometry(nav_x, nav_y, nav_w, nav_h)
    nav_panel.setStyleSheet(_panel_stylesheet(style))
    nav_panel.show()

    content_panel = QFrame(window.content_layer)
    content_panel.setGeometry(content_x, content_y, content_w, content_h)
    content_panel.setStyleSheet(_panel_stylesheet(style))
    content_panel.show()

    for index, (category_id, text) in enumerate(CATEGORIES):
        button = _nav_button(window, nav_panel, 18, 22 + (index * 56), nav_w - 36, 42, category_id, text, style)
        window._settings_category_buttons[category_id] = button

    pages = {
        "general": _build_general_page(window, content_panel, style),
        "appearance": _build_appearance_page(window, content_panel, style),
        "character": _build_character_page(window, content_panel, style),
        "roll20": _build_roll20_page(window, content_panel, style),
        "debug": _build_debug_page(window, content_panel, style),
    }
    window._settings_category_pages = pages
    _update_category_state(window)


def _settings_style(window):
    theme_style = getattr(window, "theme_style", {}) if isinstance(getattr(window, "theme_style", {}), dict) else {}
    default_text = theme_style.get("default_text", {}) if isinstance(theme_style.get("default_text", {}), dict) else {}
    nav_style = theme_style.get("nav_button", {}) if isinstance(theme_style.get("nav_button", {}), dict) else {}
    return {
        "text": str(default_text.get("color", "#e8e0c8")),
        "muted": "rgba(232, 224, 200, 175)",
        "gold": str(nav_style.get("active_color", "#f2d28b")),
        "blue": "#8ec7ff",
        "border": "rgba(207, 166, 83, 150)",
        "panel_bg": "rgba(10, 9, 8, 135)",
        "field_bg": "rgba(8, 8, 8, 165)",
        "button_asset": "buttons/menu_button_medium.png",
        "wide_button_asset": "buttons/menu_button_wide.png",
        "checkbox_true": "icons/checkmark_true.png",
        "checkbox_false": "icons/checkmark_false.png",
    }


def _panel_stylesheet(style):
    return (
        "QFrame {"
        f"background: {style['panel_bg']};"
        f"border: 1px solid {style['border']};"
        "}"
    )


def _label(parent, x, y, w, h, text, style, size=18, weight=500, color=None, align=Qt.AlignLeft | Qt.AlignVCenter):
    label = QLabel(parent)
    label.setGeometry(x, y, w, h)
    label.setText(text)
    label.setAlignment(align)
    label.setStyleSheet(
        f"background: transparent; border: none; color: {color or style['text']}; "
        f"font-size: {size}px; font-weight: {weight};"
    )
    return label


def _section_title(parent, y, text, style):
    title = _label(parent, 34, y, 360, 34, text, style, size=22, weight=700, color=style["gold"])
    title.show()
    line = QFrame(parent)
    line.setGeometry(34, y + 38, parent.width() - 68, 1)
    line.setStyleSheet(f"background: {style['border']}; border: none;")
    line.show()
    return y + 56


def _value_label(parent, x, y, w, h, text, style):
    label = QLabel(parent)
    label.setGeometry(x, y, w, h)
    label.setText(text)
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    label.setStyleSheet(
        "QLabel {"
        f"background: {style['field_bg']}; color: {style['blue']}; "
        f"border: 1px solid {style['border']}; padding-left: 12px; "
        "font-size: 18px; font-weight: 650;"
        "}"
    )
    label.show()
    return label


def _combo(parent, x, y, w, h, style):
    combo = QComboBox(parent)
    combo.setGeometry(x, y, w, h)
    combo.setStyleSheet(
        "QComboBox {"
        f"background-color: {style['field_bg']}; color: {style['blue']}; "
        f"border: 1px solid {style['border']}; padding-left: 10px; padding-right: 24px; "
        "font-size: 17px; font-weight: 600;"
        "}"
        "QComboBox::drop-down {"
        f"border-left: 1px solid {style['border']}; width: 24px; background: rgba(30, 22, 12, 170);"
        "}"
        "QComboBox QAbstractItemView {"
        "background-color: rgba(10, 10, 10, 235);"
        f"color: {style['text']}; selection-background-color: rgba(95, 69, 30, 210);"
        f"border: 1px solid {style['border']};"
        "}"
    )
    combo.show()
    return combo


def _button(window, parent, x, y, w, h, text, callback, style):
    return window.create_asset_text_button(
        parent,
        {
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "asset": style["button_asset"],
            "text": text,
            "font_size": 17,
            "color": style["gold"],
        },
        text,
        callback,
    )


def _nav_button(window, parent, x, y, w, h, category_id, text, style):
    result = window.create_asset_text_button(
        parent,
        {
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "asset": style["wide_button_asset"],
            "text": text,
            "font_size": 16,
            "color": style["text"],
        },
        text,
        lambda checked=False, cid=category_id: _set_category(window, cid),
    )
    return result


def _set_category(window, category_id):
    window._settings_active_category = category_id
    _update_category_state(window)


def _update_category_state(window):
    active = getattr(window, "_settings_active_category", "general")
    style = _settings_style(window)
    for category_id, button in getattr(window, "_settings_category_buttons", {}).items():
        text_label = button.get("text") if isinstance(button, dict) else None
        if text_label is not None:
            color = style["gold"] if category_id == active else style["text"]
            size = 17 if category_id == active else 16
            text_label.setStyleSheet(
                f"background: transparent; color: {color}; font-size: {size}px; font-weight: 750;"
            )
    for category_id, page in getattr(window, "_settings_category_pages", {}).items():
        page.setVisible(category_id == active)
        if category_id == active:
            page.raise_()


def _page(parent):
    page = QWidget(parent)
    page.setGeometry(0, 0, parent.width(), parent.height())
    page.setStyleSheet("background: transparent;")
    page.show()
    return page


def _settings_dict(window):
    if not isinstance(getattr(window, "settings", None), dict):
        window.settings, _created = load_settings()
    return window.settings


def _save_window_settings(window):
    save_settings(_settings_dict(window))


def _build_general_page(window, parent, style):
    page = _page(parent)
    y = _section_title(page, 32, "ALLGEMEIN", style)

    _label(page, 34, y, 320, 34, "Beim Start letzten Charakter laden", style, size=18).show()
    _checkbox(
        window,
        page,
        390,
        y - 5,
        "startup_load_last",
        bool(_settings_dict(window).get("startup", {}).get("load_last_character", True)),
        lambda checked: _set_nested_setting(window, "startup", "load_last_character", checked),
        style,
    )
    y += 62

    _label(page, 34, y, 200, 34, "Startbereich", style, size=18).show()
    combo = _combo(page, 390, y - 2, 240, 38, style)
    current = str(_settings_dict(window).get("startup", {}).get("start_tab", "character") or "character")
    for key, label in START_TAB_LABELS.items():
        combo.addItem(label, key)
        if key == current:
            combo.setCurrentIndex(combo.count() - 1)
    combo.currentIndexChanged.connect(
        lambda _index, c=combo: _set_nested_setting(window, "startup", "start_tab", c.currentData())
    )
    y += 70

    _section_title(page, y, "EINSTELLUNGEN MERKEN", style)
    _label(
        page,
        34,
        y + 58,
        parent.width() - 84,
        54,
        "Alle neuen Optionen werden in der bestehenden data/settings.json gespeichert.",
        style,
        size=17,
        color=style["muted"],
    ).show()
    return page


def _build_appearance_page(window, parent, style):
    page = _page(parent)
    y = _section_title(page, 32, "DARSTELLUNG", style)

    _label(page, 34, y, 220, 34, "Aktuelles Theme", style, size=18).show()
    window.settings_theme_value_label = _value_label(page, 390, y - 2, 260, 38, window.get_active_theme(), style)
    y += 60
    _button(window, page, 390, y, 220, 44, "Theme wechseln", window.on_settings_switch_theme_clicked, style)
    y += 82

    _section_title(page, y, "UI", style)
    y += 58
    _label(page, 34, y, 220, 34, "UI-Skalierung", style, size=18).show()
    combo = _combo(page, 390, y - 2, 160, 38, style)
    current_scale = _settings_dict(window).get("appearance", {}).get("ui_scale", 1.0)
    for value, label in SCALE_LABELS.items():
        combo.addItem(label, value)
        if float(current_scale) == float(value):
            combo.setCurrentIndex(combo.count() - 1)
    combo.currentIndexChanged.connect(
        lambda _index, c=combo: _set_nested_setting(window, "appearance", "ui_scale", c.currentData())
    )
    _label(
        page,
        34,
        y + 50,
        parent.width() - 84,
        42,
        "Skalierung wird gespeichert und kann an eine zentrale Theme-Skalierung angebunden werden.",
        style,
        size=16,
        color=style["muted"],
    ).show()
    return page


def _build_character_page(window, parent, style):
    page = _page(parent)
    y = _section_title(page, 32, "CHARAKTER", style)

    _label(page, 34, y, 220, 34, "Aktiver Charakter", style, size=18).show()
    window.settings_character_active_label = _value_label(
        page,
        390,
        y - 2,
        360,
        38,
        window.loader.current_character_name,
        style,
    )
    y += 62

    window.settings_character_combo = _combo(page, 34, y, min(620, parent.width() - 84), 38, style)
    window.settings_character_combo.currentIndexChanged.connect(window.on_settings_character_selection_changed)
    refresh_character_cache_list(window)
    y += 64

    _button(window, page, 34, y, 205, 44, "Charakter laden", window.on_settings_load_character_clicked, style)
    _button(window, page, 258, y, 205, 44, "Liste aktualisieren", window.on_settings_refresh_character_list_clicked, style)
    _button(window, page, 482, y, 220, 44, "Charakterordner öffnen", lambda: _open_character_folder(window), style)
    y += 92

    _section_title(page, y, "SPEICHERORT", style)
    _label(page, 34, y + 58, parent.width() - 84, 34, "Speicherort: data/characters", style, size=17, color=style["blue"]).show()
    _label(
        page,
        34,
        y + 96,
        parent.width() - 84,
        34,
        "Legacy characters from the old cache location remain supported.",
        style,
        size=16,
        color=style["muted"],
    ).show()
    return page


def _build_roll20_page(window, parent, style):
    page = _page(parent)
    y = _section_title(page, 32, "ROLL20 / BROWSER", style)

    _label(page, 34, y, 260, 34, "Roll20 beim Wurf öffnen", style, size=18).show()
    _checkbox(
        window,
        page,
        390,
        y - 5,
        "roll20_open_browser",
        bool(_settings_dict(window).get("roll20", {}).get("open_browser_on_roll", True)),
        lambda checked: _set_nested_setting(window, "roll20", "open_browser_on_roll", checked),
        style,
    )
    y += 76

    _section_title(page, y, "BROWSERPROFIL", style)
    y += 58
    _label(page, 34, y, 300, 34, "Status", style, size=18).show()
    _value_label(page, 390, y - 2, 360, 38, "Persistentes Roll20-Profil aktiv", style)
    y += 56

    profile_path = _browser_profile_display(window)
    _label(page, 34, y, 300, 34, "Profilpfad", style, size=18).show()
    _value_label(page, 390, y - 2, min(470, parent.width() - 430), 38, profile_path, style)
    return page


def _build_debug_page(window, parent, style):
    page = _page(parent)
    y = _section_title(page, 32, "DEBUG", style)

    _button(window, page, 34, y, 185, 44, "Debug öffnen", window.open_debug_dialog, style)
    _button(window, page, 238, y, 185, 44, "Berechnungen", window.open_calculation_center, style)
    y += 66

    _label(page, 34, y, 260, 34, "Debug beim Start anzeigen", style, size=18).show()
    _checkbox(
        window,
        page,
        390,
        y - 5,
        "debug_start",
        bool(getattr(window, "settings_debug_on_start", False)),
        lambda checked: _set_debug_on_start(window, checked),
        style,
    )
    y += 86

    _section_title(page, y, "DATEN", style)
    y += 58
    _button(window, page, 34, y, 185, 44, "Cache neu laden", window.on_settings_cache_reload_clicked, style)
    return page


def _browser_profile_display(window):
    try:
        from ui_sections import browser_section

        cfg = browser_section.load_browser_layout_config(window).get("browser_screen", {})
        profile_cfg = cfg.get("profile", {}) if isinstance(cfg, dict) else {}
        subdir = str(profile_cfg.get("storage_subdir", "browser_profiles/roll20_default") or "browser_profiles/roll20_default")
        if bool(profile_cfg.get("use_default_profile", False)):
            subdir = "browser_profiles/roll20_default"
        return subdir
    except Exception:
        return "browser_profiles/roll20_default"


def _checkbox(window, parent, x, y, key, checked, callback, style):
    container = QWidget(parent)
    container.setGeometry(x, y, 360, 48)
    icon = QLabel(container)
    icon.setGeometry(0, 0, 44, 44)
    icon.setStyleSheet("background: transparent; border: none;")
    icon.setProperty("checked", bool(checked))
    text = QLabel(container)
    text.setGeometry(56, 0, 250, 44)
    text.setText("Ein" if checked else "Aus")
    text.setStyleSheet(
        f"background: transparent; border: none; color: {style['text']}; font-size: 17px; font-weight: 600;"
    )

    click = QPushButton(container)
    click.setGeometry(0, 0, 150, 44)
    click.setText("")
    click.setCursor(Qt.PointingHandCursor)
    click.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0px; }")

    window._settings_checkbox_widgets[key] = {
        "icon": icon,
        "text": text,
        "callback": callback,
        "asset_true": style["checkbox_true"],
        "asset_false": style["checkbox_false"],
    }
    if key == "debug_start":
        window.settings_checkbox_icon_label = icon
        window.settings_checkbox_text_label = text
        window._settings_checkbox_asset_true = style["checkbox_true"]
        window._settings_checkbox_asset_false = style["checkbox_false"]

    click.clicked.connect(lambda checked=False, k=key: _toggle_checkbox(window, k))
    _update_checkbox(window, key, bool(checked))
    container.show()
    return container


def _toggle_checkbox(window, key):
    entry = getattr(window, "_settings_checkbox_widgets", {}).get(key)
    if not isinstance(entry, dict):
        return
    icon = entry.get("icon")
    checked = not bool(icon.property("checked")) if icon is not None else False
    _update_checkbox(window, key, checked)
    callback = entry.get("callback")
    if callable(callback):
        callback(checked)


def _update_checkbox(window, key, checked):
    entry = getattr(window, "_settings_checkbox_widgets", {}).get(key)
    if not isinstance(entry, dict):
        return
    icon = entry.get("icon")
    text = entry.get("text")
    if icon is None:
        return
    icon.setProperty("checked", bool(checked))
    asset = entry.get("asset_true") if checked else entry.get("asset_false")
    pixmap = window.load_ui_pixmap(asset)
    if pixmap is not None:
        icon.setPixmap(pixmap.scaled(icon.width(), icon.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        icon.setText("")
    else:
        icon.setText("X" if checked else "")
        icon.setStyleSheet("background: transparent; border: 1px solid #8a6a32; color: #f2d28b; font-size: 24px;")
    if text is not None:
        text.setText("Ein" if checked else "Aus")


def _set_nested_setting(window, group, key, value):
    settings = _settings_dict(window)
    target = settings.setdefault(group, {})
    if not isinstance(target, dict):
        target = {}
        settings[group] = target
    target[key] = value
    _save_window_settings(window)
    log_debug("render", f"settings {group}.{key}: {value}")


def _set_debug_on_start(window, checked):
    window.settings_debug_on_start = bool(checked)
    _set_nested_setting(window, "startup", "debug_on_start", bool(checked))


def _open_character_folder(window):
    try:
        folder = Path(window.loader.get_character_dir())
        folder.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(folder))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
    except Exception as exc:
        log_warning("character", f"character folder open failed: {exc}")


def update_settings_checkbox_icon(window):
    if getattr(window, "settings_checkbox_icon_label", None) is None:
        return
    _update_checkbox(window, "debug_start", bool(getattr(window, "settings_debug_on_start", False)))


def on_settings_debug_start_toggled(window):
    window.settings_debug_on_start = not window.settings_debug_on_start
    _set_nested_setting(window, "startup", "debug_on_start", bool(window.settings_debug_on_start))
    update_settings_checkbox_icon(window)
    log_debug("render", f"settings debug on start: {window.settings_debug_on_start}")


def refresh_character_cache_list(window):
    if window.settings_character_combo is None:
        return
    active_character_name = window.loader.current_character_name
    window.settings_character_combo.blockSignals(True)
    try:
        window.settings_character_combo.clear()
        caches = window.loader.list_character_caches()
        active_cache = window.loader.active_cache_path
        active_index = -1
        for i, entry in enumerate(caches):
            display_text = f"{entry['name']}  ({entry['file']})"
            window.settings_character_combo.addItem(display_text, entry["path"])
            if entry["path"] == active_cache:
                active_index = i
                active_character_name = entry["name"]
                window.loader.current_character_name = active_character_name
        if active_index >= 0:
            window.settings_character_combo.setCurrentIndex(active_index)
    finally:
        window.settings_character_combo.blockSignals(False)
    if window.settings_character_active_label is not None:
        window.settings_character_active_label.setText(active_character_name)


def on_settings_load_character_clicked(window):
    file_path, _ = QFileDialog.getOpenFileName(
        window,
        "Charakter-Datei auswählen",
        "",
        "Charakter-Dateien (*.xlsx *.xlsm *.ods);;Excel Dateien (*.xlsx *.xlsm);;ODS Dateien (*.ods);;Alle Dateien (*)",
    )

    if not file_path:
        return

    log_debug("character", f"import selected: {file_path}")
    if hasattr(window.loader, "has_unsaved_changes") and window.loader.has_unsaved_changes():
        log_warning("character", "unsaved changes before switching character")
    try:
        window.loader.load_file(file_path)
    except ValueError as exc:
        log_error("cache", f"load failed: {exc}")
        QMessageBox.warning(
            window,
            "Dateiformat nicht unterstützt",
            str(exc),
        )
        return

    window.reset_character_runtime_state()
    window.create_tabs_from_cache()
    refresh_character_cache_list(window)
    if window.settings_character_active_label is not None:
        window.settings_character_active_label.setText(window.loader.current_character_name)
    log_debug("character", f"import loaded: {window.loader.current_character_name}")
    window.show_main_section("character")


def on_settings_character_selection_changed(window, index):
    if window.settings_character_combo is None:
        return
    if index < 0:
        return
    cache_path = window.settings_character_combo.currentData()
    if not isinstance(cache_path, str) or not cache_path:
        return
    active_cache_path = window.loader.active_cache_path
    if active_cache_path and Path(cache_path) == Path(active_cache_path):
        return
    if hasattr(window.loader, "has_unsaved_changes") and window.loader.has_unsaved_changes():
        log_warning("character", "unsaved changes before switching character")
    ok = window.loader.load_character_cache(cache_path)
    if not ok:
        QMessageBox.warning(window, "Charakter laden", "Charakter-Cache konnte nicht geladen werden.")
        return
    window.reset_character_runtime_state()
    if window.settings_character_active_label is not None:
        window.settings_character_active_label.setText(window.loader.current_character_name)
    window.create_tabs_from_cache()
    if window.current_main_section == "character":
        window.show_main_section("character")
    elif window.current_main_section in ("skills", "fertigkeiten"):
        window.show_main_section("skills")
    elif window.current_main_section == "inventory":
        window.show_main_section("inventory")
    elif window.current_main_section in ("equipment", "ausruestung", "ausrüstung"):
        window.show_main_section("equipment")
    elif window.current_main_section == "magic":
        window.show_main_section("magic")
    elif window.current_main_section == "notes":
        window.show_main_section("notes")
    log_debug("cache", f"character cache loaded: {cache_path}")


def on_settings_refresh_character_list_clicked(window):
    refresh_character_cache_list(window)
    log_debug("character", "cache list refreshed")
