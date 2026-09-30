"""Docs-Ansicht-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Steuert den Wechsel zwischen Listenansicht, Raster- und Dokumentations-Oberfläche
sowie Hilfsmethoden für Dokumentations-Text, Spaltenköpfe, Sortierstatus und
heutige Datumsauswahl.
"""

from __future__ import annotations

from pathlib import Path

from app.adapters.gui.docs_table_model import NACHNAME_KEY, VORNAME_KEY
from app.adapters.gui.docs_table_rules import next_sort_spec
from app.core.domain.models_v4 import ParticipationRating
from app.core.intents.navigation_intents import ClearSelectionIntent
from app.core.intents.session_intents import GoToTodayIntent
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui


def _resolve_doc_student_index_for_cell(
    doc_student_coords: list[tuple[int, int]], x: int, y: int
) -> int | None:
    """Findet den Dokutabellen-Index für Rasterzelle (x, y).

    Reine, Tk-freie Entscheidungslogik (separat testbar) -- liefert bewusst
    ``None`` statt eines Fallback-Index, wenn an der Zelle niemand sitzt.

    Args:
        doc_student_coords: Sitzkoordinaten in Dokutabellen-Reihenfolge.
        x: Raster-x-Koordinate.
        y: Raster-y-Koordinate.
    """
    try:
        return doc_student_coords.index((x, y))
    except ValueError:
        return None


def _resolve_grid_cell_for_doc_index(
    doc_student_coords: list[tuple[int, int]], doc_selected_student_index: int
) -> tuple[int, int] | None:
    """Liefert die Rasterzelle für den aktuell in der Dokutabelle ausgewählten Index.

    Reine, Tk-freie Entscheidungslogik (separat testbar) -- liefert bewusst
    ``None`` statt eines geklemmten Index (0 oder letzter gültiger Index) bei
    einem ungültigen oder fehlenden Index.

    Args:
        doc_student_coords: Sitzkoordinaten in Dokutabellen-Reihenfolge.
        doc_selected_student_index: Aktuell ausgewählter Dokutabellen-Index.
    """
    if not 0 <= doc_selected_student_index < len(doc_student_coords):
        return None
    return doc_student_coords[doc_selected_student_index]


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

        Die Ansicht wechselt bewusst NICHT hier direkt, sondern über
        ``apply_state()`` (Übergang "Plan offen" -> "kein Plan" ruft
        ``show_plan_list_view()``): Sichtbarkeit folgt damit ausschließlich
        ``AppState``, derselben Quelle wie der Shortcut-Scope
        (``app/application/shortcut_scope.py``) -- kein Zwischenzustand mit
        versteckter Editor-Ansicht bei noch offenem Plan.
        """
        self._commit_pending_edits()
        self._flush_pending_plan_save()
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
        self._sync_grid_selection_from_doc()
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
        if self._doc_dates:
            self._select_doc_date_column(len(self._doc_dates) - 1)
        if self.selected_cell is not None:
            self._sync_doc_selection_from_grid(*self.selected_cell)
        self.docs_tree.focus_set()

    def _sync_doc_selection_from_grid(self, x: int, y: int) -> None:
        """Übernimmt die Doku-Auswahl von der Grid-Zelle (x, y).

        Nur wenn dort tatsächlich ein benannter Schüler sitzt -- sonst bleibt
        die bisherige Doku-Auswahl unverändert (kein erfundener Ersatz).

        Args:
            x: Raster-x-Koordinate der aktuellen Grid-Auswahl.
            y: Raster-y-Koordinate der aktuellen Grid-Auswahl.
        """
        idx = _resolve_doc_student_index_for_cell(self._doc_student_coords, x, y)
        if idx is None:
            return
        row_id = self._doc_tree_iid_by_student_index.get(idx)
        if row_id is not None:
            self._set_docs_row_selection(row_id)

    def _sync_grid_selection_from_doc(self) -> None:
        """Übernimmt die Grid-Auswahl vom aktuell in der Dokutabelle ausgewählten Schüler.

        Nur bei einem gültigen Doku-Index -- sonst bleibt die bisherige
        Grid-Auswahl unverändert (kein erfundener Ersatz).
        """
        cell = _resolve_grid_cell_for_doc_index(self._doc_student_coords, self._doc_selected_student_index)
        if cell is None:
            return
        self._set_selection_single(*cell)

    def _documentation_cell_text(
        self, symbols: dict[str, int], participation: ParticipationRating | None = None
    ) -> str:
        """Erstellt den Anzeigetext für eine Dokumentations-Zelle aus Symbolen und Mitarbeit-Bewertung.

        Args:
            symbols: Dictionary von symbol_name → Stärke.
            participation: Mitarbeit-Bewertung des Tages ("+"/"o"/"-"), falls gesetzt.

        Returns:
            Leerzeichen-getrennter String: Bewertung (falls gesetzt) vor den Symbol-Glyphen.
        """
        chunks: list[str] = []
        if participation:
            chunks.append(participation)
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

    def _doc_column_label(self, column_id: str) -> str:
        """Gibt den Anzeigenamen einer logischen Dokumentations-Spalte zurück.

        Args:
            column_id: Spaltenschlüssel (``"nachname"``, ``"date_3"``, ``"summary"``, ``"grade_..."`` …).

        Returns:
            Lesbarer Spaltenname (bei Datumsspalten das Datum).
        """
        if column_id == NACHNAME_KEY:
            return "Nachname"
        if column_id == VORNAME_KEY:
            return "Vorname"
        date_index = self._doc_axis.date_index_of(column_id)
        if date_index is not None and date_index < len(self._doc_dates):
            return self._doc_dates[date_index]
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
        self._select_doc_nondate_column(None)
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
        if self._doc_selected_nondate_column_id:
            label = self._doc_column_label(self._doc_selected_nondate_column_id)
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
        """Aktualisiert alle Spaltenköpfe der drei Doku-Treeviews (Sortierpfeil, aktive Spalte).

        Läuft über die logische Spaltenachse: ``> `` markiert die aktive
        Spalte (Name, Datumsanker oder Fixspalte), ``▲``/``▼`` die Sortierspalte.
        """
        if not hasattr(self, "docs_name_tree"):
            return
        sort_arrow = "▲ " if self._doc_sort_ascending else "▼ "
        active_key = self._doc_active_column_key()
        trees = self._docs_trees_by_pane()
        for key in self._doc_axis.keys:
            label = self._doc_column_label(key)
            if key == active_key:
                label = f"> {label}"
            if self._doc_sort_column == key:
                label = f"{sort_arrow}{label}"
            trees[self._doc_axis.pane_of(key)].heading(self._doc_axis.tree_column(key), text=label)

        self._refresh_doc_selection_status()

    def _sort_docs_table_by_key(self, key: str) -> None:
        """Wendet die Sortier-Klickregel auf *key* an und ordnet alle drei Treeviews neu.

        Ändert nur die Sortierspezifikation (``next_sort_spec``: gleiche Spalte
        → Richtung umkehren, neue Spalte → aufsteigend); die Reihenfolge wird
        daraus in ``_apply_doc_row_order`` berechnet.

        Args:
            key: Logischer Spaltenschlüssel der angeklickten Kopfzeile.
        """
        self._doc_sort_column, self._doc_sort_ascending = next_sort_spec(
            self._doc_sort_column, self._doc_sort_ascending, key
        )
        self._apply_doc_row_order()
        self._apply_doc_column_heading_highlight()
