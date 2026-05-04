# ⚔️ PROJECT STRUCTURE – VERBINDLICHE ARCHITEKTUR

WICHTIG:
Diese Struktur darf NICHT verändert werden.
Keine neuen Systeme erfinden.
Keine Verantwortlichkeiten verschieben.

---

## 🧠 GRUNDPRINZIP

Das Projekt ist in 3 Ebenen getrennt:

1. Daten (Excel)
2. UI-Struktur (main_view)
3. Detail-Komponenten (SheetTabs)

---

## 📂 DATEIEN UND IHRE AUFGABEN

### 🔹 main.py

* Startpunkt des Programms
* Erstellt QApplication
* Startet ui_main
* KEINE UI Logik
* KEINE Datenlogik

---

### 🔹 ui_main.py (HAUPTFENSTER)

DAS IST DIE SICHTBARE UI

Aufgaben:

* Hauptlayout definieren
* Sichtbare Panels darstellen
* Design (Stylesheet) setzen
* Navigation steuern

WICHTIG:

* NUR ui_main bestimmt, was der User sieht
* SheetTabs sind NICHT direkt sichtbar

Struktur:

* LEFT PANEL → Tabelle (Grid)
* RIGHT PANEL → Formelliste + Editor

👉 ui_main ist IMMER sichtbar

---

### 🔹 ui_tabs/sheet_tab.py

DAS IST BACKEND UI (NICHT DIREKT SICHTBAR)

Aufgaben:

* Daten eines Sheets verwalten
* Tabellenstruktur bereitstellen
* Formeln liefern

WICHTIG:

* KEIN eigenes Fenster
* KEIN eigenes Styling
* KEIN sichtbares Layout

👉 SheetTab liefert Daten, NICHT UI

---

### 🔹 data_loader.py

Aufgaben:

* Excel laden
* Sheets auslesen
* Zellwerte extrahieren
* Speichern/Laden Sheet Chache


---

### 🔹 formula_parser.py

Aufgaben:

* Formeln erkennen
* Formeln speichern
* Struktur:
  {
  "Sheet": {
  "A1": "=FORMEL"
  }
  }

---

## ⚠️ WICHTIGE REGELN

STOP:

❌ SheetTab darf KEIN sichtbares UI bauen
❌ SheetTab darf KEIN Styling enthalten
❌ ui_main darf KEINE Excel Logik enthalten
❌ Keine doppelte UI-Struktur

---

## 🎮 DESIGN REGEL

* Styling wird NUR in ui_main gesetzt
* Stylesheet global auf Hauptfenster
* KEIN Styling in einzelnen Komponenten

---

## 🧩 DATENFLUSS

Excel → data_loader → SheetTab → ui_main

👉 ui_main fragt Daten von SheetTab ab
👉 ui_main zeigt alles an

---

## 🔥 PROBLEM (WARUM DESIGN NICHT SICHTBAR WAR)

* Design wurde in SheetTab implementiert
* SheetTab ist unsichtbar
* ui_main zeigt nur main_view ohne Design

👉 Ergebnis: KEINE Änderung sichtbar

---

## ✅ LÖSUNG

* Design MUSS in ui_main passieren
* ui_main muss Panels darstellen
* SheetTab bleibt Datenquelle

---

## 🎯 ZIEL

* Klare Trennung
* Sichtbares UI nur in ui_main
* Backend Logik nur in SheetTab

---

WENN ETWAS UNKLAR IST:
→ minimal entscheiden
→ KEINE neue Architektur erfinden
