import json

from PySide6.QtGui import QIcon
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
    QRadioButton,
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
    log_info = callbacks.get("log_info")
    compact_text = callbacks.get("compact_text")
    specialization_preview = callbacks.get("specialization_preview")
    resolve_roll_asset_path = callbacks.get("resolve_roll_asset_path")

    dialog_cfg = _dict(roll_layout.get("dialog"))
    sections_cfg = _dict(roll_layout.get("sections"))
    spec_cfg = _dict(roll_layout.get("specialization_box"))
    counter_cfg = _dict(roll_layout.get("counter"))
    keep_cfg = _dict(roll_layout.get("keep_options"))
    preview_cfg = _dict(roll_layout.get("roll_preview"))
    direct_send_cfg = _dict(roll_layout.get("direct_send"))
    buttons_cfg = _dict(roll_layout.get("buttons"))
    spec_options_cfg = _dict(roll_layout.get("specialization_options"))
    paradigm_cfg = _dict(roll_layout.get("paradigm"))
    perk_suggestions_cfg = _dict(roll_layout.get("perk_suggestions"))
    labels_cfg = _dict(roll_layout.get("labels"))
    debug_cfg = _dict(roll_layout.get("debug"))

    dialog_title = str(dialog_cfg.get("title", "Roll20 Wurf-Assistent"))
    dialog_w = safe_int(dialog_cfg.get("w", 700), 700)
    dialog_h = safe_int(dialog_cfg.get("h", 620), 620)
    text_color = str(dialog_cfg.get("text_color", "#f2f2f2"))
    muted_text_color = str(dialog_cfg.get("muted_text_color", "#c8c0aa"))
    accent_color = str(dialog_cfg.get("accent_color", "#f2d28b"))
    base_font_size = safe_int(dialog_cfg.get("font_size", 13), 13)
    title_font_size = safe_int(dialog_cfg.get("title_font_size", 18), 18)
    dialog_bg = str(dialog_cfg.get("background", "#202426"))
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

    checkbox_style = str(style_context.get("checkbox_style", ""))
    custom_dialog_title = str(model.get("dialog_title", "") or "")
    dialog = QDialog(parent)
    dialog.setWindowTitle(custom_dialog_title or dialog_title)
    dialog.setModal(True)
    dialog.resize(dialog_w, min(980, dialog_h + dynamic_extra))
    dialog.setStyleSheet(f"QDialog {{ background: {dialog_bg}; color: {text_color}; font-size: {base_font_size}px; }}")
    layout = QVBoxLayout(dialog)
    layout.setSpacing(spacing)

    header_text = f"Fertigkeit: {display_name}"
    if is_character_initiative:
        header_text = "Initiative"
    elif is_initiative_context:
        header_text = f"Initiative - {display_name}"
    header = QLabel(header_text)
    header.setStyleSheet(f"font-size: {title_font_size}px; font-weight: 700; color: {accent_color};")
    layout.addWidget(header)

    if is_character_initiative:
        value_label = QLabel(
            f'Wert: {model.get("raw_value", skill_value)}   Bonus: {model.get("bonus_value", 0)}   Rollwert: {skill_value}'
        )
    else:
        value_label = QLabel(f"Wert: {skill_value}")
    value_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    layout.addWidget(value_label)

    if not is_character_initiative:
        attrs_label = QLabel(f"Attribute: {attrs_text}")
        attrs_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
        layout.addWidget(attrs_label)

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
        layout.addWidget(spec_title)

        spec_value = QLabel(specialization_preview_text)
        spec_value.setWordWrap(True)
        spec_value.setStyleSheet(
            f"background: {str(spec_cfg.get('background', '#141618'))}; "
            f"border: 1px solid {str(spec_cfg.get('border_color', '#3a3a3a'))}; "
            f"padding: 8px; color: {str(spec_cfg.get('text_color', '#ffffff'))}; "
            f"font-size: {spec_font_size}px;"
        )
        spec_value.setMinimumHeight(spec_height)
        layout.addWidget(spec_value)

        spec_options_title_label = QLabel(str(spec_options_cfg.get("title", "Spezialisierungen:")))
        spec_options_title_label.setStyleSheet(
            f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;"
        )
        layout.addWidget(spec_options_title_label)

    specialization_checkboxes = []
    if show_specialization:
        if specialization_items:
            checkboxes_grid_widget = QWidget(dialog)
            checkboxes_grid_layout = QGridLayout(checkboxes_grid_widget)
            checkboxes_grid_layout.setContentsMargins(0, 0, 0, 0)
            checkboxes_grid_layout.setHorizontalSpacing(spec_options_column_spacing)
            checkboxes_grid_layout.setVerticalSpacing(spec_options_row_spacing)
            for index, item in enumerate(specialization_items):
                checkbox = QCheckBox(item, dialog)
                checkbox.setChecked(False)
                checkbox.setStyleSheet(checkbox_style)
                row = index % spec_options_max_rows_per_column
                col = index // spec_options_max_rows_per_column
                checkboxes_grid_layout.addWidget(checkbox, row, col)
                specialization_checkboxes.append(checkbox)
            checkboxes_grid_layout.setColumnStretch(99, 1)
            layout.addWidget(checkboxes_grid_widget)
            spec_hint_label = QLabel(str(spec_options_cfg.get("hint", "Spezialisierungen: +1 Vorteil je Auswahl")))
            spec_hint_label.setStyleSheet(f"color: {hint_text_color}; font-size: {hint_text_font_size}px;")
            layout.addWidget(spec_hint_label)
        else:
            spec_empty_label = QLabel(str(spec_options_cfg.get("empty_text", "Keine Spezialisierung vorhanden")))
            spec_empty_label.setStyleSheet(f"color: {hint_text_color}; font-size: {hint_text_font_size}px;")
            layout.addWidget(spec_empty_label)

    if fixed_bonus_lines:
        fixed_title = QLabel("Feste Boni:")
        fixed_title.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
        layout.addWidget(fixed_title)
        for line in fixed_bonus_lines:
            row_label = QLabel(str(line))
            row_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
            layout.addWidget(row_label)

    perk_suggestion_checkboxes = []
    if perk_suggestions:
        perk_title_label = QLabel(str(perk_suggestions_cfg.get("title", "Perk-/Nachteil-Vorschläge:")))
        perk_title_label.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
        layout.addWidget(perk_title_label)
        perk_suggestions_max_visible = safe_int(perk_suggestions_cfg.get("max_visible", 4), 4)
        if perk_suggestions_max_visible <= 0:
            perk_suggestions_max_visible = 4
        visible_suggestions = perk_suggestions[:perk_suggestions_max_visible]
        for suggestion in visible_suggestions:
            label_text = str(suggestion.get("label", "Regelvorschlag"))
            source_type = "Perk" if str(suggestion.get("source_type", "")) == "perk" else "Nachteil"
            source_name = str(suggestion.get("source_name", "") or "")
            source_effect = str(suggestion.get("source_effect", "") or "")
            source_text = f"{source_type} {source_name}".strip()
            compact_effect = compact_text(source_effect, 60) if callable(compact_text) else source_effect
            compact_source_line = source_text if not compact_effect else f"{source_text} · {compact_effect}"
            compact_source_line = compact_text(compact_source_line, 70) if callable(compact_text) else compact_source_line
            checkbox = QCheckBox(label_text, dialog)
            checkbox.setChecked(False)
            checkbox.setStyleSheet(checkbox_style)
            checkbox.setProperty("rule_id", str(suggestion.get("rule_id", "")))
            checkbox.setProperty("suggested_effect", suggestion.get("suggested_effect", {}))
            checkbox.setToolTip(source_text if not source_effect else f"{source_text}\nEffekt: {source_effect}")
            layout.addWidget(checkbox)
            source_label = QLabel(compact_source_line)
            source_label.setStyleSheet(f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;")
            source_label.setToolTip(source_text if not source_effect else f"{source_text}\nEffekt: {source_effect}")
            layout.addWidget(source_label)
            perk_suggestion_checkboxes.append(checkbox)

        remaining = len(perk_suggestions) - len(visible_suggestions)
        if remaining > 0:
            more_label = QLabel(f"... +{remaining} weitere Vorschläge")
            more_label.setStyleSheet(f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;")
            layout.addWidget(more_label)
        perk_hint_label = QLabel(str(perk_suggestions_cfg.get("hint", "Angehakte Vorschläge wirken nur manuell auf diesen Wurf.")))
        perk_hint_label.setStyleSheet(f"color: {hint_text_color}; font-size: {hint_text_font_size}px;")
        layout.addWidget(perk_hint_label)

    wellbeing_suggestion_checkboxes = []
    if wellbeing_suggestions:
        wellbeing_title_label = QLabel("Wohlbefinden-Vorschläge:")
        wellbeing_title_label.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
        layout.addWidget(wellbeing_title_label)
        for suggestion in wellbeing_suggestions:
            label_text = str(suggestion.get("label", "Wohlbefinden-Vorschlag"))
            source_label = str(suggestion.get("source_label", "") or "")
            source_text = f"Quelle: {source_label}" if source_label else "Quelle: Wohlbefinden"
            checkbox = QCheckBox(label_text, dialog)
            checkbox.setChecked(False)
            checkbox.setStyleSheet(checkbox_style)
            checkbox.setProperty("wellbeing_label", source_label)
            checkbox.setProperty("suggested_effect", suggestion.get("suggested_effect", {}))
            checkbox.setToolTip(source_text)
            layout.addWidget(checkbox)
            source_row = QLabel(source_text)
            source_row.setStyleSheet(f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;")
            source_row.setToolTip(source_text)
            layout.addWidget(source_row)
            wellbeing_suggestion_checkboxes.append(checkbox)

    if not is_initiative_context:
        skill_usage_text = (
            f"Skillwert wird verwendet: Ja (+{skill_value})"
            if skill_value_allowed
            else "Skillwert wird verwendet: Nein (keine Attribute/Spezialisierung)"
        )
        skill_usage_label = QLabel(skill_usage_text)
        skill_usage_label.setStyleSheet(f"color: {muted_text_cfg_color}; font-size: {muted_text_font_size}px;")
        layout.addWidget(skill_usage_label)

    controls = QHBoxLayout()
    advantages_spin = QSpinBox(dialog)
    advantages_spin.setRange(0, 99)
    advantages_spin.setValue(0)
    advantages_spin.setButtonSymbols(QSpinBox.NoButtons)
    advantages_spin.setFixedWidth(safe_int(counter_cfg.get("value_w", 42), 42))
    disadvantages_spin = QSpinBox(dialog)
    disadvantages_spin.setRange(0, 99)
    disadvantages_spin.setValue(0)
    disadvantages_spin.setButtonSymbols(QSpinBox.NoButtons)
    disadvantages_spin.setFixedWidth(safe_int(counter_cfg.get("value_w", 42), 42))
    manual_bonus_spin = QSpinBox(dialog)
    manual_bonus_spin.setRange(-999, 999)
    manual_bonus_spin.setValue(0)

    adv_minus = QPushButton("-", dialog)
    adv_plus = QPushButton("+", dialog)
    dis_minus = QPushButton("-", dialog)
    dis_plus = QPushButton("+", dialog)
    for button in (adv_minus, adv_plus, dis_minus, dis_plus):
        button.setFixedSize(safe_int(counter_cfg.get("button_w", 30), 30), safe_int(counter_cfg.get("button_h", 26), 26))
        button.setStyleSheet(
            f"background: {str(counter_cfg.get('button_background', '#34383c'))}; "
            f"color: {str(counter_cfg.get('button_text_color', '#ffffff'))}; "
            f"border: 1px solid {str(counter_cfg.get('button_border_color', '#5c6268'))};"
        )

    if bool(counter_cfg.get("use_assets", False)) and callable(resolve_roll_asset_path):
        minus_icon_path = resolve_roll_asset_path(str(counter_cfg.get("minus_asset", "") or ""))
        plus_icon_path = resolve_roll_asset_path(str(counter_cfg.get("plus_asset", "") or ""))
        if minus_icon_path is not None and plus_icon_path is not None:
            minus_icon = QIcon(str(minus_icon_path))
            plus_icon = QIcon(str(plus_icon_path))
            for button in (adv_minus, dis_minus):
                button.setIcon(minus_icon)
                button.setText("")
            for button in (adv_plus, dis_plus):
                button.setIcon(plus_icon)
                button.setText("")

    advantages_label = QLabel("Vorteile:")
    advantages_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    disadvantages_label = QLabel("Nachteile:")
    disadvantages_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    manual_label = QLabel("Manueller Bonus/Malus:")
    manual_label.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    controls.addWidget(advantages_label)
    controls.addWidget(adv_minus)
    controls.addWidget(advantages_spin)
    controls.addWidget(adv_plus)
    controls.addWidget(disadvantages_label)
    controls.addWidget(dis_minus)
    controls.addWidget(disadvantages_spin)
    controls.addWidget(dis_plus)
    controls.addSpacing(10)
    controls.addWidget(manual_label)
    controls.addWidget(manual_bonus_spin)
    controls.addStretch()
    layout.addLayout(controls)

    keep_layout = QHBoxLayout()
    keep_group = QButtonGroup(dialog)
    keep_high = QRadioButton(str(keep_cfg.get("kh_text", "Höchsten behalten (kh1)")), dialog)
    keep_low = QRadioButton(str(keep_cfg.get("kl_text", "Niedrigsten behalten (kl1)")), dialog)
    keep_group.addButton(keep_high)
    keep_group.addButton(keep_low)
    keep_high.setChecked(True)
    keep_title = QLabel("Keep:")
    keep_title.setStyleSheet(f"color: {normal_text_color}; font-size: {normal_text_font_size}px;")
    keep_high.setStyleSheet(checkbox_style)
    keep_low.setStyleSheet(checkbox_style)
    keep_layout.addWidget(keep_title)
    keep_layout.addWidget(keep_high)
    keep_layout.addWidget(keep_low)
    keep_layout.addStretch()
    layout.addLayout(keep_layout)

    paradigm_checkbox = None
    if not is_initiative_context:
        paradigm_checkbox = QCheckBox(str(paradigm_cfg.get("text", "Paradigma / Brennen verwenden (+10)")), dialog)
        paradigm_checkbox.setChecked(False)
        paradigm_checkbox.setToolTip(str(paradigm_cfg.get("tooltip", "Manueller Schalter. Es wird kein Paradigma automatisch verbraucht.")))
        paradigm_checkbox.setStyleSheet(checkbox_style)
        layout.addWidget(paradigm_checkbox)

    preview_title = QLabel(preview_label_text)
    preview_title.setStyleSheet(f"font-weight: 700; color: {section_title_color}; font-size: {section_title_font_size}px;")
    layout.addWidget(preview_title)

    roll_command_edit = QLineEdit(dialog)
    roll_command_edit.setPlaceholderText("/r 1d20")
    roll_command_edit.setStyleSheet(
        f"font-size: {preview_font_size}px; font-weight: 700; "
        f"color: {str(preview_cfg.get('text_color', '#f2d28b'))}; "
        f"background: {str(preview_cfg.get('background', '#101214'))}; "
        f"border: 1px solid {str(preview_cfg.get('border_color', '#8a6a32'))}; padding: 10px;"
    )
    roll_command_edit.setMinimumHeight(preview_height)
    layout.addWidget(roll_command_edit)

    direct_send_checkbox = None
    if bool(direct_send_cfg.get("enabled", True)):
        direct_send_checkbox = QCheckBox(str(direct_send_cfg.get("text", "Direkt an Roll20 senden")), dialog)
        direct_send_checkbox.setToolTip(str(direct_send_cfg.get("tooltip", "Noch nicht implementiert. Aktuell wird nur kopiert.")))
        direct_send_checkbox.setStyleSheet(checkbox_style)
        layout.addWidget(direct_send_checkbox)

    buttons_layout = QHBoxLayout()
    copy_button = QPushButton(str(buttons_cfg.get("copy_text", "Kopieren")), dialog)
    copy_open_browser_button = QPushButton(
        str(buttons_cfg.get("copy_open_browser_text", "Kopieren & Browser öffnen")),
        dialog,
    )
    close_button = QPushButton(str(buttons_cfg.get("close_text", "Schließen")), dialog)
    buttons_layout.addStretch()
    buttons_layout.addWidget(copy_button)
    buttons_layout.addWidget(copy_open_browser_button)
    buttons_layout.addWidget(close_button)
    layout.addLayout(buttons_layout)

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
        if direct_send_checkbox is not None and direct_send_checkbox.isChecked() and callable(log_info):
            log_info("roll20", "ROLL SEND PLACEHOLDER direct Roll20 send requested but not implemented")
        dialog.accept()

    def copy_roll_command_and_open_browser():
        command = roll_command_edit.text().strip()
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
    for checkbox in specialization_checkboxes:
        checkbox.toggled.connect(update_roll_preview)
    for checkbox in perk_suggestion_checkboxes:
        checkbox.toggled.connect(lambda checked=False, cb=checkbox: on_perk_suggestion_toggled(cb, checked))
    for checkbox in wellbeing_suggestion_checkboxes:
        checkbox.toggled.connect(lambda checked=False, cb=checkbox: on_wellbeing_suggestion_toggled(cb, checked))
    copy_button.clicked.connect(copy_roll_command)
    copy_open_browser_button.clicked.connect(copy_roll_command_and_open_browser)
    close_button.clicked.connect(dialog.close)
    update_roll_preview()
    return dialog.exec()


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
