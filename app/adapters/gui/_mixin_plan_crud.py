"""Plan-CRUD-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Methoden zum Umbenennen, Löschen und Duplizieren von Sitzplänen bereit.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters.gui.dialog_services import messagebox, simpledialog
from app.core.intents.plan_intents import DeletePlanIntent, DuplicatePlanIntent, RenamePlanIntent


class PlanCrudMixin:
    """Mixin: Sitzplan umbenennen, löschen, duplizieren (v4 intents)."""

    def _selected_plan_list_entry(self):
        """Gibt den aktuell in der Planliste ausgewählten PlanListEntry zurück oder None."""
        self._ensure_list_selection()
        selected = self.plan_listbox.curselection()
        if not selected:
            return None
        index = int(selected[0])
        if index < 0 or index >= len(self._plan_index):
            return None
        return self._plan_index[index]

    def _default_duplicate_name(self, source_name: str) -> str:
        """Gibt den Standardnamen für eine Kopie zurück.

        Args:
            source_name: Name des Quellplans, von dem die Kopie abgeleitet wird.
        """
        base = source_name.strip() or "Neuer Sitzplan"
        return f"{base} Kopie"

    def rename_selected_plan_dialog(self) -> None:
        """Öffnet einen Dialog zum Umbenennen des ausgewählten Sitzplans."""
        entry = self._selected_plan_list_entry()
        if not entry:
            self.status_var.set("Kein Sitzplan ausgewaehlt")
            return
        plan_path = entry.path
        while True:
            plan_name = simpledialog.askstring(
                "Sitzplan umbenennen", "Neuer Name der Lerngruppe:", parent=self, initialvalue=entry.name
            )
            if plan_name is None:
                return
            if not plan_name.strip():
                messagebox.showerror("Fehler", "Bitte gib einen Namen ein.", parent=self)
                continue
            try:
                self._controller.dispatch(RenamePlanIntent(plan_path=plan_path, new_name=plan_name))
                return
            except FileExistsError:
                overwrite = messagebox.askyesnocancel(
                    "Datei existiert bereits", "Für diese Lerngruppe existiert bereits ein Plan. Überschreiben?", parent=self
                )
                if overwrite is None:
                    return
                if overwrite:
                    self._controller.dispatch(RenamePlanIntent(plan_path=plan_path, new_name=plan_name))
                    return
                continue
            except Exception as exc:
                messagebox.showerror("Fehler", f"Sitzplan konnte nicht umbenannt werden:\n{exc}", parent=self)
                return

    def delete_selected_plan_dialog(self) -> None:
        """Öffnet einen Bestätigungs-Dialog zum Löschen des ausgewählten Sitzplans."""
        entry = self._selected_plan_list_entry()
        if not entry:
            self.status_var.set("Kein Sitzplan ausgewaehlt")
            return
        plan_path = entry.path
        confirm = messagebox.askyesno(
            "Sitzplan loeschen", f"Moechtest du den Sitzplan '{entry.name}' wirklich loeschen?", parent=self
        )
        if not confirm:
            return
        self._controller.dispatch(DeletePlanIntent(plan_path=plan_path))

    def duplicate_selected_plan_dialog(self) -> None:
        """Öffnet einen Dialog zum Duplizieren des ausgewählten Sitzplans (v4: DuplicatePlanIntent)."""
        entry = self._selected_plan_list_entry()
        if not entry:
            self.status_var.set("Kein Sitzplan ausgewaehlt")
            return
        plan_path = entry.path
        suggested_name = self._default_duplicate_name(entry.name)
        while True:
            plan_name = simpledialog.askstring(
                "Sitzplan duplizieren", "Name der Lerngruppe:", parent=self, initialvalue=suggested_name
            )
            if plan_name is None:
                return
            if not plan_name.strip():
                messagebox.showerror("Fehler", "Bitte gib einen Namen ein.", parent=self)
                continue
            overwrite = False
            if self.plan_repository.plan_name_taken(plan_path, plan_name):
                choice = messagebox.askyesnocancel(
                    "Datei existiert bereits", "Für diese Lerngruppe existiert bereits ein Plan. Überschreiben?", parent=self
                )
                if choice is None:
                    return
                if not choice:
                    continue
                overwrite = True
            self._controller.dispatch(DuplicatePlanIntent(plan_path=plan_path, new_name=plan_name, overwrite=overwrite))
            return
