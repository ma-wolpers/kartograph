"""Plan-Listen-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Methoden zum Aktualisieren der Planliste, zum Öffnen von Plänen
und zum Erstellen neuer Pläne bereit.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.adapters.gui.dialog_services import messagebox, simpledialog
from app.adapters.gui.main_window_constants import LOGGER
from app.application.plan_listing import build_plan_list
from app.core.intents.plan_intents import CreatePlanIntent, OpenPlanIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui


class PlanListMixin:
    """Mixin: Planliste aktualisieren, Pläne öffnen und neu erstellen (v4)."""

    def refresh_plan_list(self) -> None:
        """Lädt alle Pläne aus dem Sitzplan-Ordner neu und aktualisiert die Listbox."""
        started = time.perf_counter()
        LOGGER.info("refresh_plan_list started")
        include_archived = self._controller.state.settings.show_archived_plans
        try:
            plan_list = build_plan_list(self.plan_repository, self.plans_dir, include_archived=include_archived)
        except Exception as exc:
            self.status_var.set(f"Planliste konnte nicht geladen werden: {exc}")
            LOGGER.exception("refresh_plan_list: list_plans failed")
            plan_list = []

        if not plan_list:
            try:
                self.plan_repository.create_new_plan(self.plans_dir, "Neuer Sitzplan")
                plan_list = build_plan_list(self.plan_repository, self.plans_dir, include_archived=include_archived)
            except Exception as exc:
                self.status_var.set(f"Konnte keinen Startplan erstellen: {exc}")

        self._apply_plan_list(plan_list)
        LOGGER.info("refresh_plan_list finished in %.3fs with %d plans", time.perf_counter() - started, len(plan_list))

    def open_selected_plan_from_list(self) -> None:
        """Öffnet den in der Planliste aktuell ausgewählten Plan."""
        self._ensure_list_selection()
        selected = self.plan_listbox.curselection()
        if not selected:
            return
        index = int(selected[0])
        if index < 0 or index >= len(self._plan_index):
            return
        plan_path = self._plan_index[index].path
        self.open_plan(plan_path)

    def open_plan(self, plan_path: Path) -> None:
        """Lädt einen Sitzplan und wechselt in die Rasteransicht (v4).

        Args:
            plan_path: Dateipfad des zu ladenden Sitzplans.
        """
        started = time.perf_counter()
        LOGGER.info("open_plan started: %s", plan_path)

        self._flush_pending_name_save()
        self._flush_pending_plan_save()

        # Pre-load for out-of-bounds check
        try:
            plan = self.plan_repository.load_plan(plan_path)
        except Exception as exc:
            LOGGER.exception("open_plan failed while loading %s", plan_path)
            messagebox.showerror("Fehler beim Öffnen", str(exc))
            return

        out_of_bounds = self._count_out_of_bounds_desks(plan)
        if out_of_bounds > 0:
            messagebox.showwarning(
                "Plan nur teilweise darstellbar",
                f"{out_of_bounds} Schuelertische liegen ausserhalb des aktuellen Canvas-Bereichs (+/-{self.canvas_radius}) und koennen nicht angezeigt werden.",
                parent=self,
            )

        self._controller.dispatch(OpenPlanIntent(plan_path=plan_path))
        LOGGER.info("open_plan finished in %.3fs", time.perf_counter() - started)

    def create_new_plan_dialog(self) -> None:
        """Öffnet einen Dialog zum Erstellen eines neuen Sitzplans (v4)."""
        while True:
            plan_name = simpledialog.askstring("Neuer Sitzplan", "Name der Lerngruppe:", parent=self)
            if plan_name is None:
                return
            self._flush_pending_name_save()
            self._flush_pending_plan_save()
            try:
                self._controller.dispatch(CreatePlanIntent(name=plan_name))
                return
            except FileExistsError:
                overwrite = messagebox.askyesnocancel(
                    "Datei existiert bereits",
                    "Für diese Lerngruppe existiert bereits ein Plan. Überschreiben?",
                    parent=self,
                )
                if overwrite is None:
                    return
                if overwrite:
                    self._controller.dispatch(CreatePlanIntent(name=plan_name))
                    return
                continue
            except Exception as exc:
                messagebox.showerror("Fehler", f"Neuer Sitzplan konnte nicht erstellt werden:\n{exc}")
                return
