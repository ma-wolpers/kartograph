"""Namenfit-CSV-Export-Mixin für das Kartograph-Hauptfenster.

Stellt den interaktiven Export-Dialog bereit, über den das Namensformat
gewählt und eine Namenfit-kompatible CSV-Datei geschrieben wird.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters.gui.dialog_services import filedialog, messagebox
from app.adapters.gui.main_window_constants import NAME_FORMAT_OPTIONS
from app.core.domain.namenfit_csv_export import NamenfitExportError
from app.core.intents.view_intents import ExportNamenfitCsvIntent
from app.infrastructure.exporters.namenfit_csv_exporter import export_namenfit_csv
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class NamenfitExportMixin:
    """Mixin: Konfigurationsdialog für den Namenfit-CSV-Export eines Sitzplans."""

    def export_plan_namenfit_csv_dialog(self) -> None:
        """Öffnet den Namenfit-CSV-Export-Dialog und exportiert bei Bestätigung.

        Konfigurierbare Option: Namensformat (dieselben ``NAME_FORMAT_OPTIONS``
        wie Grid/Sitzplan-Vorschau/PDF-Export). Die Eindeutigkeits-Auflösung
        läuft für diesen Export immer, unabhängig von der App-weiten
        Einstellung — Namenfit setzt eindeutige Namen pro Datei voraus (siehe
        ``build_namenfit_rows()``), anders als die rein kosmetische
        Grid-Anzeige, wo das optional ist.
        """
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geöffnet")
            return

        dialog = self._create_overlay_dialog("Für Namenfit exportieren (CSV)", "420x340")
        container = tui.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        format_var = ui.StringVar(value=self.name_format)
        tui.Label(container, text="Namensformat").pack(anchor="w", pady=(0, 6))
        first_format_button: ui.Widget | None = None
        for option in NAME_FORMAT_OPTIONS:
            button = tui.Radiobutton(container, text=option, value=option, variable=format_var)
            button.pack(anchor="w")
            if first_format_button is None:
                first_format_button = button

        tui.Label(
            container,
            text=(
                "Jede Tischgruppe wird als eigener Spaltenblock exportiert.\n"
                "Bei gleichen Vornamen wird automatisch so viel vom Nachnamen\n"
                "ergänzt, wie zur Eindeutigkeit nötig."
            ),
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

        self._focus_overlay_widget(dialog, first_format_button)

        def do_export() -> None:
            output = filedialog.asksaveasfilename(
                parent=dialog,
                defaultextension=".csv",
                filetypes=[("CSV", "*.csv")],
                initialfile=f"{self.current_plan.meta.name}.csv",
            )
            if not output:
                return
            try:
                export_namenfit_csv(
                    self.current_plan,
                    Path(output),
                    name_format=format_var.get(),
                    disambiguate_colliding_names=True,
                )
                self._controller.dispatch(ExportNamenfitCsvIntent())
                self.status_var.set(f"Namenfit-CSV exportiert: {Path(output).name}")
                dialog.destroy()
            except NamenfitExportError as exc:
                messagebox.showerror("Namenfit-Export nicht möglich", str(exc), parent=dialog)
            except Exception as exc:
                messagebox.showerror("Namenfit-Export fehlgeschlagen", str(exc), parent=dialog)

        button_row = tui.Frame(container)
        button_row.pack(fill="x", pady=(12, 0))
        cancel_button = tui.Button(button_row, text="Abbrechen", command=dialog.destroy)
        cancel_button.pack(side="right")
        self._attach_hover_help(cancel_button, label="Exportdialog ohne Datei schliessen", shortcut="Esc")
        export_button = tui.Button(button_row, text="Exportieren", command=do_export)
        export_button.pack(side="right", padx=(0, 8))
        self._attach_hover_help(export_button, label="Sitzplan als Namenfit-CSV exportieren", shortcut="Enter")
