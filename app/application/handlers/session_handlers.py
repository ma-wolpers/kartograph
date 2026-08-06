from __future__ import annotations

import dataclasses
from copy import deepcopy
from datetime import date

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.student_id import StudentId
from app.core.intents.session_intents import (
    AddSessionIntent,
    ClearDocEntryIntent,
    DeleteSessionIntent,
    GoToTodayIntent,
    NavigateSessionIntent,
)
from app.core.usecases.v4.session_usecases import ensure_session


def _delete_session(plan: SeatingPlan, target_date: str) -> SeatingPlan:
    """Entfernt die Session an *target_date* (inkl. aller Einträge) aus dem Plan.

    Args:
        plan: Plan, aus dem die Session entfernt wird.
        target_date: Datum (YYYY-MM-DD) der zu löschenden Session.
    """
    next_plan = deepcopy(plan)
    next_plan.documentation.sessions = [
        s for s in next_plan.documentation.sessions if s.date != target_date
    ]
    return next_plan


def _clear_entry(plan: SeatingPlan, student_id: StudentId, target_date: str) -> SeatingPlan:
    """Entfernt den Dokumentationseintrag eines Schülers an *target_date*, falls eine Session existiert.

    Args:
        plan: Plan, aus dem der Eintrag entfernt wird.
        student_id: Betroffener Schüler.
        target_date: Datum (YYYY-MM-DD) der Session.
    """
    next_plan = deepcopy(plan)
    session = next_plan.documentation.session_for_date(target_date)
    if session is not None:
        session.entries.pop(student_id, None)
    return next_plan


def handle_add_session(intent: AddSessionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Stellt sicher, dass für *intent.date* eine Session existiert, und wählt sie aus.

    Args:
        intent: Datum (YYYY-MM-DD), für das eine Session sichergestellt wird.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = ensure_session(state.current_plan, intent.date)
    _record_and_save(next_plan, state.current_plan_path, "session.add", ctx)
    return dataclasses.replace(
        _with_plan(state, next_plan, ctx),
        doc_selected_date=intent.date,
    )


def handle_delete_session(intent: DeleteSessionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht die Session aus *intent*; hebt die Datumsauswahl auf, falls sie diese betraf.

    Args:
        intent: Datum (YYYY-MM-DD) der zu löschenden Session.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = _delete_session(state.current_plan, intent.date)
    _record_and_save(next_plan, state.current_plan_path, "session.delete", ctx)
    cleared_date = None if state.doc_selected_date == intent.date else state.doc_selected_date
    return dataclasses.replace(
        _with_plan(state, next_plan, ctx),
        doc_selected_date=cleared_date,
    )


def handle_navigate_session(intent: NavigateSessionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Wählt das vorige/nächste Datum relativ zu ``state.doc_selected_date`` (*intent.direction*).

    Ist die aktuelle Auswahl in der Datumsliste nicht (mehr) enthalten,
    springt die Auswahl auf das späteste Datum statt eine Richtung zu
    interpretieren — es gibt sonst keinen sinnvollen "relativ zu was".

    Args:
        intent: Navigationsrichtung ("prev" oder "next").
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    if state.current_plan is None:
        return state
    # Heutiges Datum ist immer navigierbar, auch ohne gespeicherte Session
    # (entspricht der virtuellen "Heute"-Spalte in der Doku-Tabelle, s. GUI).
    dates = sorted(set(state.current_plan.documentation.all_dates()) | {date.today().isoformat()})
    if not dates:
        return state
    current = state.doc_selected_date
    if current not in dates:
        idx = len(dates) - 1
    else:
        idx = dates.index(current)
        if intent.direction == "prev":
            idx = max(0, idx - 1)
        else:
            idx = min(len(dates) - 1, idx + 1)
    return dataclasses.replace(state, doc_selected_date=dates[idx])


def handle_go_to_today(intent: GoToTodayIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Wählt das heutige Datum als aktuellen Dokumentationstermin (legt noch keine Session an).

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    return dataclasses.replace(state, doc_selected_date=date.today().isoformat())


def handle_clear_doc_entry(intent: ClearDocEntryIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht den Dokumentationseintrag eines Schülers an *intent.date*.

    Args:
        intent: Schüler-ID und Datum (YYYY-MM-DD) des zu löschenden Eintrags.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = _clear_entry(state.current_plan, intent.student_id, intent.date)
    _record_and_save(next_plan, state.current_plan_path, "doc.entry.clear", ctx)
    return _with_plan(state, next_plan, ctx)
