"""Tischgruppen-Logik-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Enthält das Auslesen, Parsen und Anwenden der Tischgruppen-Einstellungen
aus dem Overlay-Formular. Die UI-Erstellung des Overlays liegt in
``_mixin_tablegroup.py``.
"""

from __future__ import annotations

from app.adapters.gui.dialog_services import messagebox
from app.core.domain.table_groups import TG_ROTATION_LIMIT
from app.core.intents.tablegroup_intents import ApplyTablegroupSettingsIntent
from app.core.usecases.v4.tablegroup_usecases import get_tablegroup_settings, tablegroup_number_at


class TablegroupLogicMixin:
    """Mixin: Lesen, Validieren und Anwenden von Tischgruppen-Werten (v4)."""

    def _refresh_tablegroup_overlay(self) -> None:
        """Befüllt das Overlay-Formular mit den Werten der aktuell ausgewählten Tischgruppe."""
        if not self._tablegroup_overlay or not self._tablegroup_overlay.winfo_exists():
            return
        if not self.current_plan or not self.current_plan_path:
            return
        if not self._tg_number_var or not self._tg_shift_x_var or not self._tg_shift_y_var or not self._tg_rotation_var:
            return

        x, y = self.selection.active_cell()
        number = tablegroup_number_at(self.current_plan, x, y)
        if number is None:
            self._tg_number_var.set("")
            self._tg_shift_x_var.set("0.00")
            self._tg_shift_y_var.set("0.00")
            self._tg_rotation_var.set("0.00")
            if self._tg_status_var:
                self._tg_status_var.set("Waehle einen Schuelertisch aus")
            return

        settings = get_tablegroup_settings(self.current_plan, number)
        if settings is None:
            return
        self._tg_number_var.set(str(settings.group_id))
        self._tg_shift_x_var.set(f"{settings.shift_x:.2f}")
        self._tg_shift_y_var.set(f"{settings.shift_y:.2f}")
        self._tg_rotation_var.set(f"{settings.rotation:.2f}")
        if self._tg_status_var:
            self._tg_status_var.set(f"Aktive Gruppe: TG {settings.group_id}")

    def _parse_tablegroup_overlay_values(self) -> tuple[int, float, float, float] | None:
        """Liest und validiert die Formulareingaben des Tischgruppen-Overlays.

        Returns:
            Tupel (number, shift_x, shift_y, rotation) bei gültigen Werten, sonst None.
        """
        if not self._tg_number_var or not self._tg_shift_x_var or not self._tg_shift_y_var or not self._tg_rotation_var:
            return None

        try:
            number = int(self._tg_number_var.get().strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "TG-Nummer muss eine ganze Zahl sein.", parent=self)
            return None
        if number <= 0:
            messagebox.showerror("Ungueltige Eingabe", "TG-Nummer muss groesser als 0 sein.", parent=self)
            return None

        try:
            shift_x = float(self._tg_shift_x_var.get().strip())
            shift_y = float(self._tg_shift_y_var.get().strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "x-shift und y-shift muessen Zahlen sein.", parent=self)
            return None
        if not (-0.5 < shift_x < 0.5) or not (-0.5 < shift_y < 0.5):
            messagebox.showerror("Ungueltige Eingabe", "x-shift und y-shift muessen strikt zwischen -0.5 und 0.5 liegen.", parent=self)
            return None

        try:
            rotation = float(self._tg_rotation_var.get().strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "Rotation muss eine Zahl sein.", parent=self)
            return None
        if rotation < -TG_ROTATION_LIMIT or rotation > TG_ROTATION_LIMIT:
            messagebox.showerror("Ungueltige Eingabe", f"Rotation muss zwischen {-TG_ROTATION_LIMIT:.0f} und {TG_ROTATION_LIMIT:.0f} liegen.", parent=self)
            return None

        return number, shift_x, shift_y, rotation

    def _apply_tablegroup_overlay_values(self) -> None:
        """Liest die Formulareingaben und übernimmt die Tischgruppen-Werte als einen Undo-Schritt (v4)."""
        if not self.current_plan or not self.current_plan_path:
            return

        parsed = self._parse_tablegroup_overlay_values()
        if parsed is None:
            return

        number, shift_x, shift_y, rotation = parsed
        x, y = self.selection.active_cell()
        self._controller.dispatch(
            ApplyTablegroupSettingsIntent(
                x=x,
                y=y,
                number=number,
                shift_x=shift_x,
                shift_y=shift_y,
                rotation=rotation,
                last_changed_field=self._tg_last_changed_field,
            )
        )
        self._refresh_tablegroup_overlay()
        if self._tg_status_var:
            self._tg_status_var.set(self._controller.state.status_message)
