"""PNG-ZIP-Export-Mixin für das Kartograph-Hauptfenster.

Stellt den interaktiven Export-Dialog bereit, über den ein ZIP-Archiv mit
je einem transparenten Sitzkärtchen-PNG pro benanntem Schüler geschrieben
wird. Keine Konfigurationsoptionen (rein geometrisch, kein Namensformat/
keine Symbolauswahl nötig) — bewusst minimaler als PDF-/CSV-Export-Dialog.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters.gui.dialog_services import filedialog, messagebox
from app.core.domain.student_png_export import StudentPngExportError
from app.core.intents.view_intents import ExportStudentPngsZipIntent
from app.infrastructure.exporters.student_png_zip_exporter import export_student_pngs_zip
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets as tui


class StudentPngExportMixin:
    """Mixin: Export-Dialog für PNG-Sitzkärtchen je Schüler (ZIP-Archiv)."""

    def export_plan_student_pngs_dialog(self) -> None:
        """Öffnet den Export-Dialog und schreibt bei Bestätigung das ZIP-Archiv.

        Keine Konfigurationsoptionen: der Dialog zeigt nur eine kurze
        Erklärung dessen, was exportiert wird, sowie Exportieren/Abbrechen —
        Bildgröße, Farben und Dateinamensschema sind fest (siehe
        ``student_png_renderer.py``/``student_png_export.py``), das wäre
        für diesen Export unnötige Konfigurationskomplexität im Dialog.
        """
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geöffnet")
            return

        dialog = self._create_overlay_dialog("Sitzkärtchen exportieren (ZIP)", "420x260")
        container = tui.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        tui.Label(
            container,
            text=(
                "Erzeugt ein ZIP-Archiv mit einer kleinen, transparenten\n"
                "PNG-Grafik je benanntem Schüler: alle Tische weiß, der\n"
                "Lehrertisch orange, der eigene Tisch des jeweiligen\n"
                "Schülers kräftig blau. Keine Namen, Noten, Symbole oder\n"
                "Legende auf der Grafik.\n\n"
                "Die Dateinamen im Archiv folgen der üblichen Vornamens-\n"
                "Logik (Spitzname überschreibt offiziellen Vornamen, bei\n"
                "Namensvettern wird so viel vom Nachnamen ergänzt, wie\n"
                "zur Eindeutigkeit nötig ist)."
            ),
            justify="left",
        ).pack(anchor="w")

        def do_export() -> None:
            output = filedialog.asksaveasfilename(
                parent=dialog,
                defaultextension=".zip",
                filetypes=[("ZIP", "*.zip")],
                initialfile=f"{self.current_plan.meta.name}.zip",
            )
            if not output:
                return
            try:
                count = export_student_pngs_zip(self.current_plan, Path(output))
                self._controller.dispatch(ExportStudentPngsZipIntent())
                self.status_var.set(f"{count} Sitzkärtchen exportiert: {Path(output).name}")
                dialog.destroy()
            except StudentPngExportError as exc:
                messagebox.showerror("PNG-Export nicht möglich", str(exc), parent=dialog)
            except Exception as exc:
                messagebox.showerror("PNG-Export fehlgeschlagen", str(exc), parent=dialog)

        dialog.bind("<Return>", lambda _e: do_export())

        button_row = tui.Frame(container)
        button_row.pack(fill="x", pady=(16, 0))
        cancel_button = tui.Button(button_row, text="Abbrechen", command=dialog.destroy)
        cancel_button.pack(side="right")
        self._attach_hover_help(cancel_button, label="Exportdialog ohne Datei schliessen", shortcut="Esc")
        export_button = tui.Button(button_row, text="Exportieren", command=do_export)
        export_button.pack(side="right", padx=(0, 8))
        self._attach_hover_help(export_button, label="Sitzkaertchen als ZIP-Archiv exportieren", shortcut="Enter")
        self._focus_overlay_widget(dialog, export_button)
