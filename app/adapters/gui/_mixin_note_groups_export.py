"""Dialog "Gruppen exportieren": Gruppen einer Notizspalte als PDF (Mixin).

Wer in welcher Gruppe steht und wie das Blatt aussieht, entscheidet allein
``core/domain/note_groups.build_group_sheet``; gezeichnet wird in
``infrastructure/exporters/note_groups_pdf_exporter``. Hier stehen nur die
Optionen (Entscheidungen der Nutzerin 2026-11-22):

- Kästchen-Überschrift in drei Stufen (``GROUP_LABEL_MODES``: Notiz anzeigen,
  geheim zufällig nummeriert, geheim ohne Überschrift),
- Blattausrichtung (``PAGE_ORIENTATIONS``),
- Personen ohne Eintrag als eigenes Kästchen -- die Frage erscheint nur, wenn es welche gibt.
"""

from __future__ import annotations

import random
from pathlib import Path

from app.adapters.gui._local_keys import ENTER, ESCAPE, bind_action, dialog_keys
from app.adapters.gui.dialog_services import filedialog, messagebox
from app.core.domain.note_groups import (
    DEFAULT_GROUP_LABEL_MODE,
    GROUP_LABEL_MODES,
    NoteSource,
    build_group_sheet,
    count_without_entry,
)
from app.core.domain.page_orientation import DEFAULT_PAGE_ORIENTATION, PAGE_ORIENTATIONS
from app.core.intents.view_intents import ExportNoteGroupsPdfIntent
from app.infrastructure.exporters.note_groups_pdf_exporter import export_group_sheet
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import Checkbox, RadioGroup


class NoteGroupsExportMixin:
    """Mixin: Exportdialog für die Gruppen einer Spalte des Notizenbereichs."""

    def _group_sheet_for(self, source: NoteSource, column_title: str, label_mode: str, include_without: bool):
        """Gruppenblatt mit den Namens-Einstellungen des Fensters (eine Stelle für Dialog und Export)."""
        return build_group_sheet(
            self.current_plan, source, column_title=column_title, label_mode=label_mode,
            include_without=include_without, name_format=self.name_format,
            disambiguate=self.disambiguate_colliding_names, rng=random.Random(),
        )

    def export_note_groups_dialog(self, column_key: str) -> bool:
        """Öffnet den Exportdialog für die Gruppen der Spalte *column_key*.

        Args:
            column_key: Spaltenschlüssel im Notizenbereich (allgemeine Notizen,
                Ja/Nein oder eigene Notizspalte).

        Returns:
            ``True``, wenn der Dialog geöffnet wurde (``False``: kein Plan oder keine Notizspalte).
        """
        source = self._note_source_of(column_key) if self.current_plan else None
        if source is None:
            return False
        column_title = self._doc_column_label(column_key)
        without = count_without_entry(self.current_plan, source)
        overview = self._group_sheet_for(source, column_title, DEFAULT_GROUP_LABEL_MODE, include_without=False)

        dialog = self._create_overlay_dialog(f"Gruppen exportieren: {column_title}", "460x440")
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        people = len({name for box in overview.boxes for name in box.names})
        tui.Label(frame, text=f"{len(overview.boxes)} Gruppen · {people} Personen").pack(anchor="w", pady=(0, 10))
        label_var = ui.StringVar(value=DEFAULT_GROUP_LABEL_MODE)
        labels = RadioGroup(frame, title="Überschrift der Kästchen", variable=label_var, options=GROUP_LABEL_MODES)
        labels.pack(anchor="w", pady=(0, 10))
        orientation_var = ui.StringVar(value=DEFAULT_PAGE_ORIENTATION)
        RadioGroup(frame, title="Blatt", variable=orientation_var, options=PAGE_ORIENTATIONS).pack(anchor="w", pady=(0, 10))
        without_var = ui.BooleanVar(value=True)
        if without:
            text = f"{without} {'Person' if without == 1 else 'Personen'} ohne Eintrag als eigenes Kästchen"
            Checkbox(frame, text=text, variable=without_var).pack(anchor="w", pady=(0, 6))

        def do_export() -> None:
            output = filedialog.asksaveasfilename(
                parent=dialog, defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                initialfile=f"{self.current_plan.meta.name} – Gruppen {column_title}.pdf",
            )
            if not output:
                return
            sheet = self._group_sheet_for(source, column_title, label_var.get(), bool(without) and without_var.get())
            try:
                export_group_sheet(sheet, Path(output), orientation_var.get())
            except Exception as exc:
                messagebox.showerror("Gruppen-Export fehlgeschlagen", str(exc), parent=dialog)
                return
            self._controller.dispatch(ExportNoteGroupsPdfIntent())
            self.status_var.set(f"Gruppen exportiert: {Path(output).name}")
            dialog.destroy()

        bind_action(dialog_keys(dialog), ENTER, do_export, binding_id="dialog.confirm")
        button_row = tui.Frame(frame)
        button_row.pack(fill="x", pady=(12, 0))
        cancel_button = tui.Button(button_row, text="Abbrechen", command=dialog.destroy)
        cancel_button.pack(side="right")
        self._attach_hover_help(cancel_button, label="Exportdialog ohne Datei schliessen", shortcut=ESCAPE)
        export_button = tui.Button(button_row, text="Exportieren", command=do_export)
        export_button.pack(side="right", padx=(0, 8))
        self._attach_hover_help(export_button, label="Gruppen als PDF exportieren", shortcut=ENTER)
        self._focus_overlay_widget(dialog, labels.first_button)
        return True
