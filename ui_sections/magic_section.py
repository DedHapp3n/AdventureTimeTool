from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QFrame, QLineEdit, QLabel, QStyledItemDelegate, QTableWidget, QTableWidgetItem


def render_magic_section(parent, layout_config, default_screen_cfg, callbacks=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    safe_int = callbacks.get("safe_int")
    if not callable(safe_int):
        safe_int = _safe_int
    create_panel_text = callbacks.get("create_panel_text")
    analyze_magic_sheet = callbacks.get("analyze_magic_sheet")
    clear_table_bindings = callbacks.get("clear_table_bindings")

    if callable(clear_table_bindings):
        clear_table_bindings()

    screen_cfg = layout_config.get("magic_screen", {}) if isinstance(layout_config, dict) else {}
    if not isinstance(screen_cfg, dict):
        screen_cfg = default_screen_cfg if isinstance(default_screen_cfg, dict) else {}

    screen = QFrame(parent)
    screen.setGeometry(
        safe_int(screen_cfg.get("x", 30), 30),
        safe_int(screen_cfg.get("y", 25), 25),
        safe_int(screen_cfg.get("w", 1400), 1400),
        safe_int(screen_cfg.get("h", 820), 820),
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
                "w": safe_int(title_cfg.get("w", 1400), 1400),
                "h": safe_int(title_cfg.get("h", 38), 38),
            },
            str(title_cfg.get("text", "Magie")),
            safe_int(title_cfg.get("font_size", 24), 24),
            str(title_cfg.get("color", "#f2d28b")),
            bold=True,
            align=str(title_cfg.get("align", "center")),
        )

    analysis = analyze_magic_sheet() if callable(analyze_magic_sheet) else {}
    if not isinstance(analysis, dict):
        analysis = {}
    if not str(analysis.get("sheet", "") or "").strip():
        if callable(create_panel_text):
            create_panel_text(
                screen,
                {"x": 20, "y": 80, "w": 1200, "h": 38},
                "Magie-Sheet nicht gefunden",
                20,
                "#f2d28b",
                bold=True,
                align="left",
            )
        return screen

    upgrade_cfg = screen_cfg.get("upgrade_table", {})
    render_magic_upgrade_table(
        screen,
        upgrade_cfg,
        analysis.get("upgrade_table", {}).get("rows", []),
        callbacks,
    )

    spell_cfg = screen_cfg.get("spell_table", {})
    spell_data = analysis.get("spells", {})
    render_magic_spell_table(
        screen,
        spell_cfg,
        analysis.get("sheet", "Magie"),
        spell_data.get("rows", []),
        spell_data.get("mapping", {}),
        callbacks,
    )
    return screen


def handle_magic_spell_table_item_changed(table, row_index, column_index, callbacks=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    is_rendering = callbacks.get("is_rendering")
    if callable(is_rendering) and is_rendering():
        return
    get_table_binding = callbacks.get("get_table_binding")
    binding = get_table_binding(table) if callable(get_table_binding) else {}
    if not isinstance(binding, dict):
        return
    rows = binding.get("rows", [])
    if not isinstance(rows, list) or row_index < 0 or row_index >= len(rows):
        return
    column_order = binding.get("column_order", [])
    if column_index < 0 or column_index >= len(column_order):
        return
    key = str(column_order[column_index])
    row_data = rows[row_index]
    if not isinstance(row_data, dict):
        return
    cells = row_data.get("cells", {})
    if not isinstance(cells, dict):
        return
    cell_ref = str(cells.get(key, "") or "").strip().upper()
    print_mapping_enabled = callbacks.get("print_mapping_enabled")
    log_debug = callbacks.get("log_debug")
    if not cell_ref:
        if callable(print_mapping_enabled) and print_mapping_enabled() and callable(log_debug):
            source_row = row_data.get("row_index", row_data.get("row", row_index))
            log_debug("magic", f"MAGIC EDIT SKIP no cell_ref row={source_row} column={key}")
        return
    item = table.item(row_index, column_index)
    if item is None:
        return
    new_value = str(item.text() or "")
    old_value = str(item.data(Qt.UserRole) or "")
    if new_value == old_value:
        return
    source_row = row_data.get("row_index", row_data.get("row", row_index))
    if callable(print_mapping_enabled) and print_mapping_enabled() and callable(log_debug):
        log_debug("magic", f'MAGIC EDIT row={source_row} column={key} cell={cell_ref} old="{old_value}" new="{new_value}"')
    save_cell_value = callbacks.get("save_cell_value")
    if callable(save_cell_value):
        save_cell_value(str(binding.get("sheet", "Magie") or "Magie"), cell_ref, new_value)
    row_data[key] = new_value
    row_data.setdefault("values", {})[key] = new_value
    item.setData(Qt.UserRole, new_value)
    if callable(print_mapping_enabled) and print_mapping_enabled() and callable(log_debug):
        log_debug("magic", "MAGIC SAVE active character saved")


def render_magic_upgrade_table(parent, table_cfg, upgrade_rows, callbacks=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    safe_int = callbacks.get("safe_int")
    if not callable(safe_int):
        safe_int = _safe_int
    create_panel_text = callbacks.get("create_panel_text")
    if not isinstance(table_cfg, dict) or not bool(table_cfg.get("enabled", True)):
        return

    panel_rect = {
        "x": safe_int(table_cfg.get("x", 20), 20),
        "y": safe_int(table_cfg.get("y", 50), 50),
        "w": safe_int(table_cfg.get("w", 760), 760),
        "h": safe_int(table_cfg.get("h", 250), 250),
    }
    _create_magic_frame_label(parent, table_cfg.get("frame", {}), panel_rect, safe_int)

    panel = QFrame(parent)
    panel.setGeometry(
        panel_rect["x"],
        panel_rect["y"],
        panel_rect["w"],
        panel_rect["h"],
    )
    panel.setStyleSheet("background: transparent; border: none;")
    panel.show()

    if callable(create_panel_text):
        title_cfg = table_cfg.get("title_area", {}) if isinstance(table_cfg.get("title_area", {}), dict) else {}
        create_panel_text(
            panel,
            {
                "x": safe_int(title_cfg.get("x", 18), 18),
                "y": safe_int(title_cfg.get("y", 10), 10),
                "w": safe_int(title_cfg.get("w", panel.width() - 36), panel.width() - 36),
                "h": safe_int(title_cfg.get("h", 30), 30),
            },
            str(table_cfg.get("title", "Upgrade-Tabelle")),
            safe_int(table_cfg.get("title_font_size", 18), 18),
            str(table_cfg.get("header_color", "#f2d28b")),
            bold=True,
            align="left",
        )

    inner = table_cfg.get("inner", {}) if isinstance(table_cfg.get("inner", {}), dict) else {}
    inner_x = safe_int(inner.get("x", 18), 18)
    inner_y = safe_int(inner.get("y", 48), 48)
    inner_right = safe_int(inner.get("right", 18), 18)
    inner_bottom = safe_int(inner.get("bottom", 18), 18)
    table = QTableWidget(panel)
    table.setGeometry(inner_x, inner_y, max(80, panel.width() - inner_x - inner_right), max(60, panel.height() - inner_y - inner_bottom))
    row_count = len(upgrade_rows) if isinstance(upgrade_rows, list) and upgrade_rows else 1
    max_cols = 0
    for row_data in (upgrade_rows or []):
        if isinstance(row_data, dict):
            max_cols = max(max_cols, len(row_data.get("values", [])))
    max_cols = max(1, max_cols)
    table.setRowCount(row_count)
    table.setColumnCount(1 + max_cols)
    headers = ["Upgrade"] + [f"Wert {i+1}" for i in range(max_cols)]
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectItems)
    table.setSelectionMode(QAbstractItemView.NoSelection)
    table.setWordWrap(True)
    table.setShowGrid(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
    table.horizontalHeader().setStretchLastSection(False)
    table.setStyleSheet(_magic_table_stylesheet(table_cfg, safe_int))
    table.viewport().setStyleSheet(f"background: {str(table_cfg.get('table_background', table_cfg.get('background', 'rgba(5, 5, 5, 95)')))};")
    header_h = safe_int(table_cfg.get("header_h", 30), 30)
    table.horizontalHeader().setFixedHeight(header_h)

    group_gap_color = _magic_qcolor(str(table_cfg.get("group_separator_color", "rgba(242, 210, 139, 34)")))
    for row_index, row_data in enumerate(upgrade_rows or []):
        label_item = QTableWidgetItem(str(row_data.get("label", "") or ""))
        label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
        label_item.setForeground(QColor(str(table_cfg.get("header_color", "#f2d28b"))))
        if str(row_data.get("label", "") or "").lower().startswith("scale up") and group_gap_color.isValid():
            label_item.setBackground(QBrush(group_gap_color))
        table.setItem(row_index, 0, label_item)
        values = row_data.get("values", [])
        for value_index in range(max_cols):
            value = str(values[value_index] if value_index < len(values) else "")
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setForeground(QColor(str(table_cfg.get("value_color", "#7fd0ff"))))
            item.setTextAlignment(Qt.AlignCenter)
            if str(row_data.get("label", "") or "").lower().startswith("scale up") and group_gap_color.isValid():
                item.setBackground(QBrush(group_gap_color))
            table.setItem(row_index, value_index + 1, item)

    row_h = safe_int(table_cfg.get("row_h", 28), 28)
    table.verticalHeader().setDefaultSectionSize(row_h)
    for row_index in range(row_count):
        table.setRowHeight(row_index, row_h)
    _apply_magic_column_widths(table, table_cfg, ["upgrade"] + [f"value_{i+1}" for i in range(max_cols)], safe_int)
    required_h = header_h + (row_count * row_h) + 8
    needs_v_scroll = required_h > table.height()
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if needs_v_scroll else Qt.ScrollBarAlwaysOff)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded if _configured_magic_width(table_cfg, ["upgrade"] + [f"value_{i+1}" for i in range(max_cols)], safe_int) > table.width() - 4 else Qt.ScrollBarAlwaysOff)
    table.show()


def render_magic_spell_table(parent, table_cfg, sheet_name, rows, mapping, callbacks=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    safe_int = callbacks.get("safe_int")
    if not callable(safe_int):
        safe_int = _safe_int
    create_panel_text = callbacks.get("create_panel_text")
    set_rendering = callbacks.get("set_rendering")
    register_table_binding = callbacks.get("register_table_binding")
    if not isinstance(table_cfg, dict) or not bool(table_cfg.get("enabled", True)):
        return

    panel_rect = {
        "x": safe_int(table_cfg.get("x", 20), 20),
        "y": safe_int(table_cfg.get("y", 330), 330),
        "w": safe_int(table_cfg.get("w", 1360), 1360),
        "h": safe_int(table_cfg.get("h", 450), 450),
    }
    _create_magic_frame_label(parent, table_cfg.get("frame", {}), panel_rect, safe_int)

    panel = QFrame(parent)
    panel.setGeometry(
        panel_rect["x"],
        panel_rect["y"],
        panel_rect["w"],
        panel_rect["h"],
    )
    panel.setStyleSheet("background: transparent; border: none;")
    panel.show()

    if callable(create_panel_text):
        title_cfg = table_cfg.get("title_area", {}) if isinstance(table_cfg.get("title_area", {}), dict) else {}
        create_panel_text(
            panel,
            {
                "x": safe_int(title_cfg.get("x", 18), 18),
                "y": safe_int(title_cfg.get("y", 10), 10),
                "w": safe_int(title_cfg.get("w", panel.width() - 36), panel.width() - 36),
                "h": safe_int(title_cfg.get("h", 30), 30),
            },
            str(table_cfg.get("title", "Magie")),
            safe_int(table_cfg.get("title_font_size", 18), 18),
            str(table_cfg.get("header_color", "#f2d28b")),
            bold=True,
            align="left",
        )

    columns_cfg = table_cfg.get("columns", {})
    if not isinstance(columns_cfg, dict):
        columns_cfg = {}
    column_order = ["school", "info", "prepared_spell", "charge", "duration", "effect"]
    headers = [str(columns_cfg.get(key, {}).get("title", key)) for key in column_order]

    min_rows = max(1, safe_int(table_cfg.get("min_rows", 14), 14))
    visible_rows = list(rows) if isinstance(rows, list) else []
    while len(visible_rows) < min_rows:
        visible_rows.append({"row": 0, "row_index": 0, "values": {}, "cells": {}, "school": "", "info": "", "prepared_spell": "", "charge": "", "duration": "", "effect": ""})

    table = QTableWidget(panel)
    inner = table_cfg.get("inner", {}) if isinstance(table_cfg.get("inner", {}), dict) else {}
    inner_x = safe_int(inner.get("x", 18), 18)
    inner_y = safe_int(inner.get("y", 48), 48)
    inner_right = safe_int(inner.get("right", 18), 18)
    inner_bottom = safe_int(inner.get("bottom", 18), 18)
    table.setGeometry(inner_x, inner_y, max(120, panel.width() - inner_x - inner_right), max(120, panel.height() - inner_y - inner_bottom))
    table.setRowCount(len(visible_rows))
    table.setColumnCount(len(column_order))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setWordWrap(True)
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectItems)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(
        QAbstractItemView.DoubleClicked
        | QAbstractItemView.EditKeyPressed
        | QAbstractItemView.SelectedClicked
    )
    table.setFocusPolicy(Qt.StrongFocus)
    table.setShowGrid(True)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setFixedHeight(safe_int(table_cfg.get("header_h", 32), 32))
    table.setStyleSheet(_magic_table_stylesheet(table_cfg, safe_int))
    table.viewport().setStyleSheet(f"background: {str(table_cfg.get('table_background', table_cfg.get('background', 'rgba(5, 5, 5, 95)')))};")
    table.setItemDelegate(_MagicCellDelegate(table, table_cfg, safe_int))

    if callable(set_rendering):
        set_rendering(True)
    try:
        for row_index, row_data in enumerate(visible_rows):
            values = row_data.get("values", {})
            cells = row_data.get("cells", {})
            if not isinstance(values, dict):
                values = {}
            if not isinstance(cells, dict):
                cells = {}
            for col_index, key in enumerate(column_order):
                value = str(values.get(key, row_data.get(key, "")) or "")
                item = QTableWidgetItem(value)
                item.setToolTip(value if value else "")
                item.setData(Qt.UserRole, value)
                can_edit = bool(table_cfg.get("editable", True)) and bool(str(cells.get(key, "") or "").strip())
                if can_edit:
                    item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                else:
                    item.setFlags((item.flags() & ~Qt.ItemIsEditable) | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                color = str(table_cfg.get("value_color", "#7fd0ff")) if key in ("charge", "duration") else str(table_cfg.get("text_color", "#ffffff"))
                item.setForeground(QColor(color))
                if key in ("charge", "duration"):
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                table.setItem(row_index, col_index, item)
    finally:
        if callable(set_rendering):
            set_rendering(False)

    _apply_magic_column_widths(table, table_cfg, column_order, safe_int)
    min_row_h = safe_int(table_cfg.get("row_h", max(30, safe_int(table_cfg.get("font_size", 14), 14) * 2)), 30)
    max_row_h = safe_int(table_cfg.get("max_row_h", 54), 54)
    table.verticalHeader().setDefaultSectionSize(min_row_h)
    table.resizeRowsToContents()
    for row_index in range(table.rowCount()):
        height = max(min_row_h, table.rowHeight(row_index))
        if max_row_h > 0:
            height = min(max_row_h, height)
        table.setRowHeight(row_index, height)

    binding = {
        "sheet": str(sheet_name or "Magie"),
        "rows": visible_rows,
        "mapping": mapping if isinstance(mapping, dict) else {},
        "column_order": column_order,
    }
    if callable(register_table_binding):
        register_table_binding(table, binding)
    table.itemChanged.connect(
        lambda item, widget=table: handle_magic_spell_table_item_changed(widget, item.row(), item.column(), callbacks)
    )
    table.show()


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)


def _optional_magic_ui_pixmap(parent, asset_rel_path):
    asset_name = str(asset_rel_path or "").strip().replace("\\", "/").lstrip("/")
    if not asset_name:
        return None
    try:
        window = parent.window()
        if hasattr(window, "load_ui_pixmap"):
            pixmap = window.load_ui_pixmap(asset_name)
            if pixmap is not None and not pixmap.isNull():
                return pixmap
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


def _magic_frame_opacity(frame_cfg):
    try:
        opacity = float(frame_cfg.get("opacity", 1.0))
    except Exception:
        opacity = 1.0
    return max(0.0, min(1.0, opacity))


def _magic_qcolor(value):
    raw = str(value or "").strip()
    if raw.lower().startswith("rgba(") and raw.endswith(")"):
        pieces = [piece.strip() for piece in raw[5:-1].split(",")]
        if len(pieces) == 4:
            try:
                return QColor(
                    max(0, min(255, int(pieces[0]))),
                    max(0, min(255, int(pieces[1]))),
                    max(0, min(255, int(pieces[2]))),
                    max(0, min(255, int(pieces[3]))),
                )
            except Exception:
                return QColor()
    return QColor(raw)


def _render_magic_nine_slice_pixmap(src, target_w, target_h, frame_cfg, safe_int):
    slice_cfg = frame_cfg.get("slice", {}) if isinstance(frame_cfg.get("slice", {}), dict) else {}
    src_w = max(1, src.width())
    src_h = max(1, src.height())
    left = max(0, min(safe_int(slice_cfg.get("left", 16), 16), src_w))
    right = max(0, min(safe_int(slice_cfg.get("right", 16), 16), src_w - left))
    top = max(0, min(safe_int(slice_cfg.get("top", 16), 16), src_h))
    bottom = max(0, min(safe_int(slice_cfg.get("bottom", 16), 16), src_h - top))
    target_w = max(1, target_w)
    target_h = max(1, target_h)
    smooth_scaling = bool(frame_cfg.get("smooth_scaling", True))
    center_src_w = max(0, src_w - left - right)
    center_src_h = max(0, src_h - top - bottom)
    center_dst_w = max(0, target_w - left - right)
    center_dst_h = max(0, target_h - top - bottom)
    rendered = QPixmap(target_w, target_h)
    rendered.fill(Qt.transparent)
    painter = QPainter(rendered)
    if smooth_scaling:
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setOpacity(_magic_frame_opacity(frame_cfg))

    def draw_slice(dx, dy, dw, dh, sx, sy, sw, sh):
        if dw > 0 and dh > 0 and sw > 0 and sh > 0:
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


def _create_magic_frame_label(parent, frame_cfg, rect_cfg, safe_int):
    if not isinstance(frame_cfg, dict) or not bool(frame_cfg.get("enabled", False)):
        return None
    src = _optional_magic_ui_pixmap(parent, frame_cfg.get("asset", ""))
    if src is None:
        return None
    margin = max(0, safe_int(frame_cfg.get("margin", 0), 0))
    x = safe_int(rect_cfg.get("x", 0), 0) - margin
    y = safe_int(rect_cfg.get("y", 0), 0) - margin
    w = max(1, safe_int(rect_cfg.get("w", 1), 1) + margin * 2)
    h = max(1, safe_int(rect_cfg.get("h", 1), 1) + margin * 2)
    frame = QLabel(parent)
    frame.setGeometry(x, y, w, h)
    render_mode = str(frame_cfg.get("render_mode", "nine_slice") or "nine_slice").strip().lower()
    if render_mode == "nine_slice":
        frame.setPixmap(_render_magic_nine_slice_pixmap(src, w, h, frame_cfg, safe_int))
    else:
        frame.setPixmap(src.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation if bool(frame_cfg.get("smooth_scaling", True)) else Qt.FastTransformation))
    frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    frame.show()
    return frame


def _magic_scrollbar_stylesheet(scrollbar_cfg):
    if not isinstance(scrollbar_cfg, dict):
        scrollbar_cfg = {}
    w = str(scrollbar_cfg.get("w", 12))
    bg = str(scrollbar_cfg.get("background", "#17110f"))
    handle = str(scrollbar_cfg.get("handle", "#6c4a22"))
    handle_hover = str(scrollbar_cfg.get("handle_hover", "#8c622f"))
    minimum = str(scrollbar_cfg.get("minimum_handle", 24))
    return (
        f"QScrollBar:vertical {{ background: {bg}; width: {w}px; margin: 0px; }}"
        f"QScrollBar::handle:vertical {{ background: {handle}; min-height: {minimum}px; }}"
        f"QScrollBar::handle:vertical:hover {{ background: {handle_hover}; }}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        f"QScrollBar:horizontal {{ background: {bg}; height: {w}px; margin: 0px; }}"
        f"QScrollBar::handle:horizontal {{ background: {handle}; min-width: {minimum}px; }}"
        f"QScrollBar::handle:horizontal:hover {{ background: {handle_hover}; }}"
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }"
        "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }"
    )


def _magic_table_stylesheet(table_cfg, safe_int):
    selection_cfg = table_cfg.get("selection", {}) if isinstance(table_cfg.get("selection", {}), dict) else {}
    selection_bg = str(selection_cfg.get("background", "rgba(242, 210, 139, 45)"))
    selection_text = str(selection_cfg.get("text_color", "#ffffff"))
    selection_border = str(selection_cfg.get("border_color", "rgba(242, 210, 139, 120)"))
    selection_enabled = bool(selection_cfg.get("enabled", True))
    border_color = str(table_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
    header_bg = str(table_cfg.get("header_background", "rgba(20, 16, 10, 190)"))
    return (
        "QTableWidget {"
        f"background: {str(table_cfg.get('table_background', table_cfg.get('background', 'rgba(5, 5, 5, 95)')))};"
        "border: none;"
        f"color: {str(table_cfg.get('text_color', '#ffffff'))};"
        f"gridline-color: {border_color};"
        f"font-size: {safe_int(table_cfg.get('font_size', 14), 14)}px;"
        "}"
        "QTableWidget::item {"
        f"padding: {safe_int(table_cfg.get('cell_padding', 5), 5)}px;"
        "}"
        "QTableWidget::item:selected {"
        + (
            f"background: {selection_bg}; color: {selection_text}; border: 1px solid {selection_border};"
            if selection_enabled
            else "background: transparent; color: inherit; border: none;"
        )
        + "}"
        "QTableWidget::item:focus { outline: none; }"
        "QHeaderView::section {"
        f"background: {header_bg};"
        f"color: {str(table_cfg.get('header_color', '#f2d28b'))};"
        f"font-size: {safe_int(table_cfg.get('header_font_size', table_cfg.get('font_size', 14)), 14)}px;"
        "font-weight: 700;"
        f"border: 1px solid {border_color};"
        f"padding: {safe_int(table_cfg.get('header_padding', 4), 4)}px;"
        "}"
        + _magic_scrollbar_stylesheet(table_cfg.get("scrollbar", {}))
    )


def _configured_magic_width(table_cfg, column_order, safe_int):
    columns_cfg = table_cfg.get("columns", {}) if isinstance(table_cfg.get("columns", {}), dict) else {}
    width = 0
    for key in column_order:
        col_cfg = columns_cfg.get(key, {}) if isinstance(columns_cfg.get(key, {}), dict) else {}
        width += safe_int(col_cfg.get("w", 120), 120)
    return width


def _apply_magic_column_widths(table, table_cfg, column_order, safe_int):
    columns_cfg = table_cfg.get("columns", {}) if isinstance(table_cfg.get("columns", {}), dict) else {}
    configured_width = _configured_magic_width(table_cfg, column_order, safe_int)
    available_width = max(1, table.width() - 4)
    extra = max(0, available_width - configured_width)
    fill_last = bool(table_cfg.get("fill_last_column", True))
    for col_index, key in enumerate(column_order):
        col_cfg = columns_cfg.get(key, {}) if isinstance(columns_cfg.get(key, {}), dict) else {}
        width = safe_int(col_cfg.get("w", 120), 120)
        if fill_last and col_index == len(column_order) - 1:
            width += extra
        table.setColumnWidth(col_index, max(1, width))


class _MagicCellDelegate(QStyledItemDelegate):
    def __init__(self, parent, table_cfg, safe_int):
        super().__init__(parent)
        self._table_cfg = table_cfg if isinstance(table_cfg, dict) else {}
        self._safe_int = safe_int

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor_cfg = self._table_cfg.get("editor", {}) if isinstance(self._table_cfg.get("editor", {}), dict) else {}
        bg = str(editor_cfg.get("background", "#14100d"))
        text = str(editor_cfg.get("text_color", "#eadfca"))
        border = str(editor_cfg.get("border_color", "rgba(242, 210, 139, 150)"))
        selection = str(editor_cfg.get("selection", "rgba(127, 208, 255, 70)"))
        editor.setStyleSheet(
            "QLineEdit {"
            f"background: {bg};"
            f"color: {text};"
            f"border: 1px solid {border};"
            f"font-size: {self._safe_int(editor_cfg.get('font_size', self._table_cfg.get('font_size', 14)), 14)}px;"
            f"padding: {self._safe_int(editor_cfg.get('padding', 4), 4)}px;"
            f"selection-background-color: {selection};"
            "}"
        )
        return editor
