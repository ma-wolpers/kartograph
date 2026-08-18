"""Docs-Ansicht-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Steuert den Wechsel zwischen Listenansicht, Raster- und Dokumentations-Oberfläche
sowie Hilfsmethoden für Dokumentations-Text, Spaltenköpfe, Sortierstatus und
heutige Datumsauswahl.
"""

from __future__ import annotations

from pathlib import Path

from app.core.intents.navigation_intents import ClearSelectionIntent
from app.core.intents.session_intents import GoToTodayIntent
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui


class DocsViewMixin:
    """Mixin: Ansichtswechsel, Dokumentations-Text-Helfer und Dokumentations-Sortierung."""

    def _ensure_list_selection(self, preferred_path: Path | None = None) -> None:
        """Stellt sicher, dass in der Planliste eine Zeile ausgewählt ist.

        Args:
            preferred_path: Pfad, der bevorzugt ausgewählt werden soll. Wenn ``None``,
                wird die aktuelle Auswahl beibehalten oder auf Index 0 zurückgefallen.
        """
        if not self._plan_index:
            return

        desired_index = 0
        if preferred_path is not None:
            for idx, entry in enumerate(self._plan_index):
                if entry.path == preferred_path:
                    desired_index = idx
                    break
        elif self.plan_listbox.curselection():
            desired_index = int(self.plan_listbox.curselection()[0])

        desired_index = max(0, min(desired_index, len(self._plan_index) - 1))
        self.plan_listbox.selection_clear(0, ui.END)
        self.plan_listbox.selection_set(desired_index)
        self.plan_listbox.activate(desired_index)
        self.plan_listbox.see(desired_index)

    def show_plan_list_view(self) -> None:
        """Wechselt zur Planlisten-Ansicht und gibt der Listbox den Fokus."""
        self._close_tablegroup_overlay()
        self.editor_view.pack_forget()
        self.list_view.pack(fill="both", expand=True)
        self._ensure_list_selection(preferred_path=self.current_plan_path)
        self.plan_listbox.focus_set()

    def _return_to_plan_list(self) -> None:
        """Verlässt den Editor zurück zur Planliste und schließt den offenen Plan im AppState.

        Einziger Ort, der beide Rückwege (Escape und der Button/Menüpunkt
        "Zur Planliste") zusammenführt — hält so ``AppState.current_plan``
        mit der sichtbaren Ansicht synchron, statt es (wie zuvor) offen zu
        lassen, obwohl der Editor gar nicht mehr zu sehen ist.
        """
        self._flush_pending_name_save()
        self.show_plan_list_view()
        self._hide_details()
        self._controller.dispatch(ClearSelectionIntent())

    def show_editor_view(self) -> None:
        """Wechselt zur Editor-Ansicht (Raster oder Doku, je nach letzter Oberfläche)."""
        self.list_view.pack_forget()
        self.editor_view.pack(fill="both", expand=True)
        if self._editor_surface == "docs":
            self.show_documentation_surface()
        else:
            self.show_grid_surface()
        self._position_tablegroup_overlay()

    def show_grid_surface(self) -> None:
        """Zeigt die Rasteroberfläche und blendet Doku-Container und Details aus.

        Reine Oberflächen-Umschaltung; ``self._editor_surface`` wird von
        ``apply_state`` aus ``AppState.editor_surface`` gespiegelt (v4: SetEditorSurfaceIntent).
        """
        self.docs_container.pack_forget()
        if not self.editor_topbar.winfo_ismapped():
            self.editor_topbar.pack(fill="x", padx=12, pady=(12, 8))
        self.grid_stack.pack_forget()
        self.details_container.pack_forget()
        self._apply_details_overlay_position()
        self.canvas.focus_set()

    def show_documentation_surface(self) -> None:
        """Zeigt die Dokumentations-Oberfläche, aktualisiert die Tabelle und setzt den Fokus.

        Reine Oberflächen-Umschaltung; ``self._editor_surface`` wird von
        ``apply_state`` aus ``AppState.editor_surface`` gespiegelt (v4: SetEditorSurfaceIntent).
        """
        if not self.current_plan:
            return
        self.editor_topbar.pack_forget()
        self.grid_stack.pack_forget()
        self.details_container.pack_forget()
        self.docs_container.pack(fill="both", expand=True)
        self._refresh_documentation_table()
        self.docs_tree.focus_set()

    def _documentation_cell_text(self, symbols: dict[str, int]) -> str:
        """Erstellt den Anzeigetext für eine Dokumentations-Zelle aus einem Symbol-Dictionary.

        Args:
            symbols: Dictionary von symbol_name → Stärke.

        Returns:
            Leerzeichen-getrennter Glyph-String.
        """
        chunks: list[str] = []
        for symbol, strength in sorted(symbols.items()):
            glyph = self._symbol_glyph(symbol)
            chunks.append(glyph * max(1, min(3, int(strength))))
        return " ".join(chunks)

    def _documentation_summary_text(self, x: int, y: int) -> str:
        """Erstellt den Zusammenfassungstext (neueste Symbole) für einen Schülertisch.

        Args:
            x: Raster-x-Koordinate.
            y: Raster-y-Koordinate.

        Returns:
            Glyph-String aus der letzten Dokumentations-Zusammenfassung oder Leerstring.
        """
        if not self.current_plan:
            return ""
        student = self.current_plan.student_at(x, y)
        if student is None:
            return ""
        summary = summarize_latest_symbols(self.current_plan, student.student_id)
        return self._documentation_cell_text(summary)

    def _doc_fixed_column_label(self, column_id: str) -> str:
        """Gibt den Anzeigenamen einer festen Dokumentations-Spalte zurück.

        Args:
            column_id: Interne Spalten-ID (z. B. ``"summary"``, ``"overall"``, ``"grade_..."``)

        Returns:
            Lesbarer Spaltenname.
        """
        if column_id == "summary":
            return "Zusammenfassung"
        if column_id == "overall":
            return "Gesamtnote"
        if column_id == "written_total":
            return "Schriftlich gesamt"
        if column_id == "sonstige_total":
            return "Sonstig gesamt"
        if column_id.startswith("grade_"):
            raw_id = column_id[len("grade_"):]
            for grade in self.current_plan.documentation.grade_columns if self.current_plan else []:
                if grade.column_id == raw_id:
                    return grade.title
        return column_id

    def select_today_documentation_date(self) -> None:
        """Springt in der Dokumentationstabelle auf das heutige Datum (v4: GoToTodayIntent).

        ``apply_state`` übernimmt ``state.doc_selected_date`` anschließend in
        ``self._doc_selected_date_index`` und aktualisiert die Spaltenkopf-Markierung.
        """
        if not self._doc_dates:
            return
        self._select_doc_fixed_column(None)
        self._controller.dispatch(GoToTodayIntent())

    def _refresh_doc_selection_status(self) -> None:
        """Aktualisiert die Status-Statusvariable mit Name und Datum der aktuellen Doku-Zelle."""
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            self._doc_selection_status_var.set("Doku-Zelle: -")
            return
        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        student = self.current_plan.student_at(x, y)
        name = ""
        if student is not None and student.is_named():
            first = student.first_name.strip()
            last = (student.last_name or "").strip()
            name = f"{last}, {first}" if last else first
        display_name = name or f"({x},{y})"
        if self._doc_selected_fixed_column_id:
            label = self._doc_fixed_column_label(self._doc_selected_fixed_column_id)
            self._doc_selection_status_var.set(f"Doku-Zelle: {display_name} | {label}")
            self.after_idle(self._update_docs_cell_highlight)
            return
        self._doc_selection_status_var.set(f"Doku-Zelle: {display_name} | {self._doc_dates[date_index]}")
        self.after_idle(self._update_docs_cell_highlight)

    def _selected_docs_coordinates_and_date(self) -> tuple[int, int, str] | None:
        """Gibt (x, y, date_key) für die aktuell ausgewählte Doku-Zelle zurück.

        Returns:
            Tuple aus Koordinaten und Datums-Schlüssel, oder ``None`` wenn keine Auswahl.
        """
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return None
        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        return x, y, self._doc_dates[date_index]

    def _apply_doc_column_heading_highlight(self) -> None:
        """Aktualisiert alle Spaltenköpfe der Dokumentations-Tabelle (Sortierzeichen, Selektion)."""
        if not hasattr(self, "docs_tree"):
            return
        sort_arrow = "▲ " if self._doc_sort_ascending else "▼ "

        nachname_title = "Nachname"
        if self._doc_sort_column == "nachname":
            nachname_title = f"{sort_arrow}{nachname_title}"
        self.docs_tree.heading("#0", text=nachname_title)

        vorname_title = "Vorname"
        if self._doc_sort_column == "vorname":
            vorname_title = f"{sort_arrow}{vorname_title}"
        self.docs_tree.heading("vorname", text=vorname_title)

        for idx, date_key in enumerate(self._doc_dates):
            col_id = self._doc_date_column_ids[idx]
            title = date_key
            if idx == self._doc_selected_date_index and not self._doc_selected_fixed_column_id:
                title = f"> {title}"
            if self._doc_sort_column == col_id:
                title = f"{sort_arrow}{title}"
            self.docs_tree.heading(col_id, text=title)

        if hasattr(self, "docs_right_tree") and hasattr(self, "_doc_fixed_column_ids"):
            for fixed_col_id in self._doc_fixed_column_ids:
                base_label = self._doc_fixed_column_label(fixed_col_id)
                label = f"> {base_label}" if fixed_col_id == self._doc_selected_fixed_column_id else base_label
                if self._doc_sort_column == fixed_col_id:
                    label = f"{sort_arrow}{label}"
                self.docs_right_tree.heading(fixed_col_id, text=label)

        self._refresh_doc_selection_status()

    def _sort_docs_table_by_column(self, col_id: str, *, source: str) -> None:
        """Schaltet die Sortierrichtung für eine Spalte um und sortiert beide Treeviews.

        Args:
            col_id: Tkinter-Spalten-ID (z. B. ``"#0"``, ``"#1"``, ``"#2"``).
            source: ``"main"`` für den linken Treeview, ``"right"`` für den rechten.
        """
        if source == "main":
            if col_id == "#0":
                sort_key = "nachname"
            elif col_id == "#1":
                sort_key = "vorname"
            else:
                try:
                    date_index = int(col_id[1:]) - 2
                except (ValueError, TypeError):
                    return
                if not (0 <= date_index < len(self._doc_date_column_ids)):
                    return
                sort_key = self._doc_date_column_ids[date_index]
        else:
            try:
                col_index = int(col_id[1:]) - 1
            except (ValueError, TypeError):
                return
            if not (0 <= col_index < len(self._doc_fixed_column_ids)):
                return
            sort_key = self._doc_fixed_column_ids[col_index]
        if self._doc_sort_column == sort_key:
            self._doc_sort_ascending = not self._doc_sort_ascending
        else:
            self._doc_sort_column = sort_key
            self._doc_sort_ascending = True
        self._apply_doc_sort_order()
        self._apply_doc_column_heading_highlight()
