# Copilot Instructions (kartograph)

Arbeite in klarer Dokumenttrennung und halte Guardrails strikt ein.

Pflichtregeln:

1. Architektur-Referenz
- `docs/ARCHITEKTUR.md` beschreibt nur den aktuellen Zustand.
- Keine Abschluss-/Historienlisten im Architekturdokument.

2. Development-Log
- Bei Feature- und Architektur-Aenderungen immer `docs/DEVELOPMENT_LOG.md` im selben Zyklus aktualisieren.
- Bugfix-Only-Aenderungen sind davon ausgenommen.

3. Public Changelog
- Nutzerrelevante Aenderungen in `CHANGELOG.md` eintragen.

4. PR-Disziplin
- `.github/pull_request_template.md` verwenden und Checkliste vollstaendig pflegen.

5. Guardrails sind bindend
- `tools/ci/check_ai_guardrails.py` muss lokal und in CI bestehen.
