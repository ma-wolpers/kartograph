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
