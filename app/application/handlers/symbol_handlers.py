from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _commit_plan_change, requires_open_plan
from app.core.intents.symbol_intents import (
    RecordDocumentationSymbolIntent,
    ToggleDiagnosticSymbolIntent,
)
from app.core.usecases.v4.symbol_usecases import record_symbol, toggle_diagnostic_symbol


@requires_open_plan
def handle_toggle_diagnostic_symbol(
    intent: ToggleDiagnosticSymbolIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Schaltet ein Diagnose-Symbol um und trägt es am Datum ein, als ein Undo-Schritt.

    Args:
        intent: Schüler-ID, Datum des Doku-Eintrags und umzuschaltendes Symbol.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = toggle_diagnostic_symbol(state.current_plan, intent.student_id, intent.date, intent.symbol)
    return _commit_plan_change(state, ctx, next_plan)


@requires_open_plan
def handle_record_documentation_symbol(
    intent: RecordDocumentationSymbolIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Trägt die Symbolstärke aus *intent* für den Schüler an diesem Datum in die Dokumentation ein (0 = löschen).

    Args:
        intent: Schüler-ID, Datum, Symbol und einzutragende Stärke.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    next_plan = record_symbol(
        state.current_plan, intent.student_id, intent.date, intent.symbol, intent.strength
    )
    return _commit_plan_change(state, ctx, next_plan)
