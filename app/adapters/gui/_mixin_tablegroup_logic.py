"""Tischgruppen-Logik-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Enthält das Auslesen, Parsen und Anwenden der Tischgruppen-Einstellungen
aus dem Overlay-Formular. Die UI-Erstellung des Overlays liegt in
``_mixin_tablegroup.py``.
"""

from __future__ import annotations

from app.adapters.gui.dialog_services import messagebox
from app.core.domain.table_groups import TG_ROTATION_LIMIT
from app.core.usecases.v4.tablegroup_usecases import (
    detect_overlaps_for_tablegroup,
    get_tablegroup_settings,
    normalize_tablegroups,
    set_tablegroup_number_with_cascade,
    set_tablegroup_transforms,
    tablegroup_number_at,
)


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

        normalized = normalize_tablegroups(self.current_plan)
        self._replace_current_plan(normalized)
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
        self._tg_number_var.set(str(settings.number))
        self._tg_shift_x_var.set(f"{settings.shift_x:.2f}")
        self._tg_shift_y_var.set(f"{settings.shift_y:.2f}")
        self._tg_rotation_var.set(f"{settings.rotation:.2f}")
        if self._tg_status_var:
            self._tg_status_var.set(f"Aktive Gruppe: TG {settings.number}")

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
        """Liest die Formulareingaben, wendet die Tischgruppen-Werte an und speichert (v4)."""
        if not self.current_plan or not self.current_plan_path:
            return

        parsed = self._parse_tablegroup_overlay_values()
        if parsed is None:
            return

        target_number, shift_x, shift_y, rotation = parsed
        x, y = self.selection.active_cell()
        next_plan = normalize_tablegroups(self.current_plan)

        source_number = tablegroup_number_at(next_plan, x, y)
        if source_number is None:
            if self._tg_status_var:
                self._tg_status_var.set("Nur Schuelertische gehoeren zu Tischgruppen")
            return

        if source_number != target_number:
            next_plan = set_tablegroup_number_with_cascade(next_plan, source_number, target_number)
            source_number = target_number

        next_plan = set_tablegroup_transforms(next_plan, source_number, shift_x=shift_x, shift_y=shift_y, rotation=rotation)

        teacher_overlap, student_overlap = detect_overlaps_for_tablegroup(next_plan, source_number)
        if teacher_overlap or student_overlap:
            if self._tg_last_changed_field == "shift_y":
                next_plan = set_tablegroup_transforms(next_plan, source_number, shift_y=0.0)
                reset_label = "y-shift"
            elif self._tg_last_changed_field == "rotation":
                next_plan = set_tablegroup_transforms(next_plan, source_number, rotation=0.0)
                reset_label = "rotation"
            else:
                next_plan = set_tablegroup_transforms(next_plan, source_number, shift_x=0.0)
                reset_label = "x-shift"

            teacher_overlap, student_overlap = detect_overlaps_for_tablegroup(next_plan, source_number)
            if teacher_overlap or student_overlap:
                next_plan = set_tablegroup_transforms(next_plan, source_number, shift_x=0.0, shift_y=0.0, rotation=0.0)
                reset_label = "x/y-shift und rotation"
            status = f"Ueberlappung erkannt: {reset_label} auf 0 gesetzt"
        else:
            status = f"TG {source_number} gespeichert"

        self.plan_repository.save_plan(next_plan, self.current_plan_path)
        self._replace_current_plan(next_plan)
        if self._tg_status_var:
            self._tg_status_var.set(status)

        self.redraw_grid()
        self._refresh_details_panel()
        self._refresh_tablegroup_overlay()
