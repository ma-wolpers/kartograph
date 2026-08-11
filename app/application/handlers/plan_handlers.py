from __future__ import annotations

import dataclasses
import logging

from app.application.app_state import AppState, InteractionMode, PlanListEntry
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _refresh_plan_list, _with_plan
from app.core.domain.plan_selection import RectSelection
from app.core.domain.settings import resolve_plans_dir
from app.core.intents.plan_intents import (
    CreatePlanIntent,
    DeletePlanIntent,
    DuplicatePlanIntent,
    OpenPlanIntent,
    RenamePlanIntent,
)

_log = logging.getLogger("kartograph.handlers.plan")


def handle_open_plan(intent: OpenPlanIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Lädt den Plan aus *intent* und macht ihn zum aktuellen Plan; setzt History und Auswahl zurück.

    Args:
        intent: Pfad der zu öffnenden Plandatei.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History, Plan-Verzeichnis).
    """
    try:
        plan = ctx.plan_repository.load_plan(intent.plan_path)
    except Exception:
        _log.exception("handle_open_plan: load failed for %s", intent.plan_path)
        return dataclasses.replace(state, status_message=f"Fehler beim Öffnen: {intent.plan_path.name}")

    ctx.history.reset(plan)
    plan_list = _refresh_plan_list(state, ctx)
    return dataclasses.replace(
        state,
        current_plan=plan,
        current_plan_path=intent.plan_path,
        plan_list=plan_list,
        selection=RectSelection(0, 0),
        interaction_mode=InteractionMode.GRID,
        can_undo=False,
        can_redo=False,
        status_message="",
    )


def handle_create_plan(intent: CreatePlanIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt einen neuen Plan namens *intent.name* an und macht ihn zum aktuellen Plan.

    Args:
        intent: Anzeigename des neuen Plans.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History, Plan-Verzeichnis).
    """
    try:
        plans_dir = resolve_plans_dir(state.settings.plans_dir, ctx.default_plans_dir)
        plan_path, plan = ctx.plan_repository.create_new_plan(plans_dir, intent.name)
    except Exception:
        _log.exception("handle_create_plan: failed for name=%r", intent.name)
        return dataclasses.replace(state, status_message="Fehler beim Erstellen des Plans")

    ctx.history.reset(plan)
    plan_list = _refresh_plan_list(state, ctx)
    return dataclasses.replace(
        state,
        current_plan=plan,
        current_plan_path=plan_path,
        plan_list=plan_list,
        selection=RectSelection(0, 0),
        interaction_mode=InteractionMode.GRID,
        can_undo=False,
        can_redo=False,
        status_message="",
    )


def handle_rename_plan(intent: RenamePlanIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Benennt den Plan aus *intent* um; aktualisiert ``current_plan_path``, falls er gerade offen ist.

    Args:
        intent: Pfad des umzubenennenden Plans und neuer Anzeigename.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository).
    """
    try:
        new_path, plan = ctx.plan_repository.rename_plan(intent.plan_path, intent.new_name)
    except Exception:
        _log.exception("handle_rename_plan: failed")
        return dataclasses.replace(state, status_message="Fehler beim Umbenennen")

    plan_list = _refresh_plan_list(state, ctx)
    new_current_path = new_path if state.current_plan_path == intent.plan_path else state.current_plan_path
    return dataclasses.replace(state, plan_list=plan_list, current_plan_path=new_current_path)


def handle_delete_plan(intent: DeletePlanIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht den Plan aus *intent*; schließt ihn im Editor, falls er gerade offen ist.

    Args:
        intent: Pfad des zu löschenden Plans.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository).
    """
    try:
        ctx.plan_repository.delete_plan(intent.plan_path)
    except Exception:
        _log.exception("handle_delete_plan: failed for %s", intent.plan_path)
        return dataclasses.replace(state, status_message="Fehler beim Löschen")

    plan_list = _refresh_plan_list(state, ctx)
    was_open = state.current_plan_path == intent.plan_path
    if was_open:
        return dataclasses.replace(
            state,
            current_plan=None,
            current_plan_path=None,
            plan_list=plan_list,
            interaction_mode=InteractionMode.LIST,
            can_undo=False,
            can_redo=False,
        )
    return dataclasses.replace(state, plan_list=plan_list)


def handle_duplicate_plan(intent: DuplicatePlanIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Dupliziert den Plan aus *intent* unter dem neuen Namen; öffnet das Duplikat nicht automatisch.

    Args:
        intent: Quellpfad, neuer Anzeigename und ob eine vorhandene Zieldatei überschrieben werden soll.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository).
    """
    try:
        _new_path, _plan = ctx.plan_repository.duplicate_plan(
            intent.plan_path, intent.new_name, overwrite=intent.overwrite
        )
    except Exception:
        _log.exception("handle_duplicate_plan: failed for %s", intent.plan_path)
        return dataclasses.replace(state, status_message="Fehler beim Duplizieren")

    plan_list = _refresh_plan_list(state, ctx)
    return dataclasses.replace(state, plan_list=plan_list, status_message=f"Plan dupliziert: {intent.new_name}")
