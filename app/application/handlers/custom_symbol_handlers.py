"""Handler für die CRUD-Intents eigener Doku-Symbole.

Validierungsfehler aus den Usecases (``InvalidGlyphError``/
``InvalidShortcutError``) werden hier bewusst NICHT abgefangen: die GUI
validiert bereits vor dem Dispatch (siehe ``_mixin_symbol_management.py``),
ein Fehler, der trotzdem bis hierher durchkommt, ist ein Programmfehler und
soll sichtbar bleiben statt still geschluckt zu werden.
"""

from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.intents.custom_symbol_intents import (
    AddCustomSymbolIntent,
    DeleteCustomSymbolIntent,
    UpdateCustomSymbolIntent,
)
from app.core.usecases.v4.custom_symbol_usecases import (
    add_custom_symbol,
    delete_custom_symbol,
    update_custom_symbol,
)


def handle_add_custom_symbol(intent: AddCustomSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt ein neues eigenes Doku-Symbol an, speichert und schreibt History.

    Args:
        intent: Glyph, Bedeutung und rohes Tastenkürzel des neuen Symbols.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan, _symbol_id = add_custom_symbol(state.current_plan, intent.glyph, intent.meaning, intent.shortcut)
    _record_and_save(next_plan, state.current_plan_path, "custom_symbol.add", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_update_custom_symbol(intent: UpdateCustomSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Ändert ein bestehendes eigenes Doku-Symbol, speichert und schreibt History.

    Args:
        intent: ID des zu bearbeitenden Symbols sowie die neuen Feldwerte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = update_custom_symbol(
        state.current_plan, intent.symbol_id, intent.glyph, intent.meaning, intent.shortcut
    )
    _record_and_save(next_plan, state.current_plan_path, "custom_symbol.update", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_delete_custom_symbol(intent: DeleteCustomSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Entfernt ein eigenes Doku-Symbol aus dem Katalog, speichert und schreibt History.

    Args:
        intent: ID des zu löschenden Symbols.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = delete_custom_symbol(state.current_plan, intent.symbol_id)
    _record_and_save(next_plan, state.current_plan_path, "custom_symbol.delete", ctx)
    return _with_plan(state, next_plan, ctx)
