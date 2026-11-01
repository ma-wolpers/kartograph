from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.usecases.v4.accommodation_usecases import set_accommodations


@requires_open_plan
def handle_set_accommodations(
    intent: SetAccommodationsIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt die Nachteilsausgleiche des Schülers aus *intent* und speichert den Plan.

    Args:
        intent: Schüler-ID und vollständige neue Liste der Nachteilsausgleiche.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = set_accommodations(state.current_plan, intent.student_id, intent.accommodations)
    return _commit_plan_change(state, ctx, next_plan, merge_key=("accommodations", intent.student_id))
