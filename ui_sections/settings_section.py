import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog, QLabel, QMessageBox, QComboBox, QFrame, QPushButton, QWidget,
    QScrollArea, QVBoxLayout, QHBoxLayout, QSizePolicy,
)

from app_logger import log_debug, log_error, log_warning
from app_paths import load_settings, save_settings
from ui_sections.notes_section import _render_notes_nine_slice_pixmap


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
    cfg = style["config"]
    geometry = cfg.get("layout", {})
    title_cfg = cfg.get("title", {})
    title = _label(window.content_layer, title_cfg.get("text", "Einstellungen"), style,
                   size=int(title_cfg.get("font_size", 30)), color=style["gold"], weight=700)
    title.setGeometry(int(title_cfg.get("x", 58)), int(title_cfg.get("y", 30)),
                      int(title_cfg.get("w", 500)), int(title_cfg.get("h", 46)))
    title.show()

    nav_x, nav_y = int(geometry.get("x", 58)), int(geometry.get("y", 96))
    nav_w = int(geometry.get("navigation_w", 242))
    panel_h = max(1, window.content_layer.height() - nav_y - int(geometry.get("bottom", 44)))
    content_x = nav_x + nav_w + int(geometry.get("panel_gap", 20))
    content_w = max(1, window.content_layer.width() - content_x - int(geometry.get("right", 58)))
    nav_panel = _panel(window, window.content_layer, nav_x, nav_y, nav_w, panel_h, style)
    content_panel = _panel(window, window.content_layer, content_x, nav_y, content_w, panel_h, style)

    nav_cfg = cfg.get("navigation", {})
    nav_scroll, nav_body = _scroll_body(nav_panel, style)
    nav_layout = nav_body.layout()
    nav_layout.setContentsMargins(*nav_cfg.get("margins", [4, 8, 4, 8]))
    nav_layout.setSpacing(int(nav_cfg.get("spacing", 12)))
    nav_button_w = nav_w - 2 * int(cfg.get("panel", {}).get("inset", 16))
    margins = nav_cfg.get("margins", [4, 8, 4, 8])
    nav_button_w -= int(margins[0]) + int(margins[2])
    nav_button_w -= int(cfg.get("scrollbar", {}).get("w", 12))
    for category_id, text in CATEGORIES:
        button = _nav_button(window, nav_body, nav_button_w, category_id, text, style)
        nav_layout.addWidget(button["container"], 0, Qt.AlignLeft)
        window._settings_category_buttons[category_id] = button
    nav_layout.addStretch()

    window._settings_category_pages = {
        "general": _build_general_page(window, content_panel, style),
        "appearance": _build_appearance_page(window, content_panel, style),
        "character": _build_character_page(window, content_panel, style),
        "roll20": _build_roll20_page(window, content_panel, style),
        "debug": _build_debug_page(window, content_panel, style),
    }
    _update_category_state(window)


def _settings_style(window):
    cfg = getattr(window, "main_ui_layout_config", {}).get("settings_page", {})
    theme = getattr(window, "theme_style", {})
    colors = cfg.get("colors", {})
    return {
        "config": cfg,
        "text": str(colors.get("text", theme.get("default_text", {}).get("color", "#e8e0c8"))),
        "gold": str(colors.get("heading", theme.get("nav_button", {}).get("active_color", "#f2d28b"))),
        "muted": str(colors.get("muted", "#c8c0aa")),
        "blue": str(colors.get("value", "#7fd0ff")),
        "separator": str(colors.get("separator", "rgba(242, 210, 139, 75)")),
        "panel_bg": str(colors.get("fallback_panel", "rgba(10, 9, 8, 135)")),
        "field_bg": str(colors.get("field_background", "#14100d")),
        "selection": str(colors.get("selection", "#5f451e")),
        "checkbox_true": cfg.get("checkbox", {}).get("asset_true", "ui_elements/icons/checkmark_true.png"),
        "checkbox_false": cfg.get("checkbox", {}).get("asset_false", "ui_elements/icons/checkmark_false.png"),
        "window": window,
    }


def _panel(window, parent, x, y, w, h, style):
    panel = QFrame(parent)
    panel.setGeometry(x, y, w, h)
    panel.setFrameShape(QFrame.NoFrame)
    panel.setStyleSheet("background: transparent; border: none;")
    cfg = style["config"].get("panel", {})
    source = window.load_ui_pixmap(cfg.get("asset", "panels/shared_skils_panel_frame.png"))
    background = QLabel(panel)
    background.setGeometry(0, 0, w, h)
    background.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    if source is not None and not source.isNull():
        background.setPixmap(_render_notes_nine_slice_pixmap(source, w, h, cfg, window._safe_int))
    else:
        background.setStyleSheet(f"background: {style['panel_bg']}; border: none;")
    background.lower()
    panel.show()
    return panel


def _scrollbar_style(style):
    cfg = style["config"].get("scrollbar", {})
    width = int(cfg.get("w", 12))
    minimum = int(cfg.get("minimum_handle", 24))
    background = cfg.get("background", "#17110f")
    handle = cfg.get("handle", "#6c4a22")
    return (
        f"QScrollBar:vertical {{ background: {background}; width: {width}px; margin: 0px; }}"
        f"QScrollBar:horizontal {{ background: {background}; height: {width}px; margin: 0px; }}"
        f"QScrollBar::handle:vertical {{ background: {handle}; min-height: {minimum}px; }}"
        f"QScrollBar::handle:horizontal {{ background: {handle}; min-width: {minimum}px; }}"
        "QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }"
        "QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }"
    )


def _scroll_body(parent, style):
    inset = int(style["config"].get("panel", {}).get("inset", 16))
    scroll = QScrollArea(parent)
    scroll.setGeometry(inset, inset, max(1, parent.width() - inset * 2), max(1, parent.height() - inset * 2))
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }" + _scrollbar_style(style))
    scroll.viewport().setAutoFillBackground(False)
    body = QWidget()
    body.setStyleSheet("background: transparent;")
    QVBoxLayout(body)
    scroll.setWidget(body)
    body.setAutoFillBackground(False)
    scroll.show()
    return scroll, body


def _label(parent, text, style, size=None, weight=500, color=None):
    label = QLabel(str(text), parent)
    label.setTextFormat(Qt.PlainText)
    label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    size = size or int(style["config"].get("fonts", {}).get("label", 16))
    label.setStyleSheet(
        f"background: transparent; border: none; color: {color or style['text']}; "
        f"font-size: {size}px; font-weight: {weight};"
    )
    return label


def _section_title(page, text, style):
    cfg = style["config"]
    page.layout().addSpacing(int(cfg.get("content", {}).get("section_gap", 16)))
    section = QWidget(page)
    section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(int(cfg.get("separator", {}).get("spacing", 8)))
    layout.addWidget(_label(section, text, style, size=int(cfg.get("fonts", {}).get("section", 18)),
                            weight=700, color=style["gold"]))
    line = QFrame(section)
    line.setFixedHeight(int(cfg.get("separator", {}).get("h", 1)))
    line.setStyleSheet(f"background: {style['separator']}; border: none;")
    layout.addWidget(line)
    page.layout().addWidget(section)


def _field_background(style, wide=False):
    cfg = style["config"].get("fields", {})
    name = cfg.get("wide_frame", "frames/1024x122_box.png") if wide else cfg.get("frame", "frames/512x122_box.png")
    path = style["window"].resolve_ui_asset_path(name)
    if path is not None and path.exists():
        return f'border-image: url("{path.as_posix()}") 0 0 0 0 stretch stretch;'
    return f"background: {style['field_bg']};"


def _value_label(parent, text, style, width_key="value_w"):
    cfg = style["config"].get("fields", {})
    label = _label(parent, text, style)
    label.setFixedSize(int(cfg.get(width_key, 260)), int(cfg.get("h", 40)))
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if width_key == "path_w":
        label.setToolTip(str(text))
    label.setStyleSheet(
        "QLabel {" + _field_background(style, width_key in {"character_w", "path_w"}) +
        f"color: {style['blue']}; border: none; padding: 0px {int(cfg.get('padding', 12))}px; "
        f"font-size: {int(style['config'].get('fonts', {}).get('value', 17))}px; font-weight: 600; }}"
    )
    if cfg.get("align", "left") == "center":
        label.setAlignment(Qt.AlignCenter)
    return label


def _combo(parent, style, width_key="selector_w"):
    cfg = style["config"].get("fields", {})
    combo = QComboBox(parent)
    combo.setFixedSize(int(cfg.get(width_key, 240)), int(cfg.get("h", 40)))
    combo.setStyleSheet(
        "QComboBox {" + _field_background(style, width_key == "character_w") +
        f"color: {style['blue']}; border: none; padding-left: {int(cfg.get('padding', 12))}px; "
        f"padding-right: {int(cfg.get('dropdown_w', 26))}px; "
        f"font-size: {int(style['config'].get('fonts', {}).get('value', 17))}px; }}"
        f"QComboBox::drop-down {{ border: none; background: transparent; width: {int(cfg.get('dropdown_w', 26))}px; }}"
        "QComboBox::down-arrow { image: none; width: 0px; height: 0px; }"
        "QComboBox QAbstractItemView {"
        f"background: {style['field_bg']}; color: {style['text']}; border: none; "
        f"selection-background-color: {style['selection']}; selection-color: {style['blue']}; }}"
        + _scrollbar_style(style)
    )
    arrow_width = int(cfg.get("dropdown_w", 26))
    arrow = _label(combo, cfg.get("dropdown_text", "▾"), style, color=style["gold"])
    arrow.setGeometry(combo.width() - arrow_width, 0, arrow_width, combo.height())
    arrow.setAlignment(Qt.AlignCenter)
    arrow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    return combo


def _button(window, parent, text, callback, style, wide=False):
    cfg = style["config"].get("buttons", {})
    width = int(cfg.get("wide_w" if wide else "w", 240 if wide else 200))
    height = int(cfg.get("h", 44))
    result = window.create_asset_text_button(parent, {
        "x": 0, "y": 0, "w": width, "h": height,
        "asset": cfg.get("asset", "buttons/menu_button_medium.png"), "text": text,
        "font_size": int(cfg.get("font_size", 16)), "color": style["gold"],
    }, text, callback)
    result["container"].setFixedSize(width, height)
    return result["container"]


def _nav_button(window, parent, width, category_id, text, style):
    cfg = style["config"].get("navigation", {})
    height = int(cfg.get("button_h", 44))
    result = window.create_asset_text_button(parent, {
        "x": 0, "y": 0, "w": width, "h": height,
        "asset": cfg.get("button_asset", "buttons/menu_button_wide.png"), "text": text,
        "font_size": int(cfg.get("font_size", 16)), "color": style["muted"],
    }, text, lambda checked=False, cid=category_id: _set_category(window, cid))
    result["container"].setFixedSize(width, height)
    marker = QLabel(result["container"])
    inset = int(cfg.get("indicator_inset", 10))
    marker.setGeometry(inset, inset, int(cfg.get("indicator_w", 3)), max(1, height - inset * 2))
    marker.setStyleSheet(f"background: {style['gold']}; border: none;")
    marker.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    result["marker"] = marker
    return result


def _set_category(window, category_id):
    window._settings_active_category = category_id
    _update_category_state(window)


def _update_category_state(window):
    active = getattr(window, "_settings_active_category", "general")
    style = _settings_style(window)
    cfg = style["config"].get("navigation", {})
    for category_id, button in getattr(window, "_settings_category_buttons", {}).items():
        selected = category_id == active
        text_label = button.get("text") if isinstance(button, dict) else None
        if text_label is not None:
            color = style["gold"] if selected else style["muted"]
            size = int(cfg.get("active_font_size", 17) if selected else cfg.get("font_size", 16))
            text_label.setStyleSheet(
                f"background: transparent; color: {color}; font-size: {size}px; font-weight: 750;"
            )
        if isinstance(button, dict) and button.get("marker") is not None:
            button["marker"].setVisible(selected)
    for category_id, page in getattr(window, "_settings_category_pages", {}).items():
        page.setVisible(category_id == active)
        if category_id == active:
            page.raise_()


def _page(parent, title, style):
    scroll, page = _scroll_body(parent, style)
    page._settings_scroll = scroll
    cfg = style["config"]
    layout = page.layout()
    layout.setContentsMargins(*cfg.get("content", {}).get("margins", [18, 12, 18, 20]))
    layout.setSpacing(int(cfg.get("content", {}).get("row_spacing", 14)))
    layout.addWidget(_label(page, title, style, size=int(cfg.get("fonts", {}).get("page", 24)),
                            weight=700, color=style["gold"]))
    return page


def _finish_page(page):
    page.layout().addStretch()
    return page._settings_scroll


def _form_row(page, text, control, style):
    cfg = style["config"].get("content", {})
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(int(cfg.get("column_gap", 20)))
    label = _label(page, text, style)
    label.setFixedWidth(int(cfg.get("label_w", 290)))
    label.setWordWrap(True)
    row.addWidget(label)
    row.addWidget(control)
    row.addStretch()
    page.layout().addLayout(row)


def _actions(page, style, *buttons):
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(int(style["config"].get("buttons", {}).get("spacing", 12)))
    for button in buttons:
        row.addWidget(button)
    row.addStretch()
    page.layout().addLayout(row)


def _note(page, text, style):
    label = _label(page, text, style, size=int(style["config"].get("fonts", {}).get("note", 14)), color=style["muted"])
    label.setWordWrap(True)
    page.layout().addWidget(label)


def _settings_dict(window):
    if not isinstance(getattr(window, "settings", None), dict):
        window.settings, _created = load_settings()
    return window.settings


def _save_window_settings(window):
    save_settings(_settings_dict(window))


def _build_general_page(window, parent, style):
    page = _page(parent, "ALLGEMEIN", style)
    _section_title(page, "STARTVERHALTEN", style)
    checkbox = _checkbox(window, page, "startup_load_last",
        bool(_settings_dict(window).get("startup", {}).get("load_last_character", True)),
        lambda checked: _set_nested_setting(window, "startup", "load_last_character", checked), style)
    _form_row(page, "Beim Start letzten Charakter laden", checkbox, style)
    combo = _combo(page, style)
    current = str(_settings_dict(window).get("startup", {}).get("start_tab", "character") or "character")
    for key, label in START_TAB_LABELS.items():
        combo.addItem(label, key)
        if key == current:
            combo.setCurrentIndex(combo.count() - 1)
    combo.currentIndexChanged.connect(
        lambda _index, c=combo: _set_nested_setting(window, "startup", "start_tab", c.currentData())
    )
    _form_row(page, "Startbereich", combo, style)
    return _finish_page(page)


def _build_appearance_page(window, parent, style):
    page = _page(parent, "DARSTELLUNG", style)
    _section_title(page, "THEME", style)
    window.settings_theme_value_label = _value_label(page, window.get_active_theme(), style)
    _form_row(page, "Aktuelles Theme", window.settings_theme_value_label, style)
    _actions(page, style, _button(window, page, "Theme wechseln", window.on_settings_switch_theme_clicked, style))
    _section_title(page, "UI", style)
    combo = _combo(page, style, "scale_w")
    current_scale = _settings_dict(window).get("appearance", {}).get("ui_scale", 1.0)
    for value, label in SCALE_LABELS.items():
        combo.addItem(label, value)
        if float(current_scale) == float(value):
            combo.setCurrentIndex(combo.count() - 1)
    combo.currentIndexChanged.connect(
        lambda _index, c=combo: _set_nested_setting(window, "appearance", "ui_scale", c.currentData())
    )
    _form_row(page, "UI-Skalierung", combo, style)
    _note(page, "Die Auswahl wird gespeichert. Die Darstellung wird derzeit noch nicht skaliert.", style)
    return _finish_page(page)


def _build_character_page(window, parent, style):
    page = _page(parent, "CHARAKTER", style)
    _section_title(page, "AUSWAHL", style)
    window.settings_character_active_label = _value_label(page, window.loader.current_character_name, style, "character_w")
    _form_row(page, "Aktiver Charakter", window.settings_character_active_label, style)
    window.settings_character_combo = _combo(page, style, "character_w")
    window.settings_character_combo.currentIndexChanged.connect(window.on_settings_character_selection_changed)
    refresh_character_cache_list(window)
    _form_row(page, "Charakter auswählen", window.settings_character_combo, style)
    _actions(page, style,
        _button(window, page, "Auswahl laden", lambda: on_settings_load_selected_character_clicked(window), style),
        _button(window, page, "Datei laden", window.on_settings_load_character_clicked, style),
        _button(window, page, "Liste aktualisieren", window.on_settings_refresh_character_list_clicked, style))
    _actions(page, style, _button(window, page, "Charakterordner öffnen", lambda: _open_character_folder(window), style, wide=True))
    _note(page, "Speicherort: data/characters", style)
    _note(page, "Ältere Charaktere aus dem bisherigen Cache-Pfad werden weiterhin unterstützt.", style)
    return _finish_page(page)


def _build_roll20_page(window, parent, style):
    page = _page(parent, "ROLL20 / BROWSER", style)
    _section_title(page, "WÜRFELN", style)
    checkbox = _checkbox(window, page, "roll20_open_browser",
        bool(_settings_dict(window).get("roll20", {}).get("open_browser_on_roll", True)),
        lambda checked: _set_nested_setting(window, "roll20", "open_browser_on_roll", checked), style)
    _form_row(page, "Roll20 beim Wurf öffnen", checkbox, style)
    _section_title(page, "BROWSERPROFIL", style)
    _form_row(page, "Status", _value_label(page, "Persistentes Roll20-Profil aktiv", style, "path_w"), style)
    _form_row(page, "Profilpfad", _value_label(page, _browser_profile_display(window), style, "path_w"), style)
    return _finish_page(page)


def _build_debug_page(window, parent, style):
    page = _page(parent, "DEBUG & DATEN", style)
    _section_title(page, "DEBUG", style)
    _actions(page, style,
        _button(window, page, "Debug öffnen", window.open_debug_dialog, style),
        _button(window, page, "Berechnungen", window.open_calculation_center, style))
    checkbox = _checkbox(window, page, "debug_start", bool(getattr(window, "settings_debug_on_start", False)),
                         lambda checked: _set_debug_on_start(window, checked), style)
    _form_row(page, "Debug beim Start anzeigen", checkbox, style)
    _section_title(page, "DATEN", style)
    _actions(page, style, _button(window, page, "Cache neu laden", window.on_settings_cache_reload_clicked, style))
    return _finish_page(page)


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


def _checkbox(window, parent, key, checked, callback, style):
    cfg = style["config"].get("checkbox", {})
    size = int(cfg.get("size", 32))
    gap = int(cfg.get("spacing", 10))
    width = int(cfg.get("w", 120))
    container = QWidget(parent)
    container.setFixedSize(width, size)
    icon = QLabel(container)
    icon.setGeometry(0, 0, size, size)
    icon.setAlignment(Qt.AlignCenter)
    icon.setStyleSheet("background: transparent; border: none;")
    icon.setProperty("checked", bool(checked))
    text = _label(container, "Ein" if checked else "Aus", style)
    text.setGeometry(size + gap, 0, max(1, width - size - gap), size)
    click = QPushButton(container)
    click.setGeometry(0, 0, width, size)
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
        icon.setPixmap(pixmap.scaled(icon.width(), icon.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
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


def on_settings_load_selected_character_clicked(window):
    if window.settings_character_combo is None:
        return
    cache_path = window.settings_character_combo.currentData()
    if not isinstance(cache_path, str) or not cache_path:
        QMessageBox.warning(window, "Charakter laden", "Kein Charakter in der Liste ausgewählt.")
        return
    _load_character_cache_path(window, cache_path)


def _show_after_character_cache_load(window):
    current_section = str(getattr(window, "current_main_section", "") or "")
    if current_section in ("character", "skills", "fertigkeiten", "inventory", "equipment", "ausruestung", "ausrüstung", "magic", "notes"):
        if current_section in ("skills", "fertigkeiten"):
            window.show_main_section("skills")
        elif current_section in ("equipment", "ausruestung", "ausrüstung"):
            window.show_main_section("equipment")
        else:
            window.show_main_section(current_section)
        return

    startup = _settings_dict(window).get("startup", {})
    start_tab = str(startup.get("start_tab", "character") if isinstance(startup, dict) else "character")
    if start_tab not in START_TAB_LABELS:
        start_tab = "character"
    window.show_main_section(start_tab)


def _load_character_cache_path(window, cache_path):
    if hasattr(window.loader, "has_unsaved_changes") and window.loader.has_unsaved_changes():
        log_warning("character", "unsaved changes before switching character")
    ok = window.loader.load_character_cache(cache_path)
    if not ok:
        QMessageBox.warning(window, "Charakter laden", "Charakter-Cache konnte nicht geladen werden.")
        return False
    window.reset_character_runtime_state()
    if window.settings_character_active_label is not None:
        window.settings_character_active_label.setText(window.loader.current_character_name)
    window.create_tabs_from_cache()
    _show_after_character_cache_load(window)
    log_debug("cache", f"character cache loaded: {cache_path}")
    return True


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
    _load_character_cache_path(window, cache_path)


def on_settings_refresh_character_list_clicked(window):
    refresh_character_cache_list(window)
    log_debug("character", "cache list refreshed")
