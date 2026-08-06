from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.intents.color_intents import ToggleColorIntent
from app.core.usecases.v4.color_usecases import toggle_color_tag


def handle_toggle_color(intent: ToggleColorIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Schaltet den Farbpunkt aus *intent* beim Schüler um, speichert und schreibt History.

    Args:
        intent: Schüler-ID und umzuschaltender Farbschlüssel.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = toggle_color_tag(state.current_plan, intent.student_id, intent.color_key)
    _record_and_save(next_plan, state.current_plan_path, "color.toggle", ctx)
    return _with_plan(state, next_plan, ctx)
