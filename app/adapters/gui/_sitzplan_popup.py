"""Sitzplan-Vorschau-Popup für Kartograph.

Zeigt den Sitzplan ohne Noten und Symbole, mit Farbmarkierungen als
Tischrahmen, und aktualisiert sich automatisch, wenn der Plan im Hauptfenster
geändert wird. Ansicht, Farbauswahl und Staffelung kommen als
``PreviewOptions`` aus dem Vorschau-Dialog (``_mixin_sitzplan_preview_dialog.py``);
die Rahmenlogik selbst liegt rein in ``app/core/domain/preview_color_frames.py``.
"""

from __future__ import annotations

from app.adapters.gui.ui_theme import kartograph_theme
from app.core.domain.color_order import PaletteEntryTuple, palette_by_key, palette_order
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.preview_color_frames import PreviewOptions, frame_colors_outer_to_inner, frame_rings
from app.core.domain.seat_orientation import orient_geometries, world_bounds
from app.core.domain.student_naming import compute_display_names
from app.core.domain.table_groups import build_seat_geometries_v4
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import on_resize, ui

_PADDING = 24
_FRAME_WIDTH_PER_CELL = 0.07
"""Wunschbreite eines Farbrings relativ zur Zellgröße (wird bei vielen Ringen gedeckelt)."""


class SitzplanPopup:
    """Vorschaufenster: Sitzplan ohne Noten und Symbole, Farben als Tischrahmen."""

    def __init__(
        self,
        parent,
        color_palette: list[PaletteEntryTuple],
        options: PreviewOptions,
        theme_key: str = "mono_day",
        name_format: str = "Vorname Nachname",
    ) -> None:
        """Erzeugt das Fenster samt Canvas; gezeichnet wird erst mit ``update()``.

        Args:
            parent: Elternfenster (Hauptfenster).
            color_palette: Die Palette des Hauptfensters (``COLOR_MARKER_PALETTE``);
                Reihenfolge und Hex-Werte werden daraus abgeleitet, nicht kopiert.
            options: Anfangseinstellungen aus dem Vorschau-Dialog.
            theme_key: Aktives Theme für Hintergrund-, Tisch- und Textfarben.
            name_format: Namensformat wie in Grid und PDF.
        """
        self._window = ui.Toplevel(parent)
        self._window.title("Sitzplan-Vorschau")
        self._window.geometry("860x640")
        self._theme_key = theme_key
        self._name_format = name_format
        self._disambiguate = False
        self._display_names: dict = {}
        self._plan: SeatingPlan | None = None
        self._options = options
        self._color_order = palette_order(color_palette)
        self._color_by_key = palette_by_key(color_palette)

        self._canvas = ui.Canvas(
            self._window,
            bg=kartograph_theme(theme_key)["bg_main"],
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)
        # within=True: wie frueher am Toplevel-Tag (auch das Canvas meldet seine Groesse).
        on_resize(self._window, lambda _event: self._window.after_idle(self._redraw), within=True)

    @property
    def window(self) -> ui.Toplevel:
        """Das Toplevel-Fenster der Vorschau (für Registrierung, Lift, Schließen)."""
        return self._window

    @property
    def options(self) -> PreviewOptions:
        """Die aktuell angezeigten Einstellungen (Vorbelegung für den nächsten Dialog)."""
        return self._options

    def set_options(self, options: PreviewOptions) -> None:
        """Übernimmt neue Einstellungen aus dem Dialog und zeichnet neu.

        Args:
            options: Ansicht, Farbauswahl und Staffelung.
        """
        self._options = options
        self._redraw()

    def update(self, plan: SeatingPlan | None, theme_key: str, name_format: str, disambiguate: bool = False) -> None:
        """Aktualisiert Plan, Theme und Namensformat, dann neu zeichnen.

        Args:
            plan: Aktueller Plan oder ``None`` (leere Vorschau).
            theme_key: Aktives Theme.
            name_format: Namensformat.
            disambiguate: Kollidierende Vornamen per Nachnamen-Präfix unterscheiden.
        """
        self._plan = plan
        self._theme_key = theme_key
        self._name_format = name_format
        self._disambiguate = disambiguate
        self._display_names = (
            compute_display_names(plan.classroom.students, name_format, disambiguate) if plan is not None else {}
        )
        self._canvas.configure(bg=kartograph_theme(theme_key)["bg_main"])
        self._redraw()

    def _redraw(self) -> None:
        """Zeichnet alle Tische neu: erst Flächen und Rahmen, danach alle Beschriftungen.

        Die zwei Durchgänge garantieren, dass Namen über allen Rahmen liegen,
        auch wenn ein langer Name über den eigenen Tisch hinausragt.
        """
        self._canvas.delete("all")
        if not self._plan:
            return

        theme = kartograph_theme(self._theme_key)
        items = orient_geometries(build_seat_geometries_v4(self._plan), self._options.orientation)
        if not items:
            return
        bounds = world_bounds(item.polygon for item in items)

        self._canvas.update_idletasks()
        avail_w = max(self._canvas.winfo_width(), 200) - 2 * _PADDING
        avail_h = max(self._canvas.winfo_height(), 200) - 2 * _PADDING
        cell = max(18, min(avail_w / bounds.span_x, avail_h / bounds.span_y))
        # Inhalt zentrieren
        origin_x = _PADDING + (avail_w - bounds.span_x * cell) / 2 - bounds.min_x * cell
        origin_y = _PADDING + (avail_h - bounds.span_y * cell) / 2 - bounds.min_y * cell

        labels: list[tuple[float, float, object]] = []
        for item in items:
            canvas_pts = [(origin_x + wx * cell, origin_y + wy * cell) for wx, wy in item.polygon]
            geometry = item.geometry
            fill = theme["teacher_fill"] if geometry.is_teacher else theme["accent_soft"]
            self._canvas.create_polygon(_flat(canvas_pts), fill=fill, outline=theme["border"], width=1)
            if geometry.student is not None:
                self._draw_color_frames(canvas_pts, geometry.student.diagnostic.color_tags, cell)
            ys = [py for _px, py in canvas_pts]
            labels.append((origin_x + item.center[0] * cell, (min(ys) + max(ys)) / 2, geometry))

        for label_x, label_y, geometry in labels:
            self._draw_label(label_x, label_y, geometry, theme, cell)

    def _draw_color_frames(self, canvas_pts: list[tuple[float, float]], color_tags: list[str], cell: float) -> None:
        """Zeichnet die Farbringe eines Tisches (außen höchste Farbe, innen Farbe 1).

        Tk zeichnet eine Polygon-Outline mittig auf der Linie. Deshalb liefert
        ``frame_rings`` die Mittellinie jedes Rings, und die Ringe schließen
        lückenlos aneinander an.

        Args:
            canvas_pts: Tischpolygon in Canvas-Pixeln.
            color_tags: Farbschlüssel des Schülers.
            cell: Aktuelle Zellgröße in Pixeln (skaliert die Ringbreite).
        """
        colors = frame_colors_outer_to_inner(color_tags, self._color_order, self._options)
        if not colors:
            return
        width, rings = frame_rings(canvas_pts, len(colors), max(2.0, cell * _FRAME_WIDTH_PER_CELL))
        for color_key, ring in zip(colors, rings):
            _label, hex_color = self._color_by_key[color_key]
            self._canvas.create_polygon(_flat(ring), fill="", outline=hex_color, width=width)

    def _draw_label(self, x: float, y: float, geometry, theme: dict, cell: float) -> None:
        """Beschriftet einen Tisch: "Lehrertisch" bzw. den Anzeigenamen des Schülers.

        Args:
            x: Canvas-x der Beschriftungsmitte.
            y: Canvas-y der Beschriftungsmitte.
            geometry: ``SeatGeometryV4`` des Tisches.
            theme: Aktives Theme-Dict.
            cell: Zellgröße in Pixeln (skaliert die Schrift).
        """
        if geometry.is_teacher:
            self._canvas.create_text(
                x, y, text="Lehrertisch", fill=theme["teacher_text"],
                font=("Segoe UI", max(7, int(cell * 0.12)), "bold"),
            )
        elif geometry.student is not None:
            name = self._display_names.get(geometry.student.student_id, "")
            if name:
                self._canvas.create_text(
                    x, y, text=name, fill=theme["fg_primary"],
                    font=("Segoe UI", max(7, int(cell * 0.14)), "bold"),
                )


def _flat(points: list[tuple[float, float]]) -> list[float]:
    """Wandelt ``[(x, y), …]`` in die flache Koordinatenliste, die ``create_polygon`` erwartet.

    Args:
        points: Polygon-Eckpunkte.
    """
    return [coord for point in points for coord in point]
