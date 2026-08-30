import json
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QComboBox, QLineEdit, QPushButton, QScrollArea, QTextEdit, QWidget

from app_logger import log_error, log_debug
from app_paths import data_path, resource_path
from ui_dialogs.perk_picker_dialog import open_perk_picker


STEPS = [
    ("species", "Spezies"),
    ("concept", "Biografie"),
    ("attributes", "Attribute"),
    ("skills_perks", "Fertigkeiten & Perks"),
    ("equipment", "Ausrüstung"),
    ("summary", "Zusammenfassung"),
]

CREATOR_ATTRIBUTE_OPTIONS = [
    ("K", "Kraft"),
    ("G", "Geschick"),
    ("Z", "Zähigkeit"),
    ("R", "Reflex"),
    ("I", "Intelligenz"),
    ("W", "Willenskraft"),
    ("C", "Charisma"),
    ("S", "Sinne"),
]
CREATOR_ATTRIBUTE_ALIASES = {
    "K": "K",
    "KRAFT": "K",
    "G": "G",
    "GESCHICK": "G",
    "GESCHICKLICHKEIT": "G",
    "Z": "Z",
    "ZAEHIGKEIT": "Z",
    "ZÄHIGKEIT": "Z",
    "R": "R",
    "REFLEX": "R",
    "REFLEXE": "R",
    "I": "I",
    "INTELLIGENZ": "I",
    "W": "W",
    "WILLENSKRAFT": "W",
    "C": "C",
    "CHARISMA": "C",
    "S": "S",
    "SINNE": "S",
}

SPECIES = [
    {
        "id": "menschen",
        "name": "Menschen",
        "description": "Anpassungsfaehige Allrounder mit schneller Entwicklung.",
        "perks": ["Schnelle Entwicklung"],
        "bp_bonus": "",
        "notes": "+Baupunkte [9]",
    },
    {
        "id": "taimana",
        "name": "Taimana",
        "description": "Robuste Spezies mit eigenem kulturellen Profil.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "irdene",
        "name": "Irdene",
        "description": "Standhafte Spezies mit Erdverbundenheit.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "weaver",
        "name": "Weaver",
        "description": "Feinsinnige Spezies mit besonderem Talentprofil.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "sylph",
        "name": "Sylph",
        "description": "Leichte, bewegliche Spezies mit luftiger Praegung.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "wyverian_wylv",
        "name": "Wyverian / Wylv",
        "description": "Drachennahe Spezies mit markanter Herkunft.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "ork",
        "name": "Ork",
        "description": "Kampfstaerke und Zaehigkeit stehen im Vordergrund.",
        "perks": ["Kriegerblut", "Kampftalent (Lvl: 2)", "Robust"],
        "bp_bonus": "",
        "notes": "15 BP",
    },
    {
        "id": "goblin",
        "name": "Goblin",
        "description": "Kleine, flinke Spezies mit eigenwilligem Profil.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "gremlin",
        "name": "Gremlin",
        "description": "Kleine Spezies mit technischem oder listigem Einschlag.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "nhym",
        "name": "Nhym",
        "description": "Spezies mit besonderer Herkunft und eigenem Spielgefuehl.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "shab_ark",
        "name": "Shab'ark",
        "description": "Markante Spezies mit koerperlicher Praegung.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "malaschi",
        "name": "Malaschi",
        "description": "Ungewoehnliche Spezies mit eigenem Talentfokus.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "armelidae",
        "name": "Armelidae",
        "description": "Spezies mit auffaelliger Gestalt und klarer Identitaet.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "volx",
        "name": "Volx",
        "description": "Spezies mit eigenstaendiger Kultur und Anlagen.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "lepurii",
        "name": "Lepurii",
        "description": "Bewegliche Spezies mit wacher Wahrnehmung.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "kitsune",
        "name": "Kitsune",
        "description": "Mystische Spezies mit Sinn fuer Illusion und Wahrnehmung.",
        "perks": ["3tes Auge", "Illusion (natuerlich)", "Feines Gehoer"],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "xacivi",
        "name": "Xacivi",
        "description": "Fremdartige Spezies mit eigenem Schwerpunkt.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "naggahi",
        "name": "Naggahi",
        "description": "Spezies mit reptilischer oder schlangenartiger Praegung.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "korika",
        "name": "Korika",
        "description": "Spezies mit eigener Tradition und Ausrichtung.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "kri_tikki",
        "name": "Kri'tikki",
        "description": "Spezies mit besonderer Gestalt und Instinkten.",
        "perks": [],
        "bp_bonus": "",
        "notes": "",
    },
    {
        "id": "yun_ga",
        "name": "Yûn'ga",
        "description": "Pflanzennahe Spezies mit magischer Begabung.",
        "perks": ["Photosynthese", "Feueranfaellig", "Magieanwender", "Pflanzensprache"],
        "bp_bonus": "",
        "notes": "+2 BP fuer Magietalente",
    },
]

for species in SPECIES:
    species["image_path"] = f"assets/ui_elements/character_creator/species/{species['id']}.png"


# zoom < 1.0 shows more of the portrait
# positive offset_x moves image right / negative moves left
# positive offset_y moves image down / negative moves up
SPECIES_PORTRAIT_TUNING = {
    "taimana": {"zoom": 0.90, "offset_x": -4.8, "offset_y": 2.0},
    "menschen": {"zoom": 0.90, "offset_x": 0, "offset_y": 0},
    "irdene": {"zoom": 1.0, "offset_x": -10, "offset_y": 0},
    "sylph": {"zoom": 0.88, "offset_x": 0, "offset_y": 3},
    "shab_ark": {"zoom": 0.90, "offset_x": 0, "offset_y": 5},
    "malaschi": {"zoom": 0.90, "offset_x": 0, "offset_y": 5},
    "wyverian_wylv": {"zoom": 1, "offset_x": -5, "offset_y": 0},
    "armelidae": {"zoom": 0.85, "offset_x": 0, "offset_y": 0},
    "volx": {"zoom": 1, "offset_x": -4, "offset_y": 0},
    "goblin": {"zoom": 1, "offset_x": 0, "offset_y": -5},
    "gremlin": {"zoom": 1, "offset_x": 0, "offset_y": -5},
    "armelidae": {"zoom": 1, "offset_x": 0, "offset_y": 15},
}


def render_character_creator_section(window):
    if window.content_layer is None:
        return

    state = _ensure_creator_state(window)
    content_w = window.content_layer.width()
    content_h = window.content_layer.height()
    margin = 24
    title_h = 44
    step_h = 46
    footer_h = 54
    gap = 14

    title = QLabel(window.content_layer)
    title.setGeometry(margin, 4, content_w - (margin * 2), title_h)
    title.setText("Charakter erstellen")
    title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 30px; font-weight: 800;")
    title.show()

    _render_step_buttons(window, margin, title_h + 4, content_w - (margin * 2), step_h, state)

    panel_y = title_h + step_h + gap + 8
    panel_h = max(260, content_h - panel_y - footer_h - gap)
    if state.get("step") == "species":
        panel = QWidget(window.content_layer)
        panel.setGeometry(margin, panel_y, content_w - (margin * 2), panel_h)
        panel.setStyleSheet("background: transparent; border: none;")
        panel.show()
    else:
        panel = _create_framed_panel(
            window,
            window.content_layer,
            margin,
            panel_y,
            content_w - (margin * 2),
            panel_h,
        )

    if state.get("step") == "species":
        _render_species_step(window, panel, state)
    elif state.get("step") == "concept":
        _render_concept_step(window, panel, state)
    elif state.get("step") == "attributes":
        _render_attributes_step(window, panel, state)
    elif state.get("step") == "skills_perks":
        _render_skills_perks_step(window, panel, state)
    elif state.get("step") == "equipment":
        _render_equipment_step(window, panel, state)
    elif state.get("step") == "summary":
        _render_summary_step(window, panel, state)
    else:
        _render_placeholder_step(panel, state)

    _render_footer(window, margin, panel_y + panel_h + gap, content_w - (margin * 2), footer_h, state)


def _ensure_creator_state(window):
    state = getattr(window, "_character_creator_state", None)
    if not isinstance(state, dict):
        state = {}
        window._character_creator_state = state
    state.setdefault("step", "species")
    state.setdefault("species_id", SPECIES[0]["id"])
    state.setdefault("species_name", SPECIES[0]["name"])
    state.setdefault("species_image_path", SPECIES[0]["image_path"])
    start_values = state.get("start_values")
    if not isinstance(start_values, dict):
        start_values = {}
        state["start_values"] = start_values
    start_values["ap"] = _clamp_start_ap(start_values.get("ap", 5))
    start_values["xp"] = _non_negative_int(start_values.get("xp", 0))
    concept = state.get("concept")
    if not isinstance(concept, dict):
        concept = {}
        state["concept"] = concept
    concept.setdefault("character_name", "")
    concept.setdefault("player_name", "")
    concept.setdefault("short_concept", "")
    concept.setdefault("origin", "")
    concept.setdefault("role", "")
    concept.setdefault("motivation", "")
    concept.setdefault("description", "")
    paradigms = state.get("paradigms")
    if not isinstance(paradigms, list):
        paradigms = []
        state["paradigms"] = paradigms
    while len(paradigms) < 3:
        paradigms.append({"name": "", "grad": 1})
    del paradigms[3:]
    for paradigm in paradigms:
        if isinstance(paradigm, dict):
            paradigm.setdefault("name", "")
            paradigm["grad"] = 2 if int(paradigm.get("grad", 1) or 1) == 2 else 1
    attributes = state.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {}
        state["attributes"] = attributes
    body = attributes.get("body")
    if not isinstance(body, dict):
        body = {}
        attributes["body"] = body
    mind = attributes.get("mind")
    if not isinstance(mind, dict):
        mind = {}
        attributes["mind"] = mind
    for key in ("kraft", "geschick", "zaehigkeit", "reflex"):
        body.setdefault(key, 0)
    for key in ("intelligenz", "willenskraft", "charisma", "sinne"):
        mind.setdefault(key, 0)
    skills = state.get("skills")
    if not isinstance(skills, dict):
        skills = {}
        state["skills"] = skills
    perks = state.get("perks")
    if not isinstance(perks, list):
        perks = []
        state["perks"] = perks
    disadvantages = state.get("disadvantages")
    if not isinstance(disadvantages, list):
        disadvantages = []
        state["disadvantages"] = disadvantages
    equipment = state.get("equipment")
    if not isinstance(equipment, dict):
        equipment = {}
        state["equipment"] = equipment
    money = equipment.get("money")
    if not isinstance(money, dict):
        money = {}
        equipment["money"] = money
    money.setdefault("gulden", 0)
    money.setdefault("schilling", 0)
    money.setdefault("heller", 0)
    for key in ("items", "armor", "weapons"):
        if not isinstance(equipment.get(key), list):
            equipment[key] = []
    equipment.setdefault("notes", "")
    if state.get("step") not in {step_id for step_id, _ in STEPS}:
        state["step"] = "species"
    species = _species_by_id(state.get("species_id"))
    state["species_id"] = species["id"]
    state["species_name"] = species["name"]
    state["species_image_path"] = species["image_path"]
    return state


def _rerender(window):
    window.clear_content_layer()
    render_character_creator_section(window)


def _set_step(window, step):
    state = _ensure_creator_state(window)
    state["step"] = step
    _rerender(window)


def _render_step_buttons(window, x, y, w, h, state):
    gap = 8
    button_w = max(112, (w - (gap * (len(STEPS) - 1))) // len(STEPS))
    for index, (step_id, label) in enumerate(STEPS):
        active = step_id == state.get("step")
        result = window.create_asset_text_button(
            window.content_layer,
            {
                "x": x + (index * (button_w + gap)),
                "y": y,
                "w": button_w,
                "h": h,
                "text": label,
                "asset": "buttons/menu_button_medium.png",
                "font_size": 14,
                "color": "#f2d28b" if active else "#9a8560",
            },
            label,
            lambda checked=False, step=step_id: _set_step(window, step),
        )
        button = result.get("button") if isinstance(result, dict) else None
        if button is not None:
            button.setStyleSheet(
                "QPushButton { background: transparent; padding: 0px; "
                f"border: {'2px solid rgba(242, 210, 139, 190)' if active else 'none'}; }}"
                "QPushButton:hover { border: 2px solid rgba(242, 210, 139, 130); }"
            )


def _render_placeholder_step(panel, state):
    step_label = dict(STEPS).get(state.get("step"), "Schritt")
    label = QLabel(panel)
    label.setGeometry(20, 20, panel.width() - 40, panel.height() - 40)
    label.setText(f"{step_label}\n\nKommt später.")
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(
        "background: transparent; color: #f2d28b; font-size: 24px; font-weight: 700;"
    )
    label.show()


def _render_concept_step(window, panel, state):
    pad = 18
    body_w = panel.width() - (pad * 2)
    body_h = panel.height() - (pad * 2)
    concept = state.get("concept", {})

    ref_w = max(210, min(300, int(body_w * 0.27)))
    gap = 18
    left_w = max(320, body_w - ref_w - gap)
    if left_w + gap + ref_w > body_w:
        ref_w = max(180, body_w - left_w - gap)

    scroll = QScrollArea(panel)
    scroll.setGeometry(pad, pad, left_w, body_h)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: #17110f; width: 12px; }"
        "QScrollBar::handle:vertical { background: #6c4a22; min-height: 24px; }"
    )

    host = QWidget(scroll)
    host.setStyleSheet("background: transparent;")
    inner_w = max(320, left_w - 26)
    cursor_y = 10

    title = QLabel(host)
    title.setGeometry(8, cursor_y, inner_w - 16, 34)
    title.setText("Biografie")
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 26px; font-weight: 800;")
    title.show()
    cursor_y += 42

    intro = QLabel(host)
    intro.setGeometry(8, cursor_y, inner_w - 16, 50)
    intro.setText(
        "Beschreibe hier Herkunft, Rolle, Motivation und Persönlichkeit deines Charakters. Diese Angaben sind erzählerisch "
        "und können später noch angepasst werden."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 14px; font-weight: 600;")
    intro.show()
    cursor_y += 66

    cursor_y = _create_bio_section_heading(host, 8, cursor_y, inner_w - 16, "Grunddaten")
    field_gap = 14
    row_h = 64
    if inner_w >= 560:
        compact_w = (inner_w - 16 - (field_gap * 2)) // 3
        wide_w = (inner_w - 16 - field_gap) // 2
        _create_concept_line_edit(host, 8, cursor_y, compact_w, "Charaktername", concept, "character_name")
        _create_concept_line_edit(host, 8 + compact_w + field_gap, cursor_y, compact_w, "Spielername", concept, "player_name")
        _create_concept_line_edit(host, 8 + ((compact_w + field_gap) * 2), cursor_y, compact_w, "Beruf / Rolle", concept, "role")
        cursor_y += row_h
        _create_concept_line_edit(host, 8, cursor_y, wide_w, "Kurzkonzept", concept, "short_concept")
        _create_concept_line_edit(host, 8 + wide_w + field_gap, cursor_y, wide_w, "Herkunft / Kultur", concept, "origin")
        cursor_y += row_h + 4
    else:
        field_w = (inner_w - 16 - field_gap) // 2
        _create_concept_line_edit(host, 8, cursor_y, field_w, "Charaktername", concept, "character_name")
        _create_concept_line_edit(host, 8 + field_w + field_gap, cursor_y, field_w, "Spielername", concept, "player_name")
        cursor_y += row_h
        _create_concept_line_edit(host, 8, cursor_y, field_w, "Beruf / Rolle", concept, "role")
        _create_concept_line_edit(host, 8 + field_w + field_gap, cursor_y, field_w, "Herkunft / Kultur", concept, "origin")
        cursor_y += row_h
        _create_concept_line_edit(host, 8, cursor_y, inner_w - 16, "Kurzkonzept", concept, "short_concept")
        cursor_y += row_h + 4

    cursor_y = _render_creator_paradigms_editor(window, host, 8, cursor_y + 10, inner_w - 16, state)

    cursor_y = _create_bio_section_heading(host, 8, cursor_y + 10, inner_w - 16, "Persönlichkeit & Motivation")
    cursor_y = _create_concept_text_edit(host, 8, cursor_y, inner_w - 16, "Motivation", concept, "motivation", 104)
    cursor_y = _create_concept_text_edit(host, 8, cursor_y + 14, inner_w - 16, "Kurzbeschreibung", concept, "description", 128)

    host.setMinimumSize(inner_w, max(body_h, cursor_y + 12))
    scroll.setWidget(host)
    scroll.show()

    _render_bio_species_reference(window, panel, pad + left_w + gap, pad, ref_w, body_h, state)


def _create_bio_section_heading(parent, x, y, w, text):
    title = QLabel(parent)
    title.setGeometry(x, y, w, 26)
    title.setText(text)
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 18px; font-weight: 800;")
    title.show()

    line = QLabel(parent)
    line.setGeometry(x, y + 30, w, 2)
    line.setStyleSheet("background: rgba(160, 110, 35, 150);")
    line.show()
    return y + 44


def _render_creator_paradigms_editor(window, parent, x, y, w, state):
    paradigms = state.setdefault("paradigms", [{"name": "", "grad": 1}, {"name": "", "grad": 1}, {"name": "", "grad": 1}])
    y = _create_bio_section_heading(parent, x, y, w, "Paradigmen / Wesentlichkeiten")
    row_h = 42
    for index in range(3):
        entry = paradigms[index] if index < len(paradigms) and isinstance(paradigms[index], dict) else {"name": "", "grad": 1}
        paradigms[index] = entry
        label = QLabel(parent)
        label.setGeometry(x, y + 8, 92, 28)
        label.setText(f"Paradigma {index + 1}")
        label.setStyleSheet("background: transparent; color: #e2c678; font-size: 13px; font-weight: 800;")
        label.show()

        editor = QLineEdit(parent)
        editor.setGeometry(x + 102, y + 4, max(140, w - 248), 34)
        editor.setText(str(entry.get("name", "") or ""))
        editor.setPlaceholderText("Name / Wesentlichkeit")
        editor.setStyleSheet(_concept_input_style())
        editor.textChanged.connect(lambda value, target=entry: target.__setitem__("name", value))
        editor.show()

        grad = QComboBox(parent)
        grad.setGeometry(x + w - 132, y + 4, 132, 34)
        grad.addItem("Grad 1", 1)
        grad.addItem("Grad 2", 2)
        grad.setCurrentIndex(1 if int(entry.get("grad", 1) or 1) == 2 else 0)
        grad.setStyleSheet(_concept_input_style())
        grad.currentIndexChanged.connect(
            lambda _idx, target=entry, widget=grad: target.__setitem__("grad", int(widget.currentData() or 1))
        )
        grad.show()
        y += row_h
    return y + 4


def _render_bio_species_reference(window, parent, x, y, w, h, state):
    species = _species_by_id(state.get("species_id"))

    portrait_size = max(92, min(116, w - 70, int(h * 0.30)))
    portrait_x = x + ((w - portrait_size) // 2)
    portrait_y = y + 18
    image = QLabel(parent)
    image.setGeometry(portrait_x, portrait_y, portrait_size, portrait_size)
    image.setAlignment(Qt.AlignCenter)
    image.setStyleSheet(
        "background: transparent; color: #d5b66f; border: none; "
        "font-size: 16px; font-weight: 800;"
    )
    pixmap = _load_species_source_pixmap(window, species)
    if not state.get("species_id"):
        image.setPixmap(_species_missing_portrait_pixmap("Keine Spezies gewählt", portrait_size, portrait_size, False))
    elif pixmap.isNull():
        image.setPixmap(_species_missing_portrait_pixmap("Kein Bild vorhanden", portrait_size, portrait_size, False))
    else:
        image.setPixmap(_cached_species_portrait_pixmap(window, species, image.width(), image.height()))
    image.show()

    text_y = portrait_y + portrait_size + 14
    name = QLabel(parent)
    name.setGeometry(x + 8, text_y, w - 16, 30)
    name.setText(species["name"] if state.get("species_id") else "-")
    name.setAlignment(Qt.AlignCenter)
    name.setStyleSheet("background: transparent; color: #f2d28b; font-size: 18px; font-weight: 900;")
    name.show()

    note = QLabel(parent)
    note.setGeometry(x + 8, text_y + 34, w - 16, 24)
    note.setText("Ausgewählte Spezies" if state.get("species_id") else "Keine Spezies gewählt")
    note.setAlignment(Qt.AlignCenter)
    note.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 13px; font-weight: 700;")
    note.show()


def _concept_label(parent, x, y, w, text):
    label = QLabel(parent)
    label.setGeometry(x, y, w, 22)
    label.setText(text)
    label.setStyleSheet("background: transparent; color: #e2c678; font-size: 14px; font-weight: 800;")
    label.show()
    return label


def _create_concept_line_edit(parent, x, y, w, label_text, concept, key):
    _concept_label(parent, x, y, w, label_text)
    editor = QLineEdit(parent)
    editor.setGeometry(x, y + 26, w, 34)
    editor.setText(str(concept.get(key, "") or ""))
    editor.setStyleSheet(_concept_input_style())
    editor.textChanged.connect(lambda value, target=concept, field=key: target.__setitem__(field, value))
    editor.show()
    return editor


def _create_concept_text_edit(parent, x, y, w, label_text, concept, key, h):
    _concept_label(parent, x, y, w, label_text)
    editor = QTextEdit(parent)
    editor.setGeometry(x, y + 26, w, h)
    editor.setPlainText(str(concept.get(key, "") or ""))
    editor.setStyleSheet(_concept_input_style())
    editor.textChanged.connect(lambda target=concept, field=key, widget=editor: target.__setitem__(field, widget.toPlainText()))
    editor.show()
    return y + 26 + h


def _concept_input_style():
    return (
        "background: rgba(8, 6, 5, 210); color: #f2ead2; "
        "border: 1px solid rgba(121, 82, 34, 190); "
        "border-radius: 5px; "
        "selection-background-color: rgba(120, 76, 28, 200); "
        "font-size: 15px; padding: 7px;"
    )


def _render_attributes_step(window, panel, state):
    pad = 18
    body_w = panel.width() - (pad * 2)
    body_h = panel.height() - (pad * 2)
    attributes = state.get("attributes", {})
    body_attrs = attributes.get("body", {})
    mind_attrs = attributes.get("mind", {})
    start_ap = _creator_start_ap(state)
    start_xp = _creator_start_xp(state)
    total = _attribute_total(attributes)
    total_color = "#d86b3a" if total > start_ap else "#cdbb8a"

    outer = _create_framed_panel(window, panel, pad, pad, body_w, body_h)

    title = QLabel(outer)
    title.setGeometry(26, 22, body_w - 52, 34)
    title.setText("Attribute")
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 26px; font-weight: 800;")
    title.show()

    start_label = QLabel(outer)
    start_label.setGeometry(26, 58, 90, 28)
    start_label.setText("Startwerte")
    start_label.setStyleSheet("background: transparent; color: #e2c678; font-size: 14px; font-weight: 800;")
    start_label.show()
    _render_start_value_control(window, outer, 126, 56, "Start-AP", start_ap, 1, 50, lambda delta: _change_start_ap(window, delta))
    _render_start_value_control(window, outer, 330, 56, "Start-XP", start_xp, 0, 999999, lambda delta: _change_start_xp(window, delta), step=10)

    points = QLabel(outer)
    points.setGeometry(560, 58, max(220, body_w - 612), 26)
    points.setText(f"Verteilte AP: {total} / {start_ap}")
    points.setStyleSheet(f"background: transparent; color: {total_color}; font-size: 15px; font-weight: 700;")
    points.show()

    group_gap = 22
    group_y = 108
    group_h = 286
    group_w = (body_w - 52 - group_gap) // 2
    left_x = 26
    right_x = left_x + group_w + group_gap

    _render_attribute_group(
        window,
        outer,
        left_x,
        group_y,
        group_w,
        group_h,
        "Körper",
        "body",
        [
            ("kraft", "Kraft"),
            ("geschick", "Geschick"),
            ("zaehigkeit", "Zähigkeit"),
            ("reflex", "Reflex"),
        ],
        body_attrs,
        "#8f2f2a",
    )
    _render_attribute_group(
        window,
        outer,
        right_x,
        group_y,
        group_w,
        group_h,
        "Geist",
        "mind",
        [
            ("intelligenz", "Intelligenz"),
            ("willenskraft", "Willenskraft"),
            ("charisma", "Charisma"),
            ("sinne", "Sinne"),
        ],
        mind_attrs,
        "#2f85b7",
    )


def _render_start_value_control(window, parent, x, y, label_text, value, min_value, max_value, callback, step=1):
    label = QLabel(parent)
    label.setGeometry(x, y, 72, 30)
    label.setText(label_text)
    label.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 13px; font-weight: 800;")
    label.show()
    _create_attribute_button(window, parent, x + 76, y, 28, 30, "-", lambda: callback(-step))
    value_label = QLabel(parent)
    value_label.setGeometry(x + 108, y, 62, 30)
    value_label.setText(str(max(min_value, min(max_value, int(value or 0)))))
    value_label.setAlignment(Qt.AlignCenter)
    value_label.setStyleSheet(
        "background: rgba(9, 7, 6, 170); color: #9fc7ff; "
        "border: 1px solid rgba(160, 110, 35, 150); font-size: 15px; font-weight: 800;"
    )
    value_label.show()
    _create_attribute_button(window, parent, x + 174, y, 28, 30, "+", lambda: callback(step))


def _render_attribute_group(window, parent, x, y, w, h, title_text, group_key, rows, values, accent):
    group = QWidget(parent)
    group.setGeometry(x, y, w, h)
    group.setStyleSheet("background: transparent; border: none;")
    group.show()

    title = QLabel(group)
    title.setGeometry(0, 0, w, 32)
    title.setText(title_text)
    title.setStyleSheet(f"background: transparent; color: {accent}; font-size: 24px; font-weight: 900;")
    title.show()

    separator = QLabel(group)
    separator.setGeometry(0, 38, w, 3)
    separator.setStyleSheet(f"background: {accent};")
    separator.show()

    row_y = 58
    row_h = 44
    for attr_key, attr_label in rows:
        _render_attribute_row(window, group, 0, row_y, w, row_h, group_key, attr_key, attr_label, values, accent)
        row_y += row_h + 14


def _render_attribute_row(window, parent, x, y, w, h, group_key, attr_key, attr_label, values, accent):
    row_bg = QLabel(parent)
    row_bg.setGeometry(x, y, w, h)
    row_bg.setStyleSheet(f"background: rgba(9, 7, 6, 100); border-left: 3px solid {accent};")
    row_bg.show()

    label = QLabel(parent)
    label.setGeometry(x + 14, y, max(120, w - 182), h)
    label.setText(attr_label)
    label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    label.setStyleSheet("background: transparent; color: #e8dcc0; font-size: 17px; font-weight: 700;")
    label.show()

    minus_x = x + w - 146
    value_x = x + w - 96
    plus_x = x + w - 42
    _create_attribute_button(window, parent, minus_x, y + 7, 34, 34, "-", lambda: _change_attribute(window, group_key, attr_key, -1))

    value = QLabel(parent)
    value.setGeometry(value_x, y + 4, 42, 40)
    value.setText(str(_clamp_attribute_value(values.get(attr_key, 0))))
    value.setAlignment(Qt.AlignCenter)
    value.setStyleSheet(
        "background: rgba(9, 7, 6, 170); color: #9fc7ff; "
        "border: 1px solid rgba(160, 110, 35, 150); font-size: 22px; font-weight: 800;"
    )
    value.show()

    _create_attribute_button(window, parent, plus_x, y + 7, 34, 34, "+", lambda: _change_attribute(window, group_key, attr_key, 1))


def _create_attribute_button(window, parent, x, y, w, h, text, callback):
    button = QPushButton(parent)
    button.setGeometry(x, y, w, h)
    button.setText(text)
    button.setCursor(Qt.PointingHandCursor)
    button.setStyleSheet(
        "QPushButton { background: rgba(24, 18, 14, 185); color: #f2d28b; "
        "border: 1px solid rgba(160, 110, 35, 170); font-size: 20px; font-weight: 800; padding: 0px; }"
        "QPushButton:hover { background: rgba(80, 48, 22, 170); color: #ffffff; }"
    )
    button.clicked.connect(callback)
    button.show()
    return button


def _change_attribute(window, group_key, attr_key, delta):
    state = _ensure_creator_state(window)
    attributes = state["attributes"]
    group = attributes[group_key]
    current = _clamp_attribute_value(group.get(attr_key, 0))
    next_value = _clamp_attribute_value(current + delta)
    if delta > 0:
        before_total = _attribute_total(attributes)
        added_cost = _attribute_point_cost(next_value) - _attribute_point_cost(current)
        if before_total + added_cost > _creator_start_ap(state):
            return
    group[attr_key] = next_value
    _rerender(window)


def _change_start_ap(window, delta):
    state = _ensure_creator_state(window)
    start_values = state.setdefault("start_values", {})
    start_values["ap"] = _clamp_start_ap(_creator_start_ap(state) + int(delta or 0))
    _rerender(window)


def _change_start_xp(window, delta):
    state = _ensure_creator_state(window)
    start_values = state.setdefault("start_values", {})
    start_values["xp"] = max(0, _creator_start_xp(state) + int(delta or 0))
    _rerender(window)


def _creator_start_ap(state):
    start_values = state.get("start_values", {}) if isinstance(state.get("start_values"), dict) else {}
    return _clamp_start_ap(start_values.get("ap", 5))


def _creator_start_xp(state):
    start_values = state.get("start_values", {}) if isinstance(state.get("start_values"), dict) else {}
    return _non_negative_int(start_values.get("xp", 0))


def _clamp_start_ap(value):
    try:
        return max(1, min(50, int(value or 5)))
    except Exception:
        return 5


def _clamp_attribute_value(value):
    return max(0, min(2, int(value or 0)))


def _attribute_total(attributes):
    total = 0
    for group_key in ("body", "mind"):
        group = attributes.get(group_key, {})
        if isinstance(group, dict):
            total += sum(_attribute_point_cost(value) for value in group.values())
    return total


def _attribute_point_cost(value):
    value = _clamp_attribute_value(value)
    return (value * (value + 1)) // 2


def _attribute_raw_total(attributes):
    total = 0
    for group_key in ("body", "mind"):
        group = attributes.get(group_key, {})
        if isinstance(group, dict):
            total += sum(_clamp_attribute_value(value) for value in group.values())
    return total


def _render_skills_perks_step(window, panel, state):
    pad = 18
    body_w = panel.width() - (pad * 2)
    body_h = panel.height() - (pad * 2)
    bp_parts = _creator_bp_parts(state)
    spent_bp = bp_parts["spent"]
    remaining_bp = 25 - spent_bp

    outer = _create_framed_panel(window, panel, pad, pad, body_w, body_h)

    title = QLabel(outer)
    title.setGeometry(26, 20, body_w - 52, 32)
    title.setText("Fertigkeiten & Perks")
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 26px; font-weight: 800;")
    title.show()

    summary = QLabel(outer)
    summary.setGeometry(26, 56, body_w - 52, 28)
    remaining_color = "#d86b3a" if remaining_bp < 0 else "#cdbb8a"
    summary.setText(
        f"Start-BP: 25    Fertigkeiten: {bp_parts['skills']}    Perks: {bp_parts['perks']}    "
        f"Nachteile: -{bp_parts['disadvantages']}    Verbleibend: {remaining_bp}"
    )
    summary.setStyleSheet(f"background: transparent; color: {remaining_color}; font-size: 16px; font-weight: 800;")
    summary.show()

    status_text = _clean_string(state.get("skills_perks_status"))
    section_y = 98
    if status_text:
        status = QLabel(outer)
        status.setGeometry(26, 84, body_w - 52, 22)
        status.setText(status_text)
        status.setStyleSheet("background: transparent; color: #d8aa4c; font-size: 13px; font-weight: 700;")
        status.show()
        section_y = 114
    section_h = max(260, body_h - section_y - 24)
    gap = 22
    left_w = int((body_w - 52 - gap) * 0.58)
    right_w = body_w - 52 - gap - left_w
    _render_creator_skills_panel(window, outer, 26, section_y, left_w, section_h, state)
    _render_creator_perks_panel(window, outer, 26 + left_w + gap, section_y, right_w, section_h, state)


def _render_creator_skills_panel(window, parent, x, y, w, h, state):
    panel = _create_framed_panel(window, parent, x, y, w, h)
    heading = QLabel(panel)
    heading.setGeometry(18, 14, w - 36, 28)
    heading.setText("Fertigkeiten")
    heading.setStyleSheet("background: transparent; color: #f2d28b; font-size: 22px; font-weight: 800;")
    heading.show()
    line = QLabel(panel)
    line.setGeometry(18, 48, w - 36, 2)
    line.setStyleSheet("background: rgba(160, 110, 35, 170);")
    line.show()

    scroll = QScrollArea(panel)
    scroll.setGeometry(14, 62, w - 28, h - 76)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: #17110f; width: 12px; }"
        "QScrollBar::handle:vertical { background: #6c4a22; min-height: 24px; }"
    )
    host = QWidget(scroll)
    host.setStyleSheet("background: transparent;")
    inner_w = max(360, w - 58)
    cursor_y = 8

    for category in _creator_skill_categories(window):
        category_title = QLabel(host)
        category_title.setGeometry(8, cursor_y, inner_w - 16, 24)
        category_title.setText(str(category.get("title", "Fertigkeiten") or "Fertigkeiten"))
        category_title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 16px; font-weight: 800;")
        category_title.show()
        cursor_y += 30
        for skill in category.get("skills", []):
            cursor_y = _render_creator_skill_row(window, host, 8, cursor_y, inner_w - 16, skill, state) + 8
        cursor_y += 8

    host.setMinimumSize(inner_w, max(h - 76, cursor_y + 8))
    scroll.setWidget(host)
    scroll.show()


def _render_creator_skill_row(window, parent, x, y, w, skill, state):
    skill_id = str(skill.get("id", "") or "").strip()
    if not skill_id:
        skill_id = _sanitize_filename(str(skill.get("name", "skill") or "skill")).lower()
    skills_state = state.setdefault("skills", {})
    entry = skills_state.setdefault(skill_id, {"selected": False, "active": False, "attribute": "", "specialization": ""})
    entry.setdefault("selected", bool(entry.get("active", False)))
    entry.setdefault("attribute", "")
    entry.setdefault("specialization", "")
    allowed_options = _creator_skill_attribute_options(skill)
    current_attribute = _canonical_creator_attribute(entry.get("attribute"))
    if current_attribute not in {code for code, _label in allowed_options}:
        current_attribute = ""
        entry["attribute"] = ""
    locked = _creator_skill_is_locked(state, skill)
    selected = bool(entry.get("selected", False)) and not locked
    if selected and not current_attribute and len(allowed_options) == 1:
        current_attribute = allowed_options[0][0]
        entry["attribute"] = current_attribute
    active = _creator_skill_is_active(entry) and selected and not locked
    entry["active"] = active
    row_h = 66

    row = QWidget(parent)
    row.setGeometry(x, y, w, row_h)
    row.setStyleSheet("background: rgba(9, 7, 6, 95); border: none;")

    _create_creator_skill_checkbox(window, row, 0, 16, 26, 26, selected, locked, lambda: _toggle_creator_skill(window, skill_id))

    name = QLabel(row)
    name.setGeometry(36, 0, max(130, w - 344), 30)
    name.setText(str(skill.get("name", skill_id) or skill_id))
    name_color = "#766c5c" if locked else "#e8dcc0"
    name.setStyleSheet(f"background: transparent; color: {name_color}; font-size: 14px; font-weight: 800;")
    name.show()

    attr = QComboBox(row)
    attr.setGeometry(w - 298, 2, 112, 30)
    attr.addItem("-", "")
    for code, label in allowed_options:
        attr.addItem(label, code)
    selected_index = attr.findData(current_attribute)
    if selected_index >= 0:
        attr.setCurrentIndex(selected_index)
    attr.setStyleSheet(_concept_input_style())
    attr.setEnabled(selected and not locked)
    attr.currentIndexChanged.connect(
        lambda _index, target=entry, widget=attr: _set_creator_skill_attribute(window, target, widget)
    )
    attr.show()

    spec = QLineEdit(row)
    spec.setGeometry(36, 34, w - 36, 30)
    spec.setText(str(entry.get("specialization", "") or ""))
    spec.setPlaceholderText("Spezialisierung")
    spec.setStyleSheet(_concept_input_style())
    spec.setEnabled(selected and not locked)
    cost = QLabel(row)
    cost.setGeometry(w - 176, 2, 176, 30)
    if locked:
        state_text = "gesperrt"
    elif active:
        state_text = "1 BP"
    elif selected:
        state_text = "unvollständig"
    else:
        state_text = "inaktiv"
    cost.setText(state_text)
    cost.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    cost.setStyleSheet(f"background: transparent; color: {'#f2d28b' if active else '#9a8560'}; font-size: 13px; font-weight: 800;")
    cost.show()
    spec.textChanged.connect(
        lambda value, target=entry, cost_label=cost: _set_creator_skill_specialization(
            value, target, cost_label
        )
    )
    spec.editingFinished.connect(lambda target=entry: _sync_creator_skill_activation(window, target))
    spec.show()

    row.show()
    return y + row_h


def _render_creator_perks_panel(window, parent, x, y, w, h, state):
    panel = _create_framed_panel(window, parent, x, y, w, h)
    heading = QLabel(panel)
    heading.setGeometry(18, 14, w - 36, 28)
    heading.setText("Perks & Nachteile")
    heading.setStyleSheet("background: transparent; color: #f2d28b; font-size: 22px; font-weight: 800;")
    heading.show()
    line = QLabel(panel)
    line.setGeometry(18, 48, w - 36, 2)
    line.setStyleSheet("background: rgba(160, 110, 35, 170);")
    line.show()

    half_h = max(150, (h - 68) // 2)
    _render_creator_catalog_section(
        window,
        panel,
        14,
        62,
        w - 28,
        half_h,
        state,
        "perks",
        "Perks",
        "Perk hinzufügen",
        "Noch keine Perks hinzugefügt.",
        "perk",
    )
    _render_creator_catalog_section(
        window,
        panel,
        14,
        70 + half_h,
        w - 28,
        max(150, h - half_h - 84),
        state,
        "disadvantages",
        "Nachteile",
        "Nachteil hinzufügen",
        "Noch keine Nachteile hinzugefügt.",
        "disadvantage",
    )


def _render_creator_catalog_section(
    window, parent, x, y, w, h, state, list_key, title, button_text, empty_text, entry_type
):
    title_label = QLabel(parent)
    title_label.setGeometry(x + 4, y, max(80, w - 178), 28)
    title_label.setText(title)
    title_label.setStyleSheet("background: transparent; color: #e8dcc0; font-size: 15px; font-weight: 800;")
    title_label.show()

    _create_attribute_button(
        window,
        parent,
        x + max(0, w - 162),
        y,
        min(158, w),
        30,
        button_text,
        lambda: _add_creator_catalog_entry(window, list_key, entry_type),
    )

    scroll = QScrollArea(parent)
    scroll.setGeometry(x, y + 36, w, max(80, h - 40))
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: #17110f; width: 12px; }"
        "QScrollBar::handle:vertical { background: #6c4a22; min-height: 24px; }"
    )
    host = QWidget(scroll)
    host.setStyleSheet("background: transparent;")
    inner_w = max(260, w - 30)
    cursor_y = 8
    entries = state.setdefault(list_key, [])
    if not entries:
        empty = QLabel(host)
        empty.setGeometry(8, cursor_y, inner_w - 16, 30)
        empty.setText(empty_text)
        empty.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 14px; font-weight: 700;")
        empty.show()
        cursor_y += 38
    for index, entry in enumerate(entries):
        cursor_y = _render_creator_catalog_entry_row(window, host, 8, cursor_y, inner_w - 16, list_key, index, entry) + 8
    host.setMinimumSize(inner_w, max(80, cursor_y + 8))
    scroll.setWidget(host)
    scroll.show()


def _render_creator_catalog_entry_row(window, parent, x, y, w, list_key, index, entry):
    row_h = 78
    row = QWidget(parent)
    row.setGeometry(x, y, w, row_h)
    row.setStyleSheet("background: rgba(9, 7, 6, 105); border: 1px solid rgba(160, 110, 35, 110);")
    entry = entry if isinstance(entry, dict) else {}

    name = QLabel(row)
    name.setGeometry(10, 8, max(120, w - 72), 24)
    name.setText(str(entry.get("name", "") or "Unbenannter Eintrag"))
    name.setStyleSheet("background: transparent; color: #f2d28b; font-size: 14px; font-weight: 800;")
    name.show()

    bp = QLabel(row)
    bp.setGeometry(w - 58, 8, 32, 24)
    bp.setText(str(_perk_bp_value(entry)))
    bp.setAlignment(Qt.AlignCenter)
    bp.setStyleSheet("background: rgba(9, 7, 6, 170); color: #9fc7ff; border: 1px solid rgba(160, 110, 35, 150); font-size: 13px; font-weight: 800;")
    bp.show()

    effect = QLabel(row)
    effect.setGeometry(10, 36, max(120, w - 52), 34)
    effect.setText(str(entry.get("effect", "") or entry.get("description", "") or ""))
    effect.setWordWrap(True)
    effect.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 12px; font-weight: 600;")
    effect.show()

    _create_attribute_button(window, row, w - 30, 48, 24, 24, "×", lambda: _remove_creator_catalog_entry(window, list_key, index))
    row.show()
    return y + row_h


def _creator_skill_categories(window):
    try:
        definitions = window.load_skill_definitions()
        categories = definitions.get("categories", []) if isinstance(definitions, dict) else []
        if isinstance(categories, list) and categories:
            return categories
    except Exception:
        pass
    return [
        {"id": "allgemein", "title": "Allgemein", "skills": [{"id": "allgemein_probe", "name": "Allgemeine Probe"}]},
        {"id": "kampf", "title": "Kampf", "skills": [{"id": "nahkampf", "name": "Nahkampf"}]},
        {"id": "wissen", "title": "Wissen", "skills": [{"id": "geschichte", "name": "Geschichte"}]},
        {"id": "handwerk", "title": "Handwerk", "skills": [{"id": "reparieren", "name": "Reparieren"}]},
    ]


def _create_creator_skill_checkbox(window, parent, x, y, w, h, checked, locked, callback):
    icon = QLabel(parent)
    icon.setGeometry(x, y, w, h)
    asset = "ui_elements/icons/checkmark_true.png" if checked else "ui_elements/icons/checkmark_false.png"
    pixmap = window.load_ui_pixmap(asset)
    if pixmap is not None and not pixmap.isNull():
        icon.setPixmap(pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
    else:
        icon.setText("X" if checked else "")
        icon.setAlignment(Qt.AlignCenter)
    opacity = "90" if locked else "190"
    icon.setStyleSheet(f"background: rgba(12, 9, 7, {opacity}); border: none;")
    icon.show()

    button = QPushButton(parent)
    button.setGeometry(x, y, w, h)
    button.setText("")
    button.setEnabled(not locked)
    button.setCursor(Qt.PointingHandCursor if not locked else Qt.ArrowCursor)
    button.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0px; }")
    button.clicked.connect(lambda checked=False: callback())
    button.raise_()
    button.show()
    return button


def _canonical_creator_attribute(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return CREATOR_ATTRIBUTE_ALIASES.get(text.upper(), "")


def _creator_skill_attribute_options(skill):
    raw_values = skill.get("attributes", []) if isinstance(skill, dict) else []
    allowed = []
    if isinstance(raw_values, list):
        for value in raw_values:
            code = _canonical_creator_attribute(value)
            if code and code not in allowed:
                allowed.append(code)
    if not allowed:
        note = str(skill.get("note", "") if isinstance(skill, dict) else "").casefold()
        body = [code for code, _label in CREATOR_ATTRIBUTE_OPTIONS[:4]]
        mind = [code for code, _label in CREATOR_ATTRIBUTE_OPTIONS[4:]]
        if "körper" in note or "koerper" in note:
            allowed = body
        elif "geist" in note:
            allowed = mind
        else:
            allowed = body + mind
        if "freie wahl" in note or ("körper" in note and "geist" in note) or ("koerper" in note and "geist" in note):
            allowed = body + mind
    label_by_code = dict(CREATOR_ATTRIBUTE_OPTIONS)
    return [(code, label_by_code.get(code, code)) for code in allowed if code in label_by_code]


def _creator_skill_is_active(entry):
    if not isinstance(entry, dict):
        return False
    selected = bool(entry.get("selected", entry.get("active", False)))
    return bool(selected and _canonical_creator_attribute(entry.get("attribute")) and _clean_string(entry.get("specialization")))


def _set_creator_skill_attribute(window, entry, combo):
    entry["attribute"] = str(combo.currentData() or "")
    entry["active"] = _creator_skill_is_active(entry)
    _rerender(window)


def _set_creator_skill_specialization(value, entry, cost_label):
    entry["specialization"] = value
    active = _creator_skill_is_active(entry)
    entry["active"] = active
    if active:
        state_text = "1 BP"
    elif bool(entry.get("selected", entry.get("active", False))):
        state_text = "unvollständig"
    else:
        state_text = "inaktiv"
    cost_label.setText(state_text)
    cost_label.setStyleSheet(
        f"background: transparent; color: {'#f2d28b' if active else '#9a8560'}; font-size: 13px; font-weight: 800;"
    )


def _sync_creator_skill_activation(window, entry):
    entry["active"] = _creator_skill_is_active(entry)
    _rerender(window)


def _toggle_creator_skill(window, skill_id):
    state = _ensure_creator_state(window)
    entry = state["skills"].setdefault(skill_id, {"selected": False, "active": False, "attribute": "", "specialization": ""})
    entry["selected"] = not bool(entry.get("selected", False))
    entry["active"] = _creator_skill_is_active(entry)
    _rerender(window)


def _creator_skill_is_locked(state, skill):
    skill_id = str(skill.get("id", "") if isinstance(skill, dict) else "").strip().casefold()
    skill_name = str(skill.get("name", "") if isinstance(skill, dict) else "").strip().casefold()
    if skill_id != "magieanwendung" and "magieanwendung" not in skill_name and "magie anwenden" not in skill_name:
        return False
    return not _creator_has_magic_user_perk(state)


def _creator_has_magic_user_perk(state):
    perks = state.get("perks", []) if isinstance(state.get("perks"), list) else []
    for perk in perks:
        if not isinstance(perk, dict):
            continue
        perk_id = str(perk.get("id", "") or "").strip().casefold()
        perk_name = str(perk.get("name", "") or "").strip().casefold()
        if perk_id == "magie_anwender" or perk_name == "magieanwender":
            return True
    return False


def _add_creator_catalog_entry(window, list_key, entry_type):
    state = _ensure_creator_state(window)
    result = open_perk_picker(window, entry_type)
    if not isinstance(result, dict) or result.get("action") != "select":
        return
    entry = _normalize_creator_catalog_entry(result.get("entry"), entry_type)
    if not entry:
        return
    entries = state.setdefault(list_key, [])
    entry_id = str(entry.get("id", "") or "").strip()
    if entry_id and any(isinstance(existing, dict) and str(existing.get("id", "") or "").strip() == entry_id for existing in entries):
        state["skills_perks_status"] = f"{entry.get('name', 'Eintrag')} ist bereits ausgewählt."
        _rerender(window)
        return
    entries.append(entry)
    state["skills_perks_status"] = ""
    _rerender(window)


def _remove_creator_catalog_entry(window, list_key, index):
    state = _ensure_creator_state(window)
    entries = state.get(list_key, [])
    if isinstance(entries, list) and 0 <= index < len(entries):
        entries.pop(index)
    _rerender(window)


def _normalize_creator_catalog_entry(entry, entry_type):
    if not isinstance(entry, dict):
        return {}
    clean = {}
    for key in (
        "id",
        "name",
        "type",
        "category",
        "bp",
        "effect",
        "description",
        "species",
        "requirements",
        "tags",
        "source",
        "level",
        "selected_level",
        "max_level",
        "upgrade_of",
    ):
        if key in entry:
            clean[key] = entry.get(key)
    clean["type"] = entry_type
    clean["name"] = _clean_string(clean.get("name"))
    clean["effect"] = _clean_string(clean.get("effect") or clean.get("description"))
    clean["bp"] = _perk_bp_value(clean)
    return clean if clean.get("name") or clean.get("id") else {}


def _perk_bp_value(perk):
    try:
        return max(0, int(perk.get("bp", 0) or 0))
    except Exception:
        return 0


def _creator_spent_bp(state):
    return _creator_bp_parts(state)["spent"]


def _creator_bp_parts(state):
    skills = state.get("skills", {})
    skill_bp = sum(1 for entry in skills.values() if isinstance(entry, dict) and _creator_skill_is_active(entry))
    perks = state.get("perks", [])
    perk_bp = sum(_perk_bp_value(perk) for perk in perks if isinstance(perk, dict))
    disadvantages = state.get("disadvantages", [])
    disadvantage_bp = sum(_perk_bp_value(disadvantage) for disadvantage in disadvantages if isinstance(disadvantage, dict))
    return {
        "skills": skill_bp,
        "perks": perk_bp,
        "disadvantages": disadvantage_bp,
        "spent": skill_bp + perk_bp - disadvantage_bp,
    }


def build_character_state(window) -> dict:
    state = getattr(window, "_character_creator_state", None)
    if not isinstance(state, dict):
        state = {}
    species = _species_by_id(state.get("species_id"))
    concept = state.get("concept", {}) if isinstance(state.get("concept"), dict) else {}
    attributes = state.get("attributes", {}) if isinstance(state.get("attributes"), dict) else {}
    start_values_src = state.get("start_values", {}) if isinstance(state.get("start_values"), dict) else {}
    clean_start_values = {
        "ap": _clamp_start_ap(start_values_src.get("ap", 5)),
        "xp": _non_negative_int(start_values_src.get("xp", 0)),
    }
    body_src = attributes.get("body", {}) if isinstance(attributes.get("body"), dict) else {}
    mind_src = attributes.get("mind", {}) if isinstance(attributes.get("mind"), dict) else {}
    body = {
        "kraft": _clamp_attribute_value(body_src.get("kraft", 0)),
        "geschick": _clamp_attribute_value(body_src.get("geschick", 0)),
        "zaehigkeit": _clamp_attribute_value(body_src.get("zaehigkeit", 0)),
        "reflex": _clamp_attribute_value(body_src.get("reflex", 0)),
    }
    mind = {
        "intelligenz": _clamp_attribute_value(mind_src.get("intelligenz", 0)),
        "willenskraft": _clamp_attribute_value(mind_src.get("willenskraft", 0)),
        "charisma": _clamp_attribute_value(mind_src.get("charisma", 0)),
        "sinne": _clamp_attribute_value(mind_src.get("sinne", 0)),
    }
    clean_attributes = {
        "body": body,
        "mind": mind,
        "total": _attribute_total({"body": body, "mind": mind}),
        "raw_total": _attribute_raw_total({"body": body, "mind": mind}),
    }
    clean_skills = _build_clean_skills(window, state)
    clean_perks = _build_clean_perks(state)
    clean_disadvantages = _build_clean_catalog_entries(state, "disadvantages", "disadvantage")
    clean_paradigms = _build_clean_paradigms(state)
    clean_equipment = _build_clean_equipment(state)
    skill_bp = sum(int(skill.get("bp", 0) or 0) for skill in clean_skills)
    perk_bp = sum(int(perk.get("bp", 0) or 0) for perk in clean_perks)
    disadvantage_bp = sum(int(disadvantage.get("bp", 0) or 0) for disadvantage in clean_disadvantages)
    spent_bp = skill_bp + perk_bp - disadvantage_bp
    return {
        "version": 1,
        "status": "draft",
        "species": {
            "id": str(species.get("id", "") or ""),
            "name": str(species.get("name", "") or ""),
            "perks": list(species.get("perks", []) or []),
            "notes": "\n".join(value for value in (species.get("bp_bonus"), species.get("notes")) if value),
        },
        "concept": {
            "character_name": _clean_string(concept.get("character_name")),
            "player_name": _clean_string(concept.get("player_name")),
            "short_concept": _clean_string(concept.get("short_concept")),
            "origin": _clean_string(concept.get("origin")),
            "role": _clean_string(concept.get("role")),
            "motivation": _clean_string(concept.get("motivation")),
            "description": _clean_string(concept.get("description")),
        },
        "start_values": clean_start_values,
        "attributes": clean_attributes,
        "paradigms": clean_paradigms,
        "skills": clean_skills,
        "perks": clean_perks,
        "disadvantages": clean_disadvantages,
        "equipment": clean_equipment,
        "bp": {
            "base": 25,
            "start_ap": clean_start_values["ap"],
            "start_xp": clean_start_values["xp"],
            "skills": skill_bp,
            "perks": perk_bp,
            "disadvantages": disadvantage_bp,
            "spent": spent_bp,
            "remaining": 25 - spent_bp,
        },
        "meta": {
            "created_by": "character_creator",
            "saved": False,
        },
    }


def save_character_state(window) -> tuple[bool, str]:
    try:
        character_state = build_character_state(window)
        character_state["status"] = "created"
        meta = character_state.setdefault("meta", {})
        meta["saved"] = True
        meta["save_format"] = "character_creator_json"
        meta["source"] = "character_creator"
        meta["saved_at"] = datetime.now(timezone.utc).isoformat()

        character_name = character_state.get("concept", {}).get("character_name", "")
        safe_name = _sanitize_created_character_filename(character_name) or "unnamed_character"
        save_dir = data_path("characters/.keep").parent
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = _next_available_character_path(save_dir, safe_name)
        save_path.write_text(json.dumps(character_state, ensure_ascii=False, indent=2), encoding="utf-8")
        return True, str(save_path)
    except Exception as exc:
        return False, str(exc)


def finalize_character_state(window) -> tuple[bool, str]:
    try:
        character_state = build_character_state(window)
        character_name = _clean_string(character_state.get("concept", {}).get("character_name"))
        if not character_name:
            return False, "Charaktername fehlt."

        slug = window.loader.make_character_slug(character_name)
        if not slug or slug == "unknown_character":
            return False, "Aus dem Charakternamen konnte kein gültiger Dateiname erzeugt werden."

        character_state["status"] = "created"
        meta = character_state.setdefault("meta", {})
        meta["saved"] = True
        meta["save_format"] = "cell_cache"
        meta["source"] = "character_creator"
        meta["saved_at"] = datetime.now(timezone.utc).isoformat()

        save_dir = Path(window.loader.get_character_dir())
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = _next_available_character_path(save_dir, slug)

        if not window.loader.finalize_creator_state(character_state, str(save_path)):
            return False, "Konvertierung in normale Charakterdaten fehlgeschlagen."

        window._start_screen_mode = "menu"
        window.reset_character_runtime_state()
        window.create_tabs_from_cache()
        window.show_main_section("character")
        log_debug("creator", f"finalized character: {save_path}")
        return True, str(save_path)
    except Exception as exc:
        log_error("creator", f"finalize failed: {exc}")
        return False, str(exc)


def load_character_state_from_file(path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _sanitize_created_character_filename(value):
    text = str(value or "").strip()
    for char in '\\/:*?"<>|':
        text = text.replace(char, "_")
    text = text.strip(" .")
    return text


def _next_available_character_path(save_dir, safe_name):
    candidate = save_dir / f"{safe_name}.json"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = save_dir / f"{safe_name}_{index}.json"
        if not candidate.exists():
            return candidate
        index += 1


def _build_clean_skills(window, state):
    skills = state.get("skills", {}) if isinstance(state.get("skills"), dict) else {}
    name_map = _creator_skill_name_map(window)
    clean = []
    for skill_id, entry in skills.items():
        if not isinstance(entry, dict) or not _creator_skill_is_active(entry):
            continue
        clean.append(
            {
                "id": str(skill_id),
                "name": name_map.get(str(skill_id), str(skill_id)),
                "attribute": _canonical_creator_attribute(entry.get("attribute")),
                "specialization": _clean_string(entry.get("specialization")),
                "bp": 1,
            }
        )
    return clean


def _creator_skill_name_map(window):
    names = {}
    for category in _creator_skill_categories(window):
        for skill in category.get("skills", []):
            if isinstance(skill, dict) and skill.get("id"):
                names[str(skill.get("id"))] = str(skill.get("name", skill.get("id")) or skill.get("id"))
    return names


def _build_clean_perks(state):
    return _build_clean_catalog_entries(state, "perks", "perk")


def _build_clean_paradigms(state):
    paradigms = state.get("paradigms", []) if isinstance(state.get("paradigms"), list) else []
    clean = []
    for index in range(3):
        entry = paradigms[index] if index < len(paradigms) and isinstance(paradigms[index], dict) else {}
        clean.append(
            {
                "name": _clean_string(entry.get("name")),
                "grad": 2 if int(entry.get("grad", 1) or 1) == 2 else 1,
            }
        )
    return clean


def _build_clean_catalog_entries(state, list_key, entry_type):
    perks = state.get(list_key, []) if isinstance(state.get(list_key), list) else []
    clean = []
    for perk in perks:
        if not isinstance(perk, dict):
            continue
        name = _clean_string(perk.get("name"))
        bp = _perk_bp_value(perk)
        effect = _clean_string(perk.get("effect"))
        if name or bp or effect or perk.get("id"):
            clean_entry = {
                "id": _clean_string(perk.get("id")),
                "name": name,
                "type": _clean_string(perk.get("type") or entry_type),
                "category": _clean_string(perk.get("category")),
                "bp": bp,
                "effect": effect,
            }
            for key in ("description", "species", "requirements", "tags", "source", "level", "selected_level", "max_level", "upgrade_of"):
                if key in perk:
                    clean_entry[key] = perk.get(key)
            clean.append(clean_entry)
    return clean


def _build_clean_equipment(state):
    equipment = state.get("equipment", {}) if isinstance(state.get("equipment"), dict) else {}
    money = equipment.get("money", {}) if isinstance(equipment.get("money"), dict) else {}
    return {
        "money": {
            "gulden": _non_negative_int(money.get("gulden")),
            "schilling": _non_negative_int(money.get("schilling")),
            "heller": _non_negative_int(money.get("heller")),
        },
        "items": _clean_equipment_rows(equipment.get("items", [])),
        "weapons": _clean_equipment_rows(equipment.get("weapons", [])),
        "armor": _clean_equipment_rows(equipment.get("armor", [])),
        "notes": _clean_string(equipment.get("notes")),
    }


def _clean_equipment_rows(rows):
    if not isinstance(rows, list):
        return []
    clean = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean_row = {str(key): _clean_string(value) for key, value in row.items()}
        if any(str(value).strip() for value in clean_row.values()):
            clean.append(clean_row)
    return clean


def _clean_string(value):
    return str(value or "").strip()


def _render_equipment_step(window, panel, state):
    pad = 18
    body_w = panel.width() - (pad * 2)
    body_h = panel.height() - (pad * 2)
    equipment = state.get("equipment", {})

    outer = _create_framed_panel(window, panel, pad, pad, body_w, body_h)
    scroll = QScrollArea(outer)
    scroll.setGeometry(14, 14, body_w - 28, body_h - 28)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: #17110f; width: 12px; }"
        "QScrollBar::handle:vertical { background: #6c4a22; min-height: 24px; }"
    )

    host = QWidget(scroll)
    host.setStyleSheet("background: transparent;")
    inner_w = max(720, body_w - 58)
    cursor_y = 10

    title = QLabel(host)
    title.setGeometry(8, cursor_y, inner_w - 16, 34)
    title.setText("Ausrüstung")
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 26px; font-weight: 800;")
    title.show()
    cursor_y += 42

    hint = QLabel(host)
    hint.setGeometry(8, cursor_y, inner_w - 16, 24)
    hint.setText("Ausrüstungskosten/BP werden später verrechnet.")
    hint.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 14px; font-weight: 700;")
    hint.show()
    cursor_y += 38

    cursor_y = _render_equipment_money_section(host, 8, cursor_y, inner_w - 16, equipment) + 16
    cursor_y = _render_equipment_list_section(
        window,
        host,
        8,
        cursor_y,
        inner_w - 16,
        "Inventar / Startausrüstung",
        "Item hinzufügen",
        equipment["items"],
        [
            ("name", "Name", 0.36),
            ("pl", "PL", 0.12),
            ("count", "Anzahl", 0.14),
            ("note", "Notiz", 0.30),
        ],
        lambda: _add_equipment_row(window, "items", {"name": "", "pl": "", "count": "1", "note": ""}),
        "items",
    ) + 16
    cursor_y = _render_equipment_list_section(
        window,
        host,
        8,
        cursor_y,
        inner_w - 16,
        "Waffen",
        "Waffe hinzufügen",
        equipment["weapons"],
        [
            ("name", "Name", 0.28),
            ("damage", "Schaden / Effekt", 0.26),
            ("attribute", "Attribut / Fertigkeit", 0.24),
            ("note", "Notiz", 0.18),
        ],
        lambda: _add_equipment_row(window, "weapons", {"name": "", "damage": "", "attribute": "", "note": ""}),
        "weapons",
    ) + 16
    cursor_y = _render_equipment_list_section(
        window,
        host,
        8,
        cursor_y,
        inner_w - 16,
        "Rüstung",
        "Rüstung hinzufügen",
        equipment["armor"],
        [
            ("name", "Name", 0.34),
            ("protection", "Schutz / Werte", 0.28),
            ("note", "Notiz", 0.30),
        ],
        lambda: _add_equipment_row(window, "armor", {"name": "", "protection": "", "note": ""}),
        "armor",
    ) + 16

    cursor_y = _render_equipment_notes_section(host, 8, cursor_y, inner_w - 16, equipment) + 12

    host.setMinimumSize(inner_w, max(body_h - 28, cursor_y))
    scroll.setWidget(host)
    scroll.show()


def _render_equipment_money_section(parent, x, y, w, equipment):
    money = equipment.get("money", {})
    section_h = 86
    _section_heading(parent, x, y, w, "Startgeld")
    fields = [("gulden", "Gulden"), ("schilling", "Schilling"), ("heller", "Heller")]
    field_w = (w - 32) // 3
    for index, (key, label_text) in enumerate(fields):
        field_x = x + (index * (field_w + 16))
        _concept_label(parent, field_x, y + 34, field_w, label_text)
        editor = QLineEdit(parent)
        editor.setGeometry(field_x, y + 58, field_w, 30)
        editor.setText(str(_non_negative_int(money.get(key, 0))))
        editor.setStyleSheet(_concept_input_style())
        editor.textChanged.connect(lambda value, target=money, field=key: target.__setitem__(field, _non_negative_int(value)))
        editor.show()
    return y + section_h


def _render_equipment_list_section(window, parent, x, y, w, title, add_text, rows, columns, add_callback, list_key):
    row_h = 42
    section_h = 78 + max(1, len(rows)) * row_h
    _section_heading(parent, x, y, w, title)
    _create_attribute_button(window, parent, x + w - 190, y, 190, 32, add_text, add_callback)
    header_y = y + 40
    cursor_y = y + 64
    if not rows:
        empty = QLabel(parent)
        empty.setGeometry(x, cursor_y, w, 26)
        empty.setText("Noch keine Einträge.")
        empty.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 14px; font-weight: 700;")
        empty.show()
        return y + section_h

    col_x = x
    usable_w = w - 34
    col_widths = []
    for _, label_text, ratio in columns:
        col_w = int(usable_w * ratio)
        col_widths.append(col_w)
        label = QLabel(parent)
        label.setGeometry(col_x, header_y, col_w - 8, 20)
        label.setText(label_text)
        label.setStyleSheet("background: transparent; color: #f2d28b; font-size: 13px; font-weight: 800;")
        label.show()
        col_x += col_w

    for row_index, row_data in enumerate(rows):
        col_x = x
        row_y = cursor_y + (row_index * row_h)
        for col_index, (key, _, _) in enumerate(columns):
            col_w = col_widths[col_index]
            editor = QLineEdit(parent)
            editor.setGeometry(col_x, row_y, col_w - 8, 30)
            editor.setText(str(row_data.get(key, "") or ""))
            editor.setStyleSheet(_concept_input_style())
            editor.textChanged.connect(lambda value, target=row_data, field=key: target.__setitem__(field, value))
            editor.show()
            col_x += col_w
        remove = QPushButton(parent)
        remove.setGeometry(x + w - 28, row_y, 28, 30)
        remove.setText("X")
        remove.setCursor(Qt.PointingHandCursor)
        remove.setStyleSheet(
            "QPushButton { background: rgba(24, 18, 14, 185); color: #d86b3a; "
            "border: 1px solid rgba(160, 110, 35, 170); font-size: 14px; font-weight: 900; padding: 0px; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        remove.clicked.connect(lambda checked=False, key=list_key, idx=row_index: _remove_equipment_row(window, key, idx))
        remove.show()
    return y + section_h


def _render_equipment_notes_section(parent, x, y, w, equipment):
    _section_heading(parent, x, y, w, "Ausrüstungsnotizen")
    editor = QTextEdit(parent)
    editor.setGeometry(x, y + 38, w, 96)
    editor.setPlainText(str(equipment.get("notes", "") or ""))
    editor.setStyleSheet(_concept_input_style())
    editor.textChanged.connect(lambda target=equipment, widget=editor: target.__setitem__("notes", widget.toPlainText()))
    editor.show()
    return y + 138


def _section_heading(parent, x, y, w, text):
    title = QLabel(parent)
    title.setGeometry(x, y, w, 28)
    title.setText(text)
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 18px; font-weight: 800;")
    title.show()
    line = QLabel(parent)
    line.setGeometry(x, y + 30, w, 2)
    line.setStyleSheet("background: rgba(160, 110, 35, 170);")
    line.show()


def _add_equipment_row(window, list_key, template):
    state = _ensure_creator_state(window)
    state["equipment"][list_key].append(dict(template))
    _rerender(window)


def _remove_equipment_row(window, list_key, index):
    state = _ensure_creator_state(window)
    rows = state["equipment"].get(list_key, [])
    if 0 <= index < len(rows):
        rows.pop(index)
    _rerender(window)


def _non_negative_int(value):
    try:
        return max(0, int(str(value or "0").strip() or 0))
    except Exception:
        return 0


def _render_summary_step(window, panel, state):
    pad = 18
    body_w = panel.width() - (pad * 2)
    body_h = panel.height() - (pad * 2)
    character_state = build_character_state(window)

    outer = _create_framed_panel(window, panel, pad, pad, body_w, body_h)
    scroll = QScrollArea(outer)
    scroll.setGeometry(14, 14, body_w - 28, body_h - 74)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: #17110f; width: 12px; }"
        "QScrollBar::handle:vertical { background: #6c4a22; min-height: 24px; }"
    )

    host = QWidget(scroll)
    host.setStyleSheet("background: transparent;")
    inner_w = max(720, body_w - 58)
    cursor_y = 10

    title = QLabel(host)
    title.setGeometry(8, cursor_y, inner_w - 16, 34)
    title.setText("Zusammenfassung")
    title.setStyleSheet("background: transparent; color: #f2d28b; font-size: 26px; font-weight: 800;")
    title.show()
    cursor_y += 46

    cursor_y = _summary_species_section(host, 8, cursor_y, inner_w - 16, character_state) + 16
    cursor_y = _summary_concept_section(host, 8, cursor_y, inner_w - 16, character_state) + 16
    cursor_y = _summary_attributes_section(host, 8, cursor_y, inner_w - 16, character_state) + 16
    cursor_y = _summary_skills_section(host, 8, cursor_y, inner_w - 16, character_state) + 16
    cursor_y = _summary_perks_section(host, 8, cursor_y, inner_w - 16, character_state) + 16
    cursor_y = _summary_equipment_section(host, 8, cursor_y, inner_w - 16, character_state) + 12

    host.setMinimumSize(inner_w, max(body_h - 74, cursor_y))
    scroll.setWidget(host)
    scroll.show()

    status = QLabel(outer)
    status.setGeometry(18, body_h - 46, body_w - 240, 34)
    status.setText("")
    status.setStyleSheet("background: transparent; color: #cdbb8a; font-size: 15px; font-weight: 800;")
    status.show()
    _create_attribute_button(
        window,
        outer,
        body_w - 218,
        body_h - 48,
        200,
        36,
        "Fertigstellen",
        lambda: _finalize_character_state_from_summary(window, status),
    )


def _summary_species_section(parent, x, y, w, character_state):
    species = character_state.get("species", {})
    perks = "\n".join(f"- {perk}" for perk in species.get("perks", [])) or "-"
    notes = _dash(species.get("notes"))
    return _summary_section(
        parent,
        x,
        y,
        w,
        "Spezies",
        [
            ("Auswahl", species.get("name", "-")),
            ("Perks", perks),
            ("Notizen", notes),
        ],
    )


def _summary_concept_section(parent, x, y, w, character_state):
    concept = character_state.get("concept", {})
    return _summary_section(
        parent,
        x,
        y,
        w,
        "Biografie",
        [
            ("Charaktername", _dash(concept.get("character_name"))),
            ("Spielername", _dash(concept.get("player_name"))),
            ("Kurzkonzept", _dash(concept.get("short_concept"))),
            ("Herkunft / Kultur", _dash(concept.get("origin"))),
            ("Beruf / Rolle", _dash(concept.get("role"))),
            ("Motivation", _dash(concept.get("motivation"))),
            ("Kurzbeschreibung", _dash(concept.get("description"))),
        ],
    )


def _summary_attributes_section(parent, x, y, w, character_state):
    attributes = character_state.get("attributes", {})
    start_values = character_state.get("start_values", {}) if isinstance(character_state.get("start_values"), dict) else {}
    start_ap = _clamp_start_ap(start_values.get("ap", 5))
    start_xp = _non_negative_int(start_values.get("xp", 0))
    body = attributes.get("body", {})
    mind = attributes.get("mind", {})
    body_text = "\n".join(
        f"{label}: {_clamp_attribute_value(body.get(key, 0))}"
        for key, label in (("kraft", "Kraft"), ("geschick", "Geschick"), ("zaehigkeit", "Zähigkeit"), ("reflex", "Reflex"))
    )
    mind_text = "\n".join(
        f"{label}: {_clamp_attribute_value(mind.get(key, 0))}"
        for key, label in (("intelligenz", "Intelligenz"), ("willenskraft", "Willenskraft"), ("charisma", "Charisma"), ("sinne", "Sinne"))
    )
    return _summary_section(
        parent,
        x,
        y,
        w,
        "Attribute",
        [
            ("Körper", body_text),
            ("Geist", mind_text),
            ("Verteilte AP", f"{attributes.get('total', 0)} / {start_ap}"),
            ("Start-XP", str(start_xp)),
            ("Attributsumme", str(attributes.get("raw_total", 0))),
        ],
    )


def _summary_skills_section(parent, x, y, w, character_state):
    skills = character_state.get("skills", [])
    active = []
    for skill in skills:
        parts = [str(skill.get("name") or skill.get("id") or "-")]
        if skill.get("attribute"):
            parts.append(f"Attribut: {skill.get('attribute')}")
        if skill.get("specialization"):
            parts.append(f"Spezialisierung: {skill.get('specialization')}")
        active.append(" | ".join(parts))
    return _summary_section(
        parent,
        x,
        y,
        w,
        "Fertigkeiten",
        [
            ("Aktive Fertigkeiten", "\n".join(f"- {item}" for item in active) if active else "-"),
            ("BP", _bp_summary_text(character_state)),
        ],
    )


def _summary_perks_section(parent, x, y, w, character_state):
    perks = character_state.get("perks", [])
    rows = []
    for perk in perks:
        if not isinstance(perk, dict):
            continue
        name = _dash(perk.get("name"))
        bp = _perk_bp_value(perk)
        effect = _dash(perk.get("effect"))
        rows.append(f"- {name} ({bp} BP): {effect}")
    return _summary_section(parent, x, y, w, "Perks", [("Auswahl", "\n".join(rows) if rows else "-")])


def _summary_equipment_section(parent, x, y, w, character_state):
    equipment = character_state.get("equipment", {})
    money = equipment.get("money", {})
    money_text = (
        f"{_non_negative_int(money.get('gulden'))} Gulden, "
        f"{_non_negative_int(money.get('schilling'))} Schilling, "
        f"{_non_negative_int(money.get('heller'))} Heller"
    )
    return _summary_section(
        parent,
        x,
        y,
        w,
        "Ausrüstung",
        [
            ("Startgeld", money_text),
            ("Items", _summary_equipment_rows(equipment.get("items"), ("name", "pl", "count", "note"))),
            ("Waffen", _summary_equipment_rows(equipment.get("weapons"), ("name", "damage", "attribute", "note"))),
            ("Rüstung", _summary_equipment_rows(equipment.get("armor"), ("name", "protection", "note"))),
            ("Notizen", _dash(equipment.get("notes"))),
        ],
    )


def _summary_section(parent, x, y, w, heading, rows):
    _section_heading(parent, x, y, w, heading)
    cursor_y = y + 40
    for label_text, value in rows:
        text = f"{label_text}: {value}"
        line_count = max(1, str(text).count("\n") + 1)
        h = max(26, line_count * 22 + 6)
        label = QLabel(parent)
        label.setGeometry(x + 10, cursor_y, w - 20, h)
        label.setText(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        label.setStyleSheet("background: transparent; color: #e8dcc0; font-size: 15px; font-weight: 600;")
        label.show()
        cursor_y += h + 6
    return cursor_y


def _summary_equipment_rows(rows, keys):
    if not isinstance(rows, list) or not rows:
        return "-"
    rendered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        values = [_dash(row.get(key)) for key in keys]
        rendered.append("- " + " | ".join(values))
    return "\n".join(rendered) if rendered else "-"


def _bp_summary_text(character_state):
    bp = character_state.get("bp", {}) if isinstance(character_state.get("bp"), dict) else {}
    if not bp:
        return "BP-Berechnung kommt später."
    return (
        f"Start-BP: {int(bp.get('base', 25) or 25)} | "
        f"Ausgegeben: {int(bp.get('spent', 0) or 0)} | "
        f"Verbleibend: {int(bp.get('remaining', 25) or 25)}"
    )


def _save_character_state_from_summary(window, status_label):
    ok, message = save_character_state(window)
    if ok:
        status_label.setText(f"Charakter gespeichert: {message}")
    else:
        status_label.setText(f"Speichern fehlgeschlagen: {message}")


def _finalize_character_state_from_summary(window, status_label):
    ok, message = finalize_character_state(window)
    if not ok:
        status_label.setText(f"Fertigstellen fehlgeschlagen: {message}")


def _dash(value):
    text = str(value or "").strip()
    return text if text else "-"


def _create_framed_panel(window, parent, x, y, w, h):
    panel = QWidget(parent)
    panel.setGeometry(x, y, w, h)
    panel.setStyleSheet("background: rgba(10, 8, 7, 155);")

    bg = QLabel(panel)
    bg.setGeometry(0, 0, w, h)
    bg.setStyleSheet("background: rgba(10, 8, 7, 150); border: 1px solid rgba(104, 74, 35, 140);")
    frame_pixmap = window.load_ui_pixmap("panels/shared_skils_panel_frame.png")
    if frame_pixmap is not None and not frame_pixmap.isNull():
        bg.setPixmap(frame_pixmap.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        bg.setStyleSheet("background: transparent;")
    bg.lower()
    panel.show()
    return panel


def _create_species_card(window, parent, x, y, w, h, species, selected):
    container = QWidget(parent)
    container.setGeometry(x, y, w, h)
    container.setStyleSheet("background: transparent; border: none;")

    plate_h = 32
    portrait_size = max(46, min(116, w - 2, h - plate_h - 4))
    portrait_x = (w - portrait_size) // 2
    portrait_y = 2

    image = QLabel(container)
    image.setGeometry(portrait_x, portrait_y, portrait_size, portrait_size)
    image.setAlignment(Qt.AlignCenter)
    image.setStyleSheet(
        "background: transparent; color: #d5b66f; border: none; "
        "font-size: 15px; font-weight: 800;"
    )
    pixmap = _load_species_source_pixmap(window, species)
    if pixmap.isNull():
        image.setPixmap(_species_missing_portrait_pixmap(species["name"], portrait_size, portrait_size, selected))
    else:
        portrait = _cached_species_portrait_pixmap(window, species, image.width(), image.height())
        image.setPixmap(portrait)
    image.show()

    if selected:
        selected_ring = QLabel(container)
        ring_pad = 4
        selected_ring.setGeometry(
            portrait_x + ring_pad,
            portrait_y + ring_pad,
            portrait_size - (ring_pad * 2),
            portrait_size - (ring_pad * 2),
        )
        selected_ring.setStyleSheet(
            f"background: transparent; border: 4px solid rgba(242, 210, 139, 220); "
            f"border-radius: {(portrait_size - (ring_pad * 2)) // 2}px;"
        )
        selected_ring.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        selected_ring.show()

    plate_w = min(w, max(68, int(portrait_size * 1.15)))
    plate_x = (w - plate_w) // 2
    plate_y = portrait_y + portrait_size + 2
    plate = QLabel(container)
    plate.setGeometry(plate_x, plate_y, plate_w, plate_h)
    plate_pixmap = window.load_ui_pixmap("frames/512x122_box.png")
    if plate_pixmap is None or plate_pixmap.isNull():
        plate_pixmap = window.load_ui_pixmap("buttons/menu_button_medium.png")
    if plate_pixmap is not None and not plate_pixmap.isNull():
        plate.setPixmap(plate_pixmap.scaled(plate.width(), plate.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        plate.setStyleSheet("background: transparent;")
    else:
        plate.setStyleSheet("background: rgba(20, 14, 10, 210); border-top: 1px solid rgba(160, 110, 35, 170);")
    plate.show()

    name = QLabel(container)
    name.setGeometry(plate_x + 6, plate_y, plate_w - 12, plate_h)
    name.setText(species["name"])
    name.setAlignment(Qt.AlignCenter)
    name.setStyleSheet(
        "background: transparent; "
        f"color: {'#f2d28b' if selected else '#d8c38a'}; "
        "font-size: 12px; font-weight: 900;"
    )
    name.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    name.show()

    hit = QPushButton(container)
    hit.setGeometry(0, 0, w, h)
    hit.setText("")
    hit.setCursor(Qt.PointingHandCursor)
    hit.setStyleSheet(
        "QPushButton { border: none; background: transparent; padding: 0px; }"
        "QPushButton:hover { border: none; background: transparent; }"
    )
    hit.clicked.connect(lambda checked=False, species_id=species["id"]: _select_species(window, species_id))
    hit.raise_()
    container.show()
    return container


def _species_card_portrait_pixmap(source, target_w, target_h, tuning=None):
    tuning = tuning if isinstance(tuning, dict) else {}
    zoom = _safe_float(tuning.get("zoom"), 1.0)
    if zoom <= 0:
        zoom = 1.0
    offset_x = int(_safe_float(tuning.get("offset_x"), 0))
    offset_y = int(_safe_float(tuning.get("offset_y"), 0))

    crop_x = max(0, int(source.width() * 0.42))
    crop_y = max(0, int(source.height() * 0.05))
    crop_w = max(1, min(source.width() - crop_x, int(source.width() * 0.56)))
    crop_h = max(1, min(source.height() - crop_y, int(source.height() * 0.75)))
    cropped = source.copy(crop_x, crop_y, crop_w, crop_h)
    scaled_w = max(1, int(target_w * zoom))
    scaled_h = max(1, int(target_h * zoom))
    scaled = cropped.scaled(scaled_w, scaled_h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

    portrait = QPixmap(target_w, target_h)
    portrait.fill(Qt.transparent)
    painter = QPainter(portrait)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    draw_x = ((target_w - scaled.width()) // 2) + offset_x
    draw_y = int((target_h - scaled.height()) * 0.42) + offset_y
    painter.drawPixmap(draw_x, draw_y, scaled)
    painter.end()
    return portrait


def _species_floating_portrait_pixmap(source, target_w, target_h, tuning=None):
    target_w = max(1, int(target_w))
    target_h = max(1, int(target_h))
    portrait = _species_card_portrait_pixmap(source, target_w, target_h, tuning)

    token = QPixmap(target_w, target_h)
    token.fill(Qt.transparent)
    painter = QPainter(token)
    painter.setRenderHint(QPainter.Antialiasing, True)

    inset = 4
    path = QPainterPath()
    path.addEllipse(inset, inset, target_w - (inset * 2), target_h - (inset * 2))
    painter.fillPath(path, QColor(255, 255, 255, 255))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, portrait)
    painter.setClipping(False)
    painter.setPen(QPen(QColor(120, 82, 38, 175), 2))
    painter.drawEllipse(inset + 1, inset + 1, target_w - ((inset + 1) * 2), target_h - ((inset + 1) * 2))

    painter.end()
    return token


def _load_species_source_pixmap(window, species):
    cache = getattr(window, "_creator_species_pixmap_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        window._creator_species_pixmap_cache = cache
    image_path = _resolve_species_image_path(species)
    key = (species.get("id", species.get("name", "")), str(image_path))
    if key not in cache:
        cache[key] = QPixmap(str(image_path)) if image_path.exists() else QPixmap()
    return cache[key]


def _cached_species_portrait_pixmap(window, species, target_w, target_h):
    cache = getattr(window, "_creator_species_portrait_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        window._creator_species_portrait_cache = cache
    image_path = _resolve_species_image_path(species)
    tuning = _species_portrait_tuning(species)
    zoom = _safe_float(tuning.get("zoom"), 1.0)
    offset_x = int(_safe_float(tuning.get("offset_x"), 0))
    offset_y = int(_safe_float(tuning.get("offset_y"), 0))
    key = (
        species.get("id", species.get("name", "")),
        str(image_path),
        int(target_w),
        int(target_h),
        "portrait",
        zoom,
        offset_x,
        offset_y,
    )
    if key not in cache:
        source = _load_species_source_pixmap(window, species)
        cache[key] = _species_floating_portrait_pixmap(source, target_w, target_h, tuning) if not source.isNull() else QPixmap()
    return cache[key]


def _cached_species_preview_pixmap(window, species, target_w, target_h):
    cache = getattr(window, "_creator_species_full_preview_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        window._creator_species_full_preview_cache = cache
    image_path = _resolve_species_image_path(species)
    key = (species.get("id", species.get("name", "")), str(image_path), int(target_w), int(target_h), "full")
    if key not in cache:
        source = _load_species_source_pixmap(window, species)
        cache[key] = source.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation) if not source.isNull() else QPixmap()
    return cache[key]


def _species_portrait_tuning(species):
    species_id = str(species.get("id", "") or "").strip().lower()
    if species_id in SPECIES_PORTRAIT_TUNING:
        return SPECIES_PORTRAIT_TUNING[species_id]
    normalized_name = _sanitize_filename(species.get("name", "")).lower()
    return SPECIES_PORTRAIT_TUNING.get(normalized_name, {})


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _species_missing_portrait_pixmap(name, target_w, target_h, selected):
    target_w = max(1, int(target_w))
    target_h = max(1, int(target_h))
    token = QPixmap(target_w, target_h)
    token.fill(Qt.transparent)
    painter = QPainter(token)
    painter.setRenderHint(QPainter.Antialiasing, True)

    inset = 4
    path = QPainterPath()
    path.addEllipse(inset, inset, target_w - (inset * 2), target_h - (inset * 2))
    painter.fillPath(path, QColor(8, 6, 5, 222))
    painter.setPen(QPen(QColor(242, 210, 139, 220) if selected else QColor(120, 82, 38, 175), 3 if selected else 2))
    painter.drawEllipse(inset + 1, inset + 1, target_w - ((inset + 1) * 2), target_h - ((inset + 1) * 2))
    painter.setPen(QColor(213, 182, 111, 230))
    painter.drawText(10, 10, target_w - 20, target_h - 20, Qt.AlignCenter | Qt.TextWordWrap, str(name or "-"))
    painter.end()
    return token


def _render_species_step(window, panel, state):
    pad = 18
    grid_w = int((panel.width() - (pad * 2)) * 0.68)
    details_x = pad + grid_w + 18
    details_w = panel.width() - details_x - pad
    body_h = panel.height() - (pad * 2)

    grid_panel = _create_framed_panel(window, panel, pad, pad, grid_w, body_h)
    grid_scroll = QScrollArea(grid_panel)
    grid_scroll.setGeometry(10, 10, grid_w - 20, body_h - 20)
    grid_scroll.setWidgetResizable(False)
    grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    grid_scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: #17110f; width: 12px; }"
        "QScrollBar::handle:vertical { background: #6c4a22; min-height: 24px; }"
    )
    grid_host = QWidget(grid_scroll)
    grid_host.setStyleSheet("background: transparent;")

    columns = 7
    rows = 3
    grid_pad = 6
    card_gap = 3
    inner_w = max(300, grid_w - 34)
    card_w = max(42, (inner_w - (grid_pad * 2) - (card_gap * (columns - 1))) // columns)
    card_h = max(124, min(172, (body_h - 20 - (grid_pad * 2) - (card_gap * (rows - 1))) // rows))
    content_h = grid_pad + (rows * card_h) + ((rows - 1) * card_gap) + grid_pad
    grid_host.setMinimumSize(inner_w, max(body_h - 20, content_h))
    grid_host.resize(inner_w, max(body_h - 20, content_h))
    for index, species_item in enumerate(SPECIES):
        row = index // columns
        col = index % columns
        card_x = grid_pad + (col * (card_w + card_gap))
        card_y = grid_pad + (row * (card_h + card_gap))
        _create_species_card(
            window,
            grid_host,
            card_x,
            card_y,
            card_w,
            card_h,
            species_item,
            species_item["id"] == state.get("species_id"),
        )
    grid_scroll.setWidget(grid_host)
    grid_scroll.show()

    species = _species_by_id(state.get("species_id"))
    preview_h = max(220, min(330, int(body_h * 0.50)))
    preview_frame = _create_framed_panel(window, panel, details_x, pad, details_w, preview_h)
    preview = QLabel(preview_frame)
    preview.setGeometry(12, 12, details_w - 24, preview_h - 24)
    preview.setAlignment(Qt.AlignCenter)
    preview.setStyleSheet(
        "background: rgba(9, 7, 6, 145); color: #d5b66f; border: none; "
        "font-size: 28px; font-weight: 800;"
    )
    pixmap = _load_species_source_pixmap(window, species)
    if pixmap.isNull():
        preview.setText(species["name"])
    else:
        preview.setPixmap(_cached_species_preview_pixmap(window, species, preview.width(), preview.height()))
    preview.show()

    detail_y = pad + preview_h + 16
    detail_h = max(150, body_h - preview_h - 16)
    _render_species_details(window, panel, details_x, detail_y, details_w, detail_h, species)


def _render_species_details(window, parent, x, y, w, h, species):
    detail_frame = _create_framed_panel(window, parent, x, y, w, h)
    scroll = QScrollArea(detail_frame)
    scroll.setGeometry(12, 12, w - 24, h - 24)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { background: #17110f; width: 12px; }"
        "QScrollBar::handle:vertical { background: #6c4a22; min-height: 24px; }"
    )

    host = QWidget(scroll)
    host.setStyleSheet("background: transparent;")
    inner_w = max(200, w - 48)
    cursor_y = 10

    cursor_y = _create_detail_title(
        host,
        8,
        cursor_y,
        inner_w - 16,
        species["name"],
    )
    cursor_y = _create_detail_text_section(
        host,
        8,
        cursor_y + 12,
        inner_w - 16,
        "Beschreibung",
        species["description"],
    )
    perks_text = "\n".join(f"- {perk}" for perk in species.get("perks", [])) or "-"
    cursor_y = _create_detail_text_section(
        host,
        8,
        cursor_y + 14,
        inner_w - 16,
        "Perks",
        perks_text,
    )
    notes_parts = [value for value in (species.get("bp_bonus"), species.get("notes")) if value]
    notes_text = "\n".join(notes_parts) if notes_parts else "-"
    cursor_y = _create_detail_text_section(
        host,
        8,
        cursor_y + 14,
        inner_w - 16,
        "Notizen",
        notes_text,
    )

    host.setMinimumSize(inner_w, max(h - 24, cursor_y + 8))
    scroll.setWidget(host)
    scroll.show()


def _create_detail_title(parent, x, y, w, text):
    title_h = 34
    title = QLabel(parent)
    title.setGeometry(x, y, w, title_h)
    title.setText(text)
    title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    title.setStyleSheet(
        "background: transparent; color: #f2d28b; font-size: 26px; font-weight: 800;"
    )
    title.show()
    return y + title_h


def _create_detail_text_section(parent, x, y, w, heading, body, body_font_size=15):
    line_count = max(1, str(body).count("\n") + 1)
    heading_h = 24
    separator_h = 2
    body_h = max(34, (line_count * (body_font_size + 6)) + 8)

    separator = QLabel(parent)
    separator.setGeometry(x, y, w, separator_h)
    separator.setStyleSheet("background: rgba(160, 110, 35, 170);")
    separator.show()

    title = QLabel(parent)
    title.setGeometry(x, y + 10, w, heading_h)
    title.setText(heading)
    title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    title.setStyleSheet(
        "background: transparent; color: #f2d28b; font-size: 16px; font-weight: 800;"
    )
    title.show()

    text = QLabel(parent)
    text.setGeometry(x, y + 10 + heading_h + 8, w, body_h)
    text.setText(str(body))
    text.setWordWrap(True)
    text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    text.setStyleSheet(
        f"background: transparent; color: #e8dcc0; font-size: {body_font_size}px; font-weight: 600;"
    )
    text.show()

    return y + 10 + heading_h + 8 + body_h


def _render_footer(window, x, y, w, h, state):
    button_w = 190
    gap = 12

    window.create_asset_text_button(
        window.content_layer,
        {
            "x": x,
            "y": y,
            "w": button_w,
            "h": h,
            "text": "Zurück zur Auswahl",
            "asset": "buttons/menu_button_medium.png",
            "font_size": 15,
            "color": "#f2d28b",
        },
        "Zurück zur Auswahl",
        lambda: _return_to_start_menu(window),
    )

    current_index = _current_step_index(state)
    back_x = x + w - (button_w * 2) - gap
    next_x = x + w - button_w
    window.create_asset_text_button(
        window.content_layer,
        {
            "x": back_x,
            "y": y,
            "w": button_w,
            "h": h,
            "text": "Zurück",
            "asset": "buttons/menu_button_medium.png",
            "font_size": 15,
            "color": "#9a8560" if current_index <= 0 else "#f2d28b",
        },
        "Zurück",
        lambda: _move_step(window, -1),
    )
    window.create_asset_text_button(
        window.content_layer,
        {
            "x": next_x,
            "y": y,
            "w": button_w,
            "h": h,
            "text": "Weiter",
            "asset": "buttons/menu_button_medium.png",
            "font_size": 15,
            "color": "#9a8560" if current_index >= len(STEPS) - 1 else "#f2d28b",
        },
        "Weiter",
        lambda: _move_step(window, 1),
    )


def _return_to_start_menu(window):
    window._start_screen_mode = "menu"
    window.clear_content_layer()
    from ui_sections import start_section

    start_section.render_start_section(window)


def _move_step(window, delta):
    state = _ensure_creator_state(window)
    index = _current_step_index(state)
    next_index = max(0, min(len(STEPS) - 1, index + delta))
    state["step"] = STEPS[next_index][0]
    _rerender(window)


def _current_step_index(state):
    step = state.get("step")
    for index, (step_id, _) in enumerate(STEPS):
        if step_id == step:
            return index
    return 0


def _select_species(window, species_id):
    state = _ensure_creator_state(window)
    species = _species_by_id(species_id)
    state["species_id"] = species["id"]
    state["species_name"] = species["name"]
    state["species_image_path"] = species["image_path"]
    _rerender(window)


def _resolve_species_image_path(species):
    species_dir = resource_path("assets/ui_elements/character_creator/species")
    candidates = [
        species_dir / f"{species['name']}.png",
        species_dir / f"{species['id']}.png",
        species_dir / f"{_sanitize_filename(species['name'])}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _sanitize_filename(value):
    invalid_chars = '\\/:*?"<>|'
    text = str(value)
    for char in invalid_chars:
        text = text.replace(char, "_")
    return text


def _species_by_id(species_id):
    for species in SPECIES:
        if species["id"] == species_id:
            return species
    return SPECIES[0]
