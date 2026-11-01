from __future__ import annotations

import dataclasses

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.intents.tablegroup_intents import ApplyTablegroupSettingsIntent
from app.core.usecases.v4.tablegroup_usecases import RESET_ALL_TRANSFORMS, apply_tablegroup_settings

_RESET_LABELS = {
    "shift_x": "x-shift",
    "shift_y": "y-shift",
    "rotation": "rotation",
    RESET_ALL_TRANSFORMS: "x/y-shift und rotation",
}


@requires_open_plan
def handle_apply_tablegroup_settings(
    intent: ApplyTablegroupSettingsIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Übernimmt die Tischgruppen-Einstellungen aus *intent* als einen Undo-Schritt.

    Args:
        intent: Position, Nummer, Geometrie und zuletzt bearbeitetes Feld.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    result = apply_tablegroup_settings(
        state.current_plan,
        intent.x,
        intent.y,
        number=intent.number,
        shift_x=intent.shift_x,
        shift_y=intent.shift_y,
        rotation=intent.rotation,
        last_changed_field=intent.last_changed_field,
    )
    if result.plan is None:
        return dataclasses.replace(state, status_message="Nur Schuelertische gehoeren zu Tischgruppen")
    if result.reset_field is None:
        status = f"TG {intent.number} gespeichert"
    else:
        status = f"Ueberlappung erkannt: {_RESET_LABELS[result.reset_field]} auf 0 gesetzt"
    return _commit_plan_change(state, ctx, result.plan, status=status)
