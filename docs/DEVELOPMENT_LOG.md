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
