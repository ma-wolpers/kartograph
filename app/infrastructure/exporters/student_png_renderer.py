"""Rendert transparente PNG-Miniaturkarten des Sitzplans, ein Bild je Schüler.

Reines Rendering ohne Datei-I/O: nimmt vorberechnete v4-Sitzplatzgeometrien
entgegen und gibt PNG-kodierte Bytes zurück. Das ZIP-Zusammenbauen liegt in
``student_png_zip_exporter.py``, die Dateinamens-Auflösung in
``app/core/domain/student_png_export.py``.

Koordinatensystem: Kartographs Weltkoordinaten (aus
``build_seat_geometries_v4()``) wachsen wie Pillow-Pixelkoordinaten nach
unten (top-left Ursprung) -- anders als der PDF-Export, der wegen
ReportLabs y-nach-oben-Konvention explizit invertieren muss, mappt
``GeometryTransform`` daher rein linear ohne Achsen-Umkehr. Siehe die
Verifikation im Architektur-Dokument bzw. Entwicklungslog für die Belege
(Live-Grid-Canvas ``_mixin_grid_render.py`` und Sitzplan-Popup
``_sitzplan_popup.py`` verwenden dasselbe ungespiegelte Mapping).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.domain.table_groups import SeatGeometryV4

TABLE_FILL_COLOR = "#FFFFFF"
TABLE_OUTLINE_COLOR = "#000000"
TEACHER_FILL_COLOR = "#FF8C00"
OWN_TABLE_FILL_COLOR = "#0057D8"

CONTENT_SIZE_PX = 320
"""Längere Kante der Tisch-Bounding-Box in Pixeln (vor Rand-Aufschlag)."""

MARGIN_PX = 14
"""Rand zusätzlich zur Content-Größe, auf allen vier Seiten des Bildes."""

SUPERSAMPLE_FACTOR = 4
"""Faktor, mit dem intern in höherer Auflösung gezeichnet wird, bevor auf
die Zielgröße herunterskaliert wird -- Pillows ImageDraw.polygon() glättet
Kanten sonst nicht selbst, ohne Supersampling wirken die kleinen
Kärtchen treppig."""

STUDENT_OUTLINE_WIDTH = 2
TEACHER_OUTLINE_WIDTH = 3


@dataclass(frozen=True)
class GeometryTransform:
    """Lineare Weltkoordinaten-zu-Pixel-Transformation für einen Export.

    Wird einmal pro Export über ``build_geometry_transform()`` berechnet
    und für jeden Schüler wiederverwendet, damit alle PNGs eines Exports
    dieselbe Bildgröße und denselben Maßstab teilen -- nur die Füllfarbe des
    jeweils eigenen Tisches wechselt zwischen den Bildern.
    """

    scale: float
    origin_x: float
    origin_y: float
    canvas_size: tuple[int, int]

    def to_pixel(self, wx: float, wy: float) -> tuple[float, float]:
        """Wandelt eine Weltkoordinate in eine Pixelkoordinate um.

        Reine lineare Abbildung ohne Achsen-Umkehr (siehe Moduldocstring):
        ``pixel = origin + welt * scale``.

        Args:
            wx: X-Weltkoordinate (z. B. ``geometry.center_x`` oder ein
                Polygon-Eckpunkt).
            wy: Y-Weltkoordinate.
        """
        return (self.origin_x + wx * self.scale, self.origin_y + wy * self.scale)


def build_geometry_transform(
    geometries: list[SeatGeometryV4],
    *,
    content_size_px: int = CONTENT_SIZE_PX,
    margin_px: int = MARGIN_PX,
) -> GeometryTransform:
    """Berechnet Skalierung, Ursprung und Bildgröße aus der Bounding-Box aller Tisch-Polygone.

    Formel (``span_x``/``span_y`` wie bei ``pdf_exporter.py`` und
    ``_sitzplan_popup.py`` über ``max(0.1, ...)`` gegen Nulldivision bei
    einer entarteten Bounding-Box abgesichert -- etabliertes Muster aus dem
    bestehenden PDF-/Vorschau-Rendering):

    - ``scale = content_size_px / max(span_x, span_y)``
    - ``content_w = span_x * scale`` (kleiner-gleich ``content_size_px``)
    - ``content_h = span_y * scale``
    - ``canvas_size = (round(content_w) + 2*margin_px, round(content_h) + 2*margin_px)``
    - ``origin_x = margin_px - min_x * scale``, analog für ``origin_y``

    Die längere Kante der Tisch-Bounding-Box wird also exakt auf
    ``content_size_px`` skaliert, die kürzere im selben Maßstab (das
    Seitenverhältnis des Klassenraums bleibt erhalten statt in ein Quadrat
    gepresst zu werden), und der Rand kommt danach auf allen vier Seiten
    zusätzlich oben drauf. Beispiel: Bounding-Box-Seitenverhältnis 2:1 ->
    Content 320x160px -> ``canvas_size = (348, 188)`` bei ``margin_px=14``.

    ``geometries`` ist laut ``build_seat_geometries_v4()`` nie leer (der
    Lehrertisch wird dort immer als erstes Element eingefügt), eine leere
    Liste wird hier daher nicht gesondert behandelt.

    Args:
        geometries: Vorberechnete Sitzplatzgeometrien (Lehrertisch + alle
            Schülerplätze) des zu exportierenden Plans.
        content_size_px: Zielgröße der längeren Bounding-Box-Kante in Pixeln.
        margin_px: Zusätzlicher Rand auf allen vier Seiten.
    """
    all_points = [point for geometry in geometries for point in geometry.polygon]
    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    span_x = max(0.1, max_x - min_x)
    span_y = max(0.1, max_y - min_y)

    scale = content_size_px / max(span_x, span_y)
    canvas_w = round(span_x * scale) + 2 * margin_px
    canvas_h = round(span_y * scale) + 2 * margin_px
    origin_x = margin_px - min_x * scale
    origin_y = margin_px - min_y * scale

    return GeometryTransform(scale=scale, origin_x=origin_x, origin_y=origin_y, canvas_size=(canvas_w, canvas_h))


def _desk_style(geometry: SeatGeometryV4, target_student_id: StudentId) -> tuple[str, int]:
    """Bestimmt Füllfarbe und Umrandungsbreite für einen einzelnen Tisch.

    Priorität (unzweideutig, da ``is_teacher=True`` in ``SeatGeometryV4``
    strukturell ``student=None`` impliziert -- ein Tisch kann nie
    gleichzeitig Lehrertisch und Ziel-Schüler-Tisch sein):

    1. Lehrertisch -> ``TEACHER_FILL_COLOR``, dickere Umrandung.
    2. Tisch von *target_student_id* -> ``OWN_TABLE_FILL_COLOR``.
    3. Alle anderen Tische -> ``TABLE_FILL_COLOR``.

    Args:
        geometry: Geometrie des zu zeichnenden Tisches.
        target_student_id: Schüler, dessen Kärtchen gerade gerendert wird.
    """
    if geometry.is_teacher:
        return TEACHER_FILL_COLOR, TEACHER_OUTLINE_WIDTH
    if geometry.student is not None and geometry.student.student_id == target_student_id:
        return OWN_TABLE_FILL_COLOR, STUDENT_OUTLINE_WIDTH
    return TABLE_FILL_COLOR, STUDENT_OUTLINE_WIDTH


def render_student_png(
    geometries: list[SeatGeometryV4],
    transform: GeometryTransform,
    target_student_id: StudentId,
) -> bytes:
    """Rendert die transparente PNG-Miniaturkarte für genau einen Schüler.

    Rein geometrisch: alle Tische als weiße, schwarz umrandete Kästen, der
    Lehrertisch orange, der Tisch von *target_student_id* kräftig blau --
    keine Namen, Noten, Symbole oder Legende (siehe ``_desk_style()`` für
    die Farbzuordnung).

    Zeichnet auf einer ``SUPERSAMPLE_FACTOR``-fach vergrößerten, vollständig
    transparenten RGBA-Fläche und skaliert danach mit
    ``Image.Resampling.LANCZOS`` auf ``transform.canvas_size`` herunter --
    Pillows Polygon-Zeichnung glättet Kanten sonst nicht selbst.

    Args:
        geometries: Vorberechnete Sitzplatzgeometrien des Plans (dieselbe
            Liste, aus der *transform* über ``build_geometry_transform()``
            berechnet wurde).
        transform: Gemeinsame Geometrie-zu-Pixel-Transformation für alle
            Kärtchen dieses Exports.
        target_student_id: Schüler, dessen eigener Tisch blau markiert wird.

    Returns:
        PNG-kodierte Bytes (Modus RGBA).

    Raises:
        RuntimeError: Wenn Pillow nicht installiert ist.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception as exc:
        raise RuntimeError("PNG-Export benoetigt Pillow (pip install Pillow).") from exc

    canvas_w, canvas_h = transform.canvas_size
    super_size = (canvas_w * SUPERSAMPLE_FACTOR, canvas_h * SUPERSAMPLE_FACTOR)
    image = Image.new("RGBA", super_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for geometry in geometries:
        fill_color, outline_width = _desk_style(geometry, target_student_id)
        polygon_px = [
            tuple(coord * SUPERSAMPLE_FACTOR for coord in transform.to_pixel(wx, wy))
            for wx, wy in geometry.polygon
        ]
        draw.polygon(
            polygon_px,
            fill=fill_color,
            outline=TABLE_OUTLINE_COLOR,
            width=outline_width * SUPERSAMPLE_FACTOR,
        )

    image = image.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
