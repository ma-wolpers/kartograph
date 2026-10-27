"""Optionen und Rahmenlogik der Sitzplan-Live-Vorschau (rein, ohne GUI).

Die Vorschau zeigt Farbmarkierungen als Rahmen um den Tisch:

- **Staffelung an:** alle gewählten Farben eines Tisches als konzentrische
  Ringe, Farbe 1 (erste in Palettenreihenfolge) ganz innen, die höchste
  ganz außen.
- **Staffelung aus:** nur ein Ring in der höchsten gewählten Farbe.

Die Farbnummerierung ist die Palettenreihenfolge (``color_order``); hier
wird nichts über einzelne Farben hart kodiert.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.core.domain.color_order import order_color_keys
from app.core.domain.seat_orientation import TEACHER_TOP

Point = tuple[float, float]

MAX_FRAME_FRACTION = 0.6
"""Höchstens dieser Anteil des Inkreisradius darf von Rahmen belegt sein (Platz für den Namen)."""


@dataclass(frozen=True)
class PreviewOptions:
    """Einstellungen einer Sitzplan-Vorschau.

    Die Defaults sind die Vorbelegung des Dialogs, wenn noch keine Vorschau
    offen ist (Entscheidung der Nutzerin): Lehrertisch oben, keine Farben,
    Staffelung an (wirkt erst, sobald Farben gewählt sind).

    Attributes:
        orientation: Ansicht-Schlüssel aus ``seat_orientation.ORIENTATION_MODES``.
        selected_colors: Explizit gewählte Farbschlüssel. Später neu
            vergebene Farben sind nicht enthalten und bleiben ausgeblendet,
            bis sie im Dialog angehakt werden.
        staggered: Farbstaffelung (alle Ringe) statt nur höchster Farbe.
    """

    orientation: str = TEACHER_TOP
    selected_colors: frozenset[str] = frozenset()
    staggered: bool = True


def selectable_color_keys(used_tags: Iterable[str], color_order: Sequence[str]) -> list[str]:
    """Gibt die im Dialog wählbaren Farben zurück: vergeben und in der Palette bekannt.

    Schlüssel ohne Palettenelement (etwa aus älteren Dateien) haben keine
    Farbe zum Zeichnen und werden deshalb nicht angeboten.

    Args:
        used_tags: Im Plan vergebene Farbschlüssel (``color_usecases.used_color_tags``).
        color_order: Palettenreihenfolge (``color_order.palette_order``).

    Returns:
        Wählbare Schlüssel in Palettenreihenfolge.
    """
    known = set(color_order)
    return [key for key in order_color_keys(used_tags, color_order) if key in known]


def frame_colors_outer_to_inner(
    color_tags: Iterable[str], color_order: Sequence[str], options: PreviewOptions
) -> list[str]:
    """Bestimmt die Rahmenfarben eines Tisches, von außen nach innen.

    Beispiel bei Palette ``gelb(1), orange(2), rot(3)`` und Tisch mit
    ``{gelb, rot}``, beide gewählt: gestaffelt ``["rot", "gelb"]`` (rot außen,
    gelb innen), ungestaffelt ``["rot"]``.

    Args:
        color_tags: Farbschlüssel des Tisches (beliebige Reihenfolge).
        color_order: Palettenreihenfolge.
        options: Vorschau-Einstellungen (Auswahl und Staffelung).

    Returns:
        Farbschlüssel, Index 0 = äußerster Ring; leer, wenn nichts zu zeichnen ist.
    """
    chosen = [key for key in order_color_keys(color_tags, color_order) if key in options.selected_colors]
    if not chosen:
        return []
    if not options.staggered:
        return [chosen[-1]]
    return list(reversed(chosen))


def _signed_area(points: Sequence[Point]) -> float:
    """Doppelte vorzeichenbehaftete Fläche (Shoelace); positiv bei Gegenuhrzeigersinn in y-oben-Koordinaten.

    Args:
        points: Polygon-Eckpunkte in Reihenfolge.
    """
    return sum(
        points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )


def _edge_lines(points: Sequence[Point], distance: float) -> list[tuple[Point, Point]]:
    """Verschiebt jede Kante um *distance* nach innen; liefert je Kante (Punkt, Richtung).

    Args:
        points: Konvexes Polygon.
        distance: Verschiebung nach innen (gleiche Einheit wie die Punkte).
    """
    sign = 1.0 if _signed_area(points) > 0 else -1.0
    lines = []
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / length * sign, dx / length * sign  # Normale zur Polygon-Innenseite
        lines.append(((x1 + nx * distance, y1 + ny * distance), (dx, dy)))
    return lines


def _intersect(a: tuple[Point, Point], b: tuple[Point, Point]) -> Point:
    """Schnittpunkt zweier Geraden in Punkt-Richtungs-Form; bei Parallelen der Punkt von *b*.

    Args:
        a: Erste Gerade ``((px, py), (dx, dy))``.
        b: Zweite Gerade.
    """
    (px, py), (dx, dy) = a
    (qx, qy), (ex, ey) = b
    denom = dx * ey - dy * ex
    if abs(denom) < 1e-12:
        return (qx, qy)
    t = ((qx - px) * ey - (qy - py) * ex) / denom
    return (px + t * dx, py + t * dy)


def inset_convex_polygon(points: Sequence[Point], distance: float) -> list[Point]:
    """Verkleinert ein konvexes Polygon, indem jede Kante um *distance* parallel nach innen wandert.

    Anders als ein Skalieren zum Mittelpunkt bleibt der Abstand zu allen
    Kanten gleich. So sind Rahmenringe auch an rotierten, nicht quadratischen
    Tischen überall gleich breit.

    Args:
        points: Eckpunkte eines konvexen Polygons (beliebiger Umlaufsinn).
        distance: Abstand nach innen; muss kleiner als der Inkreisradius sein.

    Returns:
        Eckpunkte des verkleinerten Polygons, gleiche Anzahl und Reihenfolge.
    """
    lines = _edge_lines(points, distance)
    return [_intersect(lines[i - 1], lines[i]) for i in range(len(lines))]


def inradius(points: Sequence[Point]) -> float:
    """Kleinster Abstand vom Schwerpunkt der Ecken zu einer Kante (für Rechtecke: halbe kurze Seite).

    Args:
        points: Konvexes Polygon.
    """
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    distances = []
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1.0
        distances.append(abs((x2 - x1) * (y1 - cy) - (x1 - cx) * (y2 - y1)) / length)
    return min(distances)


def frame_rings(points: Sequence[Point], count: int, preferred_width: float) -> tuple[float, list[list[Point]]]:
    """Berechnet Breite und Mittellinien-Polygone für *count* konzentrische Rahmenringe.

    Ring ``i`` (0 = außen) liegt mit seiner Mittellinie bei ``(i + 0.5) * width``
    innerhalb der Tischkante, Ringe schließen also lückenlos aneinander an. Die
    Breite wird bei vielen Ringen verkleinert, sodass alle zusammen höchstens
    ``MAX_FRAME_FRACTION`` des Inkreisradius belegen.

    Args:
        points: Tischpolygon (konvex), z. B. in Canvas-Pixeln.
        count: Anzahl Ringe.
        preferred_width: Wunschbreite eines Rings.

    Returns:
        ``(width, rings)``; ``rings[i]`` ist das Polygon der Mittellinie von Ring ``i``.
    """
    if count <= 0:
        return (0.0, [])
    width = min(preferred_width, MAX_FRAME_FRACTION * inradius(points) / count)
    return (width, [inset_convex_polygon(points, (i + 0.5) * width) for i in range(count)])
