from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QFrame, QPushButton, QTextEdit


def notes_debug_enabled(notes_layout):
    screen_cfg = notes_layout.get("notes_screen", {}) if isinstance(notes_layout, dict) else {}
    debug_cfg = screen_cfg.get("debug", {}) if isinstance(screen_cfg, dict) else {}
    return isinstance(debug_cfg, dict) and bool(debug_cfg.get("enabled", False))


def _optional_notes_ui_pixmap(parent, asset_rel_path):
    asset_name = str(asset_rel_path or "").strip()
    if not asset_name:
        return None
    try:
        window = parent.window()
        primary_base = getattr(window, "theme_asset_base_path", None)
        if primary_base is not None:
            primary = primary_base / asset_name
            if primary.exists():
                pixmap = QPixmap(str(primary))
                if not pixmap.isNull():
                    return pixmap
        assets_dir = getattr(window, "assets_dir", None)
        if assets_dir is not None:
            fallback = assets_dir / "themes" / "diablo" / "ui" / asset_name
            if fallback.exists():
                pixmap = QPixmap(str(fallback))
                if not pixmap.isNull():
                    return pixmap
    except Exception:
        return None
    return None


def _notes_frame_opacity(frame_cfg):
    try:
        opacity = float(frame_cfg.get("opacity", 1.0))
    except Exception:
        opacity = 1.0
    return max(0.0, min(1.0, opacity))


def _render_notes_fit_pixmap(src, target_w, target_h, frame_cfg):
    target_w = max(1, target_w)
    target_h = max(1, target_h)
    smooth_scaling = bool(frame_cfg.get("smooth_scaling", True))
    transform = Qt.SmoothTransformation if smooth_scaling else Qt.FastTransformation
    scaled = src.scaled(target_w, target_h, Qt.IgnoreAspectRatio, transform)

    rendered = QPixmap(target_w, target_h)
    rendered.fill(Qt.transparent)
    painter = QPainter(rendered)
    painter.setOpacity(_notes_frame_opacity(frame_cfg))
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return rendered


def _render_notes_nine_slice_pixmap(src, target_w, target_h, frame_cfg, safe_int):
    slice_cfg = frame_cfg.get("slice", {}) if isinstance(frame_cfg.get("slice", {}), dict) else {}
    src_w = max(1, src.width())
    src_h = max(1, src.height())
    left = max(0, min(safe_int(slice_cfg.get("left", 24), 24), src_w))
    right = max(0, min(safe_int(slice_cfg.get("right", 24), 24), src_w - left))
    top = max(0, min(safe_int(slice_cfg.get("top", 24), 24), src_h))
    bottom = max(0, min(safe_int(slice_cfg.get("bottom", 24), 24), src_h - top))

    target_w = max(1, target_w)
    target_h = max(1, target_h)
    if left + right > target_w:
        overflow = left + right - target_w
        shrink_left = min(left, overflow // 2)
        left -= shrink_left
        right = max(0, right - (overflow - shrink_left))
    if top + bottom > target_h:
        overflow = top + bottom - target_h
        shrink_top = min(top, overflow // 2)
        top -= shrink_top
        bottom = max(0, bottom - (overflow - shrink_top))

    smooth_scaling = bool(frame_cfg.get("smooth_scaling", True))
    opacity = _notes_frame_opacity(frame_cfg)
    center_src_w = max(0, src_w - left - right)
    center_src_h = max(0, src_h - top - bottom)
    center_dst_w = max(0, target_w - left - right)
    center_dst_h = max(0, target_h - top - bottom)

    rendered = QPixmap(target_w, target_h)
    rendered.fill(Qt.transparent)
    painter = QPainter(rendered)
    if smooth_scaling:
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setOpacity(opacity)

    def draw_slice(dx, dy, dw, dh, sx, sy, sw, sh):
        if dw <= 0 or dh <= 0 or sw <= 0 or sh <= 0:
            return
        painter.drawPixmap(dx, dy, dw, dh, src, sx, sy, sw, sh)

    draw_slice(0, 0, left, top, 0, 0, left, top)
    draw_slice(target_w - right, 0, right, top, src_w - right, 0, right, top)
    draw_slice(0, target_h - bottom, left, bottom, 0, src_h - bottom, left, bottom)
    draw_slice(target_w - right, target_h - bottom, right, bottom, src_w - right, src_h - bottom, right, bottom)
    draw_slice(left, 0, center_dst_w, top, left, 0, center_src_w, top)
    draw_slice(left, target_h - bottom, center_dst_w, bottom, left, src_h - bottom, center_src_w, bottom)
    draw_slice(0, top, left, center_dst_h, 0, top, left, center_src_h)
    draw_slice(target_w - right, top, right, center_dst_h, src_w - right, top, right, center_src_h)
    if bool(frame_cfg.get("draw_center", True)):
        draw_slice(left, top, center_dst_w, center_dst_h, left, top, center_src_w, center_src_h)
    painter.end()
    return rendered


def _create_notes_editor_frame(parent, editor_cfg, frame_cfg, safe_int):
    if not isinstance(frame_cfg, dict) or not bool(frame_cfg.get("enabled", False)):
        return False
    src = _optional_notes_ui_pixmap(parent, frame_cfg.get("asset", ""))
    if src is None:
        return False

    margin = max(0, safe_int(frame_cfg.get("margin", 0), 0))
    x = safe_int(editor_cfg.get("x", 20), 20) - margin
    y = safe_int(editor_cfg.get("y", 60), 60) - margin
    w = max(1, safe_int(editor_cfg.get("w", 1340), 1340) + margin * 2)
    h = max(1, safe_int(editor_cfg.get("h", 620), 620) + margin * 2)

    shadow_cfg = frame_cfg.get("shadow", {}) if isinstance(frame_cfg.get("shadow", {}), dict) else {}
    if bool(shadow_cfg.get("enabled", False)):
        shadow = QLabel(parent)
        shadow.setGeometry(
            x + safe_int(shadow_cfg.get("x", 3), 3),
            y + safe_int(shadow_cfg.get("y", 4), 4),
            w,
            h,
        )
        shadow.setStyleSheet(f"background: {str(shadow_cfg.get('color', 'rgba(0, 0, 0, 120)'))};")
        shadow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        shadow.show()
        shadow.lower()

    frame = QLabel(parent)
    frame.setGeometry(x, y, w, h)
    render_mode = str(frame_cfg.get("render_mode", "fit") or "fit").strip().lower()
    if render_mode == "nine_slice":
        frame.setPixmap(_render_notes_nine_slice_pixmap(src, w, h, frame_cfg, safe_int))
    else:
        frame.setPixmap(_render_notes_fit_pixmap(src, w, h, frame_cfg))
    frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    frame.show()
    return True


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
    frame_cfg = editor_cfg.get("frame", {}) if isinstance(editor_cfg.get("frame", {}), dict) else {}
    editor_frame_active = _create_notes_editor_frame(screen, editor_cfg, frame_cfg, safe_int)
    editor_border_style = "border: none;" if editor_frame_active and bool(frame_cfg.get("remove_editor_border_when_active", False)) else f"border: 1px solid {editor_border};"

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
        f"{editor_border_style}"
        f"color: {editor_text_color};"
        f"font-size: {editor_font_size}px;"
        "padding: 8px;"
        "}"
    )
    editor.show()
    editor.raise_()

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
