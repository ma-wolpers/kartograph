# GUI Migration Backlog

## Active Exemptions
- app/adapters/gui/main_window.py
  remove_by: 2026-12-31
  reason: Existing main GUI entrypoint remains baseline while strict shared-contract checks are active.
- app/adapters/gui/main_window.py:KartographMainWindow
  remove_by: 2026-09-30
  reason: Local ui.Tk baseclass pending migration to bw-gui host/factory.

## Notes
- This backlog tracks all currently allowed baseline/exemption entries referenced by guardrails.
- Exemptions are temporary and must be removed after migration completion.
