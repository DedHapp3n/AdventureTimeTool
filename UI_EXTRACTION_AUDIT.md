# UI Extraction Audit

Audit-only review of the current UI extraction state. No code or JSON changes were made while collecting these findings.

## Main Finding

The extraction is incomplete. Most tabs have extracted entry points, but `ui_main.py` is still the owner for large parts of Skills, shared rendering helpers, data extraction, dialog orchestration, and edit behavior.

The biggest confirmed issue: normal Skills table rendering still happens in `ui_main.py`, not in `ui_sections/skills_section.py`.

Active normal Skills renderer:

- `ui_main.py:5351` - `MainWindow.render_skills_table(...)`

## Section Module Status

| Module | Main public render functions | Called from `ui_main.py` | Active | Ownership |
|---|---|---|---|---|
| `ui_sections/character_section.py` | `render_character_section`, `render_character_initiative_panel`, `render_character_paradigm_panel` | `render_character_screen()` | Yes | Mostly full rendering, but edit/resource/data helpers remain in `ui_main.py` |
| `ui_sections/skills_section.py` | `render_skills_section`, `render_skills_se_table` | `render_skills_screen()` | Yes | Partial only; delegates normal table to `window.render_skills_table()` |
| `ui_sections/inventory_section.py` | `render_inventory_screen` plus table/money helpers | `render_inventory_screen()` and wrapper methods | Yes | Mostly extracted, still uses `window.*` wrappers heavily |
| `ui_sections/equipment_section.py` | `render_equipment_section`, armor/weapons renderers | `render_equipment_screen()` | Yes | Mostly extracted rendering; analysis/data remains in `ui_main.py` |
| `ui_sections/magic_section.py` | `render_magic_section`, spell/upgrade tables | `render_magic_screen()` | Yes | Mostly extracted via callbacks |
| `ui_sections/notes_section.py` | `render_notes_section` | `render_notes_screen()` | Yes | Extracted via callbacks |
| `ui_sections/settings_section.py` | `render_settings_section` plus settings actions | `render_settings_page()` | Yes | Mostly extracted, with wrappers in `ui_main.py` |

## Active Render Paths Still In `ui_main.py`

High-risk remaining UI/render functions:

- `ui_main.py:5351` - `render_skills_table`: renders the real normal Skills table, including headers, rows, skill buttons, attribute slots, Wert/value cells, specialization editors, and note editors. Risk 5.
- `ui_main.py:4835` - Skills SE persistence/picker/upgrade helpers: not the normal visual table, but tightly coupled to Skills UI. Risk 3.
- `ui_main.py:3281` - `open_skill_roll_dialog`: builds the Roll20 model and reads many dialog layout keys before calling extracted `open_roll20_dialog`. Risk 4.
- `ui_main.py:4653` - `render_browser_screen`: full browser tab remains in `ui_main.py`. Risk 2.
- `ui_main.py:6501` - `render_character_front`: old/fallback Character renderer remains. It is only used if `character_screen` is missing from `ui_layout.json`. Risk 2.
- `ui_main.py:6473` - `create_panel_text`, `_create_content_panel`, text/color helpers: shared rendering primitives still centralized. Risk 3.
- `ui_main.py:6763` - `eventFilter`: handles Character resource clicks, Character edits, perk edits, wellbeing toggles, paradigm toggles, and inventory renaming. Risk 4.

## Skills Extraction Audit

Active call flow:

1. `show_main_section("skills")` calls `ui_main.py:4832` - `render_skills_screen`.
2. `render_skills_screen` calls `skills_section.render_skills_section(self)`.
3. `ui_sections/skills_section.py:258` - `render_skills_section` loads `skills_layout.json`, renders category tabs, builds skill source info, and handles the SE pseudo-tab.
4. For normal skill categories, `ui_sections/skills_section.py:380` calls `window.render_skills_table(...)`.
5. `ui_main.py:5351` renders the actual normal skills table.

Answers:

- `render_skills_screen` is defined in `ui_main.py`, but is only a wrapper.
- `render_skills_section` is defined in `ui_sections/skills_section.py`.
- The normal skills table is rendered in `ui_main.py`.
- `skills_section.py` does not render the normal skills table itself.
- Attribute slot boxes are rendered in `ui_main.py:5577-5637`.
- Wert/value cells are rendered in `ui_main.py:5639-5682`.
- Specialization cells are rendered in `ui_main.py:5683-5728`.
- Note cells are rendered in `ui_main.py:5729-5775`.
- Roll20 click bindings are attached in `ui_main.py:5571-5573` for skill names and `ui_main.py:5678-5680` for Wert/value cells.

### Skills Layout JSON Usage

Active layout source:

- Main UI points to `skills_screen.layout_file` in `ui_layout.json`.
- `load_skills_layout_config()` loads `assets/themes/<active>/skills_layout.json`.
- Fallback is `assets/themes/diablo/skills_layout.json`.

Actively read major keys:

- `skills_screen.x/y/w/h`
- `skills_screen.category_tabs`
- `skills_screen.category_tabs.button`
- `skills_screen.table.x/y/w/h`
- `skills_screen.table.header_h`
- `skills_screen.table.row_h`
- `skills_screen.table.max_visible_rows`
- `skills_screen.table.font_size`
- `skills_screen.table.header_font_size`
- `skills_screen.table.header_color`
- `skills_screen.table.skill_name_color`
- `skills_screen.table.attribute_color`
- `skills_screen.table.value_color`
- `skills_screen.table.specialization_color`
- `skills_screen.table.note_color`
- `skills_screen.table.content_inset`
- `skills_screen.table.frame`
- `skills_screen.table.row_fields`
- `skills_screen.table.columns`
- `skills_screen.se_tab`

Configured but not used by the normal Skills renderer:

- `skills_screen.table.min_row_h`
- `skills_screen.table.max_row_h`
- `skills_screen.table.wrap_text`
- `skills_screen.table.columns.value.text_padding_left`
- `skills_screen.table.columns.value.text_padding_right`
- `skills_screen.se_tab.xp_info.readonly`
- `skills_screen.se_tab.skill_upgrade_info.readonly`

Why Wert/value frame changes may not show:

- The active normal table renderer is in `ui_main.py`, not `skills_section.py`.
- The frame helper lives in `skills_section.py`, but is called by `ui_main.py`.
- `row_fields.value.frame` is read, but text placement is controlled by `row_fields.value.w/h/text_offset_x/text_offset_y/text_align` plus `columns.value.x/w`.
- Some adjacent-looking config keys exist but are not read by the active renderer.

## Character Extraction Audit

Active call flow:

1. `show_main_section("character")`
2. `ui_main.py:6498` - `render_character_screen`
3. `ui_sections/character_section.py:746` - `render_character_section`

`character_section.py` renders:

- Character info panel
- Attribute panel
- Perk/disadvantage panel
- Wohlbefinden panel at `character_section.py:1449`
- Initiative panel at `character_section.py:245`
- Paradigmen panel at `character_section.py:417`

Character logic remaining in `ui_main.py`:

- Data reads/formatting: `_read_data_map_cell`, `_resolve_data_map_cell_ref`, `format_character_display_value`
- Edit handling: `_create_character_value_editor`, `_handle_character_widget_double_click`, `_on_character_field_edited`
- Resource dialogs: `open_character_resource_dialog`
- Initiative discovery/roll data: `get_character_initiative_data` and helpers
- Paradigm analysis: `_analyze_character_paradigm_area`
- Fallback old renderer: `render_character_front`

Character layout source:

- `character_screen` is read from `assets/themes/<active>/ui_layout.json`.
- All inspected themes include `character_screen`.
- `character_front` is obsolete in the normal active path and only used if `character_screen` is missing.

Unused or suspicious Character systems:

- `character_section.py:134` - `_apply_nine_slice_frame_for_rect` appears unused.
- Frame `content_margin` is returned by frame helpers but not meaningfully applied to child layout.
- `character_front` remains as an old/fallback renderer and can confuse visual work.

## Dialog Extraction Audit

Active dialog modules:

- `ui_dialogs/roll20_dialog.py:21` - `open_roll20_dialog` is active. Called from `ui_main.py:3508`.
- `ui_dialogs/resource_dialog.py:14` - `open_resource_dialog` is active. Called from `ui_main.py:5971`.

Remaining dialog logic in `ui_main.py`:

- `open_skill_roll_dialog` still prepares a large part of the Roll20 dialog model and style context before delegating.
- Character text edit dialogs remain directly in `ui_main.py:6242-6268`.
- `open_debug_dialog` remains in `ui_main.py`.

## Layout Loading Audit

Active loaders:

- Main UI: `load_main_ui_layout_config()` -> `assets/themes/<active>/ui_layout.json`, fallback Diablo.
- Skills: `load_skills_layout_config()` -> `skills_screen.layout_file` from `ui_layout.json`, default `skills_layout.json`, fallback Diablo.
- Inventory: `load_inventory_layout_config()` -> `inventory_screen.layout_file`, default `inventory_layout.json`, fallback Diablo.
- Equipment: `load_equipment_layout_config()` -> `equipment_screen.layout_file`, default `equipment_layout.json`, fallback Diablo.
- Magic: `load_magic_layout_config()` -> `magic_screen.layout_file`, default `magic_layout.json`, fallback Diablo.
- Notes: `load_notes_layout_config()` -> `notes_screen.layout_file`, default `notes_layout.json`, fallback Diablo.
- Roll dialog: `load_roll_dialog_layout_config()` -> `roll_dialog_layout.json`, fallback Diablo.

The active theme path is `assets/themes`, not `data/config`, except shared config files under `assets/config` for skills, perks, and calculation mappings.

Notable configured-but-unused keys found by scan:

- `ui_layout.json`: `column_1`, `column_2`, `column_3`
- `equipment_layout.json`: key names `physical`, `elemental` are present under `column_groups`; no direct code read was found by key-name scan.
- `roll_dialog_layout.json`: `specialization_options.hint_color`
- `skills_layout.json`: `table.min_row_h`, `table.max_row_h`, `table.wrap_text`, `columns.value.text_padding_left`, `columns.value.text_padding_right`, SE `readonly` flags.

## Duplicates And Half-Extractions

- `skills_section.py` exists but delegates the normal Skills table to `ui_main.py`.
- `ui_main.py` still has the old/full normal Skills renderer.
- Skills frame helpers live in `skills_section.py`, but the active renderer using them is in `ui_main.py`.
- Character rendering is extracted, but Character editing and resource interactions still run through `ui_main.py` and `eventFilter`.
- Roll20 dialog UI is extracted, but dialog model/style preparation remains large in `ui_main.py`.
- Inventory is extracted, but `ui_main.py` keeps many wrapper methods that just call `inventory_section`.
- `character_front` remains as a fallback renderer beside the active `character_screen` system.

## Recommended Cleanup Plan

1. Move normal Skills table rendering into `ui_sections/skills_section.py`.
   - Files: `ui_main.py`, `ui_sections/skills_section.py`
   - Risk: 5
   - Benefit: fixes the main wrong-file visual-edit problem.
   - Tests: launch Skills tab; verify category switching, Wert click roll, attribute slot edit, specialization/note edit, and missing-cache messages.

2. Move Skills SE behavior out of `ui_main.py`.
   - Files: `ui_main.py`, `ui_sections/skills_section.py`
   - Risk: 3
   - Benefit: creates one Skills ownership boundary.
   - Tests: SE add rows, skill picker, persistence, upgrade suggestions.

3. Split Roll20 model building from dialog rendering.
   - Files: `ui_main.py`, `ui_dialogs/roll20_dialog.py`
   - Risk: 4
   - Benefit: avoids duplicate dialog config responsibility.
   - Tests: skill roll, initiative roll, perks/wellbeing suggestions, copy command.

4. Move Character edit/resource handlers into `character_section.py` or a dedicated `character_controller.py`.
   - Files: `ui_main.py`, `ui_sections/character_section.py`, `ui_dialogs/resource_dialog.py`
   - Risk: 4
   - Benefit: Character rendering and interactions stop depending on scattered event-filter logic.
   - Tests: edit basic fields, attributes, wellbeing toggle, paradigm toggle, resource dialogs.

5. Remove or quarantine obsolete fallback renderers/config.
   - Files: `ui_main.py`, theme `ui_layout.json`
   - Risk: 2
   - Benefit: reduces confusion between `character_front` and `character_screen`.
   - Tests: theme load fallback, character screen render.

