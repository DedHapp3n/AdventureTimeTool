# Adventure Time Tool

## 1. Projektziel

Das Projekt ist ein assetbasiertes Fantasy-RPG-Character-Tool.

Der aktuelle Fokus liegt darauf, Charakterdaten aus echten Tabellen-Dateien zu importieren, in einem JSON-Cache vorzubereiten und anschließend in einer themenbasierten Fantasy-UI darzustellen.

Wichtig bleibt:

* Keine neue Architektur erfinden
* Verantwortlichkeiten sauber trennen
* Sichtbare Fantasy-UI nur dort bauen, wo sie hingehört
* Daten, Formelberechnung, Cache und Rendering nicht vermischen

---

## 2. Aktuelle Ordnerstruktur

```text
AdventureTimeTool/
├── main.py
├── ui_main.py
├── data_loader.py
├── formula_parser.py
├── ui_tabs/
│   └── sheet_tab.py
├── assets/
│   ├── config/
│   │   └── theme_config.json
│   └── themes/
│       └── <theme>/
│           ├── ui_layout.json
│           └── ui/
│               └── ...
└── data/
    ├── cache/
    │   └── *.json
    └── current_character.json
```

---

## 3. Aufgaben der Dateien

### main.py

* Startpunkt des Programms
* Erstellt `QApplication`
* Erstellt `MainWindow`
* Enthält keine UI-Logik
* Enthält keine Datenlogik

### ui_main.py

`ui_main.py` enthält die sichtbare Haupt-UI.

Aufgaben:

* Baut `GameCanvas` / Hauptfläche
* Baut und rendert das `MainFrame`-Asset als Programmhintergrund
* Lädt das aktive Theme
* Liest `assets/themes/<theme>/ui_layout.json`
* Rendert die Hauptnavigation
* Rendert die Settings-Seite
* Rendert den Character-Screen
* Rendert Panels und Texte
* Öffnet das Debug-Fenster / den Debug-Dialog
* Darf Styles, Assets und Layouts setzen
* Darf Daten aus `DataLoader` und Cache anzeigen

Nicht in `ui_main.py`:

* Keine Excel-/ODS-Parserlogik
* Keine eigene Formel-Engine
* Keine hart codierten Theme-Koordinaten, wenn sie in JSON gehören

### data_loader.py

`data_loader.py` ist für Dateiimport, Cache-Aufbau und Charakter-Cache-Verwaltung zuständig.

Aufgaben:

* Lädt `.xlsx`, `.xlsm` und `.ods`
* Baut `cell_cache`
* Ruft `FormulaParser.recalculate_cache()` auf
* Speichert charakterbezogene JSON-Caches in `data/cache/`
* Verwaltet den aktiven Charakter über `data/current_character.json`
* Listet vorhandene Charakter-Caches
* Lädt Charakter-Caches

Nicht in `data_loader.py`:

* Keine sichtbare UI bauen
* Keine Fantasy-Layouts rendern

### formula_parser.py

`formula_parser.py` ist für Formel-Erkennung, Normalisierung und Berechnung im Cache zuständig.

Aufgaben:

* Erkennt Zellreferenzen
* Normalisiert einfache Excel-/deutsche Formelsyntax
* Berechnet Formeln im Cache
* Unterstützt einfache Zellreferenzen
* Unterstützt Grundrechenarten
* Unterstützt `SUM` / `SUMME`
* Unterstützt einfache `IF` / `WENN`-Logik
* Unterstützt Bereiche
* Schreibt berechnete Werte in `cell_cache[*][*]["value"]`

Wichtig:

* Die UI zeigt keine Formelstrings an
* Die UI liest für sichtbare Werte `value`
* `formula_parser.py` kennt keine UI

### ui_tabs/sheet_tab.py

`SheetTab` ist aktuell eine Debug-/Sheet-Datenstruktur.

Aufgaben:

* Baut Cell-Cache für SheetTab-Fälle
* Liefert Daten und Formeln für Debug-Tabellen
* Verwaltet Sheet-bezogene Datenstrukturen

Nicht in `SheetTab`:

* Kein eigenes Hauptfenster
* Kein sichtbares Fantasy-UI bauen
* Kein Fantasy-UI-Styling enthalten

---

## 4. Datenfluss

### Import

```text
xlsx / xlsm / ods
→ data_loader.load_file()
→ cell_cache bauen
→ formula_parser.recalculate_cache()
→ data/cache/<character>.json speichern
→ data/current_character.json aktualisieren
→ ui_main rendert aus cell_cache
```

### Programmstart

```text
data/current_character.json
→ data_loader lädt aktiven Cache
→ ui_main rendert aktiven Charakter
```

### Debug

```text
ui_main öffnet Debug-Fenster
→ Tabellenansicht aus Cache- / Sheet-Daten
```

---

## 5. Theme-/Asset-System

Themes liegen unter:

```text
assets/themes/<theme>/
```

Ein Theme besteht aus:

* `ui_layout.json`
* `ui/...` für die verwendeten UI-Assets

`assets/config/theme_config.json` merkt das aktive Theme und die verfügbaren Themes.

Das aktive Theme wird in `ui_main.py` geladen. `ui_main.py` liest anschließend die passende `ui_layout.json` und rendert daraus Canvas, MainFrame, Navigation, Content-Bereich, Settings-Seite, Character-Screen, Panels und Texte.

Themewechsel:

* Per Settings-Button / Settings-Seite
* Per `F3`

Wichtig:

* Layout-Koordinaten gehören in `ui_layout.json`
* Panel-Positionen gehören in `ui_layout.json`
* Textpositionen gehören in `ui_layout.json`
* Sichtbares Rendering passiert trotzdem in `ui_main.py`

---

## 6. Character-Screen-System

Der Character-Screen ist aktuell nicht in eine eigene Python-Datei ausgelagert.

Er wird in `ui_main.py` über `render_character_screen()` gerendert.

Genutzter Layout-Bereich:

```text
character_screen
```

aus:

```text
assets/themes/<theme>/ui_layout.json
```

Aktuelle Hauptpanels:

* `character_info_panel`
* `attribute_panel`
* `perk_panel`

Daten kommen aus:

```text
character_screen.data_map
```

Textpositionen kommen aus:

```text
character_screen.text_layout
```

Wichtig:

* Keine Texte hart im Code positionieren, wenn JSON-Werte vorhanden sind
* Jede Textdefinition soll `font_size` und `color` unterstützen
* Die UI zeigt nur Cache-`value`, keine Formelstrings
* Datenbindung soll über `data_map` laufen

---

## 7. Settings-/Debug-System

Die Settings-Seite ist Teil der Haupt-UI und wird in `ui_main.py` gerendert.

Sie enthält aktuell:

* Theme-Anzeige
* Theme wechseln
* Aktiver Charakter
* Dropdown mit vorhandenen JSON-Caches
* Charakter laden / importieren
* Liste aktualisieren
* Debug öffnen
* Debug beim Start anzeigen
* Cache neu laden

Wichtig:

* Charakter laden/importieren soll echte Tabellen-Dateien importieren
* Unterstützte Importformate: `.xlsx`, `.xlsm`, `.ods`
* Das Dropdown zeigt vorhandene JSON-Caches aus `data/cache/`
* Debug ist ein separates Debug-Fenster / ein separater Dialog mit Tabellenansicht

---

## 8. Cache-System

Charakter-Caches liegen unter:

```text
data/cache/*.json
```

Sie entstehen aus importierten Tabellen-Dateien und enthalten den vorbereiteten `cell_cache`.

Der aktive Charakter wird gemerkt in:

```text
data/current_character.json
```

Diese Datei merkt:

* Aktive Cache-Datei
* Charaktername
* Ursprungsdatei (`source_file`)
* Zeitpunkt des letzten Ladens

Die UI rendert aus dem aktiven Cache. Sichtbare Werte kommen aus `value`.

---

## 9. Wichtige Regeln / STOP-Liste

STOP:

* `SheetTab` darf kein sichtbares Fantasy-UI bauen
* `SheetTab` darf kein Styling enthalten
* `ui_main.py` darf keine Excel-/ODS-Parserlogik enthalten
* `ui_main.py` darf keine Formel-Engine enthalten
* `formula_parser.py` darf keine UI kennen
* `data_loader.py` darf keine sichtbare UI bauen
* Keine doppelte UI-Struktur
* Keine Theme-Koordinaten hart in Python, wenn sie in JSON gehören
* Keine Formelstrings im Frontend anzeigen
* Keine falsche Annahme, dass der Character-Screen bereits eine eigene `.py`-Datei hat

---

## 10. Aktueller Stand / bekannte nächste Schritte

Aktueller Stand:

* Assetbasierte Haupt-UI mit `GameCanvas`
* `MainFrame`-Asset als Programmhintergrund
* Content-Layer innerhalb `content_area`
* Hauptnavigation oben:
  * Charakter
  * Fertigkeiten
  * Inventar
  * Ausrüstung
  * Magie
  * Notizen
* Settings über Settings-Button
* Themewechsel per `F3`
* Character-Screen wird in `ui_main.py` gerendert
* Debug als separates Debug-Fenster / Dialog mit Tabellenansicht
* Import von `.xlsx`, `.xlsm` und `.ods`
* Charakter-Caches in `data/cache/`
* Aktiver Charakter über `data/current_character.json`

Bekannte nächste Schritte:

* Attribute-Ansicht weiter ausbauen
* Perk-/Nachteil-Daten später für Würfellogik nutzbar machen
* Character-Screen-Panels weiter per JSON feinjustieren
* Editierbare Felder später sauber über `data_map` / `edit_target` lösen
* Weitere Tabs ausbauen:
  * Fertigkeiten
  * Inventar
  * Ausrüstung
  * Magie
  * Notizen
