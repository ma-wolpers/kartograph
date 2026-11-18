"""Intents für programmweite Katalogänderungen (Dialog „Symbole und Kompetenzen“).

Wirken auf alle Pläne und werden sofort in ``config/symbols.json`` bzw.
``config/competences.json`` gespeichert; sie sind nicht Teil der
Plan-History (kein Rückgängig).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.intents.base import Intent


@dataclass(frozen=True)
class UpdateCatalogSymbolIntent(Intent):
    """Ändert Name, Kürzel, Aktiv-Zustand und Standard-Kompetenzen eines Katalogsymbols."""

    key: str
    name: str
    shortcut: str
    active: bool
    competence_ids: tuple[str, ...]


@dataclass(frozen=True)
class AddCatalogSymbolIntent(Intent):
    """Legt ein neues programmweites Diagnosesymbol an."""

    name: str
    codepoint: str
    shortcut: str
    competence_ids: tuple[str, ...]


@dataclass(frozen=True)
class UpdateCompetenceIntent(Intent):
    """Ändert Name, Gruppe und Stufentexte ``(eins, zwei, drei)`` einer Kompetenz."""

    competence_id: str
    name: str
    group: str
    levels: tuple[str, str, str]


@dataclass(frozen=True)
class AddCompetenceIntent(Intent):
    """Legt eine neue Kompetenz an."""

    name: str
    group: str
    levels: tuple[str, str, str]
