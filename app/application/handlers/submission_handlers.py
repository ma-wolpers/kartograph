"""Handler für "Abgaben zählen": lösen die Symbolnamen aus dem Katalog auf und speichern undo-fähig."""

from __future__ import annotations

import dataclasses

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.domain.submission_status import (
    ABSENT_CODEPOINT,
    CatalogSymbolMissing,
    resolve_symbol_name,
    submission_symbol_names,
)
from app.core.intents.submission_intents import ApplyMissingSubmissionsIntent, SetSubmissionStatusIntent
from app.core.usecases.v4.submission_usecases import apply_missing_submissions, set_submission_status


def handle_apply_missing_submissions(
    intent: ApplyMissingSubmissionsIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt X für alle Personen ohne Abgabe gemäß *intent*.

    Fehlt eines der benötigten Symbole im Katalog, bleibt der Plan
    unverändert und die Statuszeile nennt den fehlenden Codepoint.

    Args:
        intent: Datum, Abgebende, Abwesenden-Wahl und Modus.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    try:
        names = submission_symbol_names(state.symbol_catalog)
        absent = resolve_symbol_name(state.symbol_catalog, ABSENT_CODEPOINT)
    except CatalogSymbolMissing as err:
        return dataclasses.replace(state, status_message=str(err))
    next_plan = apply_missing_submissions(
        state.current_plan,
        intent.date,
        intent.submitted,
        names,
        absent_symbol=absent,
        mark_absent=intent.mark_absent,
        mode="complement" if intent.mode == "complement" else "replace",
    )
    _record_and_save(next_plan, state.current_plan_path, "submission.missing.apply", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_set_submission_status(intent: SetSubmissionStatusIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt den Abgabestatus einer Person (genau eines von ✓/◐/X).

    Args:
        intent: Person, Datum und Status.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    try:
        names = submission_symbol_names(state.symbol_catalog)
    except CatalogSymbolMissing as err:
        return dataclasses.replace(state, status_message=str(err))
    next_plan = set_submission_status(state.current_plan, intent.student_id, intent.date, intent.status, names)
    # Jede Bewertung ist eine eigene Entscheidung: nie mit der vorigen zusammenfassen.
    _record_and_save(next_plan, state.current_plan_path, "submission.status.set", ctx, coalesce=False)
    return _with_plan(state, next_plan, ctx)
