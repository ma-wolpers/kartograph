"""Anordnung der Kästchen auf dem Gruppenblatt (reine Geometrie, kein ReportLab).

Regeln:

- feste Spaltenzahl je Blattausrichtung (``COLUMNS_BY_ORIENTATION``: 3 hochkant, 4 quer),
- Kästchen laufen zeilenweise von links nach rechts; die Zeilenhöhe ist die
  des höchsten Kästchens der Zeile,
- passt eine Zeile nicht mehr auf die Seite, beginnt eine neue Seite; ein
  Kästchen wird nie geteilt (die erste Seite hat unter der Überschrift weniger Platz).

Koordinaten in PDF-Punkten mit Ursprung unten links (wie ReportLab).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

COLUMNS_BY_ORIENTATION: dict[str, int] = {"portrait": 3, "landscape": 4}


@dataclass(frozen=True)
class BoxPlacement:
    """Platz eines Kästchens auf einer Seite.

    Attributes:
        index: Index des Kästchens in der Eingabe.
        left: Linke Kante.
        top: Obere Kante.
        width: Breite.
        height: Höhe.
    """

    index: int
    left: float
    top: float
    width: float
    height: float


def layout_group_boxes(
    box_heights: Sequence[float],
    page_size: tuple[float, float],
    *,
    columns: int,
    margin: float,
    gap: float,
    first_page_offset: float,
) -> list[list[BoxPlacement]]:
    """Verteilt Kästchen der Höhen *box_heights* auf Seiten.

    Args:
        box_heights: Benötigte Höhe je Kästchen (Zeichenreihenfolge).
        page_size: ``(Breite, Höhe)`` der Seite.
        columns: Kästchen je Zeile.
        margin: Seitenrand ringsum.
        gap: Abstand zwischen Kästchen (waagrecht und senkrecht).
        first_page_offset: Zusätzlicher Platz oben auf der ersten Seite (Überschrift).

    Returns:
        Eine Liste je Seite mit den Platzierungen; leer, wenn es keine Kästchen gibt.
    """
    page_w, page_h = page_size
    width = (page_w - 2 * margin - (columns - 1) * gap) / columns
    pages: list[list[BoxPlacement]] = []
    current: list[BoxPlacement] = []
    top = page_h - margin - first_page_offset
    for row_start in range(0, len(box_heights), columns):
        row = range(row_start, min(row_start + columns, len(box_heights)))
        row_height = max(box_heights[i] for i in row)
        if current and top - row_height < margin:
            pages.append(current)
            current, top = [], page_h - margin
        for column, index in enumerate(row):
            current.append(BoxPlacement(index, margin + column * (width + gap), top, width, row_height))
        top -= row_height + gap
    if current:
        pages.append(current)
    return pages
