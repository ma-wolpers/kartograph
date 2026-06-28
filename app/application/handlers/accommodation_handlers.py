from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.usecases.v4.accommodation_usecases import set_accommodations


def handle_set_accommodations(
    intent: SetAccommodationsIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt die Nachteilsausgleiche des Schülers aus *intent* und speichert den Plan.

    Args:
        intent: Schüler-ID und vollständige neue Liste der Nachteilsausgleiche.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = set_accommodations(state.current_plan, intent.student_id, intent.accommodations)
    _record_and_save(next_plan, state.current_plan_path, "accommodation.set", ctx)
    return _with_plan(state, next_plan, ctx)
