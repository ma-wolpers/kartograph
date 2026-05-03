from app.adapters.gui.popup_policy import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry


def test_popup_manifest_tracks_stack() -> None:
    registry = PopupPolicyRegistry()
    registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
    registry.open_popup("tablegroup", "Tischeinstellungen", "dialog.modal")

    manifest = registry.popup_manifest()
    assert manifest["policies"] == ["dialog.modal"]
    assert manifest["active_stack"] == ["tablegroup"]


def test_mode_blocking_popup_respects_policy_flag() -> None:
    registry = PopupPolicyRegistry()
    registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
    registry.register_policy(
        PopupPolicy(
            policy_id="dialog.non_blocking",
            kind=POPUP_KIND_NON_MODAL,
            affects_mode=False,
            trap_focus=False,
        )
    )

    registry.open_popup("runtime", "Runtime", "dialog.non_blocking")
    assert registry.has_active_popup() is True
    assert registry.has_mode_blocking_popup() is False

    registry.open_popup("modal", "Modal", "dialog.modal")
    assert registry.has_mode_blocking_popup() is True
