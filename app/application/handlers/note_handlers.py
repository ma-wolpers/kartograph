from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.intents.note_intents import SetNotesIntent
from app.core.usecases.v4.note_usecases import set_notes


@requires_open_plan
def handle_set_notes(
    intent: SetNotesIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt die Notizen des Schülers aus *intent* und speichert den Plan.

    Args:
        intent: Schüler-ID und vollständige neue Liste der Notizen.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = set_notes(state.current_plan, intent.student_id, intent.notes)
    return _commit_plan_change(state, ctx, next_plan, merge_key=("notes", intent.student_id))
