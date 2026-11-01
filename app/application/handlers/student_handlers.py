from __future__ import annotations

import dataclasses
import logging

from app.application.app_state import AppState, InteractionMode
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.intents.student_intents import (
    CreateStudentIntent,
    DeleteStudentsIntent,
    MoveStudentIntent,
    RenameStudentIntent,
    SetNicknameIntent,
    SetTeacherSeatIntent,
)
from app.core.usecases.v4.student_usecases import (
    create_student,
    delete_students,
    move_student,
    move_teacher_seat,
    rename_student,
    set_nickname,
)

_log = logging.getLogger("kartograph.handlers.student")


@requires_open_plan
def handle_create_student(intent: CreateStudentIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt einen neuen Schüler an und wechselt direkt in den Namenseditier-Modus.

    Args:
        intent: Ziel-Rasterkoordinaten des neuen Schülers.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = create_student(state.current_plan, intent.x, intent.y)
    return dataclasses.replace(
        _commit_plan_change(state, ctx, next_plan),
        interaction_mode=InteractionMode.NAME_EDIT,
    )


@requires_open_plan
def handle_move_student(intent: MoveStudentIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Verschiebt einen Schüler an eine neue Zelle (Diagnoseprofil/Historie bleiben erhalten).

    Args:
        intent: Schüler-ID und Ziel-Rasterkoordinaten.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = move_student(state.current_plan, intent.student_id, intent.new_x, intent.new_y)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_rename_student(intent: RenameStudentIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt Vor- und Nachname eines Schülers und kehrt in den Raster-Interaktionsmodus zurück.

    Args:
        intent: Schüler-ID sowie neuer Vor- und Nachname.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = rename_student(state.current_plan, intent.student_id, intent.first_name, intent.last_name)
    return dataclasses.replace(
        _commit_plan_change(state, ctx, next_plan, merge_key=("student.rename", intent.student_id)),
        interaction_mode=InteractionMode.GRID,
    )


@requires_open_plan
def handle_set_nickname(intent: SetNicknameIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt den Spitznamen eines Schülers und speichert den Plan.

    Args:
        intent: Schüler-ID und neuer Spitzname.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = set_nickname(state.current_plan, intent.student_id, intent.nickname)
    return _commit_plan_change(state, ctx, next_plan, merge_key=("student.nickname", intent.student_id))


@requires_open_plan
def handle_delete_students(intent: DeleteStudentsIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Entfernt die ausgewählten Schüler vollständig aus dem Plan, als ein Undo-Schritt.

    Args:
        intent: IDs der zu löschenden Schüler.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = delete_students(state.current_plan, intent.student_ids)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_set_teacher_seat(intent: SetTeacherSeatIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Verschiebt den Lehrertisch auf eine neue Zelle.

    Args:
        intent: Ziel-Rasterkoordinaten des Lehrertischs.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = move_teacher_seat(state.current_plan, intent.x, intent.y)
    return _commit_plan_change(state, ctx, next_plan)
