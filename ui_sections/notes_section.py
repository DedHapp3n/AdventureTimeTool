from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QFrame, QPushButton, QTextEdit


def notes_debug_enabled(notes_layout):
    screen_cfg = notes_layout.get("notes_screen", {}) if isinstance(notes_layout, dict) else {}
    debug_cfg = screen_cfg.get("debug", {}) if isinstance(screen_cfg, dict) else {}
    return isinstance(debug_cfg, dict) and bool(debug_cfg.get("enabled", False))


def render_notes_section(parent, layout_config, default_screen_cfg, callbacks=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    safe_int = callbacks.get("safe_int")
    if not callable(safe_int):
        safe_int = _safe_int
    create_panel_text = callbacks.get("create_panel_text")
    get_text = callbacks.get("get_text")
    save_text = callbacks.get("save_text")
    has_active_character = callbacks.get("has_active_character")
    log_debug = callbacks.get("log_debug")

    screen_cfg = layout_config.get("notes_screen", {}) if isinstance(layout_config, dict) else {}
    if not isinstance(screen_cfg, dict):
        screen_cfg = default_screen_cfg if isinstance(default_screen_cfg, dict) else {}
    notes_debug = notes_debug_enabled(layout_config)

    screen = QFrame(parent)
    screen.setGeometry(
        safe_int(screen_cfg.get("x", 40), 40),
        safe_int(screen_cfg.get("y", 40), 40),
        safe_int(screen_cfg.get("w", 1380), 1380),
        safe_int(screen_cfg.get("h", 790), 790),
    )
    screen.setStyleSheet("background: transparent;")
    screen.show()

    title_cfg = screen_cfg.get("title", {})
    if isinstance(title_cfg, dict) and bool(title_cfg.get("enabled", True)) and callable(create_panel_text):
        create_panel_text(
            screen,
            {
                "x": safe_int(title_cfg.get("x", 0), 0),
                "y": safe_int(title_cfg.get("y", 0), 0),
                "w": safe_int(title_cfg.get("w", 1380), 1380),
                "h": safe_int(title_cfg.get("h", 42), 42),
            },
            str(title_cfg.get("text", "Notizen")),
            safe_int(title_cfg.get("font_size", 24), 24),
            str(title_cfg.get("color", "#f2d28b")),
            bold=True,
            align=str(title_cfg.get("align", "center")),
        )

    editor_cfg = screen_cfg.get("editor", {})
    if not isinstance(editor_cfg, dict):
        editor_cfg = {}
    editor_x = safe_int(editor_cfg.get("x", 20), 20)
    editor_y = safe_int(editor_cfg.get("y", 60), 60)
    editor_w = safe_int(editor_cfg.get("w", 1340), 1340)
    editor_h = safe_int(editor_cfg.get("h", 620), 620)
    editor_font_size = safe_int(editor_cfg.get("font_size", 16), 16)
    editor_text_color = str(editor_cfg.get("text_color", "#ffffff"))
    editor_bg = str(editor_cfg.get("background", "rgba(5, 5, 5, 120)"))
    editor_border = str(editor_cfg.get("border_color", "rgba(242, 210, 139, 100)"))

    editor = QTextEdit(screen)
    editor.setGeometry(editor_x, editor_y, editor_w, editor_h)
    editor.setAcceptRichText(False)
    editor.setLineWrapMode(QTextEdit.WidgetWidth)
    editor.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    editor.setPlaceholderText(str(editor_cfg.get("placeholder", "Notizen...")))
    editor.setStyleSheet(
        "QTextEdit {"
        f"background: {editor_bg};"
        f"border: 1px solid {editor_border};"
        f"color: {editor_text_color};"
        f"font-size: {editor_font_size}px;"
        "padding: 8px;"
        "}"
    )
    editor.show()

    status_cfg = screen_cfg.get("status", {})
    status_label = None
    if isinstance(status_cfg, dict) and bool(status_cfg.get("enabled", True)):
        status_label = QLabel(screen)
        status_label.setGeometry(
            safe_int(status_cfg.get("x", 20), 20),
            safe_int(status_cfg.get("y", 700), 700),
            safe_int(status_cfg.get("w", 700), 700),
            safe_int(status_cfg.get("h", 32), 32),
        )
        status_label.setText("")
        status_label.setStyleSheet(
            "background: transparent; "
            f"color: {str(status_cfg.get('color', '#e8e0c8'))}; "
            f"font-size: {safe_int(status_cfg.get('font_size', 14), 14)}px;"
            "font-weight: 500;"
        )
        status_label.show()

    autosave_cfg = screen_cfg.get("autosave", {})
    if not isinstance(autosave_cfg, dict):
        autosave_cfg = {}
    autosave_enabled = bool(autosave_cfg.get("enabled", True))
    autosave_delay_ms = max(100, safe_int(autosave_cfg.get("delay_ms", 600), 600))

    autosave_timer = QTimer(screen)
    autosave_timer.setSingleShot(True)
    autosave_timer.setInterval(autosave_delay_ms)

    notes_text = get_text() if callable(get_text) else ""
    state = {
        "loading_text": True,
        "last_saved_text": str(notes_text),
    }
    try:
        editor.setPlainText(notes_text)
    finally:
        state["loading_text"] = False
    if notes_debug and callable(log_debug):
        log_debug("notes", f"NOTES LOAD chars={len(notes_text)}")

    if status_label is not None:
        status_label.setText("Automatisch gespeichert")

    def run_autosave():
        if state["loading_text"]:
            return
        if callable(has_active_character) and not has_active_character():
            if status_label is not None:
                status_label.setText("Kein Charakter geladen")
            return
        text_value = editor.toPlainText()
        if text_value == str(state["last_saved_text"]):
            if status_label is not None:
                status_label.setText("Automatisch gespeichert")
            return
        if notes_debug and callable(log_debug):
            log_debug("notes", f"NOTES AUTOSAVE chars={len(text_value)}")
        ok = save_text(text_value) if callable(save_text) else False
        if ok:
            state["last_saved_text"] = text_value
            if notes_debug and callable(log_debug):
                log_debug("notes", "NOTES SAVE active character saved")
            if status_label is not None:
                status_label.setText("Automatisch gespeichert")
        else:
            if status_label is not None:
                status_label.setText("Autosave fehlgeschlagen — siehe Terminal")

    autosave_timer.timeout.connect(run_autosave)

    def on_text_changed():
        if state["loading_text"]:
            return
        text_value = editor.toPlainText()
        if text_value == str(state["last_saved_text"]):
            return
        if status_label is not None:
            status_label.setText("Speichert...")
        if notes_debug and callable(log_debug):
            log_debug("notes", f"NOTES AUTOSAVE QUEUED chars={len(text_value)}")
        if autosave_enabled:
            autosave_timer.start()

    editor.textChanged.connect(on_text_changed)

    save_cfg = screen_cfg.get("save_button", {})
    if isinstance(save_cfg, dict) and bool(save_cfg.get("enabled", True)):
        save_button = QPushButton(screen)
        save_button.setGeometry(
            safe_int(save_cfg.get("x", 1120), 1120),
            safe_int(save_cfg.get("y", 700), 700),
            safe_int(save_cfg.get("w", 220), 220),
            safe_int(save_cfg.get("h", 44), 44),
        )
        save_button.setText(str(save_cfg.get("text", "Speichern")))
        save_button.setCursor(Qt.PointingHandCursor)
        save_button.setStyleSheet(
            "QPushButton {"
            "background-color: rgba(35, 24, 12, 185);"
            "color: #f2d28b;"
            "border: 1px solid rgba(184, 138, 53, 150);"
            "border-radius: 4px;"
            "font-size: 18px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { border: 1px solid #f2d28b; color: #ffffff; }"
        )

        def on_save_clicked():
            text_value = editor.toPlainText()
            if notes_debug and callable(log_debug):
                log_debug("notes", f"NOTES SAVE chars={len(text_value)}")
            ok = save_text(text_value) if callable(save_text) else False
            if ok:
                state["last_saved_text"] = text_value
                if notes_debug and callable(log_debug):
                    log_debug("notes", "NOTES SAVE active character saved")
                if status_label is not None:
                    status_label.setText("Automatisch gespeichert")
            else:
                if status_label is not None:
                    status_label.setText("Autosave fehlgeschlagen — siehe Terminal")

        save_button.clicked.connect(on_save_clicked)
        save_button.show()

    return screen


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)
