import re

from app_logger import log_debug, log_warning

ARMOR_FIELDS = [
    "slot",
    "name",
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
    "attributes",
]

WEAPON_FIELDS = [
    "name",
    "weapon_type",
    "pl",
    "damage_cut",
    "damage_blunt",
    "damage_pierce",
    "physical_dice",
    "physical_bonus",
    "elemental_dice",
    "elemental_elements",
    "elemental_bonus",
    "durability_current",
    "durability_max",
    "attributes",
]


def _equipment_fields(table_type):
    return ARMOR_FIELDS if table_type == "armor" else WEAPON_FIELDS


def _empty_custom_equipment_row(table_type):
    return {field_key: "" for field_key in _equipment_fields(table_type)}


def _custom_equipment_key(table_type):
    return "armor_rows" if table_type == "armor" else "weapon_rows"


def _equipment_app_meta(window):
    if not isinstance(getattr(window.loader, "app_meta", None), dict):
        window.loader.app_meta = {}
    custom_sections = window.loader.app_meta.setdefault("custom_sections", {})
    if not isinstance(custom_sections, dict):
        custom_sections = {}
        window.loader.app_meta["custom_sections"] = custom_sections
    equipment_meta = custom_sections.setdefault("equipment", {})
    if not isinstance(equipment_meta, dict):
        equipment_meta = {}
        custom_sections["equipment"] = equipment_meta
    return equipment_meta


def _normalize_custom_equipment_rows(window, table_type):
    equipment_meta = _equipment_app_meta(window)
    row_key = _custom_equipment_key(table_type)
    rows = equipment_meta.get(row_key, [])
    if not isinstance(rows, list):
        rows = []
    normalized_rows = []
    fields = _equipment_fields(table_type)
    for row_data in rows:
        if not isinstance(row_data, dict):
            row_data = {}
        normalized_rows.append({field_key: str(row_data.get(field_key, "") or "") for field_key in fields})
    equipment_meta[row_key] = normalized_rows
    return normalized_rows


def _custom_equipment_row_for_ui(table_type, row_data, row_index):
    ui_row = {field_key: str(row_data.get(field_key, "") or "") for field_key in _equipment_fields(table_type)}
    ui_row.update(
        {
            "row": row_index,
            "row_index": row_index,
            "custom_row_index": row_index,
            "storage": "custom",
            "cells": {},
            "is_data_row": any(str(ui_row.get(field_key, "") or "").strip() for field_key in _equipment_fields(table_type)),
            "is_empty_row": not any(str(ui_row.get(field_key, "") or "").strip() for field_key in _equipment_fields(table_type)),
        }
    )
    return ui_row


def get_custom_equipment_rows(window, table_type):
    rows = _normalize_custom_equipment_rows(window, table_type)
    return [_custom_equipment_row_for_ui(table_type, row_data, index) for index, row_data in enumerate(rows)]


def ensure_custom_equipment_min_rows(window, table_type, min_rows):
    rows = _normalize_custom_equipment_rows(window, table_type)
    changed = False
    while len(rows) < max(0, int(min_rows or 0)):
        rows.append(_empty_custom_equipment_row(table_type))
        changed = True
    if changed:
        window.loader.save_active_character_json()
    return get_custom_equipment_rows(window, table_type)


def save_custom_equipment_cell(window, table_type, row_index, field_key, value):
    fields = _equipment_fields(table_type)
    if field_key not in fields:
        return False
    rows = _normalize_custom_equipment_rows(window, table_type)
    while row_index >= len(rows):
        rows.append(_empty_custom_equipment_row(table_type))
    rows[row_index][field_key] = str(value or "")
    window.loader.save_active_character_json()
    return True


def custom_equipment_row_is_empty(table_type, row_data):
    if not isinstance(row_data, dict):
        return True
    return not any(str(row_data.get(field_key, "") or "").strip() for field_key in _equipment_fields(table_type))


def grow_custom_equipment_rows_if_needed(window, table_type, row_index, min_rows=12, grow_by=3):
    rows = _normalize_custom_equipment_rows(window, table_type)
    if row_index != len(rows) - 1:
        return False
    if custom_equipment_row_is_empty(table_type, rows[row_index]):
        return False
    for _ in range(max(1, int(grow_by or 1))):
        rows.append(_empty_custom_equipment_row(table_type))
    while len(rows) < max(0, int(min_rows or 0)):
        rows.append(_empty_custom_equipment_row(table_type))
    window.loader.save_active_character_json()
    return True


def _normalize_equipment_text(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = text.replace("-", " ").replace("/", " ").replace("_", " ")
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _equipment_cache_text(sheet_cache, cell_ref):
    cell_data = sheet_cache.get(cell_ref)
    value = cell_data.get("value") if isinstance(cell_data, dict) else cell_data
    if value is None:
        return ""
    return str(value).strip()


def _equipment_cell_sort_key(window, cell_ref):
    match = re.match(r"^([A-Z]+)(\d+)$", str(cell_ref).strip().upper())
    if not match:
        return (0, 0)
    return (int(match.group(2)), window._col_letters_to_index(match.group(1)))


def get_equipment_sheet_cache(window):
    exact_candidates = {"ausrüstung", "ausruestung"}
    cache = window.loader.cell_cache
    if not isinstance(cache, dict):
        if window._equipment_print_mapping_enabled():
            log_warning("equipment", "sheet not found")
        return "", {}

    for sheet_name, sheet_cache in cache.items():
        normalized = _normalize_equipment_text(sheet_name)
        if normalized in exact_candidates and isinstance(sheet_cache, dict):
            if window._equipment_print_mapping_enabled():
                log_debug("equipment", f"sheet found: {sheet_name} cells={len(sheet_cache)}")
            return sheet_name, sheet_cache

    for sheet_name, sheet_cache in cache.items():
        normalized = _normalize_equipment_text(sheet_name)
        if "ausruestung" in normalized and isinstance(sheet_cache, dict):
            if window._equipment_print_mapping_enabled():
                log_debug("equipment", f"sheet found: {sheet_name} cells={len(sheet_cache)}")
            return sheet_name, sheet_cache

    if window._equipment_print_mapping_enabled():
        log_warning("equipment", "sheet not found")
    return "", {}


def _find_equipment_column(
    header_entries,
    header_rows,
    include_tokens,
    exclude_tokens=None,
    min_col=1,
):
    if exclude_tokens is None:
        exclude_tokens = []
    candidates = []
    for entry in header_entries:
        row = entry.get("row", 0)
        col = entry.get("col", 0)
        norm = entry.get("norm", "")
        if row not in header_rows or col < min_col:
            continue
        if not all(token in norm for token in include_tokens):
            continue
        if any(token in norm for token in exclude_tokens):
            continue
        score = len(norm)
        candidates.append((score, row, col))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][2]


def _is_equipment_header_value(value):
    normalized = _normalize_equipment_text(value)
    if not normalized:
        return False
    known_headers = {
        "wo getragen",
        "name",
        "pl",
        "kopf",
        "brust",
        "arme",
        "beine",
        "feuer",
        "wasser",
        "erde",
        "wind",
        "blitz",
        "eis",
        "saeure",
        "licht",
        "dunkel",
        "haltbarkeit",
        "attribute sonderfertigkeiten",
        "ruestung",
        "physische resistenzen",
        "elementare resistenzen",
        "summe",
    }
    return normalized in known_headers


def _is_valid_armor_data_core(slot_value, name_value, pl_value):
    slot_text = str(slot_value or "").strip()
    name_text = str(name_value or "").strip()
    pl_text = str(pl_value or "").strip()
    if name_text and _normalize_equipment_text(name_text) != "name":
        if not _is_equipment_header_value(name_text):
            return True
    if slot_text and _normalize_equipment_text(slot_text) != "wo getragen":
        if not _is_equipment_header_value(slot_text):
            return True
    if pl_text and _normalize_equipment_text(pl_text) != "pl":
        if not _is_equipment_header_value(pl_text):
            return True
    return False


def _is_valid_weapon_data_core(name_value, weapon_type_value, pl_value, physical_dice_value="", attributes_value=""):
    header_values = {
        "name",
        "waffentyp",
        "pl",
        "schnitt",
        "stoss",
        "stich",
        "wuerfel",
        "bonus",
        "elemente",
        "haltbarkeit",
        "attribute sonderfertigkeiten",
        "waffe",
        "schadensart",
        "physisch",
        "elementar",
    }
    for value in (
        name_value,
        weapon_type_value,
        pl_value,
        physical_dice_value,
        attributes_value,
    ):
        text = str(value or "").strip()
        normalized = _normalize_equipment_text(text)
        if text and normalized and normalized not in header_values:
            return True
    return False


def _equipment_row_text(row_data):
    if not isinstance(row_data, dict):
        return ""
    values = []
    for key, value in row_data.items():
        if key in {"row", "row_index", "cells", "is_data_row", "is_empty_row"}:
            continue
        text = str(value or "").strip()
        if text:
            values.append(text)
    return " ".join(values)


def _equipment_stop_reason(kind, row_data):
    text = _equipment_row_text(row_data)
    norm = _normalize_equipment_text(text)
    if not norm:
        return "", ""

    if kind == "armor":
        armor_stop_markers = {
            "waffe",
            "waffen",
            "waffentyp",
            "schnitt",
            "stoss",
            "stich",
            "schadensart",
        }
        if any(marker in norm for marker in armor_stop_markers):
            return "weapon_section_header", text
        return "", ""

    weapon_stop_markers = {
        "elementare",
        "boni",
        "affinitaet",
        "affinitaeten",
        "feuer wasser erde",
    }
    if "feuer" in norm and "wasser" in norm and "erde" in norm:
        return "unrelated_section_header", text
    if any(marker in norm for marker in weapon_stop_markers):
        return "unrelated_section_header", text
    return "", ""


def _extract_equipment_rows(
    sheet_cache,
    mapping,
    kind,
    max_rows=30,
    stop_before_row=0,
    window=None,
):
    if not isinstance(mapping, dict):
        return []
    data_start_row = int(mapping.get("data_start_row", 0) or 0)
    if data_start_row <= 0:
        return []
    columns = mapping.get("columns", {})
    if not isinstance(columns, dict):
        columns = {}
    rows = []
    effective_max_rows = max(0, int(max_rows or 0))
    if stop_before_row and stop_before_row > data_start_row:
        effective_max_rows = min(effective_max_rows, max(0, stop_before_row - data_start_row))
    for offset in range(effective_max_rows):
        row_index = data_start_row + offset
        if stop_before_row and row_index >= stop_before_row:
            break
        row_data = {"row": row_index, "row_index": row_index, "cells": {}}
        non_empty = False
        for key, col_letters in columns.items():
            if not isinstance(col_letters, str) or not col_letters:
                row_data[key] = ""
                row_data["cells"][key] = ""
                continue
            cell_ref = f"{col_letters}{row_index}"
            value = _equipment_cache_text(sheet_cache, cell_ref)
            row_data[key] = value
            row_data["cells"][key] = cell_ref
            if value:
                non_empty = True

        stop_reason, stop_text = _equipment_stop_reason(kind, row_data)
        if stop_reason:
            if window is not None and window._equipment_print_mapping_enabled():
                log_debug(
                    "equipment",
                    f'EQUIPMENT SKIP {kind} row={row_index} reason={stop_reason} text="{stop_text}"',
                )
            break

        if kind == "armor":
            is_data = _is_valid_armor_data_core(
                row_data.get("slot", ""),
                row_data.get("name", ""),
                row_data.get("pl", ""),
            )
        else:
            is_data = _is_valid_weapon_data_core(
                row_data.get("name", ""),
                row_data.get("weapon_type", ""),
                row_data.get("pl", ""),
                row_data.get("physical_dice", ""),
                row_data.get("attributes", ""),
            )
        row_data["is_data_row"] = bool(is_data)
        row_data["is_empty_row"] = not non_empty
        rows.append(row_data)
    return rows


def _find_weapon_stop_before_row(entries, weapon_data_start_row):
    if weapon_data_start_row <= 0:
        return 0, "fallback"
    for entry in entries:
        row = int(entry.get("row", 0) or 0)
        if row <= weapon_data_start_row:
            continue
        norm = str(entry.get("norm", "") or "")
        if not norm:
            continue
        if "feuer" in norm and "wasser" in norm and "erde" in norm:
            return row, "unrelated_section_header"
        for marker in ("elementare", "boni", "affinitaet", "affinitaeten"):
            if marker in norm:
                return row, "unrelated_section_header"
    return 0, "fallback"


def _find_equipment_first_data_row(sheet_cache, start_row, key_columns):
    if not isinstance(sheet_cache, dict):
        return start_row + 3
    normalized_cols = [str(col).strip().upper() for col in key_columns if isinstance(col, str) and col]
    for row_index in range(start_row + 1, start_row + 30):
        row_values = [
            _equipment_cache_text(sheet_cache, f"{col_letters}{row_index}")
            for col_letters in normalized_cols
        ]
        if _is_valid_armor_data_core(
            row_values[0] if len(row_values) > 0 else "",
            row_values[1] if len(row_values) > 1 else "",
            row_values[2] if len(row_values) > 2 else "",
        ):
            return row_index
    return start_row + 3


def _find_armor_header_columns(header_entries, anchor_row):
    header_rows = [anchor_row + i for i in range(0, 8)]
    slot_col = _find_equipment_column(header_entries, header_rows, ["wo", "getragen"])
    name_col = _find_equipment_column(
        header_entries, header_rows, ["name"], exclude_tokens=["waffe", "waffentyp"]
    )
    pl_col = _find_equipment_column(header_entries, header_rows, ["pl"])
    if slot_col is None or name_col is None or pl_col is None:
        return None
    return {"slot_col": slot_col, "name_col": name_col, "pl_col": pl_col}


def _build_armor_mapping(window, header_entries, anchor_row, sheet_cache):
    if anchor_row <= 0:
        return {}
    header_cols = _find_armor_header_columns(header_entries, anchor_row)
    if not isinstance(header_cols, dict):
        return {}

    slot_col = int(header_cols["slot_col"])
    name_col = int(header_cols["name_col"])
    pl_col = int(header_cols["pl_col"])
    header_row = 0
    for entry in header_entries:
        if int(entry.get("col", 0)) == slot_col and "wo getragen" == entry.get("norm", ""):
            header_row = int(entry.get("row", 0))
            break
    if header_row <= 0:
        header_row = anchor_row + 2
    header_rows = [header_row]

    phys_head_col = pl_col + 2
    phys_chest_col = pl_col + 4
    phys_arms_col = pl_col + 6
    phys_legs_col = pl_col + 8
    fire_col = pl_col + 10
    water_col = pl_col + 12
    earth_col = pl_col + 14
    wind_col = pl_col + 16
    lightning_col = pl_col + 18
    ice_col = pl_col + 20
    acid_col = pl_col + 22
    light_col = pl_col + 24
    dark_col = pl_col + 26
    durability_current_col = pl_col + 28
    slash_col = pl_col + 30
    durability_max_col = pl_col + 31
    attributes_col = pl_col + 35

    slot_letters = window._col_index_to_letters(slot_col)
    name_letters = window._col_index_to_letters(name_col)
    pl_letters = window._col_index_to_letters(pl_col)
    data_start_row = _find_equipment_first_data_row(
        sheet_cache,
        header_row,
        [slot_letters, name_letters, pl_letters],
    )

    mapping = {
        "start_row": header_row,
        "header_rows": header_rows,
        "data_start_row": data_start_row,
        "columns": {
            "slot": slot_letters,
            "name": name_letters,
            "pl": pl_letters,
            "phys_head": window._col_index_to_letters(phys_head_col),
            "phys_chest": window._col_index_to_letters(phys_chest_col),
            "phys_arms": window._col_index_to_letters(phys_arms_col),
            "phys_legs": window._col_index_to_letters(phys_legs_col),
            "fire": window._col_index_to_letters(fire_col),
            "water": window._col_index_to_letters(water_col),
            "earth": window._col_index_to_letters(earth_col),
            "wind": window._col_index_to_letters(wind_col),
            "lightning": window._col_index_to_letters(lightning_col),
            "ice": window._col_index_to_letters(ice_col),
            "acid": window._col_index_to_letters(acid_col),
            "light": window._col_index_to_letters(light_col),
            "dark": window._col_index_to_letters(dark_col),
            "durability_current": window._col_index_to_letters(durability_current_col),
            "durability_max": window._col_index_to_letters(durability_max_col),
            "attributes": window._col_index_to_letters(attributes_col),
        },
    }
    slash_value = _equipment_cache_text(
        sheet_cache,
        f"{window._col_index_to_letters(slash_col)}{data_start_row}",
    )
    if window._equipment_print_mapping_enabled():
        log_debug("equipment", f"EQUIPMENT ARMOR COLUMN CHECK durability_slash={window._col_index_to_letters(slash_col)}{data_start_row} sample={slash_value}")
    return mapping


def _build_weapon_mapping(window, header_entries, anchor_row):
    if anchor_row <= 0:
        return {}
    header_rows = [anchor_row + i for i in range(0, 5)]
    name_col = _find_equipment_column(
        header_entries, header_rows, ["name"], exclude_tokens=["wo", "getragen"]
    )
    weapon_type_col = _find_equipment_column(
        header_entries, header_rows, ["waffentyp"]
    )
    pl_col = _find_equipment_column(header_entries, header_rows, ["pl"])
    if name_col is None or pl_col is None:
        return {}

    header_row = 0
    for entry in header_entries:
        if int(entry.get("col", 0)) == name_col and entry.get("norm", "") == "name":
            header_row = int(entry.get("row", 0))
            break
    if header_row <= 0:
        header_row = anchor_row + 2

    if weapon_type_col is None:
        weapon_type_col = name_col + 4

    damage_cut_col = pl_col + 2
    damage_blunt_col = pl_col + 4
    damage_pierce_col = pl_col + 6
    physical_dice_col = pl_col + 9
    physical_bonus_col = pl_col + 13
    elemental_dice_col = pl_col + 16
    elemental_elements_col = pl_col + 20
    elemental_bonus_col = pl_col + 24
    durability_current_col = pl_col + 27
    slash_col = pl_col + 29
    durability_max_col = pl_col + 30
    attributes_col = pl_col + 32
    data_start_row = header_row + 2

    mapping = {
        "start_row": header_row,
        "header_rows": [header_row],
        "data_start_row": data_start_row,
        "columns": {
            "name": window._col_index_to_letters(name_col),
            "weapon_type": window._col_index_to_letters(weapon_type_col),
            "pl": window._col_index_to_letters(pl_col),
            "damage_cut": window._col_index_to_letters(damage_cut_col),
            "damage_blunt": window._col_index_to_letters(damage_blunt_col),
            "damage_pierce": window._col_index_to_letters(damage_pierce_col),
            "physical_dice": window._col_index_to_letters(physical_dice_col),
            "physical_bonus": window._col_index_to_letters(physical_bonus_col),
            "elemental_dice": window._col_index_to_letters(elemental_dice_col),
            "elemental_elements": window._col_index_to_letters(elemental_elements_col),
            "elemental_bonus": window._col_index_to_letters(elemental_bonus_col),
            "durability_current": window._col_index_to_letters(durability_current_col),
            "durability_max": window._col_index_to_letters(durability_max_col),
            "attributes": window._col_index_to_letters(attributes_col),
        },
    }
    if window._equipment_print_mapping_enabled():
        # The visible "/" separator between current and max is intentionally skipped.
        log_debug("equipment", f"EQUIPMENT WEAPON COLUMN CHECK durability_current={window._col_index_to_letters(durability_current_col)}{data_start_row} slash={window._col_index_to_letters(slash_col)}{data_start_row} durability_max={window._col_index_to_letters(durability_max_col)}{data_start_row}")
    return mapping


def analyze_equipment_sheet(window):
    sheet_name, sheet_cache = get_equipment_sheet_cache(window)
    if not sheet_name or not isinstance(sheet_cache, dict) or not sheet_cache:
        window.equipment_analysis = {"sheet": "", "armor": {"mapping": {}, "rows": []}, "weapons": {"mapping": {}, "rows": []}}
        return window.equipment_analysis

    entries = []
    for cell_ref, cell_data in sheet_cache.items():
        text = _equipment_cache_text(sheet_cache, cell_ref)
        if not text:
            continue
        row, col = _equipment_cell_sort_key(window, cell_ref)
        if row <= 0 or col <= 0:
            continue
        entries.append(
            {
                "cell": str(cell_ref).upper(),
                "row": row,
                "col": col,
                "text": text,
                "norm": _normalize_equipment_text(text),
            }
        )

    entries.sort(key=lambda item: (item["row"], item["col"]))
    print_mapping = window._equipment_print_mapping_enabled()
    print_rows = window._equipment_print_rows_enabled()
    target_headers = {
        "ruestung",
        "waffe",
        "wo getragen",
        "name",
        "pl",
        "physische resistenzen",
        "elementare resistenzen",
        "haltbarkeit",
        "attribute sonderfertigkeiten",
        "waffentyp",
        "schadensart",
        "physisch",
        "elementar",
    }
    for entry in entries:
        if print_mapping and entry["norm"] in target_headers:
            log_debug("equipment", f'EQUIPMENT HEADER text="{entry["text"]}" cell={entry["cell"]}')

    armor_anchor = 0
    weapon_anchor = 0
    for entry in entries:
        if entry["norm"] == "ruestung" and armor_anchor == 0:
            armor_anchor = entry["row"]
        if entry["norm"] == "waffe" and weapon_anchor == 0:
            weapon_anchor = entry["row"]
    if print_mapping and armor_anchor > 0:
        log_debug("equipment", f"EQUIPMENT TABLE armor start_row={armor_anchor}")
    elif print_mapping:
        log_debug("equipment", "EQUIPMENT TABLE armor not found")
    if print_mapping and weapon_anchor > 0:
        log_debug("equipment", f"EQUIPMENT TABLE weapon start_row={weapon_anchor}")
    elif print_mapping:
        log_debug("equipment", "EQUIPMENT TABLE weapon not found")

    armor_mapping = _build_armor_mapping(window, entries, armor_anchor, sheet_cache)
    weapon_mapping = _build_weapon_mapping(window, entries, weapon_anchor)

    if print_mapping and armor_mapping:
        log_debug("equipment", f"EQUIPMENT ARMOR MAP start_row={armor_mapping['start_row']} data_start_row={armor_mapping['data_start_row']}")
        for key, col_letters in armor_mapping.get("columns", {}).items():
            if col_letters:
                log_debug("equipment", f"EQUIPMENT ARMOR COLUMN {key}={col_letters}")
        sample_row = int(armor_mapping.get("data_start_row", 0) or 0)
        if sample_row > 0:
            for check_key in ("phys_chest", "durability_current", "durability_max"):
                col_letters = str(armor_mapping.get("columns", {}).get(check_key, "") or "")
                if not col_letters:
                    continue
                sample_value = _equipment_cache_text(sheet_cache, f"{col_letters}{sample_row}")
                log_debug("equipment", f"EQUIPMENT ARMOR COLUMN CHECK {check_key}={col_letters}{sample_row} sample={sample_value}")
    if print_mapping and weapon_mapping:
        log_debug("equipment", f"EQUIPMENT WEAPON MAP start_row={weapon_mapping['start_row']} data_start_row={weapon_mapping['data_start_row']}")
        for key, col_letters in weapon_mapping.get("columns", {}).items():
            if col_letters:
                log_debug("equipment", f"EQUIPMENT WEAPON COLUMN {key}={col_letters}")

    armor_data_start = int(armor_mapping.get("data_start_row", 0) or 0) if armor_mapping else 0
    weapon_data_start = int(weapon_mapping.get("data_start_row", 0) or 0) if weapon_mapping else 0
    armor_stop_before_row = weapon_anchor if weapon_anchor > 0 else 0
    armor_max_rows = max(0, armor_stop_before_row - armor_data_start) if armor_stop_before_row and armor_data_start else 12

    weapon_stop_before_row, weapon_stop_reason = _find_weapon_stop_before_row(entries, weapon_data_start)
    weapon_max_rows = (
        max(0, weapon_stop_before_row - weapon_data_start)
        if weapon_stop_before_row and weapon_data_start
        else 10
    )

    if print_mapping:
        armor_end = armor_stop_before_row - 1 if armor_stop_before_row else armor_data_start + armor_max_rows - 1
        log_debug(
            "equipment",
            f"EQUIPMENT RANGE armor start={armor_data_start} end={armor_end} weapon_anchor={weapon_anchor}",
        )
        weapon_end = (
            weapon_stop_before_row - 1
            if weapon_stop_before_row
            else weapon_data_start + weapon_max_rows - 1
        )
        log_debug(
            "equipment",
            f"EQUIPMENT RANGE weapons start={weapon_data_start} end={weapon_end} stop_reason={weapon_stop_reason}",
        )

    armor_rows = _extract_equipment_rows(
        sheet_cache,
        armor_mapping,
        "armor",
        max_rows=armor_max_rows,
        stop_before_row=armor_stop_before_row,
        window=window,
    )
    weapon_rows = _extract_equipment_rows(
        sheet_cache,
        weapon_mapping,
        "weapon",
        max_rows=weapon_max_rows,
        stop_before_row=weapon_stop_before_row,
        window=window,
    )

    if print_mapping and armor_mapping:
        data_start_row = int(armor_mapping.get("data_start_row", 0) or 0)
        debug_fields = [
            ("slot", "slot"),
            ("name", "name"),
            ("pl", "pl"),
            ("phys_chest", "phys_chest"),
            ("phys_arms", "phys_arms"),
            ("phys_legs", "phys_legs"),
            ("durability_current", "durability_current"),
            ("durability_max", "durability_max"),
        ]
        for row_index in range(data_start_row, data_start_row + 3):
            for field_key, label in debug_fields:
                col_letters = str(armor_mapping.get("columns", {}).get(field_key, "") or "")
                if not col_letters:
                    continue
                cell_ref = f"{col_letters}{row_index}"
                value = _equipment_cache_text(sheet_cache, cell_ref)
                log_debug("equipment", f"EQUIPMENT ARMOR DEBUG CELL row={row_index} field={label} cell={cell_ref} value={value}")

    expected_found = False
    for row_data in armor_rows:
        name_norm = _normalize_equipment_text(row_data.get("name", ""))
        slot_norm = _normalize_equipment_text(row_data.get("slot", ""))
        if name_norm == "leder ruestung" and slot_norm == "brust arme beine":
            expected_found = True
            break
    if print_mapping and not expected_found and armor_rows:
        log_debug("equipment", "EQUIPMENT ARMOR ERROR expected armor row not found")
    elif print_mapping and not armor_rows:
        log_debug("equipment", "EQUIPMENT ARMOR ERROR expected armor row not found")

    has_weapon_data_rows = any(bool(row.get("is_data_row")) for row in weapon_rows if isinstance(row, dict))
    if print_rows:
        for row_data in armor_rows:
            if not row_data.get("is_data_row"):
                continue
            log_debug("equipment", f'EQUIPMENT ARMOR ROW row={row_data["row"]} slot="{row_data.get("slot", "")}" name="{row_data.get("name", "")}" pl="{row_data.get("pl", "")}"')
        for row_data in weapon_rows:
            if not row_data.get("is_data_row"):
                continue
            durability_summary = ""
            current_value = str(row_data.get("durability_current", "") or "").strip()
            max_value = str(row_data.get("durability_max", "") or "").strip()
            if current_value or max_value:
                durability_summary = f"{current_value}/{max_value}".strip("/")
            log_debug("equipment", f'EQUIPMENT WEAPON ROW row={row_data["row"]} name="{row_data.get("name", "")}" type="{row_data.get("weapon_type", "")}" pl="{row_data.get("pl", "")}" phys_dice="{row_data.get("physical_dice", "")}" phys_bonus="{row_data.get("physical_bonus", "")}" durability="{durability_summary}"')
    if print_rows and not has_weapon_data_rows:
        log_debug("equipment", "EQUIPMENT WEAPON no rows found")

    window.equipment_analysis = {
        "sheet": sheet_name,
        "armor": {
            "mapping": armor_mapping,
            "rows": armor_rows,
        },
        "weapons": {
            "mapping": weapon_mapping,
            "rows": weapon_rows,
        },
    }
    return window.equipment_analysis
