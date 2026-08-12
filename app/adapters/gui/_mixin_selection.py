"""Auswahl-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Stellt Raster-Grenzen, Scroll-Region, Auswahl-State, Viewport-Folge-Logik
sowie Key-Handler für Namenseingabe und Return-Taste bereit.
"""

from __future__ import annotations

from datetime import date

from app.adapters.gui.main_window_constants import LIST_ACTIVE
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.models_v4 import SeatingPlan
from app.core.intents.navigation_intents import MoveSelectionIntent, SelectCellIntent


class SelectionMixin:
    """Mixin: Raster-Grenzen, Auswahl-State und Key-Handler (v4)."""

    def _grid_min(self) -> int:
        """Gibt die minimale Raster-Koordinate zurück."""
        return -self.canvas_radius

    def _grid_max(self) -> int:
        """Gibt die maximale Raster-Koordinate zurück."""
        return self.canvas_radius

    def _count_out_of_bounds_desks(self, plan: SeatingPlan, radius: int | None = None) -> int:
        """Zählt Schüler, die außerhalb des angegebenen Radius liegen (v4).

        Args:
            plan: Sitzplan, dessen Schüler geprüft werden.
            radius: Zu prüfender Radius; ``None`` verwendet ``self.canvas_radius``.
        """
        effective_radius = self.canvas_radius if radius is None else self._normalize_canvas_radius(radius)
        min_grid = -effective_radius
        max_grid = effective_radius
        return sum(
            1 for s in plan.classroom.students
            if s.seat.x < min_grid or s.seat.x > max_grid
            or s.seat.y < min_grid or s.seat.y > max_grid
        )

    def _grid_pixel_bounds(self) -> tuple[float, float, float, float]:
        """Berechnet die Pixel-Grenzen des gesamten Rasters."""
        min_grid = self._grid_min()
        max_grid = self._grid_max()
        min_x = min_grid * self.cell_size
        min_y = min_grid * self.cell_size
        max_x = (max_grid + 1) * self.cell_size
        max_y = (max_grid + 1) * self.cell_size
        return min_x, min_y, max_x, max_y

    def _update_scroll_region(self) -> None:
        """Setzt die Canvas-Scroll-Region auf die aktuellen Raster-Pixel-Grenzen."""
        min_x, min_y, max_x, max_y = self._grid_pixel_bounds()
        self.canvas.configure(scrollregion=(min_x, min_y, max_x, max_y))

    def _clamp_cell(self, x: int, y: int) -> tuple[int, int]:
        """Klemmt Raster-Koordinaten auf den gültigen Canvas-Bereich.

        Args:
            x: Raster-x-Koordinate.
            y: Raster-y-Koordinate.
        """
        min_grid = self._grid_min()
        max_grid = self._grid_max()
        return max(min_grid, min(max_grid, x)), max(min_grid, min(max_grid, y))

    def _set_selection_single(self, x: int, y: int) -> None:
        """Setzt die Auswahl auf eine einzelne geklemmte Zelle (v4: SelectCellIntent).

        ``apply_state`` synct das Ergebnis zurück in ``self.selection``/``self.selected_cell``.

        Args:
            x: Raster-x-Koordinate der Zielzelle.
            y: Raster-y-Koordinate der Zielzelle.
        """
        cx, cy = self._clamp_cell(x, y)
        self._controller.dispatch(SelectCellIntent(x=cx, y=cy))

    def _set_selection_focus(self, x: int, y: int) -> None:
        """Verschiebt den Auswahl-Fokus auf eine geklemmte Zelle (v4: MoveSelectionIntent, expand=True).

        Args:
            x: Raster-x-Koordinate der Zielzelle.
            y: Raster-y-Koordinate der Zielzelle.
        """
        cx, cy = self._clamp_cell(x, y)
        focus_x, focus_y = self.selection.active_cell()
        self._controller.dispatch(MoveSelectionIntent(dx=cx - focus_x, dy=cy - focus_y, expand=True))

    def _collapse_selection_to_anchor(self) -> None:
        """Reduziert eine Bereichsauswahl auf die Ankerzelle (v4: SelectCellIntent)."""
        ax, ay = self.selection.anchor_cell()
        self._controller.dispatch(SelectCellIntent(x=ax, y=ay))

    def move_selection(self, dx: int, dy: int) -> None:
        """Verschiebt die Einzelauswahl um einen Schritt und folgt dem Viewport (v4: MoveSelectionIntent).

        Args:
            dx: Verschiebung in x-Richtung (in Zellen).
            dy: Verschiebung in y-Richtung (in Zellen).
        """
        if not self.editor_view.winfo_ismapped():
            return
        x, y = self.selection.active_cell()
        cx, cy = self._clamp_cell(x + dx, y + dy)
        self._controller.dispatch(MoveSelectionIntent(dx=cx - x, dy=cy - y))
        self._follow_selection_viewport(*self.selection.active_cell())
        self.redraw_grid()
        self._update_selection_no_open()

    def expand_selection(self, dx: int, dy: int) -> None:
        """Erweitert die Bereichsauswahl um einen Schritt (v4: MoveSelectionIntent, expand=True).

        Args:
            dx: Verschiebung in x-Richtung (in Zellen).
            dy: Verschiebung in y-Richtung (in Zellen).
        """
        if not self.editor_view.winfo_ismapped():
            return
        x, y = self.selection.active_cell()
        cx, cy = self._clamp_cell(x + dx, y + dy)
        self._controller.dispatch(MoveSelectionIntent(dx=cx - x, dy=cy - y, expand=True))
        self._follow_selection_viewport(*self.selection.active_cell())
        self.redraw_grid()
        self._update_selection_no_open()

    def _follow_selection_viewport(self, x: int, y: int) -> None:
        """Verschiebt den Viewport so, dass die Zelle im Puffer-Bereich sichtbar bleibt.

        Args:
            x: Raster-x-Koordinate der zu zeigenden Zelle.
            y: Raster-y-Koordinate der zu zeigenden Zelle.
        """
        buffer_cells = self.viewport_follow_buffer
        if buffer_cells <= 0:
            self.center_on_cell(x, y)
            return
        self.update_idletasks()
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        left_cell = int(self.canvas.canvasx(0) // self.cell_size)
        right_cell = int(self.canvas.canvasx(width - 1) // self.cell_size)
        top_cell = int(self.canvas.canvasy(0) // self.cell_size)
        bottom_cell = int(self.canvas.canvasy(height - 1) // self.cell_size)
        if right_cell - left_cell < buffer_cells * 2 or bottom_cell - top_cell < buffer_cells * 2:
            self.center_on_cell(x, y)
            return
        if x < left_cell + buffer_cells or x > right_cell - buffer_cells or y < top_cell + buffer_cells or y > bottom_cell - buffer_cells:
            self.center_on_cell(x, y)

    def _on_return_key(self, _event) -> str | None:
        """Handler für Return/KP_Enter: kontextabhängige Bestätigungs-Aktion.

        Args:
            _event: Tkinter-Tastaturereignis (ungenutzt).
        """
        if self._is_text_input_focused():
            return "break"
        if self.editor_view.winfo_ismapped():
            if self._editor_surface == "docs":
                fixed_column_id = self._doc_selected_fixed_column_id
                date_index = self._doc_selected_date_index
                if self._doc_selected_fixed_column_id and self._doc_selected_fixed_column_id.startswith("grade_"):
                    self._open_selected_docs_grade_cell_editor()
                    self.after_idle(lambda: self._restore_docs_column_selection(fixed_column_id, date_index))
                    return "break"
                self.after_idle(lambda: self._restore_docs_column_selection(fixed_column_id, date_index))
                return "break"
            if not self.selection.is_single():
                self._collapse_selection_to_anchor()
                self.redraw_grid()
                self._refresh_details_panel()
            return self._handle_intent(UiIntent.CONFIRM_SELECTION)
        if self.interaction_mode == LIST_ACTIVE:
            return self._handle_intent(UiIntent.LIST_OPEN_SELECTED)
        return self._handle_intent(UiIntent.CONFIRM_SELECTION)

    def _bind_editor_return_override(self, widget) -> None:
        """Bindet Return und KP_Enter an ``_on_return_key`` für einen Toolbar-Button.

        Args:
            widget: Toolbar-Button-Widget, an das die Tastenbindung gebunden wird.
        """
        widget.bind("<Return>", self._on_return_key)
        widget.bind("<KP_Enter>", self._on_return_key)

    def _on_name_entry_escape(self, _event) -> str:
        """Handler für Escape in Namensfeldern: verlässt den Namenseditor-Modus.

        Args:
            _event: Tkinter-Tastaturereignis (ungenutzt).
        """
        self.exit_name_edit_mode()
        return "break"

    def _on_name_entry_return(self, _event) -> str:
        """Handler für Return in Namensfeldern: verlässt den Namenseditor-Modus.

        Args:
            _event: Tkinter-Tastaturereignis (ungenutzt).
        """
        self.exit_name_edit_mode()
        return "break"

    def _today_doc_date(self) -> str:
        """Gibt das heutige Datum im ISO-Format als Dokumentations-Datums-Schlüssel zurück."""
        return date.today().isoformat()
