"""Canvas-Events-Mixin für das Kartograph-Hauptfenster.

Behandelt Mausklicks, Drag, Doppelklick, MouseWheel und Zoom auf dem
Raster-Canvas sowie die zugehörigen Viewport-Operationen.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import NAME_EDITING
from app.core.intents.view_intents import ResetViewIntent, ZoomInIntent, ZoomOutIntent


class CanvasEventsMixin:
    """Mixin: Canvas-Mausereignisse, Zoom und Viewport-Navigation."""

    def _register_canvas_event_bindings(self) -> None:
        """Bindet alle Maus- und Tastaturereignisse an den Canvas."""
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<Configure>", lambda _event: self.redraw_grid())
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mouse_wheel)

    def _on_canvas_click(self, event) -> None:
        """Setzt die Einzelauswahl auf die angeklickte Zelle und initiiert Drag.

        Args:
            event: Tkinter-Mausereignis.
        """
        x, y = self._event_to_cell(event)
        self._set_selection_single(x, y)
        self._drag_active = True
        self.canvas.focus_set()
        self.redraw_grid()
        self._update_selection_no_open()

    def _on_canvas_drag(self, event) -> None:
        """Erweitert die Auswahl während eines Drag-Vorgangs.

        Args:
            event: Tkinter-Mausereignis.
        """
        if not self._drag_active:
            return
        x, y = self._event_to_cell(event)
        self._set_selection_focus(x, y)
        self.redraw_grid()
        self._update_selection_no_open()

    def _on_canvas_release(self, event) -> None:
        """Schließt einen Drag-Vorgang ab und aktualisiert die Auswahl.

        Args:
            event: Tkinter-Mausereignis.
        """
        if not self._drag_active:
            return
        self._drag_active = False
        x, y = self._event_to_cell(event)
        self._set_selection_focus(x, y)
        self.redraw_grid()
        self._update_selection_no_open()

    def _update_selection_no_open(self) -> None:
        """Aktualisiert den Auswahl-Marker ohne den Details-Panel zu öffnen.

        Leere Zelle oder Mehrfachauswahl schließen das Details-Panel automatisch.
        Bei einer Einzelauswahl auf einem Tisch wird das Panel nur aktualisiert
        wenn es bereits offen ist.
        """
        if not self.current_plan:
            self._set_details_panel_visible(False)
            self._selected_marker_var.set("")
            self._name_var.set("")
            self._last_name_var.set("")
            self.name_entry.configure(state="disabled")
            self.last_name_entry.configure(state="disabled")
            self._refresh_tablegroup_overlay()
            return

        x, y = self.selection.active_cell()
        min_x, min_y, max_x, max_y = self.selection.bounds()

        if not self.selection.is_single():
            count = (max_x - min_x + 1) * (max_y - min_y + 1)
            self._selected_marker_var.set(f"Bereich: ({min_x}, {min_y}) bis ({max_x}, {max_y}) | {count} Zellen")
            self._set_details_panel_visible(False)
            self._name_var.set("")
            self._last_name_var.set("")
            self.name_entry.configure(state="disabled")
            self.last_name_entry.configure(state="disabled")
            if self.interaction_mode == NAME_EDITING:
                self.canvas.focus_set()
            self._refresh_tablegroup_overlay()
            return

        self._selected_marker_var.set(f"Markierung: ({x}, {y})")
        student = self.current_plan.student_at(x, y)
        ts = self.current_plan.classroom.teacher_seat
        is_occupied = student is not None or (ts.x == x and ts.y == y)

        if not is_occupied:
            self._set_details_panel_visible(False)
            self._name_var.set("")
            self._last_name_var.set("")
            self.name_entry.configure(state="disabled")
            self.last_name_entry.configure(state="disabled")
            if self.interaction_mode == NAME_EDITING:
                self.canvas.focus_set()
        elif self._details_panel_visible:
            self._refresh_details_panel()

        self._refresh_tablegroup_overlay()

    def _on_canvas_double_click(self, event) -> None:
        """Wählt die Zelle aus, bestätigt sie und öffnet den Namenseditor.

        Args:
            event: Tkinter-Mausereignis.
        """
        x, y = self._event_to_cell(event)
        self._set_selection_single(x, y)
        self.confirm_selected_cell()
        self.enter_name_edit_mode()

    def _event_to_cell(self, event) -> tuple[int, int]:
        """Wandelt Canvas-Pixel-Koordinaten in Raster-Zellkoordinaten um.

        Args:
            event: Tkinter-Mausereignis.

        Returns:
            Geklemmte (x, y)-Zellkoordinaten.
        """
        world_x = int((self.canvas.canvasx(event.x)) // self.cell_size)
        world_y = int((self.canvas.canvasy(event.y)) // self.cell_size)
        return self._clamp_cell(world_x, world_y)

    def _on_mouse_wheel(self, event) -> None:
        """Scrollt den Canvas vertikal per Mausrad.

        Args:
            event: Tkinter-Mausradereignis (liefert ``delta`` für die Richtung).
        """
        steps = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(steps, "units")
        self.redraw_grid()

    def _on_shift_mouse_wheel(self, event) -> None:
        """Scrollt den Canvas horizontal per Shift+Mausrad.

        Args:
            event: Tkinter-Mausradereignis (liefert ``delta`` für die Richtung).
        """
        steps = -1 if event.delta > 0 else 1
        self.canvas.xview_scroll(steps, "units")
        self.redraw_grid()

    def _on_ctrl_mouse_wheel(self, event) -> None:
        """Zoomt per Ctrl+Mausrad ein oder aus.

        Args:
            event: Tkinter-Mausradereignis (liefert ``delta`` für die Richtung).
        """
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self) -> None:
        """Vergrößert die Ansicht um eine Stufe (v4: ZoomInIntent)."""
        self._controller.dispatch(ZoomInIntent())

    def zoom_out(self) -> None:
        """Verkleinert die Ansicht um eine Stufe (v4: ZoomOutIntent)."""
        self._controller.dispatch(ZoomOutIntent())

    def reset_viewport(self) -> None:
        """Setzt Zoomfaktor, Auswahl und Viewport auf die Ausgangswerte zurück (v4: ResetViewIntent)."""
        self._controller.dispatch(ResetViewIntent())
        self._set_selection_single(0, 0)
        self.center_on_cell(0, 0)
        self.redraw_grid()
        self._refresh_details_panel()

    def center_on_cell(self, x: int, y: int) -> None:
        """Verschiebt den Viewport so, dass die angegebene Zelle zentriert sichtbar ist.

        Args:
            x: Raster-x-Koordinate.
            y: Raster-y-Koordinate.
        """
        self.update_idletasks()
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        min_x, min_y, max_x, max_y = self._grid_pixel_bounds()
        total_w = max_x - min_x
        total_h = max_y - min_y

        cx, cy = self._clamp_cell(x, y)
        target_x = cx * self.cell_size + self.cell_size / 2
        target_y = cy * self.cell_size + self.cell_size / 2

        left = target_x - width / 2
        top = target_y - height / 2

        x_fraction = (left - min_x) / max(1, total_w)
        y_fraction = (top - min_y) / max(1, total_h)

        self.canvas.xview_moveto(max(0.0, min(1.0, x_fraction)))
        self.canvas.yview_moveto(max(0.0, min(1.0, y_fraction)))
