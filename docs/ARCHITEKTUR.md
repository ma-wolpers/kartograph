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
- Archivierte Sitzplaene liegen als dieselben, unveraenderten JSON-Dateien im Unterordner `plans/ALT/`. Da `list_plans()` nicht rekursiv arbeitet, ist die Ordnerlage die alleinige Quelle der Wahrheit fuer "archiviert" — kein zusaetzliches Feld im Planformat. Sichtbarkeit archivierter Plaene in der Planliste ist eine persistente Einstellung (`KartographSettings.show_archived_plans`).
- Bei jedem Speichern wird zusaetzlich ein zeitgestempeltes JSON-Backup in einem versteckten AppData-Pfad (`%APPDATA%/Kartograph/backups/<plan>`) abgelegt; pro Lerngruppe bleibt eine Rotation der letzten 20 Sicherungen erhalten.
- Zusaetzlich erzeugt die GUI in festem Intervall (5 Minuten) Snapshot-Backups des aktuell geoeffneten Plans ueber die Repository-Backup-API, ohne die Primardatei neu zu schreiben.
- Symboldefinitionen werden aus `config/symbols.json` gelesen und validiert.
- PDF-Export wird ueber einen dedizierten Infrastructure-Exporter umgesetzt.

## Datenfluss
- GUI-Interaktionen werden in Use-Cases ueberfuehrt.
- KeyBindings werden zentral ueber `bw_libs/ui_contract/keybinding.py` verwaltet; modebezogene Aktivierungen und Konflikte sind dort nachvollziehbar.
- Pop-up-Verhalten wird zentral ueber `bw_libs/ui_contract/popup.py` mit einheitlicher Focus-/Lifecycle-Policy gefuehrt.
- HSM-Vertragslogik fuer Intent-Katalog, Escape-Prioritaet und Transition-Validierung liegt zentral in `bw_libs/ui_contract/hsm.py`.
- Globale Keyboard-Shortcuts werden im GUI-Adapter auf UI-Intents gemappt; `Strg+T` oeffnet das Tischgruppen-Overlay, `1..9` toggeln Farbpunkte am markierten Schuelertisch.
- Use-Cases lesen/schreiben ueber Repository-Schnittstellen.
- Persistenz erfolgt ueber JSON-Repository-Implementierungen.
- Tischgruppen-Metadaten werden im JSON-Repository serialisiert und beim Laden (inkl. Legacy-Defaults) normalisiert.
- Farbmarker und deren planweite Bedeutungen werden im JSON-Repository serialisiert; ungenutzte Bedeutungszeilen werden beim Mutieren/Laden bereinigt.
- Symbolkonfiguration wird beim App-Start geladen und in der GUI als Katalog/Legende genutzt.
- Das S:S-Detailoverlay (Name, Symbole, Farbbuttons) ist in der Ansicht links/rechts/unten andockbar; das Tischgruppen-Overlay kann ebenfalls links/rechts/unten positioniert werden (persistente Settings).
- Die Editoransicht unterstuetzt zwei Oberflaechen: Rasteransicht und Dokumentationsansicht. Der Wechsel erfolgt ueber UI-Intent (`view.documentation.toggle`) und teilt sich denselben geladenen Planzustand.
- Die Dokumentationsansicht rendert eine zeilenorientierte Schuelertabelle mit Datums-Spalten, symbolischer Tagesdarstellung, Zusammenfassungs- und Notenspalten sowie Gesamtnotenanzeige aus den Core-Use-Cases.
- Die Dokumentationsansicht ist horizontal geteilt: links/mitte scrollen Datums-Spalten, rechts steht eine synchronisierte, horizontal fixe Tabelle fuer Zusammenfassung, Notenspalten und Gesamtnote.
- Symbol-Shortcuts gelten in beiden Editoroberflaechen: In der Rasteransicht toggeln sie Sitzplan-Symbole, in der Dokumentationsansicht schreiben sie in die aktuell markierte Tageszelle der ausgewaehlten Schuelerzeile.
- Der Symbolkatalog enthaelt zusaetzlich die Spezialsymbole `X` (nicht abgegeben/verweigert) und `∅` (abwesend); sie werden ueber dieselbe Konfigurations- und Shortcut-Pipeline geladen.
- Preview-Rendering und PDF-Export verwenden dieselbe Domain-Transformationslogik fuer Tischgruppen (x/y-Shift, Rotation), damit die Darstellung konsistent bleibt.
- Der Markierungsrahmen fuer aktive Auswahlen wird aus transformierten Tischpolygonen abgeleitet, damit Shift/Rotation der Tischgruppe visuell korrekt abgebildet werden.
- Bei Transformationskollisionen (Lehrer- oder Schuelertisch) wird der zuletzt geaenderte Transformationswert auf 0 zurueckgesetzt.
- Exportaktionen werden in der GUI angestossen und durch den Infrastructure-Exporter als PDF geschrieben.

## Bekannte Ausnahmen vom 300-Zeilen-Limit
- `app/adapters/gui/main_window.py` (329 Codezeilen ohne Docstrings/Kommentare/Imports/Leerzeilen): zentrale Fensterklasse, die ~30 GUI-Mixins zusammensetzt und `apply_state()` orchestriert — Aufsplitten wuerde die zusammenhaengende Tk-Widget-Verdrahtung und den State-Sync-Callback fragmentieren, ohne die Zeilenzahl wirklich zu senken.
- `tests/test_app_controller.py` (~1060 Codezeilen ohne Docstrings/Kommentare/Imports/Leerzeilen, 103 Testmethoden): eine Testdatei, kein Programm-Feature — die Struktur folgt bewusst der Handler-Isolation-Gliederung der Applikationsschicht (`TestHandle<Feature>Handlers`-Klassen), nicht eigenen fachlichen Modulgrenzen. Ein Split nach Zeilenzahl wuerde diese 1:1-Zuordnung zu den Handler-Modulen aufbrechen, ohne einen Klarheitsgewinn zu bringen.

## Build- und Laufzeitkontext
- Start lokal ueber `start-kartograph.bat` oder `python kartograph.py`.
- Abhaengigkeiten sind in `requirements.txt` definiert.
