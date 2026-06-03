from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QAbstractItemView, QFrame, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QWidget

from app_logger import log_debug


class InlineTextEdit(QTextEdit):
    def __init__(self, on_commit=None, parent=None):
        super().__init__(parent)
        self.on_commit = on_commit
        self._initial_text = ""

    def set_initial_text(self, text):
        self._initial_text = "" if text is None else str(text)
        self.setPlainText(self._initial_text)

    def focusOutEvent(self, event):
        new_text = self.toPlainText()
        if self.on_commit and new_text != self._initial_text:
            self.on_commit(new_text, self._initial_text)
            self._initial_text = new_text
        super().focusOutEvent(event)


def _optional_theme_ui_pixmap(window, asset_rel_path):
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


def _apply_source_crop(window, src, frame_cfg):
    crop_cfg = frame_cfg.get("source_crop") if isinstance(frame_cfg, dict) else None
    if not isinstance(crop_cfg, dict):
        return src
    src_w = max(1, src.width())
    src_h = max(1, src.height())
    x = max(0, min(window._safe_int(crop_cfg.get("x", 0), 0), src_w - 1))
    y = max(0, min(window._safe_int(crop_cfg.get("y", 0), 0), src_h - 1))
    w = max(1, min(window._safe_int(crop_cfg.get("w", src_w - x), src_w - x), src_w - x))
    h = max(1, min(window._safe_int(crop_cfg.get("h", src_h - y), src_h - y), src_h - y))
    cropped = src.copy(x, y, w, h)
    return cropped if not cropped.isNull() else src


def _frame_opacity(frame_cfg):
    try:
        opacity = float(frame_cfg.get("opacity", 1.0))
    except Exception:
        opacity = 1.0
    return max(0.0, min(1.0, opacity))


def _render_fit_pixmap(src, target_w, target_h, frame_cfg):
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
    painter.setOpacity(_frame_opacity(frame_cfg))
    dx = int((target_w - scaled.width()) / 2) if keep_aspect and fit_mode != "stretch" else 0
    dy = int((target_h - scaled.height()) / 2) if keep_aspect and fit_mode != "stretch" else 0
    painter.drawPixmap(dx, dy, scaled)
    painter.end()
    return rendered


def _render_nine_slice_pixmap(window, src, target_w, target_h, frame_cfg):
    slice_cfg = frame_cfg.get("slice", {}) if isinstance(frame_cfg.get("slice", {}), dict) else {}
    src_w = max(1, src.width())
    src_h = max(1, src.height())
    left = max(0, min(window._safe_int(slice_cfg.get("left", 32), 32), src_w))
    right = max(0, min(window._safe_int(slice_cfg.get("right", 32), 32), src_w - left))
    top = max(0, min(window._safe_int(slice_cfg.get("top", 32), 32), src_h))
    bottom = max(0, min(window._safe_int(slice_cfg.get("bottom", 32), 32), src_h - top))

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
    try:
        render_scale = float(frame_cfg.get("render_scale", 1.0))
    except Exception:
        render_scale = 1.0
    render_scale = max(1.0, min(4.0, render_scale))
    opacity = _frame_opacity(frame_cfg)

    center_src_w = max(0, src_w - left - right)
    center_src_h = max(0, src_h - top - bottom)
    scaled_w = max(1, int(round(target_w * render_scale)))
    scaled_h = max(1, int(round(target_h * render_scale)))
    scaled_left = max(0, int(round(left * render_scale)))
    scaled_right = max(0, int(round(right * render_scale)))
    scaled_top = max(0, int(round(top * render_scale)))
    scaled_bottom = max(0, int(round(bottom * render_scale)))
    scaled_center_dst_w = max(0, scaled_w - scaled_left - scaled_right)
    scaled_center_dst_h = max(0, scaled_h - scaled_top - scaled_bottom)

    rendered = QPixmap(scaled_w, scaled_h)
    rendered.fill(Qt.transparent)
    painter = QPainter(rendered)
    if smooth_scaling:
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setOpacity(opacity)

    def draw_slice(dx, dy, dw, dh, sx, sy, sw, sh):
        if dw <= 0 or dh <= 0 or sw <= 0 or sh <= 0:
            return
        painter.drawPixmap(dx, dy, dw, dh, src, sx, sy, sw, sh)

    draw_slice(0, 0, scaled_left, scaled_top, 0, 0, left, top)
    draw_slice(scaled_w - scaled_right, 0, scaled_right, scaled_top, src_w - right, 0, right, top)
    draw_slice(0, scaled_h - scaled_bottom, scaled_left, scaled_bottom, 0, src_h - bottom, left, bottom)
    draw_slice(scaled_w - scaled_right, scaled_h - scaled_bottom, scaled_right, scaled_bottom, src_w - right, src_h - bottom, right, bottom)
    draw_slice(scaled_left, 0, scaled_center_dst_w, scaled_top, left, 0, center_src_w, top)
    draw_slice(scaled_left, scaled_h - scaled_bottom, scaled_center_dst_w, scaled_bottom, left, src_h - bottom, center_src_w, bottom)
    draw_slice(0, scaled_top, scaled_left, scaled_center_dst_h, 0, top, left, center_src_h)
    draw_slice(scaled_w - scaled_right, scaled_top, scaled_right, scaled_center_dst_h, src_w - right, top, right, center_src_h)
    if bool(frame_cfg.get("draw_center", True)):
        draw_slice(scaled_left, scaled_top, scaled_center_dst_w, scaled_center_dst_h, left, top, center_src_w, center_src_h)
    painter.end()

    if render_scale > 1.0:
        rendered = rendered.scaled(
            target_w,
            target_h,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation if smooth_scaling else Qt.FastTransformation,
        )
    return rendered


def apply_skills_table_frame_if_enabled(window, parent, table_cfg):
    frame_cfg = table_cfg.get("frame", {}) if isinstance(table_cfg, dict) else {}
    if not isinstance(frame_cfg, dict) or not bool(frame_cfg.get("enabled", False)):
        return {"active": False}
    src = _optional_theme_ui_pixmap(window, frame_cfg.get("asset", ""))
    if src is None:
        return {"active": False}

    x = window._safe_int(table_cfg.get("x", 20), 20)
    y = window._safe_int(table_cfg.get("y", 80), 80)
    w = max(1, window._safe_int(table_cfg.get("w", 1380), 1380))
    h = max(1, window._safe_int(table_cfg.get("h", 700), 700))
    bg = QLabel(parent)
    bg.setGeometry(x, y, w, h)
    bg.setPixmap(_render_nine_slice_pixmap(window, _apply_source_crop(window, src, frame_cfg), w, h, frame_cfg))
    bg.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    bg.show()
    return {
        "active": True,
        "remove_old_border_when_active": bool(frame_cfg.get("remove_old_border_when_active", True)),
        "transparent_panel_background_when_active": bool(frame_cfg.get("transparent_panel_background_when_active", True)),
        "fallback_border": bool(frame_cfg.get("fallback_border", True)),
    }


def apply_skills_row_field_frame_if_enabled(window, parent, row_fields_cfg, field_id, rect_cfg, raise_frame=False):
    field_cfg = row_fields_cfg.get(field_id, {}) if isinstance(row_fields_cfg, dict) else {}
    frame_cfg = field_cfg.get("frame", {}) if isinstance(field_cfg, dict) else {}
    if not isinstance(frame_cfg, dict) or not bool(frame_cfg.get("enabled", False)):
        return False
    src = _optional_theme_ui_pixmap(window, frame_cfg.get("asset", ""))
    if src is None:
        return False

    rect_x = window._safe_int(rect_cfg.get("x", 0), 0)
    rect_y = window._safe_int(rect_cfg.get("y", 0), 0)
    rect_w = max(1, window._safe_int(rect_cfg.get("w", 1), 1))
    rect_h = max(1, window._safe_int(rect_cfg.get("h", 1), 1))
    w = max(1, window._safe_int(field_cfg.get("w", frame_cfg.get("image_w", rect_w)), rect_w))
    h = max(1, window._safe_int(field_cfg.get("h", frame_cfg.get("image_h", rect_h)), rect_h))
    offset_x = window._safe_int(frame_cfg.get("image_offset_x", 0), 0)
    offset_y = window._safe_int(frame_cfg.get("image_offset_y", 0), 0)
    x = rect_x + int((rect_w - w) / 2) + offset_x
    y = rect_y + int((rect_h - h) / 2) + offset_y
    src = _apply_source_crop(window, src, frame_cfg)
    render_mode = str(frame_cfg.get("render_mode", "") or "").strip().lower()
    if not render_mode:
        render_mode = "nine_slice" if field_id in ("specialization", "note") else "fit"
    bg = QLabel(parent)
    bg.setGeometry(x, y, w, h)
    if render_mode == "nine_slice":
        bg.setPixmap(_render_nine_slice_pixmap(window, src, w, h, frame_cfg))
    else:
        bg.setPixmap(_render_fit_pixmap(src, w, h, frame_cfg))
    bg.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    bg.show()
    if raise_frame:
        bg.raise_()
    return True


def _create_asset_category_button(window, parent, cfg, title, is_active, callback):
    button_cfg = cfg.get("button", {}) if isinstance(cfg, dict) else {}
    if not isinstance(button_cfg, dict) or not bool(button_cfg.get("enabled", False)):
        return None

    asset_key = "active_asset" if is_active else "inactive_asset"
    asset = str(button_cfg.get(asset_key, button_cfg.get("asset", "")) or "").strip()
    pixmap = _optional_theme_ui_pixmap(window, asset)
    if pixmap is None:
        return None

    w = window._safe_int(cfg.get("button_w", 220), 220)
    h = window._safe_int(cfg.get("button_h", 42), 42)
    container = QWidget(parent)
    container.setGeometry(0, 0, w, h)

    bg_label = QLabel(container)
    bg_label.setGeometry(0, 0, w, h)
    bg_label.setPixmap(pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    bg_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    bg_label.show()

    font_size = window._safe_int(button_cfg.get("font_size", cfg.get("font_size", 20)), 20)
    active_color = str(button_cfg.get("active_color", cfg.get("active_color", "#f2d28b")))
    inactive_color = str(button_cfg.get("inactive_color", cfg.get("inactive_color", "#9a8560")))
    color = active_color if is_active else inactive_color
    border = "1px solid rgba(242, 210, 139, 170)" if is_active and bool(button_cfg.get("selected_border", True)) else "none"

    click_button = QPushButton(container)
    click_button.setGeometry(0, 0, w, h)
    click_button.setText(title)
    click_button.setCursor(Qt.PointingHandCursor)
    click_button.setStyleSheet(
        "QPushButton {"
        "background: transparent;"
        f"border: {border};"
        f"color: {color};"
        f"font-size: {font_size}px;"
        "font-weight: 700;"
        "padding: 0px;"
        "}"
        "QPushButton:hover { color: #ffffff; border: 1px solid rgba(242, 210, 139, 210); }"
    )
    click_button.clicked.connect(callback)
    click_button.show()
    container.show()
    return container


def render_skills_section(window):
    if window.content_layer is None:
        return

    layout_config = window.load_skills_layout_config()
    skill_definitions = window.load_skill_definitions()
    screen_cfg = layout_config.get("skills_screen", {})
    categories = skill_definitions.get("categories", [])
    if not isinstance(categories, list):
        categories = []
    se_cfg = screen_cfg.get("se_tab", {})
    if not isinstance(se_cfg, dict):
        se_cfg = {}
    se_enabled = bool(se_cfg.get("enabled", True))
    se_button_text = str(se_cfg.get("button_text", "SE") or "SE")
    categories_for_tabs = list(categories)
    if se_enabled:
        categories_for_tabs.append({"id": "se", "title": se_button_text, "skills": []})
    attribute_map = skill_definitions.get("attribute_map", {})
    if not isinstance(attribute_map, dict):
        attribute_map = {}

    category_ids = [
        str(category.get("id", ""))
        for category in categories_for_tabs
        if isinstance(category, dict) and str(category.get("id", "")).strip()
    ]
    if window.skills_debug_sources:
        log_debug("skills", f"render category={window.current_skill_category}")
        log_debug("skills", f"loaded categories={category_ids}")
    has_skills_cache = bool(window.loader.cell_cache) and isinstance(
        window.loader.cell_cache.get("Fertigkeiten"),
        dict,
    )
    if has_skills_cache:
        window.build_skill_source_infos(categories, attribute_map)
    else:
        window.skill_source_infos = {}
        if window.skills_debug_sources:
            log_debug("skills", "no Fertigkeiten sheet loaded")

    if window.current_skill_category not in category_ids and category_ids:
        window.current_skill_category = category_ids[0]

    screen = QFrame(window.content_layer)
    screen.setGeometry(
        window._safe_int(screen_cfg.get("x", 20), 20),
        window._safe_int(screen_cfg.get("y", 20), 20),
        window._safe_int(screen_cfg.get("w", 1420), 1420),
        window._safe_int(screen_cfg.get("h", 820), 820),
    )
    screen.setStyleSheet("background: transparent;")
    screen.show()

    tabs_cfg = screen_cfg.get("category_tabs", {})
    tabs_container = QFrame(screen)
    tabs_container.setGeometry(
        window._safe_int(tabs_cfg.get("x", 20), 20),
        window._safe_int(tabs_cfg.get("y", 10), 10),
        window._safe_int(tabs_cfg.get("w", 1380), 1380),
        window._safe_int(tabs_cfg.get("h", 50), 50),
    )
    tabs_container.setStyleSheet("background: transparent;")
    tabs_container.show()

    button_w = window._safe_int(tabs_cfg.get("button_w", 220), 220)
    button_h = window._safe_int(tabs_cfg.get("button_h", 42), 42)
    button_gap = window._safe_int(tabs_cfg.get("gap", 18), 18)
    button_cfg = tabs_cfg.get("button", {}) if isinstance(tabs_cfg.get("button", {}), dict) else {}
    tab_font_size = window._safe_int(button_cfg.get("font_size", tabs_cfg.get("font_size", 20)), 20)
    active_color = str(tabs_cfg.get("active_color", "#f2d28b"))
    inactive_color = str(tabs_cfg.get("inactive_color", "#9a8560"))

    for index, category in enumerate(categories_for_tabs):
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("id", "")).strip()
        if not category_id:
            continue
        title = str(category.get("title", category_id))
        is_active = category_id == window.current_skill_category
        callback = lambda checked=False, cid=category_id: window.on_skill_category_clicked(cid)
        asset_button = _create_asset_category_button(
            window,
            tabs_container,
            tabs_cfg,
            title,
            is_active,
            callback,
        )
        if asset_button is not None:
            asset_button.move(index * (button_w + button_gap), 0)
            continue
        button = QPushButton(tabs_container)
        button.setGeometry(index * (button_w + button_gap), 0, button_w, button_h)
        button.setText(title)
        button.setCursor(Qt.PointingHandCursor)
        color = active_color if is_active else inactive_color
        border = "#b88a35" if is_active else "rgba(180, 140, 70, 90)"
        bg = "rgba(35, 24, 12, 185)" if is_active else "rgba(8, 8, 8, 125)"
        button.setStyleSheet(
            "QPushButton {"
            f"background-color: {bg};"
            f"color: {color};"
            f"border: 1px solid {border};"
            "border-radius: 4px;"
            f"font-size: {tab_font_size}px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { border: 1px solid #f2d28b; color: #ffffff; }"
        )
        button.clicked.connect(callback)
        button.show()

    active_category = None
    for category in categories_for_tabs:
        if isinstance(category, dict) and category.get("id") == window.current_skill_category:
            active_category = category
            break
    if active_category is None:
        active_category = {"id": window.current_skill_category, "skills": []}

    if str(window.current_skill_category).strip().lower() == "se":
        render_skills_se_table(window, screen, screen_cfg, se_cfg)
        return screen
    render_skills_table(window, screen, screen_cfg.get("table", {}), active_category, attribute_map)
    return screen


def render_skills_se_table(window, parent, screen_cfg, se_cfg):
    table_area_cfg = screen_cfg.get("table", {})
    if not isinstance(table_area_cfg, dict):
        table_area_cfg = {}
    se_table_cfg = se_cfg.get("table", {}) if isinstance(se_cfg, dict) else {}
    if not isinstance(se_table_cfg, dict):
        se_table_cfg = {}
    x = window._safe_int(se_table_cfg.get("x", window._safe_int(table_area_cfg.get("x", 20), 20) + 20), 40)
    y = window._safe_int(se_table_cfg.get("y", window._safe_int(table_area_cfg.get("y", 80), 80) + 20), 110)
    w = window._safe_int(se_table_cfg.get("w", 340), 340)
    h = window._safe_int(se_table_cfg.get("h", 520), 520)
    min_rows = window._safe_int(se_table_cfg.get("min_rows", 16), 16)
    add_rows = window._safe_int(se_table_cfg.get("add_rows_when_last_filled", 3), 3)
    columns_cfg = se_table_cfg.get("columns", {})
    if not isinstance(columns_cfg, dict):
        columns_cfg = {}
    text_col_cfg = columns_cfg.get("text", {})
    value_col_cfg = columns_cfg.get("value", {})
    if not isinstance(text_col_cfg, dict):
        text_col_cfg = {}
    if not isinstance(value_col_cfg, dict):
        value_col_cfg = {}

    frame = QFrame(parent)
    frame.setGeometry(x, y, w, h)
    frame.setStyleSheet(
        "background: rgba(5, 5, 5, 95);"
        "border: 1px solid rgba(242, 210, 139, 70);"
        "border-radius: 4px;"
    )
    frame.show()

    se_table = QTableWidget(frame)
    se_table.setGeometry(8, 8, max(1, w - 16), max(1, h - 16))
    se_table.setColumnCount(2)
    se_table.setHorizontalHeaderLabels(
        [
            str(text_col_cfg.get("title", "Fertigkeit")),
            str(value_col_cfg.get("title", "SE")),
        ]
    )
    se_table.verticalHeader().setVisible(False)
    se_table.setWordWrap(False)
    se_table.setEditTriggers(
        QAbstractItemView.DoubleClicked
        | QAbstractItemView.EditKeyPressed
        | QAbstractItemView.SelectedClicked
    )
    se_table.setSelectionMode(QAbstractItemView.SingleSelection)
    se_table.setSelectionBehavior(QAbstractItemView.SelectItems)
    se_table.setStyleSheet(
        "QTableWidget {"
        "background: rgba(5, 5, 5, 95);"
        "color: #f2f2f2;"
        "gridline-color: rgba(242, 210, 139, 70);"
        "font-size: 14px;"
        "border: none;"
        "selection-background-color: rgba(242, 210, 139, 30);"
        "selection-color: #ffffff;"
        "}"
        "QHeaderView::section {"
        "background: rgba(24, 16, 8, 175);"
        "color: #f2d28b;"
        "font-size: 14px;"
        "font-weight: 700;"
        "border: 1px solid rgba(242, 210, 139, 70);"
        "padding: 3px;"
        "}"
    )

    rows = window._get_skills_se_rows_from_meta()
    while len(rows) < max(0, int(min_rows)):
        rows.append({"text": "", "skill_key": "", "skill_name": "", "value": ""})

    window._skills_se_loading = True
    se_table.blockSignals(True)
    try:
        se_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            bound_skill_name = str(row.get("skill_name", "") or "").strip()
            text_value = bound_skill_name or str(row.get("text", "") or "")
            value_value = str(row.get("value", "") or "")
            text_item = QTableWidgetItem(text_value)
            value_item = QTableWidgetItem(value_value)
            text_item.setFlags((text_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled) & ~Qt.ItemIsEditable)
            skill_key = str(row.get("skill_key", "") or "").strip()
            if skill_key:
                text_item.setData(Qt.UserRole, skill_key)
                text_item.setData(Qt.UserRole + 1, text_value)
            text_item.setToolTip(text_value if text_value else "")
            value_item.setToolTip(value_value if value_value else "")
            se_table.setItem(row_index, 0, text_item)
            se_table.setItem(row_index, 1, value_item)
        text_w = window._safe_int(text_col_cfg.get("w", 240), 240)
        value_w = window._safe_int(value_col_cfg.get("w", 80), 80)
        available = max(1, se_table.width() - 4)
        configured = text_w + value_w
        if configured > available:
            text_w = max(120, text_w - (configured - available))
        se_table.setColumnWidth(0, max(1, text_w))
        se_table.setColumnWidth(1, max(1, value_w))
        for r in range(se_table.rowCount()):
            se_table.setRowHeight(r, 28)
    finally:
        se_table.blockSignals(False)
        window._skills_se_loading = False

    se_table.cellChanged.connect(
        lambda row, col, widget=se_table, mr=min_rows, ar=add_rows: window.on_skills_se_table_cell_changed(
            widget, mr, ar
        )
    )
    se_table.cellDoubleClicked.connect(
        lambda row, col, widget=se_table: window.open_skills_se_skill_picker(widget, row) if col == 0 else None
    )
    se_table.show()

    xp_cfg = se_cfg.get("xp_info", {}) if isinstance(se_cfg, dict) else {}
    if not isinstance(xp_cfg, dict):
        xp_cfg = {}
    if not bool(xp_cfg.get("enabled", True)):
        return

    character_screen = window.main_ui_layout_config.get("character_screen", {})
    data_map = character_screen.get("data_map", {}) if isinstance(character_screen, dict) else {}
    basic_map = data_map.get("basic", {}) if isinstance(data_map, dict) else {}
    if not isinstance(basic_map, dict):
        basic_map = {}

    default_sheet = "Charakterbogen"
    if isinstance(data_map, dict):
        default_sheet = str(data_map.get("sheet", default_sheet))

    def resolve_mapping_cell(entry, fallback_cell):
        sheet_name = default_sheet
        cell_ref = fallback_cell
        if isinstance(entry, str) and entry.strip():
            cell_ref = entry.strip()
        elif isinstance(entry, dict):
            sheet_name = str(entry.get("sheet", default_sheet))
            mapped_cell = entry.get("cell")
            if isinstance(mapped_cell, str) and mapped_cell.strip():
                cell_ref = mapped_cell.strip()
        return sheet_name, cell_ref

    exp_current_sheet, exp_current_cell = resolve_mapping_cell(basic_map.get("exp_current", "B16"), "B16")
    exp_max_sheet, exp_max_cell = resolve_mapping_cell(basic_map.get("exp_max", "F16"), "F16")

    def parse_int_value(value):
        text = str(value or "").strip()
        if not text:
            return 0
        text = text.replace(",", ".")
        try:
            return int(float(text))
        except Exception:
            return 0

    exp_current_raw = window.get_cache_cell_value(exp_current_sheet, exp_current_cell, 0)
    exp_max_raw = window.get_cache_cell_value(exp_max_sheet, exp_max_cell, 0)
    exp_current = parse_int_value(exp_current_raw)
    exp_max = parse_int_value(exp_max_raw)
    if window.skills_debug_sources:
        log_debug("skills", f"SKILLS UPGRADE XP current={exp_current} max={exp_max}")

    xp_x = window._safe_int(xp_cfg.get("x", x + w + 40), x + w + 40)
    xp_y = window._safe_int(xp_cfg.get("y", y), y)
    xp_w = window._safe_int(xp_cfg.get("w", 260), 260)
    xp_h = window._safe_int(xp_cfg.get("h", 150), 150)
    xp_title = str(xp_cfg.get("title", "XP Info"))
    xp_font_size = window._safe_int(xp_cfg.get("font_size", 16), 16)
    xp_title_font_size = window._safe_int(xp_cfg.get("title_font_size", 18), 18)
    xp_label_color = str(xp_cfg.get("label_color", "#f2d28b"))
    xp_text_color = str(xp_cfg.get("text_color", "#ffffff"))
    xp_value_color = str(xp_cfg.get("value_color", "#7fd0ff"))
    xp_border_color = str(xp_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
    xp_bg = str(xp_cfg.get("background", "rgba(5, 5, 5, 95)"))
    labels_cfg = xp_cfg.get("labels", {})
    if not isinstance(labels_cfg, dict):
        labels_cfg = {}
    label_current = str(labels_cfg.get("current", "Current"))
    label_max = str(labels_cfg.get("max", "Max"))

    xp_frame = QFrame(parent)
    xp_frame.setGeometry(xp_x, xp_y, xp_w, xp_h)
    xp_frame.setStyleSheet(
        f"background: {xp_bg};"
        f"border: 1px solid {xp_border_color};"
        "border-radius: 4px;"
    )
    xp_frame.show()

    window.create_panel_text(
        xp_frame,
        {"x": 10, "y": 8, "w": max(1, xp_w - 20), "h": 28},
        xp_title,
        xp_title_font_size,
        xp_label_color,
        bold=True,
        align="left",
    )

    line_y = 44
    line_h = 28
    window.create_panel_text(
        xp_frame,
        {"x": 10, "y": line_y, "w": 70, "h": line_h},
        f"{label_current}:",
        xp_font_size,
        xp_text_color,
        bold=False,
        align="left",
    )
    window.create_panel_text(
        xp_frame,
        {"x": 85, "y": line_y, "w": max(1, xp_w - 110), "h": line_h},
        str(exp_current),
        xp_font_size,
        xp_value_color,
        bold=True,
        align="left",
    )

    line_y += line_h
    window.create_panel_text(
        xp_frame,
        {"x": 10, "y": line_y, "w": 70, "h": line_h},
        f"{label_max}:",
        xp_font_size,
        xp_text_color,
        bold=False,
        align="left",
    )
    window.create_panel_text(
        xp_frame,
        {"x": 85, "y": line_y, "w": max(1, xp_w - 110), "h": line_h},
        str(exp_max),
        xp_font_size,
        xp_value_color,
        bold=True,
        align="left",
    )

    upgrade_cfg = {}
    if isinstance(se_cfg, dict):
        upgrade_cfg = se_cfg.get("skill_upgrade_info", {})
    if not isinstance(upgrade_cfg, dict):
        upgrade_cfg = {}
    if bool(upgrade_cfg.get("enabled", True)):
        up_x = window._safe_int(upgrade_cfg.get("x", xp_x), xp_x)
        up_y = window._safe_int(upgrade_cfg.get("y", xp_y + xp_h + 12), xp_y + xp_h + 12)
        up_w = window._safe_int(upgrade_cfg.get("w", xp_w), xp_w)
        up_h = window._safe_int(upgrade_cfg.get("h", 300), 300)
        up_title = str(upgrade_cfg.get("title", "Skill Upgrade"))
        max_items = window._safe_int(upgrade_cfg.get("max_items", 999), 999)
        word_wrap = bool(upgrade_cfg.get("word_wrap", True))
        scrollable = bool(upgrade_cfg.get("scrollable", True))
        up_title_font_size = window._safe_int(upgrade_cfg.get("title_font_size", xp_title_font_size), xp_title_font_size)
        up_font_size = window._safe_int(upgrade_cfg.get("font_size", max(12, xp_font_size - 1)), max(12, xp_font_size - 1))
        up_label_color = str(upgrade_cfg.get("label_color", xp_label_color))
        up_text_color = str(upgrade_cfg.get("text_color", xp_text_color))
        up_border_color = str(upgrade_cfg.get("border_color", xp_border_color))
        up_bg = str(upgrade_cfg.get("background", xp_bg))
        muted_color = str(upgrade_cfg.get("muted_color", "#d8d0b0"))

        upgrade_frame = QFrame(parent)
        upgrade_frame.setGeometry(up_x, up_y, up_w, up_h)
        upgrade_frame.setStyleSheet(
            f"background: {up_bg};"
            f"border: 1px solid {up_border_color};"
            "border-radius: 4px;"
        )
        upgrade_frame.show()

        window.create_panel_text(
            upgrade_frame,
            {"x": 10, "y": 8, "w": max(1, up_w - 20), "h": 28},
            up_title,
            up_title_font_size,
            up_label_color,
            bold=True,
            align="left",
        )

        upgrade_result = window.build_se_upgrade_candidates(rows, exp_current)
        status = str(upgrade_result.get("status", "no_upgrade_data"))
        groups = upgrade_result.get("groups", {}) if isinstance(upgrade_result, dict) else {}
        if not isinstance(groups, dict):
            groups = {}

        lines = []
        if status == "no_se_entries":
            lines.append(("Keine SE-Einträge", up_text_color, True))
        elif status == "no_bound_entries":
            lines.append(("Keine gebundenen SE-Einträge", up_text_color, True))
        elif status == "no_costs":
            lines.append(("Keine Upgrade-Kosten gefunden", up_text_color, True))
        elif status == "no_upgrade_data":
            lines.append(("Keine Upgrade-Daten gefunden", up_text_color, True))
        else:
            def add_group(title, items):
                if not items:
                    return
                lines.append((f"{title}:", up_label_color, True))
                for item in items:
                    lines.append(
                        (
                            f'- {item["skill_name"]} — SE {item["available_se"]}/{item["needed_se"]} · XP {item["available_xp"]}/{item["needed_xp"]}',
                            up_text_color,
                            False,
                        )
                    )

            possible_items = list(groups.get("possible", []))
            missing_xp_items = list(groups.get("missing_xp", []))
            missing_se_items = list(groups.get("missing_se", []))
            missing_both_items = list(groups.get("missing_both", []))
            unknown_items = list(groups.get("unknown", []))
            broken_link_items = list(groups.get("broken_link", []))
            add_group("Möglich", possible_items)
            add_group("Fehlt XP", missing_xp_items)
            add_group("Fehlt SE", missing_se_items)
            add_group("Fehlt beides", missing_both_items)
            add_group("Max / keine Stufe bekannt", unknown_items)
            add_group("Ungültiger Skill-Link", broken_link_items)

            if not lines:
                lines.append(("Keine Upgrade-Daten gefunden", up_text_color, True))

        display_lines = []
        more_count = 0
        if max_items > 0:
            display_lines = lines[:max_items]
            more_count = max(0, len(lines) - len(display_lines))
        else:
            display_lines = lines
        if more_count > 0:
            display_lines.append((f"... +{more_count} weitere", muted_color, False))

        html_lines = []
        for text, color, bold in display_lines:
            safe_text = (
                str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            weight = "700" if bold else "400"
            html_lines.append(
                f'<div style="color:{color}; font-size:{up_font_size}px; font-weight:{weight}; margin:2px 0;">{safe_text}</div>'
            )

        content = QTextEdit(upgrade_frame)
        content.setGeometry(10, 42, max(1, up_w - 20), max(1, up_h - 52))
        content.setReadOnly(True)
        content.setLineWrapMode(QTextEdit.WidgetWidth if word_wrap else QTextEdit.NoWrap)
        if not scrollable:
            content.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            content.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setStyleSheet(
            "QTextEdit {"
            f"background: {up_bg};"
            f"color: {up_text_color};"
            f"border: 1px solid {up_border_color};"
            "border-radius: 3px;"
            "padding: 4px;"
            "}"
        )
        content.setHtml("".join(html_lines))
        content.show()

    if window.skills_debug_sources:
        log_debug("skills", f"SKILLS SE XP current={exp_current} max={exp_max}")

def render_skills_table(window, parent, table_cfg, category, attribute_map):
    frame_state = apply_skills_table_frame_if_enabled(window, parent, table_cfg)
    frame_active = bool(frame_state.get("active", False))
    table = QFrame(parent)
    table.setGeometry(
        window._safe_int(table_cfg.get("x", 20), 20),
        window._safe_int(table_cfg.get("y", 80), 80),
        window._safe_int(table_cfg.get("w", 1380), 1380),
        window._safe_int(table_cfg.get("h", 700), 700),
    )
    if frame_active and bool(frame_state.get("remove_old_border_when_active", True)):
        table_background = "transparent" if bool(frame_state.get("transparent_panel_background_when_active", True)) else "rgba(5, 5, 5, 95)"
        table.setStyleSheet(
            f"background: {table_background};"
            "border: none;"
            "border-radius: 0px;"
        )
    else:
        table.setStyleSheet(
            "background: rgba(5, 5, 5, 95);"
            "border: 1px solid rgba(242, 210, 139, 70);"
            "border-radius: 4px;"
        )
    table.show()

    header_h = window._safe_int(table_cfg.get("header_h", 42), 42)
    row_h = window._safe_int(table_cfg.get("row_h", 42), 42)
    max_rows = window._safe_int(table_cfg.get("max_visible_rows", 15), 15)
    font_size = window._safe_int(table_cfg.get("font_size", 17), 17)
    header_font_size = window._safe_int(table_cfg.get("header_font_size", 19), 19)
    header_color = str(table_cfg.get("header_color", "#f2d28b"))
    columns = table_cfg.get("columns", {})
    if not isinstance(columns, dict):
        columns = {}
    row_fields_cfg = table_cfg.get("row_fields", {})
    if not isinstance(row_fields_cfg, dict):
        row_fields_cfg = {}
    inset_cfg = table_cfg.get("content_inset", {})
    if not isinstance(inset_cfg, dict):
        inset_cfg = {}
    inset_left = max(0, window._safe_int(inset_cfg.get("left", 0), 0))
    inset_top = max(0, window._safe_int(inset_cfg.get("top", 0), 0))
    inset_right = max(0, window._safe_int(inset_cfg.get("right", 0), 0))
    inset_bottom = max(0, window._safe_int(inset_cfg.get("bottom", 0), 0))
    content_x = inset_left
    content_y = inset_top
    content_w = max(1, table.width() - inset_left - inset_right)
    content_h = max(1, table.height() - inset_top - inset_bottom)

    header_bg = QFrame(table)
    header_bg.setGeometry(content_x, content_y, content_w, header_h)
    header_bg.setStyleSheet(
        "background: rgba(24, 16, 8, 175); border-bottom: 1px solid rgba(242, 210, 139, 85);"
    )
    header_bg.show()

    for column_id in ("skill", "attributes", "value", "specialization", "note"):
        col_cfg = columns.get(column_id, {})
        window.create_panel_text(
            table,
            {
                "x": content_x + window._safe_int(col_cfg.get("x", 0), 0),
                "y": content_y,
                "w": window._safe_int(col_cfg.get("w", 120), 120),
                "h": header_h,
            },
            str(col_cfg.get("title", column_id)),
            header_font_size,
            header_color,
            bold=True,
            align="center" if column_id in ("attributes", "value") else "left",
        )

    if not window.loader.cell_cache:
        window.create_panel_text(
            table,
            {"x": content_x, "y": content_y + header_h, "w": content_w, "h": min(row_h * 2, max(1, content_h - header_h))},
            "Kein Charaktercache geladen",
            font_size,
            str(table_cfg.get("note_color", "#d8d0b0")),
            bold=True,
            align="center",
        )
        if window.skills_debug_sources:
            log_debug("skills", "no Fertigkeiten sheet loaded")
        return
    if not isinstance(window.loader.cell_cache.get("Fertigkeiten"), dict):
        window.create_panel_text(
            table,
            {"x": content_x, "y": content_y + header_h, "w": content_w, "h": min(row_h * 2, max(1, content_h - header_h))},
            "Keine Fertigkeiten-Daten gefunden",
            font_size,
            str(table_cfg.get("note_color", "#d8d0b0")),
            bold=True,
            align="center",
        )
        log_debug("skills", "no Fertigkeiten sheet loaded")
        return

    skills = category.get("skills", []) if isinstance(category, dict) else []
    if not isinstance(skills, list):
        skills = []
    category_id = str(category.get("id", "")) if isinstance(category, dict) else ""
    visible_skills = skills[:max_rows]
    if window.skills_debug_sources:
        log_debug("skills", f"SKILLS RENDER category={category_id}")
        log_debug("skills", f"SKILLS RENDER source rows={len(skills)}")
        log_debug("skills", f"SKILLS RENDER visible rows={len(visible_skills)}")
    if len(skills) > max_rows:
        if window.skills_debug_sources:
            log_debug("skills", f"rows truncated category={category_id}")

    row_colors = ("rgba(8, 8, 8, 125)", "rgba(20, 20, 20, 105)")
    current_y = content_y + header_h
    for index, skill in enumerate(visible_skills):
        if not isinstance(skill, dict):
            continue
        y = current_y
        row_bg = QFrame(table)
        row_bg.setGeometry(content_x, y, content_w, row_h)
        row_bg.setStyleSheet(
            f"background: {row_colors[index % 2]};"
            "border-bottom: 1px solid rgba(255, 255, 255, 24);"
        )
        row_bg.lower()
        row_bg.show()

        skill_name = str(skill.get("name", ""))
        attributes = skill.get("attributes", [])
        if not isinstance(attributes, list):
            attributes = []
        attribute_sum = window.calculate_skill_attribute_sum(skill, attribute_map)
        source_key = window.get_skill_source_key(category_id, skill)
        source_info = window.skill_source_infos.get(source_key)
        if not isinstance(source_info, dict):
            source_info = window.build_skill_source_info(skill, category_id, attribute_map)
        display_name = source_info.get("display_name", skill_name)
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = skill_name
        sheet_value = source_info.get("calculated_value")
        if sheet_value is None:
            display_value = "0" if source_info.get("row") is not None else ""
            if window.skills_debug_sources:
                log_debug(
                    "skills",
                    f"SKILLS FALLBACK {display_name} no sheet value, using: "
                    f"{display_value if display_value else 'blank'}",
                )
        else:
            display_value = window.format_character_display_value(sheet_value, "int")
            try:
                sheet_int_value = int(display_value)
            except Exception:
                sheet_int_value = sheet_value
            if sheet_int_value != attribute_sum:
                if window.skills_debug_sources:
                    log_debug(
                        "skills",
                        f"SKILLS DIFF {display_name} sheet={sheet_value} "
                        f"attribute_sum={attribute_sum} display={display_value}",
                    )
            else:
                if window.skills_debug_sources:
                    log_debug(
                        "skills",
                        f"SKILLS OK {display_name} sheet={sheet_value} "
                        f"attribute_sum={attribute_sum} display={display_value}",
                    )
        if window.skills_debug_sources:
            log_debug("skills", f"skill value {display_name} {attributes[:4]} -> {display_value}")
            log_debug(
                "skills",
                f"SKILLS ROW row={source_info.get('row')} name={display_name} value={display_value}",
            )
        slot_values = source_info.get("display_attribute_slots", [])
        if not isinstance(slot_values, list) or len(slot_values) < 4:
            row_value = source_info.get("row")
            block = window.get_skill_block_config_for_row(row_value, category_id) if row_value is not None else None
            slot_values = window.get_skill_attribute_slot_values_from_row(row_value, block) if row_value is not None else ["", "", "", ""]
        slot_values = (slot_values + ["", "", "", ""])[:4]
        display_specialization = source_info.get("display_specialization", "")
        display_note = source_info.get("display_note", "")

        skill_col = columns.get("skill", {})
        attr_col = columns.get("attributes", {})
        value_col = columns.get("value", {})
        spec_col = columns.get("specialization", {})
        note_col = columns.get("note", {})
        skill_pad_l = max(0, window._safe_int(skill_col.get("text_padding_left", 8), 8))
        skill_pad_r = max(0, window._safe_int(skill_col.get("text_padding_right", 6), 6))
        spec_pad_l = max(0, window._safe_int(spec_col.get("text_padding_left", 8), 8))
        spec_pad_r = max(0, window._safe_int(spec_col.get("text_padding_right", 8), 8))
        note_pad_l = max(0, window._safe_int(note_col.get("text_padding_left", 8), 8))
        note_pad_r = max(0, window._safe_int(note_col.get("text_padding_right", 8), 8))
        spec_x = content_x + window._safe_int(spec_col.get("x", 690), 690) + spec_pad_l
        spec_w = max(1, window._safe_int(spec_col.get("w", 470), 470) - spec_pad_l - spec_pad_r)
        note_x = content_x + window._safe_int(note_col.get("x", 1170), 1170) + note_pad_l
        note_w = max(1, window._safe_int(note_col.get("w", 210), 210) - note_pad_l - note_pad_r)
        row_height = row_h
        row_bg.setGeometry(content_x, y, content_w, row_height)

        skill_x = content_x + window._safe_int(skill_col.get("x", 0), 0) + skill_pad_l
        skill_w = max(1, window._safe_int(skill_col.get("w", 360), 360) - skill_pad_l - skill_pad_r)
        skill_button = QPushButton(table)
        skill_button.setGeometry(skill_x, y, skill_w, row_height)
        skill_button.setText(display_name)
        skill_button.setFlat(True)
        skill_button.setCursor(Qt.PointingHandCursor)
        skill_button.setStyleSheet(
            "QPushButton {"
            "background: transparent;"
            "border: none;"
            f"color: {str(table_cfg.get('skill_name_color', '#f2d28b'))};"
            f"font-size: {font_size}px;"
            "font-weight: 700;"
            "text-align: left;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { border: 1px solid rgba(242, 210, 139, 60); }"
        )
        skill_button.clicked.connect(
            lambda checked=False, sk=source_key: window.on_skill_row_roll_clicked(sk)
        )
        skill_button.setToolTip(display_name if display_name else "")
        skill_button.show()

        slot_w = window._safe_int(attr_col.get("slot_w", 42), 42)
        slot_gap = window._safe_int(attr_col.get("slot_gap", 8), 8)
        attr_x = content_x + window._safe_int(attr_col.get("x", 370), 370)
        attr_field_cfg = row_fields_cfg.get("attribute_slot", {}) if isinstance(row_fields_cfg.get("attribute_slot", {}), dict) else {}
        slot_box_w = max(1, window._safe_int(attr_field_cfg.get("w", slot_w), slot_w))
        slot_box_h = max(1, window._safe_int(attr_field_cfg.get("h", max(1, row_height - 10)), max(1, row_height - 10)))
        attribute_cells = source_info.get("attribute_cells", [])
        if not isinstance(attribute_cells, list):
            attribute_cells = []
        for slot_index in range(4):
            letter = str(slot_values[slot_index] or "")
            slot_x = attr_x + slot_index * (slot_w + slot_gap)
            slot_h = slot_box_h
            slot_y = y + int((row_height - slot_h) / 2)
            slot_frame_x = slot_x + int((slot_w - slot_box_w) / 2)
            slot_frame_active = apply_skills_row_field_frame_if_enabled(
                window,
                table,
                row_fields_cfg,
                "attribute_slot",
                {"x": slot_frame_x, "y": slot_y, "w": slot_box_w, "h": slot_h},
            )
            slot = QPushButton(table)
            slot.setGeometry(
                slot_frame_x,
                slot_y,
                slot_box_w,
                slot_h,
            )
            slot.setStyleSheet(
                "QPushButton {"
                f"background: {'transparent' if slot_frame_active else 'rgba(0, 0, 0, 105)'};"
                f"border: {'none' if slot_frame_active else '1px solid rgba(255, 255, 255, 42)'};"
                f"border-radius: {'0px' if slot_frame_active else '3px'};"
                f"color: {str(table_cfg.get('attribute_color', '#ffffff'))};"
                f"font-size: {font_size}px;"
                "font-weight: 700;"
                "padding: 0px;"
                "}"
                "QPushButton:hover { border: 1px solid rgba(242, 210, 139, 140); }"
            )
            slot.setText(letter)
            slot.setFlat(True)
            slot.setProperty("source_key", source_key)
            slot.setProperty("slot_index", slot_index)
            slot.setProperty("sheet_name", "Fertigkeiten")
            slot.setProperty(
                "cell_ref",
                str(attribute_cells[slot_index]).strip().upper()
                if slot_index < len(attribute_cells)
                else "",
            )
            if window.is_skill_attribute_slot_editable(source_info, slot_index):
                slot.setCursor(Qt.PointingHandCursor)
                slot.setToolTip("Attribut ändern")
                slot.clicked.connect(
                    lambda checked=False, widget=slot: window.open_skill_attribute_slot_menu(widget)
                )
            else:
                slot.setCursor(Qt.ArrowCursor)
            slot.show()

        value_x = content_x + window._safe_int(value_col.get("x", 600), 600)
        value_w = window._safe_int(value_col.get("w", 80), 80)
        value_field_cfg = row_fields_cfg.get("value", {}) if isinstance(row_fields_cfg.get("value", {}), dict) else {}
        value_box_w = max(1, window._safe_int(value_field_cfg.get("w", value_w), value_w))
        value_box_h = max(1, window._safe_int(value_field_cfg.get("h", max(1, row_height - 10)), max(1, row_height - 10)))
        value_box_x = value_x + int((value_w - value_box_w) / 2)
        value_box_y = y + int((row_height - value_box_h) / 2)
        value_text_offset_x = window._safe_int(value_field_cfg.get("text_offset_x", 0), 0)
        value_text_offset_y = window._safe_int(value_field_cfg.get("text_offset_y", 0), 0)
        value_text_align = str(value_field_cfg.get("text_align", "center") or "center")
        value_frame_cfg = value_field_cfg.get("frame", {}) if isinstance(value_field_cfg.get("frame", {}), dict) else {}
        value_frame_enabled = bool(value_frame_cfg.get("enabled", False))
        value_frame_pixmap = (
            _optional_theme_ui_pixmap(window, value_frame_cfg.get("asset", ""))
            if value_frame_enabled
            else None
        )
        value_frame_active = value_frame_pixmap is not None
        value_fallback_border = bool(value_frame_cfg.get("fallback_border", False))

        value_container = QWidget(table)
        value_container.setGeometry(value_box_x, value_box_y, value_box_w, value_box_h)
        value_container.setStyleSheet("background: transparent; border: none;")

        if value_frame_active:
            value_bg = QLabel(value_container)
            value_bg.setGeometry(0, 0, value_box_w, value_box_h)
            src = _apply_source_crop(window, value_frame_pixmap, value_frame_cfg)
            render_mode = str(value_frame_cfg.get("render_mode", "fit") or "fit").strip().lower()
            if render_mode == "nine_slice":
                value_bg.setPixmap(_render_nine_slice_pixmap(window, src, value_box_w, value_box_h, value_frame_cfg))
            else:
                value_bg.setPixmap(_render_fit_pixmap(src, value_box_w, value_box_h, value_frame_cfg))
            value_bg.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            value_bg.show()

        value_label = QLabel(value_container)
        value_label.setGeometry(value_text_offset_x, value_text_offset_y, value_box_w, value_box_h)
        value_label.setText(display_value)
        align_key = value_text_align.strip().lower()
        if align_key == "left":
            value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        elif align_key == "right":
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(
            "QLabel {"
            "background: transparent;"
            f"border: {'none' if value_frame_active or not value_fallback_border else '1px solid rgba(127, 208, 255, 60)'};"
            f"color: {str(table_cfg.get('value_color', '#7fd0ff'))};"
            f"font-size: {font_size}px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
        )
        value_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        value_label.show()

        value_button = QPushButton(value_container)
        value_button.setGeometry(0, 0, value_box_w, value_box_h)
        value_button.setText("")
        value_button.setFlat(True)
        value_button.setCursor(Qt.PointingHandCursor)
        value_button.setStyleSheet(
            "QPushButton {"
            "background: transparent;"
            "border: none;"
            "color: transparent;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { background: transparent; border: none; }"
        )
        value_button.clicked.connect(
            lambda checked=False, sk=source_key: window.on_skill_row_roll_clicked(sk)
        )
        value_button.show()
        value_button.raise_()
        value_container.show()
        value_container.raise_()
        spec_text = str(display_specialization)
        spec_frame_active = apply_skills_row_field_frame_if_enabled(
            window,
            table,
            row_fields_cfg,
            "specialization",
            {"x": spec_x, "y": y + 2, "w": spec_w, "h": max(24, row_height - 4)},
        )
        if window.is_skill_specialization_editable(source_info):
            spec_editor = InlineTextEdit(
                on_commit=lambda new_text, old_text, sk=source_key: window.save_skill_text_cell_value(
                    sk, "specialization", new_text, old_text
                ),
                parent=table,
            )
            spec_editor.setGeometry(spec_x, y + 2, spec_w, max(24, row_height - 4))
            spec_editor.set_initial_text(spec_text)
            spec_editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            spec_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            spec_editor.setStyleSheet(
                "QTextEdit {"
                "background: transparent;"
                f"border: {'none' if spec_frame_active else '1px solid rgba(242, 210, 139, 40)'};"
                f"color: {str(table_cfg.get('specialization_color', '#ffffff'))};"
                f"font-size: {font_size}px;"
                "font-weight: 500;"
                "padding: 0px;"
                "}"
                "QTextEdit:focus { border: 1px solid rgba(242, 210, 139, 120); }"
            )
            spec_editor.setToolTip(spec_text if spec_text else "Spezialisierung bearbeiten")
            spec_editor.show()
        else:
            spec_label = window.create_panel_text(
                table,
                {
                    "x": spec_x,
                    "y": y,
                    "w": spec_w,
                    "h": row_height,
                },
                spec_text,
                font_size,
                str(table_cfg.get("specialization_color", "#ffffff")),
            )
            spec_label.setToolTip(spec_text if spec_text else "")
        note_text = str(display_note)
        note_label = window.create_panel_text(
            table,
            {
                "x": note_x,
                "y": y,
                "w": note_w,
                "h": row_height,
            },
            note_text,
            font_size,
            str(table_cfg.get("note_color", "#d8d0b0")),
        )
        note_label.setToolTip(note_text if note_text else "")
        current_y += row_height
