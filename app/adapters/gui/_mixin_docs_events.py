"""Docs-Events-Mixin für das Kartograph-Hauptfenster.

Behandelt Klick-, Auswahl- und Tastaturereignisse beider Dokumentations-Treeviews
sowie die horizontale und vertikale Tastaturnavigation in der Doku-Tabelle.
"""

from __future__ import annotations


class DocsEventsMixin:
    """Mixin: Treeview-Ereignisse und Tastaturnavigation in der Dokumentations-Ansicht."""

    def _on_docs_tree_click(self, event) -> None:
        """Behandelt Klick auf den linken Doku-Treeview (Kopf: sortieren; Zeile: selektieren).

        Args:
            event: Tkinter-Mausereignis.
        """
        if self.docs_tree.identify_region(event.x, event.y) == "heading":
            self._sort_docs_table_by_column(self.docs_tree.identify_column(event.x), source="main")
            return
        row_id = self.docs_tree.identify_row(event.y)
        if row_id:
            self._set_docs_row_selection(row_id, source="main")
        self._doc_selected_fixed_column_id = None
        col_id = self.docs_tree.identify_column(event.x)
        if col_id.startswith("#"):
            try:
                col_index = int(col_id[1:]) - 1
            except ValueError:
                col_index = -1
            if 0 <= col_index < len(self._doc_dates):
                self._doc_selected_date_index = col_index
                self._apply_doc_column_heading_highlight()

    def _on_docs_tree_select(self) -> None:
        """Behandelt programmgesteuerte Zeilenauswahl im linken Treeview."""
        if self._syncing_docs_selection:
            return
        selected = self.docs_tree.selection()
        if not selected:
            return
        row_id = selected[0]
        self._set_docs_row_selection(row_id, source="main")
        if self.focus_get() == self.docs_tree:
            self._doc_selected_fixed_column_id = None
        self._refresh_doc_selection_status()

    def _on_docs_tree_keypress(self, event) -> None:
        """Stellt nach Tasteneingabe im linken Treeview die Spaltenauswahl wieder her (außer Pfeile).

        Args:
            event: Tkinter-Tastaturereignis (``keysym`` bestimmt, ob Pfeiltasten ignoriert werden).
        """
        if event.keysym in {"Left", "Right", "Up", "Down"}:
            return
        self._preserve_docs_column_selection_after_keypress()

    def _on_docs_right_tree_click(self, event) -> None:
        """Behandelt Klick auf den rechten Doku-Treeview (Kopf: sortieren; Zeile: selektieren).

        Args:
            event: Tkinter-Mausereignis.
        """
        if self.docs_right_tree.identify_region(event.x, event.y) == "heading":
            self._sort_docs_table_by_column(self.docs_right_tree.identify_column(event.x), source="right")
            return
        row_id = self.docs_right_tree.identify_row(event.y)
        if row_id:
            self._set_docs_row_selection(row_id, source="right")
        col_id = self.docs_right_tree.identify_column(event.x)
        if col_id.startswith("#"):
            try:
                col_index = int(col_id[1:]) - 1
            except ValueError:
                col_index = -1
            if 0 <= col_index < len(self._doc_fixed_column_ids):
                selected_column_id = self._doc_fixed_column_ids[col_index]
                if selected_column_id == "summary":
                    self._doc_selected_fixed_column_id = self._first_selectable_doc_fixed_column()
                else:
                    self._doc_selected_fixed_column_id = selected_column_id
                self._apply_doc_column_heading_highlight()

    def _on_docs_right_tree_double_click(self, event) -> None:
        """Öffnet den Inline-Editor bei Doppelklick auf eine Noten-Zelle im rechten Treeview.

        Args:
            event: Tkinter-Mausereignis.
        """
        row_id = self.docs_right_tree.identify_row(event.y)
        if not row_id:
            return
        self._set_docs_row_selection(row_id, source="right")
        col_id = self.docs_right_tree.identify_column(event.x)
        if not col_id.startswith("#"):
            return
        try:
            col_index = int(col_id[1:]) - 1
        except ValueError:
            return
        if not (0 <= col_index < len(self._doc_fixed_column_ids)):
            return
        fixed_column_id = self._doc_fixed_column_ids[col_index]
        if fixed_column_id == "summary":
            return
        self._doc_selected_fixed_column_id = fixed_column_id
        self._apply_doc_column_heading_highlight()
        if fixed_column_id.startswith("grade_"):
            self._open_docs_inline_grade_editor(row_id, fixed_column_id)

    def _on_docs_right_tree_select(self) -> None:
        """Behandelt programmgesteuerte Zeilenauswahl im rechten Treeview."""
        if self._syncing_docs_selection:
            return
        selected = self.docs_right_tree.selection()
        if not selected:
            return
        row_id = selected[0]
        self._set_docs_row_selection(row_id, source="right")
        if self.focus_get() != self.docs_right_tree:
            self._refresh_doc_selection_status()
            return
        if self._doc_selected_fixed_column_id not in set(self._doc_fixed_column_ids) or self._doc_selected_fixed_column_id == "summary":
            self._doc_selected_fixed_column_id = None
        if self._doc_selected_fixed_column_id is None:
            self._doc_selected_fixed_column_id = self._first_selectable_doc_fixed_column()
        self._apply_doc_column_heading_highlight()

    def _on_docs_right_tree_keypress(self, event) -> None:
        """Stellt nach Tasteneingabe im rechten Treeview die Spaltenauswahl wieder her (außer Pfeile).

        Args:
            event: Tkinter-Tastaturereignis (``keysym`` bestimmt, ob Pfeiltasten ignoriert werden).
        """
        if event.keysym in {"Left", "Right", "Up", "Down"}:
            return
        self._preserve_docs_column_selection_after_keypress()

    def _set_docs_row_selection(self, row_id: str, source: str | None = None) -> None:
        """Synchronisiert die Zeilenauswahl beider Treeviews auf ``row_id``.

        Args:
            row_id: Treeview-IID der Zielzeile.
            source: ``"main"`` oder ``"right"`` — der Quell-Treeview wird nicht neu gesetzt.
        """
        if not row_id:
            return
        if self._syncing_docs_selection:
            return
        if not self.docs_tree.exists(row_id) or not self.docs_right_tree.exists(row_id):
            return
        self._syncing_docs_selection = True
        try:
            if source != "main":
                main_selected = self.docs_tree.selection()
                if len(main_selected) != 1 or main_selected[0] != row_id:
                    self.docs_tree.selection_set(row_id)
                if self.docs_tree.focus() != row_id:
                    self.docs_tree.focus(row_id)
                self.docs_tree.see(row_id)
            if source != "right":
                right_selected = self.docs_right_tree.selection()
                if len(right_selected) != 1 or right_selected[0] != row_id:
                    self.docs_right_tree.selection_set(row_id)
                if self.docs_right_tree.focus() != row_id:
                    self.docs_right_tree.focus(row_id)
                self.docs_right_tree.see(row_id)
        finally:
            self._syncing_docs_selection = False

        student_idx = self._doc_student_index_by_iid.get(row_id)
        if student_idx is not None:
            self._doc_selected_student_index = student_idx

    def _on_docs_vertical_nav(self, delta: int, *, source: str) -> str:
        """Navigiert in der Doku-Tabelle um ``delta`` Zeilen in visueller Reihenfolge.

        Args:
            delta: Schrittweite (positiv = nach unten, negativ = nach oben).
            source: ``"main"`` oder ``"right"`` — bestimmt wohin der Fokus geht.

        Returns:
            ``"break"`` um die Standard-Tkinter-Navigation zu unterdrücken.
        """
        if not self._shortcut_scope_allows("docs"):
            return "break"
        if not self._doc_student_coords:
            return "break"

        fixed_column_id = self._doc_selected_fixed_column_id
        date_index = self._doc_selected_date_index

        all_iids = list(self.docs_tree.get_children(""))
        if not all_iids:
            return "break"

        current_iid = self._doc_tree_iid_by_student_index.get(
            max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        )
        try:
            visual_pos = all_iids.index(current_iid) if current_iid in all_iids else 0
        except ValueError:
            visual_pos = 0

        next_pos = max(0, min(visual_pos + delta, len(all_iids) - 1))
        row_id = all_iids[next_pos]

        self._set_docs_row_selection(row_id)
        if source == "right":
            self.docs_right_tree.focus_set()
        else:
            self.docs_tree.focus_set()
        self._refresh_doc_selection_status()
        self.after_idle(lambda: self._restore_docs_column_selection(fixed_column_id, date_index))
        self.after_idle(self._update_docs_cell_highlight)
        return "break"

    def _on_docs_horizontal_nav(self, delta: int) -> str:
        """Navigiert horizontal durch Datums- und Fixspalten in der Doku-Tabelle.

        Args:
            delta: ``1`` nach rechts, ``-1`` nach links.

        Returns:
            ``"break"`` um die Standard-Navigation zu unterdrücken.
        """
        if not self._shortcut_scope_allows("docs"):
            return "break"

        if delta > 0:
            if self._doc_selected_fixed_column_id is None:
                if self._doc_dates and self._doc_selected_date_index < len(self._doc_dates) - 1:
                    self._doc_selected_date_index += 1
                elif self._doc_fixed_column_ids:
                    self._doc_selected_fixed_column_id = self._first_selectable_doc_fixed_column()
                self._apply_doc_column_heading_highlight()
                return "break"
            if self._doc_selected_fixed_column_id not in self._doc_fixed_column_ids or self._doc_selected_fixed_column_id == "summary":
                self._doc_selected_fixed_column_id = self._first_selectable_doc_fixed_column()
                self._apply_doc_column_heading_highlight()
                return "break"
            next_col = self._adjacent_selectable_doc_fixed_column(self._doc_selected_fixed_column_id, step=1)
            if next_col is not None:
                self._doc_selected_fixed_column_id = next_col
            self._apply_doc_column_heading_highlight()
            return "break"

        if self._doc_selected_fixed_column_id is None:
            if self._doc_dates:
                self._doc_selected_date_index = max(0, self._doc_selected_date_index - 1)
                self._apply_doc_column_heading_highlight()
            return "break"

        if self._doc_selected_fixed_column_id not in self._doc_fixed_column_ids or self._doc_selected_fixed_column_id == "summary":
            self._doc_selected_fixed_column_id = None
            self._apply_doc_column_heading_highlight()
            return "break"
        prev_col = self._adjacent_selectable_doc_fixed_column(self._doc_selected_fixed_column_id, step=-1)
        if prev_col is not None:
            self._doc_selected_fixed_column_id = prev_col
        else:
            self._doc_selected_fixed_column_id = None
        self._apply_doc_column_heading_highlight()
        return "break"
