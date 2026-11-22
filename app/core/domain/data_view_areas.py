"""Bereiche der Datenansicht und ihre Sichtbarkeitsregel (SSOT, reines Python).

Die Datenansicht zeigt nebeneinander: **Namen** (immer sichtbar) und die
ein-/ausblendbaren Bereiche **Doku** (Datumsspalten), **Notizen** und
**Noten**. Wunsch der Nutzerin (2026-11-17): neben den Namen höchstens zwei
weitere Bereiche gleichzeitig; ist das Maximum erreicht, ist der Schalter des
dritten ausgegraut. Die Auswahl wird pro Sitzplan gespeichert
(``KartographSettings.data_view_areas``, Schlüssel ``plan_id``) -- bewusst in
den Einstellungen statt in der Plandatei, damit Rückgängig/Wiederholen die
Ansicht nicht mit zurückdreht.

Alles, was Bereiche betrifft (Reihenfolge, Beschriftung, Grenze, Vorgabe,
Umschalten, Lesen aus den Einstellungen), steht nur hier; Tabelle, Toolbar und
Aktionssperren leiten sich daraus ab.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum


class DataArea(Enum):
    """Ein Bereich der Datenansicht; die Deklarationsreihenfolge ist die Anzeigereihenfolge (links → rechts)."""

    NAMEN = "namen"
    DOKU = "doku"
    NOTIZEN = "notizen"
    NOTEN = "noten"

    @property
    def label(self) -> str:
        """Sichtbarer Name des Bereichs (Schalter, Hinweise)."""
        return _LABELS[self]

    @property
    def toggleable(self) -> bool:
        """Lässt sich der Bereich ausblenden? (Nur die Namen sind immer da.)"""
        return self is not DataArea.NAMEN


_LABELS = {DataArea.NAMEN: "Namen", DataArea.DOKU: "Doku", DataArea.NOTIZEN: "Notizen", DataArea.NOTEN: "Noten"}

TOGGLEABLE_AREAS: tuple[DataArea, ...] = tuple(area for area in DataArea if area.toggleable)
MAX_VISIBLE_DATA_AREAS = 2
DEFAULT_VISIBLE_AREAS: tuple[DataArea, ...] = (DataArea.DOKU, DataArea.NOTEN)
"""Vorgabe für Pläne ohne gespeicherte Auswahl (= Ansicht vor Einführung der Bereiche)."""


def normalize_visible_areas(raw: Iterable[object]) -> tuple[DataArea, ...]:
    """Liest eine gespeicherte Bereichsliste tolerant ein.

    Unbekannte Werte und ``NAMEN`` entfallen, Dubletten zählen einmal, die
    Reihenfolge ist immer die Anzeigereihenfolge, und mehr als
    ``MAX_VISIBLE_DATA_AREAS`` Bereiche werden von rechts gekürzt.

    Args:
        raw: Werte wie ``["noten", "doku"]`` oder ``DataArea``-Elemente.

    Returns:
        Normalisierte sichtbare Bereiche, z. B. ``(DataArea.DOKU, DataArea.NOTEN)``.
    """
    keys = {item.value if isinstance(item, DataArea) else str(item).strip() for item in raw}
    return tuple(area for area in TOGGLEABLE_AREAS if area.value in keys)[:MAX_VISIBLE_DATA_AREAS]


def can_enable(area: DataArea, visible: tuple[DataArea, ...]) -> bool:
    """Darf *area* (zusätzlich) eingeblendet sein? Bereits sichtbare Bereiche immer.

    Args:
        area: Ein ausblendbarer Bereich.
        visible: Aktuell sichtbare Bereiche.

    Returns:
        ``False`` genau dann, wenn *area* unsichtbar ist und das Maximum erreicht ist
        (der Schalter wird dann ausgegraut).
    """
    return area in visible or len(visible) < MAX_VISIBLE_DATA_AREAS


def with_area(visible: tuple[DataArea, ...], area: DataArea, shown: bool) -> tuple[DataArea, ...]:
    """Blendet *area* ein oder aus; ein Einblenden über das Maximum hinaus ändert nichts.

    Args:
        visible: Aktuell sichtbare Bereiche.
        area: Umzuschaltender, ausblendbarer Bereich.
        shown: Gewünschter Zustand.

    Returns:
        Neue sichtbare Bereiche in Anzeigereihenfolge.
    """
    if shown and not can_enable(area, visible):
        return visible
    wanted = (set(visible) | {area}) if shown else (set(visible) - {area})
    return normalize_visible_areas(wanted)


def shown_areas(visible: tuple[DataArea, ...]) -> tuple[DataArea, ...]:
    """Alle angezeigten Bereiche links → rechts: die Namen, dann die sichtbaren.

    Args:
        visible: Sichtbare ausblendbare Bereiche.

    Returns:
        z. B. ``(NAMEN, NOTIZEN, NOTEN)``; höchstens ``1 + MAX_VISIBLE_DATA_AREAS`` Einträge.
    """
    return (DataArea.NAMEN, *normalize_visible_areas(visible))


def visible_areas_for(stored: Mapping[str, tuple[DataArea, ...]], plan_id: str) -> tuple[DataArea, ...]:
    """Sichtbare Bereiche eines Plans aus der gespeicherten Zuordnung.

    Ein gespeichertes leeres Tupel heißt "alles ausgeblendet" und ist etwas
    anderes als ein fehlender Eintrag (dann gilt ``DEFAULT_VISIBLE_AREAS``).

    Args:
        stored: ``plan_id`` → sichtbare Bereiche (``KartographSettings.data_view_areas``).
        plan_id: ID des Plans.

    Returns:
        Sichtbare Bereiche des Plans.
    """
    return stored[plan_id] if plan_id in stored else DEFAULT_VISIBLE_AREAS


def parse_stored_areas(payload: object) -> dict[str, tuple[DataArea, ...]]:
    """Liest die gespeicherte Zuordnung ``plan_id → Bereichsliste`` aus den rohen Einstellungen.

    Args:
        payload: Roher Wert, erwartet ``{"<plan_id>": ["doku", "noten"], ...}``.

    Returns:
        Bereinigte Zuordnung; Ungültiges entfällt still.
    """
    if not isinstance(payload, dict):
        return {}
    return {
        str(plan_id): normalize_visible_areas(areas)
        for plan_id, areas in payload.items()
        if str(plan_id).strip() and isinstance(areas, list)
    }


def dump_stored_areas(stored: Mapping[str, tuple[DataArea, ...]]) -> dict[str, list[str]]:
    """Wandelt die Zuordnung in die JSON-Form der Einstellungsdatei.

    Args:
        stored: ``plan_id`` → sichtbare Bereiche.

    Returns:
        ``{"<plan_id>": ["doku", "noten"], ...}``.
    """
    return {plan_id: [area.value for area in areas] for plan_id, areas in stored.items()}
