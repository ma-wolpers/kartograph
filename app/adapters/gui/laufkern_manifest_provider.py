"""Builds LaufKern manifests from Kartograph runtime shortcut registry state."""

from __future__ import annotations

from bw_libs.ui_contract.keybinding import KeybindingRegistry
from bw_libs.ui_contract.laufkern import LaufKernRoute, build_manifest


def build_runtime_shortcut_manifest(registry: KeybindingRegistry):
    """Build one declarative manifest from current runtime shortcut registrations.

    Args:
        registry: Keybinding registry holding the current runtime shortcut definitions.
    """

    definitions = registry.all()
    intents = tuple(sorted({definition.intent for definition in definitions}))
    routes = tuple(
        LaufKernRoute(
            route_id=f"shortcut.{definition.binding_id}",
            intent=definition.intent,
            route_type="shortcut",
            modes=tuple(definition.modes),
            binding_id=definition.binding_id,
            metadata={"sequence": definition.sequence},
        )
        for definition in definitions
    )
    return build_manifest(
        manifest_id="kartograph.shortcuts.runtime",
        repo_name="kartograph",
        intents=intents,
        routes=routes,
        keybinding_registry=registry,
        metadata={"provider": "kartograph.app.adapters.gui.laufkern_manifest_provider"},
    )
