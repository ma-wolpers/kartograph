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
- Zusaetzlich zum globalen Symbolkatalog kann jeder Plan eigene, ausschliesslich dokumentationsgebundene Symbole fuehren (`SeatingPlan.custom_symbols: dict[str, CustomSymbolDefinition]`, Schluessel = stabile ID statt Bedeutungstext). `app/core/domain/effective_symbol.py::build_effective_documentation_symbols()` vereinheitlicht globalen Katalog (nur `role=documentation_only`) und eigene Symbole zu einer GUI-Projektion, ohne die Domain-Modelle zu vermischen; `app/core/domain/custom_symbol_validation.py` validiert Glyph (Grapheme-Cluster-Heuristik) und Tastenkuerzel (`Ctrl+Shift+<Buchstabe>`, geprueft gegen eine zentrale Liste reservierter Systemkuerzel).
- PDF-Export wird ueber einen dedizierten Infrastructure-Exporter umgesetzt.
- PNG-ZIP-Export (ein transparentes Sitzkaertchen je benanntem Schueler) nutzt dieselbe v4-Geometrieberechnung (`build_seat_geometries_v4`) wie PDF-Export und Sitzplan-Vorschau; Dateinamens-Aufloesung (`app/core/domain/student_png_export.py`) baut auf `compute_display_names()` auf, Rendering laeuft ueber Pillow (`app/infrastructure/exporters/student_png_renderer.py`, keine Datei-I/O), ZIP-Zusammenbau ueber einen duennen I/O-Wrapper (`student_png_zip_exporter.py`). Anders als der PDF-Export mappt der PNG-Renderer Weltkoordinaten ohne y-Invertierung auf Pixel, weil Pillow (wie die Tkinter-Canvases von Grid und Sitzplan-Vorschau) y nach unten wachsen laesst -- nur ReportLabs PDF-Koordinatensystem waechst nach oben und braucht deshalb die Invertierung.

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
- Der Symbolkatalog enthaelt zusaetzlich die Spezialsymbole `X` (nicht abgegeben/verweigert), `∅` (abwesend) und `☐` (Aufgaben nicht gemacht); sie werden ueber dieselbe Konfigurations- und Shortcut-Pipeline geladen.
- Eigene Doku-Symbole toggeln ueber denselben Mechanismus wie eingebaute dokumentationsgebundene Symbole (`record_symbol()`/`RecordDocumentationSymbolIntent`, generisch ueber beliebige Symbol-Schluessel) und erscheinen dadurch automatisch auch tagesaktuell auf dem Tisch im Raster. Ihr Tastenkuerzel-Raum (`Ctrl+Shift+<Buchstabe>`) ist vollstaendig getrennt vom Einzelbuchstaben-Raum eingebauter Symbole; die komplette freie Buchstabenmenge wird einmalig beim Start gebunden, ein Handler loest pro Tastendruck live gegen den aktuell offenen Plan auf -- kein Rebind bei Planwechsel. Verwaltet werden eigene Symbole ueber ein eigenes Popup ("Symbol-Verwaltung", Ansicht-Menue/Toolbar), das auch alle eingebauten Symbole samt Bewertungsstufen zur Referenz anzeigt.
- Preview-Rendering und PDF-Export verwenden dieselbe Domain-Transformationslogik fuer Tischgruppen (x/y-Shift, Rotation), damit die Darstellung konsistent bleibt.
- Der Markierungsrahmen fuer aktive Auswahlen wird aus transformierten Tischpolygonen abgeleitet, damit Shift/Rotation der Tischgruppe visuell korrekt abgebildet werden.
- Bei Transformationskollisionen (Lehrer- oder Schuelertisch) wird der zuletzt geaenderte Transformationswert auf 0 zurueckgesetzt.
- Exportaktionen werden in der GUI angestossen und durch den Infrastructure-Exporter als PDF geschrieben.
- Der PNG-ZIP-Export berechnet die Tisch-Pixelgeometrie einmal pro Export (`GeometryTransform`) und rendert daraus pro benanntem Schueler ein eigenes PNG mit identischer Bildgroesse/Skalierung; nur die Fuellfarbe des eigenen Tisches wechselt. Schichtgrenzen strikt eingehalten: Domain (`student_png_export.py`) kennt Pillow nicht, der Renderer macht kein Datei-I/O, der ZIP-Exporter macht kein GUI, die GUI waehlt nur den Zielpfad und startet den Export ueber ein No-Op-Intent (analog PDF/CSV).

## Bekannte Ausnahmen vom 300-Zeilen-Limit
- `app/adapters/gui/main_window.py` (~407 Codezeilen ohne Docstrings/Kommentare/Imports/Leerzeilen, Stand: eigene Doku-Symbole-Feature): zentrale Fensterklasse, die ~30 GUI-Mixins zusammensetzt und `apply_state()` orchestriert — Aufsplitten wuerde die zusammenhaengende Tk-Widget-Verdrahtung und den State-Sync-Callback fragmentieren, ohne die Zeilenzahl wirklich zu senken.
- `tests/test_app_controller.py` (~1243 Codezeilen ohne Docstrings/Kommentare/Imports/Leerzeilen, Stand: eigene Doku-Symbole-Feature): eine Testdatei, kein Programm-Feature — die Struktur folgt bewusst der Handler-Isolation-Gliederung der Applikationsschicht (`TestHandle<Feature>Handlers`-Klassen), nicht eigenen fachlichen Modulgrenzen. Ein Split nach Zeilenzahl wuerde diese 1:1-Zuordnung zu den Handler-Modulen aufbrechen, ohne einen Klarheitsgewinn zu bringen.
- `app/adapters/gui/_mixin_shortcuts.py` (~282 Codezeilen ohne Docstrings/Kommentare/Imports/Leerzeilen, Stand: Buchstaben-Shortcuts fuer eigene Doku-Symbole): zentrale Registrierung *aller* globalen und modusspezifischen Tastenkuerzel plus der Runtime-Kontext-Auswertung (`_build_runtime_context`, `_bind_runtime_shortcut`, `_handle_intent`). War bereits vor diesem Feature ueber dem Richtmass; die Umstellung der eigenen-Symbol-Kuerzel von `Ctrl+Shift+<Buchstabe>` auf einfache Buchstaben hat die Datei um eine zweite, analoge Bindeschleife (Gross-/Kleinschreibung) erweitert. Ein Split (z. B. Bindungs-Registrierung vs. Runtime-Auswertung) waere moeglich, wurde aber bewusst nicht im Rahmen dieses Bugfix-Batches vorgenommen, um keinen unabhaengigen Refactor in die Aenderung hineinzuziehen — bei der naechsten inhaltlichen Aenderung an dieser Datei nachholen.

## Build- und Laufzeitkontext
- Start lokal ueber `start-kartograph.bat` oder `python kartograph.py`.
- Abhaengigkeiten sind in `requirements.txt` definiert.
