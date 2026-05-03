from bw_libs.ui_contract.keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
)


def test_runtime_evaluation_in_dialog_and_preview_modes() -> None:
    registry = KeybindingRegistry()
    preview_binding = KeyBindingDefinition(
        binding_id="view.toggle",
        sequence="<Control-Shift-d>",
        intent="view.documentation.toggle",
        modes=(UI_MODE_PREVIEW,),
        allow_when_text_input=False,
    )
    dialog_binding = KeyBindingDefinition(
        binding_id="debug.runtime",
        sequence="<Control-Shift-r>",
        intent="debug.runtime",
        modes=(UI_MODE_DIALOG,),
        allow_when_text_input=True,
    )
    registry.register(preview_binding)
    registry.register(dialog_binding)

    can_execute, reason = registry.evaluate_runtime(
        preview_binding,
        KeybindingRuntimeContext(active_mode=UI_MODE_PREVIEW, dialog_open=True),
    )
    assert can_execute is False
    assert reason == "dialog-priority"

    can_execute, reason = registry.evaluate_runtime(
        dialog_binding,
        KeybindingRuntimeContext(active_mode=UI_MODE_DIALOG, dialog_open=True),
    )
    assert can_execute is True
    assert reason == "active"
