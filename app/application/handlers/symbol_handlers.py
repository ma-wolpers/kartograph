from __future__ import annotations

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save, _with_plan
from app.core.intents.symbol_intents import (
    RecordDocumentationSymbolIntent,
    ToggleDiagnosticSymbolIntent,
)
from app.core.usecases.v4.symbol_usecases import record_symbol, toggle_diagnostic_symbol


def handle_toggle_diagnostic_symbol(
    intent: ToggleDiagnosticSymbolIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Schaltet ein Diagnose-Symbol im Schülerprofil um (unabhängig von der Dokumentations-Historie).

    Args:
        intent: Schüler-ID und umzuschaltendes Symbol.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = toggle_diagnostic_symbol(state.current_plan, intent.student_id, intent.symbol)
    _record_and_save(next_plan, state.current_plan_path, "symbol.diagnostic.toggle", ctx)
    return _with_plan(state, next_plan, ctx)


def handle_record_documentation_symbol(
    intent: RecordDocumentationSymbolIntent, state: AppState, ctx: HandlerContext
) -> AppState:
    """Trägt die Symbolstärke aus *intent* für den Schüler an diesem Datum in die Dokumentation ein (0 = löschen).

    Args:
        intent: Schüler-ID, Datum, Symbol und einzutragende Stärke.
        state: Aktueller AppState.
        ctx: Handler-Kontext (Repository, History).
    """
    if state.current_plan is None or state.current_plan_path is None:
        return state
    next_plan = record_symbol(
        state.current_plan, intent.student_id, intent.date, intent.symbol, intent.strength
    )
    _record_and_save(next_plan, state.current_plan_path, "symbol.doc.record", ctx)
    return _with_plan(state, next_plan, ctx)
