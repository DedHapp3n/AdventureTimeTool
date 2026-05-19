# Adventure Time Tool

## 1. Projektziel

Adventure Time Tool ist ein Fantasy-/Pen&Paper-Character-Tool.

Der aktuelle Datenfluss ist:

```text
Tabellen-Datei (.xlsx/.xlsm/.ods)
-> DataLoader
-> JSON-Cache
-> FormulaParser-Recalculation
-> themenbasierte Fantasy-UI
```

Die sichtbare UI liest im Normalfall vorbereitete Cache-`value`-Werte. Formeln bleiben in der Cache-Struktur erhalten und werden durch `FormulaParser` normalisiert, ausgewertet oder im Berechnungszentrum analysiert. `DataLoader` verwaltet Tabellenimport, Charakter-Cache, aktive Charakterdatei und Speichern nach UI-Edits.

## 2. Aktuelle Projektstruktur

```text
AdventureTimeTool/
├── main.py
├── ui_main.py
├── data_loader.py
├── formula_parser.py
├── calculation_center.py
├── app_paths.py
├── app_logger.py
├── build.py
├── AdventureTimeTool.spec
├── requirements.txt
├── ui_tabs/
│   └── sheet_tab.py
├── assets/
│   ├── config/
│   │   ├── calculation_rules.json
│   │   ├── calculation_overrides.json
│   │   ├── perk_rules.json
│   │   ├── skill_definitions.json
│   │   ├── skill_sheet_mapping.json
│   │   └── theme_config.json
│   └── themes/
│       └── <theme>/
│           ├── ui_layout.json
│           ├── skills_layout.json
│           ├── inventory_layout.json
│           ├── equipment_layout.json
│           ├── magic_layout.json
│           ├── notes_layout.json
│           ├── roll_dialog_layout.json
│           └── ui/
└── data/
    ├── settings.json
    ├── current_character.json
    ├── cache/
    │   └── *.json
    └── config/
        ├── calculation_rules.json
        └── calculation_overrides.json
```

## 3. Wichtige Dateien

`main.py` startet die Qt-Anwendung und öffnet `MainWindow`.

`ui_main.py` enthält aktuell die Haupt-UI: Navigation, Tabs, Screens, Settings, Debug-Ansichten, Roll20-Wurf-Assistent und viele JSON-gesteuerte Renderpfade.

`data_loader.py` lädt `.xlsx`, `.xlsm` und `.ods`, baut den `cell_cache`, speichert Charakter-Caches und verwaltet `data/current_character.json`.

`formula_parser.py` erkennt Referenzen, normalisiert einfache Excel-/deutsche Formelsyntax, berechnet Cache-Formeln und liefert Formel-Traces für Analyse.

`calculation_center.py` zeigt Formeln, Werte, Fehler, Rules und Overrides. Es ist derzeit Analyse-/Editor-Schicht.

`app_paths.py` kapselt Pfade für Entwicklung und PyInstaller-Build. `assets/` sind Ressourcen, `data/` ist beschreibbarer Runtime-Bereich.

`app_logger.py` stellt zentrale Logging-Funktionen mit Debug-Kategorien bereit.

`ui_tabs/sheet_tab.py` ist eine Debug-/SheetTab-Struktur für Tabellenansichten und Formelinspektion.

## 4. Aktive Tabs und Bereiche

- Charakter
- Fertigkeiten / SE
- Inventar
- Ausrüstung
- Magie
- Notizen
- Settings
- Berechnungszentrum

Das Berechnungszentrum wird aus der UI heraus geöffnet und ist kein eigener Hauptnavigationstab.

## 5. Theme- und Asset-System

Themes werden aus `assets/themes/<theme>/` erkannt. Ein Theme besteht aus mehreren Layout-Dateien plus `ui/` Assets.

Wichtig:

- `assets/` ist als read-only Ressourcenbereich zu behandeln.
- `data/` ist der beschreibbare Runtime-Bereich.
- Das aktive Theme steht in `data/settings.json`.
- `assets/config/theme_config.json` ist nur noch Legacy-/Default-Migration, wenn `data/settings.json` fehlt.
- Theme-Koordinaten und Layoutwerte sollen in JSON bleiben, wenn bereits passende Keys existieren.

## 6. Data und Runtime

`data/settings.json` enthält Runtime-Settings wie aktives Theme, Theme-Liste, Fenstergröße und Debug-Konfiguration.

`data/cache/*.json` enthält vorbereitete Charakter-Caches. Diese Dateien entstehen aus Tabellenimporten oder UI-Speichern und sollten nicht manuell bearbeitet werden.

`data/current_character.json` merkt den aktiven Charaktercache, Charaktername, Ursprung und Ladezeitpunkt.

`assets/config/calculation_rules.json` und `assets/config/calculation_overrides.json` sind Default-Vorlagen. Zur Laufzeit verwendet das Tool die beschreibbaren Dateien in `data/config/`.

## 7. Berechnungszentrum

Das Berechnungszentrum zeigt:

- Cache-Formeln und Werte
- Formel-Traces und Fehler
- fehlende oder manuelle Berechnungsziele
- Calculation Rules
- Overrides
- verwaiste Overrides

Rules werden aktuell analysiert und mit Cache-Werten verglichen. `apply_to_cache` ist im Datenmodell vorhanden, wird aber nicht automatisch auf den Cache angewandt. Overrides sind eine eigene Analyse-/Notizschicht und überschreiben nicht direkt Excel- oder Cache-Formeln.

## 8. Roll20-Wurf-Assistent

Der Roll20-Wurf-Assistent nutzt einen zentralen Roll-Dialog.

Aktuelle Quellen und Funktionen:

- Fertigkeitswürfe
- Character-Initiative
- Wohlbefinden-Vorschläge
- Perk-/Nachteil-Vorschläge
- Spezialisierungs-Checkboxen
- Paradigma/Brennen bei normalen Skillwürfen
- Roll20-Kommando kopieren

Initiative nutzt den Character-Initiative-Wert aus dem Charakterbereich und nicht den normalen Skillwert. Direktes Senden an Roll20 ist als UI-Option vorhanden, aber aktuell nicht implementiert.

## 9. Debug und Logging

`app_logger.py` stellt bereit:

- `log_debug(category, message)`
- `log_info(category, message)`
- `log_warning(category, message)`
- `log_error(category, message)`

Standardbetrieb:

- Terminal bleibt ruhig.
- Warnings und Errors bleiben sichtbar.
- Debug-Ausgaben erscheinen nur, wenn Debug global und die Kategorie aktiv ist.

Debug-Konfiguration in `data/settings.json`:

```json
{
  "debug": {
    "enabled": false,
    "categories": {
      "paths": false,
      "theme": false,
      "cache": false,
      "save": false,
      "render": false,
      "character": false,
      "skills": false,
      "inventory": false,
      "equipment": false,
      "magic": false,
      "notes": false,
      "calculation": false,
      "roll20": false,
      "parser": false,
      "build": true
    }
  }
}
```

Bestehende UI-spezifische Debug-Flags in Theme-Layouts bleiben vorerst erhalten und werden nicht automatisch entfernt.

## 10. Build

PyInstaller-Build:

```bash
python build.py
```

Falls PyInstaller fehlt:

```bash
pip install pyinstaller
```

Der Build ist ein one-dir Build. `assets/` werden mitgegeben. Bei einer gebauten App wird `data/` neben der ausführbaren Datei erstellt und beschrieben. Die Pfadlogik liegt in `app_paths.py`.

## 11. Installation / Dependencies

Offensichtliche Python-Abhängigkeiten stehen in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Aktuell verwendet:

- PySide6
- openpyxl
- pyinstaller

ODS-Lesen nutzt Standardbibliotheken (`zipfile`, `xml.etree.ElementTree`) und benötigt keine zusätzliche ODS-Library.

## 12. Architekturregeln / STOP-Liste

- `DataLoader` baut keine UI.
- `FormulaParser` kennt keine UI.
- `ui_main.py` soll keine eigene Formelengine enthalten.
- `assets/` read-only behandeln.
- `data/` ist Runtime-/User-Bereich.
- Keine Theme-Koordinaten hart im Code ergänzen, wenn JSON-Keys vorhanden sind.
- `data/cache/*.json` nicht manuell verändern.
- `data/current_character.json` nicht manuell verändern.
- Excel-/ODS-/XLSX-Dateien nicht als Cleanup-Nebenwirkung ändern.
- Dead-Code erst nach separater Cleanup-Phase entfernen.

## 13. Bekannte Altlasten

`ui_main.py` ist groß und enthält viele historisch gewachsene Pfade. Ein Dead-Code-/Debug-/README-Audit liegt hier:

```text
docs/audit_dead_code_debug_readme.md
```

Cleanup 1.0 führt Logging ein und aktualisiert diese README. Dead-Code-Löschung, UI-Aufteilung und größere Refactors sind spätere Phasen.

