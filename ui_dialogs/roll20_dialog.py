import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def open_roll20_dialog(parent, model, callbacks=None, style_context=None):
    callbacks = callbacks if isinstance(callbacks, dict) else {}
    style_context = style_context if isinstance(style_context, dict) else {}
    roll_layout = style_context.get("roll_layout", {})
    if not isinstance(roll_layout, dict):
        roll_layout = {}

    safe_int = callbacks.get("safe_int")
    if not callable(safe_int):
        safe_int = _safe_int
    build_command = callbacks.get("build_command")
    open_roll20_browser = callbacks.get("open_roll20_browser")
    log_debug = callbacks.get("log_debug")
    compact_text = callbacks.get("compact_text")
    specialization_preview = callbacks.get("specialization_preview")
    resolve_roll_asset_path = callbacks.get("resolve_roll_asset_path")

    dialog_cfg = _dict(roll_layout.get("dialog"))
    sections_cfg = _dict(roll_layout.get("sections"))
    spec_cfg = _dict(roll_layout.get("specialization_box"))
    counter_cfg = _dict(roll_layout.get("counter"))
    keep_cfg = _dict(roll_layout.get("keep_options"))
    preview_cfg = _dict(roll_layout.get("roll_preview"))
    buttons_cfg = _dict(roll_layout.get("buttons"))
    boxes_cfg = _dict(roll_layout.get("boxes"))
    checkbox_cfg = _dict(roll_layout.get("checkbox"))
    spec_options_cfg = _dict(roll_layout.get("specialization_options"))
    paradigm_cfg = _dict(roll_layout.get("paradigm"))
    perk_suggestions_cfg = _dict(roll_layout.get("perk_suggestions"))
    labels_cfg = _dict(roll_layout.get("labels"))
    debug_cfg = _dict(roll_layout.get("debug"))
    layout_cfg = _dict(roll_layout.get("layout"))
    title_cfg = _dict(roll_layout.get("title"))
    close_button_cfg = _dict(roll_layout.get("close_button"))

    dialog_title = str(dialog_cfg.get("title", "Roll20 Wurf-Assistent"))
    dialog_w = safe_int(dialog_cfg.get("w", 700), 700)
    dialog_h = safe_int(dialog_cfg.get("h", 620), 620)
    use_main_canvas_ratio = bool(dialog_cfg.get("use_main_canvas_ratio", False))
    main_canvas_reference_cfg = _dict(dialog_cfg.get("main_canvas_reference"))
    if use_main_canvas_ratio:
        reference_w = safe_int(main_canvas_reference_cfg.get("w", 0), 0)
        reference_h = safe_int(main_canvas_reference_cfg.get("h", 0), 0)
        if reference_w > 0 and reference_h > 0:
            dialog_h = round(dialog_w * reference_h / reference_w)
    text_color = str(dialog_cfg.get("text_color", "#f2f2f2"))
    muted_text_color = str(dialog_cfg.get("muted_text_color", "#c8c0aa"))
    accent_color = str(dialog_cfg.get("accent_color", "#f2d28b"))
    base_font_size = safe_int(dialog_cfg.get("font_size", 13), 13)
    title_font_size = safe_int(dialog_cfg.get("title_font_size", 18), 18)
    dialog_bg = str(dialog_cfg.get("background", "#202426"))
    dialog_frame_cfg = _dict(dialog_cfg.get("frame"))
    main_frame_cfg = _dict(dialog_cfg.get("main_frame"))
    main_frame_enabled = bool(main_frame_cfg.get("enabled", False))
    fixed_size = bool(dialog_cfg.get("fixed_size", False))
    frameless_window = bool(dialog_cfg.get("frameless_window", False))
    use_main_theme_background = bool(dialog_cfg.get("use_main_theme_background", False))
    layout_padding = safe_int(layout_cfg.get("padding", 32), 32)
    spacing = safe_int(sections_cfg.get("spacing", 12), 12)
    spec_height = safe_int(spec_cfg.get("height", 64), 64)
    spec_font_size = safe_int(spec_cfg.get("font_size", 13), 13)
    preview_label_text = str(preview_cfg.get("label", "Roll20-Befehl:"))
    preview_font_size = safe_int(preview_cfg.get("font_size", 22), 22)
    preview_height = safe_int(preview_cfg.get("height", 58), 58)
    section_title_color = str(labels_cfg.get("section_title_color", accent_color))
    section_title_font_size = safe_int(labels_cfg.get("section_title_font_size", base_font_size), base_font_size)
    normal_text_color = str(labels_cfg.get("normal_text_color", text_color))
    normal_text_font_size = safe_int(labels_cfg.get("normal_text_font_size", base_font_size), base_font_size)
    muted_text_cfg_color = str(labels_cfg.get("muted_text_color", muted_text_color))
    muted_text_font_size = safe_int(
        labels_cfg.get("muted_text_font_size", max(10, base_font_size - 1)),
        max(10, base_font_size - 1),
    )
    hint_text_color = str(labels_cfg.get("hint_text_color", muted_text_cfg_color))
    hint_text_font_size = safe_int(labels_cfg.get("hint_text_font_size", muted_text_font_size), muted_text_font_size)
    checkbox_style = str(style_context.get("checkbox_style", ""))
    checkbox_style = _dialog_checkbox_style(
        checkbox_style,
        checkbox_cfg,
        resolve_roll_asset_path,
        normal_text_color,
        normal_text_font_size,
        safe_int,
    )
    info_background = str(boxes_cfg.get("info_background", "rgba(0, 0, 0, 70)"))
    info_border_color = str(boxes_cfg.get("info_border_color", "rgba(242, 210, 139, 70)"))
    info_frame_cfg = _dict(boxes_cfg.get("info_frame"))
    specialization_frame_cfg = _dict(boxes_cfg.get("specialization_frame"))
    preview_frame_cfg = _dict(boxes_cfg.get("preview_frame"))
    debug_preview_enabled = bool(debug_cfg.get("preview", False))
    debug_toggles_enabled = bool(debug_cfg.get("toggles", True))
    debug_info_only_enabled = bool(debug_cfg.get("info_only", False))
    debug_paradigm_enabled = bool(debug_cfg.get("paradigm", False))

    display_name = str(model.get("display_name", ""))
    specialization_text = str(model.get("specialization_text", "") or "")
    attrs_text = str(model.get("attrs_text", "-"))
    skill_value = safe_int(model.get("skill_value", 0), 0)
    skill_value_allowed = bool(model.get("skill_value_allowed", True))
    is_initiative_context = bool(model.get("is_initiative_context", False))
    is_character_initiative = bool(model.get("is_character_initiative", False))
    specialization_items = model.get("specialization_items", [])
    if not isinstance(specialization_items, list):
        specialization_items = []
    perk_suggestions = model.get("perk_suggestions", [])
    if not isinstance(perk_suggestions, list):
        perk_suggestions = []
    wellbeing_suggestions = model.get("wellbeing_suggestions", [])
    if not isinstance(wellbeing_suggestions, list):
        wellbeing_suggestions = []
    fixed_bonus_lines = model.get("fixed_bonus_lines", [])
    if not isinstance(fixed_bonus_lines, list):
        fixed_bonus_lines = []
    fixed_extra_bonuses = model.get("fixed_extra_bonuses", [])
    if not isinstance(fixed_extra_bonuses, list):
        fixed_extra_bonuses = []

    dynamic_extra = 0
    dynamic_extra += max(0, len(specialization_items) - 6) * 14
    dynamic_extra += max(0, len(perk_suggestions) - 2) * 18
    dynamic_extra += max(0, len(wellbeing_suggestions) - 2) * 18

    custom_dialog_title = str(model.get("dialog_title", "") or "")
    dialog = QDialog(parent)
    dialog.setWindowTitle(custom_dialog_title or dialog_title)
    dialog.setModal(True)
    if frameless_window:
        dialog.setWindowFlag(Qt.FramelessWindowHint, True)
    if fixed_size:
        dialog.setFixedSize(dialog_w, dialog_h)
    else:
        dialog.resize(dialog_w, min(980, dialog_h + dynamic_extra))
    dialog.setStyleSheet(
        _dialog_style(
            dialog_bg,
            text_color,
            base_font_size,
            str(dialog_cfg.get("border_color", accent_color)),
            {} if main_frame_enabled else dialog_frame_cfg,
            resolve_roll_asset_path,
        )
    )

    if main_frame_enabled:
        frame_rect = _rect_from_cfg(main_frame_cfg, 0, 0, dialog_w, dialog_h, safe_int)
        frame_label = QLabel(dialog)
        frame_label.setGeometry(*frame_rect)
        frame_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        frame_pixmap = _asset_pixmap(str(main_frame_cfg.get("asset", "") or ""), resolve_roll_asset_path)
        if frame_pixmap is not None:
            frame_label.setPixmap(frame_pixmap.scaled(frame_rect[2], frame_rect[3], Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        frame_label.lower()

    root = QWidget(dialog)
    root.setObjectName("roll20Root")
    root.setGeometry(0, 0, dialog_w, dialog_h)
    root_background = "transparent" if use_main_theme_background or main_frame_enabled else dialog_bg
    root.setStyleSheet(f"QWidget#roll20Root {{ background: {root_background}; }}")

    title_rect = _rect_from_cfg(title_cfg, 260, 18, 500, 42, safe_int)
    left_rect = _rect_from_cfg(_dict(layout_cfg.get("left")), 54, 132, 500, 260, safe_int)
    right_rect = _rect_from_cfg(_dict(layout_cfg.get("right")), 590, 132, 360, 260, safe_int)
    preview_rect = _rect_from_cfg(_dict(layout_cfg.get("preview")), 54, 420, 896, 76, safe_int)
    buttons_area_cfg = _dict(buttons_cfg.get("area"))
    buttons_rect = _rect_from_cfg(buttons_area_cfg, 230, 68, 560, 46, safe_int)
    buttons_gap = safe_int(buttons_area_cfg.get("gap", 16), 16)
    title_panel, title_layout = _make_panel_layout(root, title_rect, 0, spacing=0)
    left_scroll, left_content, left_layout = _make_scroll_zone(root, left_rect, 4, spacing)
    right_scroll, right_content, right_layout = _make_scroll_zone(root, right_rect, 4, spacing)
    preview_panel, preview_layout = _make_panel_layout(root, preview_rect, 0, spacing=4)
    buttons_panel, buttons_layout = _make_panel_layout(root, buttons_rect, 0, spacing=0)

    custom_close_button = None
    if bool(close_button_cfg.get("enabled", False)):
        custom_close_button = QPushButton(root)
        custom_close_button.setGeometry(*_anchored_rect_from_cfg(close_button_cfg, dialog_w, 20, 32, 32, safe_int))
        close_icon_path = resolve_roll_asset_path(str(close_button_cfg.get("asset", "") or "")) if callable(resolve_roll_asset_path) else None
        if close_icon_path is not None:
            custom_close_button.setIcon(QIcon(str(close_icon_path)))
            custom_close_button.setIconSize(custom_close_button.size())
        custom_close_button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
        custom_close_button.setCursor(Qt.PointingHandCursor)

    header_text = f"Fertigkeit: {display_name}"
    if is_character_initiative:
        header_text = "Initiative"
    elif is_initiative_context:
        header_text = f"Initiative - {display_name}"
    header = QLabel(header_text)
    header_alignment = _alignment_from_cfg(str(title_cfg.get("align", "center")))
    header_font_size = safe_int(title_cfg.get("font_size", title_font_size), title_font_size)
    header_color = str(title_cfg.get("color", accent_color))
    header.setStyleSheet(
        f"font-size: {header_font_size}px; font-weight: 700; color: {header_color}; padding: 0px;"
    )
    header.setAlignment(header_alignment | Qt.AlignVCenter)
    header.setText(_elided_text(header, header_text, title_rect[2]))
    title_layout.addWidget(header)

    if is_character_initiative:
        value_label = QLabel(
            f'Wert: {model.get("raw_value", skill_value)}   Bonus: {model.get("bonus_value", 0)}   Rollwert: {skill_value}'
        )
    else:
        value_label = QLabel(f"Wert: {skill_value}")
    value_label.setStyleSheet(
        _framed_box_style(
            info_background,
            info_border_color,
            normal_text_color,
            normal_text_font_size,
            info_frame_cfg,
            resolve_roll_asset_path,
            padding=safe_int(info_frame_cfg.get("padding", 6), 6),
        )
    )
    left_layout.addWidget(value_label)

    if not is_character_initiative:
        attrs_label = QLabel(f"Attribute: {attrs_text}")
        attrs_label.setStyleSheet(
            _framed_box_style(
                info_background,
                info_border_color,
                normal_text_color,
                normal_text_font_size,
                info_frame_cfg,
                resolve_roll_asset_path,
                padding=safe_int(info_frame_cfg.get("padding", 6), 6),
            )
        )
        left_layout.addWidget(attrs_label)

    show_specialization = not is_initiative_context
    spec_options_max_rows_per_column = safe_int(spec_options_cfg.get("max_rows_per_column", 6), 6)
    if spec_options_max_rows_per_column <= 0:
        spec_options_max_rows_per_column = 6
    spec_options_column_spacing = safe_int(spec_options_cfg.get("column_spacing", 24), 24)
    spec_options_row_spacing = safe_int(spec_options_cfg.get("row_spacing", 8), 8)
    spec_preview_max_chars = safe_int(spec_options_cfg.get("preview_max_chars", 48), 48)
    if callable(specialization_preview):
        specialization_preview_text = specialization_preview(specialization_text, spec_preview_max_chars)
    else:
        specialization_preview_text = specialization_text

    if show_specialization:
        spec_title = QLabel("Spezialisierung:")
        spec_title.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
        left_layout.addWidget(spec_title)

        spec_value = QLabel(specialization_preview_text)
        spec_value.setWordWrap(True)
        spec_value.setStyleSheet(
            _framed_box_style(
                str(spec_cfg.get("background", "#141618")),
                str(spec_cfg.get("border_color", "#3a3a3a")),
                str(spec_cfg.get("text_color", "#ffffff")),
                spec_font_size,
                specialization_frame_cfg,
                resolve_roll_asset_path,
                padding=safe_int(specialization_frame_cfg.get("padding", 8), 8),
            )
        )
        spec_value.setMinimumHeight(spec_height)
        left_layout.addWidget(spec_value)

        spec_options_title_label = QLabel(str(spec_options_cfg.get("title", "Spezialisierungen:")))
        spec_options_title_label.setStyleSheet(
            f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;"
        )
        left_layout.addWidget(spec_options_title_label)

    specialization_checkboxes = []
    if show_specialization:
        if specialization_items:
            checkboxes_grid_widget = QWidget(left_content)
            checkboxes_grid_layout = QGridLayout(checkboxes_grid_widget)
            checkboxes_grid_layout.setContentsMargins(0, 0, 0, 0)
            checkboxes_grid_layout.setHorizontalSpacing(spec_options_column_spacing)
            checkboxes_grid_layout.setVerticalSpacing(spec_options_row_spacing)
            for index, item in enumerate(specialization_items):
                checkbox = QCheckBox(item, left_content)
                checkbox.setChecked(False)
                checkbox.setStyleSheet(checkbox_style)
                row = index % spec_options_max_rows_per_column
                col = index // spec_options_max_rows_per_column
                checkboxes_grid_layout.addWidget(checkbox, row, col)
                specialization_checkboxes.append(checkbox)
            checkboxes_grid_layout.setColumnStretch(99, 1)
            left_layout.addWidget(checkboxes_grid_widget)
            spec_hint_label = QLabel(str(spec_options_cfg.get("hint", "Spezialisierungen: +1 Vorteil je Auswahl")))
            spec_hint_label.setStyleSheet(f"color: {hint_text_color}; font-size: {hint_text_font_size}px;")
            left_layout.addWidget(spec_hint_label)
        else:
            spec_empty_label = QLabel(str(spec_options_cfg.get("empty_text", "Keine Spezialisierung vorhanden")))
            spec_empty_label.setStyleSheet(f"color: {hint_text_color}; font-size: {hint_text_font_size}px;")
            left_layout.addWidget(spec_empty_label)

    if fixed_bonus_lines:
        fixed_title = QLabel("Feste Boni:")
        fixed_title.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
        right_layout.addWidget(fixed_title)
        for line in fixed_bonus_lines:
            row_label = QLabel(str(line))
            row_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
            right_layout.addWidget(row_label)

    perk_suggestion_checkboxes = []
    if perk_suggestions:
        perk_title_label = QLabel(str(perk_suggestions_cfg.get("title", "Perk-/Nachteil-Vorschläge:")))
        perk_title_label.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
        right_layout.addWidget(perk_title_label)
        for suggestion in perk_suggestions:
            label_text = str(suggestion.get("label", "Regelvorschlag"))
            source_type = "Perk" if str(suggestion.get("source_type", "")) == "perk" else "Nachteil"
            source_name = str(suggestion.get("source_name", "") or "")
            source_effect = str(suggestion.get("source_effect", "") or "")
            source_text = f"{source_type} {source_name}".strip()
            compact_effect = compact_text(source_effect, 60) if callable(compact_text) else source_effect
            compact_source_line = source_text if not compact_effect else f"{source_text} · {compact_effect}"
            compact_source_line = compact_text(compact_source_line, 70) if callable(compact_text) else compact_source_line
            checkbox = QCheckBox(label_text, right_content)
            checkbox.setChecked(False)
            checkbox.setStyleSheet(checkbox_style)
            checkbox.setProperty("rule_id", str(suggestion.get("rule_id", "")))
            checkbox.setProperty("suggested_effect", suggestion.get("suggested_effect", {}))
            checkbox.setToolTip(source_text if not source_effect else f"{source_text}\nEffekt: {source_effect}")
            right_layout.addWidget(checkbox)
            source_label = QLabel(compact_source_line)
            source_label.setStyleSheet(f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;")
            source_label.setToolTip(source_text if not source_effect else f"{source_text}\nEffekt: {source_effect}")
            right_layout.addWidget(source_label)
            perk_suggestion_checkboxes.append(checkbox)

        perk_hint_label = QLabel(str(perk_suggestions_cfg.get("hint", "Angehakte Vorschläge wirken nur manuell auf diesen Wurf.")))
        perk_hint_label.setStyleSheet(f"color: {hint_text_color}; font-size: {hint_text_font_size}px;")
        right_layout.addWidget(perk_hint_label)

    wellbeing_suggestion_checkboxes = []
    if wellbeing_suggestions:
        wellbeing_title_label = QLabel("Wohlbefinden-Vorschläge:")
        wellbeing_title_label.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
        right_layout.addWidget(wellbeing_title_label)
        for suggestion in wellbeing_suggestions:
            label_text = str(suggestion.get("label", "Wohlbefinden-Vorschlag"))
            source_label = str(suggestion.get("source_label", "") or "")
            source_text = f"Quelle: {source_label}" if source_label else "Quelle: Wohlbefinden"
            checkbox = QCheckBox(label_text, right_content)
            suggested_effect = suggestion.get("suggested_effect", {})
            checkbox.setChecked(_effect_grants_dice(suggested_effect))
            checkbox.setStyleSheet(checkbox_style)
            checkbox.setProperty("wellbeing_label", source_label)
            checkbox.setProperty("suggested_effect", suggested_effect)
            checkbox.setToolTip(source_text)
            right_layout.addWidget(checkbox)
            source_row = QLabel(source_text)
            source_row.setStyleSheet(f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;")
            source_row.setToolTip(source_text)
            right_layout.addWidget(source_row)
            wellbeing_suggestion_checkboxes.append(checkbox)

    if not is_initiative_context:
        skill_usage_text = (
            f"Skillwert wird verwendet: Ja (+{skill_value})"
            if skill_value_allowed
            else "Skillwert wird verwendet: Nein (keine Attribute/Spezialisierung)"
        )
        skill_usage_label = QLabel(skill_usage_text)
        skill_usage_label.setStyleSheet(f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;")
        left_layout.addWidget(skill_usage_label)

    controls = QVBoxLayout()
    advantages_spin = QSpinBox(dialog)
    advantages_spin.setRange(0, 99)
    advantages_spin.setValue(0)
    advantages_spin.setButtonSymbols(QSpinBox.NoButtons)
    disadvantages_spin = QSpinBox(dialog)
    disadvantages_spin.setRange(0, 99)
    disadvantages_spin.setValue(0)
    disadvantages_spin.setButtonSymbols(QSpinBox.NoButtons)
    manual_bonus_spin = QSpinBox(dialog)
    manual_bonus_spin.setRange(-999, 999)
    manual_bonus_spin.setValue(0)
    manual_bonus_spin.setButtonSymbols(QSpinBox.NoButtons)

    counter_value_w = safe_int(counter_cfg.get("value_w", 42), 42)
    counter_value_h = safe_int(counter_cfg.get("value_h", 34), 34)
    manual_value_w = safe_int(counter_cfg.get("manual_value_w", 64), 64)
    advantages_spin.setFixedSize(counter_value_w, counter_value_h)
    disadvantages_spin.setFixedSize(counter_value_w, counter_value_h)
    manual_bonus_spin.setFixedSize(manual_value_w, counter_value_h)
    for spinbox in (advantages_spin, disadvantages_spin, manual_bonus_spin):
        spinbox.lineEdit().setAlignment(Qt.AlignCenter)

    adv_minus = QPushButton("-", dialog)
    adv_plus = QPushButton("+", dialog)
    dis_minus = QPushButton("-", dialog)
    dis_plus = QPushButton("+", dialog)
    manual_minus = QPushButton("-", dialog)
    manual_plus = QPushButton("+", dialog)
    for button in (adv_minus, adv_plus, dis_minus, dis_plus, manual_minus, manual_plus):
        button.setFixedSize(safe_int(counter_cfg.get("button_w", 30), 30), safe_int(counter_cfg.get("button_h", 26), 26))
        button.setStyleSheet(
            _small_button_style(
                str(counter_cfg.get("button_background", "#34383c")),
                str(counter_cfg.get("button_text_color", "#ffffff")),
                str(counter_cfg.get("button_border_color", "#5c6268")),
            )
        )

    if bool(counter_cfg.get("use_assets", False)) and callable(resolve_roll_asset_path):
        minus_icon_path = resolve_roll_asset_path(str(counter_cfg.get("minus_asset", "") or ""))
        plus_icon_path = resolve_roll_asset_path(str(counter_cfg.get("plus_asset", "") or ""))
        if minus_icon_path is not None and plus_icon_path is not None:
            minus_icon = QIcon(str(minus_icon_path))
            plus_icon = QIcon(str(plus_icon_path))
            for button in (adv_minus, dis_minus, manual_minus):
                button.setIcon(minus_icon)
                button.setText("")
            for button in (adv_plus, dis_plus, manual_plus):
                button.setIcon(plus_icon)
                button.setText("")

    advantages_label = QLabel("Vorteile:")
    advantages_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    disadvantages_label = QLabel("Nachteile:")
    disadvantages_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    manual_label = QLabel("Manueller Bonus/Malus:")
    manual_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    spinbox_style = _spinbox_style(preview_cfg, counter_cfg, normal_text_font_size, resolve_roll_asset_path)
    advantages_spin.setStyleSheet(spinbox_style)
    disadvantages_spin.setStyleSheet(spinbox_style)
    manual_bonus_spin.setStyleSheet(spinbox_style)
    controls.setContentsMargins(0, 0, 0, 0)
    controls.setSpacing(6)
    for label, minus_button, spinbox, plus_button in (
        (advantages_label, adv_minus, advantages_spin, adv_plus),
        (disadvantages_label, dis_minus, disadvantages_spin, dis_plus),
        (manual_label, manual_minus, manual_bonus_spin, manual_plus),
    ):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label.setFixedWidth(safe_int(counter_cfg.get("label_w", 150), 150))
        row.addWidget(label)
        row.addWidget(minus_button)
        row.addWidget(spinbox)
        row.addWidget(plus_button)
        row.addStretch()
        controls.addLayout(row)
    right_layout.insertLayout(0, controls)

    keep_layout = QHBoxLayout()
    keep_group = QButtonGroup(dialog)
    keep_group.setExclusive(True)
    keep_high = QCheckBox(str(keep_cfg.get("kh_text", "Höchsten behalten (kh1)")), dialog)
    keep_low = QCheckBox(str(keep_cfg.get("kl_text", "Niedrigsten behalten (kl1)")), dialog)
    keep_group.addButton(keep_high)
    keep_group.addButton(keep_low)
    keep_high.setChecked(True)
    keep_title = QLabel("Keep:")
    keep_title.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    keep_style = _marker_checkbox_style(keep_cfg, resolve_roll_asset_path, normal_text_color, normal_text_font_size, safe_int)
    keep_high.setStyleSheet(keep_style)
    keep_low.setStyleSheet(keep_style)
    keep_layout.addWidget(keep_title)
    keep_layout.addWidget(keep_high)
    keep_layout.addWidget(keep_low)
    keep_layout.addStretch()
    right_layout.insertLayout(1, keep_layout)

    paradigm_checkbox = None
    if not is_initiative_context:
        paradigm_checkbox = QCheckBox(str(paradigm_cfg.get("text", "Paradigma / Brennen verwenden (+10)")), dialog)
        paradigm_checkbox.setChecked(False)
        paradigm_checkbox.setToolTip(str(paradigm_cfg.get("tooltip", "Manueller Schalter. Es wird kein Paradigma automatisch verbraucht.")))
        paradigm_checkbox.setStyleSheet(
            _marker_checkbox_style(
                _dict(paradigm_cfg.get("indicator")),
                resolve_roll_asset_path,
                normal_text_color,
                normal_text_font_size,
                safe_int,
            )
        )
        right_layout.insertWidget(2, paradigm_checkbox)

    preview_title = QLabel(preview_label_text)
    preview_title.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
    preview_layout.addWidget(preview_title)

    roll_command_edit = QLineEdit(dialog)
    roll_command_edit.setPlaceholderText("/r 1d20")
    roll_command_edit.setStyleSheet(
        _framed_box_style(
            str(preview_cfg.get("background", "#101214")),
            str(preview_cfg.get("border_color", "#8a6a32")),
            str(preview_cfg.get("text_color", "#f2d28b")),
            preview_font_size,
            preview_frame_cfg,
            resolve_roll_asset_path,
            padding=safe_int(preview_frame_cfg.get("padding", 10), 10),
            bold=True,
        )
    )
    roll_command_edit.setMinimumHeight(preview_height)
    roll_command_edit.setFixedHeight(preview_height)
    preview_layout.addWidget(roll_command_edit)

    buttons_row = QHBoxLayout()
    buttons_row.setContentsMargins(0, 0, 0, 0)
    buttons_row.setSpacing(buttons_gap)
    copy_button = _make_dialog_button(
        str(buttons_cfg.get("copy_text", "Kopieren")),
        dialog,
        buttons_cfg,
        resolve_roll_asset_path,
        safe_int,
        "copy",
    )
    copy_open_browser_button = _make_dialog_button(
        str(buttons_cfg.get("copy_open_browser_text", "Kopieren & Browser öffnen")),
        dialog,
        buttons_cfg,
        resolve_roll_asset_path,
        safe_int,
        "copy_open_browser",
    )
    close_button = _make_dialog_button(
        str(buttons_cfg.get("close_text", "Schließen")),
        dialog,
        buttons_cfg,
        resolve_roll_asset_path,
        safe_int,
        "close",
    )
    buttons_row.addStretch()
    buttons_row.addWidget(copy_button)
    buttons_row.addWidget(copy_open_browser_button)
    buttons_row.addWidget(close_button)
    buttons_row.addStretch()
    buttons_layout.addLayout(buttons_row)

    def current_keep_mode():
        if keep_high.isChecked():
            return "kh1"
        if keep_low.isChecked():
            return "kl1"
        return ""

    def adjust_spin(spinbox, delta):
        spinbox.setValue(max(spinbox.minimum(), min(spinbox.maximum(), spinbox.value() + delta)))

    def collect_checked_suggestion_effects(checkboxes, source_label):
        collected = {"advantage": 0, "disadvantage": 0, "extra_bonuses": [], "info_only": []}
        if not isinstance(checkboxes, list):
            return collected
        for checkbox in checkboxes:
            if checkbox is None or not checkbox.isChecked():
                continue
            effect = checkbox.property("suggested_effect")
            if not isinstance(effect, dict):
                effect = {}
            label = str(checkbox.property("rule_id") or checkbox.property("wellbeing_label") or checkbox.text() or "")
            if bool(effect.get("info_only", False)):
                collected["info_only"].append(label)
                continue
            advantage = _effect_int(effect.get("advantage", 0))
            disadvantage = _effect_int(effect.get("disadvantage", 0))
            flat_bonus = _effect_int(effect.get("flat_bonus", effect.get("bonus", 0)))
            flat_malus = _effect_int(effect.get("flat_malus", 0))
            collected["advantage"] += max(0, advantage)
            collected["disadvantage"] += max(0, disadvantage)
            if flat_bonus != 0:
                collected["extra_bonuses"].append(flat_bonus)
            if flat_malus != 0:
                collected["extra_bonuses"].append(-abs(flat_malus))
        if debug_info_only_enabled and callable(log_debug):
            for info_label in collected["info_only"]:
                log_debug("roll20", f'ROLL EFFECT INFO_ONLY source={source_label} label="{info_label}"')
        return collected

    def update_roll_preview():
        specialization_advantages = sum(1 for checkbox in specialization_checkboxes if checkbox.isChecked())
        perk_effects = collect_checked_suggestion_effects(perk_suggestion_checkboxes, "perk")
        wellbeing_effects = collect_checked_suggestion_effects(wellbeing_suggestion_checkboxes, "wellbeing")
        dice_count = (
            1
            + advantages_spin.value()
            + specialization_advantages
            + perk_effects["advantage"]
            + wellbeing_effects["advantage"]
            - disadvantages_spin.value()
            - perk_effects["disadvantage"]
            - wellbeing_effects["disadvantage"]
        )
        if dice_count <= 0:
            dice_count = 1
        skill_bonus = skill_value if skill_value_allowed else 0
        manual_bonus = manual_bonus_spin.value()
        extra_bonuses = []
        if paradigm_checkbox is not None and paradigm_checkbox.isChecked():
            paradigm_bonus = safe_int(paradigm_cfg.get("bonus", 10), 10)
            extra_bonuses.append(paradigm_bonus)
            if debug_paradigm_enabled and callable(log_debug):
                log_debug("roll20", f"ROLL PARADIGM active=True bonus={paradigm_bonus}")
        extra_bonuses.extend(fixed_extra_bonuses)
        extra_bonuses.extend(perk_effects["extra_bonuses"])
        extra_bonuses.extend(wellbeing_effects["extra_bonuses"])
        command = build_command(dice_count, current_keep_mode(), skill_bonus, manual_bonus, extra_bonuses)
        roll_command_edit.setText(command)
        if debug_preview_enabled and callable(log_debug):
            log_debug("roll20", f'ROLL PREVIEW dice={dice_count} skill={skill_bonus} manual={manual_bonus} extras={extra_bonuses} command="{command}"')

    def copy_roll_command():
        command = roll_command_edit.text().strip()
        QApplication.clipboard().setText(command)
        if callable(log_debug):
            log_debug("roll20", f"ROLL COPY {command}")
        dialog.accept()

    def copy_roll_command_and_open_browser():
        command = _roll_command_with_label(roll_command_edit.text().strip(), display_name)
        QApplication.clipboard().setText(command)
        if callable(log_debug):
            log_debug("roll20", f"ROLL COPY OPEN_BROWSER {command}")
        dialog.accept()
        if callable(open_roll20_browser):
            open_roll20_browser()

    def on_perk_suggestion_toggled(checkbox, checked):
        if checkbox is None:
            return
        rule_id = str(checkbox.property("rule_id") or "")
        effect = checkbox.property("suggested_effect")
        if not isinstance(effect, dict):
            effect = {}
        compact_effect = json.dumps(effect, ensure_ascii=False, separators=(",", ":"))
        if debug_toggles_enabled and callable(log_debug):
            log_debug("roll20", f"PERK SUGGESTION TOGGLE rule={rule_id} checked={bool(checked)} effect={compact_effect}")
        update_roll_preview()

    def on_wellbeing_suggestion_toggled(checkbox, checked):
        if checkbox is None:
            return
        label = str(checkbox.property("wellbeing_label") or "")
        effect = checkbox.property("suggested_effect")
        if not isinstance(effect, dict):
            effect = {}
        compact_effect = json.dumps(effect, ensure_ascii=False, separators=(",", ":"))
        if debug_toggles_enabled and callable(log_debug):
            log_debug("roll20", f'WELLBEING SUGGESTION TOGGLE label="{label}" checked={bool(checked)} effect={compact_effect}')
        update_roll_preview()

    advantages_spin.valueChanged.connect(update_roll_preview)
    disadvantages_spin.valueChanged.connect(update_roll_preview)
    manual_bonus_spin.valueChanged.connect(update_roll_preview)
    keep_high.toggled.connect(update_roll_preview)
    keep_low.toggled.connect(update_roll_preview)
    if paradigm_checkbox is not None:
        paradigm_checkbox.toggled.connect(update_roll_preview)
    adv_minus.clicked.connect(lambda: adjust_spin(advantages_spin, -1))
    adv_plus.clicked.connect(lambda: adjust_spin(advantages_spin, 1))
    dis_minus.clicked.connect(lambda: adjust_spin(disadvantages_spin, -1))
    dis_plus.clicked.connect(lambda: adjust_spin(disadvantages_spin, 1))
    manual_minus.clicked.connect(lambda: adjust_spin(manual_bonus_spin, -1))
    manual_plus.clicked.connect(lambda: adjust_spin(manual_bonus_spin, 1))
    for checkbox in specialization_checkboxes:
        checkbox.toggled.connect(update_roll_preview)
    for checkbox in perk_suggestion_checkboxes:
        checkbox.toggled.connect(lambda checked=False, cb=checkbox: on_perk_suggestion_toggled(cb, checked))
    for checkbox in wellbeing_suggestion_checkboxes:
        checkbox.toggled.connect(lambda checked=False, cb=checkbox: on_wellbeing_suggestion_toggled(cb, checked))
    copy_button.clicked.connect(copy_roll_command)
    copy_open_browser_button.clicked.connect(copy_roll_command_and_open_browser)
    close_button.clicked.connect(dialog.close)
    if custom_close_button is not None:
        custom_close_button.clicked.connect(dialog.close)
    update_roll_preview()
    return dialog.exec()


def _rect_from_cfg(rect_cfg, default_x, default_y, default_w, default_h, safe_int):
    return (
        safe_int(rect_cfg.get("x", default_x), default_x),
        safe_int(rect_cfg.get("y", default_y), default_y),
        safe_int(rect_cfg.get("w", default_w), default_w),
        safe_int(rect_cfg.get("h", default_h), default_h),
    )


def _roll_command_with_label(command, label):
    clean_command = str(command or "").strip()
    clean_label = " ".join(str(label or "").split())
    if not clean_command or not clean_label:
        return clean_command
    return f"{clean_command} ({clean_label})"


def _anchored_rect_from_cfg(rect_cfg, parent_w, default_top, default_w, default_h, safe_int):
    rect_w = safe_int(rect_cfg.get("w", default_w), default_w)
    rect_h = safe_int(rect_cfg.get("h", default_h), default_h)
    if str(rect_cfg.get("anchor", "") or "").strip().lower() == "top_right":
        right = safe_int(rect_cfg.get("right", 12), 12)
        top = safe_int(rect_cfg.get("top", default_top), default_top)
        return (max(0, int(parent_w) - right - rect_w), top, rect_w, rect_h)
    return (
        safe_int(rect_cfg.get("x", max(0, int(parent_w) - 44)), max(0, int(parent_w) - 44)),
        safe_int(rect_cfg.get("y", default_top), default_top),
        rect_w,
        rect_h,
    )


def _alignment_from_cfg(value):
    normalized = str(value or "").strip().lower()
    if normalized == "left":
        return Qt.AlignLeft
    if normalized == "right":
        return Qt.AlignRight
    return Qt.AlignHCenter


def _elided_text(label, text, width):
    available_width = max(10, int(width) - 8)
    return QFontMetrics(label.font()).elidedText(str(text), Qt.ElideRight, available_width)


def _make_panel_layout(parent, rect, margin, spacing=8):
    panel = QWidget(parent)
    panel.setGeometry(*rect)
    panel.setStyleSheet("background: transparent;")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(margin, margin, margin, margin)
    panel_layout.setSpacing(spacing)
    return panel, panel_layout


def _make_scroll_zone(parent, rect, margin, spacing):
    scroll = QScrollArea(parent)
    scroll.setGeometry(*rect)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollArea > QWidget > QWidget { background: transparent; }")
    content = QWidget(scroll)
    content.setStyleSheet("background: transparent;")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(margin, margin, margin, margin)
    content_layout.setSpacing(spacing)
    scroll.setWidget(content)
    return scroll, content, content_layout


class RollAssetButton(QPushButton):
    def __init__(self, text, pixmap, text_color, hover_text_color, pressed_text_color, font_size, parent=None):
        super().__init__(text, parent)
        self._pixmap = pixmap if isinstance(pixmap, QPixmap) and not pixmap.isNull() else None
        self._text_color = str(text_color)
        self._hover_text_color = str(hover_text_color)
        self._pressed_text_color = str(pressed_text_color)
        self._hovered = False
        self._pressed = False
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; "
            f"font-size: {int(font_size)}px; font-weight: 700; color: {self._text_color}; "
            "}"
        )
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if self._pixmap is not None:
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = int((self.width() - scaled.width()) / 2)
            y = int((self.height() - scaled.height()) / 2)
            painter.drawPixmap(x, y, scaled)
        color = self._pressed_text_color if self._pressed else self._hover_text_color if self._hovered else self._text_color
        painter.setPen(QColor(color))
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())
        painter.end()


def _dialog_style(background, text_color, font_size, border_color, frame_cfg, resolve_asset_path):
    style = f"QDialog {{ background: {background}; color: {text_color}; font-size: {font_size}px; border: 2px solid {border_color};"
    if bool(frame_cfg.get("enabled", False)):
        border_width = _safe_int(frame_cfg.get("border_width", 12), 12)
        image_style = _border_image_style(frame_cfg, resolve_asset_path)
        if image_style:
            style += f" border: {border_width}px solid transparent; {image_style}"
    style += " }"
    return style


def _info_label_style(text_color, font_size, background, border_color):
    return (
        f"color: {text_color}; font-size: {font_size}px; "
        f"background: {background}; border: 1px solid {border_color}; "
        "border-radius: 3px; padding: 5px 8px;"
    )


def _framed_box_style(background, border_color, text_color, font_size, frame_cfg, resolve_asset_path, padding=8, bold=False):
    weight = "700" if bold else "500"
    style = (
        f"font-size: {font_size}px; font-weight: {weight}; "
        f"color: {text_color}; background: {background}; "
        f"border: 1px solid {border_color}; padding: {max(0, int(padding))}px;"
    )
    if bool(frame_cfg.get("enabled", False)):
        border_width = _safe_int(frame_cfg.get("border_width", 10), 10)
        image_style = _border_image_style(frame_cfg, resolve_asset_path)
        if image_style:
            style = (
                f"font-size: {font_size}px; font-weight: {weight}; color: {text_color}; "
                f"background: {background}; border: {border_width}px solid transparent; "
                f"padding: {max(0, int(padding))}px; {image_style}"
            )
    return style


def _small_button_style(background, text_color, border_color):
    return (
        "QPushButton {"
        f"background: {background}; color: {text_color}; border: 1px solid {border_color}; "
        "border-radius: 3px; font-weight: 700; padding: 0px;"
        "}"
        "QPushButton:hover { border: 1px solid rgba(242, 210, 139, 180); }"
        "QPushButton:pressed { background: rgba(0, 0, 0, 120); }"
    )


def _spinbox_style(preview_cfg, counter_cfg, font_size, resolve_asset_path):
    background = str(counter_cfg.get("value_background", preview_cfg.get("background", "#101214")))
    text_color = str(counter_cfg.get("value_text_color", preview_cfg.get("text_color", "#f2d28b")))
    border_color = str(counter_cfg.get("value_border_color", counter_cfg.get("button_border_color", "#5c6268")))
    value_frame_cfg = _dict(counter_cfg.get("value_frame"))
    render_mode = str(value_frame_cfg.get("render_mode", "image") or "image").strip().lower()
    if render_mode == "css":
        return (
            "QSpinBox {"
            f"background: {background}; color: {text_color}; border: 1px solid {border_color}; "
            f"border-radius: 3px; font-size: {font_size}px; font-weight: 700; padding: 2px 6px;"
            "}"
            "QSpinBox::up-button { width: 0px; height: 0px; border: none; }"
            "QSpinBox::down-button { width: 0px; height: 0px; border: none; }"
        )
    value_padding = _safe_int(value_frame_cfg.get("padding", 3), 3)
    box_style = _framed_box_style(
        background,
        border_color,
        text_color,
        font_size,
        value_frame_cfg,
        resolve_asset_path,
        padding=value_padding,
        bold=True,
    )
    return (
        "QSpinBox {"
        f"{box_style}"
        "}"
        "QSpinBox::up-button { width: 0px; height: 0px; border: none; }"
        "QSpinBox::down-button { width: 0px; height: 0px; border: none; }"
    )


def _dialog_checkbox_style(base_style, checkbox_cfg, resolve_asset_path, text_color, font_size, safe_int):
    style = str(base_style or "")
    if "QCheckBox" not in style:
        spacing = safe_int(checkbox_cfg.get("spacing", 6), 6)
        cfg_text_color = str(checkbox_cfg.get("text_color", text_color))
        cfg_font_size = safe_int(checkbox_cfg.get("font_size", font_size), font_size)
        style += f"QCheckBox {{ color: {cfg_text_color}; font-size: {cfg_font_size}px; spacing: {spacing}px; }}"
    if bool(checkbox_cfg.get("use_assets", False)):
        checked_url = _asset_url(str(checkbox_cfg.get("asset_checked", "") or ""), resolve_asset_path)
        unchecked_url = _asset_url(str(checkbox_cfg.get("asset_unchecked", "") or ""), resolve_asset_path)
        if checked_url and unchecked_url:
            indicator_w = safe_int(checkbox_cfg.get("indicator_w", 18), 18)
            indicator_h = safe_int(checkbox_cfg.get("indicator_h", 18), 18)
            style += (
                f"QCheckBox::indicator {{ width: {indicator_w}px; height: {indicator_h}px; }}"
                f"QCheckBox::indicator:checked {{ image: url({checked_url}); }}"
                f"QCheckBox::indicator:unchecked {{ image: url({unchecked_url}); }}"
            )
    return style


def _marker_checkbox_style(indicator_cfg, resolve_asset_path, text_color, font_size, safe_int):
    cfg_text_color = str(indicator_cfg.get("text_color", text_color))
    cfg_font_size = safe_int(indicator_cfg.get("font_size", font_size), font_size)
    spacing = safe_int(indicator_cfg.get("spacing", 6), 6)
    style = f"QCheckBox {{ color: {cfg_text_color}; font-size: {cfg_font_size}px; spacing: {spacing}px; }}"
    checked_url = _asset_url(str(indicator_cfg.get("active_asset", "") or ""), resolve_asset_path)
    unchecked_url = _asset_url(str(indicator_cfg.get("inactive_asset", "") or ""), resolve_asset_path)
    if checked_url and unchecked_url:
        indicator_w = safe_int(indicator_cfg.get("indicator_w", 18), 18)
        indicator_h = safe_int(indicator_cfg.get("indicator_h", 18), 18)
        style += (
            f"QCheckBox::indicator {{ width: {indicator_w}px; height: {indicator_h}px; }}"
            f"QCheckBox::indicator:checked {{ image: url({checked_url}); }}"
            f"QCheckBox::indicator:unchecked {{ image: url({unchecked_url}); }}"
        )
    return style


def _make_dialog_button(text, parent, buttons_cfg, resolve_asset_path, safe_int, button_key="copy"):
    background = str(buttons_cfg.get("background", "rgba(52, 56, 60, 190)"))
    text_color = str(buttons_cfg.get("text_color", "#f2d28b"))
    hover_text_color = str(buttons_cfg.get("hover_text_color", "#ffffff"))
    pressed_text_color = str(buttons_cfg.get("pressed_text_color", hover_text_color))
    font_size = safe_int(buttons_cfg.get("font_size", 13), 13)
    padding_x = safe_int(buttons_cfg.get("padding_x", 14), 14)
    padding_y = safe_int(buttons_cfg.get("padding_y", 6), 6)
    width_key = f"{button_key}_w"
    button_w = safe_int(buttons_cfg.get(width_key, buttons_cfg.get("w", 190)), 190)
    button_h = safe_int(buttons_cfg.get("h", 42), 42)
    visual_mode = str(buttons_cfg.get("visual_mode", "") or "").strip().lower()
    if bool(buttons_cfg.get("use_assets", False)) and visual_mode == "menu_asset":
        pixmap = _asset_pixmap(str(buttons_cfg.get("asset", "") or ""), resolve_asset_path)
        if pixmap is not None:
            button = RollAssetButton(
                text,
                pixmap,
                text_color,
                hover_text_color,
                pressed_text_color,
                font_size,
                parent,
            )
            button.setFixedSize(button_w, button_h)
            return button

    button = QPushButton(text, parent)
    button.setFixedSize(button_w, button_h)
    button.setStyleSheet(
        "QPushButton {"
        f"background: {background}; color: {text_color}; border: none; "
        f"font-size: {font_size}px; font-weight: 700; padding: {padding_y}px {padding_x}px;"
        "}"
        f"QPushButton:hover {{ color: {hover_text_color}; }}"
        f"QPushButton:pressed {{ color: {pressed_text_color}; }}"
    )
    return button


def _asset_pixmap(relative_path, resolve_asset_path):
    if not relative_path or not callable(resolve_asset_path):
        return None
    path = resolve_asset_path(relative_path)
    if path is None:
        return None
    pixmap = QPixmap(str(path))
    return pixmap if not pixmap.isNull() else None


def _border_image_style(frame_cfg, resolve_asset_path):
    asset_url = _asset_url(str(frame_cfg.get("asset", "") or ""), resolve_asset_path)
    if not asset_url:
        return ""
    slice_cfg = _dict(frame_cfg.get("slice"))
    left = _safe_int(slice_cfg.get("left", 10), 10)
    top = _safe_int(slice_cfg.get("top", 10), 10)
    right = _safe_int(slice_cfg.get("right", 10), 10)
    bottom = _safe_int(slice_cfg.get("bottom", 10), 10)
    return f"border-image: url({asset_url}) {top} {right} {bottom} {left} stretch stretch;"


def _asset_url(relative_path, resolve_asset_path):
    if not relative_path or not callable(resolve_asset_path):
        return ""
    path = resolve_asset_path(relative_path)
    if path is None:
        return ""
    return str(path).replace("\\", "/")


def _dict(value):
    return value if isinstance(value, dict) else {}


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)


def _effect_int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def _effect_grants_dice(effect):
    if not isinstance(effect, dict):
        return False
    return _effect_int(effect.get("advantage", 0)) > 0 or _effect_int(effect.get("disadvantage", 0)) > 0
