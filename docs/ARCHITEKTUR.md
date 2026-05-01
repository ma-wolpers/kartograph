# Architektur (kartograph)

Dieses Dokument beschreibt den aktuellen Ist-Zustand.

## Architekturueberblick
- Einstiegspunkt ist `kartograph.py`.
- Die Anwendung ist in Schichten unter `app/` organisiert:
  - `app/core`: Domainmodell und Use-Cases.
  - `app/infrastructure`: Dateisystem-/Persistenzzugriffe.
  - `app/adapters/gui`: GUI-Adapter und Fensterlogik.
- Tischgruppen werden im Domain-Layer als Zusammenhangskomponenten (4er-Nachbarschaft) aus Schuelertischen berechnet; Lehrertische sind ausgeschlossen. Leere Schuelertische koennen Teil einer benannten Tischgruppe sein, duerfen aber keine eigene Tischgruppe bilden.
- Pro Tischgruppe werden Metadaten (TG-Nummer, x/y-Shift, Rotation) pro Schuelertisch persistiert und bei allen Planmutationen normalisiert.
- Pro Schuelertisch werden optionale Farbmarker (`color_markers`) persistiert; planweit werden Farb-Bedeutungen (`color_meanings`) gefuehrt.
- Das Planmodell wurde auf JSON v3 erweitert: planweit werden Dokumentationstage (`documentation.dates`), Notenspalten (`documentation.grade_columns`) und Gewichtung schriftlich/sonstig (`documentation.grade_weighting`) gehalten.
- Pro Schuelertisch koennen tagesbasierte Dokumentationseintraege (`documentation_entries`) gespeichert werden mit Symbolstaerken, Notenwerten und optionaler Notiz.
- Leere Tageskontexte bleiben volatil: Beim Speichern werden nur Dokumentationstage persistiert, die mindestens einen inhaltlichen Eintrag enthalten.
- Sitzplaene werden als JSON-Dateien in `plans/` abgelegt.
- Bei jedem Speichern wird zusaetzlich ein zeitgestempeltes JSON-Backup in einem versteckten AppData-Pfad (`%APPDATA%/Kartograph/backups/<plan>`) abgelegt; pro Lerngruppe bleibt eine Rotation der letzten 20 Sicherungen erhalten.
- Symboldefinitionen werden aus `config/symbols.json` gelesen und validiert.
- PDF-Export wird ueber einen dedizierten Infrastructure-Exporter umgesetzt.

## Datenfluss
- GUI-Interaktionen werden in Use-Cases ueberfuehrt.
- Globale Keyboard-Shortcuts werden im GUI-Adapter auf UI-Intents gemappt; `Strg+T` oeffnet das Tischgruppen-Overlay, `1..9` toggeln Farbpunkte am markierten Schuelertisch.
- Use-Cases lesen/schreiben ueber Repository-Schnittstellen.
- Persistenz erfolgt ueber JSON-Repository-Implementierungen.
- Tischgruppen-Metadaten werden im JSON-Repository serialisiert und beim Laden (inkl. Legacy-Defaults) normalisiert.
- Farbmarker und deren planweite Bedeutungen werden im JSON-Repository serialisiert; ungenutzte Bedeutungszeilen werden beim Mutieren/Laden bereinigt.
- Symbolkonfiguration wird beim App-Start geladen und in der GUI als Katalog/Legende genutzt.
- Das S:S-Detailoverlay (Name, Symbole, Farbbuttons) ist in der Ansicht links/rechts/unten andockbar; das Tischgruppen-Overlay kann ebenfalls links/rechts/unten positioniert werden (persistente Settings).
- Die Editoransicht unterstuetzt zwei Oberflaechen: Rasteransicht und Dokumentationsansicht. Der Wechsel erfolgt ueber UI-Intent (`view.documentation.toggle`) und teilt sich denselben geladenen Planzustand.
- Die Dokumentationsansicht rendert eine zeilenorientierte Schuelertabelle mit Datums-Spalten, symbolischer Tagesdarstellung, Zusammenfassungs- und Notenspalten sowie Gesamtnotenanzeige aus den Core-Use-Cases.
- Symbol-Shortcuts gelten in beiden Editoroberflaechen: In der Rasteransicht toggeln sie Sitzplan-Symbole, in der Dokumentationsansicht schreiben sie in die aktuell markierte Tageszelle der ausgewaehlten Schuelerzeile.
- Der Symbolkatalog enthaelt zusaetzlich die Spezialsymbole `X` (nicht abgegeben/verweigert) und `∅` (abwesend); sie werden ueber dieselbe Konfigurations- und Shortcut-Pipeline geladen.
- Preview-Rendering und PDF-Export verwenden dieselbe Domain-Transformationslogik fuer Tischgruppen (x/y-Shift, Rotation), damit die Darstellung konsistent bleibt.
- Der Markierungsrahmen fuer aktive Auswahlen wird aus transformierten Tischpolygonen abgeleitet, damit Shift/Rotation der Tischgruppe visuell korrekt abgebildet werden.
- Bei Transformationskollisionen (Lehrer- oder Schuelertisch) wird der zuletzt geaenderte Transformationswert auf 0 zurueckgesetzt.
- Exportaktionen werden in der GUI angestossen und durch den Infrastructure-Exporter als PDF geschrieben.

## Build- und Laufzeitkontext
- Start lokal ueber `start-kartograph.bat` oder `python kartograph.py`.
- Abhaengigkeiten sind in `requirements.txt` definiert.
