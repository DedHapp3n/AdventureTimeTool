from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QComboBox, QPushButton, QWidget

from app_logger import log_debug, log_error, log_warning


def render_settings_section(window):
    if window.content_layer is None:
        return
    settings_page = window.main_ui_layout_config.get("settings_page", {})
    default_text_style = window.theme_style.get("default_text", {})
    default_color = str(default_text_style.get("color", "#e8e0c8"))

    title_cfg = settings_page.get("title", {})
    title_text = str(title_cfg.get("text", "Settings"))
    title_x = int(title_cfg.get("x", 60))
    title_y = int(title_cfg.get("y", 40))
    title_w = int(title_cfg.get("w", 400))
    title_h = int(title_cfg.get("h", 50))
    title_font = int(title_cfg.get("font_size", 32))
    title_label = QLabel(window.content_layer)
    title_label.setGeometry(title_x, title_y, title_w, title_h)
    title_label.setText(title_text)
    title_label.setStyleSheet(
        f"background: transparent; color: {default_color}; font-size: {title_font}px; font-weight: 700;"
    )
    title_label.show()

    theme_section_title_cfg = settings_page.get("theme_section_title", {})
    theme_section_title = QLabel(window.content_layer)
    theme_section_title.setGeometry(
        int(theme_section_title_cfg.get("x", 100)),
        int(theme_section_title_cfg.get("y", 145)),
        int(theme_section_title_cfg.get("w", 300)),
        int(theme_section_title_cfg.get("h", 35)),
    )
    theme_section_title.setText(str(theme_section_title_cfg.get("text", "Theme")))
    theme_section_title.setStyleSheet(
        f"background: transparent; color: {default_color}; "
        f"font-size: {int(theme_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
    )
    theme_section_title.show()

    theme_label_cfg = settings_page.get("theme_label", {})
    theme_label_x = int(theme_label_cfg.get("x", 80))
    theme_label_y = int(theme_label_cfg.get("y", 120))
    theme_label_w = int(theme_label_cfg.get("w", 420))
    theme_label_h = int(theme_label_cfg.get("h", 40))
    theme_label_font = int(theme_label_cfg.get("font_size", 22))
    theme_text_prefix = str(theme_label_cfg.get("text", "Aktuelles Theme"))
    window.settings_theme_label = QLabel(window.content_layer)
    window.settings_theme_label.setGeometry(theme_label_x, theme_label_y, theme_label_w, theme_label_h)
    window.settings_theme_label.setText(theme_text_prefix)
    window.settings_theme_label.setStyleSheet(
        f"background: transparent; color: {default_color}; font-size: {theme_label_font}px; font-weight: 500;"
    )
    window.settings_theme_label.show()

    theme_value_cfg = settings_page.get("theme_value", {})
    theme_value_x = int(theme_value_cfg.get("x", theme_label_x + 210))
    theme_value_y = int(theme_value_cfg.get("y", theme_label_y))
    theme_value_w = int(theme_value_cfg.get("w", 260))
    theme_value_h = int(theme_value_cfg.get("h", theme_label_h))
    window.settings_theme_value_label = QLabel(window.content_layer)
    window.settings_theme_value_label.setGeometry(theme_value_x, theme_value_y, theme_value_w, theme_value_h)
    window.settings_theme_value_label.setText(window.get_active_theme())
    window.settings_theme_value_label.setStyleSheet(
        f"background: transparent; color: {default_color}; "
        f"font-size: {int(theme_value_cfg.get('font_size', theme_label_font))}px; font-weight: 600;"
    )
    window.settings_theme_value_label.show()

    window.create_asset_text_button(
        window.content_layer,
        settings_page.get("theme_switch_button", {}),
        "Theme wechseln",
        window.on_settings_switch_theme_clicked,
    )

    character_section_title_cfg = settings_page.get("character_section_title", {})
    character_section_y = int(character_section_title_cfg.get("y", 330))
    character_title = QLabel(window.content_layer)
    character_title.setGeometry(
        int(character_section_title_cfg.get("x", 100)),
        character_section_y,
        int(character_section_title_cfg.get("w", 300)),
        int(character_section_title_cfg.get("h", 35)),
    )
    character_title.setText(str(character_section_title_cfg.get("text", "Charakter")))
    character_title.setStyleSheet(
        f"background: transparent; color: {default_color}; "
        f"font-size: {int(character_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
    )
    character_title.show()

    active_character_label_cfg = settings_page.get("active_character_label", {})
    active_prefix = QLabel(window.content_layer)
    active_prefix.setGeometry(
        int(active_character_label_cfg.get("x", 110)),
        int(active_character_label_cfg.get("y", character_section_y + 44)),
        int(active_character_label_cfg.get("w", 220)),
        int(active_character_label_cfg.get("h", 32)),
    )
    active_prefix.setText(str(active_character_label_cfg.get("text", "Aktiver Charakter:")))
    active_prefix.setStyleSheet(
        f"background: transparent; color: {default_color}; "
        f"font-size: {int(active_character_label_cfg.get('font_size', 18))}px; font-weight: 500;"
    )
    active_prefix.show()

    active_character_value_cfg = settings_page.get("active_character_value", {})
    window.settings_character_active_label = QLabel(window.content_layer)
    window.settings_character_active_label.setGeometry(
        int(active_character_value_cfg.get("x", 320)),
        int(active_character_value_cfg.get("y", character_section_y + 44)),
        int(active_character_value_cfg.get("w", 420)),
        int(active_character_value_cfg.get("h", 32)),
    )
    window.settings_character_active_label.setText(window.loader.current_character_name)
    window.settings_character_active_label.setStyleSheet(
        f"background: transparent; color: {default_color}; "
        f"font-size: {int(active_character_value_cfg.get('font_size', 18))}px; font-weight: 600;"
    )
    window.settings_character_active_label.show()

    character_select_cfg = settings_page.get("character_select", {})
    select_x = int(character_select_cfg.get("x", 80))
    select_y = int(character_select_cfg.get("y", character_section_y + 88))
    select_w = int(character_select_cfg.get("w", 620))
    select_h = int(character_select_cfg.get("h", 36))
    nav_style = window.theme_style.get("nav_button", {})
    combo_text_color = str(nav_style.get("active_color", default_color))

    window.settings_character_combo = QComboBox(window.content_layer)
    window.settings_character_combo.setGeometry(select_x, select_y, select_w, select_h)
    window.settings_character_combo.setStyleSheet(
        "QComboBox {"
        "background-color: rgba(10, 10, 10, 180);"
        f"color: {combo_text_color};"
        "border: 1px solid #8a6a32;"
        "padding-left: 8px;"
        "padding-right: 24px;"
        "}"
        "QComboBox::drop-down {"
        "subcontrol-origin: padding;"
        "subcontrol-position: top right;"
        "width: 20px;"
        "border-left: 1px solid #8a6a32;"
        "background: rgba(30, 20, 10, 180);"
        "}"
        "QComboBox QAbstractItemView {"
        "background-color: rgba(10, 10, 10, 220);"
        f"color: {combo_text_color};"
        "selection-background-color: rgba(80, 60, 30, 180);"
        "border: 1px solid #8a6a32;"
        "}"
    )
    window.settings_character_combo.show()
    window.settings_character_combo.currentIndexChanged.connect(window.on_settings_character_selection_changed)
    refresh_character_cache_list(window)

    window.create_asset_text_button(
        window.content_layer,
        settings_page.get("character_load_button", {}),
        "Charakter laden",
        window.on_settings_load_character_clicked,
    )

    window.create_asset_text_button(
        window.content_layer,
        settings_page.get("character_refresh_button", {}),
        "Liste aktualisieren",
        window.on_settings_refresh_character_list_clicked,
    )

    debug_section_title_cfg = settings_page.get("debug_section_title", {})
    debug_section_title = QLabel(window.content_layer)
    debug_section_title.setGeometry(
        int(debug_section_title_cfg.get("x", 100)),
        int(debug_section_title_cfg.get("y", 570)),
        int(debug_section_title_cfg.get("w", 300)),
        int(debug_section_title_cfg.get("h", 35)),
    )
    debug_section_title.setText(str(debug_section_title_cfg.get("text", "Debug")))
    debug_section_title.setStyleSheet(
        f"background: transparent; color: {default_color}; "
        f"font-size: {int(debug_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
    )
    debug_section_title.show()

    window.create_asset_text_button(
        window.content_layer,
        settings_page.get("debug_button", {}),
        "Debug öffnen",
        window.open_debug_dialog,
    )
    window.create_asset_text_button(
        window.content_layer,
        settings_page.get("calculation_center_button", {}),
        "Berechnungen",
        window.open_calculation_center,
    )

    checkbox_cfg = settings_page.get("checkbox_debug_start", {})
    cb_x = int(checkbox_cfg.get("x", 80))
    cb_y = int(checkbox_cfg.get("y", 300))
    cb_w = int(checkbox_cfg.get("w", 50))
    cb_h = int(checkbox_cfg.get("h", 50))
    cb_text = str(checkbox_cfg.get("text", "Debug beim Start anzeigen"))
    window._settings_checkbox_asset_true = str(checkbox_cfg.get("asset_true", "icons/checkmark_true.png"))
    window._settings_checkbox_asset_false = str(checkbox_cfg.get("asset_false", "icons/checkmark_false.png"))

    checkbox_container = QWidget(window.content_layer)
    checkbox_container.setGeometry(cb_x, cb_y, 700, max(50, cb_h))

    window.settings_checkbox_icon_label = QLabel(checkbox_container)
    window.settings_checkbox_icon_label.setGeometry(0, 0, cb_w, cb_h)
    window.settings_checkbox_icon_label.setStyleSheet("background: transparent;")

    window.settings_checkbox_text_label = QLabel(checkbox_container)
    window.settings_checkbox_text_label.setGeometry(cb_w + 16, 0, 620, cb_h)
    window.settings_checkbox_text_label.setText(cb_text)
    window.settings_checkbox_text_label.setStyleSheet(
        f"background: transparent; color: {default_color}; font-size: 20px; font-weight: 500;"
    )

    click_overlay = QPushButton(checkbox_container)
    click_overlay.setGeometry(0, 0, 700, max(50, cb_h))
    click_overlay.setText("")
    click_overlay.setCursor(Qt.PointingHandCursor)
    click_overlay.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0px; }")
    click_overlay.clicked.connect(window.on_settings_debug_start_toggled)
    click_overlay.raise_()
    checkbox_container.show()

    data_section_title_cfg = settings_page.get("data_section_title", {})
    data_section_title = QLabel(window.content_layer)
    data_section_title.setGeometry(
        int(data_section_title_cfg.get("x", 100)),
        int(data_section_title_cfg.get("y", 785)),
        int(data_section_title_cfg.get("w", 300)),
        int(data_section_title_cfg.get("h", 35)),
    )
    data_section_title.setText(str(data_section_title_cfg.get("text", "Daten")))
    data_section_title.setStyleSheet(
        f"background: transparent; color: {default_color}; "
        f"font-size: {int(data_section_title_cfg.get('font_size', 24))}px; font-weight: 700;"
    )
    data_section_title.show()

    window.create_asset_text_button(
        window.content_layer,
        settings_page.get("reload_cache_button", {}),
        "Cache neu laden",
        window.on_settings_cache_reload_clicked,
    )

    update_settings_checkbox_icon(window)


def update_settings_checkbox_icon(window):
    if window.settings_checkbox_icon_label is None:
        return
    asset = (
        window._settings_checkbox_asset_true
        if window.settings_debug_on_start
        else window._settings_checkbox_asset_false
    )
    pixmap = window.load_ui_pixmap(asset)
    if pixmap is not None:
        w = window.settings_checkbox_icon_label.width()
        h = window.settings_checkbox_icon_label.height()
        window.settings_checkbox_icon_label.setPixmap(
            pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        )
    else:
        fallback = "☑" if window.settings_debug_on_start else "☐"
        window.settings_checkbox_icon_label.setText(fallback)
        window.settings_checkbox_icon_label.setStyleSheet(
            "background: transparent; color: #ffffff; font-size: 28px;"
        )


def on_settings_debug_start_toggled(window):
    window.settings_debug_on_start = not window.settings_debug_on_start
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
    elif window.current_main_section == "magic":
        window.show_main_section("magic")
    elif window.current_main_section == "notes":
        window.show_main_section("notes")
    log_debug("cache", f"character cache loaded: {cache_path}")


def on_settings_refresh_character_list_clicked(window):
    refresh_character_cache_list(window)
    log_debug("character", "cache list refreshed")
