from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _can_redo, _can_undo, _record_and_save, _refresh_plan_list, _with_plan
from app.core.domain.list_action_history import DeletePlanAction, DuplicatePlanAction, RenamePlanAction
from app.core.intents.edit_intents import (
    CopySelectionIntent,
    CutSelectionIntent,
    PasteSelectionIntent,
    RedoIntent,
    UndoIntent,
)

_log = logging.getLogger("kartograph.handlers.edit")


def _plan_exists(ctx: HandlerContext, path: Path) -> bool:
    """Prüft über das Repository, ob unter *path* bereits eine Plandatei liegt."""
    try:
        ctx.plan_repository.load_plan(path)
    except Exception:
        return False
    return True


def _list_history_flags(ctx: HandlerContext) -> tuple[bool, bool]:
    """Liefert (can_undo, can_redo) für ``ctx.list_history`` als reine State-Ableitung."""
    return ctx.list_history.peek_undo() is not None, ctx.list_history.peek_redo() is not None


def _apply_list_undo(state: AppState, ctx: HandlerContext) -> AppState:
    """Macht die zuletzt aufgezeichnete Listenaktion (Rename/Delete/Duplicate) rückgängig.

    Peek-dann-confirm: die Umkehrung wird zuerst versucht; nur bei Erfolg
    wandert der Eintrag über ``confirm_undo()`` auf den Redo-Stack. Schlägt
    die Umkehrung fehl (z. B. Pfadkollision), bleibt der Stack unverändert,
    damit der Nutzer den Konflikt auflösen und erneut Undo versuchen kann.

    Args:
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History, Listen-History).
    """
    action = ctx.list_history.peek_undo()
    if action is None:
        return dataclasses.replace(state, status_message="Nichts rückgängig zu machen")

    if isinstance(action, DeletePlanAction):
        if _plan_exists(ctx, action.path):
            return dataclasses.replace(
                state, status_message=f"Datei existiert bereits, kann nicht wiederhergestellt werden: {action.path.name}"
            )
        try:
            ctx.plan_repository.save_plan(action.plan, action.path)
        except Exception:
            _log.exception("handle_undo: restore of deleted plan failed for %s", action.path)
            return dataclasses.replace(state, status_message="Fehler beim Wiederherstellen")
        status = "Löschen rückgängig gemacht"

    elif isinstance(action, DuplicatePlanAction):
        try:
            ctx.plan_repository.delete_plan(action.path)
        except Exception:
            _log.exception("handle_undo: removing duplicate failed for %s", action.path)
            return dataclasses.replace(state, status_message="Fehler beim Rückgängigmachen des Duplikats")
        if ctx.history.plan_path == action.path:
            ctx.history.discard()
        status = "Duplizieren rückgängig gemacht"

    else:  # RenamePlanAction
        if action.before_path != action.after_path and _plan_exists(ctx, action.before_path):
            return dataclasses.replace(
                state,
                status_message=f"Datei existiert bereits, kann nicht wiederhergestellt werden: {action.before_path.name}",
            )
        try:
            ctx.plan_repository.rename_plan(action.after_path, action.before_name)
        except Exception:
            _log.exception("handle_undo: reverting rename failed for %s", action.after_path)
            return dataclasses.replace(state, status_message="Fehler beim Rückgängigmachen der Umbenennung")
        if ctx.history.plan_path == action.after_path:
            ctx.history.rename(action.before_path)
        status = "Umbenennen rückgängig gemacht"

    ctx.list_history.confirm_undo()
    can_undo, can_redo = _list_history_flags(ctx)
    plan_list = _refresh_plan_list(state, ctx)
    return dataclasses.replace(
        state, plan_list=plan_list, can_undo=can_undo, can_redo=can_redo, status_message=status
    )


def _apply_list_redo(state: AppState, ctx: HandlerContext) -> AppState:
    """Wiederholt die zuletzt rückgängig gemachte Listenaktion (Rename/Delete/Duplicate).

    Spiegelbild von ``_apply_list_undo``: gleiches Peek-dann-confirm-Muster.
    Ein Redo eines Duplicate stellt exakt den beim ursprünglichen Duplizieren
    entstandenen Snapshot wieder her (kein erneuter Aufruf der generischen
    Duplicate-Operation, die z. B. eine neue ``plan_id`` erzeugen würde).

    Args:
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History, Listen-History).
    """
    action = ctx.list_history.peek_redo()
    if action is None:
        return dataclasses.replace(state, status_message="Nichts wiederherzustellen")

    if isinstance(action, DeletePlanAction):
        try:
            ctx.plan_repository.delete_plan(action.path)
        except Exception:
            _log.exception("handle_redo: re-deleting plan failed for %s", action.path)
            return dataclasses.replace(state, status_message="Fehler beim Wiederholen des Löschens")
        if ctx.history.plan_path == action.path:
            ctx.history.discard()
        status = "Löschen wiederholt"

    elif isinstance(action, DuplicatePlanAction):
        if _plan_exists(ctx, action.path):
            return dataclasses.replace(
                state, status_message=f"Datei existiert bereits, kann nicht wiederhergestellt werden: {action.path.name}"
            )
        try:
            ctx.plan_repository.save_plan(action.plan, action.path)
        except Exception:
            _log.exception("handle_redo: recreating duplicate failed for %s", action.path)
            return dataclasses.replace(state, status_message="Fehler beim Wiederholen des Duplizierens")
        status = "Duplizieren wiederholt"

    else:  # RenamePlanAction
        if action.before_path != action.after_path and _plan_exists(ctx, action.after_path):
            return dataclasses.replace(
                state,
                status_message=f"Datei existiert bereits, kann nicht wiederhergestellt werden: {action.after_path.name}",
            )
        try:
            ctx.plan_repository.rename_plan(action.before_path, action.after_name)
        except Exception:
            _log.exception("handle_redo: reapplying rename failed for %s", action.before_path)
            return dataclasses.replace(state, status_message="Fehler beim Wiederholen der Umbenennung")
        if ctx.history.plan_path == action.before_path:
            ctx.history.rename(action.after_path)
        status = "Umbenennen wiederholt"

    ctx.list_history.confirm_redo()
    can_undo, can_redo = _list_history_flags(ctx)
    plan_list = _refresh_plan_list(state, ctx)
    return dataclasses.replace(
        state, plan_list=plan_list, can_undo=can_undo, can_redo=can_redo, status_message=status
    )


def handle_undo(intent: UndoIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Macht *intent.steps* Planänderungen rückgängig und persistiert den wiederhergestellten Plan.

    Ist kein Plan geöffnet (Listenansicht), operiert Undo stattdessen auf
    ``ctx.list_history`` (Rename/Delete/Duplicate von Plandateien) statt auf
    dem Raster-Verlauf des geöffneten Plans — siehe ``_apply_list_undo``.

    Args:
        intent: Anzahl der rückgängig zu machenden Schritte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return _apply_list_undo(state, ctx)
    restored = ctx.history.undo(intent.steps)
    if restored is None:
        return dataclasses.replace(state, status_message="Nichts rückgängig zu machen")
    try:
        ctx.plan_repository.save_plan(restored, state.current_plan_path)
    except Exception:
        _log.exception("handle_undo: save failed")
    return dataclasses.replace(
        state,
        current_plan=restored,
        can_undo=_can_undo(ctx),
        can_redo=_can_redo(ctx),
        status_message="Rückgängig",
    )


def handle_redo(intent: RedoIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Stellt *intent.steps* zuvor rückgängig gemachte Planänderungen wieder her und persistiert sie.

    Ist kein Plan geöffnet (Listenansicht), operiert Redo stattdessen auf
    ``ctx.list_history`` — siehe ``_apply_list_redo``.

    Args:
        intent: Anzahl der wiederherzustellenden Schritte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return _apply_list_redo(state, ctx)
    restored = ctx.history.redo(intent.steps)
    if restored is None:
        return dataclasses.replace(state, status_message="Nichts wiederherzustellen")
    try:
        ctx.plan_repository.save_plan(restored, state.current_plan_path)
    except Exception:
        _log.exception("handle_redo: save failed")
    return dataclasses.replace(
        state,
        current_plan=restored,
        can_undo=_can_undo(ctx),
        can_redo=_can_redo(ctx),
        status_message="Wiederhergestellt",
    )


def handle_copy_selection(intent: CopySelectionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Kopiert die Schüler in ``intent.cells`` in ``ctx.clipboard``.

    Reine Zwischenablage-Operation: verändert weder den Plan noch die
    History, es wird auch nichts gespeichert — nur ``ctx.clipboard`` wird
    befüllt (s. ``app/core/domain/student_clipboard.py``).

    Args:
        intent: Rasterzellen der aktuellen Selektion.
        state: Aktueller AppState.
        ctx: Handler-Kontext (liefert ``ctx.clipboard``).
    """
    if state.current_plan is None:
        return state
    count = ctx.clipboard.copy_from_plan(state.current_plan, list(intent.cells))
    if count == 0:
        return dataclasses.replace(state, status_message="Nichts zum Kopieren ausgewählt")
    return dataclasses.replace(state, status_message=f"{count} Schüler kopiert")


def handle_cut_selection(intent: CutSelectionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Markiert die Schüler in ``intent.cells`` zum Verschieben in ``ctx.clipboard``.

    Löscht noch nichts aus dem Plan — die tatsächliche Verschiebung erfolgt
    erst bei ``PasteSelectionIntent``. Wie ``handle_copy_selection`` rein eine
    Zwischenablage-Operation ohne History-/Speicher-Effekt.

    Args:
        intent: Rasterzellen der aktuellen Selektion.
        state: Aktueller AppState.
        ctx: Handler-Kontext (liefert ``ctx.clipboard``).
    """
    if state.current_plan is None:
        return state
    count = ctx.clipboard.mark_for_cut(state.current_plan, list(intent.cells))
    if count == 0:
        return dataclasses.replace(state, status_message="Nichts zum Ausschneiden ausgewählt")
    return dataclasses.replace(state, status_message=f"{count} Schüler zum Verschieben markiert")


def handle_paste_selection(intent: PasteSelectionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Fügt den Inhalt von ``ctx.clipboard`` ab der Zielzelle in den Plan ein.

    Bei zuvor ausgeschnittenen Schülern entspricht dies einer echten
    Verschiebung (``StudentId`` und Dokumentationshistorie bleiben erhalten);
    bei kopierten Schülern erhält jede eingefügte Kopie eine neue
    ``StudentId`` ohne Dokumentationshistorie. Zeichnet einen History-Eintrag
    auf und speichert nur, wenn tatsächlich etwas eingefügt wurde.

    Args:
        intent: Ziel-Rasterkoordinaten der linken oberen Einfüge-Ankerzelle.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History, Clipboard).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    if not ctx.clipboard.has_content():
        return dataclasses.replace(state, status_message="Zwischenablage ist leer")

    next_plan, pasted, teacher_conflict = ctx.clipboard.paste_into_plan(
        state.current_plan, intent.target_x, intent.target_y
    )
    if pasted == 0:
        message = "Lehrertisch blockiert das Einfügen" if teacher_conflict else "Nichts eingefügt"
        return dataclasses.replace(state, status_message=message)

    _record_and_save(next_plan, state.current_plan_path, "clipboard.paste", ctx)
    message = f"{pasted} Schüler eingefügt"
    if teacher_conflict:
        message += " (Lehrertisch übersprungen)"
    return _with_plan(state, next_plan, ctx, status=message)
