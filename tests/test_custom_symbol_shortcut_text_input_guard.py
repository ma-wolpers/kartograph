"""Tests: Custom-Symbol-Buchstaben-Shortcuts duerfen normale Texteingabe nicht abfangen.

Die Bindungen entstehen jetzt fuer ~11 statt 1 Buchstaben (siehe
_mixin_shortcuts.py::_bind_shortcuts()), daher wird der bestehende
Laufzeit-Schutzmechanismus (bw_gui.contracts.keybinding) hier explizit fuer
genau diese Bindungsform (modes=(UI_MODE_PREVIEW,),
allow_when_text_input=False) abgesichert -- dieselbe Vertragsebene, mit der
auch die uebrigen Runtime-Shortcuts getestet werden
(test_keybinding_registry_runtime.py).
"""

from bw_libs.ui_contract.keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
)


def _custom_symbol_binding(letter: str = "l") -> KeyBindingDefinition:
    """Baut dieselbe Bindungsform, die _bind_shortcuts() fuer ein freies
    Custom-Symbol-Kuerzel registriert."""
    return KeyBindingDefinition(
        binding_id=f"custom_symbol.{letter}",
        sequence=f"<KeyPress-{letter}>",
        intent="docs.custom_symbol_shortcut",
        modes=(UI_MODE_PREVIEW,),
        allow_when_text_input=False,
    )


def test_blocked_while_a_text_field_is_focused():
    registry = KeybindingRegistry()
    binding = _custom_symbol_binding()
    registry.register(binding)

    can_execute, reason = registry.evaluate_runtime(
        binding,
        KeybindingRuntimeContext(active_mode=UI_MODE_EDITOR, text_input_focused=True),
    )

    assert can_execute is False
    assert reason in {"text-input-focus", f"mode={UI_MODE_EDITOR}"}


def test_blocked_while_the_symbol_form_dialog_itself_is_open():
    registry = KeybindingRegistry()
    binding = _custom_symbol_binding()
    registry.register(binding)

    can_execute, reason = registry.evaluate_runtime(
        binding,
        KeybindingRuntimeContext(active_mode=UI_MODE_DIALOG, dialog_open=True),
    )

    assert can_execute is False


def test_fires_in_plain_preview_mode_without_text_focus():
    registry = KeybindingRegistry()
    binding = _custom_symbol_binding()
    registry.register(binding)

    can_execute, _reason = registry.evaluate_runtime(
        binding,
        KeybindingRuntimeContext(active_mode=UI_MODE_PREVIEW),
    )

    assert can_execute is True
