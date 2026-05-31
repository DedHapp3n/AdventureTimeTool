import html
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextDocument, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QInputDialog, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit,
)

from app_logger import log_debug, log_error


def render_inventory_screen(window):
    if window.content_layer is None:
        return

    window._inventory_loading = True
    window._inventory_table_bindings = {}
    try:
        layout_config = window.load_inventory_layout_config()
        screen_cfg = layout_config.get("inventory_screen", {})
        inventory_data = window.get_inventory_display_data()
        inventory_categories = window.build_inventory_slot_categories(inventory_data.get("sections", []))
        available_ids = [str(cat.get("id", "")) for cat in inventory_categories if isinstance(cat, dict)]
        if window.current_inventory_category not in available_ids:
            window.current_inventory_category = "inventory_01"

        screen = QFrame(window.content_layer)
        screen.setGeometry(
            window._safe_int(screen_cfg.get("x", 20), 20),
            window._safe_int(screen_cfg.get("y", 20), 20),
            window._safe_int(screen_cfg.get("w", 1420), 1420),
            window._safe_int(screen_cfg.get("h", 820), 820),
        )
        screen.setStyleSheet("background: transparent;")
        screen.show()

        title_cfg = screen_cfg.get("title", {})
        window.create_panel_text(
            screen,
            title_cfg,
            str(title_cfg.get("text", "Inventar")),
            window._safe_int(title_cfg.get("font_size", 24), 24),
            str(title_cfg.get("color", "#f2d28b")),
            bold=True,
            align=str(title_cfg.get("align", "center")),
        )

        window.render_inventory_money_panel(screen, screen_cfg.get("money", {}), inventory_data["money"])
        window.render_inventory_category_tabs(screen, screen_cfg, inventory_categories)
        window.render_inventory_active_category_table(screen, screen_cfg, inventory_categories)
    finally:
        window._inventory_loading = False


def on_inventory_category_clicked(window, category_id):
    window.current_inventory_category = str(category_id or "")
    window.show_main_section("inventory")


def rename_inventory_category(window, slot_id):
    slot_id = str(slot_id or "").strip()
    if not slot_id:
        return
    default_labels = {
        "inventory_01": "Inventar 01",
        "inventory_02": "Inventar 02",
        "inventory_03": "Inventar 03",
        "inventory_04": "Inventar 04",
        "inventory_05": "Inventar 05",
    }
    current_label = window.get_inventory_tab_label(slot_id, default_labels.get(slot_id, slot_id))
    new_label, ok = QInputDialog.getText(
        window,
        "Inventar-Tab umbenennen",
        "Name:",
        text=current_label,
    )
    if not ok:
        return
    normalized_label = str(new_label).strip()
    if not normalized_label:
        normalized_label = default_labels.get(slot_id, current_label)
    if normalized_label == current_label:
        return
    try:
        window.loader.set_inventory_tab_label(slot_id, normalized_label)
        window.loader.save_active_character_json()
        log_debug("inventory", f'INVENTORY TAB RENAME {slot_id} = "{normalized_label}"')
        window.show_main_section("inventory")
    except Exception as exc:
        log_error("inventory", f"tab rename failed: {exc}")


def render_inventory_category_tabs(window, parent, screen_cfg, categories):
    tabs_cfg = screen_cfg.get("category_tabs", {})
    if not isinstance(tabs_cfg, dict):
        tabs_cfg = {}
    tabs_container = QFrame(parent)
    tabs_container.setGeometry(
        window._safe_int(tabs_cfg.get("x", 20), 20),
        window._safe_int(tabs_cfg.get("y", 175), 175),
        window._safe_int(tabs_cfg.get("w", 1380), 1380),
        window._safe_int(tabs_cfg.get("h", 50), 50),
    )
    tabs_container.setStyleSheet("background: transparent;")
    tabs_container.show()

    button_w = window._safe_int(tabs_cfg.get("button_w", 220), 220)
    button_h = window._safe_int(tabs_cfg.get("button_h", 42), 42)
    button_gap = window._safe_int(tabs_cfg.get("gap", 18), 18)
    tab_font_size = window._safe_int(tabs_cfg.get("font_size", 20), 20)
    active_color = str(tabs_cfg.get("active_color", "#f2d28b"))
    inactive_color = str(tabs_cfg.get("inactive_color", "#9a8560"))
    hover_color = str(tabs_cfg.get("hover_color", "#ffffff"))
    use_asset_buttons = bool(tabs_cfg.get("use_asset_buttons", False))
    default_asset = str(tabs_cfg.get("asset", "buttons/menu_button_small.png") or "").strip()
    active_asset = str(tabs_cfg.get("active_asset", default_asset) or "").strip()
    inactive_asset = str(tabs_cfg.get("inactive_asset", default_asset) or "").strip()

    for index, category in enumerate(categories):
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("id", "") or "")
        if not category_id:
            continue
        title = str(category.get("title", category_id))
        is_active = category_id == window.current_inventory_category
        button = QPushButton(tabs_container)
        button.setGeometry(index * (button_w + button_gap), 0, button_w, button_h)
        button.setText(title)
        button.setCursor(Qt.PointingHandCursor)
        button.setProperty("inventory_category_id", category_id)
        button.installEventFilter(window)
        color = active_color if is_active else inactive_color
        border = "#b88a35" if is_active else "rgba(180, 140, 70, 90)"
        bg = "rgba(35, 24, 12, 185)" if is_active else "rgba(8, 8, 8, 125)"
        asset_for_state = active_asset if is_active else inactive_asset
        asset_path = window.resolve_ui_asset_path(asset_for_state) if asset_for_state else None
        has_asset = bool(use_asset_buttons and asset_path is not None and asset_path.exists())
        if has_asset:
            button.setStyleSheet(
                "QPushButton {"
                f"color: {color};"
                f"font-size: {tab_font_size}px;"
                "font-weight: 700;"
                "padding: 0px;"
                "border: none;"
                f"border-image: url({asset_path.as_posix()}) 0 0 0 0 stretch stretch;"
                "background: transparent;"
                "}"
                "QPushButton:hover {"
                f"color: {hover_color};"
                "}"
            )
        else:
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
                f"QPushButton:hover {{ border: 1px solid #f2d28b; color: {hover_color}; }}"
            )
        button.clicked.connect(
            lambda checked=False, cid=category_id: window.on_inventory_category_clicked(cid)
        )
        button.show()


def render_inventory_active_category_table(window, parent, screen_cfg, categories):
    table_cfg = screen_cfg.get("table", {})
    if not isinstance(table_cfg, dict):
        table_cfg = {}
    active_category = None
    for category in categories:
        if isinstance(category, dict) and str(category.get("id", "")) == window.current_inventory_category:
            active_category = category
            break
    if active_category is None and categories:
        active_category = categories[0]
    if active_category is None:
        active_category = {"id": "inventory_left", "title": "Inventar 01", "header_title": "Inventar", "rows": []}
    window.render_inventory_single_table_widget(parent, table_cfg, active_category)


def render_inventory_single_table_widget(window, parent, table_cfg, category):
    table_frame = QFrame(parent)
    table_frame.setGeometry(
        window._safe_int(table_cfg.get("x", 20), 20),
        window._safe_int(table_cfg.get("y", 235), 235),
        window._safe_int(table_cfg.get("w", 1380), 1380),
        window._safe_int(table_cfg.get("h", 560), 560),
    )
    border_color = str(table_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
    background = str(table_cfg.get("background", "rgba(5, 5, 5, 95)"))
    table_frame.setStyleSheet(
        f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
    )
    table_frame.show()

    columns = table_cfg.get("columns", {})
    if not isinstance(columns, dict):
        columns = {}
    name_col = columns.get("name", {})
    pl_col = columns.get("pl", {})
    count_col = columns.get("count", {})
    if not isinstance(name_col, dict):
        name_col = {}
    if not isinstance(pl_col, dict):
        pl_col = {}
    if not isinstance(count_col, dict):
        count_col = {}

    header_title = str(category.get("title", "") or category.get("header_title", "Inventar"))
    table = QTableWidget(table_frame)
    table.setGeometry(6, 6, max(1, table_frame.width() - 12), max(1, table_frame.height() - 12))
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(
        [
            header_title,
            str(pl_col.get("title", "PL")),
            str(count_col.get("title", "Anzahl")),
        ]
    )
    table.setEditTriggers(
        QAbstractItemView.DoubleClicked
        | QAbstractItemView.EditKeyPressed
        | QAbstractItemView.SelectedClicked
    )
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setSelectionBehavior(QAbstractItemView.SelectItems)
    table.setFocusPolicy(Qt.StrongFocus)
    table.setWordWrap(True)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(False)
    table.setShowGrid(True)

    font_size = window._safe_int(table_cfg.get("font_size", 15), 15)
    header_font_size = window._safe_int(table_cfg.get("header_font_size", 18), 18)
    header_color = str(table_cfg.get("header_color", "#f2d28b"))
    text_color = str(table_cfg.get("text_color", "#ffffff"))
    value_color = str(table_cfg.get("value_color", "#7fd0ff"))
    table.setStyleSheet(
        "QTableWidget {"
        f"background: {background};"
        f"color: {text_color};"
        f"gridline-color: {border_color};"
        f"font-size: {font_size}px;"
        "border: none;"
        "selection-background-color: rgba(242, 210, 139, 30);"
        "selection-color: #ffffff;"
        "}"
        "QHeaderView::section {"
        "background: rgba(24, 16, 8, 175);"
        f"color: {header_color};"
        f"font-size: {header_font_size}px;"
        "font-weight: 700;"
        f"border: 1px solid {border_color};"
        "padding: 3px;"
        "}"
    )

    rows = category.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    min_table_rows = window._safe_int(table_cfg.get("min_rows", 0), 0)
    rows = window.build_inventory_table_rows(category, min_table_rows)
    table.blockSignals(True)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            row = {}
        is_empty_slot = bool(row.get("is_empty_slot"))
        display_values = [
            "" if is_empty_slot else (str(row.get("name", "")).strip() or "(ohne Name)"),
            "" if is_empty_slot else (str(row.get("pl", "")).strip() or "-"),
            "" if is_empty_slot else (str(row.get("count", "")).strip() or "-"),
        ]
        raw_values = [
            str(row.get("name", "") or ""),
            str(row.get("pl", "") or ""),
            str(row.get("count", "") or ""),
        ]
        for column_index, value in enumerate(display_values):
            item = QTableWidgetItem(value)
            item.setData(Qt.UserRole, raw_values[column_index])
            item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setBackground(QColor(0, 0, 0, 0))
            item.setForeground(QColor(value_color if column_index in (1, 2) else text_color))
            item.setTextAlignment(
            Qt.AlignCenter if column_index in (1, 2) else Qt.AlignLeft | Qt.AlignVCenter
            )
            table.setItem(row_index, column_index, item)

    column_widths = [
        window._safe_int(name_col.get("w", 1140), 1140),
        window._safe_int(pl_col.get("w", 80), 80),
        window._safe_int(count_col.get("w", 120), 120),
    ]
    available_width = max(1, table.width() - 4)
    configured_width = sum(column_widths)
    if configured_width > available_width:
        overflow = configured_width - available_width
        column_widths[0] = max(120, column_widths[0] - overflow)
    for column_index, width in enumerate(column_widths):
        table.setColumnWidth(column_index, max(1, width))

    table.resizeRowsToContents()
    min_row_h = window._safe_int(table_cfg.get("min_row_h", 34), 34)
    max_row_h = window._safe_int(table_cfg.get("max_row_h", 90), 90)
    window._apply_inventory_row_heights(table, min_row_h, max_row_h)
    table.blockSignals(False)

    window._inventory_table_bindings[id(table)] = {
        "section_id": str(category.get("id", "")),
        "rows": rows,
        "min_row_h": min_row_h,
        "max_row_h": max_row_h,
    }
    table.cellChanged.connect(
        lambda row_index, column_index, widget=table: window.on_inventory_table_cell_changed(
            widget, row_index, column_index
        )
    )
    table.show()


def render_inventory_money_panel(window, parent, money_cfg, money):
    window._inventory_money_fields = {}
    window._inventory_money_delta_fields = {}
    panel = QFrame(parent)
    panel.setGeometry(
        window._safe_int(money_cfg.get("x", 20), 20),
        window._safe_int(money_cfg.get("y", 60), 60),
        window._safe_int(money_cfg.get("w", 420), 420),
        window._safe_int(money_cfg.get("h", 110), 110),
    )
    panel.setStyleSheet(
        "background: rgba(5, 5, 5, 95);"
        "border: 1px solid rgba(242, 210, 139, 70);"
        "border-radius: 4px;"
    )
    panel.show()

    title_color = str(money_cfg.get("title_color", "#f2d28b"))
    label_color = str(money_cfg.get("label_color", "#f2d28b"))
    value_color = str(money_cfg.get("value_color", "#ffffff"))
    title_font = window._safe_int(money_cfg.get("font_size", 18), 18)
    label_font = window._safe_int(money_cfg.get("label_font_size", 14), 14)
    value_font = window._safe_int(money_cfg.get("value_font_size", 20), 20)

    window.create_panel_text(
        panel,
        {"x": 12, "y": 8, "w": max(1, panel.width() - 24), "h": 26},
        str(money_cfg.get("title", "Geldbeutel")),
        title_font,
        title_color,
        bold=True,
        align="left",
    )

    columns = money_cfg.get("columns", [])
    if not isinstance(columns, list) or not columns:
        columns = window.get_default_inventory_layout_config()["inventory_screen"]["money"]["columns"]
    money_cells = {
        "gulden": "B9",
        "schilling": "E9",
        "heller": "H9",
        "pfifferling": "K9",
    }
    column_w = max(1, (panel.width() - 24) // max(1, len(columns)))
    for index, column in enumerate(columns):
        if not isinstance(column, dict):
            continue
        x = 12 + index * column_w
        value_id = str(column.get("id", ""))
        window.create_panel_text(
            panel,
            {"x": x, "y": 44, "w": column_w - 8, "h": 22},
            str(column.get("label", value_id)),
            label_font,
            label_color,
            bold=True,
            align="center",
        )
        money_edit = QLineEdit(panel)
        money_edit.setGeometry(x, 68, max(1, column_w - 8), 30)
        money_edit.setAlignment(Qt.AlignCenter)
        money_edit.setStyleSheet(
            "QLineEdit {"
            "background: rgba(8, 8, 8, 165);"
            "border: 1px solid rgba(242, 210, 139, 70);"
            f"color: {value_color};"
            f"font-size: {value_font}px;"
            "font-weight: 700;"
            "padding: 0px 4px;"
            "}"
        )
        money_edit.setProperty("inventory_money_cell", money_cells.get(value_id, ""))
        money_edit.blockSignals(True)
        money_edit.setText(str(money.get(value_id, "")))
        money_edit.blockSignals(False)
        money_edit.editingFinished.connect(
            lambda field=money_edit: window.on_inventory_money_edit_finished(field)
        )
        window._inventory_money_fields[value_id] = money_edit
        money_edit.show()

    delta_row_cfg = money_cfg.get("delta_row", {})
    if not isinstance(delta_row_cfg, dict):
        delta_row_cfg = {}
    delta_buttons_cfg = money_cfg.get("delta_buttons", {})
    if not isinstance(delta_buttons_cfg, dict):
        delta_buttons_cfg = {}

    delta_label = str(delta_row_cfg.get("label", "Änderung"))
    label_x = window._safe_int(delta_row_cfg.get("label_x", 12), 12)
    label_y = window._safe_int(delta_row_cfg.get("label_y", 101), 101)
    label_w = window._safe_int(delta_row_cfg.get("label_w", 100), 100)
    label_h = window._safe_int(delta_row_cfg.get("label_h", 22), 22)
    field_y = window._safe_int(delta_row_cfg.get("field_y", 124), 124)
    field_h = window._safe_int(delta_row_cfg.get("field_h", 26), 26)
    field_gap = window._safe_int(delta_row_cfg.get("field_gap", 10), 10)
    reserve_button_space = bool(delta_row_cfg.get("reserve_button_space", False))

    window.create_panel_text(
        panel,
        {"x": label_x, "y": label_y, "w": label_w, "h": label_h},
        delta_label,
        label_font,
        label_color,
        bold=True,
        align="left",
    )

    button_w = window._safe_int(delta_row_cfg.get("buttons_w", delta_buttons_cfg.get("w", 32)), 32)
    button_h = window._safe_int(delta_row_cfg.get("buttons_h", delta_buttons_cfg.get("h", 28)), 28)
    button_gap = window._safe_int(delta_row_cfg.get("buttons_gap", delta_buttons_cfg.get("gap", 6)), 6)
    button_font_size = window._safe_int(delta_row_cfg.get("font_size", delta_buttons_cfg.get("font_size", 16)), 16)
    buttons_y = window._safe_int(delta_row_cfg.get("buttons_y", delta_buttons_cfg.get("y", field_y)), field_y)
    buttons_right_margin = window._safe_int(delta_row_cfg.get("buttons_right_margin", 12), 12)

    fields_left = label_x
    fields_right = panel.width() - 12
    if reserve_button_space:
        button_space = (button_w * 2) + button_gap + buttons_right_margin + 12
        fields_right = max(fields_left + 40, panel.width() - button_space)
    available_field_w = max(40, fields_right - fields_left)
    if len(columns) > 0:
        delta_column_w = max(20, available_field_w // len(columns))
    else:
        delta_column_w = available_field_w
    delta_field_w_cfg = delta_row_cfg.get("delta_field_w", None)
    delta_field_w = window._safe_int(delta_field_w_cfg, delta_column_w - field_gap) if delta_field_w_cfg is not None else (delta_column_w - field_gap)

    for index, column in enumerate(columns):
        if not isinstance(column, dict):
            continue
        x = fields_left + index * delta_column_w
        value_id = str(column.get("id", ""))
        delta_edit = QLineEdit(panel)
        delta_edit.setGeometry(x, field_y, max(1, delta_field_w), max(1, field_h))
        delta_edit.setAlignment(Qt.AlignCenter)
        delta_edit.setText("0")
        delta_edit.setStyleSheet(
            "QLineEdit {"
            "background: rgba(8, 8, 8, 165);"
            "border: 1px solid rgba(242, 210, 139, 70);"
            f"color: {value_color};"
            f"font-size: {value_font}px;"
            "font-weight: 700;"
            "padding: 0px 4px;"
            "}"
        )
        window._inventory_money_delta_fields[value_id] = delta_edit
        delta_edit.show()

    if "minus_x" in delta_buttons_cfg:
        minus_x = window._safe_int(delta_buttons_cfg.get("minus_x"), panel.width() - buttons_right_margin - ((button_w * 2) + button_gap))
    else:
        minus_x = panel.width() - buttons_right_margin - ((button_w * 2) + button_gap)
    if "plus_x" in delta_buttons_cfg:
        plus_x = window._safe_int(delta_buttons_cfg.get("plus_x"), minus_x + button_w + button_gap)
    else:
        plus_x = minus_x + button_w + button_gap
    minus_button = QPushButton("-", panel)
    plus_button = QPushButton("+", panel)
    minus_button.setGeometry(max(0, minus_x), max(0, buttons_y), max(1, button_w), max(1, button_h))
    plus_button.setGeometry(max(0, plus_x), max(0, buttons_y), max(1, button_w), max(1, button_h))
    for button in (minus_button, plus_button):
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(
            "QPushButton {"
            "background: rgba(35, 24, 12, 185);"
            f"color: {title_color};"
            "border: 1px solid rgba(242, 210, 139, 90);"
            "border-radius: 4px;"
            f"font-size: {button_font_size}px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { border: 1px solid #f2d28b; color: #ffffff; }"
        )
    minus_button.clicked.connect(lambda: window.on_inventory_money_delta_apply("-"))
    plus_button.clicked.connect(lambda: window.on_inventory_money_delta_apply("+"))
    minus_button.show()
    plus_button.show()


def on_inventory_money_edit_finished(window, field):
    if window._inventory_loading:
        return
    if field is None:
        return
    cell_ref = str(field.property("inventory_money_cell") or "").strip().upper()
    if not cell_ref:
        return
    new_value = str(field.text())
    old_value = str(window.get_cache_cell_value("Inventar", cell_ref, "") or "")
    if new_value == old_value:
        return
    try:
        window.loader.set_cell_value("Inventar", cell_ref, new_value)
        window.loader.save_active_character_json()
        log_debug("inventory", f'INVENTORY MONEY EDIT Inventar!{cell_ref} = "{new_value}"')
        log_debug("inventory", "INVENTORY SAVE active character saved")
    except Exception as exc:
        log_error("inventory", f"edit failed: {exc}")


def _inventory_parse_non_negative_int(window, value):
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        number = int(float(text))
    except Exception:
        return 0
    return max(0, number)


def money_to_pfifferling(window, gulden, schilling, heller, pfifferling):
    return (
        int(gulden) * 1000
        + int(schilling) * 100
        + int(heller) * 10
        + int(pfifferling)
    )


def pfifferling_to_money(window, total_pfifferling):
    total = max(0, int(total_pfifferling))
    gulden = total // 1000
    rest = total % 1000
    schilling = rest // 100
    rest = rest % 100
    heller = rest // 10
    pfifferling = rest % 10
    return {
        "gulden": gulden,
        "schilling": schilling,
        "heller": heller,
        "pfifferling": pfifferling,
    }


def _inventory_get_wallet_money_values(window):
    values = {}
    for key in ("gulden", "schilling", "heller", "pfifferling"):
        field = window._inventory_money_fields.get(key)
        if field is not None:
            values[key] = window._inventory_parse_non_negative_int(field.text())
        else:
            values[key] = window._inventory_parse_non_negative_int(
                window.get_cache_cell_value(
                    "Inventar",
                    {"gulden": "B9", "schilling": "E9", "heller": "H9", "pfifferling": "K9"}[key],
                    0,
                )
            )
    return values


def on_inventory_money_delta_apply(window, op):
    if window._inventory_loading:
        return
    op = str(op or "").strip()
    if op not in {"+", "-"}:
        return
    wallet = window._inventory_get_wallet_money_values()
    delta = {}
    for key in ("gulden", "schilling", "heller", "pfifferling"):
        field = window._inventory_money_delta_fields.get(key)
        delta[key] = window._inventory_parse_non_negative_int(field.text() if field is not None else 0)
    current_total = window.money_to_pfifferling(
        wallet["gulden"], wallet["schilling"], wallet["heller"], wallet["pfifferling"]
    )
    delta_total = window.money_to_pfifferling(
        delta["gulden"], delta["schilling"], delta["heller"], delta["pfifferling"]
    )
    result_total = current_total + delta_total if op == "+" else current_total - delta_total
    if result_total < 0:
        result_total = 0
    result_money = window.pfifferling_to_money(result_total)
    save_map = {
        "gulden": "B9",
        "schilling": "E9",
        "heller": "H9",
        "pfifferling": "K9",
    }
    try:
        for key, cell_ref in save_map.items():
            value = str(int(result_money.get(key, 0)))
            window.loader.set_cell_value("Inventar", cell_ref, value)
            field = window._inventory_money_fields.get(key)
            if field is not None:
                field.blockSignals(True)
                field.setText(value)
                field.blockSignals(False)
        window.loader.save_active_character_json()
        log_debug(
            "inventory",
            f"INVENTORY MONEY DELTA op={op} input={delta['gulden']}/{delta['schilling']}/{delta['heller']}/{delta['pfifferling']} "
            f"result={result_money.get('gulden', 0)}/{result_money.get('schilling', 0)}/"
            f"{result_money.get('heller', 0)}/{result_money.get('pfifferling', 0)}",
        )
        log_debug("inventory", "INVENTORY SAVE active character saved")
        for field in window._inventory_money_delta_fields.values():
            if field is None:
                continue
            field.setText("0")
    except Exception as exc:
        log_error("inventory", f"money delta failed: {exc}")


def get_inventory_wrapped_text_height(window, text, width, font_size, max_lines=0):
    font = QFont()
    font.setPixelSize(max(1, int(font_size)))
    document = QTextDocument()
    document.setDocumentMargin(0)
    document.setDefaultFont(font)
    document.setTextWidth(max(1, int(width)))
    document.setPlainText(str(text or " "))
    height = int(math.ceil(document.size().height()))
    if max_lines and max_lines > 0:
        line_height = QFontMetrics(font).lineSpacing()
        height = min(height, max(1, line_height * int(max_lines)))
    return max(1, height)


def build_inventory_text_block_html(window, rows, text_cfg):
    font_size = window._safe_int(text_cfg.get("font_size", 14), 14)
    meta_font_size = window._safe_int(text_cfg.get("meta_font_size", 12), 12)
    line_spacing = window._safe_int(text_cfg.get("line_spacing", 4), 4)
    item_spacing = window._safe_int(text_cfg.get("item_spacing", 10), 10)
    text_color = str(text_cfg.get("text_color", "#ffffff"))
    meta_text_color = str(text_cfg.get("meta_text_color", "#7fd0ff"))
    muted_text_color = str(text_cfg.get("muted_text_color", "#c8c0aa"))

    item_html = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip() or "(ohne Name)"
        pl = str(row.get("pl", "")).strip() or "-"
        count = str(row.get("count", "")).strip() or "-"
        item_html.append(
            "<div class=\"item\">"
            f"<div class=\"name\">{html.escape(name)}</div>"
            f"<div class=\"meta\">PL: {html.escape(pl)}&nbsp;&nbsp;&nbsp;&nbsp;Anzahl: {html.escape(count)}</div>"
            "</div>"
        )
    if not item_html:
        item_html.append('<div class="empty">(keine Einträge)</div>')

    return (
        "<html><head><style>"
        "body { margin: 0; padding: 0; }"
        f".item {{ margin: 0 0 {item_spacing}px 0; }}"
        f".name {{ color: {text_color}; font-size: {font_size}px; line-height: {font_size + line_spacing}px; }}"
        f".meta {{ color: {meta_text_color}; font-size: {meta_font_size}px; line-height: {meta_font_size + line_spacing}px; }}"
        f".empty {{ color: {muted_text_color}; font-size: {font_size}px; }}"
        "</style></head><body>"
        + "".join(item_html)
        + "</body></html>"
    )


def render_inventory_text_block_tables(window, parent, tables_cfg, sections):
    section_by_id = {
        str(section.get("id", "")): section
        for section in sections
        if isinstance(section, dict)
    }
    table_y = window._safe_int(tables_cfg.get("y", 200), 200)
    default_h = max(1, parent.height() - table_y - 20)
    table_h = window._safe_int(tables_cfg.get("h", default_h), default_h)
    header_h = window._safe_int(tables_cfg.get("header_h", 38), 38)
    header_font_size = window._safe_int(tables_cfg.get("header_font_size", 16), 16)
    header_color = str(tables_cfg.get("header_color", "#f2d28b"))
    text_cfg = tables_cfg.get("text_block", {})
    if not isinstance(text_cfg, dict):
        text_cfg = {}
    background = str(text_cfg.get("background", "rgba(0, 0, 0, 35)"))
    border_color = str(
        text_cfg.get("border_color", tables_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
    )
    text_color = str(text_cfg.get("text_color", "#ffffff"))

    sections_cfg = tables_cfg.get("sections", [])
    if not isinstance(sections_cfg, list):
        sections_cfg = []
    for section_cfg in sections_cfg:
        if not isinstance(section_cfg, dict):
            continue
        section_id = str(section_cfg.get("id", ""))
        section_data = section_by_id.get(section_id, {"rows": [], "title": section_id})
        table_w = window._safe_int(section_cfg.get("w", 430), 430)

        table = QFrame(parent)
        table.setGeometry(
            window._safe_int(section_cfg.get("x", 20), 20),
            table_y,
            table_w,
            table_h,
        )
        table.setStyleSheet(
            f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
        )
        table.show()

        columns = section_cfg.get("columns", {})
        if not isinstance(columns, dict):
            columns = {}
        name_col = columns.get("name", {})
        if not isinstance(name_col, dict):
            name_col = {}
        window.create_panel_text(
            table,
            {"x": 8, "y": 0, "w": max(1, table_w - 16), "h": header_h},
            str(name_col.get("title", section_cfg.get("title", section_data.get("title", "Inventar")))),
            header_font_size,
            header_color,
            bold=True,
            align="left",
        )

        text_edit = QTextEdit(table)
        text_edit.setGeometry(6, header_h, max(1, table_w - 12), max(1, table_h - header_h - 6))
        text_edit.setReadOnly(True)
        text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        text_edit.setStyleSheet(
            "QTextEdit {"
            "background: transparent;"
            "border: none;"
            f"color: {text_color};"
            "padding: 4px;"
            "}"
        )
        rows = section_data.get("rows", [])
        if not isinstance(rows, list):
            rows = []
        text_edit.setHtml(window.build_inventory_text_block_html(rows, text_cfg))
        text_edit.show()


def render_inventory_table_widget_tables(window, parent, tables_cfg, sections):
    section_by_id = {
        str(section.get("id", "")): section
        for section in sections
        if isinstance(section, dict)
    }
    table_y = window._safe_int(tables_cfg.get("y", 200), 200)
    default_h = max(1, parent.height() - table_y - 20)
    table_h = window._safe_int(tables_cfg.get("h", default_h), default_h)
    title_h = window._safe_int(tables_cfg.get("header_h", 38), 38)
    font_size = window._safe_int(tables_cfg.get("font_size", 14), 14)
    header_font_size = window._safe_int(tables_cfg.get("header_font_size", 16), 16)
    min_row_h = window._safe_int(tables_cfg.get("min_row_h", 28), 28)
    max_row_h = window._safe_int(tables_cfg.get("max_row_h", 72), 72)
    header_color = str(tables_cfg.get("header_color", "#f2d28b"))
    text_color = str(tables_cfg.get("text_color", "#ffffff"))
    value_color = str(tables_cfg.get("value_color", "#7fd0ff"))
    border_color = str(tables_cfg.get("border_color", "rgba(242, 210, 139, 90)"))
    row_background = str(tables_cfg.get("row_background", "rgba(0, 0, 0, 18)"))
    background = str(tables_cfg.get("background", "rgba(5, 5, 5, 95)"))

    sections_cfg = tables_cfg.get("sections", [])
    if not isinstance(sections_cfg, list):
        sections_cfg = []
    for section_cfg in sections_cfg:
        if not isinstance(section_cfg, dict):
            continue
        section_id = str(section_cfg.get("id", ""))
        section_data = section_by_id.get(section_id, {"rows": [], "title": section_id})
        table_w = window._safe_int(section_cfg.get("w", 430), 430)

        container = QFrame(parent)
        container.setGeometry(
            window._safe_int(section_cfg.get("x", 20), 20),
            table_y,
            table_w,
            table_h,
        )
        container.setStyleSheet(
            f"background: {background}; border: 1px solid {border_color}; border-radius: 4px;"
        )
        container.show()

        columns = section_cfg.get("columns", {})
        if not isinstance(columns, dict):
            columns = {}
        name_col = columns.get("name", {})
        pl_col = columns.get("pl", {})
        count_col = columns.get("count", {})
        if not isinstance(name_col, dict):
            name_col = {}
        if not isinstance(pl_col, dict):
            pl_col = {}
        if not isinstance(count_col, dict):
            count_col = {}

        section_title = str(
            name_col.get("title", section_cfg.get("title", section_data.get("title", "Inventar")))
        )
        window.create_panel_text(
            container,
            {"x": 8, "y": 0, "w": max(1, table_w - 16), "h": title_h},
            section_title,
            header_font_size,
            header_color,
            bold=True,
            align="left",
        )

        table = QTableWidget(container)
        table.setGeometry(6, title_h, max(1, table_w - 12), max(1, table_h - title_h - 6))
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(
            [
                str(name_col.get("title", section_title)),
                str(pl_col.get("title", "PL")),
                str(count_col.get("title", "Anzahl")),
            ]
        )
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setFocusPolicy(Qt.StrongFocus)
        table.setWordWrap(True)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)
        table.setShowGrid(True)
        table.setStyleSheet(
            "QTableWidget {"
            f"background: {background};"
            f"color: {text_color};"
            f"gridline-color: {border_color};"
            f"font-size: {font_size}px;"
            "border: none;"
            "selection-background-color: rgba(242, 210, 139, 30);"
            "selection-color: #ffffff;"
            "}"
            "QHeaderView::section {"
            "background: rgba(24, 16, 8, 175);"
            f"color: {header_color};"
            f"font-size: {header_font_size}px;"
            "font-weight: 700;"
            f"border: 1px solid {border_color};"
            "padding: 3px;"
            "}"
        )

        rows = section_data.get("rows", [])
        if not isinstance(rows, list):
            rows = []
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                row = {}
            display_values = [
                str(row.get("name", "")).strip() or "(ohne Name)",
                str(row.get("pl", "")).strip() or "-",
                str(row.get("count", "")).strip() or "-",
            ]
            raw_values = [
                str(row.get("name", "") or ""),
                str(row.get("pl", "") or ""),
                str(row.get("count", "") or ""),
            ]
            for column_index, value in enumerate(display_values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, raw_values[column_index])
                item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                item.setBackground(QColor(0, 0, 0, 0))
                item.setForeground(QColor(value_color if column_index in (1, 2) else text_color))
                item.setTextAlignment(
                Qt.AlignCenter if column_index in (1, 2) else Qt.AlignLeft | Qt.AlignVCenter
                )
                table.setItem(row_index, column_index, item)

        column_widths = [
            window._safe_int(name_col.get("w", 320), 320),
            window._safe_int(pl_col.get("w", 45), 45),
            window._safe_int(count_col.get("w", 60), 60),
        ]
        available_width = max(1, table.width() - 4)
        configured_width = sum(column_widths)
        if configured_width > available_width:
            overflow = configured_width - available_width
            column_widths[0] = max(80, column_widths[0] - overflow)
        for column_index, width in enumerate(column_widths):
            table.setColumnWidth(column_index, max(1, width))

        table.resizeRowsToContents()
        for row_index in range(table.rowCount()):
            height = table.rowHeight(row_index)
            height = max(min_row_h, height)
            if max_row_h > 0:
                height = min(max_row_h, height)
            table.setRowHeight(row_index, height)
        table.blockSignals(False)

        window._inventory_table_bindings[id(table)] = {
            "section_id": section_id,
            "rows": rows,
        }
        table.cellChanged.connect(
            lambda row_index, column_index, widget=table: window.on_inventory_table_cell_changed(
                widget, row_index, column_index
            )
        )

        table.show()


def _apply_inventory_row_heights(window, table, min_row_h, max_row_h):
    for row_index in range(table.rowCount()):
        height = table.rowHeight(row_index)
        height = max(min_row_h, height)
        if max_row_h > 0:
            height = min(max_row_h, height)
        table.setRowHeight(row_index, height)


def _is_inventory_row_empty(window, row):
    if not isinstance(row, dict):
        return True
    return not bool(
        str(row.get("name", "") or "")
        or str(row.get("pl", "") or "")
        or str(row.get("count", "") or "")
    )


def _next_inventory_custom_row_index(window, rows, slot_id):
    max_index = -1
    slot_id = str(slot_id or "").strip()
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_slot = str(row.get("custom_slot_id", "") or "").strip()
        if row_slot and slot_id and row_slot != slot_id:
            continue
        if str(row.get("storage", "")).strip() != "custom":
            continue
        try:
            max_index = max(max_index, int(row.get("custom_row_index", -1)))
        except Exception:
            continue
    return max_index + 1


def _append_inventory_visual_empty_rows(window, table, binding, count):
    if table is None or not isinstance(binding, dict):
        return
    rows = binding.get("rows", [])
    if not isinstance(rows, list):
        return
    slot_id = str(binding.get("section_id", "") or "").strip()
    next_index = window._next_inventory_custom_row_index(rows, slot_id)
    table.blockSignals(True)
    try:
        for _ in range(max(0, int(count))):
            row_data = {
                "name": "",
                "pl": "",
                "count": "",
                "storage": "custom",
                "custom_slot_id": slot_id,
                "custom_row_index": next_index,
                "is_empty_slot": True,
            }
            rows.append(row_data)
            qt_row = table.rowCount()
            table.insertRow(qt_row)
            for column_index in range(3):
                item = QTableWidgetItem("")
                item.setData(Qt.UserRole, "")
                item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                if column_index in (1, 2):
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                table.setItem(qt_row, column_index, item)
            next_index += 1
    finally:
        table.blockSignals(False)


def on_inventory_table_cell_changed(window, table, row_index, column_index):
    if window._inventory_loading:
        return
    binding = window._inventory_table_bindings.get(id(table))
    if not isinstance(binding, dict):
        return
    rows = binding.get("rows", [])
    if not isinstance(rows, list) or row_index < 0 or row_index >= len(rows):
        return
    row = rows[row_index]
    if not isinstance(row, dict):
        return

    column_map = {
        0: ("name", "name_cell"),
        1: ("pl", "pl_cell"),
        2: ("count", "count_cell"),
    }
    if column_index not in column_map:
        return
    value_key, cell_key = column_map[column_index]
    cell_ref = str(row.get(cell_key, "") or "").strip().upper()

    item = table.item(row_index, column_index)
    if item is None:
        return
    new_value = str(item.text())
    old_value = str(item.data(Qt.UserRole) or "")
    if new_value == old_value:
        return
    was_row_empty = window._is_inventory_row_empty(row)
    row_count_before = table.rowCount()

    try:
        if cell_ref:
            window.loader.set_cell_value("Inventar", cell_ref, new_value)
            window.loader.save_active_character_json()
            item.setData(Qt.UserRole, new_value)
            row[value_key] = new_value
            row["is_empty_slot"] = not bool(
                str(row.get("name", "") or "")
                or str(row.get("pl", "") or "")
                or str(row.get("count", "") or "")
            )
            log_debug("inventory", f'INVENTORY EDIT Inventar!{cell_ref} = "{new_value}"')
            log_debug("inventory", "INVENTORY SAVE active character saved")
        else:
            slot_id = str(row.get("custom_slot_id", binding.get("section_id", "")) or "").strip()
            custom_index = row.get("custom_row_index", row_index)
            if not slot_id:
                return
            window.loader.set_inventory_custom_row_value(slot_id, custom_index, value_key, new_value)
            window.loader.save_active_character_json()
            item.setData(Qt.UserRole, new_value)
            row[value_key] = new_value
            row["storage"] = "custom"
            row["custom_slot_id"] = slot_id
            try:
                row["custom_row_index"] = int(custom_index)
            except Exception:
                row["custom_row_index"] = row_index
            row["is_empty_slot"] = not bool(
                str(row.get("name", "") or "")
                or str(row.get("pl", "") or "")
                or str(row.get("count", "") or "")
            )
            log_debug("inventory", f'INVENTORY CUSTOM EDIT {slot_id}[{custom_index}].{value_key} = "{new_value}"')
            log_debug("inventory", "INVENTORY SAVE active character saved")

        table.blockSignals(True)
        try:
            table.resizeRowToContents(row_index)
            min_row_h = window._safe_int(binding.get("min_row_h", 34), 34)
            max_row_h = window._safe_int(binding.get("max_row_h", 90), 90)
            height = max(min_row_h, table.rowHeight(row_index))
            if max_row_h > 0:
                height = min(max_row_h, height)
            table.setRowHeight(row_index, height)
        finally:
            table.blockSignals(False)

        is_row_empty_now = window._is_inventory_row_empty(row)
        row_is_near_end = row_index >= max(0, row_count_before - 3)
        if was_row_empty and not is_row_empty_now and row_is_near_end:
            window._append_inventory_visual_empty_rows(table, binding, 3)
            table.blockSignals(True)
            try:
                table.resizeRowsToContents()
                window._apply_inventory_row_heights(
                    table,
                    window._safe_int(binding.get("min_row_h", 34), 34),
                    window._safe_int(binding.get("max_row_h", 90), 90),
                )
            finally:
                table.blockSignals(False)
    except Exception as exc:
        log_error("inventory", f"edit failed: {exc}")
        table.blockSignals(True)
        item.setText(old_value)
        table.blockSignals(False)
