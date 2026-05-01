# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Added
- Tischgruppen als Zusammenhangskomponenten fuer Schuelertische mit sichtbarer TG-Nummer unter jeder Gruppe.
- Neues Tischeinstellungen-Overlay rechts per `Strg+T` mit TG-Nummer, x-shift, y-shift und Rotation.
- Farbpunkte fuer Schuelertische: pro Tisch koennen per Tastatur `1..9` oder per Farbbuttons Marker in neun Farben gesetzt/entfernt werden (Gelb, Orange, Rot, Magenta, Lila, Marine, Cyan, Tuerkis, Gruen).
- Bei der ersten Nutzung einer Farbe in einem Plan fragt Kartograph die Bedeutung ab und zeigt sie als eigene Legendenzeile; wird der letzte Marker dieser Farbe entfernt, verschwindet die Bedeutungszeile automatisch.
- Grundlagen fuer die neue Dokumentationssicht sind vorhanden: Plandateien nutzen jetzt JSON v3 mit tagesbezogener Dokumentationsstruktur, Notenspalten-Definitionen und lerngruppenspezifischer Gewichtung schriftlich/sonstig.
- Neue Dokumentations-Use-Cases sind eingefuehrt (Datum anlegen/umbenennen, Symbol-/Notenwerte setzen, Symbolzusammenfassung, Gesamtnotenanzeige).
- Neue Dokumentationsansicht im Editor: Umschalten zwischen Raster und Doku per `Strg+Shift+D`, Tabellenansicht mit Schuelerzeilen, Datums-Spalten, Zusammenfassung, Notenspalten und Gesamtnote.
- In der Dokumentationsansicht koennen Datums-Spalten umbenannt und Notenspalten (schriftlich/sonstig + Titel) per Dialog hinzugefuegt werden.
- Neue Spezialsymbole verfuegbar: `X` fuer nicht abgegebene/verweigerte Leistungen und `∅` fuer abwesende SuS.
- Bei jedem Speichern wird zusaetzlich ein lokales, verstecktes JSON-Backup im AppData-Pfad erzeugt; pro Lerngruppe bleiben die letzten 20 Sicherungen erhalten.
- Bei geoeffnetem Plan erstellt Kartograph zusaetzlich alle 5 Minuten automatisch ein Snapshot-Backup im selben AppData-Backupbereich.

### Changed
- Leere Dokumentationstage werden beim Speichern nicht persistiert; ein Tagesdatum bleibt bis zur ersten Inhalteingabe volatil.
- Beim Verschieben/Kopieren von Schuelertischen bleiben tagesbezogene Dokumentationseintraege jetzt erhalten.
- Enter in der Dokumentationsansicht bewegt die aktive Auswahl je nach Modus spaltenweise nach unten oder zeilenweise nach rechts.
- Symbol-Shortcuts funktionieren jetzt auch in der Dokumentationsansicht und schreiben direkt in die markierte Tageszelle.
- Symbolaenderungen im Sitzraster werden jetzt automatisch als heutiger Dokumentationseintrag uebernommen.
- In der Sitzrasteransicht wird die berechnete Gesamtnote je Schuelertisch oben links eingeblendet.
- In den Einstellungen gibt es jetzt einen Sichtfenster-Puffer fuer Pfeilnavigation (0 = bisheriges Verhalten, 1 = Bewegung erst ausserhalb des mittleren 3x3 Bereichs).
- Die Symbolanzeige im Sitzraster nutzt jetzt (falls vorhanden) die gleiche neueste Dokumentationszusammenfassung wie die Doku-Tabelle.
- Ueber "Symbole filtern" laesst sich nun festlegen, welche Symbole im Sitzraster angezeigt werden (Standard: alle sichtbar).
- In der Dokumentationsansicht koennen Noten jetzt direkt fuer markierte Schueler-/Datumseintraege gesetzt oder geloescht werden (Button oder `Strg+G`).
- Zusammenfassung, Notenspalten und Gesamtnote bleiben in der Dokumentationsansicht jetzt rechts fix sichtbar, waehrend Datums-Spalten horizontal scrollen.
- Symbole in der Dokumentationsansicht lassen sich jetzt auch per Button/Dialog setzen (zusaetzlich zu Shortcuts).
- Die Gewichtung schriftlich/sonstig fuer die Gesamtnote ist in der Dokumentationsansicht jetzt pro Lerngruppe konfigurierbar.
- Beim Oeffnen eines Plans steht das aktuelle Datum automatisch als Doku-Spalte bereit; ohne Eintrag bleibt sie weiterhin unsaved.
- Der zuletzt genutzte Spalten-/Zeilenmodus der Dokumentationsansicht wird jetzt gespeichert.
- In der Dokumentationsansicht kann die aktive Datumsspalte per `Alt+Links/Rechts` gewechselt werden.
- Die Dokumentationsansicht zeigt jetzt dauerhaft die aktive Zelle (Schueler + Datum) in der Toolbar an.
- In der Dokumentationsansicht springt der neue "Heute"-Button direkt zur aktuellen Datumsspalte.
- Der "Heute"-Sprung in der Dokumentationsansicht ist jetzt auch per `Strg+H` verfuegbar.
- Das Setzen von Symbolen in der Dokumentationsansicht nutzt jetzt einen Auswahl-Dialog mit klickbarer Liste statt Texteingabe.
- Der Symboldialog in der Dokumentationsansicht ist jetzt direkt per `Strg+Shift+S` erreichbar.
- Symbole koennen im Dokumentations-Symboldialog jetzt per Doppelklick oder `Enter` sofort uebernommen werden.
- Der Dokumentations-Symboldialog merkt sich jetzt die letzte Auswahl und startet beim naechsten Oeffnen auf derselben Symbolzeile.
- Im Dokumentations-Symboldialog uebernimmt jetzt auch `Numpad-Enter` die aktuelle Symbolauswahl.
- Bei leerem Symbolkatalog zeigt der Dokumentations-Symboldialog jetzt eine direkte Hinweismeldung statt eines leeren Dialogfensters.
- Beim Oeffnen des Dokumentations-Symboldialogs wird jetzt bevorzugt das bereits aktive Symbol der aktuell markierten Doku-Zelle vorselektiert.
- Der Dokumentations-Symboldialog zeigt jetzt einen sichtbaren Tastaturhinweis fuer `Enter` (uebernehmen) und `Esc` (schliessen).
- Im Dokumentations-Symboldialog gibt es jetzt eine explizite Aktion `Loeschen`, die das ausgewaehlte Symbol fuer die aktive Doku-Zelle direkt auf 0 setzt.
- Im Dokumentations-Symboldialog waehlen `1-9` (inkl. Numpad) jetzt direkt die entsprechenden Symbolzeilen.
- Im Dokumentations-Symboldialog loeschen jetzt auch `Entf` und `Backspace` direkt das aktuell ausgewaehlte Symbol.
- Im Dokumentations-Symboldialog loest jetzt auch `0` (inkl. Numpad) direkt die Loeschen-Aktion fuer das ausgewaehlte Symbol aus.
- In der Dokumentationssicht loeschen `Strg+Entf` und `Strg+Backspace` jetzt direkt das erste aktive Symbol der aktuell markierten Doku-Zelle.
- In der Dokumentationsansicht gibt es jetzt eine direkte Toolbar-Aktion "Symbol loeschen (Strg+Entf)" fuer den schnellen Loeschpfad ohne Dialog.
- Der schnelle Symbol-Loeschpfad in der Dokumentationsansicht zeigt jetzt klare Statushinweise, wenn kein Symbol geloescht werden konnte.
- Beim S:S-Overlay in Position `links`/`rechts` wurden Button- und Legendenzeilen auf deutlich staerkere Umbrueche umgestellt, damit Inhalte nicht seitlich abgeschnitten werden.
- Farbkreise im Tisch wurden in y-Richtung weiter nach oben verschoben, damit sie nicht mehr mit Namenslabels kollidieren.
- Nach dem Bedeutungs-Popup fuer eine neu verwendete Farbe springt der Fokus wieder auf das markierte Feld im Grid zurueck.
- In der Kursansicht wurde der Toolbar-Button `Einstellungen` durch direkte Planaktionen ersetzt: `Umbenennen`, `Loeschen` und `Duplizieren`.
- `Duplizieren` fragt den Zielnamen jetzt immer per Dialog ab (mit vorbelegtem Vorschlag `<Name> Kopie`) und nutzt bei Namenskonflikten denselben Ueberschreiben-Dialog wie beim Erstellen neuer Plaene.
- Planaktionen in der Kursansicht (`Umbenennen`, `Loeschen`, `Duplizieren`) sind jetzt in `Rueckgaengig`/`Wiederholen` eingebunden.
- Fuer die neuen Kursansicht-Aktionen gibt es Tastatur-Shortcuts: `F2` (Umbenennen), `Entf` in der Liste (Loeschen), `Strg+D` (Duplizieren).
- Neue Tischgruppen entstehen jetzt immer mit der naechsten hoechsten TG-Nummer (Nummerierung nach Entstehung statt links-nach-rechts-Zuweisung).
- Das Tisch-Overlay mit Name/Symbolen/Farbbuttons ist in `Ansicht` jetzt links, rechts oder unten andockbar; die Position wird in den Einstellungen gespeichert.
- Das Tischgruppen-Overlay ist in `Ansicht` ebenfalls auf links, rechts oder unten umstellbar (persistente Position).
- Leere Schuelertische (ohne Namen) koennen Mitglied einer bestehenden Tischgruppe sein, bilden aber niemals eigenstaendig eine Tischgruppe.
- Tischgruppen lassen sich manuell umnummerieren; bei Nummernkonflikten werden bestehende Gruppen automatisch hochgezaehlt (Kaskadeneffekt).
- x/y-Shift wirkt jetzt sowohl in der Vorschau als auch im PDF-Export konsistent auf die Tischdarstellung.
- Rotationen von Tischgruppen werden sofort in Vorschau und Export dargestellt (begrenzt auf -45 bis +45 Grad).
- Bei markierten Teilen einer Tischgruppe wird ein zusaetzlicher, schwaecherer Gruppenrahmen angezeigt.
- Der Markierungsrahmen folgt bei verschobenen/rotierten Tischgruppen jetzt der transformierten Tischgeometrie statt den urspruenglichen Grid-Koordinaten.
- Ueberlappungen mit Lehrer- oder Schuelertischen fuehren zum automatischen Zuruecksetzen des zuletzt geaenderten Transformationswerts auf 0.

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
