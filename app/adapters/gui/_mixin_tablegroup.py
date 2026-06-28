"""Tischgruppen-Overlay-Mixin für das Kartograph-Hauptfenster.

Verwaltet das Öffnen, Positionieren und Schließen des Tischgruppen-Overlays.
Die Geschäftslogik (Werte lesen, parsen, anwenden) liegt in ``_mixin_tablegroup_logic.py``.
"""

from __future__ import annotations

from app.core.domain.table_groups import TG_ROTATION_LIMIT, TG_SHIFT_LIMIT
from app.core.intents.view_intents import OpenTablegroupSettingsIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui


class TablegroupMixin:
    """Mixin: Öffnen, Positionieren und Schließen des Tischgruppen-Overlays."""

    def open_tablegroup_settings_overlay(self) -> None:
        """Öffnet das Tischgruppen-Einstellungs-Overlay oder bringt es in den Vordergrund (v4: OpenTablegroupSettingsIntent)."""
        if not self.editor_view.winfo_ismapped():
            self.status_var.set("Tischeinstellungen nur im Editor verfuegbar")
            return
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geoeffnet")
            return

        x, y = self.selected_cell
        self._controller.dispatch(OpenTablegroupSettingsIntent(x=x, y=y))

        if self._tablegroup_overlay and self._tablegroup_overlay.winfo_exists():
            self._position_tablegroup_overlay()
            self._refresh_tablegroup_overlay()
            self._tablegroup_overlay.deiconify()
            self._tablegroup_overlay.lift()
            self._tablegroup_overlay.focus_force()
            return

        overlay = ui.Toplevel(self)
        overlay.title("Tischeinstellungen")
        overlay.resizable(False, False)
        overlay.transient(self)
        self._track_popup_window(overlay)
        overlay.protocol("WM_DELETE_WINDOW", self._close_tablegroup_overlay)
        overlay.bind("<Escape>", lambda _event: self._close_tablegroup_overlay())
        self._tablegroup_overlay = overlay
        self._position_tablegroup_overlay()

        body = tui.Frame(overlay)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        self._tg_number_var = ui.StringVar(value="")
        self._tg_shift_x_var = ui.StringVar(value="0.00")
        self._tg_shift_y_var = ui.StringVar(value="0.00")
        self._tg_rotation_var = ui.StringVar(value="0.00")
        self._tg_status_var = ui.StringVar(value="")

        tui.Label(body, text="TG-Nummer").grid(row=0, column=0, sticky="w", pady=(0, 4))
        number_entry = tui.Entry(body, textvariable=self._tg_number_var, width=10)
        number_entry.grid(row=0, column=1, sticky="w", pady=(0, 4))
        number_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("number"))

        tui.Label(body, text=f"x-shift (-{TG_SHIFT_LIMIT:.2f}..{TG_SHIFT_LIMIT:.2f})").grid(row=1, column=0, sticky="w", pady=(0, 4))
        shift_x_entry = tui.Entry(body, textvariable=self._tg_shift_x_var, width=10)
        shift_x_entry.grid(row=1, column=1, sticky="w", pady=(0, 4))
        shift_x_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("shift_x"))

        tui.Label(body, text=f"y-shift (-{TG_SHIFT_LIMIT:.2f}..{TG_SHIFT_LIMIT:.2f})").grid(row=2, column=0, sticky="w", pady=(0, 4))
        shift_y_entry = tui.Entry(body, textvariable=self._tg_shift_y_var, width=10)
        shift_y_entry.grid(row=2, column=1, sticky="w", pady=(0, 4))
        shift_y_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("shift_y"))

        tui.Label(body, text=f"Rotation (-{int(TG_ROTATION_LIMIT)}..{int(TG_ROTATION_LIMIT)})").grid(row=3, column=0, sticky="w", pady=(0, 4))
        rotation_entry = tui.Entry(body, textvariable=self._tg_rotation_var, width=10)
        rotation_entry.grid(row=3, column=1, sticky="w", pady=(0, 4))
        rotation_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("rotation"))

        tui.Label(body, textvariable=self._tg_status_var, style="Panel.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 8))

        button_row = tui.Frame(body)
        button_row.grid(row=5, column=0, columnspan=2, sticky="ew")
        close_button = tui.Button(button_row, text="Schliessen", command=self._close_tablegroup_overlay)
        close_button.pack(side="right")
        self._attach_hover_help(close_button, label="Tischgruppen-Overlay schliessen", shortcut="Esc")
        apply_button = tui.Button(button_row, text="Uebernehmen", command=self._apply_tablegroup_overlay_values)
        apply_button.pack(side="right", padx=(0, 8))
        self._attach_hover_help(apply_button, label="Tischgruppenwerte speichern", shortcut="Enter")

        overlay.bind("<Return>", lambda _event: self._apply_tablegroup_overlay_values())
        self._focus_overlay_widget(overlay, number_entry)
        self._refresh_tablegroup_overlay()

    def _set_tg_last_changed(self, field: str) -> None:
        """Merkt das zuletzt bearbeitete Eingabefeld für die Überlappungsauflösung.

        Args:
            field: Name des Feldes (``"number"``, ``"shift_x"``, ``"shift_y"``, ``"rotation"``).
        """
        self._tg_last_changed_field = field

    def _position_tablegroup_overlay(self) -> None:
        """Positioniert das Overlay relativ zum Hauptfenster laut Overlay-Positions-Einstellung."""
        if not self._tablegroup_overlay or not self._tablegroup_overlay.winfo_exists():
            return
        self.update_idletasks()
        width = 340
        height = 250
        position = self.tablegroup_overlay_position

        if position == "left":
            x_pos = self.winfo_rootx() + 20
            y_pos = self.winfo_rooty() + 90
        elif position == "bottom":
            x_pos = self.winfo_rootx() + max(20, (self.winfo_width() - width) // 2)
            y_pos = self.winfo_rooty() + self.winfo_height() - height - 20
        else:
            x_pos = self.winfo_rootx() + self.winfo_width() - width - 20
            y_pos = self.winfo_rooty() + 90

        x_pos = max(10, min(x_pos, self.winfo_rootx() + self.winfo_width() - width - 10))
        y_pos = max(10, min(y_pos, self.winfo_rooty() + self.winfo_height() - height - 10))
        self._tablegroup_overlay.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    def _close_tablegroup_overlay(self) -> None:
        """Schließt das Tischgruppen-Overlay und meldet es aus der Popup-Registry ab."""
        if self._tablegroup_overlay and self._tablegroup_overlay.winfo_exists():
            popup_id = str(self._tablegroup_overlay)
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)
            self._tablegroup_overlay.destroy()
        self._tablegroup_overlay = None
        self._tg_number_var = None
        self._tg_shift_x_var = None
        self._tg_shift_y_var = None
        self._tg_rotation_var = None
        self._tg_status_var = None
