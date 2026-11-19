# Symbole: Formulierungsregeln und Checkliste

Leitfaden für neue oder geänderte **eingebaute Symbole** in
`app/infrastructure/default_symbols.json` (einzige Quelle; die lokale
Arbeitskopie `config/symbols.json` wird daraus erzeugt und ergänzt).

Die Regeln sind aus den bestehenden Diagnosesymbolen abgeleitet
(Stand 2026-11-09). Neue Symbole sollen sich so lesen, als stammten sie aus
derselben Feder.

## Symbolarten

| Art | `role` | Legende | Zweck |
|---|---|---|---|
| Diagnosesymbol | (weggelassen) = `diagnostic` | drei ausformulierte Kompetenzstufen | Diagnoseprofil einer Person |
| Doku-Symbol | `documentation_only` | drei kurze Häufigkeitsstufen | tagesbezogene Dokumentation (z. B. Abwesend, Abgabe) |
| Eigenes Symbol | — (pro Plan, nicht in der Datei) | nur ein Bedeutungstext | planbezogene Doku-Symbole aus der Symbol-Verwaltung |

Die Stärke 1–3 ist die Anzahl, wie oft ein Symbol gesetzt ist
(`SymbolDefinition.legend_for_count`). **`three` ist immer die höchste
Ausprägung**, `one` die niedrigste.

## Diagnosesymbole: Formulierungsregeln

### 1. Satzform

- Ohne Subjekt, mit dem Verb vorn, kleiner Anfangsbuchstabe:
  „hört aktiv zu …“, „kann …“, „arbeitet …“, nicht „Der Schüler hört …“.
- Ein Satz pro Stufe; Teilaussagen mit Komma oder Semikolon verbinden.
- Kein Schlusspunkt.
- Geschlechtsneutral: Personalpronomen vermeiden (Satzbau ohne „sie/er“).

### 2. Ressourcenorientiert auf jeder Stufe

Jede Stufe beschreibt, **was gelingt**, und auf den unteren Stufen
**unter welcher Bedingung** es gelingt. Defizitformulierungen kommen nicht
vor.

| statt | besser |
|---|---|
| braucht Unterstützung, um Einzelarbeitsphasen einzuhalten | hält Einzelarbeitsphasen ein, wenn enge Begleitung zur Verfügung steht |
| kann Materialien nicht selbst organisieren | kann Arbeitsmaterialien organisieren, wenn genaue Vorgaben zur Verfügung stehen |
| beteiligt sich kaum | beteiligt sich vor allem nach direkter Ansprache oder Ermutigung |

Auf Stufe 1 werden die Hilfen konkret benannt, in Klammern mit „z. B.“:
„(z. B. Materialliste, Checkliste, feste Ablage)“. Das macht die Legende
zugleich zum Förderhinweis.

### 3. Steigerung über feste Signalwörter

| Stufe | typische Signalwörter |
|---|---|
| `three` | selbstständig, eigeninitiativ, sicher, kontinuierlich, verlässlich, flexibel, unaufgefordert |
| `two` | überwiegend, meist, in der Regel, weitgehend, auf Anregung, nach Erinnerung, bei Bedarf gezielt |
| `one` | phasenweise, vor allem nach Ansprache, mit Anleitung/Begleitung, wenn … zur Verfügung steht |

### 4. Parallele Teilaspekte

Alle drei Stufen behandeln **dieselben Teilaspekte** in derselben
Reihenfolge, nur unterschiedlich ausgeprägt. Beispiel „Konzentration“:

| Teilaspekt | `three` | `two` | `one` |
|---|---|---|---|
| konzentriert arbeiten | selbstständig konzentriert | überwiegend konzentriert | phasenweise konzentriert |
| zur Aufgabe zurückfinden | eigeninitiativ | nach Ermutigung oder Erinnerung | mit enger Begleitung |
| Rücksicht auf andere | trägt zu ruhiger Arbeitsatmosphäre bei | respektiert die Arbeitsatmosphäre | hält Einzelarbeitsphasen ein, hört zu |

### 5. Abgrenzung

Vor dem Anlegen mit den vorhandenen Symbolen vergleichen: Ein Teilaspekt
sollte möglichst nur in einem Symbol stehen. Bekannte Überschneidung:
„zuhören“ kommt in „Interaktion“ (Gesprächsverhalten) und
„Konzentration“ (bei der Sache bleiben) vor.

### 6. Bedeutung (Name)

Ein deutsches Substantiv oder eine kurze Substantivgruppe
(„Beteiligung“, „Umgang mit Material“).

## Kompetenzen (atomar)

Seit 2026-11-18 stehen die Stufentexte der Diagnosesymbole nicht mehr im
Symbol, sondern in atomaren Kompetenzen:
`app/infrastructure/default_competences.json` (einzige Quelle, Felder `id`,
`name`, `group`, `levels` mit `one`/`two`/`three`). Ein Diagnosesymbol
verknüpft eine oder mehrere Kompetenzen; die Legende zeigt deren Text zur
gesetzten Stufe.

- **Eine Kompetenz = ein Teilaspekt** aus Regel 4. Die Regeln 1–3 gelten je
  Kompetenz und Stufe; „parallele Teilaspekte“ ergeben sich jetzt daraus, dass
  ein Symbol mehrere Kompetenzen verknüpft.
- **Abgrenzung (Regel 5):** Ein Teilaspekt steht genau in einer Kompetenz.
  Statt Text zu doppeln, verknüpfen mehrere Symbole dieselbe Kompetenz – oder
  keines (z. B. „aktiv zuhören“, bewusst weder bei Interaktion noch bei
  Konzentration voreingestellt).
- **`id` nie ändern** (ASCII, `gruppe.teilaspekt`); sie ist die Identität im
  Katalog-Abgleich. Name, Gruppe und Texte dürfen überarbeitet werden.
- `group` ordnet die Auswahl im Dialog (meist das frühere Bündel bzw.
  „Lernvoraussetzungen“).
- `tests/test_default_catalog_integrity.py` prüft IDs, drei Stufen und die
  Satzform (klein, ohne Schlusspunkt).

## Doku-Symbole: Formulierungsregeln

Kurz und zählend, gestuft nach Häufigkeit:
`one` = „einmal(ig) …“, `two` = „mehrfach …“, `three` = „wiederholt …“ bzw.
„regelmäßig …“. Auch hier ohne Subjekt und ohne Schlusspunkt.

## Technische Checkliste für ein neues eingebautes Symbol

1. Eintrag in `app/infrastructure/default_symbols.json`: `codepoint`, `key`
   (stabiler Speicherschlüssel), `shortcut`; Diagnosesymbole mit `competences`
   (IDs aus `default_competences.json`, fehlende Kompetenzen dort zuerst
   anlegen), Doku-Symbole mit `role: documentation_only` und `legend`
   (`one`/`two`/`three`). Ein abweichender Anzeigename steht in `name`.
2. **Glyph in Segoe UI Symbol (`seguisym.ttf`) prüfen.** Der PDF-Export
   registriert nur eine Symbolschrift (`pdf_exporter._FONT_CANDIDATES`);
   ein Zeichen, das nur in der Emoji-Schrift steckt, erscheint im PDF als
   Kästchen.
3. **Kürzel:** ein freier Buchstabe, nicht in `RESERVED_SYMBOL_LETTERS`
   (`custom_symbol_validation.py`) und nicht von einem anderen eingebauten
   Symbol belegt. `tests/test_shortcut_bindings_headless.py` prüft die
   Konfliktfreiheit.
4. Nichts an `config/symbols.json`/`config/competences.json` ändern: der
   Loader (`catalog_working_copy.py`) ergänzt neue Symbole und Kompetenzen beim
   nächsten Start, ohne eigene Anpassungen anzutasten.
5. CHANGELOG (nutzerseitig) und `docs/DEVELOPMENT_LOG.md` ergänzen.

## In der Oberfläche ändern

- **Alle Pläne:** *Ansicht → Symbole und Kompetenzen (alle Pläne)…* ändert die
  Arbeitskopien `config/symbols.json`/`config/competences.json` (Name, Taste,
  aktiv, Standard-Kompetenzen; neue Symbole und Kompetenzen). Die
  Standarddateien bleiben unverändert; der Schlüssel eines Symbols nie.
- **Ein Plan:** *Symbol-Verwaltung → Für diesen Plan anpassen…* speichert
  lokalen Namen und Kompetenzen im Plan (`symbol_overrides`).

## Vorhandene Symbole ändern

- **Codepoint nie ändern.** Er ist die Identität eines eingebauten Symbols
  im Katalog-Abgleich (`known_builtin_codepoints`); ein neuer Codepoint
  gilt als neues Symbol.
- **`key` nie ändern.** Pläne und Einstellungen speichern Symbole unter ihrem
  `key`; ohne Eintrag in `LEGACY_SYMBOL_RENAMES`
  (`app/core/domain/symbol_renames.py`) verwaisen erfasste Beobachtungen. Zum
  Umbenennen in der Anzeige genügt `name`.
- Kompetenztexte und Verknüpfungen dürfen frei überarbeitet werden. Bestehende
  lokale Arbeitskopien übernehmen solche Änderungen allerdings nicht
  automatisch, weil vorhandene Einträge nie überschrieben werden.
- Arbeitskopien im alten Format (`meaning` und eigene Legende je
  Diagnosesymbol) werden nicht mehr umgestellt; der Loader fällt dann auf die
  Standards zurück. Die Umstellung lief einmalig (2026-11-18/19).
