from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QAbstractItemView, QFrame, QPushButton, QTableWidget, QTableWidgetItem

from app_logger import log_debug, log_error, log_warning


def _optional_equipment_ui_pixmap(window, asset_rel_path):
    asset_name = str(asset_rel_path or "").strip()
    if not asset_name:
        return None
    try:
        primary = window.theme_asset_base_path / asset_name
        if primary.exists():
            pixmap = QPixmap(str(primary))
            if not pixmap.isNull():
                return pixmap
        fallback = window.assets_dir / "themes" / "diablo" / "ui" / asset_name
        if fallback.exists():
            pixmap = QPixmap(str(fallback))
            if not pixmap.isNull():
                return pixmap
    except Exception:
        return None
    return None


def _optional_equipment_ui_asset_path(window, asset_rel_path):
    asset_name = str(asset_rel_path or "").strip()
    if not asset_name:
        return None
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


def _equipment_frame_opacity(frame_cfg):
    try:
        opacity = float(frame_cfg.get("opacity", 1.0))
    except Exception:
        opacity = 1.0
    return max(0.0, min(1.0, opacity))


def _render_equipment_fit_pixmap(src, target_w, target_h, frame_cfg):
    target_w = max(1, target_w)
    target_h = max(1, target_h)
    smooth_scaling = bool(frame_cfg.get("smooth_scaling", True))
    keep_aspect = bool(frame_cfg.get("keep_aspect", True))
    fit_mode = str(frame_cfg.get("fit_mode", "contain") or "contain").strip().lower()
    transform = Qt.SmoothTransformation if smooth_scaling else Qt.FastTransformation
    aspect_mode = Qt.KeepAspectRatio if keep_aspect and fit_mode != "stretch" else Qt.IgnoreAspectRatio
    scaled = src.scaled(target_w, target_h, aspect_mode, transform)

    rendered = QPixmap(target_w, target_h)
    rendered.fill(Qt.transparent)
    painter = QPainter(rendered)
    painter.setOpacity(_equipment_frame_opacity(frame_cfg))
    dx = int((target_w - scaled.width()) / 2) if keep_aspect and fit_mode != "stretch" else 0
    dy = int((target_h - scaled.height()) / 2) if keep_aspect and fit_mode != "stretch" else 0
    painter.drawPixmap(dx, dy, scaled)
    painter.end()
    return rendered


def _render_equipment_nine_slice_pixmap(window, src, target_w, target_h, frame_cfg):
    slice_cfg = frame_cfg.get("slice", {}) if isinstance(frame_cfg.get("slice", {}), dict) else {}
    src_w = max(1, src.width())
    src_h = max(1, src.height())
    left = max(0, min(window._safe_int(slice_cfg.get("left", 24), 24), src_w))
    right = max(0, min(window._safe_int(slice_cfg.get("right", 24), 24), src_w - left))
    top = max(0, min(window._safe_int(slice_cfg.get("top", 24), 24), src_h))
    bottom = max(0, min(window._safe_int(slice_cfg.get("bottom", 24), 24), src_h - top))

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
    opacity = _equipment_frame_opacity(frame_cfg)
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


def _create_equipment_shadow(window, parent, rect_cfg, shadow_cfg):
    if not isinstance(shadow_cfg, dict) or not bool(shadow_cfg.get("enabled", False)):
        return None
    x = window._safe_int(rect_cfg.get("x", 0), 0)
    y = window._safe_int(rect_cfg.get("y", 0), 0)
    w = max(1, window._safe_int(rect_cfg.get("w", 1), 1))
    h = max(1, window._safe_int(rect_cfg.get("h", 1), 1))
    shadow_x = window._safe_int(shadow_cfg.get("x", 3), 3)
    shadow_y = window._safe_int(shadow_cfg.get("y", 4), 4)
    shadow_color = str(shadow_cfg.get("color", "rgba(0, 0, 0, 120)"))
    shadow = QLabel(parent)
    shadow.setGeometry(x + shadow_x, y + shadow_y, w, h)
    shadow.setStyleSheet(f"background: {shadow_color}; border: none;")
    shadow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    shadow.show()
    return shadow


def _create_equipment_frame_label(window, parent, frame_cfg, rect_cfg, raise_frame=False):
    if not isinstance(frame_cfg, dict) or not bool(frame_cfg.get("enabled", False)):
        return None
    src = _optional_equipment_ui_pixmap(window, frame_cfg.get("asset", ""))
    if src is None:
        return None
    x = window._safe_int(rect_cfg.get("x", 0), 0)
    y = window._safe_int(rect_cfg.get("y", 0), 0)
    w = max(1, window._safe_int(rect_cfg.get("w", 1), 1))
    h = max(1, window._safe_int(rect_cfg.get("h", 1), 1))
    shadow_label = _create_equipment_shadow(
        window,
        parent,
        {"x": x, "y": y, "w": w, "h": h},
        frame_cfg.get("shadow", {}) if isinstance(frame_cfg.get("shadow", {}), dict) else {},
    )
    label = QLabel(parent)
    label.setGeometry(x, y, w, h)
    render_mode = str(frame_cfg.get("render_mode", "fit") or "fit").strip().lower()
    if render_mode == "nine_slice":
        label.setPixmap(_render_equipment_nine_slice_pixmap(window, src, w, h, frame_cfg))
    else:
        label.setPixmap(_render_equipment_fit_pixmap(src, w, h, frame_cfg))
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    label.show()
    if raise_frame:
        if shadow_label is not None:
            shadow_label.raise_()
        label.raise_()
    return label


def _apply_equipment_panel_frame_if_enabled(window, parent, panel_cfg, rect_cfg):
    frame_cfg = panel_cfg.get("frame", {}) if isinstance(panel_cfg, dict) else {}
    label = _create_equipment_frame_label(window, parent, frame_cfg, rect_cfg)
    return {
        "active": label is not None,
        "remove_old_border_when_active": bool(frame_cfg.get("remove_old_border_when_active", True)) if isinstance(frame_cfg, dict) else True,
        "transparent_panel_background_when_active": bool(frame_cfg.get("transparent_panel_background_when_active", True)) if isinstance(frame_cfg, dict) else True,
        "fallback_border": bool(frame_cfg.get("fallback_border", True)) if isinstance(frame_cfg, dict) else True,
    }


def _create_equipment_framed_title(window, parent, panel_cfg, panel_w, title_text, font_size, color):
    title_frame_cfg = panel_cfg.get("title_frame", {}) if isinstance(panel_cfg, dict) else {}
    if not isinstance(title_frame_cfg, dict) or not bool(title_frame_cfg.get("enabled", False)):
        return None
    x = window._safe_int(title_frame_cfg.get("x", 10), 10)
    y = window._safe_int(title_frame_cfg.get("y", 8), 8)
    w = max(1, window._safe_int(title_frame_cfg.get("w", panel_w - 20), panel_w - 20))
    h = max(1, window._safe_int(title_frame_cfg.get("h", 32), 32))
    w = min(w, max(1, panel_w - x))
    align = str(title_frame_cfg.get("align", "left") or "left").strip().lower()
    text_padding_x = window._safe_int(title_frame_cfg.get("text_padding_x", 8), 8)
    text_x = x + text_padding_x if align == "left" else x
    text_w = max(1, w - (text_padding_x * 2 if align == "left" else 0))
    frame_cfg = dict(title_frame_cfg)
    _create_equipment_frame_label(window, parent, frame_cfg, {"x": x, "y": y, "w": w, "h": h})
    label = window.create_panel_text(
        parent,
        {"x": text_x, "y": y, "w": text_w, "h": h},
        title_text,
        font_size,
        color,
        bold=True,
        align=align,
    )
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    label.raise_()
    return label


def on_equipment_category_clicked(window, category_id):
    category = str(category_id or "").strip()
    if category not in {"armor", "weapons"}:
        category = "armor"
    window.current_equipment_category = category
    window.show_main_section("equipment")


def render_equipment_category_tabs(window, parent, screen_cfg):
    tabs_cfg = screen_cfg.get("category_tabs", {}) if isinstance(screen_cfg, dict) else {}
    if not isinstance(tabs_cfg, dict) or not bool(tabs_cfg.get("enabled", True)):
        return

    x = window._safe_int(tabs_cfg.get("x", 20), 20)
    y = window._safe_int(tabs_cfg.get("y", 10), 10)
    w = max(1, window._safe_int(tabs_cfg.get("w", 520), 520))
    h = max(1, window._safe_int(tabs_cfg.get("h", 50), 50))
    button_w = max(1, window._safe_int(tabs_cfg.get("button_w", 220), 220))
    button_h = max(1, window._safe_int(tabs_cfg.get("button_h", 42), 42))
    gap = window._safe_int(tabs_cfg.get("gap", 18), 18)
    font_size = window._safe_int(tabs_cfg.get("font_size", 20), 20)
    active_color = str(tabs_cfg.get("active_color", "#f2d28b"))
    inactive_color = str(tabs_cfg.get("inactive_color", "#9a8560"))
    default_asset = str(tabs_cfg.get("asset", "buttons/menu_button_medium.png") or "").strip()
    active_asset = str(tabs_cfg.get("active_asset", default_asset) or "").strip()
    inactive_asset = str(tabs_cfg.get("inactive_asset", default_asset) or "").strip()

    tabs = QFrame(parent)
    tabs.setGeometry(x, y, w, h)
    tabs.setStyleSheet("background: transparent; border: none;")
    tabs.show()

    categories = [("armor", "Ausrüstung"), ("weapons", "Waffen")]
    active_category = str(getattr(window, "current_equipment_category", "armor") or "armor")
    shadow_cfg = tabs_cfg.get("shadow", {}) if isinstance(tabs_cfg.get("shadow", {}), dict) else {}
    for index, (category_id, title) in enumerate(categories):
        is_active = category_id == active_category
        button_x = index * (button_w + gap)
        if bool(shadow_cfg.get("enabled", False)):
            shadow = QLabel(tabs)
            shadow.setGeometry(
                button_x + window._safe_int(shadow_cfg.get("x", 2), 2),
                window._safe_int(shadow_cfg.get("y", 3), 3),
                button_w,
                button_h,
            )
            shadow.setStyleSheet(
                f"background: {str(shadow_cfg.get('color', 'rgba(0, 0, 0, 120)'))}; border: none;"
            )
            shadow.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            shadow.show()

        asset = active_asset if is_active else inactive_asset
        asset_path = _optional_equipment_ui_asset_path(window, asset)
        button = QPushButton(tabs)
        button.setGeometry(button_x, 0, button_w, button_h)
        button.setText(title)
        button.setCursor(Qt.PointingHandCursor)
        color = active_color if is_active else inactive_color
        if asset_path is not None:
            background_style = f"border-image: url({asset_path.as_posix()}) 0 0 0 0 stretch stretch;"
        else:
            background_style = "background: rgba(5, 5, 5, 110);"
        button.setStyleSheet(
            "QPushButton {"
            f"{background_style}"
            "border: none;"
            f"color: {color};"
            f"font-size: {font_size}px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
            f"QPushButton:hover {{ color: {active_color}; }}"
        )
        button.clicked.connect(lambda checked=False, cid=category_id: on_equipment_category_clicked(window, cid))
        button.show()


def render_equipment_section(window, parent, layout_config):
    window._equipment_table_bindings = {}
    screen_cfg = layout_config.get("equipment_screen", {}) if isinstance(layout_config, dict) else {}
    if str(getattr(window, "current_equipment_category", "") or "") not in {"armor", "weapons"}:
        window.current_equipment_category = "armor"
    screen = QFrame(parent)
    screen.setGeometry(
        window._safe_int(screen_cfg.get("x", 20), 20),
        window._safe_int(screen_cfg.get("y", 20), 20),
        window._safe_int(screen_cfg.get("w", 1420), 1420),
        window._safe_int(screen_cfg.get("h", 820), 820),
    )
    screen.setStyleSheet("background: transparent;")
    screen.show()

    title_cfg = screen_cfg.get("title", {})
    if bool(screen_cfg.get("show_title", False)):
        window.create_panel_text(
            screen,
            title_cfg,
            str(title_cfg.get("text", "Ausrüstung")),
            window._safe_int(title_cfg.get("font_size", 24), 24),
            str(title_cfg.get("color", "#f2d28b")),
            bold=True,
            align=str(title_cfg.get("align", "center")),
        )
    debug_cfg = screen_cfg.get("debug", {})
    if not isinstance(debug_cfg, dict):
        debug_cfg = {}
    if bool(debug_cfg.get("enabled", True)) and (
        bool(screen_cfg.get("show_debug_label", False)) or bool(debug_cfg.get("show_label", False))
    ):
        window.create_panel_text(
            screen,
            {"x": 20, "y": 70, "w": 700, "h": 30},
            "Ausrüstung Analyse - siehe Terminal",
            16,
            "#e8e0c8",
            bold=False,
            align="left",
        )
    render_equipment_category_tabs(window, screen, screen_cfg)
    analysis = window.analyze_equipment_sheet()
    if not isinstance(analysis, dict):
        analysis = {}
    armor_block = analysis.get("armor", {}) if isinstance(analysis, dict) else {}
    armor_rows = armor_block.get("rows", []) if isinstance(armor_block, dict) else []
    if not isinstance(armor_rows, list):
        armor_rows = []
    weapons_block = analysis.get("weapons", {}) if isinstance(analysis, dict) else {}
    weapon_rows = weapons_block.get("rows", []) if isinstance(weapons_block, dict) else []
    if not isinstance(weapon_rows, list):
        weapon_rows = []

    if window.current_equipment_category == "weapons":
        try:
            render_equipment_weapons_table(window, screen, screen_cfg.get("weapons", {}), weapon_rows)
        except Exception as exc:
            log_error("equipment", f"weapon render failed: {exc}")
            window.create_panel_text(
                screen,
                {"x": 20, "y": 150, "w": 760, "h": 32},
                "Waffen konnten nicht gerendert werden - siehe Terminal",
                16,
                "#e8e0c8",
                bold=False,
                align="left",
            )
    else:
        try:
            render_equipment_armor_table(window, screen, screen_cfg.get("armor", {}), armor_rows)
        except Exception as exc:
            log_error("equipment", f"armor render failed: {exc}")
            window.create_panel_text(
                screen,
                {"x": 20, "y": 150, "w": 760, "h": 32},
                "Rüstung konnte nicht gerendert werden - siehe Terminal",
                16,
                "#e8e0c8",
                bold=False,
                align="left",
            )

        if not armor_rows:
            window.create_panel_text(
                screen,
                {"x": 20, "y": 410, "w": 700, "h": 30},
                "Keine Rüstungsdaten gefunden",
                16,
                "#e8e0c8",
                bold=False,
                align="left",
            )
    return screen


def equipment_summary_int(value):
    text = str(value or "").strip()
    if not text or text in {"-", "/"}:
        return 0
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def build_armor_summary_row(window, armor_rows):
    summary_fields = [
        "phys_head",
        "phys_chest",
        "phys_arms",
        "phys_legs",
        "fire",
        "water",
        "earth",
        "wind",
        "lightning",
        "ice",
        "acid",
        "light",
        "dark",
    ]
    summary_row = {
        "slot": "",
        "name": "Summe",
        "pl": "",
        "durability_current": "",
        "durability_max": "",
        "attributes": "",
    }
    # Summary stays runtime-only; no equipment values are written back in phase 5.2.x.
    for field_key in summary_fields:
        total = 0
        for row_data in armor_rows:
            if isinstance(row_data, dict):
                total += equipment_summary_int(row_data.get(field_key, ""))
        summary_row[field_key] = str(total)
    if window._equipment_print_rows_enabled():
        log_debug("equipment", "EQUIPMENT ARMOR SUMMARY " + " ".join(f"{field}={summary_row.get(field, '0')}" for field in summary_fields))
    return summary_row


def get_equipment_table_edit_settings(window, table_cfg):
    if not isinstance(table_cfg, dict):
        table_cfg = {}
    edit_cfg = table_cfg.get("edit", {})
    if not isinstance(edit_cfg, dict):
        edit_cfg = {}
    editable = bool(table_cfg.get("editable", False)) and bool(edit_cfg.get("enabled", True))
    save_on_cell_change = bool(edit_cfg.get("save_on_cell_change", True))
    debug_enabled = bool(edit_cfg.get("debug", True)) and window._equipment_debug_enabled()
    return editable, save_on_cell_change, debug_enabled


def apply_equipment_item_editability(item, editable):
    if item is None:
        return
    if editable:
        item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
    else:
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setFlags(item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)


def _equipment_row_is_empty(row_data, meaningful_fields):
    if not isinstance(row_data, dict):
        return True
    for field_key in meaningful_fields:
        if str(row_data.get(field_key, "") or "").strip():
            return False
    return True


def _equipment_dynamic_rows_config(window, table_cfg, fallback_min_rows):
    dynamic_cfg = table_cfg.get("dynamic_rows", {}) if isinstance(table_cfg, dict) else {}
    if not isinstance(dynamic_cfg, dict):
        dynamic_cfg = {}
    enabled = bool(dynamic_cfg.get("enabled", False))
    min_rows = window._safe_int(dynamic_cfg.get("min_rows", fallback_min_rows), fallback_min_rows)
    grow_by = window._safe_int(dynamic_cfg.get("grow_by", 3), 3)
    trigger_remaining = window._safe_int(dynamic_cfg.get("trigger_empty_rows_remaining", 1), 1)
    scan_extra_mapped_rows = window._safe_int(dynamic_cfg.get("scan_extra_mapped_rows", 0), 0)
    return {
        "enabled": enabled,
        "min_rows": max(0, min_rows),
        "grow_by": max(1, grow_by),
        "trigger_empty_rows_remaining": max(0, trigger_remaining),
        "trim_trailing_empty": bool(dynamic_cfg.get("trim_trailing_empty", True)),
        "scan_extra_mapped_rows": max(0, scan_extra_mapped_rows),
    }


def _equipment_last_non_empty_row_index(rows, meaningful_fields):
    if not isinstance(rows, list):
        return -1
    for row_index in range(len(rows) - 1, -1, -1):
        if not _equipment_row_is_empty(rows[row_index], meaningful_fields):
            return row_index
    return -1


def _equipment_dynamic_state(window):
    state = getattr(window, "_equipment_dynamic_visible_rows", None)
    if not isinstance(state, dict):
        state = {}
        window._equipment_dynamic_visible_rows = state
    return state


def _equipment_visible_data_row_count(window, table_type, rows, meaningful_fields, dynamic_cfg):
    min_rows = int(dynamic_cfg.get("min_rows", 0))
    last_non_empty = _equipment_last_non_empty_row_index(rows, meaningful_fields)
    trigger_remaining = int(dynamic_cfg.get("trigger_empty_rows_remaining", 1))
    base_count = max(min_rows, last_non_empty + 1 + trigger_remaining)
    max_safe_display = max(min_rows, len(rows) if isinstance(rows, list) else 0)
    state = _equipment_dynamic_state(window)
    state_count = state.get(table_type)
    try:
        visible_count = int(state_count)
    except Exception:
        visible_count = base_count
    visible_count = max(base_count, min(visible_count, max_safe_display))
    state[table_type] = visible_count
    return visible_count


def _adjust_equipment_dynamic_rows_after_edit(window, binding):
    dynamic_cfg = binding.get("dynamic_rows", {})
    if not isinstance(dynamic_cfg, dict) or not bool(dynamic_cfg.get("enabled", False)):
        return False
    table_type = str(binding.get("table_type", ""))
    rows = binding.get("rows", [])
    if not isinstance(rows, list):
        return False
    meaningful_fields = binding.get("meaningful_fields", [])
    if not isinstance(meaningful_fields, list):
        meaningful_fields = []
    current_count = int(binding.get("visible_data_row_count", len(rows)))
    min_rows = int(dynamic_cfg.get("min_rows", 12))
    grow_by = int(dynamic_cfg.get("grow_by", 3))
    trigger_remaining = int(dynamic_cfg.get("trigger_empty_rows_remaining", 1))
    max_safe_display = max(min_rows, len(rows))
    mapped_visible_count = min(current_count, len(rows))
    last_non_empty = _equipment_last_non_empty_row_index(rows[:mapped_visible_count], meaningful_fields)
    filled_count = last_non_empty + 1
    empty_remaining = max(0, mapped_visible_count - filled_count)
    desired_count = current_count
    if empty_remaining < trigger_remaining and current_count < max_safe_display:
        desired_count = min(max_safe_display, current_count + grow_by)
    elif bool(dynamic_cfg.get("trim_trailing_empty", True)):
        spare_after_data = grow_by + trigger_remaining
        trim_threshold = max(min_rows, filled_count + spare_after_data)
        if current_count > trim_threshold:
            desired_count = max(min_rows, filled_count + trigger_remaining)
    desired_count = max(min_rows, min(desired_count, max_safe_display))
    if desired_count == current_count:
        return False
    state = _equipment_dynamic_state(window)
    state[table_type] = desired_count
    return True


def _log_equipment_dynamic_rows(window, table_type, rows, meaningful_fields, visible_data_row_count, dynamic_cfg):
    if not window._equipment_debug_enabled():
        return
    if not isinstance(rows, list):
        rows = []
    filled = sum(1 for row_data in rows if not _equipment_row_is_empty(row_data, meaningful_fields))
    mapped_empty = sum(1 for row_data in rows if _equipment_row_is_empty(row_data, meaningful_fields))
    min_rows = int(dynamic_cfg.get("min_rows", 0))
    grow_by = int(dynamic_cfg.get("grow_by", 3))
    trigger_remaining = int(dynamic_cfg.get("trigger_empty_rows_remaining", 1))
    max_safe_display = max(min_rows, len(rows))
    growth_possible = visible_data_row_count < len(rows)
    reason = "" if growth_possible else " reason=no_extra_mapped_rows"
    filler_note = " filler_rows_non_editable=True" if visible_data_row_count > len(rows) else ""
    log_debug(
        "equipment",
        f"EQUIPMENT DYNAMIC {table_type} analyzed={len(rows)} filled={filled} "
        f"mapped_empty={mapped_empty} visible={visible_data_row_count} min_rows={min_rows} "
        f"grow_by={grow_by} trigger_empty_rows_remaining={trigger_remaining} "
        f"max_safe_display={max_safe_display} growth_possible={growth_possible}{reason}{filler_note}",
    )


def refresh_armor_summary_table_row(window, table):
    binding = window._equipment_table_bindings.get(id(table), {})
    if not isinstance(binding, dict):
        return
    rows = binding.get("rows", [])
    summary_row_index = int(binding.get("summary_row_index", -1))
    if summary_row_index < 0 or summary_row_index >= table.rowCount():
        return
    summary_row = build_armor_summary_row(window, rows)
    summary_row["name"] = str(binding.get("summary_label", "Summe"))
    binding["summary_row"] = summary_row
    window._equipment_table_bindings[id(table)] = binding
    table.blockSignals(True)
    try:
        for col_index, (field_key, _) in enumerate(binding.get("column_order", [])):
            item = table.item(summary_row_index, col_index)
            if item is None:
                continue
            value = str(summary_row.get(field_key, "") or "").strip()
            item.setText(value)
            item.setToolTip(value if value else "")
            item.setData(Qt.UserRole, value)
    finally:
        table.blockSignals(False)


def on_equipment_table_item_changed(window, table, row_index, column_index):
    if window._equipment_rendering:
        return
    binding = window._equipment_table_bindings.get(id(table), {})
    if not isinstance(binding, dict):
        return
    if not bool(binding.get("save_on_cell_change", True)):
        return
    summary_row_index = int(binding.get("summary_row_index", -1))
    if row_index == summary_row_index:
        return
    data_row_offset = int(binding.get("data_row_offset", 0))
    data_row_index = row_index - data_row_offset
    rows = binding.get("rows", [])
    if not isinstance(rows, list) or data_row_index < 0 or data_row_index >= len(rows):
        return
    row_data = rows[data_row_index]
    if not isinstance(row_data, dict):
        return
    if row_data.get("is_summary_row"):
        return
    column_order = binding.get("column_order", [])
    if column_index < 0 or column_index >= len(column_order):
        return
    field_key = str(column_order[column_index][0])
    item = table.item(row_index, column_index)
    if item is None:
        return
    cells = row_data.get("cells", {})
    if not isinstance(cells, dict):
        cells = {}
    cell_ref = str(cells.get(field_key, "") or "").strip()
    if not cell_ref:
        if binding.get("debug"):
            log_debug("equipment", f"EQUIPMENT EDIT SKIP no cell_ref table={binding.get('table_type')} row={row_index} column={field_key}")
        return

    new_value = str(item.text() or "")
    old_value = str(item.data(Qt.UserRole) or "")
    if new_value == old_value:
        return

    sheet_name = str(window.equipment_analysis.get("sheet", "") or "Ausrüstung")
    table_type = str(binding.get("table_type", ""))
    source_row = row_data.get("row_index", row_data.get("row", data_row_index))
    if binding.get("debug"):
        log_debug("equipment", f"EQUIPMENT EDIT table={table_type} ui_row={row_index} source_row={source_row} column={field_key} cell={cell_ref} old={old_value!r} new={new_value!r}")

    window.loader.set_cell_value(sheet_name, cell_ref, new_value)
    window.loader.save_active_character_json()
    row_data[field_key] = new_value
    item.setData(Qt.UserRole, new_value)
    if binding.get("debug"):
        log_debug("equipment", "EQUIPMENT SAVE active character saved")

    if table_type == "armor":
        refresh_armor_summary_table_row(window, table)
    dynamic_cfg = binding.get("dynamic_rows", {})
    if isinstance(dynamic_cfg, dict) and bool(dynamic_cfg.get("enabled", False)) and _adjust_equipment_dynamic_rows_after_edit(window, binding):
        window.show_main_section("equipment")


def render_equipment_armor_table(window, parent, armor_cfg, armor_rows):
    if not isinstance(armor_cfg, dict) or not armor_cfg.get("enabled", True):
        return

    table_x = window._safe_int(armor_cfg.get("x", 20), 20)
    table_y = window._safe_int(armor_cfg.get("y", 70), 70)
    table_w = window._safe_int(armor_cfg.get("w", 1380), 1380)
    table_h = window._safe_int(armor_cfg.get("h", 330), 330)
    title_text = str(armor_cfg.get("title", "Rüstung"))
    title_font_size = window._safe_int(armor_cfg.get("title_font_size", 20), 20)
    title_color = str(armor_cfg.get("title_color", "#f2d28b"))
    font_size = window._safe_int(armor_cfg.get("font_size", 14), 14)
    header_font_size = window._safe_int(armor_cfg.get("header_font_size", 14), 14)
    header_color = str(armor_cfg.get("header_color", "#f2d28b"))
    text_color = str(armor_cfg.get("text_color", "#ffffff"))
    value_color = str(armor_cfg.get("value_color", "#7fd0ff"))
    border_color = str(armor_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
    table_background_mode = str(armor_cfg.get("table_background_mode", "dark") or "dark")
    background = str(armor_cfg.get("background", "rgba(5, 5, 5, 95)"))
    table_background = background if table_background_mode == "dark" else str(armor_cfg.get("table_background", background))
    min_row_h = window._safe_int(armor_cfg.get("min_row_h", 32), 32)
    max_row_h = window._safe_int(armor_cfg.get("max_row_h", 120), 120)
    min_rows = window._safe_int(armor_cfg.get("min_rows", 10), 10)
    dynamic_rows_cfg = _equipment_dynamic_rows_config(window, armor_cfg, min_rows)
    if dynamic_rows_cfg.get("enabled"):
        min_rows = int(dynamic_rows_cfg.get("min_rows", min_rows))
    summary_cfg = armor_cfg.get("summary", {})
    if not isinstance(summary_cfg, dict):
        summary_cfg = {}
    summary_enabled = bool(summary_cfg.get("enabled", True))
    summary_row_h = window._safe_int(summary_cfg.get("height", 34), 34)
    summary_text_color = str(summary_cfg.get("text_color", "#000000"))
    summary_label_color = str(summary_cfg.get("label_color", "#f2d28b"))
    summary_background_raw = str(summary_cfg.get("background", "rgba(230, 210, 120, 120)"))
    summary_physical_background_raw = str(
        summary_cfg.get("physical_background", "rgba(210, 210, 210, 150)")
    )
    summary_elemental_background_raw = str(
        summary_cfg.get("elemental_background", "rgba(245, 210, 90, 150)")
    )
    summary_durability_background_raw = str(
        summary_cfg.get("durability_background", "rgba(170, 170, 185, 120)")
    )
    summary_label = str(summary_cfg.get("label", "Summe"))
    editable, save_on_cell_change, edit_debug = get_equipment_table_edit_settings(window, armor_cfg)

    panel_frame_state = _apply_equipment_panel_frame_if_enabled(
        window,
        parent,
        armor_cfg,
        {"x": table_x, "y": table_y, "w": table_w, "h": table_h},
    )
    panel = QFrame(parent)
    panel.setGeometry(table_x, table_y, table_w, table_h)
    if panel_frame_state.get("active") and panel_frame_state.get("transparent_panel_background_when_active"):
        panel.setStyleSheet("background: transparent; border: none;")
    elif panel_frame_state.get("active") and panel_frame_state.get("remove_old_border_when_active"):
        panel.setStyleSheet(f"background: {background}; border: none; border-radius: 4px;")
    else:
        panel.setStyleSheet(
            f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
        )
    panel.show()

    title_frame_cfg = armor_cfg.get("title_frame", {}) if isinstance(armor_cfg.get("title_frame", {}), dict) else {}
    show_panel_title = bool(armor_cfg.get("show_title", False)) or bool(title_frame_cfg.get("enabled", False))
    title_label = None
    if show_panel_title:
        title_label = _create_equipment_framed_title(
            window, panel, armor_cfg, table_w, title_text, title_font_size, title_color
        )
    if show_panel_title and title_label is None:
        window.create_panel_text(
            panel,
            {"x": 10, "y": 8, "w": table_w - 20, "h": 28},
            title_text,
            title_font_size,
            title_color,
            bold=True,
            align="left",
        )

    columns_cfg = armor_cfg.get("columns", {})
    if not isinstance(columns_cfg, dict):
        columns_cfg = {}

    column_order = [
        ("slot", "Wo getragen"),
        ("name", "Name"),
        ("pl", "PL"),
        ("phys_head", "Kopf"),
        ("phys_chest", "Brust"),
        ("phys_arms", "Arme"),
        ("phys_legs", "Beine"),
        ("fire", "Feuer"),
        ("water", "Wasser"),
        ("earth", "Erde"),
        ("wind", "Wind"),
        ("lightning", "Blitz"),
        ("ice", "Eis"),
        ("acid", "Säure"),
        ("light", "Licht"),
        ("dark", "Dunkel"),
        ("durability_current", "Haltb."),
        ("durability_max", "Max"),
        ("attributes", "Attribute / Sonderfertigkeiten"),
    ]
    meaningful_fields = [field_key for field_key, _ in column_order]

    table = QTableWidget(panel)
    table_top = 42 if show_panel_title else 10
    table.setGeometry(10, table_top, table_w - 20, table_h - table_top - 10)
    table.setColumnCount(len(column_order))
    summary_row = build_armor_summary_row(window, armor_rows) if summary_enabled else {}
    if summary_enabled:
        summary_row["name"] = summary_label
    data_row_offset = 1 if summary_enabled else 0
    summary_row_index = 0 if summary_enabled else -1
    if dynamic_rows_cfg.get("enabled"):
        visible_data_row_count = _equipment_visible_data_row_count(
            window, "armor", armor_rows, meaningful_fields, dynamic_rows_cfg
        )
        _log_equipment_dynamic_rows(
            window, "armor", armor_rows, meaningful_fields, visible_data_row_count, dynamic_rows_cfg
        )
    else:
        visible_data_row_count = max(len(armor_rows), min_rows)
    table_row_count = visible_data_row_count + (1 if summary_enabled else 0)
    table.setRowCount(table_row_count)
    if editable:
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )
    else:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setWordWrap(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(False)

    field_to_col_index = {}
    header_labels = []
    for col_index, (field_key, fallback_title) in enumerate(column_order):
        field_to_col_index[field_key] = col_index
        col_cfg = columns_cfg.get(field_key, {})
        if not isinstance(col_cfg, dict):
            col_cfg = {}
        header_title = str(col_cfg.get("title", fallback_title))
        col_width = window._safe_int(col_cfg.get("w", 70), 70)
        header_labels.append(header_title)
        table.setColumnWidth(col_index, col_width)
    table.setHorizontalHeaderLabels(header_labels)

    table.setStyleSheet(
        "QTableWidget {"
        f"background: {table_background};"
        f"color: {text_color};"
        f"gridline-color: {border_color};"
        "border: none;"
        f"font-size: {font_size}px;"
        "}"
        "QHeaderView::section {"
        "background: rgba(0,0,0,0);"
        f"color: {header_color};"
        f"font-size: {header_font_size}px; font-weight: 700;"
        f"border: 1px solid {border_color};"
        "padding: 4px;"
        "}"
        "QTableWidget::item { padding: 4px; }"
    )

    group_styles = {}
    column_groups = armor_cfg.get("column_groups", {})
    if not isinstance(column_groups, dict):
        column_groups = {}
    for group_cfg in column_groups.values():
        if not isinstance(group_cfg, dict):
            continue
        group_columns = group_cfg.get("columns", [])
        if not isinstance(group_columns, list):
            group_columns = []
        for field_key in group_columns:
            field_name = str(field_key or "").strip()
            if field_name:
                group_styles[field_name] = group_cfg

    element_header_colors = armor_cfg.get("element_header_colors", {})
    if not isinstance(element_header_colors, dict):
        element_header_colors = {}
    column_backgrounds = armor_cfg.get("column_backgrounds", {})
    if not isinstance(column_backgrounds, dict):
        column_backgrounds = {}
    header_backgrounds = armor_cfg.get("header_backgrounds", {})
    if not isinstance(header_backgrounds, dict):
        header_backgrounds = {}
    cell_text_colors = armor_cfg.get("cell_text_colors", {})
    if not isinstance(cell_text_colors, dict):
        cell_text_colors = {}

    value_fields = {
        "pl",
        "phys_head",
        "phys_chest",
        "phys_arms",
        "phys_legs",
        "fire",
        "water",
        "earth",
        "wind",
        "lightning",
        "ice",
        "acid",
        "light",
        "dark",
        "durability_current",
        "durability_max",
    }
    center_fields = value_fields

    column_background_brushes = {}
    header_background_brushes = {}
    summary_default_color, _ = window.parse_layout_color(summary_background_raw, "rgba(230,210,120,120)")
    summary_physical_color, _ = window.parse_layout_color(
        summary_physical_background_raw, "rgba(210,210,210,150)"
    )
    summary_elemental_color, _ = window.parse_layout_color(
        summary_elemental_background_raw, "rgba(245,210,90,150)"
    )
    summary_durability_color, _ = window.parse_layout_color(
        summary_durability_background_raw, "rgba(170,170,185,120)"
    )
    for field_key, _ in column_order:
        col_bg_raw = column_backgrounds.get(field_key, "")
        if not col_bg_raw:
            group_cfg = group_styles.get(field_key, {})
            if isinstance(group_cfg, dict):
                col_bg_raw = group_cfg.get("background", "")
        col_color, col_ok = window.parse_layout_color(col_bg_raw, "rgba(0,0,0,0)")
        column_background_brushes[field_key] = QBrush(col_color)

        header_bg_raw = header_backgrounds.get(field_key, "")
        if not header_bg_raw:
            group_cfg = group_styles.get(field_key, {})
            if isinstance(group_cfg, dict):
                header_bg_raw = group_cfg.get("background", "")
        header_color_parsed, header_ok = window.parse_layout_color(header_bg_raw, "rgba(0,0,0,0)")
        header_background_brushes[field_key] = QBrush(header_color_parsed)

        if window._equipment_print_mapping_enabled():
            log_debug("equipment", f"EQUIPMENT ARMOR STYLE TEST column={field_key} cell_bg={col_bg_raw} header_bg={header_bg_raw}")
            if field_key == "durability_current":
                title_text_current = header_labels[field_to_col_index[field_key]]
                log_debug("equipment", f"EQUIPMENT ARMOR STYLE TEST column=durability_current title={title_text_current}")
            if not col_ok and str(col_bg_raw or "").strip() not in {"", "-"}:
                log_warning("equipment", f"EQUIPMENT ARMOR STYLE ERROR column={field_key} value={col_bg_raw} parsed=False")
            elif not col_ok:
                log_debug("equipment", f"EQUIPMENT ARMOR STYLE empty column value skipped column={field_key}")
            if not header_ok and str(header_bg_raw or "").strip() not in {"", "-"}:
                log_warning("equipment", f"EQUIPMENT ARMOR STYLE ERROR column={field_key} value={header_bg_raw} parsed=False")
            elif not header_ok:
                log_debug("equipment", f"EQUIPMENT ARMOR STYLE empty header value skipped column={field_key}")

    for field_key, _ in column_order:
        col_index = field_to_col_index.get(field_key)
        if col_index is None:
            continue
        header_item = table.horizontalHeaderItem(col_index)
        if header_item is None:
            continue
        header_item.setToolTip(header_item.text())
        header_item.setBackground(header_background_brushes.get(field_key, QBrush()))
        header_item.setForeground(QBrush(QColor("#f2d28b")))

    for field_key, color_value in element_header_colors.items():
        col_index = field_to_col_index.get(str(field_key or "").strip())
        if col_index is None:
            continue
        header_item = table.horizontalHeaderItem(col_index)
        if header_item is None:
            continue
        element_color = QColor(str(color_value))
        if element_color.isValid():
            header_item.setForeground(QBrush(element_color))

    table.blockSignals(True)
    window._equipment_rendering = True
    for row_index in range(table_row_count):
        is_summary_row = summary_enabled and row_index == summary_row_index
        if is_summary_row:
            row_data = summary_row
        else:
            data_row_index = row_index - data_row_offset
            row_data = (
                armor_rows[data_row_index]
                if data_row_index >= 0
                and data_row_index < len(armor_rows)
                and isinstance(armor_rows[data_row_index], dict)
                else {}
            )
        row_has_data = any(str(row_data.get(key, "") or "").strip() for key, _ in column_order)
        for col_index, (field_key, _) in enumerate(column_order):
            raw_value = str(row_data.get(field_key, "") or "").strip()
            display_value = raw_value if raw_value else ""
            item = QTableWidgetItem(display_value)
            item.setData(Qt.UserRole, raw_value)
            if field_key in center_fields:
                item.setTextAlignment(Qt.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            custom_text_color = str(cell_text_colors.get(field_key, "") or "").strip()
            if is_summary_row:
                if field_key == "name":
                    item.setForeground(QBrush(QColor(summary_label_color)))
                else:
                    item.setForeground(QBrush(QColor(summary_text_color)))
            elif custom_text_color:
                item.setForeground(QBrush(QColor(custom_text_color)))
            elif raw_value and field_key in value_fields:
                item.setForeground(QColor(value_color))
            else:
                item.setForeground(QColor(text_color))
            if is_summary_row:
                if field_key in {"phys_head", "phys_chest", "phys_arms", "phys_legs"}:
                    item.setBackground(QBrush(summary_physical_color))
                elif field_key in {
                    "fire",
                    "water",
                    "earth",
                    "wind",
                    "lightning",
                    "ice",
                    "acid",
                    "light",
                    "dark",
                }:
                    item.setBackground(QBrush(summary_elemental_color))
                elif field_key in {"durability_current", "durability_max"}:
                    item.setBackground(QBrush(summary_durability_color))
                else:
                    item.setBackground(QBrush(summary_default_color))
            else:
                item.setBackground(column_background_brushes.get(field_key, QBrush()))
            if raw_value:
                item.setToolTip(raw_value)
            elif not row_has_data:
                item.setToolTip("")
            can_edit = (
                editable
                and not is_summary_row
                and data_row_index >= 0
                and data_row_index < len(armor_rows)
                and bool(str(row_data.get("cells", {}).get(field_key, "") or "").strip())
            )
            apply_equipment_item_editability(item, can_edit)
            table.setItem(row_index, col_index, item)
        table.setRowHeight(row_index, summary_row_h if is_summary_row else min_row_h)
        if edit_debug and not is_summary_row and data_row_index >= 0 and data_row_index < len(armor_rows):
            cell_ref = str(row_data.get("cells", {}).get("name", "") or "").strip()
            if cell_ref:
                log_debug("equipment", f"EQUIPMENT EDIT MAP armor row={row_data.get('row_index', row_index)} column=name cell={cell_ref}")

    table.resizeRowsToContents()
    for row_index in range(table_row_count):
        if summary_enabled and row_index == summary_row_index:
            table.setRowHeight(row_index, summary_row_h)
            continue
        current_h = table.rowHeight(row_index)
        if current_h < min_row_h:
            table.setRowHeight(row_index, min_row_h)
        elif current_h > max_row_h:
            table.setRowHeight(row_index, max_row_h)

    table.blockSignals(False)
    window._equipment_rendering = False
    window._equipment_table_bindings[id(table)] = {
        "table_type": "armor",
        "rows": armor_rows,
        "column_order": column_order,
        "meaningful_fields": meaningful_fields,
        "summary_row_index": summary_row_index,
        "data_row_offset": data_row_offset,
        "visible_data_row_count": visible_data_row_count,
        "dynamic_rows": dynamic_rows_cfg,
        "summary_row": summary_row,
        "summary_label": summary_label,
        "save_on_cell_change": save_on_cell_change,
        "debug": edit_debug,
    }
    table.itemChanged.connect(
        lambda item, widget=table: on_equipment_table_item_changed(
            window, widget, item.row(), item.column()
        )
    )
    table.show()


def render_equipment_weapons_table(window, parent, weapons_cfg, weapon_rows):
    if not isinstance(weapons_cfg, dict) or not weapons_cfg.get("enabled", True):
        return

    table_x = window._safe_int(weapons_cfg.get("x", 20), 20)
    table_y = window._safe_int(weapons_cfg.get("y", 470), 470)
    table_w = window._safe_int(weapons_cfg.get("w", 1380), 1380)
    table_h = window._safe_int(weapons_cfg.get("h", 300), 300)
    title_text = str(weapons_cfg.get("title", "Waffen"))
    title_font_size = window._safe_int(weapons_cfg.get("title_font_size", 20), 20)
    title_color = str(weapons_cfg.get("title_color", "#f2d28b"))
    font_size = window._safe_int(weapons_cfg.get("font_size", 14), 14)
    header_font_size = window._safe_int(weapons_cfg.get("header_font_size", 14), 14)
    header_color = str(weapons_cfg.get("header_color", "#f2d28b"))
    text_color = str(weapons_cfg.get("text_color", "#ffffff"))
    value_color = str(weapons_cfg.get("value_color", "#7fd0ff"))
    border_color = str(weapons_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
    table_background_mode = str(weapons_cfg.get("table_background_mode", "default") or "default")
    background = str(weapons_cfg.get("background", "rgba(5, 5, 5, 95)"))
    table_background = str(weapons_cfg.get("table_background", background)) if table_background_mode == "default" else background
    min_row_h = window._safe_int(weapons_cfg.get("min_row_h", 32), 32)
    max_row_h = window._safe_int(weapons_cfg.get("max_row_h", 72), 72)
    min_rows = window._safe_int(weapons_cfg.get("min_rows", 8), 8)
    dynamic_rows_cfg = _equipment_dynamic_rows_config(window, weapons_cfg, min_rows)
    if dynamic_rows_cfg.get("enabled"):
        min_rows = int(dynamic_rows_cfg.get("min_rows", min_rows))
    editable, save_on_cell_change, edit_debug = get_equipment_table_edit_settings(window, weapons_cfg)

    panel_frame_state = _apply_equipment_panel_frame_if_enabled(
        window,
        parent,
        weapons_cfg,
        {"x": table_x, "y": table_y, "w": table_w, "h": table_h},
    )
    panel = QFrame(parent)
    panel.setGeometry(table_x, table_y, table_w, table_h)
    if panel_frame_state.get("active") and panel_frame_state.get("transparent_panel_background_when_active"):
        panel.setStyleSheet("background: transparent; border: none;")
    elif panel_frame_state.get("active") and panel_frame_state.get("remove_old_border_when_active"):
        panel.setStyleSheet(f"background: {background}; border: none; border-radius: 4px;")
    else:
        panel.setStyleSheet(
            f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
        )
    panel.show()

    title_frame_cfg = weapons_cfg.get("title_frame", {}) if isinstance(weapons_cfg.get("title_frame", {}), dict) else {}
    show_panel_title = bool(weapons_cfg.get("show_title", False)) or bool(title_frame_cfg.get("enabled", False))
    title_label = None
    if show_panel_title:
        title_label = _create_equipment_framed_title(
            window, panel, weapons_cfg, table_w, title_text, title_font_size, title_color
        )
    if show_panel_title and title_label is None:
        window.create_panel_text(
            panel,
            {"x": 10, "y": 8, "w": table_w - 20, "h": 28},
            title_text,
            title_font_size,
            title_color,
            bold=True,
            align="left",
        )

    columns_cfg = weapons_cfg.get("columns", {})
    if not isinstance(columns_cfg, dict):
        columns_cfg = {}

    column_order = [
        ("name", "Name"),
        ("weapon_type", "Waffentyp"),
        ("pl", "PL"),
        ("damage_cut", "Schnitt"),
        ("damage_blunt", "Stoß"),
        ("damage_pierce", "Stich"),
        ("physical_dice", "Phys. Würfel"),
        ("physical_bonus", "Phys. Bonus"),
        ("elemental_dice", "Elem. Würfel"),
        ("elemental_elements", "Element(e)"),
        ("elemental_bonus", "Elem. Bonus"),
        ("durability_current", "Haltb."),
        ("durability_max", "Max"),
        ("attributes", "Attribute / Sonderfertigkeiten"),
    ]
    meaningful_fields = [field_key for field_key, _ in column_order]

    table = QTableWidget(panel)
    table_top = 42 if show_panel_title else 10
    table.setGeometry(10, table_top, table_w - 20, table_h - table_top - 10)
    table.setColumnCount(len(column_order))
    if dynamic_rows_cfg.get("enabled"):
        visible_data_row_count = _equipment_visible_data_row_count(
            window, "weapons", weapon_rows, meaningful_fields, dynamic_rows_cfg
        )
        _log_equipment_dynamic_rows(
            window, "weapons", weapon_rows, meaningful_fields, visible_data_row_count, dynamic_rows_cfg
        )
    else:
        visible_data_row_count = max(len(weapon_rows), min_rows)
    table_row_count = visible_data_row_count
    table.setRowCount(table_row_count)
    if editable:
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )
    else:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setWordWrap(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(False)

    field_to_col_index = {}
    header_labels = []
    for col_index, (field_key, fallback_title) in enumerate(column_order):
        field_to_col_index[field_key] = col_index
        col_cfg = columns_cfg.get(field_key, {})
        if not isinstance(col_cfg, dict):
            col_cfg = {}
        header_title = str(col_cfg.get("title", fallback_title))
        col_width = window._safe_int(col_cfg.get("w", 70), 70)
        header_labels.append(header_title)
        table.setColumnWidth(col_index, col_width)
    table.setHorizontalHeaderLabels(header_labels)

    table.setStyleSheet(
        "QTableWidget {"
        f"background: {table_background};"
        f"color: {text_color};"
        f"gridline-color: {border_color};"
        "border: none;"
        f"font-size: {font_size}px;"
        "}"
        "QHeaderView::section {"
        "background: rgba(0,0,0,0);"
        f"color: {header_color};"
        f"font-size: {header_font_size}px; font-weight: 700;"
        f"border: 1px solid {border_color};"
        "padding: 4px;"
        "}"
        "QTableWidget::item { padding: 4px; }"
    )

    column_backgrounds = weapons_cfg.get("column_backgrounds", {})
    if not isinstance(column_backgrounds, dict):
        column_backgrounds = {}
    header_backgrounds = weapons_cfg.get("header_backgrounds", {})
    if not isinstance(header_backgrounds, dict):
        header_backgrounds = {}
    cell_text_colors = weapons_cfg.get("cell_text_colors", {})
    if not isinstance(cell_text_colors, dict):
        cell_text_colors = {}

    value_fields = {
        "pl",
        "damage_cut",
        "damage_blunt",
        "damage_pierce",
        "physical_dice",
        "physical_bonus",
        "elemental_dice",
        "elemental_bonus",
        "durability_current",
        "durability_max",
    }
    center_fields = value_fields | {"weapon_type", "elemental_elements"}

    column_background_brushes = {}
    header_background_brushes = {}
    for field_key, _ in column_order:
        col_bg_raw = str(column_backgrounds.get(field_key, "") or "")
        col_color, _ = window.parse_layout_color(col_bg_raw, "rgba(0,0,0,0)")
        column_background_brushes[field_key] = QBrush(col_color)

        header_bg_raw = str(header_backgrounds.get(field_key, "") or col_bg_raw)
        header_color_parsed, _ = window.parse_layout_color(header_bg_raw, "rgba(0,0,0,0)")
        header_background_brushes[field_key] = QBrush(header_color_parsed)

    for field_key, _ in column_order:
        col_index = field_to_col_index.get(field_key)
        if col_index is None:
            continue
        header_item = table.horizontalHeaderItem(col_index)
        if header_item is None:
            continue
        header_item.setToolTip(header_item.text())
        header_item.setBackground(header_background_brushes.get(field_key, QBrush()))
        header_item.setForeground(QBrush(QColor("#f2d28b")))

    table.blockSignals(True)
    window._equipment_rendering = True
    for row_index in range(table_row_count):
        row_data = (
            weapon_rows[row_index]
            if row_index < len(weapon_rows) and isinstance(weapon_rows[row_index], dict)
            else {}
        )
        for col_index, (field_key, _) in enumerate(column_order):
            raw_value = str(row_data.get(field_key, "") or "").strip()
            item = QTableWidgetItem(raw_value)
            item.setData(Qt.UserRole, raw_value)
            if field_key in center_fields:
                item.setTextAlignment(Qt.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            custom_text_color = str(cell_text_colors.get(field_key, "") or "").strip()
            if custom_text_color:
                item.setForeground(QBrush(QColor(custom_text_color)))
            elif raw_value and field_key in value_fields:
                item.setForeground(QColor(value_color))
            else:
                item.setForeground(QColor(text_color))
            item.setBackground(column_background_brushes.get(field_key, QBrush()))
            if raw_value:
                item.setToolTip(raw_value)
            can_edit = (
                editable
                and row_index < len(weapon_rows)
                and bool(str(row_data.get("cells", {}).get(field_key, "") or "").strip())
            )
            apply_equipment_item_editability(item, can_edit)
            table.setItem(row_index, col_index, item)
        table.setRowHeight(row_index, min_row_h)
        if edit_debug and row_index < len(weapon_rows):
            cell_ref = str(row_data.get("cells", {}).get("name", "") or "").strip()
            if cell_ref:
                log_debug("equipment", f"EQUIPMENT EDIT MAP weapons row={row_data.get('row_index', row_index)} column=name cell={cell_ref}")

    table.resizeRowsToContents()
    for row_index in range(table_row_count):
        current_h = table.rowHeight(row_index)
        if current_h < min_row_h:
            table.setRowHeight(row_index, min_row_h)
        elif current_h > max_row_h:
            table.setRowHeight(row_index, max_row_h)

    table.blockSignals(False)
    window._equipment_rendering = False
    window._equipment_table_bindings[id(table)] = {
        "table_type": "weapons",
        "rows": weapon_rows,
        "column_order": column_order,
        "meaningful_fields": meaningful_fields,
        "summary_row_index": -1,
        "data_row_offset": 0,
        "visible_data_row_count": visible_data_row_count,
        "dynamic_rows": dynamic_rows_cfg,
        "save_on_cell_change": save_on_cell_change,
        "debug": edit_debug,
    }
    table.itemChanged.connect(
        lambda item, widget=table: on_equipment_table_item_changed(
            window, widget, item.row(), item.column()
        )
    )
    table.show()
