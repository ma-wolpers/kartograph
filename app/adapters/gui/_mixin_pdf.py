"""PDF-Export-Mixin für das Kartograph-Hauptfenster.

Stellt den interaktiven PDF-Export-Dialog bereit, über den Perspektive,
Notenansicht, Symbole, Farbpunkte und Legende konfiguriert werden können.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters.gui.dialog_services import filedialog, messagebox
from app.core.intents.view_intents import ExportPdfIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class PdfMixin:
    """Mixin: Konfigurationsdialog für den PDF-Export eines Sitzplans."""

    def export_plan_pdf_dialog(self) -> None:
        """Öffnet den PDF-Export-Dialog und exportiert den aktuellen Plan bei Bestätigung.

        Konfigurierbare Optionen:
        - Perspektive (Lehrertisch unten / oben)
        - Notenansicht (keine / nur Gesamtnote / inkl. Klammernoten)
        - Welche Symbole exportiert werden (nur tatsächlich vorhandene)
        - Farbpunkte und Legendenseite ein-/ausblenden
        """
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geöffnet")
            return

        dialog = self._create_overlay_dialog("PDF exportieren", "520x680")
        container = tui.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        mode_var = ui.StringVar(value="teacher_bottom")
        grade_mode_var = ui.StringVar(value="none")
        include_color_markers_var = ui.BooleanVar(value=False)
        include_legend_var = ui.BooleanVar(value=False)
        available_symbols = self._collect_export_symbols(self.current_plan)
        symbol_vars: dict[str, ui.BooleanVar] = {}

        tui.Label(container, text="Ansicht wählen").pack(anchor="w", pady=(0, 6))
        first_mode_button = tui.Radiobutton(
            container,
            text="Lehrertisch unten (Standard)",
            value="teacher_bottom",
            variable=mode_var,
        )
        first_mode_button.pack(anchor="w")
        tui.Radiobutton(
            container,
            text="Lehrertisch oben (180° Perspektive)",
            value="teacher_top",
            variable=mode_var,
        ).pack(anchor="w", pady=(4, 10))

        tui.Label(container, text="Noten").pack(anchor="w", pady=(0, 6))
        tui.Radiobutton(container, text="Keine Noten (Standard)", value="none", variable=grade_mode_var).pack(anchor="w")
        tui.Radiobutton(container, text="Nur fertige Gesamtnote", value="final_only", variable=grade_mode_var).pack(anchor="w", pady=(4, 0))
        tui.Radiobutton(container, text="Gesamtnote inkl. Klammernoten", value="include_provisional", variable=grade_mode_var).pack(anchor="w", pady=(4, 10))

        tui.Label(container, text="Symbole (nur im Plan vorhandene)").pack(anchor="w", pady=(0, 6))
        symbols_frame = tui.Frame(container)
        symbols_frame.pack(fill="x")
        if available_symbols:
            for symbol_name in available_symbols:
                var = ui.BooleanVar(value=True)
                symbol_vars[symbol_name] = var
                tui.Checkbutton(symbols_frame, text=symbol_name, variable=var).pack(anchor="w", pady=(0, 2))
            symbol_button_row = tui.Frame(container)
            symbol_button_row.pack(fill="x", pady=(4, 8))
            all_symbols_button = tui.Button(
                symbol_button_row,
                text="Alle Symbole",
                command=lambda: [var.set(True) for var in symbol_vars.values()],
            )
            all_symbols_button.pack(side="left")
            self._attach_hover_help(all_symbols_button, label="Alle verfuegbaren Symbole fuer Export aktivieren", shortcut=None)
            no_symbols_button = tui.Button(
                symbol_button_row,
                text="Keine Symbole",
                command=lambda: [var.set(False) for var in symbol_vars.values()],
            )
            no_symbols_button.pack(side="left", padx=(6, 0))
            self._attach_hover_help(no_symbols_button, label="Alle Symbolauswahlen deaktivieren", shortcut=None)
        else:
            tui.Label(symbols_frame, text="Im Plan sind aktuell keine Symbole vorhanden.").pack(anchor="w", pady=(0, 8))

        tui.Checkbutton(container, text="Farbige Punkte mit exportieren", variable=include_color_markers_var).pack(anchor="w", pady=(0, 6))
        tui.Checkbutton(container, text="Legende auf weiterer Seite exportieren", variable=include_legend_var).pack(anchor="w", pady=(0, 6))

        self._focus_overlay_widget(dialog, first_mode_button)

        def do_export() -> None:
            selected_symbols = {symbol_name for symbol_name, var in symbol_vars.items() if var.get()}
            output = filedialog.asksaveasfilename(
                parent=dialog,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile=f"{self.current_plan.meta.name}.pdf",
            )
            if not output:
                return
            try:
                self.pdf_exporter.export_plan(
                    self.current_plan,
                    Path(output),
                    mode_var.get(),
                    grade_mode=grade_mode_var.get(),
                    visible_symbols=selected_symbols,
                    include_color_markers=include_color_markers_var.get(),
                    include_legend_page=include_legend_var.get(),
                )
                self._controller.dispatch(ExportPdfIntent())
                self.status_var.set(f"PDF exportiert: {Path(output).name}")
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("PDF-Export fehlgeschlagen", str(exc), parent=dialog)

        button_row = tui.Frame(container)
        button_row.pack(fill="x", pady=(12, 0))
        cancel_button = tui.Button(button_row, text="Abbrechen", command=dialog.destroy)
        cancel_button.pack(side="right")
        self._attach_hover_help(cancel_button, label="Exportdialog ohne Datei schliessen", shortcut="Esc")
        export_button = tui.Button(button_row, text="Exportieren", command=do_export)
        export_button.pack(side="right", padx=(0, 8))
        self._attach_hover_help(export_button, label="Sitzplan als PDF exportieren", shortcut="Enter")
