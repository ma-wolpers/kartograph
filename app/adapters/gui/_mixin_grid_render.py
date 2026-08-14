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


class GridRenderMixin:
    """Mixin: Rasterzeichnung und Auswahl-Indikatoren (v4)."""

    def redraw_grid(self) -> None:
        """Zeichnet das gesamte Raster neu auf dem Canvas."""
        self.canvas.delete("grid")
        if not self.current_plan:
            return

        theme = kartograph_theme(self.theme_key)
        self._display_names = compute_display_names(
            self.current_plan.classroom.students, self.name_format, self.disambiguate_colliding_names
        )

        left = self.canvas.canvasx(0)
        top = self.canvas.canvasy(0)
        right = self.canvas.canvasx(self.canvas.winfo_width())
        bottom = self.canvas.canvasy(self.canvas.winfo_height())

        start_x = max(self._grid_min(), int(left // self.cell_size) - 1)
        end_x = min(self._grid_max(), int(right // self.cell_size) + 1)
        start_y = max(self._grid_min(), int(top // self.cell_size) - 1)
        end_y = min(self._grid_max(), int(bottom // self.cell_size) + 1)

        geometries = build_seat_geometries_v4(self.current_plan)
        geometry_by_coord = {(g.x, g.y): g for g in geometries if not g.is_teacher}
        selected_cells = set(self.selection.cells())
        selected_tablegroups: set[int] = {
            g.group_id
            for g in geometries
            if not g.is_teacher and (g.x, g.y) in selected_cells and g.group_id is not None
        }

        student_name_font_size = self._compute_uniform_student_name_font_size()

        self._draw_desk_cells(
            start_x, end_x, start_y, end_y, theme,
            (left, top, right, bottom), geometry_by_coord, student_name_font_size,
        )
        self._draw_selection_indicators(geometries, selected_cells, selected_tablegroups, theme)

    def _draw_desk_cells(
        self,
        start_x: int, end_x: int, start_y: int, end_y: int,
        theme: dict,
        viewport: tuple[float, float, float, float],
        geometry_by_coord: dict,
        student_name_font_size: int,
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
        """
        left, top, right, bottom = viewport
        plan = self.current_plan

        for cy in range(start_y, end_y + 1):
            for cx in range(start_x, end_x + 1):
                x1 = cx * self.cell_size
                y1 = cy * self.cell_size
                self.canvas.create_rectangle(
                    x1, y1, x1 + self.cell_size, y1 + self.cell_size,
                    fill=theme["bg_surface"], outline=theme["border"], width=1, tags=("grid",),
                )

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
                fill=theme["teacher_fill"], outline=theme["border"], width=1, tags=("grid",),
            )
            self.canvas.create_text(
                tx1 + self.cell_size / 2, ty1 + self.cell_size / 2,
                text="Lehrertisch", fill=theme["teacher_text"],
                font=("Segoe UI", max(8, int(self.cell_size * 0.12)), "bold"), tags=("grid",),
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
                fill=theme["accent_soft"], outline=theme["border"], width=1, tags=("grid",),
            )
            center_px = geometry.center_x * self.cell_size
            self._draw_student_desk_content(student, center_px, min_px, min_py, theme, student_name_font_size)

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
                outline=theme["fg_muted"], width=1, dash=(4, 2), tags=("grid",),
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
                font=("Segoe UI", max(7, int(self.cell_size * 0.09)), "bold"), tags=("grid",),
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

        self.canvas.create_rectangle(x1, y1, x2, y2, outline=theme["focus_ring"], width=3, tags=("grid",))
