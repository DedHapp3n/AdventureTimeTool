from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_paths import config_path, ensure_runtime_defaults, resource_path
from app_logger import log_debug, log_warning


OVERRIDE_DEFAULT = {"version": 1, "overrides": {}}
RULES_DEFAULT = {"version": 1, "rules": {}}
RULE_TYPES = [
    "manual_label",
    "manual_formula",
    "missing_formula",
    "replace_formula_later",
    "ignore",
    "note_only",
]


def _override_file_path() -> Path:
    return config_path("calculation_overrides.json")


def _rules_file_path() -> Path:
    return config_path("calculation_rules.json")


def _default_override_entry(sheet: str, cell: str) -> dict[str, Any]:
    return {
        "target": {"sheet": sheet, "cell": cell},
        "display_name": "",
        "category": "",
        "description": "",
        "rule_type": "note_only",
        "formula": "",
        "enabled": False,
        "notes": "",
    }


def load_calculation_overrides() -> dict[str, Any]:
    ensure_runtime_defaults()
    path = _override_file_path()
    if not path.exists():
        log_debug("calculation", "override loaded count=0")
        return dict(OVERRIDE_DEFAULT)
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            log_warning("calculation", f"invalid override file, using defaults: {path}")
            return dict(OVERRIDE_DEFAULT)
        overrides = loaded.get("overrides")
        if not isinstance(overrides, dict):
            loaded["overrides"] = {}
        if not isinstance(loaded.get("version"), int):
            loaded["version"] = 1
        log_debug("calculation", f"override loaded count={len(loaded['overrides'])}")
        return loaded
    except Exception as exc:
        log_warning("calculation", f"override load failed, using defaults: {path} ({exc})")
        return dict(OVERRIDE_DEFAULT)


def save_calculation_overrides(data: dict[str, Any]) -> bool:
    path = _override_file_path()
    payload = dict(OVERRIDE_DEFAULT)
    if isinstance(data, dict):
        payload["version"] = int(data.get("version", 1))
        overrides = data.get("overrides", {})
        payload["overrides"] = overrides if isinstance(overrides, dict) else {}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        log_debug("calculation", f"override saved count={len(payload['overrides'])}")
        return True
    except Exception as exc:
        log_warning("calculation", f"override save failed: {path} ({exc})")
        return False


def load_calculation_rules() -> dict[str, Any]:
    ensure_runtime_defaults()
    path = _rules_file_path()
    if not path.exists():
        log_debug("calculation", "rules loaded count=0")
        return dict(RULES_DEFAULT)
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            log_warning("calculation", f"invalid rules file, using defaults: {path}")
            return dict(RULES_DEFAULT)
        rules = loaded.get("rules")
        if not isinstance(rules, dict):
            loaded["rules"] = {}
        if not isinstance(loaded.get("version"), int):
            loaded["version"] = 1
        log_debug("calculation", f"rules loaded count={len(loaded['rules'])}")
        return loaded
    except Exception as exc:
        log_warning("calculation", f"rules load failed, using defaults: {path} ({exc})")
        return dict(RULES_DEFAULT)


def save_calculation_rules(data: dict[str, Any]) -> bool:
    path = _rules_file_path()
    payload = dict(RULES_DEFAULT)
    if isinstance(data, dict):
        payload["version"] = int(data.get("version", 1))
        rules = data.get("rules", {})
        payload["rules"] = rules if isinstance(rules, dict) else {}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        log_debug("calculation", f"rules saved count={len(payload['rules'])}")
        return True
    except Exception as exc:
        log_warning("calculation", f"rules save failed: {path} ({exc})")
        return False


def _rule_template(
    rule_id: str,
    sheet: str,
    cell: str,
    display_name: str,
    category: str,
    rule_type: str,
    description: str,
    expression: str = "",
    sources: list[str] | None = None,
    notes: str = "",
    possible_sources: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "target": {"sheet": sheet, "cell": cell},
        "id": rule_id,
        "display_name": display_name,
        "category": category,
        "description": description,
        "rule_type": rule_type,
        "expression": expression,
        "enabled": True,
        "apply_to_cache": False,
        "sources": sources or [],
        "possible_sources": possible_sources or [],
        "notes": notes,
    }


def _cache_formula(cell_cache: dict[str, Any], sheet: str, cell: str) -> str:
    info = cell_cache.get(sheet, {}).get(cell)
    if isinstance(info, dict):
        formula = info.get("formula")
        if isinstance(formula, str) and formula.startswith("="):
            return formula
    return ""


def _ensure_default_character_rules(rule_store: dict[str, Any], cell_cache: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    payload = rule_store if isinstance(rule_store, dict) else dict(RULES_DEFAULT)
    rules = payload.get("rules")
    if not isinstance(rules, dict):
        rules = {}
        payload["rules"] = rules

    sheet = "Charakterbogen"
    hp_expr = _cache_formula(cell_cache, sheet, "F10") or "=(1+G5+(AG4*C5)+(F16/10))"
    mp_expr = _cache_formula(cell_cache, sheet, "F13")
    xp_expr = _cache_formula(cell_cache, sheet, "F16")
    lf_expr = _cache_formula(cell_cache, sheet, "AO23")
    sanity_expr = _cache_formula(cell_cache, sheet, "AO27")
    body_expr = _cache_formula(cell_cache, sheet, "AG4") or "=(AG7+AG9+AG11+AG13)/4"
    mind_expr = _cache_formula(cell_cache, sheet, "AR4") or "=(AR7+AR9+AR11+AR13)/4"

    defaults = {
        f"{sheet}!B10": _rule_template("character.hp_current", sheet, "B10", "HP Current", "Charakter / Ressourcen", "manual_value", "Aktuelle Lebenspunkte des Charakters."),
        f"{sheet}!F10": _rule_template(
            "character.hp_max", sheet, "F10", "HP Max", "Charakter / Ressourcen", "expression",
            "Maximale HP. Größe/Gewicht beeinflussen natürliche HP; Körper ist ein zentraler Modifikator. Aktuelle Sheet-Formel wird als Startregel übernommen.",
            hp_expr,
            ["Charakterbogen!G5", "Charakterbogen!AG4", "Charakterbogen!F16", "Charakterbogen!C5"],
            "PDF: Größe und Gewicht beeinflussen natürliche HP. Aktuelle Sheet-Formel nutzt Gewicht eventuell nicht direkt; daher Gewicht nur als possible_source markieren, solange die Formel es nicht referenziert.",
            ["Charakterbogen!G7"],
        ),
        f"{sheet}!B13": _rule_template("character.mp_current", sheet, "B13", "MP Current", "Charakter / Ressourcen", "manual_value", "Aktuelle Magiepunkte."),
        f"{sheet}!F13": _rule_template(
            "character.mp_max", sheet, "F13", "MP Max", "Charakter / Ressourcen", "expression",
            "MP Max nutzt aktuell Geist-Einzelwerte bzw. Magie-Bonus aus dem Sheet. Exakte Regel später prüfen.",
            mp_expr,
            ["Charakterbogen!AR7", "Charakterbogen!AR9", "Charakterbogen!AR18"],
        ),
        f"{sheet}!B16": _rule_template("character.xp_current", sheet, "B16", "XP Current", "Charakter / Ressourcen", "manual_value", "Aktuelle Erfahrungspunkte."),
        f"{sheet}!F16": _rule_template(
            "character.xp_max", sheet, "F16", "XP Max", "Charakter / Ressourcen",
            "expression" if xp_expr else "manual_value",
            "Maximale Erfahrungspunkte.",
            xp_expr,
            notes="Wenn keine Formel im Sheet vorhanden ist, bleibt der Wert als manual_value katalogisiert.",
        ),
        f"{sheet}!AM23": _rule_template("character.lifeforce_current", sheet, "AM23", "LifeForce Current", "Charakter / Ressourcen", "manual_value", "Aktueller Lebensenergie-Wert."),
        f"{sheet}!AO23": _rule_template(
            "character.lifeforce_max", sheet, "AO23", "LifeForce Max", "Charakter / Ressourcen",
            "expression" if lf_expr else "manual_value", "Maximaler Lebensenergie-Wert.", lf_expr,
            notes="LifeForce Max ggf. durch Spezies/Perks beeinflusst. Exakte Regel prüfen.",
        ),
        f"{sheet}!AM27": _rule_template("character.sanity_current", sheet, "AM27", "Sanity Current", "Charakter / Ressourcen", "manual_value", "Aktueller Sanity-Wert."),
        f"{sheet}!AO27": _rule_template(
            "character.sanity_max", sheet, "AO27", "Sanity Max", "Charakter / Ressourcen",
            "expression" if sanity_expr else "manual_value", "Maximaler Sanity-Wert.", sanity_expr,
        ),
        f"{sheet}!AM31": _rule_template(
            "character.faith_current", sheet, "AM31", "Faith Current", "Charakter / Ressourcen",
            "manual_value", "Aktueller Faith-Wert.",
            notes="Faith Current und Faith Max nutzen aktuell dieselbe Zielzelle AM31.",
        ),
        f"{sheet}!AG4": _rule_template("character.body", sheet, "AG4", "Körper", "Charakter / Attribute", "expression", "Körper wird aus den darunterliegenden Körper-Attributen berechnet.", body_expr, ["Charakterbogen!AG7", "Charakterbogen!AG9", "Charakterbogen!AG11", "Charakterbogen!AG13"]),
        f"{sheet}!AR4": _rule_template("character.mind", sheet, "AR4", "Geist", "Charakter / Attribute", "expression", "Geist wird aus den darunterliegenden Geist-Attributen berechnet.", mind_expr, ["Charakterbogen!AR7", "Charakterbogen!AR9", "Charakterbogen!AR11", "Charakterbogen!AR13"]),
        f"{sheet}!AG7": _rule_template("character.kraft", sheet, "AG7", "Kraft", "Charakter / Attribute", "manual_value", "Attributwert Kraft."),
        f"{sheet}!AG9": _rule_template("character.geschick", sheet, "AG9", "Geschick", "Charakter / Attribute", "manual_value", "Attributwert Geschick."),
        f"{sheet}!AG11": _rule_template("character.zaehigkeit", sheet, "AG11", "Zähigkeit", "Charakter / Attribute", "manual_value", "Attributwert Zähigkeit."),
        f"{sheet}!AG13": _rule_template("character.reflex", sheet, "AG13", "Reflex", "Charakter / Attribute", "manual_value", "Attributwert Reflex."),
        f"{sheet}!AR7": _rule_template("character.intelligenz", sheet, "AR7", "Intelligenz", "Charakter / Attribute", "manual_value", "Attributwert Intelligenz."),
        f"{sheet}!AR9": _rule_template("character.willenskraft", sheet, "AR9", "Willenskraft", "Charakter / Attribute", "manual_value", "Attributwert Willenskraft."),
        f"{sheet}!AR11": _rule_template("character.charisma", sheet, "AR11", "Charisma", "Charakter / Attribute", "manual_value", "Attributwert Charisma."),
        f"{sheet}!AR13": _rule_template("character.sinne", sheet, "AR13", "Sinne", "Charakter / Attribute", "manual_value", "Attributwert Sinne."),
    }

    changed = False
    for key, default in defaults.items():
        current = rules.get(key)
        if not isinstance(current, dict):
            rules[key] = default
            changed = True
            continue
        for stable_field in ("target", "id", "display_name", "category", "rule_type", "enabled", "apply_to_cache", "sources", "possible_sources"):
            if stable_field not in current or current.get(stable_field) in (None, "", []):
                current[stable_field] = default.get(stable_field)
                changed = True
        # expression only backfill when empty
        if (not str(current.get("expression", "")).strip()) and str(default.get("expression", "")).strip():
            current["expression"] = default.get("expression", "")
            changed = True
        if not str(current.get("description", "")).strip():
            current["description"] = default.get("description", "")
            changed = True
        if not str(current.get("notes", "")).strip() and str(default.get("notes", "")).strip():
            current["notes"] = default.get("notes", "")
            changed = True
    payload["rules"] = rules
    return payload, changed


class CalculationCenterDialog(QDialog):
    def __init__(self, parent, loader, parser):
        super().__init__(parent)
        self.loader = loader
        self.parser = parser
        self.items: list[dict[str, Any]] = []
        self.item_by_id: dict[str, dict[str, Any]] = {}
        self.override_store = load_calculation_overrides()
        self.rule_store = load_calculation_rules()
        self.current_target_key = ""
        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        self.setWindowTitle("Berechnungszentrum")
        self.resize(1200, 800)
        root_layout = QVBoxLayout(self)
        top_row = QHBoxLayout()
        search_label = QLabel("Suche:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Label, Sheet, Zelle, Formel, Fehler, Override...")
        self.search_edit.textChanged.connect(self.populate_tree)
        self.errors_only_check = QCheckBox("Nur Fehler")
        self.errors_only_check.toggled.connect(self.populate_tree)
        self.missing_only_check = QCheckBox("Nur fehlende Berechnungen")
        self.missing_only_check.toggled.connect(self.populate_tree)
        self.overrides_only_check = QCheckBox("Nur Overrides")
        self.overrides_only_check.toggled.connect(self.populate_tree)
        self.rules_only_check = QCheckBox("Nur Rules")
        self.rules_only_check.toggled.connect(self.populate_tree)
        top_row.addWidget(search_label)
        top_row.addWidget(self.search_edit, 1)
        top_row.addWidget(self.errors_only_check)
        top_row.addWidget(self.missing_only_check)
        top_row.addWidget(self.overrides_only_check)
        top_row.addWidget(self.rules_only_check)
        root_layout.addLayout(top_row)

        split = QSplitter(Qt.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Berechnungen"])
        self.tree.currentItemChanged.connect(self.on_tree_selection_changed)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_split = QSplitter(Qt.Vertical)

        self.detail_view = QTextBrowser()
        self.detail_view.setReadOnly(True)
        right_split.addWidget(self.detail_view)

        self.override_panel = QWidget()
        self.override_panel.setStyleSheet("background-color: rgba(40, 40, 40, 80);")
        override_layout = QVBoxLayout(self.override_panel)
        override_layout.addWidget(QLabel("Override"))
        self.override_hint = QLabel("Kein Berechnungsziel ausgewählt")
        self.override_hint.setWordWrap(True)
        override_layout.addWidget(self.override_hint)
        form = QFormLayout()
        self.override_display_name_edit = QLineEdit()
        self.override_category_edit = QLineEdit()
        self.override_description_edit = QTextEdit()
        self.override_rule_type_combo = QComboBox()
        self.override_rule_type_combo.addItems(RULE_TYPES)
        self.override_formula_edit = QTextEdit()
        self.override_enabled_check = QCheckBox("Aktiviert")
        self.override_notes_edit = QTextEdit()
        form.addRow("Anzeigename", self.override_display_name_edit)
        form.addRow("Kategorie", self.override_category_edit)
        form.addRow("Beschreibung", self.override_description_edit)
        form.addRow("Regeltyp", self.override_rule_type_combo)
        form.addRow("Override-Formel", self.override_formula_edit)
        form.addRow("Aktiviert", self.override_enabled_check)
        form.addRow("Notizen", self.override_notes_edit)
        override_layout.addLayout(form)
        self.override_info_label = QLabel(
            "Override ist gespeichert. Automatische Anwendung ist derzeit deaktiviert."
        )
        self.override_info_label.setWordWrap(True)
        self.override_info_label.setStyleSheet("color: #d18a26;")
        override_layout.addWidget(self.override_info_label)
        row = QHBoxLayout()
        self.override_save_button = QPushButton("Override speichern")
        self.override_delete_button = QPushButton("Override löschen")
        self.override_save_button.clicked.connect(self.save_override_from_panel)
        self.override_delete_button.clicked.connect(self.delete_override_from_panel)
        row.addWidget(self.override_save_button)
        row.addWidget(self.override_delete_button)
        override_layout.addLayout(row)
        self.override_status_label = QLabel("")
        override_layout.addWidget(self.override_status_label)
        right_split.addWidget(self.override_panel)
        right_split.setSizes([430, 350])

        right_layout.addWidget(right_split)
        self._set_override_editor_enabled(False, "Kein Berechnungsziel ausgewählt")

        split.addWidget(self.tree)
        split.addWidget(right_panel)
        split.setSizes([380, 800])
        root_layout.addWidget(split, 1)

        bottom_row = QHBoxLayout()
        self.status_label = QLabel("0 Einträge")
        self.override_button = QPushButton("Override speichern")
        self.override_button.setEnabled(False)
        self.override_button.clicked.connect(self.save_override_from_panel)
        self.refresh_button = QPushButton("Aktualisieren")
        self.refresh_button.clicked.connect(self.refresh_data)
        self.close_button = QPushButton("Schließen")
        self.close_button.clicked.connect(self.close)
        bottom_row.addWidget(self.status_label, 1)
        bottom_row.addWidget(self.override_button)
        bottom_row.addWidget(self.refresh_button)
        bottom_row.addWidget(self.close_button)
        root_layout.addLayout(bottom_row)

    def refresh_data(self):
        self.override_store = load_calculation_overrides()
        self.rule_store = load_calculation_rules()
        safe_store, changed = _ensure_default_character_rules(
            self.rule_store,
            self.loader.cell_cache if isinstance(self.loader.cell_cache, dict) else {},
        )
        self.rule_store = safe_store
        if changed:
            save_calculation_rules(self.rule_store)
        self.items = collect_calculation_entries(
            self.loader, self.parser, self.override_store, self.rule_store
        )
        self.item_by_id = {entry["id"]: entry for entry in self.items}
        self.populate_tree()

    def _set_override_editor_enabled(self, enabled: bool, hint: str = ""):
        widgets = [
            self.override_display_name_edit,
            self.override_category_edit,
            self.override_description_edit,
            self.override_rule_type_combo,
            self.override_formula_edit,
            self.override_enabled_check,
            self.override_notes_edit,
            self.override_save_button,
            self.override_delete_button,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)
        if hasattr(self, "override_button") and self.override_button is not None:
            self.override_button.setEnabled(enabled)
        self.override_hint.setText(hint)

    def _load_override_into_panel(self, entry: dict[str, Any]):
        target_key = str(entry.get("target_key", "")).strip()
        self.current_target_key = target_key
        if not target_key:
            self._set_override_editor_enabled(False, "Für diesen Eintrag kann kein Override gespeichert werden")
            return
        existing = entry.get("override") if isinstance(entry.get("override"), dict) else {}
        sheet = str(entry.get("sheet", "")).strip()
        cell = str(entry.get("cell", "")).strip()
        data = _default_override_entry(sheet, cell)
        if isinstance(existing, dict):
            data.update({k: v for k, v in existing.items() if k in data})
        if not str(data.get("display_name", "")).strip():
            data["display_name"] = str(entry.get("label", "")).strip()
        if not str(data.get("category", "")).strip():
            data["category"] = str(entry.get("category", "")).strip()
        self.override_display_name_edit.setText(str(data.get("display_name", "")))
        self.override_category_edit.setText(str(data.get("category", "")))
        self.override_description_edit.setPlainText(str(data.get("description", "")))
        rule_type = str(data.get("rule_type", "note_only"))
        idx = self.override_rule_type_combo.findText(rule_type)
        self.override_rule_type_combo.setCurrentIndex(idx if idx >= 0 else self.override_rule_type_combo.findText("note_only"))
        self.override_formula_edit.setPlainText(str(data.get("formula", "")))
        self.override_enabled_check.setChecked(bool(data.get("enabled", False)))
        self.override_notes_edit.setPlainText(str(data.get("notes", "")))
        self.override_status_label.setText("")
        if bool(data.get("enabled", False)):
            self.override_info_label.setText("Override ist aktiv markiert. Automatische Anwendung ist derzeit deaktiviert.")
        else:
            self.override_info_label.setText("Override ist gespeichert. Automatische Anwendung ist derzeit deaktiviert.")
        self._set_override_editor_enabled(True, f"Ziel: {target_key}")

    def save_override_from_panel(self):
        target_key = self.current_target_key.strip()
        if not target_key:
            return
        sheet, cell = _split_target_key(target_key)
        payload = self.override_store if isinstance(self.override_store, dict) else dict(OVERRIDE_DEFAULT)
        overrides = payload.get("overrides")
        if not isinstance(overrides, dict):
            overrides = {}
            payload["overrides"] = overrides
        overrides[target_key] = {
            "target": {"sheet": sheet, "cell": cell},
            "display_name": self.override_display_name_edit.text().strip(),
            "category": self.override_category_edit.text().strip(),
            "description": self.override_description_edit.toPlainText().strip(),
            "rule_type": self.override_rule_type_combo.currentText().strip() or "note_only",
            "formula": self.override_formula_edit.toPlainText().strip(),
            "enabled": self.override_enabled_check.isChecked(),
            "notes": self.override_notes_edit.toPlainText().strip(),
        }
        if save_calculation_overrides(payload):
            log_debug("calculation", f"override save target={target_key}")
            self.override_status_label.setText("Override gespeichert")
            self.refresh_data()

    def delete_override_from_panel(self):
        target_key = self.current_target_key.strip()
        if not target_key:
            return
        payload = self.override_store if isinstance(self.override_store, dict) else dict(OVERRIDE_DEFAULT)
        overrides = payload.get("overrides")
        if not isinstance(overrides, dict) or target_key not in overrides:
            self.override_status_label.setText("Kein Override vorhanden")
            return
        sheet, cell = _split_target_key(target_key)
        msg = f"Override für {sheet}!{cell} löschen?"
        res = QMessageBox.question(self, "Override löschen", msg, QMessageBox.Yes | QMessageBox.No)
        if res != QMessageBox.Yes:
            return
        overrides.pop(target_key, None)
        if save_calculation_overrides(payload):
            self.override_status_label.setText("Override gelöscht")
            self.refresh_data()

    def populate_tree(self):
        query = self.search_edit.text().strip().lower()
        errors_only = self.errors_only_check.isChecked()
        missing_only = self.missing_only_check.isChecked()
        overrides_only = self.overrides_only_check.isChecked()
        rules_only = self.rules_only_check.isChecked()

        self.tree.clear()
        grouped: dict[str, dict[str, list[dict[str, Any]]]] = {}
        error_overview: dict[str, list[dict[str, Any]]] = {
            "Unsupported": [],
            "Missing Reference": [],
            "Missing Formula": [],
            "Sonstige Fehler": [],
        }
        visible_count = 0
        for entry in self.items:
            status = str(entry.get("status", "manual"))
            formula = entry.get("formula")
            is_formula_missing = (not isinstance(formula, str) or not formula.startswith("="))
            has_override = bool(entry.get("override"))
            has_rule = bool(entry.get("rule"))
            if errors_only and status not in {"error", "warning", "missing_formula", "missing_rule"}:
                continue
            if missing_only and not (
                (status in {"missing_formula", "manual"} and is_formula_missing)
                or status == "missing_rule"
            ):
                continue
            if overrides_only and not has_override:
                continue
            if rules_only and not has_rule:
                continue

            override = entry.get("override") if isinstance(entry.get("override"), dict) else {}
            rule = entry.get("rule") if isinstance(entry.get("rule"), dict) else {}
            haystack = " ".join(
                [
                    str(entry.get("label", "")),
                    str(entry.get("sheet", "")),
                    str(entry.get("cell", "")),
                    str(entry.get("formula", "")),
                    str(entry.get("category", "")),
                    str(entry.get("error", "")),
                    str(entry.get("error_kind", "")),
                    str(override.get("display_name", "")),
                    str(override.get("category", "")),
                    str(override.get("description", "")),
                    str(override.get("formula", "")),
                    str(override.get("notes", "")),
                    str(rule.get("id", "")),
                    str(rule.get("display_name", "")),
                    str(rule.get("category", "")),
                    str(rule.get("description", "")),
                    str(rule.get("expression", "")),
                    str(rule.get("notes", "")),
                ]
            ).lower()
            if query and query not in haystack:
                continue

            group = str(entry.get("group", "Sonstige Sheet-Formeln"))
            category = str(entry.get("category", "Allgemein"))
            grouped.setdefault(group, {}).setdefault(category, []).append(entry)
            visible_count += 1
            if status in {"error", "warning", "missing_formula", "manual", "missing_rule"}:
                kind = str(entry.get("error_kind", "")).lower()
                if kind == "unsupported":
                    error_overview["Unsupported"].append(entry)
                elif kind in {"missing_reference", "empty_source"}:
                    error_overview["Missing Reference"].append(entry)
                elif kind in {"missing_formula", "manual", "missing_rule"}:
                    error_overview["Missing Formula"].append(entry)
                else:
                    error_overview["Sonstige Fehler"].append(entry)

        if any(error_overview.values()):
            top = QTreeWidgetItem(["Fehlerübersicht"])
            self.tree.addTopLevelItem(top)
            for bucket, bucket_entries in error_overview.items():
                if not bucket_entries:
                    continue
                bucket_item = QTreeWidgetItem([bucket])
                top.addChild(bucket_item)
                for entry in _sorted_entries(bucket_entries):
                    leaf = QTreeWidgetItem([_entry_tree_label(entry)])
                    leaf.setData(0, Qt.UserRole, entry["id"])
                    bucket_item.addChild(leaf)
            top.setExpanded(True)

        for group_name in GROUP_ORDER:
            if group_name == "Fehlerübersicht":
                continue
            categories = grouped.get(group_name)
            if not categories:
                continue
            group_item = QTreeWidgetItem([group_name])
            self.tree.addTopLevelItem(group_item)
            for category_name in sorted(categories.keys()):
                cat_item = QTreeWidgetItem([category_name])
                group_item.addChild(cat_item)
                for entry in _sorted_entries(categories[category_name]):
                    leaf = QTreeWidgetItem([_entry_tree_label(entry)])
                    leaf.setData(0, Qt.UserRole, entry["id"])
                    status = str(entry.get("status", "manual"))
                    if status == "ok":
                        leaf.setForeground(0, Qt.green)
                    elif status in {"missing_formula", "missing_rule"}:
                        leaf.setForeground(0, Qt.darkYellow)
                    elif status == "error":
                        leaf.setForeground(0, Qt.red)
                    cat_item.addChild(leaf)
            group_item.setExpanded(True)

        self.status_label.setText(f"{visible_count} Einträge sichtbar")
        if self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def on_tree_selection_changed(self, current: QTreeWidgetItem | None, _previous):
        entry = None
        if current is not None:
            item_id = current.data(0, Qt.UserRole)
            if item_id:
                entry = self.item_by_id.get(str(item_id))
        if not isinstance(entry, dict):
            self.detail_view.setPlainText("Kategorie ausgewählt.")
            self.current_target_key = ""
            self._set_override_editor_enabled(False, "Kein Berechnungsziel ausgewählt")
            return
        self.detail_view.setPlainText(format_entry_detail(entry))
        self._load_override_into_panel(entry)


GROUP_ORDER = [
    "Fehlerübersicht",
    "Verwaiste Overrides",
    "Charakter",
    "Attribute",
    "Wohlbefinden",
    "Paradigmen",
    "Fertigkeiten",
    "SE / Skill Upgrade",
    "Inventar",
    "Geldbeutel",
    "Ausrüstung / Rüstung",
    "Ausrüstung / Waffen",
    "Magie",
    "Sonstige Sheet-Formeln",
    "Fehler / Fehlende Berechnungen",
]

IMPORTANT_TARGETS = [
    ("hp current", "hp aktuell"),
    ("hp max", "hp max"),
    ("mp current", "mp aktuell"),
    ("mp max", "mp max"),
    ("xp current", "xp aktuell"),
    ("xp max", "xp max"),
    ("lifeforce current", "lifeforce aktuell"),
    ("lifeforce max", "lifeforce max"),
    ("sanity current", "sanity aktuell"),
    ("sanity max", "sanity max"),
    ("faith current", "faith aktuell"),
    ("faith max", "faith max"),
    ("körper", "körper"),
    ("geist", "geist"),
    ("kraft", "kraft"),
    ("geschick", "geschick"),
    ("zähigkeit", "zähigkeit"),
    ("reflex", "reflex"),
    ("intelligenz", "intelligenz"),
    ("willenskraft", "willenskraft"),
    ("charisma", "charisma"),
    ("sinne", "sinne"),
]


def collect_calculation_entries(
    loader, parser, override_store: dict[str, Any], rule_store: dict[str, Any]
) -> list[dict[str, Any]]:
    cell_cache = loader.cell_cache if isinstance(loader.cell_cache, dict) else {}
    entries: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    overrides = override_store.get("overrides", {}) if isinstance(override_store, dict) else {}
    rules = rule_store.get("rules", {}) if isinstance(rule_store, dict) else {}
    if not isinstance(overrides, dict):
        overrides = {}
    if not isinstance(rules, dict):
        rules = {}

    try:
        ui_targets = _load_ui_targets_for_missing_rules()
    except Exception as exc:
        log_warning("calculation", f"ui targets for missing rules unavailable: {exc}")
        ui_targets = {}
    faith_cell = ui_targets.get("faith_current")
    faith_same_cell = bool(
        faith_cell and faith_cell == ui_targets.get("faith_max")
    )

    for sheet_name, sheet_cells in cell_cache.items():
        if not isinstance(sheet_cells, dict):
            continue
        for cell_ref, raw in sheet_cells.items():
            if not isinstance(raw, dict):
                continue
            formula = raw.get("formula")
            value = raw.get("value")
            computed_value = raw.get("computed_value")
            has_formula = isinstance(formula, str) and formula.startswith("=")
            has_computed = computed_value is not None
            if not has_formula and not has_computed:
                continue

            trace = parser.trace_formula(sheet_name, cell_ref, cell_cache) if has_formula else None
            status, error = "ok", None
            if isinstance(raw.get("error"), str) and raw.get("error"):
                status, error = "error", raw.get("error")
            if isinstance(trace, dict) and trace.get("error"):
                status, error = "error", trace.get("error")

            references = raw.get("references") if isinstance(raw.get("references"), list) else parser.extract_references(formula) if has_formula else []
            sources = []
            for ref in references:
                ref_cell = str(ref).replace("$", "").upper()
                sources.append({"sheet": sheet_name, "cell": ref_cell, "value": _read_cell_value(cell_cache, sheet_name, ref_cell)})
            if isinstance(trace, dict):
                for src in trace.get("sources", []):
                    src_sheet = str(src.get("sheet", sheet_name))
                    src_cell = str(src.get("cell", "")).replace("$", "").upper()
                    if src_cell and not any(s["sheet"] == src_sheet and s["cell"] == src_cell for s in sources):
                        sources.append({"sheet": src_sheet, "cell": src_cell, "value": _read_cell_value(cell_cache, src_sheet, src_cell)})

            label = _guess_label(sheet_cells, cell_ref)
            group, category = _categorize(sheet_name, label, cell_ref)
            target_key = f"{sheet_name}!{cell_ref}"
            override = overrides.get(target_key) if isinstance(overrides.get(target_key), dict) else None
            rule = rules.get(target_key) if isinstance(rules.get(target_key), dict) else None
            if rule and str(rule.get("category", "")).strip():
                group, category = _override_category_to_group(str(rule.get("category", "")).strip())
            elif override and str(override.get("category", "")).strip():
                group, category = _override_category_to_group(str(override.get("category", "")).strip())

            display_label = label
            if rule and str(rule.get("display_name", "")).strip():
                display_label = f"{str(rule.get('display_name')).strip()} — {cell_ref}"
            elif override:
                display_label = _override_display_label(label, cell_ref, override)

            rule_eval = _evaluate_rule(rule, sheet_name, parser, cell_cache) if rule else None
            status = _status_with_rule(status, rule, rule_eval)
            warning_messages = []
            if rule and rule.get("id") in {"character.faith_current", "character.faith_max"} and faith_same_cell:
                warning_messages.append("Current und Max nutzen dieselbe Zielzelle.")
                if status == "ok":
                    status = "warning"

            entry = {
                "id": target_key,
                "target_key": target_key,
                "sheet": sheet_name,
                "cell": cell_ref,
                "label": display_label,
                "group": group,
                "category": category,
                "formula": formula,
                "normalized": trace.get("normalized") if isinstance(trace, dict) else None,
                "value": trace.get("value") if isinstance(trace, dict) and trace.get("error") is None else (value if value is not None else computed_value),
                "sources": sources,
                "steps": trace.get("steps") if isinstance(trace, dict) else [],
                "status": status,
                "error": error,
                "error_kind": _classify_error_kind(error, has_formula, sources, value),
                "override": override,
                "rule": rule,
                "rule_eval": rule_eval,
                "warnings": warning_messages,
            }
            entries.append(entry)
            used_keys.add(target_key)

    entries.extend(_collect_manual_targets(cell_cache, used_keys, overrides, rules))
    entries.extend(_collect_missing_rule_targets(cell_cache, used_keys, rules, ui_targets))
    entries.extend(_collect_orphan_overrides(used_keys, overrides))
    entries.sort(key=lambda x: (GROUP_ORDER.index(x.get("group")) if x.get("group") in GROUP_ORDER else 999, str(x.get("sheet", "")), _cell_sort_key(str(x.get("cell", ""))), str(x.get("label", ""))))
    return entries


def _collect_manual_targets(
    cell_cache: dict[str, Any], used_keys: set[str], overrides: dict[str, Any], rules: dict[str, Any]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sheet_name, sheet_cells in cell_cache.items():
        if not isinstance(sheet_cells, dict):
            continue
        labels_by_cell = {cell_ref.upper(): str(cell_data.get("value", "")).strip().lower() for cell_ref, cell_data in sheet_cells.items() if isinstance(cell_data, dict) and isinstance(cell_data.get("value"), str)}
        for cell_ref, label_text in labels_by_cell.items():
            for _, target_label in IMPORTANT_TARGETS:
                if target_label not in label_text:
                    continue
                target_cell = _find_target_value_cell(sheet_cells, cell_ref)
                if not target_cell:
                    continue
                target_key = f"{sheet_name}!{target_cell}"
                if target_key in used_keys:
                    continue
                value = _read_cell_value(cell_cache, sheet_name, target_cell)
                override = overrides.get(target_key) if isinstance(overrides.get(target_key), dict) else None
                rule = rules.get(target_key) if isinstance(rules.get(target_key), dict) else None
                group, category = _categorize(sheet_name, target_label, target_cell)
                if rule and str(rule.get("category", "")).strip():
                    group, category = _override_category_to_group(str(rule.get("category", "")).strip())
                elif override and str(override.get("category", "")).strip():
                    group, category = _override_category_to_group(str(override.get("category", "")).strip())
                status = "missing_formula" if value is not None else "manual"
                if rule:
                    status = "ok" if bool(rule.get("enabled", True)) else "warning"
                out.append(
                    {
                        "id": f"{target_key}:manual",
                        "target_key": target_key,
                        "sheet": sheet_name,
                        "cell": target_cell,
                        "label": _override_display_label(target_label, target_cell, override),
                        "group": "Fehler / Fehlende Berechnungen" if value is not None else group,
                        "category": category,
                        "formula": None,
                        "normalized": None,
                        "value": value,
                        "sources": [],
                        "steps": ["Keine Zwischenschritte verfügbar"],
                        "status": status,
                        "error": None,
                        "error_kind": status,
                        "override": override,
                        "rule": rule,
                        "rule_eval": _evaluate_rule(rule, sheet_name, None, cell_cache) if rule else None,
                        "warnings": [],
                    }
                )
                used_keys.add(target_key)
    return out


def _collect_orphan_overrides(used_keys: set[str], overrides: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key, override in overrides.items():
        if not isinstance(override, dict):
            continue
        if key in used_keys:
            continue
        sheet, cell = _split_target_key(key)
        out.append(
            {
                "id": f"{key}:orphan",
                "target_key": key,
                "sheet": sheet,
                "cell": cell,
                "label": _override_display_label(cell or key, cell or key, override),
                "group": "Verwaiste Overrides",
                "category": "Nicht im aktiven Charakter gefunden",
                "formula": None,
                "normalized": None,
                "value": None,
                "sources": [],
                "steps": ["Override existiert, aber Ziel wurde im aktuellen Charakter nicht gefunden."],
                "status": "warning",
                "error": "orphan_override",
                "error_kind": "missing_reference",
                "override": override,
            }
        )
    return out


def _collect_missing_rule_targets(
    cell_cache: dict[str, Any], used_keys: set[str], rules: dict[str, Any], ui_targets: dict[str, str]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sheet = "Charakterbogen"
    for field_id, cell in ui_targets.items():
        target_key = f"{sheet}!{cell}"
        if target_key in used_keys:
            continue
        if isinstance(rules.get(target_key), dict):
            continue
        value = _read_cell_value(cell_cache, sheet, cell)
        out.append(
            {
                "id": f"{target_key}:missing_rule",
                "target_key": target_key,
                "sheet": sheet,
                "cell": cell,
                "label": f"{_humanize_field_id(field_id)} — {cell}",
                "group": "Fehler / Fehlende Berechnungen",
                "category": "Missing Rules",
                "formula": None,
                "normalized": None,
                "value": value,
                "sources": [],
                "steps": ["Keine Calculation Rule definiert."],
                "status": "missing_rule",
                "error": f"{_humanize_field_id(field_id)} hat keine Calculation Rule.",
                "error_kind": "missing_rule",
                "override": None,
                "rule": None,
                "rule_eval": None,
                "warnings": [],
            }
        )
    return out


def _load_ui_targets_for_missing_rules() -> dict[str, str]:
    path = resource_path("assets/themes/diablo/ui_layout.json")
    targets: dict[str, str] = {}
    if not path.exists():
        log_warning("calculation", f"missing ui layout for rule targets: {path}")
        return targets
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data_map = data.get("character_screen", {}).get("data_map", {})
        basic = data_map.get("basic", {})
        for key, cell in basic.items():
            if isinstance(cell, str) and _is_cell_ref(cell):
                targets[key] = cell
        attrs = data_map.get("attributes", {})
        for attr_id, attr_data in attrs.items():
            if isinstance(attr_data, dict):
                value_cell = attr_data.get("value")
                if isinstance(value_cell, str) and _is_cell_ref(value_cell):
                    targets[attr_id] = value_cell
                items = attr_data.get("items", [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            item_id = str(item.get("id", ""))
                            item_cell = item.get("value")
                            if item_id and isinstance(item_cell, str) and _is_cell_ref(item_cell):
                                targets[item_id] = item_cell
    except Exception as exc:
        log_warning("calculation", f"failed to load ui targets for missing rules: {path} ({exc})")
        return {}
    return targets


def _evaluate_rule(rule: dict[str, Any] | None, sheet_name: str, parser, cell_cache: dict[str, Any]):
    if not isinstance(rule, dict):
        return None
    rule_type = str(rule.get("rule_type", "")).strip().lower()
    expression = str(rule.get("expression", "")).strip()
    if rule_type not in {"expression", "expression_or_missing", "expression_or_manual"}:
        return None
    if not expression:
        return {"status": "warning", "error": "missing_expression"}
    if not expression.startswith("="):
        expression = "=" + expression
    if parser is None:
        return {"status": "warning", "error": "parser_unavailable"}

    def value_getter(target_sheet, target_cell):
        sheet = cell_cache.get(target_sheet, {})
        cell = sheet.get(str(target_cell).replace("$", "").upper())
        if isinstance(cell, dict):
            formula = cell.get("formula")
            if isinstance(formula, str) and formula.startswith("="):
                return formula
            return cell.get("value")
        return None

    try:
        result = parser.evaluate_formula(sheet_name, expression, value_getter)
        if result == "Nicht unterstützt":
            return {"status": "warning", "error": "unsupported"}
        target = rule.get("target", {}) if isinstance(rule.get("target"), dict) else {}
        t_sheet = str(target.get("sheet", sheet_name))
        t_cell = str(target.get("cell", ""))
        cache_value = _read_cell_value(cell_cache, t_sheet, t_cell) if t_cell else None
        diff = _calc_diff_number(cache_value, result)
        payload = {
            "status": "ok",
            "result": result,
            "expression": expression,
            "cache_value": cache_value,
            "diff": diff,
        }
        if diff is not None and abs(diff) > 1e-9:
            payload["status"] = "warning"
            payload["error"] = "diff_mismatch"
        return payload
    except Exception as exc:
        return {"status": "warning", "error": str(exc)}


def _status_with_rule(base_status: str, rule: dict[str, Any] | None, rule_eval: dict[str, Any] | None) -> str:
    if not isinstance(rule, dict):
        return base_status
    if isinstance(rule_eval, dict) and rule_eval.get("status") == "ok":
        diff = _calc_diff_number(rule_eval.get("cache_value"), rule_eval.get("result"))
        if diff is not None and abs(diff) > 1e-9:
            return "warning"
        if base_status == "error":
            return "warning"
        return "ok" if base_status == "ok" else base_status
    if base_status == "error" and isinstance(rule_eval, dict) and rule_eval.get("status") == "ok":
        return "warning"
    if base_status == "ok" and isinstance(rule_eval, dict) and rule_eval.get("status") == "warning":
        return "warning"
    return base_status


def _override_display_label(default_label: str, cell_ref: str, override: dict[str, Any] | None) -> str:
    if isinstance(override, dict):
        display_name = str(override.get("display_name", "")).strip()
        if display_name:
            return f"{display_name} — {cell_ref}"
    return default_label


def _override_category_to_group(category_text: str) -> tuple[str, str]:
    parts = [p.strip() for p in category_text.split("/") if p.strip()]
    if not parts:
        return "Sonstige Sheet-Formeln", "Allgemein"
    group = parts[0]
    category = " / ".join(parts[1:]) if len(parts) > 1 else parts[0]
    known = set(GROUP_ORDER)
    if group not in known:
        return "Sonstige Sheet-Formeln", category_text
    return group, category


def _entry_tree_label(entry: dict[str, Any]) -> str:
    status = str(entry.get("status", "manual"))
    override = entry.get("override") if isinstance(entry.get("override"), dict) else None
    rule = entry.get("rule") if isinstance(entry.get("rule"), dict) else None
    base = f"{entry.get('label', entry.get('cell', 'Unbenannt'))} [{status}]"
    tags = ""
    if rule:
        tags += "[rule]"
    if override:
        enabled = bool(override.get("enabled", False))
        tags += "[override aktiv]" if enabled else "[override]"
    return f"{base} {tags}".rstrip()


def format_entry_detail(entry: dict[str, Any]) -> str:
    lines = []
    lines.append(f"Name: {entry.get('label', '-')}")
    lines.append(f"Status: {entry.get('status', '-')}")
    lines.append(f"Ziel: {entry.get('sheet', '?')}!{entry.get('cell', '?')}")
    lines.append(f"Aktueller Wert: {entry.get('value', '-')}")
    lines.append("")
    lines.append("Formelbereich:")
    formula = entry.get("formula")
    if isinstance(formula, str) and formula.strip():
        lines.append(f"- Original: {formula}")
        lines.append(f"- Normalisiert: {entry.get('normalized', '-')}")
    else:
        lines.append("- Keine Formel vorhanden / manuell")
    lines.append("- Override-Regel: gespeichert, automatische Anwendung ist derzeit deaktiviert")
    lines.append("")
    lines.append("Calculation Rule:")
    rule = entry.get("rule") if isinstance(entry.get("rule"), dict) else None
    if rule:
        lines.append(f"- ID: {rule.get('id', '')}")
        lines.append(f"- Anzeigename: {rule.get('display_name', '')}")
        lines.append(f"- Kategorie: {rule.get('category', '')}")
        lines.append(f"- Beschreibung: {rule.get('description', '')}")
        lines.append(f"- Regeltyp: {rule.get('rule_type', '')}")
        lines.append(f"- Expression: {rule.get('expression', '')}")
        lines.append(f"- Aktiviert: {'Ja' if bool(rule.get('enabled', True)) else 'Nein'}")
        lines.append(f"- Apply to Cache: {'Ja' if bool(rule.get('apply_to_cache', False)) else 'Nein'}")
        rule_sources = rule.get("sources", [])
        if isinstance(rule_sources, list):
            source_text = _format_rule_source_list(rule_sources, entry)
            lines.append(f"- Quellen: {source_text if source_text else '-'}")
        else:
            lines.append("- Quellen: -")
        possible_sources = rule.get("possible_sources", [])
        if isinstance(possible_sources, list) and possible_sources:
            lines.append(f"- Possible Sources: {_format_rule_source_list(possible_sources, entry)}")
        lines.append(f"- Notizen: {rule.get('notes', '')}")
        rule_eval = entry.get("rule_eval") if isinstance(entry.get("rule_eval"), dict) else None
        if rule_eval:
            lines.append(f"- Rule Ergebnis: {rule_eval.get('result', '-')}")
            lines.append(f"- Original Cache Wert: {rule_eval.get('cache_value', entry.get('value', '-'))}")
            diff_text = _calc_diff_text(rule_eval.get("cache_value"), rule_eval.get("result"))
            if diff_text != "":
                lines.append(f"- Differenz: {diff_text}")
            if rule_eval.get("status") == "warning":
                lines.append(f"- Rule Warnung: {rule_eval.get('error', 'unbekannt')}")
    else:
        lines.append("- Keine Calculation Rule definiert")
    lines.append("")
    lines.append("Override:")
    override = entry.get("override") if isinstance(entry.get("override"), dict) else None
    if override:
        lines.append(f"- Display Name: {override.get('display_name', '')}")
        lines.append(f"- Kategorie: {override.get('category', '')}")
        lines.append(f"- Beschreibung: {override.get('description', '')}")
        lines.append(f"- Regeltyp: {override.get('rule_type', 'note_only')}")
        lines.append(f"- Formel: {override.get('formula', '')}")
        enabled = bool(override.get("enabled", False))
        lines.append(f"- Aktiv: {'Ja' if enabled else 'Nein'}")
        lines.append(f"- Notizen: {override.get('notes', '')}")
        lines.append("- Hinweis: Override ist gespeichert. Automatische Anwendung ist derzeit deaktiviert.")
    else:
        lines.append("- Kein Override definiert")
    lines.append("")
    lines.append("Quellen:")
    sources = entry.get("sources") or []
    if sources:
        for src in sources:
            lines.append(f"- {src.get('sheet', '?')}!{src.get('cell', '?')} = {src.get('value', '-')}")
    else:
        lines.append("- Keine Quellen verfügbar")
    lines.append("")
    lines.append("Zwischenschritte:")
    steps = entry.get("steps") or []
    if steps:
        for step in steps:
            lines.append(f"- {step}")
    else:
        lines.append("- Keine Zwischenschritte verfügbar")
    lines.append("")
    lines.append("Fehler:")
    error_kind = str(entry.get("error_kind") or "none")
    error_code = str(entry.get("error") or "").strip()
    if error_kind == "none" or not error_code:
        lines.append("- Fehler: Keine")
    else:
        lines.append(f"- Fehlerart: {error_kind}")
        lines.append(f"- Fehlercode: {error_code}")
    if entry.get("status") in {"error", "missing_formula", "manual", "warning"}:
        lines.append(f"- Betroffene Formel: {entry.get('formula') or 'Keine Formel vorhanden'}")
        lines.append(f"- Betroffene Quelle: {_guess_problem_source(entry)}")
        lines.append(f"- Mögliche Ursache: {_build_error_cause_text(entry)}")
    warnings = entry.get("warnings") if isinstance(entry.get("warnings"), list) else []
    rule_eval = entry.get("rule_eval") if isinstance(entry.get("rule_eval"), dict) else None
    if isinstance(rule_eval, dict) and rule_eval.get("error") == "diff_mismatch":
        warnings = warnings + ["Rule weicht vom Cache-Wert ab."]
    if isinstance(rule_eval, dict) and rule_eval.get("status") == "ok" and str(entry.get("error_kind")) in {"parse_error", "unsupported"}:
        warnings = warnings + ["Originalformel meldet Fehler, Calculation Rule ist auswertbar."]
    if warnings:
        lines.append("")
        lines.append("Warnungen:")
        for warning in warnings:
            lines.append(f"- {warning}")
    return "\n".join(lines)


def _guess_problem_source(entry: dict[str, Any]) -> str:
    sources = entry.get("sources") or []
    if not sources:
        return "Keine Quelle erkannt"
    first = sources[0]
    return f"{first.get('sheet', '?')}!{first.get('cell', '?')}"


def _build_error_cause_text(entry: dict[str, Any]) -> str:
    kind = str(entry.get("error_kind") or "").lower()
    if kind == "unsupported":
        return "Diese Formel/Funktion wird vom aktuellen FormulaParser noch nicht unterstützt."
    if kind == "missing_reference":
        return "Eine referenzierte Zelle konnte nicht gefunden werden."
    if kind == "empty_source":
        return "Mindestens eine Quelle ist leer oder nicht gesetzt."
    if kind == "circular_reference":
        return "Zirkelbezug erkannt (Formel verweist direkt/indirekt auf sich selbst)."
    if kind == "parse_error":
        return "Die Formel konnte nicht sauber geparst oder ausgewertet werden."
    if kind == "missing_formula":
        return "Wert ist vorhanden, aber keine nachvollziehbare Formel/Regel wurde gefunden."
    if kind == "manual":
        return "Manueller Wert ohne Formel."
    if kind == "missing_rule":
        return "Für dieses wichtige Ziel ist keine Calculation Rule definiert."
    return "Unbekannte Ursache, Details in Fehlercode/Zwischenschritten prüfen."


def _classify_error_kind(error, has_formula: bool, sources: list[dict[str, Any]], value: Any) -> str:
    text = str(error or "").strip().lower()
    if not text:
        return "none"
    if not has_formula:
        return "missing_formula" if value is not None else "manual"
    if "cycle" in text or "circular" in text:
        return "circular_reference"
    if "missing_reference" in text or "missing_cell" in text or "missing_sheet" in text or "orphan" in text:
        return "missing_reference"
    if "empty_source" in text:
        return "empty_source"
    if "parse" in text or "syntax" in text:
        return "parse_error"
    if "missing_rule" in text:
        return "missing_rule"
    if "unsupported" in text or text == "nicht unterstützt":
        return "unsupported"
    return text


def _sorted_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda x: (str(x.get("sheet", "")), _cell_sort_key(str(x.get("cell", ""))), str(x.get("label", ""))))


def _find_target_value_cell(sheet_cells: dict[str, Any], label_cell_ref: str) -> str | None:
    row, col = _cell_to_row_col(label_cell_ref)
    if row <= 0 or col <= 0:
        return None
    for delta in (1, 2, 3):
        probe = _row_col_to_cell(row, col + delta)
        data = sheet_cells.get(probe)
        if not isinstance(data, dict):
            continue
        if data.get("value") is not None or data.get("formula"):
            return probe
    return None


def _read_cell_value(cell_cache: dict[str, Any], sheet_name: str, cell_ref: str):
    sheet = cell_cache.get(sheet_name, {})
    info = sheet.get(cell_ref)
    if isinstance(info, dict):
        return info.get("value")
    return None


def _guess_label(sheet_cells: dict[str, Any], cell_ref: str) -> str:
    row, col = _cell_to_row_col(cell_ref)
    candidates = []
    for offset in (1, 2, 3):
        left_ref = _row_col_to_cell(row, col - offset)
        cell_data = sheet_cells.get(left_ref)
        if isinstance(cell_data, dict):
            value = cell_data.get("value")
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())
    return candidates[0] if candidates else cell_ref


def _categorize(sheet_name: str, label: str, cell_ref: str):
    text = f"{sheet_name} {label} {cell_ref}".lower()
    if any(k in text for k in ["wohlbefinden", "sanity", "faith", "lifeforce"]):
        return "Wohlbefinden", "Wohlbefinden"
    if any(k in text for k in ["paradigm", "paradigmen"]):
        return "Paradigmen", "Paradigmen"
    if any(k in text for k in ["körper", "geist", "kraft", "geschick", "zähigkeit", "reflex", "intelligenz", "willenskraft", "charisma", "sinne"]):
        return "Attribute", "Attribute"
    if any(k in text for k in ["skill", "fertigkeit"]):
        return "Fertigkeiten", "Fertigkeiten"
    if any(k in text for k in ["se", "exp", "upgrade"]):
        return "SE / Skill Upgrade", "SE / Skill Upgrade"
    if any(k in text for k in ["geld", "gulden", "schilling", "heller", "money"]):
        return "Geldbeutel", "Geldbeutel"
    if any(k in text for k in ["inventar", "inventory"]):
        return "Inventar", "Inventar"
    if any(k in text for k in ["rüstung", "armor"]):
        return "Ausrüstung / Rüstung", "Ausrüstung / Rüstung"
    if any(k in text for k in ["waffe", "weapon"]):
        return "Ausrüstung / Waffen", "Ausrüstung / Waffen"
    if any(k in text for k in ["magie", "zauber", "spell"]):
        return "Magie", "Magie"
    if any(k in text for k in ["charakter", "hp", "mp", "xp"]):
        return "Charakter", "Charakter"
    return "Sonstige Sheet-Formeln", sheet_name


def _cell_sort_key(cell_ref: str):
    row, col = _cell_to_row_col(cell_ref)
    return row, col


def _cell_to_row_col(cell_ref: str):
    match = re.fullmatch(r"([A-Za-z]+)([0-9]+)", str(cell_ref).strip())
    if not match:
        return 0, 0
    letters = match.group(1).upper()
    row = int(match.group(2))
    col = 0
    for letter in letters:
        col = col * 26 + (ord(letter) - ord("A") + 1)
    return row, col


def _row_col_to_cell(row: int, col: int) -> str:
    if row <= 0 or col <= 0:
        return ""
    letters = []
    current = col
    while current > 0:
        current, rem = divmod(current - 1, 26)
        letters.append(chr(ord("A") + rem))
    return "".join(reversed(letters)) + str(row)


def _split_target_key(target_key: str) -> tuple[str, str]:
    text = str(target_key or "").strip()
    if "!" not in text:
        return "", text
    sheet, cell = text.split("!", 1)
    return sheet.strip(), cell.strip()


def _format_rule_source_list(source_list: list[Any], entry: dict[str, Any]) -> str:
    target_sheet = str(entry.get("sheet", ""))
    cache = {}
    sources_from_entry = entry.get("sources") if isinstance(entry.get("sources"), list) else []
    for src in sources_from_entry:
        if isinstance(src, dict):
            key = f"{src.get('sheet', '')}!{src.get('cell', '')}"
            cache[key] = src.get("value")
    rendered = []
    for src in source_list:
        text = str(src).strip()
        if not text:
            continue
        if "!" in text:
            sheet, cell = text.split("!", 1)
            key = f"{sheet}!{cell}"
        else:
            sheet, cell = target_sheet, text
            key = f"{sheet}!{cell}"
        value = cache.get(key, "-")
        rendered.append(f"{sheet}!{cell}={value}")
    return ", ".join(rendered)


def _calc_diff_text(original_value, rule_value) -> str:
    try:
        left = float(str(original_value).replace(",", "."))
        right = float(str(rule_value).replace(",", "."))
        diff = round(right - left, 10)
        return str(diff).rstrip("0").rstrip(".") if diff != 0 else "0"
    except Exception:
        return ""


def _calc_diff_number(original_value, rule_value):
    try:
        left = float(str(original_value).replace(",", "."))
        right = float(str(rule_value).replace(",", "."))
        return right - left
    except Exception:
        return None


def _humanize_field_id(field_id: str) -> str:
    mapping = {
        "hp_current": "HP Current",
        "hp_max": "HP Max",
        "mp_current": "MP Current",
        "mp_max": "MP Max",
        "exp_current": "XP Current",
        "exp_max": "XP Max",
        "lifeforce_current": "LifeForce Current",
        "lifeforce_max": "LifeForce Max",
        "sanity_current": "Sanity Current",
        "sanity_max": "Sanity Max",
        "faith_current": "Faith Current",
        "faith_max": "Faith Max",
        "body": "Körper",
        "mind": "Geist",
        "kraft": "Kraft",
        "geschick": "Geschick",
        "zaehigkeit": "Zähigkeit",
        "reflex": "Reflex",
        "intelligenz": "Intelligenz",
        "willenskraft": "Willenskraft",
        "charisma": "Charisma",
        "sinne": "Sinne",
    }
    return mapping.get(field_id, field_id.replace("_", " ").title())


def _is_cell_ref(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]+[0-9]+", str(value).strip()))
