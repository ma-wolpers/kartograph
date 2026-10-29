"""Canvas-Events-Mixin für das Kartograph-Hauptfenster.

Behandelt Mausklicks, Drag, Doppelklick, MouseWheel und Zoom auf dem
Raster-Canvas sowie die zugehörigen Viewport-Operationen.

Die Klick-/Drag-/Release-Handler rufen nach ``dispatch()`` bewusst kein
eigenes ``redraw_grid()`` mehr auf: ``KartographAppController.dispatch()``
löst über ``apply_state`` (main_window.py) bereits ein Redraw aus, sobald
sich der State ändert und der Editor sichtbar ist — ein zweiter Aufruf war
hier reine Verdopplung, da sich der Viewport zwischen Dispatch und Handler-
Ende nicht verschiebt (anders als bei ``move_selection``/``expand_selection``
in ``_mixin_selection.py``, wo ``_follow_selection_viewport`` den Viewport
verschieben kann und ein zweites Redraw dafür weiterhin nötig ist).
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import NAME_EDITING
from app.core.intents.view_intents import ResetViewIntent, ZoomInIntent, ZoomOutIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult, KeyModifiers
from bw_gui.contracts.pointer import Axis, WheelEvent, wheel_axis
from bw_gui.runtime import bind_click, bind_drag, bind_wheel, on_resize


class CanvasEventsMixin:
    """Mixin: Canvas-Mausereignisse, Zoom und Viewport-Navigation."""

    def _register_canvas_event_bindings(self) -> None:
        """Bindet Maus-Gesten (bw-gui-Pointer-Contract) und die Größenänderung an den Canvas.

        Press/Ziehen/Loslassen ist eine ``bind_drag``-Geste (Schwelle 0: der Press
        selbst wählt die Zelle). Der zweite Press eines Doppelklicks ist ein
        ``bind_click(count=2)`` und startet keinen Drag (Tks Mehrfachklick-Erkennung,
        wie früher ``<Double-Button-1>``). Verliert das Fenster während des Ziehens den
        Fokus, endet die Geste ohne weiteren Callback; die Auswahl bleibt, wie sie ist.
        """
        bind_drag(
            self.canvas,
            on_start=self._on_canvas_click,
            on_move=self._on_canvas_drag,
            on_end=self._on_canvas_release,
        )
        bind_click(self.canvas, self._on_canvas_double_click, count=2)
        on_resize(self.canvas, lambda _event: self._request_grid_redraw())
        bind_wheel(self.canvas, self._on_canvas_wheel)

    def _on_canvas_click(self, event) -> None:
        """Setzt die Einzelauswahl auf die angeklickte Zelle (Beginn der Drag-Geste).

        Args:
            event: bw-gui-``DragEvent`` des Press (``x``/``y`` relativ zum Canvas).
        """
        x, y = self._event_to_cell(event)
        self._set_selection_single(x, y)
        self.canvas.focus_set()
        self._update_selection_no_open()

    def _on_canvas_drag(self, event) -> None:
        """Erweitert die Auswahl während eines Drag-Vorgangs.

        Args:
            event: bw-gui-``DragEvent`` der Bewegung.
        """
        x, y = self._event_to_cell(event)
        self._set_selection_focus(x, y)
        self._update_selection_no_open()

    def _on_canvas_release(self, event) -> None:
        """Schließt einen Drag-Vorgang ab und aktualisiert die Auswahl.

        Args:
            event: bw-gui-``DragEvent`` des Loslassens (auch außerhalb des Canvas).
        """
        x, y = self._event_to_cell(event)
        self._set_selection_focus(x, y)
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
            event: bw-gui-``ClickEvent`` des zweiten Press (``count=2``).
        """
        x, y = self._event_to_cell(event)
        self._set_selection_single(x, y)
        self.confirm_selected_cell()
        self.enter_name_edit_mode()

    def _event_to_cell(self, event) -> tuple[int, int]:
        """Wandelt Canvas-Pixel-Koordinaten in Raster-Zellkoordinaten um.

        Args:
            event: bw-gui-Pointer-Ereignis mit ``x``/``y`` relativ zum Canvas.

        Returns:
            Geklemmte (x, y)-Zellkoordinaten.
        """
        world_x = int((self.canvas.canvasx(event.x)) // self.cell_size)
        world_y = int((self.canvas.canvasy(event.y)) // self.cell_size)
        return self._clamp_cell(world_x, world_y)

    def _on_canvas_wheel(self, event: WheelEvent) -> EventResult:
        """Mausrad über dem Canvas: Strg zoomt, Shift scrollt horizontal, sonst vertikal.

        Gearbeitet wird mit ganzen Rasten (``whole_steps``): ein normales Mausrad
        liefert pro Raste genau einen Schritt wie bisher; kleine Touchpad-Deltas
        sammeln sich, bis eine ganze Raste erreicht ist (früher zählte jedes
        Ereignis unabhängig von seiner Größe als ein Schritt). Positiv = zum
        Inhaltsende bzw. herauszoomen.

        Args:
            event: bw-gui-``WheelEvent``.

        Returns:
            ``EventResult.HANDLED`` -- der Canvas ist der Scroll-Empfänger.
        """
        steps = event.whole_steps
        if steps == 0:
            return EventResult.HANDLED
        if isinstance(event.modifiers, KeyModifiers) and event.modifiers.control:
            zoom = self.zoom_out if steps > 0 else self.zoom_in
            for _ in range(abs(steps)):
                zoom()
            return EventResult.HANDLED
        if wheel_axis(event) is Axis.HORIZONTAL:
            self.canvas.xview_scroll(steps, "units")
        else:
            self.canvas.yview_scroll(steps, "units")
        self._request_grid_redraw()
        return EventResult.HANDLED

    def zoom_in(self) -> None:
        """Vergrößert die Ansicht um eine Stufe (v4: ZoomInIntent)."""
        self._controller.dispatch(ZoomInIntent())

    def zoom_out(self) -> None:
        """Verkleinert die Ansicht um eine Stufe (v4: ZoomOutIntent)."""
        self._controller.dispatch(ZoomOutIntent())

    def reset_viewport(self) -> None:
        """Setzt Zoomfaktor, Auswahl und Viewport auf die Ausgangswerte zurück (v4: ResetViewIntent)."""
        self._controller.dispatch(ResetViewIntent())
        if self._editor_surface == "docs":
            return  # in der Doku-Ansicht setzt ResetView nur die Spaltenbreiten zurück
        self._set_selection_single(0, 0)
        self.center_on_cell(0, 0)
        self._request_grid_redraw()
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
