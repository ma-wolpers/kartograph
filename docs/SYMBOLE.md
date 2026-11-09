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

## Doku-Symbole: Formulierungsregeln

Kurz und zählend, gestuft nach Häufigkeit:
`one` = „einmal(ig) …“, `two` = „mehrfach …“, `three` = „wiederholt …“ bzw.
„regelmäßig …“. Auch hier ohne Subjekt und ohne Schlusspunkt.

## Technische Checkliste für ein neues eingebautes Symbol

1. Eintrag in `app/infrastructure/default_symbols.json` (`codepoint`,
   `meaning`, `shortcut`, `legend` mit `one`/`two`/`three`, ggf. `role`).
2. **Glyph in Segoe UI Symbol (`seguisym.ttf`) prüfen.** Der PDF-Export
   registriert nur eine Symbolschrift (`pdf_exporter._FONT_CANDIDATES`);
   ein Zeichen, das nur in der Emoji-Schrift steckt, erscheint im PDF als
   Kästchen.
3. **Kürzel:** ein freier Buchstabe, nicht in `RESERVED_SYMBOL_LETTERS`
   (`custom_symbol_validation.py`) und nicht von einem anderen eingebauten
   Symbol belegt. `tests/test_shortcut_bindings_headless.py` prüft die
   Konfliktfreiheit.
4. Nichts an `config/symbols.json` ändern: `_merge_new_builtins` ergänzt
   neue Symbole beim nächsten Start, ohne eigene Anpassungen anzutasten.
5. CHANGELOG (nutzerseitig) und `docs/DEVELOPMENT_LOG.md` ergänzen.

## Vorhandene Symbole ändern

- **Codepoint nie ändern.** Er ist die Identität eines eingebauten Symbols
  im Katalog-Abgleich (`known_builtin_codepoints`); ein neuer Codepoint
  gilt als neues Symbol.
- **Bedeutung umbenennen nur mit Eintrag in `LEGACY_SYMBOL_RENAMES`**
  (`app/core/domain/symbol_renames.py`). Pläne und Einstellungen speichern
  Symbole unter ihrer Bedeutung; ohne Eintrag verwaisen bereits erfasste
  Beobachtungen.
- Legendentexte dürfen frei überarbeitet werden. Bestehende lokale
  Arbeitskopien übernehmen solche Änderungen allerdings nicht automatisch,
  weil `_merge_new_builtins` vorhandene Einträge nie überschreibt.
