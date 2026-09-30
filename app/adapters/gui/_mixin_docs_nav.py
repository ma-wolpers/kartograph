"""Docs-Navigation-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt die Zell-Hervorhebung, die aktive logische Spalte (inkl. Datumsanker),
Spaltenauswahl-Wiederherstellung, Inline-Editor-Schließung und Wert-Anwendung
für die Dokumentations-Tabelle bereit.
"""

from __future__ import annotations

from app.adapters.gui.ui_theme import kartograph_theme
from app.core.intents.grade_intents import RecordGradeIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui


class DocsNavMixin:
    """Mixin: Doku-Zell-Hervorhebung, Spaltenauswahl und Inline-Editor-Verwaltung (v4)."""

    def _update_docs_cell_highlight(self) -> None:
        """Legt ein Overlay-Label auf die aktive Doku-Zelle (aktive Zeile × aktive Spalte).

        Entfernt ggf. ein vorhandenes Overlay und platziert ein neues, falls
        kein Inline-Editor geöffnet ist. Treeview und Zellwert werden über die
        Spaltenachse bzw. die logische Zeile (``self._doc_rows``) bestimmt,
        nicht über Treeview-Werte. Die Farbe stammt aus dem aktiven Theme.
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
        row = self._doc_rows.get(row_iid) if row_iid is not None else None
        column_key = self._doc_active_column_key()
        if row is None or column_key is None or not self._doc_axis.has(column_key):
            return
        tree = self._docs_trees_by_pane()[self._doc_axis.pane_of(column_key)]
        if row_iid not in tree.get_children():
            return

        bbox = tree.bbox(row_iid, self._doc_axis.tree_column(column_key))
        if not bbox:
            return
        bx, by, bw, bh = bbox

        theme = kartograph_theme(self.theme_key)
        cell_bg = theme["accent_soft"]
        cell_fg = theme["fg_primary"]
        cell_text = self._doc_axis.value_of(row, column_key)
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
        if not self._doc_selected_nondate_column_id or not self._doc_selected_nondate_column_id.startswith("grade_"):
            return
        selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
        if selected_iid is None:
            return
        self._open_docs_inline_grade_editor(selected_iid, self._doc_selected_nondate_column_id)

    def _doc_active_column_key(self) -> str | None:
        """Liefert die aktive logische Spalte der Dokutabelle.

        Returns:
            Die aktive Nicht-Datum-Spalte (Name/Fixspalte), sonst der Schlüssel
            des Datumsankers; ``None`` nur ohne Datumsspalten.
        """
        if self._doc_selected_nondate_column_id is not None:
            return self._doc_selected_nondate_column_id
        return self._doc_axis.date_key(self._doc_selected_date_index)

    def _set_doc_active_column(self, key: str) -> None:
        """Macht *key* zur aktiven logischen Spalte.

        Datumsspalte → Datumsanker auf diese Spalte, keine Nicht-Datum-Spalte
        aktiv. Andere Spalte (Name/Fixspalte) → als Nicht-Datum-Spalte aktiv;
        der Datumsanker bleibt als Ziel für Symbolaktionen und Rücksprung erhalten.

        Args:
            key: Existierender, auswählbarer Spaltenschlüssel.
        """
        date_index = self._doc_axis.date_index_of(key)
        if date_index is not None:
            self._select_doc_date_column(date_index)
        else:
            self._select_doc_nondate_column(key)

    def _is_valid_doc_nondate_column(self, key: str | None) -> bool:
        """Prüft, ob *key* als aktive Nicht-Datum-Spalte gültig ist.

        Args:
            key: Spaltenschlüssel oder ``None``.

        Returns:
            ``True`` für existierende, auswählbare Namens- oder Fixspalten.
        """
        return self._doc_axis.is_selectable(key) and not self._doc_axis.is_date(key)

    def _select_doc_date_column(self, date_index: int) -> None:
        """Wählt eine Datumsspalte aus (setzt den Datumsanker); hebt eine aktive Nicht-Datum-Spalte auf.

        Args:
            date_index: Index der Zieldatumsspalte in ``self._doc_dates``.
        """
        self._doc_selected_date_index = date_index
        self._doc_selected_nondate_column_id = None

    def _select_doc_nondate_column(self, column_id: str | None) -> None:
        """Setzt die aktive Nicht-Datum-Spalte (Name/Fixspalte) oder ``None`` für den Datumsanker.

        Rührt bewusst nicht an ``_doc_selected_date_index`` — der Index
        bleibt als Rücksprungpunkt erhalten, falls der Nutzer zurück in den
        Datumsmodus wechselt.

        Args:
            column_id: Schlüssel der Namens-/Fixspalte oder ``None``.
        """
        self._doc_selected_nondate_column_id = column_id

    def _clamp_doc_column_selection_after_rebuild(self, date_count: int) -> None:
        """Hält Datumsanker und aktive Nicht-Datum-Spalte nach einem Rebuild gültig.

        Deterministische Regel (Invariante: aktive Spalte ist danach gültig):
        der Datumsanker wird auf ``[0, date_count - 1]`` geklemmt; eine nicht
        mehr existierende Nicht-Datum-Spalte (z. B. gelöschte Notenspalte)
        wird auf ``None`` gesetzt, womit der geklemmte Datumsanker aktiv wird.
        Namensspalten existieren immer und bleiben gültig. Keine
        Auswahl-Aktion, löscht insbesondere keine noch gültige Spalte.

        Args:
            date_count: Aktuelle Anzahl der Datumsspalten nach dem Rebuild.
        """
        self._doc_selected_date_index = max(0, min(self._doc_selected_date_index, max(0, date_count - 1)))
        if not self._is_valid_doc_nondate_column(self._doc_selected_nondate_column_id):
            self._doc_selected_nondate_column_id = None

    def _restore_docs_column_selection(self, nondate_column_id: str | None, date_index: int) -> None:
        """Stellt die gespeicherte Spaltenauswahl nach einer Treeview-Aktualisierung wieder her.

        Args:
            nondate_column_id: Gespeicherte Nicht-Datum-Spalte (oder ``None`` für den Datumsanker).
            date_index: Gespeicherter Datumsanker.
        """
        if self._is_valid_doc_nondate_column(nondate_column_id):
            self._select_doc_nondate_column(nondate_column_id)
        else:
            self._select_doc_nondate_column(None)
            if self._doc_dates:
                self._select_doc_date_column(max(0, min(date_index, len(self._doc_dates) - 1)))
        self._apply_doc_column_heading_highlight()

    def _preserve_docs_column_selection_after_keypress(self) -> None:
        """Plant via ``after_idle`` die Wiederherstellung der Spaltenauswahl nach einer Tasteneingabe."""
        nondate_column_id = self._doc_selected_nondate_column_id
        date_index = self._doc_selected_date_index
        self.after_idle(lambda: self._restore_docs_column_selection(nondate_column_id, date_index))
