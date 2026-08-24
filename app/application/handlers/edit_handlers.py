from __future__ import annotations

import dataclasses
import logging

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _can_redo, _can_undo, _record_and_save, _refresh_plan_list, _with_plan
from app.core.intents.edit_intents import (
    CopySelectionIntent,
    CutSelectionIntent,
    PasteSelectionIntent,
    RedoIntent,
    UndoIntent,
)

_log = logging.getLogger("kartograph.handlers.edit")


def _undo_deleted_plan(state: AppState, ctx: HandlerContext) -> AppState:
    """Stellt den zuletzt gelöschten Plan wieder her, falls einer vorliegt.

    One-shot: bei Erfolg wird ``ctx.last_deleted_plan`` geleert, ein erneutes
    Undo hat dann nichts mehr rückgängig zu machen. Existiert am Zielpfad
    bereits wieder eine Datei (z. B. neu angelegter Plan mit gleichem Namen),
    wird nicht überschrieben und der Slot bleibt erhalten, damit der Nutzer
    den Konflikt auflösen und Undo erneut versuchen kann.

    Args:
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, zuletzt gelöschter Plan).
    """
    if ctx.last_deleted_plan is None:
        return dataclasses.replace(state, status_message="Nichts rückgängig zu machen")

    path, plan = ctx.last_deleted_plan
    try:
        ctx.plan_repository.load_plan(path)
    except Exception:
        pass
    else:
        return dataclasses.replace(
            state, status_message=f"Datei existiert bereits, kann nicht wiederhergestellt werden: {path.name}"
        )

    try:
        ctx.plan_repository.save_plan(plan, path)
    except Exception:
        _log.exception("handle_undo: restore of deleted plan failed for %s", path)
        return dataclasses.replace(state, status_message="Fehler beim Wiederherstellen")

    ctx.last_deleted_plan = None
    plan_list = _refresh_plan_list(state, ctx)
    return dataclasses.replace(
        state,
        plan_list=plan_list,
        can_undo=False,
        can_redo=False,
        status_message="Löschen rückgängig gemacht",
    )


def handle_undo(intent: UndoIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Macht *intent.steps* Planänderungen rückgängig und persistiert den wiederhergestellten Plan.

    Ist kein Plan geöffnet (Listenansicht) und wurde zuletzt ein Plan gelöscht,
    stellt Undo stattdessen diese Löschung wieder her (siehe
    ``ctx.last_deleted_plan``), statt einen Raster-Undo zu versuchen.

    Args:
        intent: Anzahl der rückgängig zu machenden Schritte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return _undo_deleted_plan(state, ctx)
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

    Args:
        intent: Anzahl der wiederherzustellenden Schritte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
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
