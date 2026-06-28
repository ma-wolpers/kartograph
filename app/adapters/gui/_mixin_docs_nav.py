"""Docs-Navigation-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt die Zell-Hervorhebung, Spaltenauswahl-Wiederherstellung, Inline-Editor-
Schließung und Wert-Anwendung für die Dokumentations-Tabelle bereit.
"""

from __future__ import annotations

from app.adapters.gui.ui_theme import THEMES
from app.core.intents.grade_intents import RecordGradeIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui


class DocsNavMixin:
    """Mixin: Doku-Zell-Hervorhebung, Spaltenauswahl und Inline-Editor-Verwaltung (v4)."""

    def _update_docs_cell_highlight(self) -> None:
        """Legt ein Overlay-Label auf die aktive Doku-Zelle im Treeview.

        Entfernt ggf. ein vorhandenes Overlay und platziert ein neues falls kein
        Inline-Editor geöffnet ist. Die Farbe stammt aus dem aktiven Theme.
        """
        if self._docs_cell_overlay is not None:
            try:
                if self._docs_cell_overlay.winfo_exists():
                    self._docs_cell_overlay.destroy()
            except Exception:
                pass
            self._docs_cell_overlay = None

        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        if self._docs_inline_editor is not None:
            return

        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        row_iid = self._doc_tree_iid_by_student_index.get(student_index)
        if row_iid is None:
            return

        if self._doc_selected_fixed_column_id:
            tree = self.docs_right_tree
            try:
                col_index = self._doc_fixed_column_ids.index(self._doc_selected_fixed_column_id)
                tree_col = f"#{col_index + 1}"
            except (ValueError, AttributeError):
                return
            if row_iid not in tree.get_children():
                return
            values = tree.item(row_iid, "values")
            cell_text = str(values[col_index]) if values and col_index < len(values) else ""
        else:
            tree = self.docs_tree
            date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
            if date_index >= len(self._doc_date_column_ids):
                return
            tree_col = self._doc_date_column_ids[date_index]
            if row_iid not in tree.get_children():
                return
            values = tree.item(row_iid, "values")
            cell_text = str(values[date_index + 1]) if values and date_index + 1 < len(values) else ""

        bbox = tree.bbox(row_iid, tree_col)
        if not bbox:
            return
        bx, by, bw, bh = bbox

        theme = THEMES.get(self.theme_key, THEMES[list(THEMES.keys())[0]])
        cell_bg = theme.get("accent_soft", "#fffde7")
        cell_fg = theme.get("fg_primary", "#000000")
        label = ui.Label(tree, text=cell_text, background=cell_bg, foreground=cell_fg, bd=1, relief="solid", anchor="w", padx=4, pady=0)
        label.place(x=bx, y=by, width=bw, height=bh)
        self._docs_cell_overlay = label

    def _close_docs_inline_editor(self, apply_changes: bool = False) -> None:
        """Schließt den Inline-Editor und wendet ggf. den eingegebenen Wert an.

        Args:
            apply_changes: Falls ``True``, wird ``_apply_docs_inline_editor_value`` aufgerufen.
        """
        editor = self._docs_inline_editor
        if editor is None:
            return
        if apply_changes:
            self._apply_docs_inline_editor_value()
        if editor.winfo_exists():
            editor.destroy()
        self._docs_inline_editor = None
        self._docs_inline_editor_tree = None
        self._docs_inline_editor_row_id = None
        self._docs_inline_editor_kind = None
        self._docs_inline_editor_model_column = None
        self.after_idle(self._update_docs_cell_highlight)

    def _apply_docs_inline_editor_value(self) -> None:
        """Übernimmt den Wert aus dem aktiven Inline-Editor als Noteneintrag (v4).

        Parst den Text als Dezimalzahl und dispatcht ``RecordGradeIntent``.
        Bei leerem Text wird die Note gelöscht (``grade=0.0``).
        """
        if not self.current_plan:
            return
        if self._docs_inline_editor is None or self._docs_inline_editor_kind != "grade":
            return

        selected = self._selected_docs_coordinates_and_date()
        if selected is None:
            return
        x, y, date_key = selected

        column_id = self._docs_inline_editor_model_column
        if not column_id:
            return
        raw_text = self._docs_inline_editor.get().strip()
        grade_value: float | None
        if not raw_text:
            grade_value = None
        else:
            try:
                grade_value = float(raw_text.replace(",", "."))
            except ValueError:
                self.status_var.set("Ungueltige Note: bitte Zahl zwischen 1 und 6 eingeben")
                return

        student = self.current_plan.student_at(x, y)
        if not student:
            return
        self._controller.dispatch(
            RecordGradeIntent(
                student_id=student.student_id,
                date=date_key,
                column_id=column_id,
                grade=grade_value if grade_value is not None else 0.0,
            )
        )
        status = "Note geloescht" if grade_value is None else "Note aktualisiert"
        self.status_var.set(status)
        self._refresh_documentation_table()

    def _on_docs_inline_editor_return(self, _event) -> str:
        """Schließt den Inline-Editor mit Übernahme (Return/KP_Enter).

        Args:
            _event: Tkinter-Tastaturereignis (Inhalt wird nicht ausgewertet).
        """
        self._close_docs_inline_editor(apply_changes=True)
        if self.docs_right_tree.winfo_exists():
            self.docs_right_tree.focus_set()
        return "break"

    def _on_docs_inline_editor_escape(self, _event) -> str:
        """Bricht den Inline-Editor ohne Übernahme ab (Escape).

        Args:
            _event: Tkinter-Tastaturereignis (Inhalt wird nicht ausgewertet).
        """
        self._close_docs_inline_editor(apply_changes=False)
        if self.docs_right_tree.winfo_exists():
            self.docs_right_tree.focus_set()
        return "break"

    def _open_selected_docs_grade_cell_editor(self) -> None:
        """Öffnet den Inline-Noten-Editor für die aktuell ausgewählte Doku-Zelle."""
        if not self._doc_selected_fixed_column_id or not self._doc_selected_fixed_column_id.startswith("grade_"):
            return
        selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
        if selected_iid is None:
            return
        self._open_docs_inline_grade_editor(selected_iid, self._doc_selected_fixed_column_id)

    def _first_selectable_doc_fixed_column(self) -> str | None:
        """Gibt die erste wählbare feste Spalte zurück (überspringt ``"summary"``).

        Returns:
            Spalten-ID oder ``None`` wenn keine wählbare Spalte vorhanden.
        """
        for column_id in self._doc_fixed_column_ids:
            if column_id != "summary":
                return column_id
        return None

    def _adjacent_selectable_doc_fixed_column(self, current_column_id: str, *, step: int) -> str | None:
        """Gibt die benachbarte wählbare feste Spalte zurück.

        Args:
            current_column_id: Ausgangsspalte.
            step: ``1`` für rechts, ``-1`` für links.

        Returns:
            Benachbarte Spalten-ID oder ``None``.
        """
        if step not in {-1, 1}:
            return None
        if current_column_id not in self._doc_fixed_column_ids:
            return None
        index = self._doc_fixed_column_ids.index(current_column_id) + step
        while 0 <= index < len(self._doc_fixed_column_ids):
            candidate = self._doc_fixed_column_ids[index]
            if candidate != "summary":
                return candidate
            index += step
        return None

    def _restore_docs_column_selection(self, fixed_column_id: str | None, date_index: int) -> None:
        """Stellt die gespeicherte Spaltenauswahl nach einer Treeview-Aktualisierung wieder her.

        Args:
            fixed_column_id: Gespeicherte feste Spalten-ID (oder ``None`` für Datumsspalte).
            date_index: Gespeicherter Datums-Spaltenindex.
        """
        if fixed_column_id is not None and fixed_column_id in self._doc_fixed_column_ids and fixed_column_id != "summary":
            self._doc_selected_fixed_column_id = fixed_column_id
        else:
            self._doc_selected_fixed_column_id = None
            if self._doc_dates:
                self._doc_selected_date_index = max(0, min(date_index, len(self._doc_dates) - 1))
        self._apply_doc_column_heading_highlight()

    def _preserve_docs_column_selection_after_keypress(self) -> None:
        """Plant via ``after_idle`` die Wiederherstellung der Spaltenauswahl nach einer Tasteneingabe."""
        fixed_column_id = self._doc_selected_fixed_column_id
        date_index = self._doc_selected_date_index
        self.after_idle(lambda: self._restore_docs_column_selection(fixed_column_id, date_index))
