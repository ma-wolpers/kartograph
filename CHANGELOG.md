# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Added
- Neue Mitarbeit-Tagesbewertung: bei markiertem Tisch (Sitzplan) oder ausgewähltem Schüler (Dokutabelle) setzt `+` (positive Mitarbeit), `o` (okay), `-` (verbesserungswürdig) oder `s` (☆, besonders gute Mitarbeit) eine Bewertung für den heutigen Tag, sichtbar direkt auf dem Tisch im Sitzplan-Raster und in der Dokumentationstabelle. Erneutes Drücken der bereits gesetzten Bewertung löscht sie wieder; pro Tag ist immer nur eine der vier Bewertungen aktiv.
- Der Tastaturkürzel-Buchstabe für "Symbol zum markierten Platz hinzufügen" wurde von "S" auf "D" geändert (wegen der neuen Mitarbeit-Bewertung auf "s") und funktioniert jetzt auch tatsächlich als Tastenkürzel (vorher nur als Tooltip-Hinweis ohne echte Wirkung).
- Der Symbolfilter-Dialog (Raster) hat jetzt das Tastenkürzel `Ctrl+F` statt des bisher nur behaupteten, aber nie funktionierenden `Ctrl+Alt+S`. Enter bestätigt jetzt außerdem wie im jeweiligen Tooltip versprochen im Symbolfilter-Dialog, im PDF-Export-Dialog, im Namenfit-CSV-Export-Dialog und im "Symbol hinzufügen"-Dialog (vorher ohne Wirkung).
- Vorname, Nachname und Spitzname werden beim Tippen nicht mehr bei jedem Tastendruck sofort gespeichert, sondern gebündelt nach einer kurzen, einstellbaren Pause (Einstellungen: "Namen speichern: Verzögerung", Standard 2 Sek.) — spätestens aber beim Verlassen des Feldes.
- Neue Export-Funktion "Für Namenfit exportieren (CSV)" (Datei-Menü und Editor-Toolbar): schreibt eine CSV-Datei im Sitzraster-Format, das die Schwester-App Namenfit direkt importieren kann — jede Tischgruppe als eigener Spaltenblock, Namensformat frei wählbar (dieselben Optionen wie bei der Namensanzeige-Einstellung), Zielpfad über den Datei-speichern-Dialog. Der Export bricht mit einer klaren Fehlermeldung ab (keine Datei wird geschrieben), wenn ein benannter Schüler zu keiner nummerierten Tischgruppe gehört, oder wenn zwei Schüler denselben Anzeigenamen hätten.
- Details-Panel: neues Feld "Spitzname" pro Schüler, editierbar neben Vor- und Nachname. Ist es gesetzt, ersetzt es den Vornamen überall in der Anzeige (Sitzplan-Grid, Sitzplan-Vorschau, PDF-Export, Dokumentationstabelle, Statusmeldungen) — nur das Vorname-Feld selbst zeigt weiterhin den echten, offiziellen Vornamen zum Bearbeiten.
- Neue Einstellung "Nur so viel Nachname wie nötig zur Unterscheidung": Ist sie aktiv, zeigen Sitzplan-Grid, Sitzplan-Vorschau und PDF-Export standardmäßig nur den Vornamen (bzw. Spitznamen) und ergänzen automatisch so viel vom Nachnamen, wie zur Unterscheidung zweier Schüler mit gleichem Vornamen nötig ist (z. B. "Paul Mö." und "Paul Mü." bei zwei Pauls mit unterschiedlichem Nachnamen-Anfang). Die Einstellung "Name in Gridansicht" heißt jetzt "Namensanzeige" und gilt jetzt einheitlich für Grid, Sitzplan-Vorschau *und* PDF-Export (bisher zeigte der PDF-Export immer fest "Vorname Nachname", unabhängig von dieser Einstellung).
- Alle Toolbar-Buttons (Planliste und Sitzplan-Editor) zeigen jetzt statt Unicode-Symbolen (＋, ✎, ⌫, ★, ⤓, ♛ …) passende PNG-Icons aus dem Tabler-Icons-Set (MIT-lizenziert, `assets/toolbar/`), die sich automatisch an das aktive Theme anpassen.
- Leertaste schaltet in Tisch- und Dokuansicht die Anwesenheit des ausgewählten Schülers für das heutige Datum um (unabhängig davon, welcher Termin in der Dokutabelle gerade angezeigt wird).
- Tischdetails im Sitzplan-Editor werden jetzt erst nach Drücken von Enter angezeigt (lesend); ein zweites Enter auf derselben Zelle startet die Namensbearbeitung. Escape schließt aufgedeckte Details zuerst, erst ein weiteres Escape geht zurück zur Kursliste.
- Neu angelegte Notenspalten werden direkt in der Dokutabelle als aktive Spalte markiert.
- Details-Panel: neues Feld "Nachteilsausgleiche" pro Schüler (Freitext-Liste, eine Zeile pro Eintrag, z. B. "Zeitzuschlag 25 %"), editierbar analog zu Name/Farbpunkten und im Sitzplan persistiert.
- Einstellungen werden jetzt typisiert im zentralen App-Zustand gehalten (`AppState.settings`) statt als freies Dict, inklusive eigenem Lese-/Schreib-Intent fuer den Einstellungsdialog.
- Live-Vorschau-Popup beim Hovern ueber Schuelertische zeigt Namen, Symbole und Nachteilsausgleiche kompakt an, ohne in den Bearbeitungsmodus wechseln zu muessen.
- Schueler-Felder unterstuetzen jetzt einen separaten "Nachname" neben dem Vornamen; PDF-Export, Legenden und Dokumentationsansicht verwenden automatisch beide Felder.

### Changed
- Der Symbol-Katalog wird beim Start einmalig zentral geladen (`AppState.symbol_catalog`) statt von der GUI separat aus der Konfigurationsdatei.
- Tastenkuerzel-Dispatch nutzt jetzt eine echte Zuordnungstabelle statt einer if/elif-Kette zur Aufloesung von UI-Aktionen.
- Dokumentationsansicht: Spalten koennen jetzt per Klick auf den Spaltenkopf sortiert werden (auf- und absteigend); die Sortierreihenfolge wird farblich hervorgehoben.

### Fixed
- `tools/ci/check_ai_guardrails.py` prüfte noch auf die alte, seit der `BwBaseWindow`-Migration nicht mehr existierende `CustomMenuBar`-Konstruktion und schlug dadurch bei jeder Änderung an der GUI-Schicht fälschlich fehl; auf den aktuellen `build_menu()`/`section_spec()`-Stand nachgezogen (reine CI-Tooling-Wartung, keine Nutzer-sichtbare Änderung).
- PDF-Export: dokumentationsgebundene Symbole (z. B. "Abwesend", "Nicht abgegeben / verweigert") erscheinen nicht mehr in der Symbol-Checkliste des Export-Dialogs. Sie zeigten dort den zuletzt jemals gesetzten Wert statt eines für den gedruckten Sitzplan sinnvollen Dauerzustands und konnten so unbeabsichtigt auf einem ausgedruckten Sitzplan landen.
- Enter auf einem neu angelegten Tisch springt jetzt direkt in die Namensbearbeitung, statt ein zweites Enter zu verlangen. Doppelklick auf einen neuen, leeren Tisch fokussierte das Namensfeld bisher manchmal in einem noch unsichtbaren Panel — behoben.
- Neu angelegte Kurse landeten in einem falschen, fest verdrahteten Standardordner statt im in den Einstellungen konfigurierten Sitzplan-Ordner; die Kursliste zeigte danach nur noch die (leeren) Kurse aus diesem falschen Ordner.
- Nach dem ersten in einer Sitzung geöffneten Kurs ließ sich kein weiterer Kurs mehr sichtbar öffnen (Doppelklick, Enter und der Öffnen-Button blieben ohne Wirkung, obwohl der Kurs intern korrekt geladen wurde).
- Pfeiltasten-Navigation im Sitzplan-Raster reagierte nach dem Löschen eines Schülertisches oder dem Verschieben des Lehrertischs nicht mehr sofort, weil der Tastaturfokus nicht zurück zum Raster wechselte.
- Kartograph stürzte beim Start zuverlässig ab: `ui_theme.py` importierte `get_theme` noch aus dem inzwischen privatisierten `bw_gui.theming`-Modul (`ImportError`), und `KartographMainWindow` versuchte weiterhin, die seit der `BwBaseWindow`-Migration schreibgeschützte `theme_key`-Property direkt zuzuweisen (`AttributeError`). Beide Stellen wurden auf die neuen bw_gui-Verträge umgestellt: privater Importpfad für `get_theme`, Theme-Wechsel jetzt ausschließlich über `BwBaseWindow.apply_theme()` (aktualisiert die Shell) statt direkter Attributzuweisung.
- Der Toolbar-Button "★ S" (Symbol zum markierten Platz hinzufügen) funktioniert wieder: der Dialog war beim Mixin-Split/v4-Umzug verloren gegangen und ist jetzt als `add_symbol_to_selected_desk_dialog()` in `_mixin_edit.py` wiederhergestellt.
- Die Legenden-Seite im PDF-Export nutzt jetzt pro Kompetenzblock getrennte Tabellen mit eigener Header-Zeile, automatischem Zeilenumbruch und kompakterer Tabellenbreite, statt einer flachen Einzeilenliste ohne sauberes Wrapping.
- PDF export popup no longer opens as an empty window: overlay dialogs now resolve the main-window parent to a valid Tk path when running through `TkRootHost`, so export controls render and respond again.
- `start-kartograph.bat` bevorzugt jetzt die lokale Projektumgebung (`kartograph/.venv`) vor der uebergeordneten `tools4school/.venv`, damit Kartograph konsistent mit den erwarteten Abhaengigkeiten startet.
- Beim Start ohne sichtbares Fenster blockiert Kartograph nicht mehr im Hintergrund: die initiale Splitter-Positionierung der Doku-Ansicht wurde auf eine einmalige Configure-Initialisierung umgestellt und erzeugt keine Idle-Endlosschleife mehr.
- Veraltete Kartograph-Prozesse aus vorherigen Sitzungen werden beim Start automatisch beendet, damit keine Zombie-Prozesse Ports oder Ressourcen blockieren.
- Maus-Trigger in Canvas-Interaktionen wurden korrigiert: bestimmte Klick-Events wurden nicht zuverlaessig ausgeloest, wenn der Mauszeiger schnell zwischen Kacheln bewegt wurde.
- Zwischenablage-Operationen (Kopieren/Ausschneiden/Einfuegen) funktionierten nach bestimmten Interaktionssequenzen nicht zuverlaessig; die Clipboard-Verarbeitung wurde robuster gemacht.

### Changed
- Die Dokumentationsansicht ist jetzt in kleinen Fenstern deutlich besser bedienbar: der Mitteltrenner zwischen Datumstabelle und Notentabelle ist per Drag&Drop verschiebbar, und horizontales Scrollen per Shift+Mausrad reagiert mit groesserer Schrittweite.
- Die Dokumentationsansicht nutzt jetzt getrennte horizontale Scrollbars pro Teilbereich (links Datum/Symbole, rechts Noten/Spalten), statt einer gemeinsamen Leiste am unteren Rand.
- PDF-Export fuer Sitzplaene wurde erweitert: Exportdialog bietet jetzt Notenmodus (keine, nur fertige Gesamtnote, inklusive Klammernoten), Symbolauswahl nur aus im Plan vorhandenen Symbolen (default: alle), optionale Farbpunkte (default: aus) und optional eine zweite Legenden-Seite mit nur tatsaechlich exportierten Symbolen/Farbpunkten.
- AI guardrails now emit non-blocking local warnings when configured core keyboard intents (for example new/rename/duplicate/undo/redo/copy/cut/paste/escape/settings/debug) are present but matching shortcut binding markers are missing in the configured main-window shortcut bindings.
- UI contract bridges are now fully decommissioned to thin shared re-export shims (`bw_libs/ui_contract/keybinding.py`, `bw_libs/ui_contract/popup.py`, `bw_libs/ui_contract/hsm.py`, `bw_libs/ui_contract/laufkern.py`); dead local duplicate implementations were removed.
- AI guardrails now enforce a Phase-I decommission gate for UI contract bridges: each bridge must keep `ensure_bw_gui_on_path` plus shared `bw_gui` imports and may not reintroduce local contract class/function implementations.
- AI guardrails now enforce LaufKern fallback sunset Wave-3: the local `ModuleNotFoundError` fallback branch was removed from `bw_libs/ui_contract/laufkern.py`, and fallback handlers are now forbidden repo-wide in guardrail scan scopes.
- Kartograph bindet jetzt eine zentrale LaufKern-Bridge (`bw_libs.ui_contract.laufkern`) fuer Manifest-, Reachability- und Tracking-Vertraege ein und bereitet damit die Trennung "Programm = Was" und "LaufKern = Wie" technisch vor.
- Die Shortcut-Runtime-Debug-Ansicht zeigt jetzt zusaetzlich eine LaufKern-Zusammenfassung zur aktuellen Intent-Erreichbarkeit (erreichbare Intents pro Runtime-Kontext und Manifest-Validierungsstatus).
- Der LaufKern-Manifestaufbau wurde in einen dedizierten Provider (`app/adapters/gui/laufkern_manifest_provider.py`) ausgelagert, damit Runtime-Integration (Wie) und app-spezifische Deklaration (Was) klar getrennt bleiben.
- Der produktive UI-Intent-Dispatch protokolliert jetzt LaufKern-Tracking-Artefakte; das Runtime-Debug zeigt dazu einen Completion-Status aus der Artefaktaggregation.
- AI guardrails now enforce LaufKern fallback sunset Wave-2: `except ModuleNotFoundError` is only allowed in the central contract bridges (`bw_libs/ui_contract/keybinding.py`, `bw_libs/ui_contract/popup.py`, `bw_libs/ui_contract/hsm.py`, `bw_libs/ui_contract/laufkern.py`); new local fallback branches are rejected.
- AI guardrails now also block local redefinitions of reserved shared primitives (`TkRootHost`, `ScrollablePopupWindow`, `WrappedTextField`) so these runtime/dialog/widget foundations must be consumed from `bw-gui` instead of being rebuilt in-repo.
- Main-window hosting now uses the shared `bw_gui.runtime.TkRootHost` primitive instead of a repo-local root delegation helper.
- AI guardrails now include `bw_libs/` in the repo-wide GUI contract scan scope, so direct `tkinter`/`ttk` imports and new local `ui`/`widgets`/`tui` baseclass patterns are also blocked in shared-library paths.
- AI guardrails no longer keep a legacy class allowlist exemption for `app/adapters/gui/main_window.py`; `KartographMainWindow` now uses a composed shared runtime root instead of local `ui.Tk` inheritance.
- AI guardrails no longer keep a future-entrypoint baseline exemption for `app/adapters/gui/main_window.py`; Kartograph now runs this entrypoint under the strict shared-GUI contract checks.
- AI guardrails now require an explicit GUI migration backlog (`docs/GUI_MIGRATION_BACKLOG.md`) for active GUI baselines/exemptions, including time-bound `remove_by` tracking.
- Governance policy now explicitly requires strict bw-gui-only usage: no local tkinter/ttk widget implementations in repo modules, and reusable GUI building blocks must be implemented in bw-gui first.
- AI guardrails now enforce repo-wide strict bw-gui usage in GUI modules: direct `tkinter`/`ttk` imports and new local `ui`/`widgets`/`tui` baseclass patterns are rejected via AST-based checks (with a legacy allowlist for existing classes).
- AI guardrails now also enforce shared-GUI bootstrap requirements for any newly added GUI entrypoint files and reject direct tkinter imports in those entrypoints.
- AI guardrails were hardened to enforce mandatory shared UI contracts in `app/adapters/gui/main_window.py` and fail fast on legacy fallback branches.
- Shared UI fallback branches were removed from `app/adapters/gui/main_window.py`: shared menu bar, hover tooltip formatting, and shared tabbed settings are now mandatory runtime paths.
- Theme special paths were removed from `app/adapters/gui/ui_theme.py`: Kartograph now requires the shared `bw_gui.theming` registry directly and no longer keeps optional fallback branches for missing shared themes.
- Theme availability in Kartograph now merges with the shared `bw_gui.theming` registry, so new central themes can be used without local duplication.
- Remaining symbol/add and PDF-export dialog actions now also expose shared hover help overlays, completing action guidance consistency across core dialog flows.
- Additional debug/overlay/filter dialog actions now also use shared hover help overlays (runtime debug refresh/offline toggle, tablegroup overlay actions, symbol filter/save actions) for consistent action and shortcut guidance.
- The settings flow now uses the shared tab-based settings dialog (`bw_gui.dialogs.open_tabbed_settings_dialog`) for storage/editor options (plans folder, canvas radius, symbol strength, viewport follow buffer).
- Hover tooltips now appear with smoother delayed behavior, pick up the active app theme automatically, and stay fully visible on-screen.
- Shared settings/sidebar and scrollbar theming received a visual polish via the updated `bw-gui` baseline styles.
- Toolbar and context hover overlays now use the shared shortcut formatter for consistent wording and shortcut rendering.
- Main window runtime imports now use shared `bw_gui.runtime` aliases (`ui`, `widgets`, `fonts`) instead of direct `tkinter` / `ttk` / `tkinter.font` imports in `app/adapters/gui/main_window.py`.
- Shared shell setup now uses `bw_gui.runtime.ui` in `bw_libs/app_shell.py` instead of direct `tkinter` imports.
- In documentation view, non-horizontal key presses now preserve the active column selection; only Left/Right can change the selected column.
- The fixed summary column in the right documentation table is now blocked from becoming the active selected column.
- Kartograph now uses the shared custom menu bar (from `bw-gui`) instead of the native OS menu bar, with unified styling and shared mnemonic behavior.
- Dialog and file chooser calls now use shared `bw_gui.dialogs` services, so popup tracking and modal handling are centralized and reusable across apps.
- Dialog routing no longer uses a local tkinter fallback path in the main window; dialog and file chooser handling is now hard-wired through the shared dialog bridge.
- Dialog handling is now routed through a centralized popup-tracked gateway, so message and input dialogs participate consistently in runtime dialog-mode handling.
- List and editor toolbars now use icon-first action buttons with shortcut badges, plus hover overlays that explain each action and its shortcut.
- Shortcut text was removed from button labels across the UI; shortcut hints are now provided via hover overlays instead.

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
