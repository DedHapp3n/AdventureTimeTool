import re


def safe_int(value, default=0):
    try:
        text = str(value).strip()
        if not text:
            return default
        return int(float(text.replace(",", ".")))
    except (TypeError, ValueError):
        return default


def normalize_dice_expression(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"(?i)\b(\d*)d(\d{1,3})\b", text)
    if not match:
        return ""
    count = match.group(1) or "1"
    sides = match.group(2)
    return f"{safe_int(count, 1)}d{safe_int(sides, 0)}" if safe_int(sides, 0) > 0 else ""


def dice_expression_parts(value: str, default_sides=6):
    dice = normalize_dice_expression(value)
    if not dice:
        return {"count": 0, "sides": default_sides}
    match = re.match(r"(?i)^(\d+)d(\d+)$", dice)
    if not match:
        return {"count": 0, "sides": default_sides}
    return {"count": safe_int(match.group(1), 0), "sides": safe_int(match.group(2), default_sides)}


def _dice_note(value):
    text = str(value or "").strip()
    dice = normalize_dice_expression(text)
    if not text or not dice:
        return ""
    note = re.sub(r"(?i)\b\d*d\d{1,3}\b", "", text, count=1).strip(" +-:/")
    return note.strip()


def parse_weapon_row(row_data: dict) -> dict:
    row = row_data if isinstance(row_data, dict) else {}
    dice_1_raw = str(row.get("dice_1", row.get("physical_dice", "")) or "")
    dice_2_raw = str(row.get("dice_2", row.get("elemental_dice", "")) or "")
    weapon = {
        "name": str(row.get("name", "") or ""),
        "weapon_type": str(row.get("weapon_type", "") or ""),
        "pl": str(row.get("pl", "") or ""),
        "damage_type_cut": str(row.get("damage_type_cut", row.get("damage_cut", "")) or ""),
        "damage_type_blunt": str(row.get("damage_type_blunt", row.get("damage_blunt", "")) or ""),
        "damage_type_pierce": str(row.get("damage_type_pierce", row.get("damage_pierce", "")) or ""),
        "dice_1": normalize_dice_expression(dice_1_raw),
        "bonus_1": str(row.get("bonus_1", row.get("physical_bonus", "")) or ""),
        "dice_2": normalize_dice_expression(dice_2_raw),
        "elements": str(row.get("elements", row.get("elemental_elements", "")) or ""),
        "bonus_2": str(row.get("bonus_2", row.get("elemental_bonus", "")) or ""),
        "durability": str(row.get("durability", row.get("durability_current", "")) or ""),
        "max_durability": str(row.get("max_durability", row.get("durability_max", "")) or ""),
        "attributes_special": str(row.get("attributes_special", row.get("attributes", "")) or ""),
        "dice_1_note": _dice_note(dice_1_raw),
        "dice_2_note": _dice_note(dice_2_raw),
    }
    return weapon


def weapon_roll_components(weapon: dict):
    data = weapon if isinstance(weapon, dict) else {}
    physical = dice_expression_parts(data.get("dice_1", ""), 6)
    elemental = dice_expression_parts(data.get("dice_2", ""), 6)
    return {
        "physical": {
            "count": physical.get("count", 0),
            "sides": physical.get("sides", 6),
            "bonus": safe_int(data.get("bonus_1", 0), 0),
            "note": str(data.get("dice_1_note", "") or ""),
        },
        "elemental": {
            "count": elemental.get("count", 0),
            "sides": elemental.get("sides", 6),
            "bonus": safe_int(data.get("bonus_2", 0), 0),
            "note": str(data.get("dice_2_note", data.get("elements", "")) or ""),
        },
        "extra": {
            "count": 0,
            "sides": 10,
            "bonus": 0,
            "note": "",
        },
        "manual_bonus": 0,
    }


def _append_bonus(parts, value):
    bonus = safe_int(value, 0)
    if bonus > 0:
        parts.append(f"+{bonus}")
    elif bonus < 0:
        parts.append(str(bonus))


def _append_component(parts, component):
    if not isinstance(component, dict):
        return
    count = max(0, safe_int(component.get("count", 0), 0))
    sides = safe_int(component.get("sides", 0), 0)
    if count <= 0 or sides <= 0:
        return
    dice_part = f"{count}d{sides}"
    parts.append(f"+{dice_part}" if parts else dice_part)
    _append_bonus(parts, component.get("bonus", 0))


def _sanitize_weapon_name(value):
    text = str(value or "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[\x00-\x1f\x7f]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def build_attack_roll_command(weapon: dict, options: dict | None = None) -> str:
    data = weapon if isinstance(weapon, dict) else {}
    options = options if isinstance(options, dict) else {}
    prefix = str(options.get("roll20_prefix", "/r") or "/r").strip() or "/r"
    parts = []
    pending_manual_bonus = 0

    components = options.get("components")
    if isinstance(components, dict):
        for key in ("physical", "elemental", "extra"):
            _append_component(parts, components.get(key, {}))
        pending_manual_bonus = components.get("manual_bonus", 0)
    else:
        dice_1 = normalize_dice_expression(data.get("dice_1", ""))
        if dice_1:
            parts.append(dice_1)
            _append_bonus(parts, data.get("bonus_1", ""))

        dice_2 = normalize_dice_expression(data.get("dice_2", ""))
        if dice_2:
            if parts:
                parts.append(f"+{dice_2}")
            else:
                parts.append(dice_2)
            _append_bonus(parts, data.get("bonus_2", ""))

        manual_dice = normalize_dice_expression(options.get("manual_dice", ""))
        if manual_dice:
            parts.append(f"+{manual_dice}" if parts else manual_dice)
        pending_manual_bonus = options.get("manual_bonus", "")

    if not parts:
        fallback = normalize_dice_expression(options.get("fallback_dice", "1d20")) or "1d20"
        parts.append(fallback)
    _append_bonus(parts, pending_manual_bonus)
    command = f"{prefix} {''.join(parts)}"
    weapon_name = _sanitize_weapon_name(data.get("name", ""))
    if weapon_name:
        command = f"{command} ({weapon_name})"
    return command
