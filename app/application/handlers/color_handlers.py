"""Handler für Farbmarkierungen und Ja/Nein-Spalten (Regeln in ``color_usecases`` / ``flag_columns``)."""

from __future__ import annotations

import dataclasses

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.intents.color_intents import AddFlagColumnIntent, DeleteFlagColumnIntent, ToggleColorIntent
from app.core.usecases.v4.color_usecases import add_flag_column, delete_flag_column, toggle_color_tag


@requires_open_plan
def handle_toggle_color(intent: ToggleColorIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Schaltet den Farbpunkt aus *intent* beim Schüler um, speichert und schreibt History.

    Args:
        intent: Schüler-ID und umzuschaltender Farbschlüssel.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = toggle_color_tag(state.current_plan, intent.student_id, intent.color_key)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_add_flag_column(intent: AddFlagColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt eine Ja/Nein-Spalte an (ein Undo-Schritt); eine schon vergebene Farbe meldet der Status.

    Args:
        intent: Titel und freie Farbe (``None`` = farblos).
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    try:
        next_plan, _key = add_flag_column(state.current_plan, intent.title, intent.color_key)
    except ValueError:
        return dataclasses.replace(state, status_message="Diese Farbe ist schon vergeben")
    return _commit_plan_change(state, ctx, next_plan, status=f"Ja/Nein-Spalte „{intent.title.strip()}“ angelegt")


@requires_open_plan
def handle_delete_flag_column(intent: DeleteFlagColumnIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Löscht eine Ja/Nein-Spalte samt Markierungen (ein Undo-Schritt).

    Args:
        intent: Schlüssel der Spalte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    return _commit_plan_change(state, ctx, delete_flag_column(state.current_plan, intent.key))
