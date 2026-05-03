# Development Log (kartograph)

Dieses Dokument trackt technische Aenderungen fuer Feature- und Architekturarbeit.

Regel:
- Keine Feature- oder Architekturaenderung ohne Update in diesem Log.
- Bugfix-Only-Changes koennen ohne Eintrag erfolgen.

## [Unreleased]

### Added
- Guardrail-Basis eingefuehrt: `AGENTS.md`, `.github/copilot-instructions.md`, PR-Template und CI-Check.
- `app/core/domain/table_groups.py` als zentrale Domainlogik fuer Zusammenhangskomponenten, TG-Normalisierung, Kaskaden-Umnummerierung und Transformationskollisionen.
- Runtime-Debug-Popup fuer Shortcuts in der Ansicht (`Ansicht -> Shortcut-Runtime-Debug anzeigen`, `Strg+Shift+R`) inkl. Offline-Simulation (`Strg+Shift+O`) und tabellarischer Aktiv/Disabled-Gruende.
- Neue Runtime-Tests fuer Zentralmodule: `tests/test_keybinding_registry_runtime.py` und `tests/test_popup_policy_registry.py`.

### Changed
- Runtime-Debug-Popup ist jetzt als nicht mode-blockierendes Parallel-Popup (`dialog.non_blocking`) registriert; der Resolver nutzt nur mode-blockierende Popup-Sessions fuer Dialog-Prioritaet.
- Wave-B-Integration gestartet: `app/adapters/gui/main_window.py` nutzt jetzt zentrale Runtime-Shortcut-Registrierung mit `evaluate_runtime` und PopupPolicy-basiertem Dialogkontext.
- Intent-Schiene erweitert: `UiIntent` und `MainWindowUiIntentController` enthalten eigene Debug-Intents fuer Runtime-Popup und Offline-Simulation.
- `app/adapters/gui/keybinding_registry.py` um `KeybindingRuntimeContext` und `evaluate_runtime` erweitert.
- Guardrails erweitert: `tools/ci/check_ai_guardrails.py` validiert Runtime-Integration sowie Debug-Intent-Routing.
- Guardrails praezisiert: `CHANGELOG.md` wird nun bei nutzer- oder coentwicklerrelevanten Aenderungen erzwungen; Prozesswarnungen (Commit-/Push-Guidance) werden nur noch lokal und nicht in CI ausgegeben.
- Zentrale UI-Governance gestartet: `app/adapters/gui/keybinding_registry.py` und `app/adapters/gui/popup_policy.py` als gemeinsame API-Basis fuer Shortcut- und Popup-Steuerung eingefuehrt.
- Guardrails erweitert: AGENTS/Copilot/PR-Template verlangen zentrale Shortcut-/Popup-Registrierung sowie Feature-Commit-Disziplin bei manuellem Push.
- `tools/ci/check_ai_guardrails.py` prueft die Existenz der neuen Zentralmodule und meldet Commit-/Push-Prozessdrift als non-blocking Warnung.
- Navigations-Moduswechsel in der Dokumentationsansicht entfernt: `_documentation_mode`, `toggle_documentation_mode`, `_move_doc_selection_on_enter` und alle zugehoerigen State- und UI-Elemente (Toolbar-Button, Strg+M-Shortcut, Intent-Handler) wurden vollstaendig entfernt.
- Enter-Verhalten in der Dokumentationsansicht vereinfacht: Enter oeffnet jetzt den In-Cell-Editor auf der aktiven Notenspalte; wenn kein editierbares Feld aktiv ist, passiert nichts; kein Positions-Sprung mehr.
- Persistente Zellenhervorhebung eingefuehrt: die aktive Doku-Zelle wird immer mit einem hellen Label-Overlay hervorgehoben (auch ausserhalb des Schreibmodus); die Zeile bleibt im normalen Treeview-Selection-Stil markiert.
- Header-Markierung erweitert: der aktive Spaltenkopf wird fuer Datums- und fixe Spalten (rechter Tree) gleichermassen mit einem `>` Praefix markiert; bei Wechsel der aktiven Spalte wird der Praefix korrekt umgesetzt.
- Tischgruppen-Normalisierung erweitert: leere Schuelertische koennen in benannten Tischgruppen mitlaufen; Komponenten ohne mindestens einen benannten Schuelertisch werden weiterhin zwingend auf TG 0 zurueckgesetzt.
- Tischgruppen-Transformationen und TG-Nachschlagefunktionen greifen jetzt fuer alle Schuelertische einer Gruppe (inklusive leerer Tische), damit Shift/Rotation konsistent auf die gesamte Gruppe wirken.
- Der aktive Markierungsrahmen im Grid-Rendering basiert jetzt auf transformierten Tischpolygonen statt auf starren Grid-Bounds, damit die Auswahl bei verschobenen/rotierten Gruppen korrekt auf dem Tisch liegt.
- Eine pytest-basierte Testsuite wurde eingefuehrt (Domain-Tests fuer Tischgruppenregeln und Geometrie-Bounds) und in den Quality-Workflow integriert.
- S:S-Overlay-Darstellung bei Docking links/rechts auf staerkere Umbrueche umgestellt: Symbol- und Farbbuttons werden in mehrere Zeilen gerastert, Legenden erhalten Wraplength statt abgeschnittener Einzeiler.
- Farbpunkte im Grid-Rendering in y-Richtung nach oben verschoben, um Ueberlappung mit Namenslabels zu vermeiden.
- Fokusverhalten nach Erstnutzungs-Bedeutungsdialog fuer Farben korrigiert: der Fokus wird anschliessend wieder explizit auf das Grid gesetzt.
- Domainmodell erweitert: `Desk` speichert jetzt `color_markers`, `SeatingPlan` speichert planweite `color_meanings`; JSON-Persistenz wurde rueckwaertskompatibel fuer beide Felder erweitert.
- Neue Use-Cases fuer Farbmarker eingefuehrt (`toggle_color_marker`, `set_color_meaning`, `is_color_used`, Cleanup ungenutzter Bedeutungen), damit Bedeutungszeilen automatisch mit der letzten Farbnutzung aufgeraeumt werden.
- Detailbereich im Editor um Farbbutton-Zeile unter den Symbolbuttons erweitert; Farbpunkte sind als Toggle pro Farbe umgesetzt und zeigen den aktiven Zustand direkt im Button.
- Globale Tastaturbelegung `1..9` im Editor eingefuehrt (Gelb bis Gruen); bei erster Plan-Nutzung einer Farbe wird ein Bedeutungsdialog erzwungen.
- Grid-Rendering erweitert: Farbpunkte werden als farbige Kreise neben dem Schuelernamen gezeichnet.
- Overlay-Layout flexibilisiert: das S:S-Detailoverlay (Name/Symbole/Farben) ist jetzt in `Ansicht` links/rechts/unten dockbar und persistiert als Setting.
- Auch das Tischgruppen-Overlay nutzt jetzt persistente Positionsoptionen links/rechts/unten und richtet sich bei Fensterbewegung/-resize automatisch neu aus.
- Clipboard-Logik erweitert, damit Farbmarker bei Copy/Cut/Paste erhalten bleiben.
- Planlisten-Toolbar in der Kursansicht umgestellt: statt `Einstellungen` werden jetzt direkte Planaktionen fuer `Umbenennen`, `Loeschen` und `Duplizieren` ueber den UI-Intent-Controller verdrahtet.
- Repository-Port und JSON-Implementierung um Plan-Dateioperationen erweitert (`rename_plan`, `delete_plan`, `duplicate_plan`) inklusive Konfliktbehandlung fuer bestehende Dateinamen.
- Fuer Planaktionen der Kursansicht wurde eine eigene Undo/Redo-Historie auf Dateiebene eingefuehrt und in die bestehenden `Rueckgaengig`/`Wiederholen`-Kommandos integriert.
- `Duplizieren` nutzt jetzt einen verpflichtenden Namensdialog mit Default `<Name> Kopie`; bei Namenskonflikten wird analog zur Neuerstellung ein Ueberschreiben-Dialog angeboten.
- Globales Shortcut-Mapping erweitert: `F2` triggert Umbenennen in der Listenansicht, `Strg+D` triggert Duplizieren in der Listenansicht, und `Entf` ist jetzt kontextsensitiv (Liste: Plan loeschen, Editor: Platz loeschen).
- TG-Normalisierung angepasst: neu entstandene oder durch Split neu zugewiesene Tischgruppen erhalten immer die naechste hoechste freie Nummer (`max + 1`) statt einer positionsabhaengigen Neuvergabe.
- Tischgruppen als Zusammenhangskomponenten eingefuehrt (4er-Nachbarschaft); Lehrertische bleiben strikt ausserhalb von Tischgruppen.
- Desk-Datenmodell und JSON-Persistenz um TG-Metadaten erweitert: TG-Nummer, x/y-Shift und Rotation.
- Neuer Shortcut `Strg+T` oeffnet ein rechtes Tischeinstellungen-Overlay mit TG-Nummer, Shift- und Rotationswerten.
- TG-Nummerierung unterstuetzt manuelle Vergabe mit Kaskadeneffekt bei Nummernkonflikten.
- Vorschau-Rendering auf transformierte Tischdarstellung pro Tischgruppe umgestellt; TG-Nummern werden unter Gruppen angezeigt.
- Bei markierten Teilmengen einer Tischgruppe wird zusaetzlich ein schwaecherer Gruppenrahmen dargestellt.
- PDF-Export auf dieselbe TG-Transformationslogik wie die Vorschau umgestellt (Shift/Rotation deckungsgleich).
- Kollisionserkennung fuer TG-Transformationen eingefuehrt: bei Ueberlappung mit Lehrer- oder Schuelertisch wird der zuletzt veraenderte Transformationswert direkt auf 0 gesetzt.
- Doku-Governance eingefuehrt mit klarer Trennung aus Architektur-Ist-Zustand, Development-Log und Changelog.
- Enter-Verhalten im Editor praezisiert: Enter fuehrt jetzt robust in den Namens-Editmodus (inkl. Cursor am Ende ohne Vollmarkierung), waehrend die Listenansicht unveraendert bleibt.
- Symbolverwaltung von binaeren Toggles auf 4er-Zyklus erweitert (0->1->2->3->0) mit persistierten Klickzaehlern pro Symbol.
- Symbolanzeige unter Schuelernamen auf reine Unicode-Glyphen umgestellt; die Anzeige wiederholt das jeweilige Symbol passend zur Klickanzahl.
- Plan-Laden abwaertskompatibel erweitert: Legacy-Listenformat fuer Symbole wird beim Einlesen in das neue Zaehlerformat migriert.
- Detailbereich neu ausgerichtet: Status und Markierungsanzeige teilen sich jetzt eine gemeinsame Kopfzeile mit rechtsbuendigem Marker-Text.
- Symbolkatalog und Legendenlogik auf user-editierbare Konfigurationsdatei `config/symbols.json` umgestellt, inklusive Validierung und Fallback-Erzeugung.
- Symbolkonfiguration um optionale Shortcut-Buchstaben erweitert; bei markiertem Schuelertisch triggern Tastatur-Shortcuts direkt den zugeordneten Symbol-Button.
- Symboldarstellung erweitert: unter Schuelernamen werden pro aktivem Symbol eigene Erklaerungszeilen mit count-basierter Legendenbedeutung gerendert.
- Dateinamensstrategie fuer neue Plaene vereinfacht: keine Zufallsanhaenge mehr; Konflikte werden im GUI-Dialog explizit abgefragt (ueberschreiben oder erneut benennen).
- PDF-Export (A4 quer) als Infrastructure-Modul eingefuehrt, mit Modusauswahl fuer Lehrertisch unten oder oben (180° Perspektive).
- Grid-Editor auf feste 101x101-Kachelgrenzen (-50..50) umgestellt; alle Navigations- und Editieraktionen clampen jetzt strikt in diesen Bereich.
- Neuer Viewport-Reset per `Strg+0`: Standard-Zoom, Auswahl auf Lehrertisch und automatische Zentrierung.
- Theme-System auf Kursplaner-Farbwelten erweitert (mehrere helle/dunkle Varianten) und in Kartograph-Keyschema gemappt.
- Undo/Redo-Historie eingefuehrt (bis 20 Schritte) mit Aktionsbündelung fuer identische, direkt aufeinanderfolgende Eingaben sowie 5er-Rollback-Aktion.
- Rechteckauswahl implementiert (Maus-Drag + Shift-Pfeiltasten) inklusive Bereichsanzeige im Detailkopf.
- Rechteck-Clipboard fuer Ausschneiden/Kopieren/Einfuegen ergaenzt; Inhalte bleiben ueber Planwechsel erhalten, Einfuegen startet an der markierten Zelle als linke obere Ecke.
- Lehrertisch-Schutz bei Clipboard-Operationen und Teacher-Move ausgebaut: Teacher wird nie kopiert/geschnitten/ueberschrieben; bei potenziellem Datenverlust durch Bounds-Wirkung erfolgt vorherige Warnung.
- Canvas-Groesse als persistente Einstellung eingefuehrt (`canvas_radius`, 1..50) und die Grid-Grenzlogik auf dynamische Radius-Werte umgestellt.
- Warnlogik erweitert: beim Verkleinern des Canvas-Radius erscheint vor dem Speichern ein Hinweis, falls im aktuell geoeffneten Plan dadurch Schuelertische ausserhalb des sichtbaren Bereichs liegen wuerden.
- Beim Oeffnen eines Plans erscheint jetzt eine Warnung, wenn enthaltene Schuelertische ausserhalb des aktuell eingestellten Canvas-Radius liegen und daher nicht dargestellt werden koennen.

### Added
- `app/infrastructure/symbol_config_loader.py` fuer Schema-Pruefung und Laden der Symbolkonfiguration.
- `app/infrastructure/exporters/pdf_exporter.py` fuer PDF-Ausgabe ohne Rasterlinien und mit klaren Tischrahmen.
- `docs/TODO.md` mit offenem Hinweis zur spaeteren Warnung bzgl. Standardperspektive (Lehrertisch unten).
- `app/core/domain/plan_history.py` fuer Undo/Redo-Historienverwaltung mit Gruppierung.
- `app/core/domain/plan_selection.py` fuer rechteckige Auswahl mit Anchor/Focus-Modell.
- `app/core/domain/desk_clipboard.py` fuer planuebergreifendes Rechteck-Clipboard.
