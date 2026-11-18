"""Reine Usecases für Änderungen am programmweiten Katalog (Symbole und Kompetenzen).

Jede Funktion bekommt den aktuellen Katalog als Tupel und gibt einen neuen
zurück; gespeichert wird im Handler über das ``SymbolCatalogRepository``. Die
Regeln stehen allein in ``core/domain/catalog_validation.py``; Verstöße werfen
``CatalogValidationError`` (die GUI prüft vorher, ein Fehler hier ist ein
Programmfehler). Programmweite Änderungen sind bewusst nicht Teil der
Plan-History (kein Rückgängig).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.core.domain.catalog_validation import (
    CatalogValidationError,
    validate_active,
    validate_catalog_name,
    validate_catalog_shortcut,
    validate_competence_fields,
    validate_competence_links,
    validate_new_glyph,
)
from app.core.domain.symbol_catalog import Competence, SymbolDefinition, slugify
from app.core.domain.symbol_renames import LEGACY_SYMBOL_RENAMES

USER_COMPETENCE_PREFIX = "eigen."


def _competence_index(competences: Sequence[Competence]) -> dict[str, Competence]:
    """Kompetenzen nach ID.

    Args:
        competences: Alle Kompetenzen.
    """
    return {competence.id: competence for competence in competences}


def update_symbol(
    catalog: Sequence[SymbolDefinition],
    competences: Sequence[Competence],
    key: str,
    name: str,
    shortcut: str,
    active: bool,
    competence_ids: Sequence[str],
) -> tuple[SymbolDefinition, ...]:
    """Ändert Name, Kürzel, Aktiv-Zustand und (bei Diagnosesymbolen) die Standard-Kompetenzen.

    Der Schlüssel bleibt unverändert, gespeicherte Beobachtungen behalten ihren Bezug.

    Args:
        catalog: Programmweiter Katalog.
        competences: Alle Kompetenzen.
        key: Schlüssel des Symbols.
        name: Neuer Anzeigename.
        shortcut: Neues Kürzel (roh, leer = keines).
        active: Neuer Aktiv-Zustand.
        competence_ids: Neue Standard-Kompetenzen (nur Diagnosesymbole).

    Raises:
        CatalogValidationError: Regelverstoß oder unbekannter Schlüssel.
    """
    current = next((definition for definition in catalog if definition.key == key), None)
    if current is None:
        raise CatalogValidationError(f"Unbekanntes Symbol: {key}")
    updated = replace(
        current,
        name=validate_catalog_name(name, key, catalog),
        shortcut=validate_catalog_shortcut(shortcut, key, catalog),
        active=validate_active(current, active),
    )
    if current.role == "diagnostic":
        updated = replace(updated, competence_ids=validate_competence_links(competence_ids, _competence_index(competences)))
    return tuple(updated if definition.key == key else definition for definition in catalog)


def new_symbol_key(name: str, catalog: Sequence[SymbolDefinition]) -> str:
    """Stabiler Schlüssel für ein neues Symbol: der Name, bei Kollision mit Zähler.

    Kollidieren darf er weder mit vorhandenen Schlüsseln noch mit früheren
    Schlüsseln aus ``LEGACY_SYMBOL_RENAMES`` (die würden beim Laden umgedeutet).

    Args:
        name: Geprüfter Anzeigename.
        catalog: Programmweiter Katalog.
    """
    taken = {definition.key.lower() for definition in catalog} | {old.lower() for old in LEGACY_SYMBOL_RENAMES}
    candidate, number = name, 2
    while candidate.lower() in taken:
        candidate, number = f"{name} ({number})", number + 1
    return candidate


def add_symbol(
    catalog: Sequence[SymbolDefinition],
    competences: Sequence[Competence],
    name: str,
    codepoint: str,
    shortcut: str,
    competence_ids: Sequence[str],
) -> tuple[tuple[SymbolDefinition, ...], str]:
    """Legt ein neues programmweites Diagnosesymbol an (am Ende der Diagnosesymbole).

    Args:
        catalog: Programmweiter Katalog.
        competences: Alle Kompetenzen.
        name: Anzeigename.
        codepoint: Zeichen aus ``GLYPH_PALETTE``.
        shortcut: Kürzel (roh, leer = keines).
        competence_ids: Verknüpfte Kompetenzen (mindestens eine).

    Returns:
        ``(neuer Katalog, Schlüssel des neuen Symbols)``.

    Raises:
        CatalogValidationError: Regelverstoß.
    """
    clean_name = validate_catalog_name(name, None, catalog)
    definition = SymbolDefinition(
        key=new_symbol_key(clean_name, catalog),
        name=clean_name,
        glyph=validate_new_glyph(codepoint, catalog),
        shortcut=validate_catalog_shortcut(shortcut, None, catalog),
        competence_ids=validate_competence_links(competence_ids, _competence_index(competences)),
    )
    position = max((i + 1 for i, d in enumerate(catalog) if d.role == "diagnostic"), default=0)
    items = list(catalog)
    items.insert(position, definition)
    return tuple(items), definition.key


def update_competence(
    competences: Sequence[Competence], competence_id: str, name: str, group: str, levels: Sequence[str]
) -> tuple[Competence, ...]:
    """Ändert Name, Gruppe und Stufentexte einer Kompetenz (die ID bleibt).

    Args:
        competences: Alle Kompetenzen.
        competence_id: ID der Kompetenz.
        name: Neuer Name.
        group: Neue Gruppe.
        levels: Neue Stufentexte ``(eins, zwei, drei)``.

    Raises:
        CatalogValidationError: Regelverstoß oder unbekannte ID.
    """
    if competence_id not in _competence_index(competences):
        raise CatalogValidationError(f"Unbekannte Kompetenz: {competence_id}")
    clean_name, clean_group, texts = validate_competence_fields(name, group, levels, competence_id, competences)
    updated = Competence(id=competence_id, name=clean_name, group=clean_group, levels=texts)
    return tuple(updated if competence.id == competence_id else competence for competence in competences)


def add_competence(
    competences: Sequence[Competence], name: str, group: str, levels: Sequence[str]
) -> tuple[tuple[Competence, ...], str]:
    """Legt eine neue Kompetenz an (ID ``eigen.<name>``, bei Kollision mit Zähler).

    Args:
        competences: Alle Kompetenzen.
        name: Name.
        group: Gruppe.
        levels: Stufentexte ``(eins, zwei, drei)``.

    Returns:
        ``(neue Kompetenzliste, ID der neuen Kompetenz)``.

    Raises:
        CatalogValidationError: Regelverstoß.
    """
    clean_name, clean_group, texts = validate_competence_fields(name, group, levels, None, competences)
    taken = set(_competence_index(competences))
    base = USER_COMPETENCE_PREFIX + slugify(clean_name)
    competence_id, number = base, 2
    while competence_id in taken:
        competence_id, number = f"{base}_{number}", number + 1
    created = Competence(id=competence_id, name=clean_name, group=clean_group, levels=texts)
    return (*competences, created), competence_id
