# Development Log (kartograph)

Dieses Dokument trackt technische Aenderungen fuer Feature- und Architekturarbeit.

Regel:
- Keine Feature- oder Architekturaenderung ohne Update in diesem Log.
- Bugfix-Only-Changes koennen ohne Eintrag erfolgen.

## [Unreleased]

### Added
- Guardrail-Basis eingefuehrt: `AGENTS.md`, `.github/copilot-instructions.md`, PR-Template und CI-Check.
- `app/core/domain/table_groups.py` als zentrale Domainlogik fuer Zusammenhangskomponenten, TG-Normalisierung, Kaskaden-Umnummerierung und Transformationskollisionen.

### Changed
- Der Dokumentations-Symboldialog zeigt jetzt einen sichtbaren Tastaturhinweis fuer `Enter` (uebernehmen) und `Esc` (schliessen).
- Der Dokumentations-Symboldialog waehlt beim Oeffnen bevorzugt das bereits aktive Symbol der aktuell markierten Doku-Zelle vor.
- Der Dokumentations-Symboldialog prueft jetzt auf leeren Symbolkatalog und zeigt dann direkt eine klare Info statt eines leeren Auswahlfensters.
- Im Dokumentations-Symboldialog uebernimmt jetzt auch `Numpad-Enter` die aktuelle Auswahl.
- Der Symboldialog der Dokumentationssicht merkt sich die zuletzt gewaehlte Symbolzeile und oeffnet bei erneutem Aufruf mit dieser Vorauswahl.
- Symbole im Dokumentations-Symboldialog lassen sich jetzt direkt per Doppelklick oder Enter uebernehmen.
- Symboldialog in der Dokumentationssicht ist jetzt zusaetzlich per Shortcut `Strg+Shift+S` aufrufbar.
- Symbolsetzen in der Dokumentationssicht von Freitext auf Auswahl-Dialog mit klickbarer Liste umgestellt (inklusive Symbolglyphen und Shortcut-Hinweisen).
- "Heute"-Sprung in der Dokumentationssicht zusaetzlich per Shortcut `Strg+H` erreichbar.
- Dokumentations-Toolbar um "Heute"-Aktion erweitert: die aktive Datumsspalte springt direkt auf das aktuelle Datum.
- Periodische Backup-Ticks in der GUI eingefuehrt: bei geoeffnetem Plan wird alle 5 Minuten ein Snapshot-Backup in AppData geschrieben.
- Dokumentations-Toolbar zeigt jetzt dauerhaft die aktive Doku-Zelle (Schuelerzeile + Datumsspalte) als Statusanzeige.
- Datums-Spaltenauswahl in der Dokumentationssicht per Tastatur erweitert (`Alt+Links/Rechts`), inklusive synchroner Spaltenmarkierung.
- Der Doku-Navigationsmodus (Spalten-/Zeilenmodus) wird jetzt in den Einstellungen persistiert und beim naechsten Start wiederhergestellt.
- Beim Laden eines Plans wird das heutige Datum automatisch als Doku-Arbeitsspalte im Arbeitsspeicher initialisiert (weiterhin volatil bis zur ersten Inhalteingabe).
- Lerngruppenspezifische Gewichtung fuer schriftlich/sonstig ist jetzt in der Dokumentationssicht per Dialog konfigurierbar und wirkt direkt auf die Gesamtnotenberechnung.
- Dokumentationssicht um Button-basierte Symbolerfassung erweitert: Symbole koennen jetzt neben Shortcuts auch per Toolbar-Dialog in die markierte Tageszelle geschrieben werden.
- Dokumentationstabelle in zwei synchronisierte Bereiche aufgeteilt: Datums-Spalten bleiben horizontal scrollbar, waehrend Zusammenfassung/Notenspalten/Gesamtnote rechts fix sichtbar bleiben.
- Dokumentationssicht um Noteneingabe erweitert: per Button/Shortcut (`Strg+G`) lassen sich Noten fuer die markierte Schueler-/Datumskombination in einer gewaehlten Notenspalte setzen oder loeschen.
- Save-Pipeline um versteckte lokale AppData-Backups erweitert: bei jedem Speichern wird ein Zeitstempel-Backup geschrieben und auf die letzten 20 Dateien pro Lerngruppe rotiert.
- Sitzraster um Symbolfilter-Dialog erweitert: sichtbare Symbole koennen gezielt ein-/ausgeblendet werden; ohne Auswahl faellt der Filter automatisch auf "alle sichtbar" zurueck.
- Sitzraster-Symbolanzeige auf Dokumentationszusammenfassung umgestellt: wenn Dokuwerte vorhanden sind, rendert die Kachel dieselben neuesten Symbolstaende wie die Zusammenfassungsspalte der Dokuansicht.
- Pfeilnavigation um konfigurierbaren Sichtfenster-Puffer erweitert (`viewport_follow_buffer`): bei Wert 0 bleibt das bisherige Zentrierverhalten, bei Wert 1 folgt die Karte erst nach Verlassen des mittleren 3x3 Bereichs.
- Grid-Rendering erweitert: die berechnete Gesamtnote wird je Schuelertisch oben links in der Kachel angezeigt.
- Raster-Symbolaenderungen werden jetzt direkt als heutiger Dokumentationseintrag gespiegelt, damit Raster-Buttons/Shortcuts die Dokuhistorie synchron fortschreiben.
- Symbol-Shortcuts in der Dokumentationssicht verdrahtet: Tastaturtasten aktualisieren jetzt die aktuell markierte Tageszelle (4er-Zyklus 0->1->2->3->0) analog zum Sitzraster.
- Symbolkonfiguration erweitert um Spezialsymbole fuer `X` (nicht abgegeben/verweigert) und `∅` (abwesend), inklusive Fallback-Payload im Config-Loader.
- GUI um eine umschaltbare Dokumentationssicht erweitert (Raster <-> Doku), inklusive neuer UI-Intents, Shortcut `Strg+Shift+D` und Menueeintrag in `Ansicht`.
- Dokumentationssicht zeigt Schuelerzeilen mit Datums-Spalten, Symboltagesinhalten, Zusammenfassungs- und Notenspalten sowie berechneter Gesamtnote; Enter-Navigation unterstuetzt Spalten-/Zeilenmodus.
- Dialogaktionen fuer Dokumentationssicht ergaenzt: Datum umbenennen und Notenspalte hinzufuegen (Typ schriftlich/sonstig, Titel).
- JSON-Repository auf Format v3 erweitert: neue Sektion `documentation` (Tage, Notenspalten, Gewichtung), tagesbezogene Desk-Eintraege (`documentation_entries`) sowie abwaertskompatibles Laden bestehender v2-Plaene.
- Persistenzregel fuer Tageskontexte umgesetzt: Dokumentationstage ohne Inhalt werden nicht in JSON geschrieben (volatile Tagesspalten bleiben bis zur ersten echten Eingabe unsaved).
- Domainmodell erweitert um `DocumentationEntry` und `GradeColumnDefinition`; `Desk` traegt jetzt tagesbezogene Dokumentationsdaten, `SeatingPlan` planweite Notenspalten-/Gewichtungsmetadaten.
- Use-Case-Layer um Dokumentations-/Notenfunktionen erweitert (Datum anlegen/umbenennen, Symbol-/Notenwerte setzen, Symbolzusammenfassung je Schueler, Gesamtnotenanzeige nach Rundungs- und Gewichtungsregeln).
- Clipboard- und Teacher-Move-Pfade uebernehmen jetzt auch Dokumentationseintraege, damit keine tagesbezogenen Informationen bei Strukturaktionen verloren gehen.
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
- Repository-API `backup_plan_snapshot` plus Test (`tests/test_backup_snapshot_api.py`) fuer Backup-Erzeugung ohne Primardatei-Write.
- Test fuer Backup-Rotation (`tests/test_backup_rotation.py`).
- Neue Tests fuer Dokumentations-Use-Cases und JSON-v3-Serialisierung/Migration (`tests/test_documentation_usecases.py`, `tests/test_json_repository_documentation.py`).
- `app/infrastructure/symbol_config_loader.py` fuer Schema-Pruefung und Laden der Symbolkonfiguration.
- `app/infrastructure/exporters/pdf_exporter.py` fuer PDF-Ausgabe ohne Rasterlinien und mit klaren Tischrahmen.
- `docs/TODO.md` mit offenem Hinweis zur spaeteren Warnung bzgl. Standardperspektive (Lehrertisch unten).
- `app/core/domain/plan_history.py` fuer Undo/Redo-Historienverwaltung mit Gruppierung.
- `app/core/domain/plan_selection.py` fuer rechteckige Auswahl mit Anchor/Focus-Modell.
- `app/core/domain/desk_clipboard.py` fuer planuebergreifendes Rechteck-Clipboard.
