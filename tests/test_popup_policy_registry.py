from app.adapters.gui.popup_policy import POPUP_KIND_MODAL, PopupPolicy, PopupPolicyRegistry


def test_popup_manifest_tracks_stack() -> None:
    registry = PopupPolicyRegistry()
    registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
    registry.open_popup("tablegroup", "Tischeinstellungen", "dialog.modal")

    manifest = registry.popup_manifest()
    assert manifest["policies"] == ["dialog.modal"]
    assert manifest["active_stack"] == ["tablegroup"]
