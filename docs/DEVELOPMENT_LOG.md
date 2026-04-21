# Development Log (kartograph)

Dieses Dokument trackt technische Aenderungen fuer Feature- und Architekturarbeit.

Regel:
- Keine Feature- oder Architekturaenderung ohne Update in diesem Log.
- Bugfix-Only-Changes koennen ohne Eintrag erfolgen.

## [Unreleased]

### Added
- Guardrail-Basis eingefuehrt: `AGENTS.md`, `.github/copilot-instructions.md`, PR-Template und CI-Check.

### Changed
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

### Added
- `app/infrastructure/symbol_config_loader.py` fuer Schema-Pruefung und Laden der Symbolkonfiguration.
- `app/infrastructure/exporters/pdf_exporter.py` fuer PDF-Ausgabe ohne Rasterlinien und mit klaren Tischrahmen.
- `docs/TODO.md` mit offenem Hinweis zur spaeteren Warnung bzgl. Standardperspektive (Lehrertisch unten).
