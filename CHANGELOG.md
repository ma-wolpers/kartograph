# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

## [0.2.1] - 2026-05-04

### Changed
- App identity metadata is now centralized in `app/app_info.py`; startup shell settings and backup appdata folder naming now read from this shared identity source.
- Application startup now uses a centralized GUI dependency builder (`AppDependencies`) and a shared Tk shell lifecycle configuration (`bw_libs/app_shell.py`).
- Plan and symbol-config JSON persistence now use the centralized atomic writer from `bw_libs/app_paths.py`.
- Shared app path/atomic-write foundation introduced via `bw_libs/app_paths.py`; settings persistence now uses the centralized atomic JSON writer.
- Central UI contracts for keybindings, popup policy, and HSM semantics now live in shared `bw_libs/ui_contract` modules to avoid duplicate maintenance.
- Escape navigation now follows a centralized priority order: close active popup first, then leave inline editing, then return to the parent view.
- Runtime shortcuts now validate their intents against a central HSM contract before execution.
- Intent dispatch now blocks unknown intents early, improving navigation and shortcut compatibility guarantees.
- The shortcut runtime debug popup now runs as a non-blocking parallel popup and no longer forces dialog-mode shortcut resolution for the main window.
- Grundlage fuer vereinheitlichte Tastatur- und Popup-Steuerung eingefuehrt: zentrale Module fuer KeyBindings (`bw_libs/ui_contract/keybinding.py`) und Popup-Policies (`bw_libs/ui_contract/popup.py`) sind jetzt Teil der App-Struktur.
- Global shortcuts are now routed through a centralized runtime keybinding resolver with mode/offline/text-focus/dialog evaluation.
- Popup lifecycle is now tracked centrally for runtime shortcut dialog-priority decisions.
- Debug runtime controls were integrated into the intent pipeline (`OPEN_SHORTCUT_RUNTIME_DEBUG`, `TOGGLE_SHORTCUT_RUNTIME_OFFLINE`).
- Guardrail checks now validate runtime integration and debug intent routing in addition to module presence.
- Governance checks now enforce changelog updates for user- or co-developer-relevant changes, and commit/push process hints are local-only (not emitted in CI logs).
- In der Dokumentationsansicht gibt es keinen Moduswechsel mehr: der Toolbar-Button und `Strg+M` wurden entfernt.
- Enter navigiert in der Dokumentationsansicht nicht mehr; Enter betritt das Eingabefeld der aktiven Notenspalte bzw. schließt es wieder.
- Die aktive Doku-Zelle ist jetzt immer sichtbar markiert, auch ohne offenen Schreibmodus (helle Zellhervorhebung gegen dunklen Zeilenhintergrund).
- Der aktive Spaltenkopf wird jetzt fuer beide Tabellenbereiche (Datumsspalten und fixe Spalten rechts) sichtbar markiert.
- Neue Runtime-Debug-Ansicht fuer Shortcuts unter `Ansicht` mit Offline-Simulation (`Strg+Shift+R`, `Strg+Shift+O`).
- Runtime module tests added for keybinding evaluation and popup policy stack behavior.

### Fixed
- Startup no longer crashes when runtime shortcuts are registered: docs/global shortcut intents are now declared centrally and validated successfully.

## [0.2.0] - 2026-04-22

### Added
- Project guardrails for architecture docs, development log updates, and changelog governance.
- Automated AI guardrail check in CI for repository policy compliance.

### Changed
- Enter im Editor setzt den Fokus jetzt zuverlaessig ins Namensfeld eines Schuelertischs (bei Lehrertischen bleibt Namenseditierung gesperrt).
- Der Cursor im Namensfeld landet beim Enter-Einstieg am Ende des Textes ohne Vollmarkierung.
- Symbol-Buttons schalten jetzt zyklisch pro Symbol durch 0, 1, 2, 3 und zurueck auf 0.
- Unter dem Schuelernamen werden gedrueckte Symbole als wiederholte Unicode-Glyphen angezeigt statt als Textnamen.
- Status und Markierung wurden in einer gemeinsamen Infozeile zusammengefuehrt; die Markierung steht rechtsbuendig.
- Symboldefinitionen werden jetzt aus `config/symbols.json` eingelesen, inklusive Unicode-Codepoint, Bedeutung und Legendenstufen (one/two/three).
- Symboldefinitionen unterstuetzen jetzt zusaetzlich Shortcut-Buchstaben; bei markiertem Schuelertisch kann das zugeordnete Symbol direkt per Taste ausgeloest werden.
- Schuelernamen werden in Kacheln standardmaessig in der oberen Haelfte gerendert, damit darunter dauerhaft Platz fuer Symbolzeilen bleibt.
- Die Namensschrift fuer Schuelertische wird jetzt global einheitlich skaliert: Wenn ein Name nicht in eine Kachel passt, wird die Schrift fuer alle Schuelertische gemeinsam verkleinert.
- Unter dem Namen eines Schuelertischs erscheinen pro aktivem Symbol eigene Erklaerungszeilen mit count-basierter Bedeutung.
- Neue Plandateien nutzen keine zufaelligen Dateianhaenge mehr; bei Namenskonflikten fragt die App nach dem Ueberschreiben.
- Das Canvas ist jetzt auf 101x101 Kacheln begrenzt (von -50 bis +50 je Achse); Navigation und Bearbeitung bleiben strikt innerhalb dieses Bereichs.
- `Strg+0` setzt den Standard-Zoom zurueck und zentriert/markiert den Lehrertisch.
- Kartograph verwendet jetzt die erweiterten Kursplaner-Farbthemes (mehrere helle und dunkle Varianten).
- Undo/Redo wurde eingefuehrt (`Strg+Z`, `Strg+Y`) mit bis zu 20 Rueckschritten und zusaetzlicher Aktion zum Rueckgaengigmachen der letzten 5 Aenderungen auf einmal.
- Mehrfachauswahl als Rechteck ist jetzt per Maus-Drag oder `Shift`+Pfeiltasten moeglich.
- Rechteckiges Ausschneiden/Kopieren/Einfuegen (`Strg+X`, `Strg+C`, `Strg+V`) funktioniert jetzt inklusive planuebergreifendem Clipboard; der Lehrertisch bleibt dabei stets geschuetzt.
- Scrollbar-/Leistenfarben wurden an das Theme angepasst, damit die zuvor braunen Streifen im unteren Bereich entfallen.
- Lehrertisch-Farbton wurde entsaettigt und leicht abgedunkelt; die Beschriftung ist jetzt weiss (auch im PDF-Export).
- Die Canvas-Groesse ist jetzt in den Einstellungen als Radius konfigurierbar (1 bis 50 Kacheln pro Richtung, Standard 50).
- Beim Verkleinern des Canvas in den Einstellungen warnt die App, wenn im aktuell geoeffneten Plan dadurch nicht mehr alle Schuelertische sichtbar waeren.
- Beim Oeffnen eines Plans warnt die App, wenn enthaltene Daten ausserhalb des aktuellen Canvas-Bereichs liegen und daher nicht vollstaendig dargestellt werden koennen.
- Der untere Detailbereich (u. a. hinter Namensfeld und Symbolbuttons) nutzt jetzt konsistente Theme-Flaechen statt bräunlicher Default-Hintergruende.

### Added
- Exportfunktion als PDF (A4 quer) mit zwei Perspektiven: Lehrertisch unten oder oben (180° Raumansicht).
