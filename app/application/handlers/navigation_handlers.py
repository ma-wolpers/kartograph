from __future__ import annotations

import dataclasses

from app.application.app_state import AppState, InteractionMode
from app.application.handler_context import HandlerContext
from app.core.domain.plan_selection import RectSelection
from app.core.intents.navigation_intents import (
    ClearSelectionIntent,
    MoveSelectionIntent,
    SelectCellIntent,
)


def handle_select_cell(intent: SelectCellIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Setzt die Auswahl auf eine Einzelzelle und wechselt in den Raster-Interaktionsmodus.

    Args:
        intent: Ziel-Rasterkoordinaten der Einzelauswahl.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    sel = RectSelection(intent.x, intent.y)
    return dataclasses.replace(state, selection=sel, interaction_mode=InteractionMode.GRID)


def handle_move_selection(intent: MoveSelectionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Verschiebt die Auswahl relativ um (*dx*, *dy*); erweitert sie bei ``expand=True`` statt zu kollabieren.

    Klemmt nicht auf Canvas-Grenzen — das übernimmt die GUI vor dem Dispatch
    (Canvas-Radius ist eine Settings-/GUI-Größe, die der Handler nicht kennt).

    Args:
        intent: Relativer Versatz (*dx*, *dy*) und ob die Auswahl erweitert
            (statt auf eine Einzelzelle kollabiert) werden soll.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    if intent.expand:
        sel = RectSelection(state.selection.anchor_x, state.selection.anchor_y)
        sel.set_focus(
            state.selection.focus_x + intent.dx,
            state.selection.focus_y + intent.dy,
        )
    else:
        new_x = state.selection.focus_x + intent.dx
        new_y = state.selection.focus_y + intent.dy
        sel = RectSelection(new_x, new_y)
    return dataclasses.replace(state, selection=sel, interaction_mode=InteractionMode.GRID)


def handle_clear_selection(intent: ClearSelectionIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Wechselt vom Raster zurück in den Listen-Interaktionsmodus.

    Args:
        intent: Trägt keine Felder.
        state: Aktueller AppState.
        ctx: Handler-Kontext (von diesem Handler nicht benötigt).
    """
    return dataclasses.replace(state, interaction_mode=InteractionMode.LIST)
