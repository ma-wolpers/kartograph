from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.intents.participation_intents import SetParticipationRatingIntent
from app.core.usecases.v4.participation_usecases import set_participation_rating


def handle_set_participation_rating(
    intent: SetParticipationRatingIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt/löscht die Mitarbeit-Bewertung aus *intent* für den Schüler an diesem Datum.

    Args:
        intent: Schüler-ID, Datum und zu setzende Bewertung.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = set_participation_rating(
        state.current_plan, intent.student_id, intent.date, intent.rating
    )
    _record_and_save(next_plan, state.current_plan_path, "participation.set", ctx)
    return _with_plan(state, next_plan, ctx)
