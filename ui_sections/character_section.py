from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit


def render_character_initiative_panel(window, character_screen, character_panel, attribute_panel, default_color):
    panel_cfg = character_screen.get("initiative_panel", {})
    if not isinstance(panel_cfg, dict) or not bool(panel_cfg.get("enabled", False)):
        return

    data = window.get_character_initiative_data()
    roll_value = data.get("roll_value") if isinstance(data, dict) else None
    panel = QFrame(window.content_layer)
    panel_x = window._safe_int(panel_cfg.get("x", character_panel.x() + character_panel.width() + 20), character_panel.x() + character_panel.width() + 20)
    panel_y = window._safe_int(panel_cfg.get("y", attribute_panel.y() + attribute_panel.height() + 6), attribute_panel.y() + attribute_panel.height() + 6)
    panel_w = window._safe_int(panel_cfg.get("w", 260), 260)
    panel_h = window._safe_int(panel_cfg.get("h", 125), 125)
    panel.setGeometry(panel_x, panel_y, panel_w, panel_h)
    panel.setStyleSheet(
        "QFrame {"
        f"background: {str(panel_cfg.get('background', 'rgba(5, 5, 5, 95)'))};"
        f"border: 1px solid {str(panel_cfg.get('border_color', 'rgba(242, 210, 139, 90)'))};"
        "border-radius: 6px;"
        "}"
    )
    panel.show()

    title = str(panel_cfg.get("title", "Initiative"))
    title_size = window._safe_int(panel_cfg.get("title_font_size", 18), 18)
    font_size = window._safe_int(panel_cfg.get("font_size", 16), 16)
    label_color = str(panel_cfg.get("color", default_color))
    value_color = str(panel_cfg.get("value_color", "#7fd0ff"))
    window.create_panel_text(
        panel,
        {"x": 10, "y": 8, "w": panel_w - 20, "h": 26},
        title,
        title_size,
        label_color,
        bold=True,
        align="left",
    )
    raw_text = str(data.get("raw_value", "-")) if isinstance(data, dict) else "-"
    bonus_text = str(data.get("bonus", 0)) if isinstance(data, dict) else "0"
    roll_text = str(roll_value) if roll_value is not None else "-"
    window.create_panel_text(panel, {"x": 12, "y": 36, "w": 96, "h": 22}, "Wert:", font_size, label_color, bold=True)
    window.create_panel_text(panel, {"x": 100, "y": 36, "w": panel_w - 112, "h": 22}, raw_text, font_size, value_color, bold=True)
    window.create_panel_text(panel, {"x": 12, "y": 59, "w": 96, "h": 22}, "Bonus:", font_size, label_color, bold=True)
    data_cfg = panel_cfg.get("data", {}) if isinstance(panel_cfg.get("data", {}), dict) else {}
    bonus_editable = bool(data_cfg.get("bonus_editable", False))
    bonus_cell = str(data.get("bonus_cell", "") if isinstance(data, dict) else "").strip().upper()
    bonus_sheet = str(data.get("sheet", "") if isinstance(data, dict) else "").strip()
    bonus_old_raw = str(data.get("raw_bonus", bonus_text) if isinstance(data, dict) else bonus_text)
    if bonus_editable and bonus_cell and bonus_sheet:
        bonus_editor = QLineEdit(panel)
        bonus_editor.setGeometry(100, 59, panel_w - 112, 22)
        bonus_editor.setText(bonus_text)
        bonus_editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bonus_editor.setStyleSheet(
            "QLineEdit {"
            "background: rgba(0,0,0,40);"
            "border: 1px solid rgba(216, 208, 176, 45);"
            f"color: {value_color};"
            f"font-size: {font_size}px;"
            "font-weight: 700;"
            "padding: 0px 4px;"
            "}"
            "QLineEdit:focus { border: 1px solid rgba(216, 208, 176, 120); }"
        )
        bonus_editor.editingFinished.connect(
            lambda e=bonus_editor, s=bonus_sheet, c=bonus_cell, o=bonus_old_raw: window._on_character_initiative_bonus_edit_finished(e, s, c, o)
        )
        bonus_editor.show()
    else:
        window.create_panel_text(panel, {"x": 100, "y": 59, "w": panel_w - 112, "h": 22}, bonus_text, font_size, value_color, bold=True)
    window.create_panel_text(panel, {"x": 12, "y": 82, "w": 96, "h": 22}, "Rollwert:", font_size, label_color, bold=True)
    window.create_panel_text(panel, {"x": 100, "y": 82, "w": panel_w - 112, "h": 22}, roll_text, font_size, value_color, bold=True)

    button_cfg = {
        "x": window._safe_int(panel_cfg.get("button_x", 12), 12),
        "y": window._safe_int(panel_cfg.get("button_y", panel_h - 38), panel_h - 38),
        "w": window._safe_int(panel_cfg.get("button_w", panel_w - 24), panel_w - 24),
        "h": window._safe_int(panel_cfg.get("button_h", 28), 28),
        "asset": str(panel_cfg.get("button_asset", "buttons/menu_button_medium.png")),
        "font_size": window._safe_int(panel_cfg.get("button_font_size", 16), 16),
        "color": str(panel_cfg.get("color", label_color)),
    }
    btn = window.create_asset_text_button(
        panel,
        button_cfg,
        str(panel_cfg.get("button_text", "Ini-Wurf")),
        window.open_character_initiative_roll,
    )
    btn_widget = btn.get("button") if isinstance(btn, dict) else btn
    if btn_widget is not None:
        btn_widget.setEnabled(roll_value is not None)


def render_character_paradigm_panel(window, character_screen, attribute_panel, default_color):
    panel_cfg = character_screen.get("paradigm_panel", {})
    if not isinstance(panel_cfg, dict) or not bool(panel_cfg.get("enabled", False)):
        return

    analysis = window._analyze_character_paradigm_area("Charakterbogen")
    window.character_paradigm_analysis = analysis
    panel = QFrame(window.content_layer)
    panel_x = window._safe_int(panel_cfg.get("x", attribute_panel.x()), attribute_panel.x())
    panel_y = window._safe_int(panel_cfg.get("y", attribute_panel.y() + attribute_panel.height() + 8), attribute_panel.y() + attribute_panel.height() + 8)
    panel_w = window._safe_int(panel_cfg.get("w", 440), 440)
    panel_h = window._safe_int(panel_cfg.get("h", 170), 170)
    layout_cfg = panel_cfg.get("layout", {})
    fallback_used = not isinstance(layout_cfg, dict)
    if not isinstance(layout_cfg, dict):
        layout_cfg = {}
    padding = window._safe_int(layout_cfg.get("padding", 10), 10)
    title_h = window._safe_int(layout_cfg.get("title_h", 28), 28)
    name_h = window._safe_int(layout_cfg.get("name_h", 34), 34)
    label_w = window._safe_int(layout_cfg.get("label_w", 70), 70)
    marker_w = window._safe_int(layout_cfg.get("marker_w", 24), 24)
    marker_h = window._safe_int(layout_cfg.get("marker_h", 24), 24)
    marker_gap = window._safe_int(layout_cfg.get("marker_gap", 4), 4)
    row_h = window._safe_int(layout_cfg.get("row_h", 30), 30)
    column_gap = window._safe_int(layout_cfg.get("column_gap", 10), 10)

    window._character_paradigm_debug(
        f"[CHARACTER PARADIGM LAYOUT] x={panel_x} y={panel_y} w={panel_w} h={panel_h}"
    )
    window._character_paradigm_debug("[CHARACTER PARADIGM CONFIG] source=ui_layout.json")
    if fallback_used:
        window._character_paradigm_debug("[CHARACTER PARADIGM LAYOUT] fallback used")

    panel.setGeometry(panel_x, panel_y, panel_w, panel_h)
    panel.setStyleSheet(
        "QFrame {"
        f"background: {str(panel_cfg.get('background', 'rgba(5, 5, 5, 95)'))};"
        f"border: 1px solid {str(panel_cfg.get('border_color', 'rgba(242, 210, 139, 90)'))};"
        "border-radius: 6px;"
        "}"
    )
    panel.show()

    title = str(panel_cfg.get("title", "Paradigmen"))
    window.create_panel_text(
        panel,
        {"x": padding, "y": padding, "w": panel_w - padding * 2, "h": title_h},
        title,
        window._safe_int(panel_cfg.get("title_font_size", 18), 18),
        str(panel_cfg.get("label_color", default_color)),
        bold=True,
        align="left",
    )

    if not analysis.get("columns"):
        window.create_panel_text(
            panel,
            {"x": padding, "y": padding + title_h + 6, "w": panel_w - padding * 2, "h": max(24, row_h)},
            "Keine Paradigmen gefunden",
            window._safe_int(panel_cfg.get("font_size", 14), 14),
            str(panel_cfg.get("text_color", "#ffffff")),
            align="left",
        )
        return

    edit_allowed = window._paradigm_edit_allowed()
    rows_cfg = panel_cfg.get("rows", [])
    if not isinstance(rows_cfg, list) or not rows_cfg:
        rows_cfg = [{"id": "grad", "label": "Grad"}, {"id": "brand", "label": "Brand"}, {"id": "daily", "label": "Daily"}]
    cols_cfg = panel_cfg.get("columns", {})
    marker_cfg = panel_cfg.get("marker", {})
    if not isinstance(marker_cfg, dict):
        marker_cfg = {}
    col_count = window._safe_int(cols_cfg.get("count", 3), 3)
    start_x = padding + label_w
    available_w = panel_w - start_x - padding
    col_w = max(80, (available_w - (col_count - 1) * column_gap) // max(1, col_count))
    header_y = padding + title_h + 6
    row_y_start = header_y + name_h
    marker_use_icon = bool(marker_cfg.get("use_icon", True))
    marker_active_asset = str(marker_cfg.get("active_asset", "icons/x.jpg") or "").strip()
    marker_fallback_text = str(marker_cfg.get("fallback_text", "X"))
    marker_icon_padding = max(0, window._safe_int(marker_cfg.get("icon_padding", 4), 4))

    for idx, col_info in enumerate(analysis.get("columns", [])[:col_count]):
        col_x = start_x + idx * (col_w + column_gap)
        name_cell = str(col_info.get("name_cell", ""))
        name_text = str(col_info.get("name", ""))
        name_label = window.create_panel_text(
            panel,
            {"x": col_x, "y": header_y, "w": col_w, "h": name_h},
            name_text,
            window._safe_int(panel_cfg.get("font_size", 14), 14),
            str(panel_cfg.get("text_color", "#ffffff")),
            bold=True,
            align="center",
        )
        if edit_allowed and name_cell:
            name_label.setProperty("character_paradigm_name_edit", True)
            name_label.setProperty("character_paradigm_index", idx)
            name_label.setProperty("character_paradigm_cell_ref", name_cell)
            name_label.setProperty("character_paradigm_old", name_text)
            name_label.setProperty("character_paradigm_sheet", str(analysis.get("sheet", "Charakterbogen")))
            name_label.installEventFilter(window)

        for row_idx, row_cfg in enumerate(rows_cfg):
            row_id = str(row_cfg.get("id", "")).strip().lower()
            cells = col_info.get(f"{row_id}_cells", [])
            if not isinstance(cells, list):
                cells = []
            marker_base_x = col_x + 2
            for marker_idx, cell_ref in enumerate(cells):
                value = window.get_cache_display_value(str(analysis.get("sheet", "Charakterbogen")), cell_ref, "")
                active = str(value or "").strip().lower() == "x"
                marker = QLabel(panel)
                mx = marker_base_x + marker_idx * (marker_w + marker_gap)
                my = row_y_start + row_idx * row_h + max(0, (row_h - marker_h) // 2)
                marker.setGeometry(mx, my, marker_w, marker_h)
                marker.setAlignment(Qt.AlignCenter)
                marker.setText("")
                if active:
                    icon_set = False
                    if marker_use_icon and marker_active_asset:
                        pixmap = window.load_ui_pixmap(marker_active_asset)
                        if pixmap is not None and not pixmap.isNull():
                            target_w = max(1, marker_w - marker_icon_padding * 2)
                            target_h = max(1, marker_h - marker_icon_padding * 2)
                            marker.setPixmap(
                                pixmap.scaled(
                                    target_w,
                                    target_h,
                                    Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation,
                                )
                            )
                            icon_set = True
                    if not icon_set:
                        marker.setText(marker_fallback_text)
                marker.setStyleSheet(
                    "QLabel {"
                    "background: rgba(0,0,0,80);"
                    "border: 1px solid rgba(232, 224, 200, 70);"
                    f"color: {str(panel_cfg.get('value_color', '#7fd0ff'))};"
                    "font-weight: 700;"
                    "}"
                )
                if edit_allowed and cell_ref:
                    marker.setProperty("character_paradigm_marker_toggle", True)
                    marker.setProperty("character_paradigm_row", row_id)
                    marker.setProperty("character_paradigm_index", idx)
                    marker.setProperty("character_paradigm_marker_index", marker_idx)
                    marker.setProperty("character_paradigm_cell_ref", cell_ref)
                    marker.setProperty("character_paradigm_active", active)
                    marker.setProperty("character_paradigm_sheet", str(analysis.get("sheet", "Charakterbogen")))
                    marker.installEventFilter(window)
                marker.show()

    for row_idx, row_cfg in enumerate(rows_cfg):
        row_label = str(row_cfg.get("label", row_cfg.get("id", "")))
        window.create_panel_text(
            panel,
            {"x": padding, "y": row_y_start + row_idx * row_h, "w": max(10, label_w - 8), "h": row_h},
            row_label,
            window._safe_int(panel_cfg.get("font_size", 14), 14),
            str(panel_cfg.get("label_color", default_color)),
            bold=True,
            align="left",
        )


def render_character_section(window):
    if window.content_layer is None:
        return
    window._character_edit_cfg = window._character_edit_config()
    window._character_rendering = True
    character_screen = window.main_ui_layout_config.get("character_screen")
    if not isinstance(character_screen, dict):
        window.render_character_front()
        window._character_rendering = False
        return

    default_text_style = window.theme_style.get("default_text", {})
    default_color = str(default_text_style.get("color", "#e8e0c8"))
    data_map = character_screen.get("data_map", {})
    text_layout = character_screen.get("text_layout", {})
    panels_cfg = character_screen.get("panels", {})

    character_panel_cfg = panels_cfg.get("character_info_panel", {})
    attribute_panel_cfg = panels_cfg.get("attribute_panel", {})
    perk_panel_cfg = panels_cfg.get("perk_panel", {})

    character_panel = window._create_content_panel(window.content_layer, character_panel_cfg)
    attribute_panel = window._create_content_panel(window.content_layer, attribute_panel_cfg)
    perk_panel = window._create_content_panel(window.content_layer, perk_panel_cfg)

    default_sheet = "Charakterbogen"
    basic_map = data_map.get("basic", {})
    name_value = window._read_data_map_cell(basic_map.get("name", "G1"), default_sheet, "Unbekannter Charakter")
    race_value = window._read_data_map_cell(basic_map.get("race", "G3"), default_sheet)
    size_value = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("size", "G5"), default_sheet),
        "auto",
    )
    weight_value = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("weight", "G7"), default_sheet),
        "auto",
    )
    hp_current = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("hp_current", "B10"), default_sheet),
        "int",
    )
    hp_max = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("hp_max", "F10"), default_sheet),
        "int",
    )
    mp_current = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("mp_current", "B13"), default_sheet),
        "int",
    )
    mp_max = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("mp_max", "F13"), default_sheet),
        "int",
    )
    exp_current = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("exp_current", "B16"), default_sheet),
        "int",
    )
    exp_max = window.format_character_display_value(
        window._read_data_map_cell(basic_map.get("exp_max", "F16"), default_sheet),
        "int",
    )

    info_layout = text_layout.get("character_info_panel", text_layout.get("info", {}))
    title_cfg = info_layout.get("title", {})
    window._create_character_value_editor(
        character_panel,
        title_cfg if isinstance(title_cfg, dict) else {},
        "name",
        basic_map.get("name", "G1"),
        default_sheet,
        name_value if name_value != "-" else "Unbekannter Charakter",
        window.get_text_font_size(title_cfg, 30),
        window.get_text_color(title_cfg, default_color),
        bold=window.get_text_bold(title_cfg, True),
        align=window.get_text_align(title_cfg, "left"),
        section_key="basic_fields",
    )

    fields_cfg = info_layout.get("fields", {})
    field_rows = fields_cfg.get("rows", []) if isinstance(fields_cfg, dict) else []
    if isinstance(field_rows, list) and field_rows:
        portrait_cfg = info_layout.get("portrait", {})
        if isinstance(portrait_cfg, dict) and bool(portrait_cfg.get("enabled", False)):
            portrait = QFrame(character_panel)
            portrait.setGeometry(
                window._safe_int(portrait_cfg.get("x", 0), 0),
                window._safe_int(portrait_cfg.get("y", 0), 0),
                window._safe_int(portrait_cfg.get("w", 120), 120),
                window._safe_int(portrait_cfg.get("h", 160), 160),
            )
            portrait.setStyleSheet(
                f"background: {str(portrait_cfg.get('fallback_color', 'rgba(0, 0, 0, 90)'))};"
                "border: 1px solid rgba(255, 255, 255, 35);"
            )
            portrait.lower()
            portrait.show()

        field_single_sources = {
            "race": basic_map.get("race", "G3"),
            "size": basic_map.get("size", "G5"),
            "weight": basic_map.get("weight", "G7"),
        }
        field_pair_sources = {
            "hp": (basic_map.get("hp_current", "B10"), basic_map.get("hp_max", "F10")),
            "mp": (basic_map.get("mp_current", "B13"), basic_map.get("mp_max", "F13")),
            "exp": (basic_map.get("exp_current", "B16"), basic_map.get("exp_max", "F16")),
            "lifeforce": (
                basic_map.get("lifeforce_current", ""),
                basic_map.get("lifeforce_max", ""),
            ),
            "sanity": (
                basic_map.get("sanity_current", ""),
                basic_map.get("sanity_max", ""),
            ),
            "faith": (
                basic_map.get("faith_current", ""),
                basic_map.get("faith_max", ""),
            ),
        }
        label_font_default = window._safe_int(fields_cfg.get("label_font_size", 18), 18)
        value_font_default = window._safe_int(fields_cfg.get("value_font_size", 18), 18)
        label_color_default = str(fields_cfg.get("label_color", default_color))
        value_color_default = str(fields_cfg.get("value_color", "#ffffff"))
        bold_values_default = bool(fields_cfg.get("bold_values", True))

        for row in field_rows:
            if not isinstance(row, dict):
                continue
            row_id = str(row.get("id", "")).strip().lower()
            if not row_id:
                continue
            mode = str(row.get("mode", "raw" if row_id in ("race",) else "auto"))
            label_text = str(row.get("label", row_id.capitalize()))
            if row_id in field_pair_sources:
                current_src, max_src = field_pair_sources[row_id]
                split_enabled = isinstance(row.get("current_rect"), dict) and isinstance(row.get("max_rect"), dict)
                current = window.format_character_display_value(
                    window._read_data_map_cell(current_src, default_sheet),
                    mode,
                )
                maximum = window.format_character_display_value(
                    window._read_data_map_cell(max_src, default_sheet),
                    mode,
                )
            else:
                source = field_single_sources.get(row_id)
                value_text = window.format_character_display_value(
                    window._read_data_map_cell(source, default_sheet),
                    mode,
                )

            label_widget = window.create_panel_text(
                character_panel,
                row.get("label_rect", {}),
                label_text,
                window._safe_int(row.get("label_font_size", row.get("font_size", label_font_default)), 14),
                str(row.get("label_color", row.get("color", label_color_default))),
                bold=bool(row.get("label_bold", False)),
                align=str(row.get("label_align", "left")),
            )
            window._make_character_resource_label_clickable(label_widget, row_id)
            if row_id in field_pair_sources:
                current_src, max_src = field_pair_sources[row_id]
                split_enabled = isinstance(row.get("current_rect"), dict) and isinstance(row.get("max_rect"), dict)
                current_rect = row.get("current_rect", {})
                max_rect = row.get("max_rect", {})
                if not split_enabled:
                    current_rect = row.get("value_rect", {})
                    max_rect = row.get("value_rect", {})
                    vx = window._safe_int(current_rect.get("x", 0), 0)
                    vy = window._safe_int(current_rect.get("y", 0), 0)
                    vw = window._safe_int(current_rect.get("w", 160), 160)
                    vh = window._safe_int(current_rect.get("h", 30), 30)
                    half = max(40, vw // 2)
                    current_rect = {"x": vx, "y": vy, "w": half, "h": vh}
                    max_rect = {"x": vx + half, "y": vy, "w": max(20, vw - half), "h": vh}
                current_sheet, current_cell = window._resolve_data_map_cell_ref(current_src, default_sheet)
                max_sheet, max_cell = window._resolve_data_map_cell_ref(max_src, default_sheet)
                window._character_debug(
                    f"[CHARACTER BASIC SPLIT] id={row_id} current_cell={current_cell or '-'} "
                    f"max_cell={max_cell or '-'} legacy_value_rect_ignored={bool(split_enabled)}"
                )
                value_font = window._safe_int(row.get("value_font_size", row.get("font_size", value_font_default)), 15)
                value_color = str(row.get("value_color", row.get("color", value_color_default)))
                value_bold = bool(row.get("bold_value", bold_values_default))
                value_align = str(row.get("value_align", "left"))
                max_editable = bool(max_cell) and not (
                    bool(current_cell)
                    and bool(max_cell)
                    and current_sheet == max_sheet
                    and current_cell == max_cell
                )
                if not max_editable:
                    window._character_debug(
                        f"[CHARACTER BASIC EDIT SKIP] field={row_id}_max reason="
                        f"{'same_cell_as_current' if max_cell else 'no_cell_ref'}"
                    )
                window._create_character_value_editor(
                    character_panel,
                    current_rect,
                    f"{row_id}_current",
                    current_src,
                    default_sheet,
                    current,
                    value_font,
                    value_color,
                    bold=value_bold,
                    align=value_align,
                    section_key="basic_fields",
                )
                window._create_character_value_editor(
                    character_panel,
                    max_rect,
                    f"{row_id}_max",
                    max_src,
                    default_sheet,
                    maximum,
                    value_font,
                    value_color,
                    bold=value_bold,
                    align=value_align,
                    editable=max_editable,
                    section_key="basic_fields",
                )
            else:
                window._character_debug(f"[CHARACTER BASIC LEGACY] id={row_id} value_rect used")
                window._create_character_value_editor(
                    character_panel,
                    row.get("value_rect", {}),
                    row_id,
                    field_single_sources.get(row_id),
                    default_sheet,
                    value_text,
                    window._safe_int(row.get("value_font_size", row.get("font_size", value_font_default)), 15),
                    str(row.get("value_color", row.get("color", value_color_default))),
                    bold=bool(row.get("bold_value", bold_values_default)),
                    align=str(row.get("value_align", "left")),
                    section_key="basic_fields",
                )
    else:
        basic_rows_cfg = info_layout.get("basic_rows", {})
        basic_rows = basic_rows_cfg.get("rows", [])
        basic_values = {"race": race_value, "size": size_value, "weight": weight_value}
        if isinstance(basic_rows, list) and basic_rows:
            for row in basic_rows:
                if not isinstance(row, dict):
                    continue
                row_id = str(row.get("id", "")).strip().lower()
                label_text = str(row.get("label", row_id.capitalize() if row_id else ""))
                value_text = basic_values.get(row_id, "-")
                window.create_panel_text(
                    character_panel,
                    row.get("label_rect", {}),
                    label_text,
                    window._safe_int(row.get("label_font_size", basic_rows_cfg.get("label_font_size", 18)), 18),
                    str(row.get("label_color", basic_rows_cfg.get("label_color", default_color))),
                    bold=False,
                    align=str(row.get("label_align", "left")),
                )
                window._create_character_value_editor(
                    character_panel,
                    row.get("value_rect", {}),
                    row_id,
                    basic_map.get(row_id, ""),
                    default_sheet,
                    value_text,
                    window._safe_int(row.get("value_font_size", basic_rows_cfg.get("value_font_size", 18)), 18),
                    str(row.get("value_color", basic_rows_cfg.get("value_color", "#ffffff"))),
                    bold=True,
                    align=str(row.get("value_align", "left")),
                    section_key="basic_fields",
                )
        else:
            rows_cfg = info_layout.get("rows", {})
            rows_x_label = window._safe_int(rows_cfg.get("label_x", 24), 24)
            rows_x_value = window._safe_int(rows_cfg.get("value_x", 210), 210)
            rows_start_y = window._safe_int(rows_cfg.get("start_y", 90), 90)
            rows_gap = window._safe_int(rows_cfg.get("row_gap", 34), 34)
            rows_font = window._safe_int(rows_cfg.get("font_size", 18), 18)
            rows_values = [("Rasse", "race", race_value), ("Größe", "size", size_value), ("Gewicht", "weight", weight_value)]
            for i, (label_text, field_key, value_text) in enumerate(rows_values):
                y = rows_start_y + i * rows_gap
                window.create_panel_text(
                    character_panel,
                    {"x": rows_x_label, "y": y, "w": 180, "h": 30},
                    f"{label_text}:",
                    rows_font,
                    str(rows_cfg.get("label_color", default_color)),
                )
                window._create_character_value_editor(
                    character_panel,
                    {"x": rows_x_value, "y": y, "w": max(120, character_panel.width() - rows_x_value - 20), "h": 30},
                    field_key,
                    basic_map.get(field_key, ""),
                    default_sheet,
                    value_text,
                    rows_font,
                    str(rows_cfg.get("value_color", "#ffffff")),
                    bold=True,
                    section_key="basic_fields",
                )

        stats_rows_cfg = info_layout.get("stat_rows", {})
        stats_rows = stats_rows_cfg.get("rows", [])
        stats_values = {
            "hp": f"{hp_current} / {hp_max}",
            "mp": f"{mp_current} / {mp_max}",
            "exp": f"{exp_current} / {exp_max}",
        }
        if isinstance(stats_rows, list) and stats_rows:
            for row in stats_rows:
                if not isinstance(row, dict):
                    continue
                row_id = str(row.get("id", "")).strip().lower()
                label_text = str(row.get("label", row_id.upper() if row_id else ""))
                value_text = stats_values.get(row_id, "-")
                label_widget = window.create_panel_text(
                    character_panel,
                    row.get("label_rect", {}),
                    label_text,
                    window._safe_int(row.get("label_font_size", stats_rows_cfg.get("label_font_size", 20)), 20),
                    str(row.get("label_color", stats_rows_cfg.get("label_color", default_color))),
                    bold=True,
                    align=str(row.get("label_align", "left")),
                )
                window._make_character_resource_label_clickable(label_widget, row_id)
                if row_id in ("hp", "mp", "exp"):
                    current_src = basic_map.get(f"{row_id}_current", "")
                    max_src = basic_map.get(f"{row_id}_max", "")
                    current_rect = row.get("current_rect", row.get("value_rect", {}))
                    max_rect = row.get("max_rect", row.get("value_rect", {}))
                    vx = window._safe_int(current_rect.get("x", 0), 0)
                    vy = window._safe_int(current_rect.get("y", 0), 0)
                    vw = window._safe_int(current_rect.get("w", 160), 160)
                    vh = window._safe_int(current_rect.get("h", 30), 30)
                    if "current_rect" not in row or "max_rect" not in row:
                        half = max(40, vw // 2)
                        current_rect = {"x": vx, "y": vy, "w": half, "h": vh}
                        max_rect = {"x": vx + half, "y": vy, "w": max(20, vw - half), "h": vh}
                    vf = window._safe_int(row.get("value_font_size", stats_rows_cfg.get("value_font_size", 26)), 26)
                    vc = str(row.get("value_color", stats_rows_cfg.get("value_color", "#ffffff")))
                    va = str(row.get("value_align", "left"))
                    window._create_character_value_editor(
                        character_panel,
                        current_rect,
                        f"{row_id}_current",
                        current_src,
                        default_sheet,
                        window.format_character_display_value(window._read_data_map_cell(current_src, default_sheet), "int"),
                        vf,
                        vc,
                        bold=True,
                        align=va,
                        section_key="basic_fields",
                    )
                    window._create_character_value_editor(
                        character_panel,
                        max_rect,
                        f"{row_id}_max",
                        max_src,
                        default_sheet,
                        window.format_character_display_value(window._read_data_map_cell(max_src, default_sheet), "int"),
                        vf,
                        vc,
                        bold=True,
                        align=va,
                        section_key="basic_fields",
                    )
                else:
                    window.create_panel_text(
                        character_panel,
                        row.get("value_rect", {}),
                        value_text,
                        window._safe_int(row.get("value_font_size", stats_rows_cfg.get("value_font_size", 26)), 26),
                        str(row.get("value_color", stats_rows_cfg.get("value_color", "#ffffff"))),
                        bold=True,
                        align=str(row.get("value_align", "left")),
                    )
        else:
            stats_cfg = info_layout.get("stats", {})
            stats_x_label = window._safe_int(stats_cfg.get("label_x", 24), 24)
            stats_x_value = window._safe_int(stats_cfg.get("value_x", 210), 210)
            stats_start_y = window._safe_int(stats_cfg.get("start_y", 230), 230)
            stats_gap = window._safe_int(stats_cfg.get("row_gap", 52), 52)
            hp_label_font = window._safe_int(stats_cfg.get("hp_label_font_size", 22), 22)
            hp_value_font = window._safe_int(stats_cfg.get("hp_value_font_size", 30), 30)
            mp_label_font = window._safe_int(stats_cfg.get("mp_label_font_size", 20), 20)
            mp_value_font = window._safe_int(stats_cfg.get("mp_value_font_size", 28), 28)
            exp_label_font = window._safe_int(stats_cfg.get("exp_label_font_size", 18), 18)
            exp_value_font = window._safe_int(stats_cfg.get("exp_value_font_size", 22), 22)
            stat_rows = [
                ("HP", f"{hp_current} / {hp_max}", hp_label_font, hp_value_font),
                ("MP", f"{mp_current} / {mp_max}", mp_label_font, mp_value_font),
                ("EXP", f"{exp_current} / {exp_max}", exp_label_font, exp_value_font),
            ]
            for i, (label_text, value_text, lf, vf) in enumerate(stat_rows):
                y = stats_start_y + i * stats_gap
                label_widget = window.create_panel_text(
                    character_panel,
                    {"x": stats_x_label, "y": y, "w": 140, "h": 34},
                    f"{label_text}:",
                    lf,
                    str(stats_cfg.get("label_color", default_color)),
                    bold=True,
                )
                window._make_character_resource_label_clickable(label_widget, label_text.lower())
                window.create_panel_text(
                    character_panel,
                    {"x": stats_x_value, "y": y - 8, "w": max(160, character_panel.width() - stats_x_value - 20), "h": max(34, vf + 10)},
                    value_text,
                    vf,
                    str(stats_cfg.get("value_color", "#ffffff")),
                    bold=True,
                )

        for bar_key, default_y, bar_color in (("hp_bar", 276, "#cc4444"), ("mp_bar", 328, "#4477cc")):
            bar_cfg = info_layout.get(bar_key, {})
            if bool(bar_cfg.get("enabled", True)):
                bar_bg = QFrame(character_panel)
                bar_x = window._safe_int(bar_cfg.get("x", 24), 24)
                bar_y = window._safe_int(bar_cfg.get("y", default_y), default_y)
                bar_w = window._safe_int(bar_cfg.get("w", 260), 260)
                bar_h = window._safe_int(bar_cfg.get("h", 12), 12)
                bar_bg.setGeometry(bar_x, bar_y, bar_w, bar_h)
                bar_bg.setStyleSheet("background: rgba(10, 10, 10, 180); border: 1px solid rgba(0,0,0,120);")
                bar_fill = QFrame(bar_bg)
                bar_fill.setGeometry(0, 0, bar_w, bar_h)
                bar_fill.setStyleSheet(f"background: {str(bar_cfg.get('color', bar_color))};")
                bar_bg.show()

    attr_layout = text_layout.get("attribute_panel", text_layout.get("attributes", {}))
    attr_map = data_map.get("attributes", {})
    body_map = attr_map.get("body", {})
    mind_map = attr_map.get("mind", {})

    panel_title_cfg = attr_layout.get("panel_title", {})
    if isinstance(panel_title_cfg, dict):
        panel_title_text = str(panel_title_cfg.get("text", "Attribute")).strip() or "Attribute"
        panel_title_rect = panel_title_cfg.get("rect", panel_title_cfg)
        window.create_panel_text(
            attribute_panel,
            panel_title_rect if isinstance(panel_title_rect, dict) else {},
            panel_title_text,
            window.get_text_font_size(panel_title_cfg, 24),
            window.get_text_color(panel_title_cfg, default_color),
            bold=window.get_text_bold(panel_title_cfg, True),
            align=window.get_text_align(panel_title_cfg, "center"),
        )

    body_header_layout = attr_layout.get("body_header", {})
    mind_header_layout = attr_layout.get("mind_header", {})
    header_style = attr_layout.get("header", {})
    rows_style = attr_layout.get("rows", {})
    value_font_size = window._safe_int(
        attr_layout.get("value_font_size", rows_style.get("font_size", 18)),
        18,
    )

    body_header_label = str(body_map.get("label", body_header_layout.get("label", "Körper"))).strip() + ":"
    mind_header_label = str(mind_map.get("label", mind_header_layout.get("label", "Geist"))).strip() + ":"

    def resolve_cell_value(mapping, fallback="-"):
        if isinstance(mapping, str):
            return window.get_cache_display_value(default_sheet, mapping, fallback)
        if isinstance(mapping, dict):
            sheet = str(mapping.get("sheet", default_sheet))
            cell = mapping.get("cell")
            if isinstance(cell, str):
                return window.get_cache_display_value(sheet, cell, fallback)
        return fallback

    body_header_cell = body_map.get("value", body_map.get("header", "-"))
    mind_header_cell = mind_map.get("value", mind_map.get("header", "-"))
    body_header_raw_value = resolve_cell_value(body_header_cell, "-")
    mind_header_raw_value = resolve_cell_value(mind_header_cell, "-")
    body_header_value = window.format_character_display_value(body_header_raw_value, "int")
    mind_header_value = window.format_character_display_value(mind_header_raw_value, "int")
    body_header_cell_txt = (
        body_header_cell
        if isinstance(body_header_cell, str)
        else str(body_header_cell.get("cell", "-")) if isinstance(body_header_cell, dict) else "-"
    )
    mind_header_cell_txt = (
        mind_header_cell
        if isinstance(mind_header_cell, str)
        else str(mind_header_cell.get("cell", "-")) if isinstance(mind_header_cell, dict) else "-"
    )
    window._character_debug(f"[ATTR] body.header {body_header_cell_txt} -> {body_header_value}")
    window._character_debug(f"[ATTR] mind.header {mind_header_cell_txt} -> {mind_header_value}")
    window._character_debug(f"[DISPLAY ATTR] body.header {body_header_raw_value} -> {body_header_value}")
    window._character_debug(f"[DISPLAY ATTR] mind.header {mind_header_raw_value} -> {mind_header_value}")

    window.create_panel_text(
        attribute_panel,
        body_header_layout.get("label_rect", {"x": 24, "y": 24, "w": 120, "h": 30}),
        body_header_label,
        window._safe_int(
            body_header_layout.get(
                "label_font_size",
                body_header_layout.get(
                    "font_size",
                    header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                ),
            ),
            22,
        ),
        str(
            body_header_layout.get(
                "label_color",
                body_header_layout.get(
                    "color",
                    header_style.get("label_color", attr_layout.get("header_color", default_color)),
                ),
            )
        ),
        bold=True,
        align=str(body_header_layout.get("label_align", "center")),
    )
    window._create_character_value_editor(
        attribute_panel,
        body_header_layout.get("value_rect", {"x": 150, "y": 24, "w": 80, "h": 30}),
        "body",
        body_header_cell,
        default_sheet,
        body_header_value,
        window._safe_int(
            body_header_layout.get(
                "value_font_size",
                body_header_layout.get(
                    "font_size",
                    header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                ),
            ),
            22,
        ),
        str(
            body_header_layout.get(
                "value_color",
                body_header_layout.get(
                    "color",
                    header_style.get("value_color", attr_layout.get("header_color", "#ffffff")),
                ),
            )
        ),
        bold=True,
        align=str(body_header_layout.get("value_align", "center")),
        section_key="attributes",
    )
    window.create_panel_text(
        attribute_panel,
        mind_header_layout.get("label_rect", {"x": 320, "y": 24, "w": 120, "h": 30}),
        mind_header_label,
        window._safe_int(
            mind_header_layout.get(
                "label_font_size",
                mind_header_layout.get(
                    "font_size",
                    header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                ),
            ),
            22,
        ),
        str(
            mind_header_layout.get(
                "label_color",
                mind_header_layout.get(
                    "color",
                    header_style.get("label_color", attr_layout.get("header_color", default_color)),
                ),
            )
        ),
        bold=True,
        align=str(mind_header_layout.get("label_align", "center")),
    )
    window._create_character_value_editor(
        attribute_panel,
        mind_header_layout.get("value_rect", {"x": 446, "y": 24, "w": 80, "h": 30}),
        "mind",
        mind_header_cell,
        default_sheet,
        mind_header_value,
        window._safe_int(
            mind_header_layout.get(
                "value_font_size",
                mind_header_layout.get(
                    "font_size",
                    header_style.get("font_size", attr_layout.get("header_font_size", 22)),
                ),
            ),
            22,
        ),
        str(
            mind_header_layout.get(
                "value_color",
                mind_header_layout.get(
                    "color",
                    header_style.get("value_color", attr_layout.get("header_color", "#ffffff")),
                ),
            )
        ),
        bold=True,
        align=str(mind_header_layout.get("value_align", "center")),
        section_key="attributes",
    )

    body_rows_layout = attr_layout.get("body_rows", {})
    mind_rows_layout = attr_layout.get("mind_rows", {})

    def render_attr_rows(group_name, items, rows_layout):
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id", "")).strip()
            if not item_id:
                continue
            row_cfg = rows_layout.get(item_id)
            if not isinstance(row_cfg, dict):
                window._character_debug(f"[ATTR] missing layout for {group_name}: {item_id}")
                continue
            label_text = str(item.get("label", item_id))
            cell_ref = item.get("value")
            raw_value_text = resolve_cell_value(cell_ref, "-")
            value_text = window.format_character_display_value(raw_value_text, "int")
            cell_txt = (
                cell_ref
                if isinstance(cell_ref, str)
                else str(cell_ref.get("cell", "-")) if isinstance(cell_ref, dict) else "-"
            )
            window._character_debug(f"[ATTR] {group_name} {item_id} {cell_txt} -> {value_text}")
            window._character_debug(f"[DISPLAY ATTR] {item_id} {raw_value_text} -> {value_text}")

            window.create_panel_text(
                attribute_panel,
                row_cfg.get("label_rect", {}),
                label_text,
                window._safe_int(
                    row_cfg.get(
                        "label_font_size",
                        row_cfg.get(
                            "font_size",
                            rows_style.get("font_size", attr_layout.get("label_font_size", 18)),
                        ),
                    ),
                    18,
                ),
                str(
                    row_cfg.get(
                        "label_color",
                        row_cfg.get("color", rows_style.get("label_color", default_color)),
                    )
                ),
                bold=False,
                align=str(row_cfg.get("label_align", "left")),
            )
            window._create_character_value_editor(
                attribute_panel,
                row_cfg.get("value_rect", {}),
                item_id.lower(),
                cell_ref,
                default_sheet,
                value_text,
                window._safe_int(
                    row_cfg.get(
                        "value_font_size",
                        row_cfg.get(
                            "font_size",
                            rows_style.get("font_size", attr_layout.get("value_font_size", value_font_size)),
                        ),
                    ),
                    18,
                ),
                str(
                    row_cfg.get(
                        "value_color",
                        row_cfg.get("color", rows_style.get("value_color", "#ffffff")),
                    )
                ),
                bold=True,
                align=str(row_cfg.get("value_align", "center")),
                section_key="attributes",
            )

    render_attr_rows("body", body_map.get("items", []), body_rows_layout)
    render_attr_rows("mind", mind_map.get("items", []), mind_rows_layout)

    def render_wellbeing_block():
        wellbeing_cfg = character_screen.get("wellbeing_panel", {})
        if not isinstance(wellbeing_cfg, dict):
            wellbeing_cfg = {}
        if wellbeing_cfg.get("enabled") is False:
            return

        fallback_x = attribute_panel.x()
        fallback_y = attribute_panel.y() + attribute_panel.height() + 8
        fallback_w = attribute_panel.width()
        fallback_h = max(430, min(450, window.content_layer.height() - fallback_y - 8))
        panel_x = window._safe_int(wellbeing_cfg.get("x", fallback_x), fallback_x)
        panel_y = window._safe_int(wellbeing_cfg.get("y", fallback_y), fallback_y)
        panel_w = window._safe_int(wellbeing_cfg.get("w", fallback_w), fallback_w)
        panel_h = window._safe_int(wellbeing_cfg.get("h", fallback_h), fallback_h)
        style_cfg = wellbeing_cfg.get("style", {})
        if not isinstance(style_cfg, dict):
            style_cfg = {}
        background = str(style_cfg.get("background", "rgba(12, 12, 12, 150)"))
        border_color = str(style_cfg.get("border_color", "rgba(242, 210, 139, 95)"))
        border_radius = window._safe_int(style_cfg.get("border_radius", 6), 6)

        panel = QFrame(window.content_layer)
        panel.setGeometry(panel_x, panel_y, panel_w, panel_h)
        panel.setStyleSheet(
            "QFrame {"
            f"background: {background};"
            f"border: 1px solid {border_color};"
            f"border-radius: {border_radius}px;"
            "}"
        )
        panel.show()

        title_cfg = wellbeing_cfg.get("title", {})
        if not isinstance(title_cfg, dict):
            title_cfg = {}
        window.create_panel_text(
            panel,
            title_cfg or {"x": 16, "y": 8, "w": panel_w - 32, "h": 24},
            str(title_cfg.get("text", "Wohlbefinden")),
            window.get_text_font_size(title_cfg, 18),
            window.get_text_color(title_cfg, default_color),
            bold=window.get_text_bold(title_cfg, True),
            align=window.get_text_align(title_cfg, "center"),
        )

        def elide_label(text, max_chars=36):
            value = str(text or "").strip()
            if len(value) <= max_chars:
                return value
            return value[: max(0, max_chars - 3)] + "..."

        entries = window.get_wellbeing_entries(wellbeing_cfg.get("data", {}))
        default_color_ranges = [
            {"start_row": 23, "end_row": 24, "color": "#7d1f20"},
            {"start_row": 25, "end_row": 28, "color": "#b74335"},
            {"start_row": 29, "end_row": 32, "color": "#d18a26"},
            {"start_row": 33, "end_row": 34, "color": "#8a877f"},
            {"start_row": 35, "end_row": 38, "color": "#8fbf5a"},
            {"start_row": 39, "end_row": 42, "color": "#4f9b45"},
            {"start_row": 43, "end_row": 44, "color": "#1f6f37"},
        ]
        color_ranges = wellbeing_cfg.get("color_ranges", default_color_ranges)
        if not isinstance(color_ranges, list) or not color_ranges:
            color_ranges = default_color_ranges

        def wellbeing_bar_color(row):
            for color_range in color_ranges:
                if not isinstance(color_range, dict):
                    continue
                start = window._safe_int(color_range.get("start_row", 0), 0)
                end = window._safe_int(color_range.get("end_row", start), start)
                if start <= row <= end:
                    return str(color_range.get("color", "#777777"))
            return "#777777"

        def entry_tooltip(entry, full_label, active):
            marker_cell = str(entry.get("marker_cell", ""))
            label_cell = str(entry.get("label_cell", ""))
            label_for_tooltip = full_label if full_label else "(leer)"
            active_text = "ja" if active else "nein"
            return (
                f"{marker_cell} / {label_cell}\n"
                f"{label_cell}: {label_for_tooltip}\n"
                f"Aktiv: {active_text}"
            )

        def render_vertical_mode():
            vertical_cfg = wellbeing_cfg.get("vertical", {})
            if not isinstance(vertical_cfg, dict):
                vertical_cfg = {}
            margin_x = window._safe_int(vertical_cfg.get("margin_x", 14), 14)
            row_y_start = window._safe_int(vertical_cfg.get("row_y_start", 38), 38)
            row_h = window._safe_int(vertical_cfg.get("row_h", 17), 17)
            row_gap = window._safe_int(vertical_cfg.get("row_gap", 1), 1)
            color_bar_w = window._safe_int(vertical_cfg.get("color_bar_w", 18), 18)
            grouped_color_bars = bool(vertical_cfg.get("grouped_color_bars", True))
            group_bar_w = window._safe_int(vertical_cfg.get("group_bar_w", color_bar_w), color_bar_w)
            group_bar_radius = window._safe_int(vertical_cfg.get("group_bar_radius", 3), 3)
            row_background_enabled = bool(vertical_cfg.get("row_background_enabled", True))
            x_field_w = window._safe_int(vertical_cfg.get("x_field_w", 28), 28)
            gap = window._safe_int(vertical_cfg.get("gap", 7), 7)
            font_size = window._safe_int(vertical_cfg.get("font_size", 11), 11)
            active_font_size = window._safe_int(vertical_cfg.get("active_font_size", font_size), font_size)
            max_label_chars = window._safe_int(vertical_cfg.get("max_label_chars", 38), 38)
            row_x = margin_x + color_bar_w + gap
            text_x = x_field_w + gap
            text_w = max(80, panel_w - row_x - text_x - margin_x)

            inactive_row_background = str(style_cfg.get("inactive_row_background", "rgba(255, 255, 255, 6)"))
            active_row_background = str(style_cfg.get("active_row_background", "rgba(242, 210, 139, 36)"))
            inactive_border = str(style_cfg.get("inactive_border", "rgba(232, 224, 200, 24)"))
            active_border = str(style_cfg.get("active_border", "rgba(242, 210, 139, 170)"))
            text_color = str(style_cfg.get("text_color", "rgba(232, 224, 200, 175)"))
            active_text_color = str(style_cfg.get("active_text_color", "#ffffff"))
            x_inactive_background = str(style_cfg.get("x_inactive_background", "rgba(0, 0, 0, 85)"))
            x_active_background = str(style_cfg.get("x_active_background", "rgba(242, 210, 139, 72)"))
            x_inactive_border = str(style_cfg.get("x_inactive_border", "rgba(232, 224, 200, 55)"))
            x_active_border = str(style_cfg.get("x_active_border", "rgba(242, 210, 139, 220)"))
            data_cfg = wellbeing_cfg.get("data", {})
            if not isinstance(data_cfg, dict):
                data_cfg = {}
            data_start_row = window._safe_int(data_cfg.get("start_row", 23), 23)
            data_end_row = window._safe_int(data_cfg.get("end_row", 44), 44)
            if data_end_row < data_start_row:
                data_start_row, data_end_row = data_end_row, data_start_row

            if grouped_color_bars:
                for color_range in color_ranges:
                    if not isinstance(color_range, dict):
                        continue
                    start_row = window._safe_int(color_range.get("start_row", data_start_row), data_start_row)
                    end_row = window._safe_int(color_range.get("end_row", start_row), start_row)
                    start_row = max(data_start_row, start_row)
                    end_row = min(data_end_row, end_row)
                    if end_row < start_row:
                        continue
                    start_index = start_row - data_start_row
                    end_index = end_row - data_start_row
                    group_y = row_y_start + start_index * (row_h + row_gap)
                    group_h = (end_index - start_index + 1) * row_h + (end_index - start_index) * row_gap
                    group_bar = QLabel(panel)
                    group_bar.setGeometry(margin_x, group_y, group_bar_w, max(1, group_h))
                    group_bar.setStyleSheet(
                        "QLabel {"
                        f"background: {str(color_range.get('color', '#777777'))};"
                        "border: none;"
                        f"border-radius: {group_bar_radius}px;"
                        "}"
                    )
                    group_bar.show()

            for index, entry in enumerate(entries):
                y = row_y_start + index * (row_h + row_gap)
                active = bool(entry.get("active"))
                full_label = str(entry.get("label", "") or "")
                tooltip = entry_tooltip(entry, full_label, active)

                row_frame = QFrame(panel)
                row_frame.setGeometry(row_x, y, panel_w - row_x - margin_x, row_h)
                row_frame.setStyleSheet(
                    "QFrame {"
                    f"background: {active_row_background if active else inactive_row_background if row_background_enabled else 'transparent'};"
                    f"border: 1px solid {active_border if active else inactive_border};"
                    "border-radius: 3px;"
                    "}"
                )
                row_frame.show()

                if not grouped_color_bars:
                    color_bar = QLabel(panel)
                    color_bar.setGeometry(margin_x, y + 2, color_bar_w, max(1, row_h - 4))
                    color_bar.setStyleSheet(
                        "QLabel {"
                        f"background: {wellbeing_bar_color(int(entry.get('row', 0)))};"
                        "border: none;"
                        f"border-radius: {group_bar_radius}px;"
                        "}"
                    )
                    color_bar.setToolTip(tooltip)
                    color_bar.show()

                x_field = QLabel(row_frame)
                x_field.setGeometry(0, 1, x_field_w, max(1, row_h - 2))
                x_field.setText("X" if active else "")
                x_field.setAlignment(Qt.AlignCenter)
                x_field.setStyleSheet(
                    "QLabel {"
                    f"background: {x_active_background if active else x_inactive_background};"
                    f"border: 1px solid {x_active_border if active else x_inactive_border};"
                    "border-radius: 2px;"
                    f"color: {active_text_color if active else text_color};"
                    "font-size: 10px;"
                    "font-weight: 700;"
                    "}"
                )
                x_field.setToolTip(tooltip)
                if window._character_edit_allowed("wellbeing"):
                    x_field.setProperty("character_wellbeing_toggle", True)
                    x_field.setProperty("character_wellbeing_row", int(entry.get("row", 0)))
                    x_field.setProperty("character_wellbeing_marker_cell", str(entry.get("marker_cell", "")))
                    x_field.setProperty("character_wellbeing_sheet_name", str(data_cfg.get("sheet", "Charakterbogen")))
                    x_field.setProperty("character_wellbeing_active", bool(active))
                    x_field.installEventFilter(window)
                x_field.show()

                text_label = QLabel(row_frame)
                text_label.setGeometry(text_x, 0, text_w, row_h)
                text_label.setText(elide_label(full_label, max_label_chars))
                text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                text_label.setStyleSheet(
                    "QLabel {"
                    "background: transparent;"
                    "border: none;"
                    f"color: {active_text_color if active else text_color};"
                    f"font-size: {active_font_size if active else font_size}px;"
                    f"font-weight: {'700' if active else '500'};"
                    "}"
                )
                text_label.setToolTip(tooltip)
                text_label.show()

        render_vertical_mode()

        panel.raise_()

    render_wellbeing_block()
    render_character_initiative_panel(window, character_screen, character_panel, attribute_panel, default_color)
    render_character_paradigm_panel(window, character_screen, attribute_panel, default_color)

    perks_layout = text_layout.get("perk_panel", text_layout.get("perks", {}))
    disadv_layout = text_layout.get("disadvantages", perks_layout.get("disadvantage_table", {}))
    perks_map = data_map.get("perks", {})
    disadv_map = data_map.get("disadvantages", {})
    window.current_perks = []
    window.current_disadvantages = []

    def elide_fixed_text(text, max_chars):
        value = str(text)
        if len(value) <= max_chars:
            return value
        return value[: max(0, max_chars - 3)] + "..."

    def render_side_table(parent, table_cfg, map_cfg, collection):
        header_y = window._safe_int(table_cfg.get("header_y", 0), 0)
        start_y = window._safe_int(table_cfg.get("start_y", header_y + 24), header_y + 24)
        row_h = window._safe_int(table_cfg.get("row_h", 24), 24)
        max_rows = window._safe_int(table_cfg.get("max_rows", 8), 8)
        header_font_size = window._safe_int(table_cfg.get("header_font_size", 15), 15)
        row_font_size = window._safe_int(table_cfg.get("row_font_size", table_cfg.get("font_size", 14)), 14)
        header_color = str(table_cfg.get("header_color", table_cfg.get("color", default_color)))
        name_color = str(table_cfg.get("name_color", table_cfg.get("row_color", "#f2d28b")))
        bp_color = str(table_cfg.get("bp_color", table_cfg.get("row_color", "#d6b35a")))
        effect_color = str(table_cfg.get("effect_color", table_cfg.get("row_color", "#ffffff")))
        name_x = window._safe_int(table_cfg.get("name_x", 0), 0)
        name_w = window._safe_int(table_cfg.get("name_w", 130), 130)
        bp_x = window._safe_int(table_cfg.get("bp_x", name_x + name_w + 8), name_x + name_w + 8)
        bp_w = window._safe_int(table_cfg.get("bp_w", 40), 40)
        effect_x = window._safe_int(table_cfg.get("effect_x", bp_x + bp_w + 8), bp_x + bp_w + 8)
        effect_w = window._safe_int(table_cfg.get("effect_w", 180), 180)

        window.create_panel_text(
            parent,
            {"x": name_x, "y": header_y, "w": name_w, "h": row_h},
            str(table_cfg.get("name_header", "Name")),
            header_font_size,
            header_color,
            bold=True,
        )
        window.create_panel_text(
            parent,
            {"x": bp_x, "y": header_y, "w": bp_w, "h": row_h},
            str(table_cfg.get("bp_header", "BP")),
            header_font_size,
            header_color,
            bold=True,
            align="center",
        )
        window.create_panel_text(
            parent,
            {"x": effect_x, "y": header_y, "w": effect_w, "h": row_h},
            str(table_cfg.get("effect_header", "Effekt")),
            header_font_size,
            header_color,
            bold=True,
        )

        start_row = window._safe_int(map_cfg.get("start_row", 0), 0)
        end_row = window._safe_int(map_cfg.get("end_row", -1), -1)
        if start_row <= 0 or end_row < start_row:
            return

        sheet_name = str(map_cfg.get("sheet", default_sheet))
        name_col = str(map_cfg.get("name_col", "A"))
        bp_col = str(map_cfg.get("bp_col", "B"))
        effect_col = str(map_cfg.get("effect_col", "C"))
        name_max_chars = window._safe_int(table_cfg.get("name_max_chars", 22), 22)
        effect_max_chars = window._safe_int(table_cfg.get("effect_max_chars", 34), 34)

        editable_table = (
            (map_cfg is perks_map and window._character_edit_allowed("perks"))
            or (map_cfg is disadv_map and window._character_edit_allowed("disadvantages"))
        )
        table_type = "perk" if map_cfg is perks_map else "disadvantage"

        rendered = 0
        max_rows = max(max_rows, end_row - start_row + 1)
        for row in range(start_row, end_row + 1):
            name = window.get_cache_display_value(sheet_name, f"{name_col}{row}", "")
            raw_bp = window.get_cache_display_value(sheet_name, f"{bp_col}{row}", "")
            effect = window.get_cache_display_value(sheet_name, f"{effect_col}{row}", "")

            bp = window.format_character_display_value(raw_bp, "int") if raw_bp else ""
            if name and name != "-":
                collection.append(name)
            y = start_y + rendered * row_h
            rendered += 1

            name_label = window.create_panel_text(
                parent,
                {"x": name_x, "y": y, "w": name_w, "h": row_h},
                elide_fixed_text(name, name_max_chars) if name else "",
                row_font_size,
                name_color,
            )
            bp_label = window.create_panel_text(
                parent,
                {"x": bp_x, "y": y, "w": bp_w, "h": row_h},
                bp,
                row_font_size,
                bp_color,
                align="center",
            )
            effect_label = window.create_panel_text(
                parent,
                {"x": effect_x, "y": y, "w": effect_w, "h": row_h},
                elide_fixed_text(effect, effect_max_chars) if effect else "",
                row_font_size,
                effect_color,
            )
            if editable_table:
                for widget, field, cell_ref, old_value in (
                    (name_label, "name", f"{name_col}{row}", name),
                    (bp_label, "bp", f"{bp_col}{row}", raw_bp),
                    (effect_label, "effect", f"{effect_col}{row}", effect),
                ):
                    widget.setProperty("character_perk_table_type", table_type)
                    widget.setProperty("character_perk_row", row)
                    widget.setProperty("character_perk_field", field)
                    widget.setProperty("character_perk_cell_ref", cell_ref)
                    widget.setProperty("character_perk_sheet_name", sheet_name)
                    widget.setProperty("character_perk_value", "" if old_value in (None, "-") else str(old_value))
                    widget.installEventFilter(window)

    if isinstance(perks_layout, dict) and "perk_table" in perks_layout and "disadvantage_table" in perks_layout:
        left_title = perks_layout.get("left_title", {})
        right_title = perks_layout.get("right_title", {})
        window.create_panel_text(
            perk_panel,
            left_title.get("rect", left_title if isinstance(left_title, dict) else {}),
            str(left_title.get("text", "Perks")) if isinstance(left_title, dict) else "Perks",
            window.get_text_font_size(left_title, 22),
            window.get_text_color(left_title, default_color),
            bold=window.get_text_bold(left_title, True),
            align=window.get_text_align(left_title, "center"),
        )
        window.create_panel_text(
            perk_panel,
            right_title.get("rect", right_title if isinstance(right_title, dict) else {}),
            str(right_title.get("text", "Nachteile")) if isinstance(right_title, dict) else "Nachteile",
            window.get_text_font_size(right_title, 22),
            window.get_text_color(right_title, default_color),
            bold=window.get_text_bold(right_title, True),
            align=window.get_text_align(right_title, "center"),
        )
        render_side_table(
            perk_panel,
            perks_layout.get("perk_table", {}),
            perks_map if isinstance(perks_map, dict) else {},
            window.current_perks,
        )
        render_side_table(
            perk_panel,
            perks_layout.get("disadvantage_table", {}),
            disadv_map if isinstance(disadv_map, dict) else {},
            window.current_disadvantages,
        )
        window._character_debug(f"[PERKS] {window.current_perks}")
        window._character_debug(f"[DISADVANTAGES] {window.current_disadvantages}")
        window._character_rendering = False
        return

    def render_table_block(parent, table_cfg, map_cfg, title_cfg, section_title, start_y_default):
        title_rect = title_cfg.get("rect", {"x": 24, "y": start_y_default, "w": 280, "h": 30})
        window.create_panel_text(
            parent,
            title_rect,
            str(title_cfg.get("text", section_title)),
            window.get_text_font_size(title_cfg, 22),
            window.get_text_color(title_cfg, default_color),
            bold=window.get_text_bold(title_cfg, True),
        )

        header_cfg = table_cfg.get("header", {})
        header_y = window._safe_int(header_cfg.get("y", window._safe_int(title_rect.get("y", start_y_default), start_y_default) + 34), start_y_default + 34)
        name_x = window._safe_int(table_cfg.get("name_x", 24), 24)
        name_w = window._safe_int(table_cfg.get("name_w", 200), 200)
        bp_x = window._safe_int(table_cfg.get("bp_x", 250), 250)
        bp_w = window._safe_int(table_cfg.get("bp_w", 60), 60)
        effect_x = window._safe_int(table_cfg.get("effect_x", 330), 330)
        effect_w = window._safe_int(table_cfg.get("effect_w", 280), 280)
        row_h = window._safe_int(table_cfg.get("row_h", 28), 28)
        max_rows = window._safe_int(table_cfg.get("max_rows", 8), 8)
        font_size = window._safe_int(table_cfg.get("font_size", 16), 16)
        header_font_size = window._safe_int(
            table_cfg.get("header_font_size", header_cfg.get("font_size", font_size)),
            font_size,
        )
        header_color = str(
            table_cfg.get("header_color", header_cfg.get("color", default_color))
        )
        row_color = str(table_cfg.get("row_color", table_cfg.get("color", "#ffffff")))

        window.create_panel_text(
            parent,
            {"x": name_x, "y": header_y, "w": name_w, "h": row_h},
            str(header_cfg.get("name", "Name")),
            header_font_size,
            header_color,
            bold=True,
        )
        window.create_panel_text(
            parent,
            {"x": bp_x, "y": header_y, "w": bp_w, "h": row_h},
            str(header_cfg.get("bp", "BP")),
            header_font_size,
            header_color,
            bold=True,
        )
        window.create_panel_text(
            parent,
            {"x": effect_x, "y": header_y, "w": effect_w, "h": row_h},
            str(header_cfg.get("effect", "Effekt")),
            header_font_size,
            header_color,
            bold=True,
        )

        start_row = window._safe_int(map_cfg.get("start_row", 0), 0)
        end_row = window._safe_int(map_cfg.get("end_row", -1), -1)
        if start_row <= 0 or end_row < start_row:
            return header_y + row_h
        sheet_name = str(map_cfg.get("sheet", default_sheet))
        name_col = str(map_cfg.get("name_col", "A"))
        bp_col = str(map_cfg.get("bp_col", "B"))
        effect_col = str(map_cfg.get("effect_col", "C"))
        row_start_y = window._safe_int(table_cfg.get("start_y", header_y + row_h + 2), header_y + row_h + 2)

        editable_table = (
            (map_cfg is perks_map and window._character_edit_allowed("perks"))
            or (map_cfg is disadv_map and window._character_edit_allowed("disadvantages"))
        )
        table_type = "perk" if map_cfg is perks_map else "disadvantage"

        rendered = 0
        max_rows = max(max_rows, end_row - start_row + 1)
        for row in range(start_row, end_row + 1):
            n = window.get_cache_display_value(sheet_name, f"{name_col}{row}", "")
            raw_b = window.get_cache_display_value(sheet_name, f"{bp_col}{row}", "")
            b = window.format_character_display_value(raw_b, "int") if raw_b else ""
            e = window.get_cache_display_value(sheet_name, f"{effect_col}{row}", "")
            y = row_start_y + rendered * row_h
            rendered += 1
            name_label = window.create_panel_text(
                parent,
                {"x": name_x, "y": y, "w": name_w, "h": row_h},
                n or "",
                font_size,
                row_color,
                align="left",
            )
            bp_label = window.create_panel_text(
                parent,
                {"x": bp_x, "y": y, "w": bp_w, "h": row_h},
                b or "",
                font_size,
                row_color,
                align="left",
            )
            effect_text = (e or "")
            if len(effect_text) > 140:
                effect_text = effect_text[:137] + "..."
            effect_label = window.create_panel_text(
                parent,
                {"x": effect_x, "y": y, "w": effect_w, "h": row_h},
                effect_text,
                font_size,
                row_color,
                align="left",
            )
            if editable_table:
                for widget, field, cell_ref, old_value in (
                    (name_label, "name", f"{name_col}{row}", n),
                    (bp_label, "bp", f"{bp_col}{row}", raw_b),
                    (effect_label, "effect", f"{effect_col}{row}", e),
                ):
                    widget.setProperty("character_perk_table_type", table_type)
                    widget.setProperty("character_perk_row", row)
                    widget.setProperty("character_perk_field", field)
                    widget.setProperty("character_perk_cell_ref", cell_ref)
                    widget.setProperty("character_perk_sheet_name", sheet_name)
                    widget.setProperty("character_perk_value", "" if old_value in (None, "-") else str(old_value))
                    widget.installEventFilter(window)
        return row_start_y + rendered * row_h

    perks_title_cfg = perks_layout.get("title", {"text": "Perks", "rect": {"x": 24, "y": 22, "w": 200, "h": 30}})
    perks_table_cfg = perks_layout.get("table", perks_layout)
    end_y = render_table_block(perk_panel, perks_table_cfg, perks_map, perks_title_cfg, "Perks", 22)

    dis_title_cfg = perks_layout.get(
        "disadvantage_title",
        {"text": "Nachteile", "rect": {"x": 24, "y": end_y + 20, "w": 220, "h": 30}},
    )
    dis_table_cfg = perks_layout.get("disadvantage_table", disadv_layout if isinstance(disadv_layout, dict) else {})
    if isinstance(dis_title_cfg, dict) and isinstance(dis_title_cfg.get("rect"), dict):
        dis_title_cfg["rect"]["y"] = window._safe_int(dis_title_cfg["rect"].get("y", end_y + 20), end_y + 20)
    render_table_block(perk_panel, dis_table_cfg, disadv_map, dis_title_cfg, "Nachteile", end_y + 20)
    window._character_rendering = False
