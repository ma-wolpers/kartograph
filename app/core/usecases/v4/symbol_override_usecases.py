"""Planbezogene Anpassung programmweiter Symbole (lokaler Name, lokale Kompetenzen).

Einzige Schreibstelle für ``SeatingPlan.symbol_overrides``. Normalisierung:
Ein Wert, der dem Programmstandard entspricht, wird als ``None`` („Standard
verwenden“) gespeichert; sind beide Felder ``None``, entfällt der Eintrag. So
überdeckt keine veraltete Kopie spätere programmweite Änderungen, und
„Programmstandard verwenden“ ist derselbe Aufruf mit ``(None, None)``.
"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy

from app.core.domain.catalog_validation import CatalogValidationError, validate_catalog_name, validate_competence_links
from app.core.domain.models_v4 import SeatingPlan, SymbolOverride
from app.core.domain.symbol_catalog import Competence, SymbolDefinition
from app.core.domain.symbol_view import apply_symbol_overrides


def set_symbol_override(
    plan: SeatingPlan,
    catalog: Sequence[SymbolDefinition],
    competences: Sequence[Competence],
    key: str,
    name: str | None,
    competence_ids: Sequence[str] | None,
) -> SeatingPlan:
    """Setzt, ändert oder entfernt die Anpassung des Symbols *key* in einer Plankopie.

    Args:
        plan: Offener Plan (wird nicht verändert).
        catalog: Programmweiter Katalog (``AppState.symbol_catalog``).
        competences: Alle Kompetenzen.
        key: Symbolschlüssel.
        name: Lokaler Name; leer/``None`` = Programmname.
        competence_ids: Lokale Kompetenzen; ``None`` = Programmstandard.

    Raises:
        CatalogValidationError: Unbekanntes Symbol, Name schon vergeben, keine
            oder unbekannte Kompetenz, Kompetenzen bei einem Doku-Symbol.
    """
    program = next((definition for definition in catalog if definition.key == key), None)
    if program is None:
        raise CatalogValidationError(f"Unbekanntes Symbol: {key}")
    local_name = None
    if name is not None and name.strip():
        others = apply_symbol_overrides(catalog, plan.symbol_overrides)
        local_name = validate_catalog_name(name, key, others)
        if local_name == program.name:
            local_name = None
    local_ids = None
    if competence_ids is not None:
        if program.role != "diagnostic":
            raise CatalogValidationError("Doku-Symbole haben keine Kompetenzen.")
        local_ids = validate_competence_links(competence_ids, {c.id: c for c in competences})
        if local_ids == program.competence_ids:
            local_ids = None
    next_plan = deepcopy(plan)
    if local_name is None and local_ids is None:
        next_plan.symbol_overrides.pop(key, None)
    else:
        next_plan.symbol_overrides[key] = SymbolOverride(name=local_name, competence_ids=local_ids)
    return next_plan
