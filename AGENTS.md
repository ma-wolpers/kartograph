# Agent Guardrails (kartograph)

Dieses Repository hat verbindliche Leitplanken fuer KI-Programmierer.

Ziel in einfachen Worten:
- Architektur als stabilen Ist-Zustand dokumentieren.
- Aenderungsverlauf getrennt und nachvollziehbar fuehren.
- Oeffentliche Kommunikation konsistent ueber Changelog und Releases pflegen.

Verbindliche Regeln:

1. Architektur-Dokumentrolle
- `docs/ARCHITEKTUR.md` enthaelt nur den aktuellen Zustand.
- Historie/Abschluesse gehoeren nicht in diese Datei.

2. Development-Log-Pflicht
- Bei Feature- und Architektur-Aenderungen muss `docs/DEVELOPMENT_LOG.md` im selben Zyklus aktualisiert werden.
- Reine Bugfix-Only-Changes koennen ohne Development-Log-Eintrag erfolgen.

3. Public-Kommunikation
- Nutzerrelevante Aenderungen werden in `CHANGELOG.md` gepflegt.
- PRs verwenden die Checkliste in `.github/pull_request_template.md`.

4. Automatische Gates
- Lokaler Check und CI pruefen die Guardrails ueber `tools/ci/check_ai_guardrails.py`.
- Ein Verstoss blockiert den Build.

5. Zentrale UI-Steuerung
- KeyBindings werden zentral in `app/adapters/gui/keybinding_registry.py` verwaltet.
- Pop-up-Verhalten wird zentral in `app/adapters/gui/popup_policy.py` verwaltet.
- Neue Shortcuts und neue Pop-ups werden zuerst in diesen Zentralmodulen definiert und danach in Views angebunden.

6. Feature-Commit und Push-Disziplin
- Feature-Aenderungen werden in eigenstaendigen Commits gebuendelt.
- Push erfolgt manuell durch den Nutzer; kein Auto-Push.
