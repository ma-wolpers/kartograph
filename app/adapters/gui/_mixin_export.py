"""Export-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Stellt Symbol-Exporthelfer, den Symbolfilterdialog, Overlay-Dialog-Infrastruktur
sowie Plan-Speichern und periodisches Backup bereit.
"""

from __future__ import annotations

import dataclasses

from app.adapters.gui.main_window_constants import DEFAULT_PERIODIC_BACKUP_INTERVAL_MS
from app.core.domain.models_v4 import SeatingPlan
from app.core.intents.view_intents import UpdateSettingsIntent
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class ExportMixin:
    """Mixin: Symbol-Exportliste, Symbolfilterdialog, Overlay-Infrastruktur, Speichern und Backup."""

    def _collect_export_symbols(self, plan: SeatingPlan) -> list[str]:
        """Gibt alle im Plan tatsächlich vorhandenen Symbole in Katalog-Reihenfolge zurück.

        Berücksichtigt Dokumentations-Einträge vorrangig, fällt auf Raster-Symbole zurück.

        Args:
            plan: Sitzplan dessen Symbole gesammelt werden.
        """
        seen: set[str] = set()
        for student in plan.classroom.students:
            if not student.is_named():
                continue
            summary = summarize_latest_symbols(plan, student.student_id)
            source = summary if summary else student.diagnostic.symbols
            for symbol_name, raw_count in source.items():
                try:
                    count = int(raw_count)
                except (TypeError, ValueError):
                    continue
                if count > 0:
                    seen.add(str(symbol_name))
        ordered: list[str] = []
        for symbol_name in self.symbol_catalog:
            if symbol_name in seen:
                ordered.append(symbol_name)
        for symbol_name in sorted(seen, key=lambda item: item.lower()):
            if symbol_name not in ordered:
                ordered.append(symbol_name)
        return ordered

    def open_grid_symbol_filter_dialog(self) -> None:
        """Öffnet einen Dialog zur Auswahl der im Raster angezeigten Symbole.

        Speichert die Auswahl persistent in den Einstellungen und zeichnet das Raster neu.
        """
        dialog = self._create_overlay_dialog("Sichtbare Symbole", "420x480")
        container = tui.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)
        tui.Label(container, text="Welche Symbole sollen im Sitzraster angezeigt werden?").pack(anchor="w", pady=(0, 8))
        vars_by_symbol: dict[str, ui.BooleanVar] = {}
        for symbol in self.symbol_catalog:
            var = ui.BooleanVar(value=symbol in self._grid_visible_symbols)
            vars_by_symbol[symbol] = var
            tui.Checkbutton(container, text=symbol, variable=var).pack(anchor="w", pady=(0, 2))

        def apply_filter() -> None:
            selected = [symbol for symbol, var in vars_by_symbol.items() if var.get()]
            if not selected:
                selected = list(self.symbol_catalog)
            self._grid_visible_symbols = set(selected)
            self._controller.dispatch(UpdateSettingsIntent(
                settings=dataclasses.replace(self._controller.state.settings, grid_visible_symbols=tuple(selected))
            ))
            dialog.destroy()
            self.redraw_grid()
            self._refresh_details_panel()

        button_row = tui.Frame(container)
        button_row.pack(fill="x", pady=(10, 0))
        all_button = tui.Button(button_row, text="Alle", command=lambda: [var.set(True) for var in vars_by_symbol.values()])
        all_button.pack(side="left")
        self._attach_hover_help(all_button, label="Alle Symbole sichtbar markieren", shortcut=None)
        save_button = tui.Button(button_row, text="Speichern", command=apply_filter)
        save_button.pack(side="right")
        self._attach_hover_help(save_button, label="Sichtbarkeitsauswahl speichern", shortcut="Enter")

    def _create_overlay_dialog(self, title: str, geometry: str) -> ui.Toplevel:
        """Erstellt ein modales Toplevel-Fenster mit Popup-Tracking und Escape-Binding.

        Args:
            title: Fenstertitel.
            geometry: Geometrie-String im Format ``"BREITExHÖHE"``.

        Returns:
            Das neue, fokussierte Toplevel-Fenster.
        """
        dialog = ui.Toplevel(self)
        dialog.title(title)
        dialog.geometry(geometry)
        dialog.transient(self)
        self._track_popup_window(dialog)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: self._destroy_tracked_dialog(dialog))
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._destroy_tracked_dialog(dialog))
        self._focus_overlay_widget(dialog, dialog)
        return dialog

    def _destroy_tracked_dialog(self, dialog: ui.Toplevel) -> None:
        """Schließt ein getrackte Dialog-Fenster und entfernt es aus der Popup-Registry.

        Args:
            dialog: Das zu schließende Toplevel-Fenster.
        """
        popup_id = str(dialog)
        self._popup_registry.close_popup(popup_id)
        self._tracked_popup_ids.discard(popup_id)
        dialog.destroy()

    def _focus_overlay_widget(self, dialog: ui.Toplevel, widget: ui.Widget) -> None:
        """Setzt nach einem kurzen Delay den Fokus auf ``widget`` innerhalb von ``dialog``.

        Args:
            dialog: Elterndialog, der geprüft wird ob er noch existiert.
            widget: Widget das den Fokus erhalten soll.
        """
        def _apply_focus() -> None:
            if not dialog.winfo_exists() or not widget.winfo_exists():
                return
            dialog.focus_force()
            widget.focus_set()

        dialog.after(1, _apply_focus)

    def _save_current_plan(self, status: str) -> None:
        """Speichert den aktuellen Plan auf Disk und aktualisiert die Statuszeile.

        Args:
            status: Statusmeldung die nach erfolgreichem Speichern angezeigt wird.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        try:
            self.plan_repository.save_plan(self.current_plan, self.current_plan_path)
            self.status_var.set(f"Gespeichert: {status}")
            self.refresh_plan_list()
        except Exception as exc:
            self.status_var.set(f"Speichern fehlgeschlagen: {exc}")

    def _periodic_backup_tick(self) -> None:
        """Erstellt ein zeitgestempeltes Backup-Snapshot und plant den nächsten Tick.

        Fehler werden stillschweigend ignoriert damit das Backup den Editor nicht stört.
        """
        try:
            if self.current_plan and self.current_plan_path:
                self.plan_repository.backup_plan_snapshot(self.current_plan, self.current_plan_path)
        except Exception:
            pass
        finally:
            if self.winfo_exists():
                self.after(DEFAULT_PERIODIC_BACKUP_INTERVAL_MS, self._periodic_backup_tick)
