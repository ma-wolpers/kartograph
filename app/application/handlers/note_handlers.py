"""Handler für allgemeine Notizen und eigene Notizspalten (Regeln in ``note_usecases``)."""

from __future__ import annotations

import dataclasses

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.intents.note_intents import AddNoteColumnIntent, DeleteNoteColumnIntent, SetNotesIntent, SetNoteValueIntent
from app.core.usecases.v4.note_usecases import add_note_column, delete_note_column, set_note_value, set_notes


@requires_open_plan
def handle_set_notes(
    intent: SetNotesIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Setzt die Notizen des Schülers aus *intent* und speichert den Plan.

    Nur laufendes Tippen (``intent.running_input``) wird mit dem vorigen Schritt
    derselben Person zusammengefasst; jede andere Änderung ist ein eigener Undo-Schritt.

    Args:
        intent: Schüler-ID und vollständige neue Liste der Notizen.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = set_notes(state.current_plan, intent.student_id, intent.notes)
    merge_key = ("notes", intent.student_id) if intent.running_input else None
    return _commit_plan_change(state, ctx, next_plan, merge_key=merge_key)


@requires_open_plan
def handle_add_note_column(intent: AddNoteColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt eine eigene Notizspalte an (ein Undo-Schritt).

    Args:
        intent: Titel und Typschlüssel.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    try:
        next_plan, _column_id = add_note_column(state.current_plan, intent.title, intent.kind)
    except ValueError:
        return dataclasses.replace(state, status_message="Unbekannter Spaltentyp")
    title = next_plan.note_columns[-1].title
    return _commit_plan_change(state, ctx, next_plan, status=f"Notizspalte „{title}“ angelegt")


@requires_open_plan
def handle_delete_note_column(intent: DeleteNoteColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht eine eigene Notizspalte samt Werten (ein Undo-Schritt).

    Args:
        intent: ID der Spalte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    return _commit_plan_change(state, ctx, delete_note_column(state.current_plan, intent.column_id))


@requires_open_plan
def handle_set_note_value(intent: SetNoteValueIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt einen Notizspalten-Wert (ein Undo-Schritt je Bestätigung); ungültige Eingaben meldet der Status.

    Args:
        intent: Person, Spalte, rohe Eingabe.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    try:
        next_plan = set_note_value(state.current_plan, intent.student_id, intent.column_id, intent.text)
    except ValueError:
        return dataclasses.replace(state, status_message=f"„{intent.text.strip()}“ passt nicht zum Spaltentyp")
    return _commit_plan_change(state, ctx, next_plan)
