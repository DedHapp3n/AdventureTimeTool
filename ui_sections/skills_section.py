from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QFrame, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit

from app_logger import log_debug


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
    tab_font_size = window._safe_int(tabs_cfg.get("font_size", 20), 20)
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
        button.clicked.connect(
            lambda checked=False, cid=category_id: window.on_skill_category_clicked(cid)
        )
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
    window.render_skills_table(screen, screen_cfg.get("table", {}), active_category, attribute_map)
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
