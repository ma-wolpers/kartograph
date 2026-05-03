## Summary
- What changed?

## Guardrails Checklist
- [ ] `docs/ARCHITEKTUR.md` remains current-state only (no history section)
- [ ] `docs/DEVELOPMENT_LOG.md` updated for feature/architecture changes
- [ ] `CHANGELOG.md` updated for user-facing changes
- [ ] New shortcuts are registered centrally in `app/adapters/gui/keybinding_registry.py`
- [ ] New popups follow central policy in `app/adapters/gui/popup_policy.py`
- [ ] Feature work is grouped in dedicated commit(s)
- [ ] No auto-push required; push stays manual
- [ ] `tools/ci/check_ai_guardrails.py` passes locally
