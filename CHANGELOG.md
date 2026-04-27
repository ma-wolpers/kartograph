# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Added
- Tischgruppen als Zusammenhangskomponenten fuer Schuelertische mit sichtbarer TG-Nummer unter jeder Gruppe.
- Neues Tischeinstellungen-Overlay rechts per `Strg+T` mit TG-Nummer, x-shift, y-shift und Rotation.
- Farbpunkte fuer Schuelertische: pro Tisch koennen per Tastatur `1..9` oder per Farbbuttons Marker in neun Farben gesetzt/entfernt werden (Gelb, Orange, Rot, Magenta, Lila, Marine, Cyan, Tuerkis, Gruen).
- Bei der ersten Nutzung einer Farbe in einem Plan fragt Kartograph die Bedeutung ab und zeigt sie als eigene Legendenzeile; wird der letzte Marker dieser Farbe entfernt, verschwindet die Bedeutungszeile automatisch.

### Changed
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
