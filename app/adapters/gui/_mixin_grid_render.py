"""Grid-Render-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Zeichnet das gesamte Raster (leere Zellen, Lehrertisch, Schülertische mit
Tischgruppen-Polygonen) und die Auswahl-Indikatoren (Fokusrahmen, TG-Beschriftungen).
Die Inhalts-Zeichnung einzelner Schülertische ist in ``_mixin_grid_helpers.py``.
"""

from __future__ import annotations

from app.adapters.gui.ui_theme import kartograph_theme
from app.core.domain.student_naming import compute_display_names
from app.core.domain.table_groups import (
    build_seat_geometries_v4,
    group_bounds_from_geometries_v4,
    list_tablegroup_numbers_v4,
    selection_bounds_from_geometries_v4,
)
from app.core.usecases.v4.grade_usecases import compute_grade_display_by_student
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols_by_student


class GridRenderMixin:
    """Mixin: Rasterzeichnung und Auswahl-Indikatoren (v4).

    ``redraw_grid()`` läuft auf jeder Cursor-Navigation, jedem Drag-Tick und
    jedem Scroll/Zoom — mit Abstand der höchstfrequenteste Hot Path der App.
    Zwei getrennte Optimierungsebenen greifen hier ineinander:

    1. Pro-Aufruf-Redundanz beseitigt: früher rief ``_draw_student_desk_content()``
       pro sichtbarem Schüler einzeln ``summarize_latest_symbols()``/
       ``compute_grade_display()`` auf (je ein eigener Sessions-Resort) und
       ``session_for_date(heute)`` mehrfach mit demselben Datum. Jetzt werden
       diese drei Werte einmal pro ``redraw_grid()``-Aufruf für ALLE Schüler
       vorberechnet (Bulk-Funktionen aus Item 1 des Perf-Fixes) und nur noch
       per Dict-Lookup weitergereicht.
    2. Cache über mehrere Aufrufe hinweg: ``compute_display_names()``,
       ``build_seat_geometries_v4()`` und die Schriftgrößen-Berechnung hängen
       nur von ``state_version`` (s. ``KartographAppController``) plus wenigen
       GUI-Einstellungen ab, nicht vom konkreten Navigations-/Drag-Ereignis —
       bei reiner Cursor-Bewegung ändert sich keiner dieser Werte, das
       Neuberechnen war reine Verschwendung.
    3. Canvas-Item-Wiederverwendung (Item 5, Stufe A, bislang nur Kacheln):
       ``canvas.delete("grid")`` + Neuerzeugung ALLER sichtbaren Items bei
       jedem Aufruf war selbst bei reinem Scrollen/Zoomen teuer. Die
       Hintergrundkacheln (dominante Item-Anzahl, bis zu ~1500 bei starkem
       Auszoomen) werden jetzt über ``_grid_tile_pool`` wiederverwendet
       (``coords()``/``itemconfigure()`` statt ``create_rectangle()``);
       überzählige Kacheln werden versteckt (``state="hidden"``), nie
       gelöscht. Andere Canvas-Items (Pulte, Auswahl-Indikatoren) tragen
       zusätzlich den Tag ``"grid_transient"`` und werden weiterhin bei jedem
       Aufruf gelöscht+neu erzeugt -- das ist eine bewusste Zwischenstufe,
       kein Versehen; ob sich die Wiederverwendung auch dafür lohnt, wird
       erst nach Messung dieser Stufe entschieden (s. ``perf_bench_redraw_grid.py``).
    """

    def redraw_grid(self) -> None:
        """Zeichnet das gesamte Raster neu auf dem Canvas."""
        self.canvas.delete("grid_transient")
        if not self.current_plan:
            for item_id in self._grid_tile_pool:
                self.canvas.itemconfigure(item_id, state="hidden")
            return

        theme = kartograph_theme(self.theme_key)
        state_version = self._controller.state_version

        names_key = (state_version, self.name_format, self.disambiguate_colliding_names)
        if names_key != self._grid_names_cache_key:
            self._grid_names_cache_value = compute_display_names(
                self.current_plan.classroom.students, self.name_format, self.disambiguate_colliding_names
            )
            self._grid_names_cache_key = names_key
        self._display_names = self._grid_names_cache_value

        if state_version != self._grid_geometry_cache_key:
            self._grid_geometry_cache_value = build_seat_geometries_v4(self.current_plan)
            self._grid_geometry_cache_key = state_version
        geometries = self._grid_geometry_cache_value

        font_key = (names_key, self.cell_size)
        if font_key != self._grid_font_size_cache_key:
            self._grid_font_size_cache_value = self._compute_uniform_student_name_font_size()
            self._grid_font_size_cache_key = font_key
        student_name_font_size = self._grid_font_size_cache_value

        # Pro Aufruf einmal für alle Schüler vorberechnen statt pro sichtbarem
        # Schüler einzeln (siehe Klassendocstring, Punkt 1).
        today_session = self.current_plan.documentation.session_for_date(self._today_doc_date())
        latest_symbols_by_student = summarize_latest_symbols_by_student(self.current_plan)
        overall_grade_by_student = compute_grade_display_by_student(self.current_plan)

        left = self.canvas.canvasx(0)
        top = self.canvas.canvasy(0)
        right = self.canvas.canvasx(self.canvas.winfo_width())
        bottom = self.canvas.canvasy(self.canvas.winfo_height())

        start_x = max(self._grid_min(), int(left // self.cell_size) - 1)
        end_x = min(self._grid_max(), int(right // self.cell_size) + 1)
        start_y = max(self._grid_min(), int(top // self.cell_size) - 1)
        end_y = min(self._grid_max(), int(bottom // self.cell_size) + 1)

        geometry_by_coord = {(g.x, g.y): g for g in geometries if not g.is_teacher}
        selected_cells = set(self.selection.cells())
        selected_tablegroups: set[int] = {
            g.group_id
            for g in geometries
            if not g.is_teacher and (g.x, g.y) in selected_cells and g.group_id is not None
        }

        self._draw_desk_cells(
            start_x, end_x, start_y, end_y, theme,
            (left, top, right, bottom), geometry_by_coord, student_name_font_size,
            today_session, latest_symbols_by_student, overall_grade_by_student,
        )
        self._draw_selection_indicators(geometries, selected_cells, selected_tablegroups, theme)

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
                tags=("grid", "grid_transient"),
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
                tags=("grid", "grid_transient"),
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
            tags=("grid", "grid_transient"),
        )

    def _sync_tile_pool(self, cell_positions: list[tuple[float, float]], theme: dict) -> None:
        """Erzeugt/aktualisiert die Hintergrundkacheln über einen wiederverwendbaren Item-Pool.

        Kachel-Slots sind anonym und austauschbar -- keine Kachel "gehört"
        über mehrere Aufrufe hinweg zu einer bestimmten Rasterzelle. Slot
        ``i`` wird pro Aufruf positional mit der i-ten sichtbaren
        Kachelposition befüllt (``coords()``/``itemconfigure()`` bei
        Wiederverwendung). Überzählige Slots werden versteckt
        (``state="hidden"``), nie gelöscht -- das ist bewusst, damit
        Schrumpfen (z.B. Reinzoomen) keine Waisen hinterlässt und kein
        erneutes ``create_rectangle()`` beim nächsten Wachstum nötig ist.

        Neu erzeugte Kacheln werden explizit an den Boden des Canvas-Stapels
        gelegt (``tag_lower()``), statt sich implizit darauf zu verlassen,
        dass alle anderen Items ohnehin nach dieser Methode neu gezeichnet
        werden -- die Stapelreihenfolge der Kacheln soll eine explizite
        Invariante sein, kein Nebenprodukt der Aufrufreihenfolge.
        """
        pool = self._grid_tile_pool
        needed = len(cell_positions)

        for index, (x1, y1) in enumerate(cell_positions):
            x2 = x1 + self.cell_size
            y2 = y1 + self.cell_size
            if index < len(pool):
                item_id = pool[index]
                self.canvas.coords(item_id, x1, y1, x2, y2)
                self.canvas.itemconfigure(
                    item_id, fill=theme["bg_surface"], outline=theme["border"], state="normal"
                )
            else:
                item_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=theme["bg_surface"], outline=theme["border"], width=1, tags=("grid",),
                )
                self.canvas.tag_lower(item_id)
                pool.append(item_id)

        for index in range(needed, len(pool)):
            self.canvas.itemconfigure(pool[index], state="hidden")
