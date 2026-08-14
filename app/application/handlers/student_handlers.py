from __future__ import annotations

import dataclasses
import logging

from app.application.app_state import AppState, InteractionMode
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.intents.student_intents import (
    CreateStudentIntent,
    DeleteStudentIntent,
    MoveStudentIntent,
    RenameStudentIntent,
    SetNicknameIntent,
    SetTeacherSeatIntent,
)
from app.core.usecases.v4.student_usecases import (
    create_student,
    delete_student,
    move_student,
    move_teacher_seat,
    rename_student,
    set_nickname,
)

_log = logging.getLogger("kartograph.handlers.student")


def handle_create_student(intent: CreateStudentIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt einen neuen Schüler an und wechselt direkt in den Namenseditier-Modus.

    Args:
        intent: Ziel-Rasterkoordinaten des neuen Schülers.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = create_student(state.current_plan, intent.x, intent.y)
    _record_and_save(next_plan, state.current_plan_path, "student.create", ctx)
    return dataclasses.replace(
        _with_plan(state, next_plan, ctx),
        interaction_mode=InteractionMode.NAME_EDIT,
    )


def handle_move_student(intent: MoveStudentIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Verschiebt einen Schüler an eine neue Zelle (Diagnoseprofil/Historie bleiben erhalten).

    Args:
        intent: Schüler-ID und Ziel-Rasterkoordinaten.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = move_student(state.current_plan, intent.student_id, intent.new_x, intent.new_y)
    _record_and_save(next_plan, state.current_plan_path, "student.move", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_rename_student(intent: RenameStudentIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt Vor- und Nachname eines Schülers und kehrt in den Raster-Interaktionsmodus zurück.

    Args:
        intent: Schüler-ID sowie neuer Vor- und Nachname.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = rename_student(state.current_plan, intent.student_id, intent.first_name, intent.last_name)
    _record_and_save(next_plan, state.current_plan_path, "student.rename", ctx)
    return dataclasses.replace(
        _with_plan(state, next_plan, ctx),
        interaction_mode=InteractionMode.GRID,
    )


def handle_set_nickname(intent: SetNicknameIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt den Spitznamen eines Schülers und speichert den Plan.

    Args:
        intent: Schüler-ID und neuer Spitzname.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = set_nickname(state.current_plan, intent.student_id, intent.nickname)
    _record_and_save(next_plan, state.current_plan_path, "student.set_nickname", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_delete_student(intent: DeleteStudentIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Entfernt einen Schüler vollständig aus dem Plan.

    Args:
        intent: ID des zu löschenden Schülers.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = delete_student(state.current_plan, intent.student_id)
    _record_and_save(next_plan, state.current_plan_path, "student.delete", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_set_teacher_seat(intent: SetTeacherSeatIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Verschiebt den Lehrertisch auf eine neue Zelle.

    Args:
        intent: Ziel-Rasterkoordinaten des Lehrertischs.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = move_teacher_seat(state.current_plan, intent.x, intent.y)
    _record_and_save(next_plan, state.current_plan_path, "teacher_seat.set", ctx)
    return _with_plan(state, next_plan, ctx)
