"""Docs-Edit-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Methoden zum Umschalten und Löschen von Dokumentationssymbolen sowie
den Inline-Noten-Editor der Dokutabelle bereit.
"""

from __future__ import annotations

from app.core.domain.symbol_toggle import next_symbol_toggle_strength
from app.core.intents.session_intents import ClearDocEntryIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime import widgets as tui


class DocsEditMixin:
    """Mixin: Symbol-Umschalten, Symbol-Löschen und Inline-Noten-Editor in der Dokumentations-Ansicht (v4)."""

    def _open_docs_inline_grade_editor(self, row_id: str, grade_column_key: str) -> None:
        """Öffnet einen Entry-Inline-Editor in der Noten-Zelle (*row_id*, *grade_column_key*).

        Die Zellgeometrie kommt aus ``bbox`` des für die Spalte zuständigen
        Treeviews; die Spalte wird über ``DocColumnAxis.tree_column`` statt
        über eine Index-Rechnung adressiert.

        Args:
            row_id: Zeilen-ID (iid), in allen drei Treeviews identisch.
            grade_column_key: Spaltenschlüssel einer Notenspalte, z. B. ``"grade_<id>"``.
        """
        if not self.current_plan:
            return
        if not self._doc_axis.is_grade(grade_column_key):
            return
        tree = self._docs_trees_by_pane()[self._doc_axis.pane_of(grade_column_key)]
        if row_id not in tree.get_children():
            return

        self._close_docs_inline_editor(apply_changes=False)

        bbox = tree.bbox(row_id, self._doc_axis.tree_column(grade_column_key))
        if not bbox:
            return
        x, y, width, height = bbox

        selected = self._selected_docs_coordinates_and_date()
        if selected is None:
            return
        coords_x, coords_y, date_key = selected
        model_column_id = grade_column_key[len("grade_"):]

        current_text = ""
        student = self.current_plan.student_at(coords_x, coords_y)
        if student is not None and student.is_named():
            session = self.current_plan.documentation.session_for_date(date_key)
            if session is not None:
                entry = session.entry_for(student.student_id)
                if entry is not None:
                    value = entry.grades.get(model_column_id)
                    if value is not None:
                        current_text = f"{float(value):.2f}".rstrip("0").rstrip(".")

        editor = tui.Entry(tree)
        editor.insert(0, current_text)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.selection_range(0, ui.END)
        editor.bind("<Return>", self._on_docs_inline_editor_return)
        editor.bind("<KP_Enter>", self._on_docs_inline_editor_return)
        editor.bind("<Escape>", self._on_docs_inline_editor_escape)
        editor.bind("<FocusOut>", lambda _event: self._close_docs_inline_editor(apply_changes=True))

        self._docs_inline_editor = editor
        self._docs_inline_editor_tree = tree
        self._docs_inline_editor_row_id = row_id
        self._docs_inline_editor_kind = "grade"
        self._docs_inline_editor_model_column = model_column_id

    def _toggle_documentation_symbol_for_student(self, student, symbol: str, date: str) -> None:
        """Schaltet *symbol* für *student* am *date* um (v4).

        Diagnosesymbole zyklen 0→1→2→3→0, Doku-Symbole (eingebaut wie eigen)
        togglen binär 0↔1 (siehe ``next_symbol_toggle_strength``). Reiner
        Toggle-Kern ohne UI-Refresh und ohne eigene Schüler-/Datumsauflösung —
        gemeinsam genutzt von der Dokuansicht (``_toggle_documentation_symbol``,
        wirkt auf die dort gewählte Datumsspalte) und dem Raster
        (``_toggle_documentation_symbol_today_grid`` in ``_mixin_edit.py``,
        wirkt immer auf das heutige Datum) — beide unterscheiden sich nur
        darin, woher *student* und *date* kommen.

        Args:
            student: Schüler, dessen Symbol umgeschaltet wird.
            symbol: Bezeichner des umzuschaltenden Symbols (eingebauter
                Meaning-Text oder eigene Symbol-ID).
            date: ISO-Datum der Doku-Session, auf die sich der Toggle bezieht.
        """
        current_strength = 0
        session = self.current_plan.documentation.session_for_date(date)
        if session is not None:
            entry = session.entry_for(student.student_id)
            if entry is not None:
                current_strength = int(entry.symbols.get(symbol, 0))
        next_strength = next_symbol_toggle_strength(
            current_strength, is_diagnostic=symbol in self.diagnostic_symbol_catalog
        )
        self._controller.dispatch(
            RecordDocumentationSymbolIntent(
                student_id=student.student_id,
                date=date,
                symbol=symbol,
                strength=next_strength,
            )
        )

    def _toggle_documentation_symbol(self, symbol: str) -> None:
        """Schaltet ein Dokumentationssymbol für die aktuelle Doku-Zellenauswahl um.

        Löst Schüler und die aktuell in der Dokutabelle ausgewählte
        Datumsspalte auf und delegiert an ``_toggle_documentation_symbol_for_student()``.
        Gilt unabhängig davon, ob *symbol* per Tastenkürzel oder über den
        "Symbol setzen"-Dialog gewählt wurde. Aktualisiert danach die
        Doku-Tabelle.

        Args:
            symbol: Bezeichner des umzuschaltenden Symbols (eingebauter
                Meaning-Text oder eigene Symbol-ID).
        """
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        date_key = self._doc_dates[date_index]
        student = self.current_plan.student_at(x, y)
        if not student or not student.is_named():
            return
        self._toggle_documentation_symbol_for_student(student, symbol, date_key)
        self._refresh_documentation_table()

    def clear_selected_documentation_symbol(self) -> None:
        """Löscht alle aktiven Symbole und Noten für die aktuelle Doku-Zelle (v4).

        Dispatcht ClearDocEntryIntent für die ausgewählte Student-/Datumskombination.
        """
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        date_key = self._doc_dates[date_index]
        student = self.current_plan.student_at(x, y)
        if not student or not student.is_named():
            return
        self._controller.dispatch(ClearDocEntryIntent(student_id=student.student_id, date=date_key))
        self._refresh_documentation_table()
