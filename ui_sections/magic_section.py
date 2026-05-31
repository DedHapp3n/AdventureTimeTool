from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView, QFrame, QTableWidget, QTableWidgetItem


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

    panel = QFrame(parent)
    panel.setGeometry(
        safe_int(table_cfg.get("x", 20), 20),
        safe_int(table_cfg.get("y", 50), 50),
        safe_int(table_cfg.get("w", 760), 760),
        safe_int(table_cfg.get("h", 250), 250),
    )
    panel.setStyleSheet("background: transparent;")
    panel.show()

    if callable(create_panel_text):
        create_panel_text(
            panel,
            {"x": 0, "y": 0, "w": panel.width(), "h": 30},
            str(table_cfg.get("title", "Upgrade Tabelle")),
            safe_int(table_cfg.get("title_font_size", 18), 18),
            str(table_cfg.get("header_color", "#f2d28b")),
            bold=True,
            align="left",
        )

    table = QTableWidget(panel)
    table.setGeometry(0, 34, panel.width(), max(60, panel.height() - 36))
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
    selection_cfg = table_cfg.get("selection", {})
    if not isinstance(selection_cfg, dict):
        selection_cfg = {}
    selection_bg = str(selection_cfg.get("background", "rgba(242, 210, 139, 45)"))
    selection_text = str(selection_cfg.get("text_color", "#ffffff"))
    selection_border = str(selection_cfg.get("border_color", "rgba(242, 210, 139, 120)"))
    selection_enabled = bool(selection_cfg.get("enabled", True))
    table.setStyleSheet(
        "QTableWidget {"
        f"background: {str(table_cfg.get('background', 'rgba(5, 5, 5, 95)'))};"
        f"border: 1px solid {str(table_cfg.get('border_color', 'rgba(242, 210, 139, 90)'))};"
        f"color: {str(table_cfg.get('text_color', '#ffffff'))};"
        f"gridline-color: {str(table_cfg.get('border_color', 'rgba(242, 210, 139, 90)'))};"
        f"font-size: {safe_int(table_cfg.get('font_size', 14), 14)}px;"
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
        f"background: rgba(20, 16, 10, 180); color: {str(table_cfg.get('header_color', '#f2d28b'))};"
        f"font-size: {safe_int(table_cfg.get('font_size', 14), 14)}px; font-weight: 700; border: 0px;"
        "}"
    )

    for row_index, row_data in enumerate(upgrade_rows or []):
        label_item = QTableWidgetItem(str(row_data.get("label", "") or ""))
        label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
        label_item.setForeground(QColor(str(table_cfg.get("header_color", "#f2d28b"))))
        table.setItem(row_index, 0, label_item)
        values = row_data.get("values", [])
        for value_index in range(max_cols):
            value = str(values[value_index] if value_index < len(values) else "")
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setForeground(QColor(str(table_cfg.get("value_color", "#7fd0ff"))))
            table.setItem(row_index, value_index + 1, item)

    table.verticalHeader().setDefaultSectionSize(26)
    content_w = max(120, table.width() - 24)
    label_w = max(180, min(260, int(content_w * 0.22)))
    min_value_col_w = 110
    required_w = label_w + (max_cols * min_value_col_w)
    needs_h_scroll = required_w > content_w
    if needs_h_scroll:
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    else:
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    table.setColumnWidth(0, label_w)
    remaining_w = max(10, content_w - label_w)
    if max_cols > 0:
        if needs_h_scroll:
            per_col = min_value_col_w
        else:
            per_col = max(min_value_col_w, int(remaining_w / max_cols))
        for col in range(1, 1 + max_cols):
            table.setColumnWidth(col, per_col)

    header_h = max(24, table.horizontalHeader().height())
    content_h = max(60, table.height() - header_h - 6)
    row_h = max(24, min(34, int(content_h / max(1, row_count))))
    for row_index in range(row_count):
        table.setRowHeight(row_index, row_h)
    required_h = header_h + (row_count * row_h) + 6
    needs_v_scroll = required_h > table.height()
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if needs_v_scroll else Qt.ScrollBarAlwaysOff)
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

    panel = QFrame(parent)
    panel.setGeometry(
        safe_int(table_cfg.get("x", 20), 20),
        safe_int(table_cfg.get("y", 330), 330),
        safe_int(table_cfg.get("w", 1360), 1360),
        safe_int(table_cfg.get("h", 450), 450),
    )
    panel.setStyleSheet("background: transparent;")
    panel.show()

    if callable(create_panel_text):
        create_panel_text(
            panel,
            {"x": 0, "y": 0, "w": panel.width(), "h": 30},
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
    table.setGeometry(0, 34, panel.width(), max(80, panel.height() - 36))
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
    selection_cfg = table_cfg.get("selection", {})
    if not isinstance(selection_cfg, dict):
        selection_cfg = {}
    selection_bg = str(selection_cfg.get("background", "rgba(242, 210, 139, 45)"))
    selection_text = str(selection_cfg.get("text_color", "#ffffff"))
    selection_border = str(selection_cfg.get("border_color", "rgba(242, 210, 139, 120)"))
    selection_enabled = bool(selection_cfg.get("enabled", True))
    table.setStyleSheet(
        "QTableWidget {"
        f"background: {str(table_cfg.get('background', 'rgba(5, 5, 5, 95)'))};"
        f"border: 1px solid {str(table_cfg.get('border_color', 'rgba(242, 210, 139, 90)'))};"
        f"color: {str(table_cfg.get('text_color', '#ffffff'))};"
        f"gridline-color: {str(table_cfg.get('border_color', 'rgba(242, 210, 139, 90)'))};"
        f"font-size: {safe_int(table_cfg.get('font_size', 14), 14)}px;"
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
        f"background: rgba(20, 16, 10, 180); color: {str(table_cfg.get('header_color', '#f2d28b'))};"
        f"font-size: {safe_int(table_cfg.get('font_size', 14), 14)}px; font-weight: 700; border: 0px;"
        "}"
    )

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
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                table.setItem(row_index, col_index, item)
    finally:
        if callable(set_rendering):
            set_rendering(False)

    total_w = panel.width()
    used_w = 0
    for col_index, key in enumerate(column_order):
        width = safe_int(columns_cfg.get(key, {}).get("w", 150), 150)
        if col_index == len(column_order) - 1:
            width = max(80, total_w - used_w - 20)
        table.setColumnWidth(col_index, width)
        used_w += width
    table.verticalHeader().setDefaultSectionSize(max(30, safe_int(table_cfg.get("font_size", 14), 14) * 2))
    table.resizeRowsToContents()

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
