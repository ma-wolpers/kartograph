"""Details-Panel-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Stellt die Refresh-Logik des Details-Panels, die Steuerung der Panel-Sichtbarkeit,
den Namenseditier-Modus sowie die Callbacks für Namensänderungen bereit.
Die Widget-Konstruktion liegt in ``_mixin_details_layout.py``.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import GRID_SELECTED, NAME_EDITING
from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.intents.student_intents import CreateStudentIntent, RenameStudentIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class DetailsMixin:
    """Mixin: Details-Panel-Refresh, Sichtbarkeit und Namenseditier-Modus (v4)."""

    def _refresh_details_panel(self) -> None:
        """Aktualisiert den gesamten Inhalt des Details-Panels für die aktuelle Auswahl."""
        self._color_marker_buttons = []
        for child in self.symbols_frame.winfo_children():
            child.destroy()
        for child in self.symbol_legend_frame.winfo_children():
            child.destroy()
        for child in self.colors_frame.winfo_children():
            child.destroy()
        for child in self.color_legend_frame.winfo_children():
            child.destroy()

        if not self.current_plan:
            self._set_details_panel_visible(False)
            self._selected_marker_var.set("")
            self._name_var.set("")
            self._last_name_var.set("")
            self.name_entry.configure(state="disabled")
            self.last_name_entry.configure(state="disabled")
            self._set_accommodations_field(None)
            self._refresh_tablegroup_overlay()
            return

        x, y = self.selection.active_cell()
        student = self.current_plan.student_at(x, y)
        ts = self.current_plan.classroom.teacher_seat
        is_teacher = ts.x == x and ts.y == y

        min_x, min_y, max_x, max_y = self.selection.bounds()
        if self.selection.is_single():
            self._selected_marker_var.set(f"Markierung: ({x}, {y})")
        else:
            count = (max_x - min_x + 1) * (max_y - min_y + 1)
            self._selected_marker_var.set(f"Bereich: ({min_x}, {min_y}) bis ({max_x}, {max_y}) | {count} Zellen")

        is_student_single = bool(self.selection.is_single() and student is not None and not is_teacher)
        self._set_details_panel_visible(is_student_single)

        if not is_student_single:
            self._name_var.set("")
            self._last_name_var.set("")
            self.name_entry.configure(state="disabled")
            self.last_name_entry.configure(state="disabled")
            self._set_accommodations_field(None)
            if self.interaction_mode == NAME_EDITING:
                self.interaction_mode = GRID_SELECTED
                self.canvas.focus_set()
            self._refresh_tablegroup_overlay()
            return

        self._name_var.set(student.first_name)
        self._last_name_var.set(student.last_name)
        self.name_entry.configure(state="normal")
        self.last_name_entry.configure(state="normal")
        self._set_accommodations_field(student)

        symbol_cols = self._details_button_columns()
        self._populate_symbol_buttons(student, symbol_cols)
        active_lines = self._symbol_legend_lines(student.diagnostic.symbols)
        if active_lines:
            for line in active_lines:
                tui.Label(self.symbol_legend_frame, text=line, wraplength=self._details_legend_wraplength(), justify="left").pack(anchor="w")

        color_cols = self._details_button_columns()
        self._populate_color_buttons(student, color_cols)
        self._apply_color_button_theme()
        for line in self._color_legend_lines(self.current_plan, student.diagnostic.color_tags):
            tui.Label(self.color_legend_frame, text=line, wraplength=self._details_legend_wraplength(), justify="left").pack(anchor="w")

        self._refresh_tablegroup_overlay()

    def _populate_symbol_buttons(self, student, symbol_cols: int) -> None:
        """Erstellt die Symbol-Toggle-Buttons im ``symbols_frame``.

        Args:
            student: Schüler, dessen Symbolstatus angezeigt wird.
            symbol_cols: Anzahl der Spalten im Button-Raster.
        """
        tui.Label(self.symbols_frame, text="Symbole").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        for symbol in self.diagnostic_symbol_catalog:
            count = int(student.diagnostic.symbols.get(symbol, 0))
            icon = self._symbol_glyph(symbol)
            shortcut = self._symbol_by_meaning.get(symbol).shortcut if self._symbol_by_meaning.get(symbol) else None
            caption = f"{icon} {symbol}" if count == 0 else f"{icon} {symbol} x{count}"
            idx = self.diagnostic_symbol_catalog.index(symbol)
            row = 1 + (idx // symbol_cols)
            col = idx % symbol_cols
            button = tui.Button(
                self.symbols_frame,
                text=caption,
                command=lambda s=symbol: self._toggle_selected_symbol(s),
            )
            button.grid(row=row, column=col, sticky="ew", padx=(0, 6), pady=(0, 4))
            self._attach_hover_help(button, label=f"Symbol {symbol} umschalten", shortcut=shortcut.upper() if shortcut else None)
        for col in range(symbol_cols):
            self.symbols_frame.columnconfigure(col, weight=1)

    def _populate_color_buttons(self, student, color_cols: int) -> None:
        """Erstellt die Farbpunkt-Toggle-Buttons im ``colors_frame``.

        Args:
            student: Schüler, dessen Farbpunkt-Status angezeigt wird.
            color_cols: Anzahl der Spalten im Button-Raster.
        """
        tui.Label(self.colors_frame, text="Farbpunkte").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        for key, color_key, label, hex_color in self.color_palette:
            active = color_key in student.diagnostic.color_tags
            caption = label if not active else f"{label}*"
            idx = int(key) - 1
            row = 1 + (idx // color_cols)
            col = idx % color_cols
            button = ui.Button(
                self.colors_frame,
                text=caption,
                command=lambda ck=color_key: self._toggle_selected_color(ck),
                fg=hex_color,
                relief="sunken" if active else "raised",
                padx=6,
                pady=2,
            )
            button.grid(row=row, column=col, sticky="ew", padx=(0, 6), pady=(0, 4))
            self._color_marker_buttons.append(button)
            self._attach_hover_help(button, label=f"Farbpunkt {label} umschalten", shortcut=key)
        for col in range(color_cols):
            self.colors_frame.columnconfigure(col, weight=1)

    def _set_details_panel_visible(self, visible: bool) -> None:
        """Blendet das ``details_frame`` ein oder aus.

        Args:
            visible: ``True`` blendet das Panel ein, ``False`` blendet es aus.
        """
        fill_mode = "both" if self.details_overlay_position in {"left", "right"} else "x"
        if visible and not self._details_panel_visible:
            self.details_frame.pack(fill=fill_mode, padx=12, pady=(4, 12))
            self._details_panel_visible = True
            return
        if not visible and self._details_panel_visible:
            self.details_frame.pack_forget()
            self._details_panel_visible = False

    def enter_name_edit_mode(self) -> None:
        """Aktiviert den Namenseditier-Modus für den aktuell ausgewählten Schüler."""
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()
            self.redraw_grid()
            self._refresh_details_panel()

        x, y = self.selected_cell
        ts = self.current_plan.classroom.teacher_seat
        if ts.x == x and ts.y == y:
            self.status_var.set("Lehrertisch ist nicht editierbar")
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            return

        student = self.current_plan.student_at(x, y)
        if not student:
            self._controller.dispatch(CreateStudentIntent(x=x, y=y))
            self.redraw_grid()

        # Re-read from updated state
        student = self.current_plan.student_at(x, y)
        if not student:
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            return

        self._refresh_details_panel()
        self.name_entry.state(["!disabled"])
        self.last_name_entry.state(["!disabled"])
        if self.name_entry.instate(["!disabled"]):
            self.interaction_mode = NAME_EDITING
            self.name_entry.focus_set()
            self.name_entry.selection_clear()
            self.name_entry.icursor(ui.END)

    def exit_name_edit_mode(self) -> None:
        """Beendet den Namenseditier-Modus und gibt den Fokus an den Canvas zurück."""
        if self.editor_view.winfo_ismapped():
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            self._refresh_details_panel()

    def confirm_selected_cell(self) -> None:
        """Bestätigt die ausgewählte Zelle: kollabiert Auswahl und legt ggf. einen Schüler an."""
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()

        x, y = self.selected_cell
        self._controller.dispatch(CreateStudentIntent(x=x, y=y))

    def _on_name_changed(self) -> None:
        """Callback für Tastatureingabe im Vorname-Feld: speichert den neuen Vornamen sofort."""
        if not self.current_plan or not self.current_plan_path:
            return
        if not self.selection.is_single():
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            return
        self._controller.dispatch(
            RenameStudentIntent(
                student_id=student.student_id,
                first_name=self._name_var.get(),
                last_name=student.last_name,
            )
        )

    def _on_last_name_changed(self) -> None:
        """Callback für Tastatureingabe im Nachname-Feld: speichert den neuen Nachnamen sofort."""
        if not self.current_plan or not self.current_plan_path:
            return
        if not self.selection.is_single():
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            return
        self._controller.dispatch(
            RenameStudentIntent(
                student_id=student.student_id,
                first_name=student.first_name,
                last_name=self._last_name_var.get(),
            )
        )

    def _set_accommodations_field(self, student) -> None:
        """Befüllt das Nachteilsausgleiche-Textfeld oder deaktiviert es bei *student* = None.

        Args:
            student: Anzuzeigender Schüler, oder ``None`` um das Feld zu leeren und zu sperren.
        """
        self.accommodations_field.text.configure(state="normal")
        self.accommodations_field.set("\n".join(student.diagnostic.accommodations) if student else "")
        if student is None:
            self.accommodations_field.text.configure(state="disabled")

    def _on_accommodations_changed(self) -> None:
        """Callback für FocusOut im Nachteilsausgleiche-Feld: speichert die Zeilenliste."""
        if not self.current_plan or not self.current_plan_path:
            return
        if not self.selection.is_single():
            return
        x, y = self.selected_cell
        student = self.current_plan.student_at(x, y)
        if not student:
            return
        lines = self.accommodations_field.get().splitlines()
        self._controller.dispatch(
            SetAccommodationsIntent(student_id=student.student_id, accommodations=lines)
        )
