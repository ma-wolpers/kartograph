"""Plan-CRUD-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Methoden zum Umbenennen, Löschen und Duplizieren von Sitzplänen bereit.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters.gui.dialog_services import messagebox, simpledialog
from app.core.intents.plan_intents import (
    ArchivePlanIntent,
    DeletePlanIntent,
    DuplicatePlanIntent,
    RenamePlanIntent,
    RestorePlanIntent,
)


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
        """Öffnet einen Dialog zum Umbenennen des ausgewählten Sitzplans (v4: RenamePlanIntent).

        Kollisionsprüfung läuft VOR dem Dispatch über
        ``self.plan_repository.plan_name_taken()`` — nicht über ein
        ``try/except FileExistsError`` um ``self._controller.dispatch(...)``
        herum, das hier vorher stand: ``KartographAppController.dispatch()``/
        ``IntentRegistry.dispatch()`` fangen jede Handler-Exception global ab
        und verwerfen den State-Wechsel, eine Exception aus
        ``handle_rename_plan()`` hätte diesen Aufrufer also nie erreicht
        (zusätzlich fängt der Handler ``FileExistsError`` ohnehin schon
        selbst ab). Exaktes Vorbild: ``duplicate_selected_plan_dialog()``
        unten, das dasselbe Pre-Check-Muster bereits richtig macht.
        """
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
            self._controller.dispatch(RenamePlanIntent(plan_path=plan_path, new_name=plan_name, overwrite=overwrite))
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

    def archive_or_restore_selected_plan_dialog(self) -> None:
        """Archiviert den ausgewaehlten Sitzplan oder stellt ihn wieder her.

        Ein archivierter Plan (``entry.is_archived``) wird sofort wiederhergestellt
        (unkritisch, kein Datenverlust). Ein normaler Plan wird nur nach expliziter
        Bestaetigung archiviert, analog zu ``delete_selected_plan_dialog``.
        """
        entry = self._selected_plan_list_entry()
        if not entry:
            self.status_var.set("Kein Sitzplan ausgewaehlt")
            return
        if entry.is_archived:
            self._controller.dispatch(RestorePlanIntent(plan_path=entry.path))
            return
        confirm = messagebox.askyesno(
            "Sitzplan archivieren", f"Moechtest du den Sitzplan '{entry.name}' archivieren?", parent=self
        )
        if not confirm:
            return
        self._controller.dispatch(ArchivePlanIntent(plan_path=entry.path))

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
