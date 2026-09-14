from __future__ import annotations

import dataclasses

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.intents.snapshot_intents import (
    CreateSnapshotIntent,
    DeleteSnapshotIntent,
    RenameSnapshotIntent,
    RestoreSnapshotIntent,
)
from app.core.usecases.v4.snapshot_usecases import (
    create_snapshot,
    delete_snapshot,
    rename_snapshot,
    restore_snapshot,
)


def handle_create_snapshot(intent: CreateSnapshotIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt einen neuen Snapshot an und speichert den Plan, sofern tatsächlich einer angelegt wurde.

    Args:
        intent: Name des neuen Snapshots.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    result = create_snapshot(state.current_plan, intent.name)
    if not result.created:
        return dataclasses.replace(state, status_message="Dieser Sitzplan ist bereits als Snapshot gespeichert")
    _record_and_save(result.plan, state.current_plan_path, "snapshot.create", ctx)
    return _with_plan(state, result.plan, ctx, status="Snapshot gespeichert")


def handle_delete_snapshot(intent: DeleteSnapshotIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht einen Snapshot und speichert den Plan, sofern tatsächlich etwas geändert wurde.

    Args:
        intent: ID des zu löschenden Snapshots.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    result = delete_snapshot(state.current_plan, intent.snapshot_id)
    if not result.changed:
        return state
    _record_and_save(result.plan, state.current_plan_path, "snapshot.delete", ctx)
    return _with_plan(state, result.plan, ctx, status="Snapshot gelöscht")


def handle_rename_snapshot(intent: RenameSnapshotIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Benennt einen Snapshot um und speichert den Plan, sofern tatsächlich etwas geändert wurde.

    Args:
        intent: ID des Snapshots sowie neuer Anzeigename.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    result = rename_snapshot(state.current_plan, intent.snapshot_id, intent.new_name)
    if not result.changed:
        return state
    _record_and_save(result.plan, state.current_plan_path, "snapshot.rename", ctx)
    return _with_plan(state, result.plan, ctx)


def handle_restore_snapshot(intent: RestoreSnapshotIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Stellt die Tischkoordinaten eines Snapshots wieder her und speichert den Plan.

    Args:
        intent: ID des wiederherzustellenden Snapshots.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    result = restore_snapshot(state.current_plan, intent.snapshot_id)
    if not result.changed:
        return state
    _record_and_save(result.plan, state.current_plan_path, "snapshot.restore", ctx)
    return _with_plan(state, result.plan, ctx, status="Snapshot geladen")
