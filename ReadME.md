# Adventure Time Tool

Adventure Time Tool is a work-in-progress local desktop RPG character tool. It is built for a themed fantasy UI, character cache workflows, and focused editing of character sections such as Fertigkeiten, Inventar, Ausruestung, Magie, Notizen, and Settings.

This is a personal tool, not a web app.

## Features

- Themed PySide6 desktop interface
- Character data import/loading through spreadsheet and JSON cache structures
- Fertigkeiten/Skills section with categories, attribute slots, specialization display/editing, SE data, and Roll20 roll support
- Inventar section with category tabs, editable table rows, and a Geldbeutel money panel
- Ausruestung, Magie, Notizen, and Settings sections
- Roll20 command dialog with copy support and direct-send placeholder behavior
- Multi-theme support through JSON layouts and theme asset folders
- Runtime character cache handling under `data/`

## Tech Stack

- Python
- PySide6
- JSON theme/layout files
- Spreadsheet and cache based character data
- `openpyxl` for `.xlsx`/`.xlsm` import

## Setup

Install the dependencies listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Run the app:

```bash
python main.py
```

## Project Structure

```text
AdventureTimeTool/
├── main.py
├── ui_main.py
├── data_loader.py
├── formula_parser.py
├── calculation_center.py
├── app_paths.py
├── app_logger.py
├── ui_sections/
├── ui_dialogs/
├── ui_tabs/
├── assets/
│   ├── config/
│   └── themes/
├── data/
└── docs/
```

## Documentation

- [Project Context](docs/PROJECT_CONTEXT.md)
- [Codex Context](docs/CODEX_CONTEXT.md)

## Assets

Theme images and UI assets are manually created. The tool should not generate or modify image assets automatically.
