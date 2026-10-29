"""Grid-Render-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Zeichnet das gesamte Raster (leere Zellen, Lehrertisch, Schülertische mit
Tischgruppen-Polygonen) und die Auswahl-Indikatoren (Fokusrahmen, TG-Beschriftungen).
Die Inhalts-Zeichnung einzelner Schülertische ist in ``_mixin_grid_helpers.py``.
"""

from __future__ import annotations

from app.adapters.gui.ui_theme import kartograph_theme
from app.core.domain.table_groups import (
    group_bounds_from_geometries_v4,
    list_tablegroup_numbers_v4,
    selection_bounds_from_geometries_v4,
)


class GridRenderMixin:
    """Mixin: Rasterzeichnung und Auswahl-Indikatoren (v4).

    ``redraw_grid()`` läuft auf jeder Cursor-Navigation, jedem Drag-Tick und
    jedem Scroll/Zoom — der häufigste Render-Pfad der App. Drei Ebenen der
    Sparsamkeit:

    1. Abgeleitete Plandaten (Anzeigenamen, Sitzgeometrien, neueste Symbole,
       Gesamtnoten) kommen aus ``controller.derived()`` — einmal berechnet pro
       ``content_version``, gemeinsam mit der Doku-Tabelle; eine Cursorbewegung
       ändert die ``content_version`` nicht.
    2. Zwei Ebenen: Die Tisch-Ebene (``grid_transient``) wird nur neu gezeichnet,
       wenn sich ihr Inhaltsschlüssel ändert; bei reiner Auswahländerung aus
       ``apply_state`` wird nur die Auswahl-Ebene (``grid_selection``) erneuert.
    3. Hintergrundkacheln laufen über den bw-gui ``CanvasItemPool``
       (wiederverwendet, Tk bekommt nur Änderungen).
    """

    def _request_grid_redraw(self) -> None:
        """Fordert ein vollständiges Raster-Neuzeichnen für den nächsten Idle-Zyklus an.

        Einziger Weg für GUI-Code außerhalb von ``apply_state``: mehrere
        Anforderungen in einem Zyklus (Scroll-Ereignisse, Drag-Ticks, mehrere
        Änderungen in einem Handler) kosten genau einen Render
        (``IdleRenderScheduler``). ``tests/test_render_entry_points.py``
        erzwingt, dass niemand sonst ``redraw_grid`` direkt aufruft.
        """
        self._grid_scheduler.mark("grid", self.redraw_grid)

    def redraw_grid(self, *, selection_only: bool = False) -> None:
        """Zeichnet das Raster: Tische nur bei geändertem Inhalt, die Auswahl-Ebene immer.

        Zwei Ebenen: Tische/Kacheln (Tag ``grid_transient``) hängen nur von
        ``content_version``, Zellgröße, Theme, sichtbarem Ausschnitt und dem
        heutigen Datum ab (geprüft: das Tische-Zeichnen liest keinen
        Auswahlzustand); die Auswahl-Ebene (Tag ``grid_selection``: Fokusrahmen,
        Tischgruppen-Rahmen/-Beschriftungen) wird immer neu gezeichnet.

        Args:
            selection_only: Nur ``apply_state`` darf das setzen — dann werden die
                Tische übersprungen, *falls* ihr Inhaltsschlüssel unverändert ist.
                Alle anderen Aufrufer zeichnen vollständig.
        """
        if not self.current_plan:
            self.canvas.delete("grid_transient")
            self.canvas.delete("grid_selection")
            self._grid_tile_pool.begin()
            self._grid_tile_pool.end()
            self._grid_content_key = None
            return

        theme = kartograph_theme(self.theme_key)
        derived = self._controller.derived()
        self._display_names = derived.display_names(self.name_format, self.disambiguate_colliding_names)
        geometries = derived.seat_geometries

        left = self.canvas.canvasx(0)
        top = self.canvas.canvasy(0)
        right = self.canvas.canvasx(self.canvas.winfo_width())
        bottom = self.canvas.canvasy(self.canvas.winfo_height())
        today = self._today_doc_date()
        content_key = (self._controller.content_version, self.cell_size, self.theme_key, left, top, right, bottom, today)

        if not (selection_only and content_key == self._grid_content_key):
            self._draw_desks(theme, derived, geometries, (left, top, right, bottom), today)
            self._grid_content_key = content_key

        selected_cells = set(self.selection.cells())
        selected_tablegroups: set[int] = {
            g.group_id
            for g in geometries
            if not g.is_teacher and (g.x, g.y) in selected_cells and g.group_id is not None
        }
        self.canvas.delete("grid_selection")
        self._draw_selection_indicators(geometries, selected_cells, selected_tablegroups, theme)

    def _draw_desks(self, theme: dict, derived, geometries: list, viewport: tuple[float, float, float, float], today: str) -> None:
        """Inhalts-Ebene: Kacheln und alle sichtbaren Tische neu zeichnen.

        Args:
            theme: Farbwerte des aktuellen Themes.
            derived: ``PlanDerivedData`` des aktuellen Inhaltsstands.
            geometries: Sitzgeometrien.
            viewport: Sichtbarer Canvas-Ausschnitt ``(left, top, right, bottom)``.
            today: Heutiges Doku-Datum.
        """
        self.canvas.delete("grid_transient")
        font_key = (self._controller.content_version, self.name_format, self.disambiguate_colliding_names, self.cell_size)
        if font_key != self._grid_font_size_cache_key:
            self._grid_font_size_cache_value = self._compute_uniform_student_name_font_size()
            self._grid_font_size_cache_key = font_key
        left, top, right, bottom = viewport
        start_x = max(self._grid_min(), int(left // self.cell_size) - 1)
        end_x = min(self._grid_max(), int(right // self.cell_size) + 1)
        start_y = max(self._grid_min(), int(top // self.cell_size) - 1)
        end_y = min(self._grid_max(), int(bottom // self.cell_size) + 1)
        geometry_by_coord = {(g.x, g.y): g for g in geometries if not g.is_teacher}
        self._draw_desk_cells(
            start_x, end_x, start_y, end_y, theme, viewport, geometry_by_coord, self._grid_font_size_cache_value,
            self.current_plan.documentation.session_for_date(today), derived.latest_symbols, derived.grade_display,
        )

    def _draw_desk_cells(
        self,
        start_x: int, end_x: int, start_y: int, end_y: int,
        theme: dict,
        viewport: tuple[float, float, float, float],
        geometry_by_coord: dict,
        student_name_font_size: int,
        today_session,
        latest_symbols_by_student: dict,
        overall_grade_by_student: dict,
    ) -> None:
        """Zeichnet alle leeren Rasterzellen sowie Lehrer- und Schülertische.

        Args:
            start_x: Erste sichtbare Rasterspalte (inklusive).
            end_x: Letzte sichtbare Rasterspalte (inklusive).
            start_y: Erste sichtbare Rasterzeile (inklusive).
            end_y: Letzte sichtbare Rasterzeile (inklusive).
            theme: Farb-/Stilwerte für das aktuelle Canvas-Theme.
            viewport: Sichtbarer Canvas-Ausschnitt als (left, top, right, bottom).
            geometry_by_coord: Sitzgeometrien je (x, y)-Koordinate.
            student_name_font_size: Einheitliche Schriftgröße für Schülernamen.
            today_session: Einmalig vorberechnete heutige Session (oder None).
            latest_symbols_by_student: Einmalig vorberechnete neueste Symbole je Schüler.
            overall_grade_by_student: Einmalig vorberechnete Gesamtnoten-Anzeige je Schüler.
        """
        left, top, right, bottom = viewport
        plan = self.current_plan

        cell_positions = [
            (cx * self.cell_size, cy * self.cell_size)
            for cy in range(start_y, end_y + 1)
            for cx in range(start_x, end_x + 1)
        ]
        self._sync_tile_pool(cell_positions, theme)

        # Teacher seat
        ts = plan.classroom.teacher_seat
        tx1 = ts.x * self.cell_size
        ty1 = ts.y * self.cell_size
        tx2 = tx1 + self.cell_size
        ty2 = ty1 + self.cell_size
        if not (tx2 < left - self.cell_size or tx1 > right + self.cell_size
                or ty2 < top - self.cell_size or ty1 > bottom + self.cell_size):
            self.canvas.create_rectangle(
                tx1, ty1, tx2, ty2,
                fill=theme["teacher_fill"], outline=theme["border"], width=1,
                tags=("grid", "grid_transient"),
            )
            self.canvas.create_text(
                tx1 + self.cell_size / 2, ty1 + self.cell_size / 2,
                text="Lehrertisch", fill=theme["teacher_text"],
                font=("Segoe UI", max(8, int(self.cell_size * 0.12)), "bold"),
                tags=("grid", "grid_transient"),
            )

        # Student seats
        for student in plan.classroom.students:
            sx, sy = student.seat.x, student.seat.y
            geometry = geometry_by_coord.get((sx, sy))
            if geometry is None:
                continue

            polygon_points: list[float] = []
            min_px = float("inf")
            min_py = float("inf")
            max_px = float("-inf")
            max_py = float("-inf")
            for world_x, world_y in geometry.polygon:
                px = world_x * self.cell_size
                py = world_y * self.cell_size
                polygon_points.extend((px, py))
                min_px = min(min_px, px)
                min_py = min(min_py, py)
                max_px = max(max_px, px)
                max_py = max(max_py, py)

            if (max_px < left - self.cell_size or min_px > right + self.cell_size
                    or max_py < top - self.cell_size or min_py > bottom + self.cell_size):
                continue

            self.canvas.create_polygon(
                polygon_points,
                fill=theme["accent_soft"], outline=theme["border"], width=1,
                tags=("grid", "grid_transient"),
            )
            center_px = geometry.center_x * self.cell_size
            self._draw_student_desk_content(
                student, center_px, min_px, min_py, theme, student_name_font_size,
                today_session, latest_symbols_by_student, overall_grade_by_student,
            )

    def _draw_selection_indicators(
        self,
        geometries: list,
        selected_cells: set,
        selected_tablegroups: set[int],
        theme: dict,
    ) -> None:
        """Zeichnet gestrichelte TG-Grenzen, TG-Beschriftungen und den Auswahl-Fokusrahmen.

        Args:
            geometries: Sitzgeometrien aller Tische im aktuellen Plan.
            selected_cells: Aktuell ausgewählte Rasterzellen als (x, y)-Koordinaten.
            selected_tablegroups: IDs der Tischgruppen, die durch die Auswahl berührt werden.
            theme: Farb-/Stilwerte für das aktuelle Canvas-Theme.
        """
        for group_id in sorted(selected_tablegroups):
            bounds = group_bounds_from_geometries_v4(geometries, group_id)
            if bounds is None:
                continue
            min_x, min_y, max_x, max_y = bounds
            self.canvas.create_rectangle(
                min_x * self.cell_size, min_y * self.cell_size,
                max_x * self.cell_size, max_y * self.cell_size,
                outline=theme["fg_muted"], width=1, dash=(4, 2),
                tags=("grid", "grid_selection"),
            )

        for group_id in list_tablegroup_numbers_v4(self.current_plan):
            bounds = group_bounds_from_geometries_v4(geometries, group_id)
            if bounds is None:
                continue
            min_x, _min_y, max_x, max_y = bounds
            label_x = (min_x + max_x) / 2
            label_y = max_y + 0.12
            self.canvas.create_text(
                label_x * self.cell_size, label_y * self.cell_size,
                text=f"TG {group_id}", fill=theme["fg_muted"],
                font=("Segoe UI", max(7, int(self.cell_size * 0.09)), "bold"),
                tags=("grid", "grid_selection"),
            )

        selection_bounds = selection_bounds_from_geometries_v4(geometries, selected_cells)
        if selection_bounds is not None:
            min_sel_x, min_sel_y, max_sel_x, max_sel_y = selection_bounds
            x1 = min_sel_x * self.cell_size
            y1 = min_sel_y * self.cell_size
            x2 = max_sel_x * self.cell_size
            y2 = max_sel_y * self.cell_size
        else:
            min_sel_x, min_sel_y, max_sel_x, max_sel_y = self.selection.bounds()
            x1 = min_sel_x * self.cell_size
            y1 = min_sel_y * self.cell_size
            x2 = (max_sel_x + 1) * self.cell_size
            y2 = (max_sel_y + 1) * self.cell_size

        self.canvas.create_rectangle(
            x1, y1, x2, y2, outline=theme["focus_ring"], width=3,
            tags=("grid", "grid_selection"),
        )

    def _sync_tile_pool(self, cell_positions: list[tuple[float, float]], theme: dict) -> None:
        """Zeichnet die Hintergrundkacheln über den gemeinsamen bw-gui ``CanvasItemPool``.

        Kachel-Slots sind anonym und austauschbar; der Pool vergibt sie pro
        Aufruf der Reihe nach, schickt Tk nur geänderte Koordinaten/Farben und
        versteckt überzählige Kacheln (nie löschen -- Schrumpfen hinterlässt
        so keine Waisen). Neu entstandene Kacheln werden explizit an den Boden
        des Canvas-Stapels gelegt (``tag_lower``): die Stapelreihenfolge ist
        eine Invariante, kein Nebenprodukt der Aufrufreihenfolge.
        """
        pool = self._grid_tile_pool
        created_before = len(pool.items)
        pool.begin()
        for x1, y1 in cell_positions:
            pool.place(
                (x1, y1, x1 + self.cell_size, y1 + self.cell_size),
                fill=theme["bg_surface"], outline=theme["border"], width=1,
            )
        pool.end()
        for item_id in pool.items[created_before:]:
            self.canvas.tag_lower(item_id)
