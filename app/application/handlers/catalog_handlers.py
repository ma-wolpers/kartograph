"""Handler für programmweite Katalogänderungen (Symbole und Kompetenzen).

Jeder Handler wendet den reinen Usecase an, speichert beide Arbeitskopien über
``ctx.symbol_catalog_repository`` und ersetzt ``AppState.symbol_catalog`` bzw.
``competence_catalog``. Keine Plan-History: Die Änderung gilt für alle Pläne
und lässt sich nicht mit Strg+Z zurücknehmen (der Dialog sagt das).
Validierungsfehler werden wie bei den eigenen Symbolen nicht abgefangen — die
GUI prüft vor dem Dispatch mit denselben Regeln.
"""

from __future__ import annotations

from dataclasses import replace

from app.application.app_state import AppState
from app.application.handler_context import HandlerContext
from app.core.domain.symbol_catalog import Competence, SymbolDefinition
from app.core.intents.catalog_intents import (
    AddCatalogSymbolIntent,
    AddCompetenceIntent,
    UpdateCatalogSymbolIntent,
    UpdateCompetenceIntent,
)
from app.core.usecases.catalog_usecases import add_competence, add_symbol, update_competence, update_symbol


def _store(
    state: AppState,
    ctx: HandlerContext,
    symbols: tuple[SymbolDefinition, ...],
    competences: tuple[Competence, ...],
    message: str,
) -> AppState:
    """Speichert den neuen Katalog und gibt den Zustand mit ihm zurück (einzige Schreibstelle).

    Args:
        state: Aktueller Zustand.
        ctx: Handler-Kontext mit ``symbol_catalog_repository``.
        symbols: Neuer Symbolkatalog.
        competences: Neue Kompetenzliste.
        message: Statusmeldung.
    """
    ctx.symbol_catalog_repository.save(symbols, competences)
    return replace(state, symbol_catalog=symbols, competence_catalog=competences, status_message=message)


def handle_update_catalog_symbol(intent: UpdateCatalogSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Ändert ein Katalogsymbol programmweit.

    Args:
        intent: Schlüssel und neue Werte.
        state: Aktueller Zustand.
        ctx: Handler-Kontext.
    """
    symbols = update_symbol(state.symbol_catalog, state.competence_catalog, intent.key, intent.name,
                            intent.shortcut, intent.active, intent.competence_ids)
    return _store(state, ctx, symbols, state.competence_catalog, f"Symbol „{intent.name.strip()}“ gespeichert (alle Pläne)")


def handle_add_catalog_symbol(intent: AddCatalogSymbolIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt ein neues programmweites Symbol an.

    Args:
        intent: Name, Zeichen, Kürzel und Kompetenzen.
        state: Aktueller Zustand.
        ctx: Handler-Kontext.
    """
    symbols, _key = add_symbol(state.symbol_catalog, state.competence_catalog, intent.name, intent.codepoint,
                               intent.shortcut, intent.competence_ids)
    return _store(state, ctx, symbols, state.competence_catalog, f"Symbol „{intent.name.strip()}“ angelegt (alle Pläne)")


def handle_update_competence(intent: UpdateCompetenceIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Ändert eine Kompetenz programmweit.

    Args:
        intent: ID und neue Werte.
        state: Aktueller Zustand.
        ctx: Handler-Kontext.
    """
    competences = update_competence(state.competence_catalog, intent.competence_id, intent.name, intent.group, intent.levels)
    return _store(state, ctx, state.symbol_catalog, competences, f"Kompetenz „{intent.name.strip()}“ gespeichert (alle Pläne)")


def handle_add_competence(intent: AddCompetenceIntent, state: AppState, ctx: HandlerContext) -> AppState:
    """Legt eine neue Kompetenz an.

    Args:
        intent: Name, Gruppe und Stufentexte.
        state: Aktueller Zustand.
        ctx: Handler-Kontext.
    """
    competences, _cid = add_competence(state.competence_catalog, intent.name, intent.group, intent.levels)
    return _store(state, ctx, state.symbol_catalog, competences, f"Kompetenz „{intent.name.strip()}“ angelegt (alle Pläne)")
