"""Handler für die Symbol-Verwaltung des Plans: eigene Doku-Symbole und Anpassungen programmweiter Symbole.

Validierungsfehler aus den Usecases (``InvalidGlyphError``/
``InvalidShortcutError``) werden hier bewusst NICHT abgefangen: die GUI
validiert bereits vor dem Dispatch (siehe ``_mixin_symbol_management.py``),
ein Fehler, der trotzdem bis hierher durchkommt, ist ein Programmfehler und
soll sichtbar bleiben statt still geschluckt zu werden.
"""

from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.domain.custom_symbol_validation import reserved_symbol_letters
from app.core.intents.custom_symbol_intents import (
    AddCustomSymbolIntent,
    DeleteCustomSymbolIntent,
    SetSymbolOverrideIntent,
    UpdateCustomSymbolIntent,
)
from app.core.usecases.v4.custom_symbol_usecases import (
    add_custom_symbol,
    delete_custom_symbol,
    update_custom_symbol,
)
from app.core.usecases.v4.symbol_override_usecases import set_symbol_override


@requires_open_plan
def handle_add_custom_symbol(intent: AddCustomSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt ein neues eigenes Doku-Symbol an, speichert und schreibt History.

    Args:
        intent: Glyph, Bedeutung und rohes Tastenkürzel des neuen Symbols.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan, _symbol_id = add_custom_symbol(
        state.current_plan,
        intent.glyph,
        intent.meaning,
        intent.shortcut,
        reserved_symbol_letters(state.symbol_catalog),
    )
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_update_custom_symbol(intent: UpdateCustomSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Ändert ein bestehendes eigenes Doku-Symbol, speichert und schreibt History.

    Args:
        intent: ID des zu bearbeitenden Symbols sowie die neuen Feldwerte.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = update_custom_symbol(
        state.current_plan,
        intent.symbol_id,
        intent.glyph,
        intent.meaning,
        intent.shortcut,
        reserved_symbol_letters(state.symbol_catalog),
    )
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_delete_custom_symbol(intent: DeleteCustomSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Entfernt ein eigenes Doku-Symbol aus dem Katalog, speichert und schreibt History.

    Args:
        intent: ID des zu löschenden Symbols.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = delete_custom_symbol(state.current_plan, intent.symbol_id)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_set_symbol_override(intent: SetSymbolOverrideIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt oder entfernt die Plan-Anpassung eines Symbols, speichert und schreibt History.

    Args:
        intent: Symbolschlüssel, lokaler Name und lokale Kompetenzen (``None`` = Standard).
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = set_symbol_override(
        state.current_plan,
        state.symbol_catalog,
        state.competence_catalog,
        intent.symbol_key,
        intent.name,
        intent.competence_ids,
    )
    return _commit_plan_change(state, ctx, next_plan)
