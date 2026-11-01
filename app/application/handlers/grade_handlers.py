from __future__ import annotations

import dataclasses
from copy import deepcopy

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.domain.models_v4 import SeatingPlan
from app.core.intents.grade_intents import (
    AddGradeColumnIntent,
    DeleteGradeColumnIntent,
    RecordGradeIntent,
    ResolveGradeConflictsIntent,
    SetGradeScaleIntent,
    UpdateGradeWeightingIntent,
)
from app.core.usecases.v4.grade_scale_usecases import set_grade_scale
from app.core.usecases.v4.grade_usecases import (
    add_grade_column,
    record_grade,
    resolve_grade_conflicts,
    set_grade_weighting,
)


def _delete_grade_column(plan: SeatingPlan, column_id: str) -> SeatingPlan:
    """Entfernt die Notenspalte *column_id* samt ihrer Noten und offenen Konflikte.

    Args:
        plan: Plan, aus dem die Spalte entfernt wird.
        column_id: ID der zu löschenden Notenspalte.
    """
    next_plan = deepcopy(plan)
    next_plan.documentation.grade_columns = [
        c for c in next_plan.documentation.grade_columns if c.column_id != column_id
    ]
    next_plan.documentation.remove_column_grades(column_id)
    return next_plan


@requires_open_plan
def handle_add_grade_column(intent: AddGradeColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt eine neue Notenspalte an und markiert sie als ausgewählt.

    Args:
        intent: Kategorie ("schriftlich"/"sonstig") und Titel der neuen Spalte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan, _column_id = add_grade_column(state.current_plan, intent.category, intent.title)
    return dataclasses.replace(
        _commit_plan_change(state, ctx, next_plan),
        doc_selected_column_id=_column_id or state.doc_selected_column_id,
    )


@requires_open_plan
def handle_delete_grade_column(intent: DeleteGradeColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht die Notenspalte aus *intent* und hebt die Auswahl auf, falls sie diese betraf.

    Args:
        intent: ID der zu löschenden Notenspalte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = _delete_grade_column(state.current_plan, intent.column_id)
    cleared_col = None if state.doc_selected_column_id == intent.column_id else state.doc_selected_column_id
    return dataclasses.replace(
        _commit_plan_change(state, ctx, next_plan),
        doc_selected_column_id=cleared_col,
    )


@requires_open_plan
def handle_record_grade(intent: RecordGradeIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Trägt die Note aus *intent* ein (``None`` löscht den Eintrag, s. ``record_grade``-Usecase).

    Args:
        intent: Schüler-ID, Spalte und einzutragende Note.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = record_grade(state.current_plan, intent.student_id, intent.column_id, intent.grade)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_resolve_grade_conflicts(
    intent: ResolveGradeConflictsIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Übernimmt die im Dialog gewählten Noten für alte Mehrfachnoten (ein Undo-Schritt).

    Args:
        intent: Gewählte Noten.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = resolve_grade_conflicts(state.current_plan, intent.choices)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_update_grade_weighting(
    intent: UpdateGradeWeightingIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt die Gewichtung schriftlicher/sonstiger Noten gemäß *intent*.

    Args:
        intent: Prozentanteile für schriftliche und sonstige Noten.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = set_grade_weighting(state.current_plan, intent.written_percent, intent.sonstige_percent)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_set_grade_scale(intent: SetGradeScaleIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Stellt die Notenskala des Plans um und rechnet alle Werte um (undo-fähig).

    Läuft wie alle Planänderungen über ``_record_and_save``, sodass Strg+Z
    den gesamten Wechsel inkl. Umrechnung in einem Schritt zurücknimmt.

    Args:
        intent: ID der Zielskala.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = set_grade_scale(state.current_plan, intent.scale_id)
    return _commit_plan_change(state, ctx, next_plan)
