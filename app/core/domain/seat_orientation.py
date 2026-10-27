"""Ansicht (Perspektive) und Welt-Bounding-Box für das Rendern von Sitzplatzgeometrien.

Einzige Quelle für
- die Ansicht-Schlüssel ``teacher_bottom``/``teacher_top`` samt Dialog-Labels
  (PDF-Export-Dialog und Sitzplan-Vorschau-Dialog bauen ihre Radiobuttons
  daraus),
- die 180°-Drehung der Weltkoordinaten für ``teacher_top``,
- die Bounding-Box aller Tischpolygone (inkl. ``max(0.1, …)``-Absicherung
  gegen Nulldivision bei entarteter Box).

Vorher steckten Drehung und Bounding-Box als Kopien in ``pdf_exporter.py``,
``_sitzplan_popup.py`` und ``student_png_renderer.py``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.core.domain.table_groups import SeatGeometryV4

Point = tuple[float, float]

TEACHER_BOTTOM = "teacher_bottom"
TEACHER_TOP = "teacher_top"

ORIENTATION_MODES: tuple[tuple[str, str], ...] = (
    (TEACHER_BOTTOM, "Lehrertisch unten"),
    (TEACHER_TOP, "Lehrertisch oben (180° Perspektive)"),
)
"""Erlaubte Ansicht-Schlüssel mit ihren Dialog-Labels, in Anzeigereihenfolge."""

_MIN_SPAN = 0.1
"""Mindestspanne der Bounding-Box je Achse (Schutz gegen Division durch 0)."""


@dataclass(frozen=True)
class OrientedSeat:
    """Eine Sitzplatzgeometrie, in die gewählte Ansicht gedreht.

    Attributes:
        polygon: Gedrehte Polygon-Eckpunkte in Weltkoordinaten.
        center: Gedrehter Tischmittelpunkt in Weltkoordinaten.
        geometry: Die ungedrehte Ursprungsgeometrie (für Schüler/Lehrer-Infos).
    """

    polygon: tuple[Point, ...]
    center: Point
    geometry: SeatGeometryV4


@dataclass(frozen=True)
class WorldBounds:
    """Achsenparallele Bounding-Box in Weltkoordinaten.

    Attributes:
        min_x: Kleinste x-Koordinate.
        min_y: Kleinste y-Koordinate.
        span_x: Breite, mindestens ``0.1``.
        span_y: Höhe, mindestens ``0.1``.
    """

    min_x: float
    min_y: float
    span_x: float
    span_y: float


def is_orientation_mode(mode: str) -> bool:
    """Prüft, ob *mode* ein bekannter Ansicht-Schlüssel ist.

    Args:
        mode: Zu prüfender Schlüssel, z. B. ``"teacher_top"``.
    """
    return any(key == mode for key, _label in ORIENTATION_MODES)


def orient_point(x: float, y: float, mode: str) -> Point:
    """Dreht einen Weltpunkt gemäß Ansicht.

    ``teacher_top`` dreht um 180° um den Ursprung (``(-x, -y)``). Eine
    Verschiebung ist nicht nötig, weil alle Renderer anschließend über
    ``world_bounds`` neu einpassen.

    Args:
        x: Welt-x.
        y: Welt-y.
        mode: Ansicht-Schlüssel; alles außer ``teacher_top`` lässt den Punkt unverändert.
    """
    if mode == TEACHER_TOP:
        return (-x, -y)
    return (x, y)


def orient_geometries(geometries: Iterable[SeatGeometryV4], mode: str) -> list[OrientedSeat]:
    """Dreht alle Sitzplatzgeometrien (Polygon und Mittelpunkt) in die Ansicht *mode*.

    Args:
        geometries: Ergebnis von ``build_seat_geometries_v4()``.
        mode: Ansicht-Schlüssel aus ``ORIENTATION_MODES``.

    Returns:
        Eine ``OrientedSeat`` je Eingabegeometrie, Reihenfolge erhalten.
    """
    return [
        OrientedSeat(
            polygon=tuple(orient_point(px, py, mode) for px, py in geometry.polygon),
            center=orient_point(geometry.center_x, geometry.center_y, mode),
            geometry=geometry,
        )
        for geometry in geometries
    ]


def world_bounds(polygons: Iterable[Sequence[Point]]) -> WorldBounds:
    """Berechnet die Bounding-Box über alle Eckpunkte aller *polygons*.

    Args:
        polygons: Polygone in Weltkoordinaten; mindestens ein Punkt muss
            vorhanden sein (``build_seat_geometries_v4()`` liefert immer den
            Lehrertisch).

    Returns:
        ``WorldBounds`` mit auf ``0.1`` nach unten begrenzten Spannen.

    Raises:
        ValueError: Wenn keine Punkte übergeben wurden.
    """
    points = [point for polygon in polygons for point in polygon]
    if not points:
        raise ValueError("Keine Punkte für die Bounding-Box")
    min_x = min(p[0] for p in points)
    min_y = min(p[1] for p in points)
    span_x = max(_MIN_SPAN, max(p[0] for p in points) - min_x)
    span_y = max(_MIN_SPAN, max(p[1] for p in points) - min_y)
    return WorldBounds(min_x=min_x, min_y=min_y, span_x=span_x, span_y=span_y)
