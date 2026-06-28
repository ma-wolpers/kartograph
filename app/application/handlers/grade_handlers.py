from __future__ import annotations

import dataclasses
from copy import deepcopy

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.domain.models_v4 import SeatingPlan
from app.core.intents.grade_intents import (
    AddGradeColumnIntent,
    DeleteGradeColumnIntent,
    RecordGradeIntent,
    UpdateGradeWeightingIntent,
)
from app.core.usecases.v4.grade_usecases import (
    add_grade_column,
    record_grade,
    set_grade_weighting,
)


def _delete_grade_column(plan: SeatingPlan, column_id: str) -> SeatingPlan:
    """Entfernt die Notenspalte *column_id* und löscht zugehörige Noten aus allen Sessions (Kaskade).

    Args:
        plan: Plan, aus dem die Spalte entfernt wird.
        column_id: ID der zu löschenden Notenspalte.
    """
    next_plan = deepcopy(plan)
    next_plan.documentation.grade_columns = [
        c for c in next_plan.documentation.grade_columns if c.column_id != column_id
    ]
    for session in next_plan.documentation.sessions:
        for entry in session.entries.values():
            entry.grades.pop(column_id, None)
    return next_plan


def handle_add_grade_column(intent: AddGradeColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt eine neue Notenspalte an und markiert sie als ausgewählt.

    Args:
        intent: Kategorie ("schriftlich"/"sonstig") und Titel der neuen Spalte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan, _column_id = add_grade_column(state.current_plan, intent.category, intent.title)
    _record_and_save(next_plan, state.current_plan_path, "grade.column.add", ctx)
    return dataclasses.replace(
        _with_plan(state, next_plan, ctx),
        doc_selected_column_id=_column_id or state.doc_selected_column_id,
    )


def handle_delete_grade_column(intent: DeleteGradeColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht die Notenspalte aus *intent* und hebt die Auswahl auf, falls sie diese betraf.

    Args:
        intent: ID der zu löschenden Notenspalte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = _delete_grade_column(state.current_plan, intent.column_id)
    _record_and_save(next_plan, state.current_plan_path, "grade.column.delete", ctx)
    cleared_col = None if state.doc_selected_column_id == intent.column_id else state.doc_selected_column_id
    return dataclasses.replace(
        _with_plan(state, next_plan, ctx),
        doc_selected_column_id=cleared_col,
    )


def handle_record_grade(intent: RecordGradeIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Trägt die Note aus *intent* ein (0.0 löscht den Eintrag, s. ``record_grade``-Usecase).

    Args:
        intent: Schüler-ID, Datum, Spalte und einzutragende Note.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    grade_value = intent.grade if intent.grade != 0.0 else None
    next_plan = record_grade(
        state.current_plan, intent.student_id, intent.date, intent.column_id, grade_value
    )
    _record_and_save(next_plan, state.current_plan_path, "grade.record", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_update_grade_weighting(
    intent: UpdateGradeWeightingIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt die Gewichtung schriftlicher/sonstiger Noten gemäß *intent*.

    Args:
        intent: Prozentanteile für schriftliche und sonstige Noten.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = set_grade_weighting(state.current_plan, intent.written_percent, intent.sonstige_percent)
    _record_and_save(next_plan, state.current_plan_path, "grade.weighting.update", ctx)
    return _with_plan(state, next_plan, ctx)
