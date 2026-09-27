"""Docs-Tabellen-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Baut die logische Dokutabelle (``DocRow`` je Schüler + ``DocColumnAxis``)
aus den Domänendaten auf und projiziert sie in die drei Treeviews
(NAMES / MAIN / RIGHT). Treeviews sind dabei reine Projektionen: Zeileninhalt,
Reihenfolge und Sortierung kommen ausschließlich aus ``self._doc_rows`` und der
Sortierspezifikation (``_doc_sort_column`` / ``_doc_sort_ascending``), nie aus
einem Treeview.
"""

from __future__ import annotations

import time

from app.adapters.gui.docs_table_model import DocColumnAxis, DocRow, DocsPane
from app.adapters.gui.docs_table_rules import sort_iids
from app.adapters.gui.main_window_constants import LOGGER
from app.core.usecases.v4.grade_usecases import (
    collect_grade_value_lists_by_student,
    compute_grade_display_by_student,
    compute_grade_subtotal_display_by_student,
    compute_latest_grades_by_student,
)
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols_by_student


class DocsTableMixin:
    """Mixin: Aufbau der logischen Dokutabelle und ihre Projektion in drei Treeviews (v4)."""

    def _refresh_documentation_table(self) -> None:
        """Baut die logische Dokutabelle neu auf und projiziert sie in alle drei Treeviews (v4).

        Ablauf: Domänendaten → ``DocRow``s (Basisreihenfolge = Sitzordnung) →
        neue ``DocColumnAxis`` → Sortierspezifikation validieren →
        ``_project_doc_rows`` (Insert/Update/Delete) → ``_apply_doc_row_order``
        (Reihenfolge) → Zeilenauswahl, aktive Spalte und Überschriften
        synchronisieren.
        """
        started = time.perf_counter()
        if not self.current_plan:
            return
        self._close_docs_inline_editor(apply_changes=False)

        self._doc_student_coords = [
            (s.seat.x, s.seat.y)
            for s in sorted(self.current_plan.classroom.students, key=lambda s: (s.seat.y, s.seat.x))
            if s.is_named()
        ]

        all_dates = sorted(
            set(s.date for s in self.current_plan.documentation.sessions) | {self._today_doc_date()}
        )
        self._doc_dates = all_dates
        self._doc_date_column_ids = [f"date_{index}" for index in range(len(all_dates))]

        grade_columns = self.current_plan.documentation.grade_columns
        written_columns = [c for c in grade_columns if c.category == "schriftlich"]
        sonstige_columns = [c for c in grade_columns if c.category == "sonstig"]

        fixed_columns: list[str] = ["summary"]
        fixed_columns.extend([f"grade_{c.column_id}" for c in grade_columns])
        if len(written_columns) > 1:
            fixed_columns.append("written_total")
        if len(sonstige_columns) > 1:
            fixed_columns.append("sonstige_total")
        fixed_columns.append("overall")
        self._doc_fixed_column_ids = list(fixed_columns)
        self._doc_axis = DocColumnAxis(self._doc_date_column_ids, fixed_columns)
        self._validate_doc_sort_spec()

        self.docs_tree.configure(columns=self._doc_axis.pane_columns(DocsPane.MAIN))
        self.docs_right_tree.configure(columns=self._doc_axis.pane_columns(DocsPane.RIGHT))
        for idx, date_key in enumerate(all_dates):
            self.docs_tree.column(self._doc_date_column_ids[idx], width=120, anchor="center", stretch=False)
            self.docs_tree.heading(self._doc_date_column_ids[idx], text=date_key)
        self.docs_right_tree.column("summary", width=180, anchor="w", stretch=False)
        for fixed_col_id in fixed_columns[1:]:
            self.docs_right_tree.column(fixed_col_id, width=120, anchor="center", stretch=False)

        # Einmalig vorberechnen statt (wie zuvor) pro Schüler x Spalte erneut zu
        # sortieren/scannen: session_for_date() als Dict, sowie die jeweils
        # neuesten Noten/Symbole für ALLE Schüler in einem Durchlauf. Das ist
        # der Kern des O(Schüler x Sessions²)-Fixes — siehe compute_latest_grades_by_student
        # und summarize_latest_symbols_by_student.
        sessions_by_date = {s.date: s for s in self.current_plan.documentation.sessions}
        students_by_coord = {(s.seat.x, s.seat.y): s for s in self.current_plan.classroom.students}
        latest_grades_by_student = compute_latest_grades_by_student(self.current_plan)
        latest_symbols_by_student = summarize_latest_symbols_by_student(self.current_plan)
        # Einmal sammeln, an alle drei Anzeige-Funktionen weiterreichen — sonst
        # würde jede für sich nochmal alle Sessions scannen (siehe Docstring
        # von collect_grade_value_lists_by_student).
        grade_value_lists = collect_grade_value_lists_by_student(self.current_plan)
        overall_display_by_student = compute_grade_display_by_student(
            self.current_plan, value_lists=grade_value_lists
        )
        written_subtotal_by_student = (
            compute_grade_subtotal_display_by_student(self.current_plan, "schriftlich", value_lists=grade_value_lists)
            if "written_total" in fixed_columns else {}
        )
        sonstige_subtotal_by_student = (
            compute_grade_subtotal_display_by_student(self.current_plan, "sonstig", value_lists=grade_value_lists)
            if "sonstige_total" in fixed_columns else {}
        )

        rows: dict[str, DocRow] = {}
        iid_by_coord_index: dict[int, str] = {}

        for coord_index, (x, y) in enumerate(self._doc_student_coords):
            student = students_by_coord.get((x, y))
            if student is None:
                continue
            date_values: list[str] = []
            for date_key in all_dates:
                session = sessions_by_date.get(date_key)
                entry = session.entry_for(student.student_id) if session else None
                date_values.append(
                    self._documentation_cell_text(entry.symbols, entry.participation) if entry else ""
                )
            summary_symbols = latest_symbols_by_student.get(student.student_id, {})
            fixed_values: list[str] = [self._documentation_cell_text(summary_symbols)]
            student_latest_grades = latest_grades_by_student.get(student.student_id, {})
            for grade in grade_columns:
                raw_grade = student_latest_grades.get(grade.column_id)
                fixed_values.append(f"{raw_grade:.2f}" if raw_grade is not None else "")
            if "written_total" in fixed_columns:
                fixed_values.append(written_subtotal_by_student.get(student.student_id, ""))
            if "sonstige_total" in fixed_columns:
                fixed_values.append(sonstige_subtotal_by_student.get(student.student_id, ""))
            fixed_values.append(overall_display_by_student.get(student.student_id, ""))

            iid = str(student.student_id)
            rows[iid] = DocRow(
                iid=iid,
                nachname=student.last_name.strip() or f"({x},{y})",
                vorname=student.first_name.strip(),
                date_cells=tuple(date_values),
                fixed_cells=tuple(fixed_values),
            )
            iid_by_coord_index[coord_index] = iid

        self._project_doc_rows(rows)
        self._doc_rows = rows
        self._doc_tree_iid_by_student_index = iid_by_coord_index
        self._doc_student_index_by_iid = {iid: idx for idx, iid in iid_by_coord_index.items()}
        self._apply_doc_row_order()

        if self._doc_student_coords:
            self._doc_selected_student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
            selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
            if selected_iid is not None:
                self._set_docs_row_selection(selected_iid)
        else:
            self._doc_selected_student_index = 0
            self._doc_selected_date_index = 0

        self._clamp_doc_column_selection_after_rebuild(len(all_dates))
        self._apply_doc_column_heading_highlight()

        elapsed = time.perf_counter() - started
        if elapsed >= 0.2:
            LOGGER.info(
                "_refresh_documentation_table finished in %.3fs (students=%d dates=%d)",
                elapsed,
                len(self._doc_student_coords),
                len(self._doc_dates),
            )

    def _validate_doc_sort_spec(self) -> None:
        """Setzt die Sortierspezifikation zurück, falls ihre Spalte nach einem Rebuild fehlt.

        Beispiel: Sortierung nach einer inzwischen gelöschten Notenspalte →
        ``_doc_sort_column = None`` (Basisreihenfolge), ``_doc_sort_ascending = True``.
        Eine weiterhin gültige Sortierung bleibt unverändert erhalten.
        """
        if self._doc_sort_column is not None and not self._doc_axis.has(self._doc_sort_column):
            self._doc_sort_column = None
            self._doc_sort_ascending = True

    def _project_doc_rows(self, rows: dict[str, DocRow]) -> None:
        """Einzige Stelle für Insert/Update/Delete von Tabellenzeilen in allen drei Treeviews.

        Fast Path: gleiche iid-Menge wie zuletzt (Normalfall bei einem
        einzelnen Symbol-/Noten-Edit) → nur geänderte ``DocRow``s per
        ``item()`` aktualisieren. Sonst alle drei Trees leeren und in
        Basisreihenfolge neu befüllen. Reihenfolge, Auswahl, Fokus und
        Markierung werden getrennt davon synchronisiert
        (``_apply_doc_row_order``, ``_set_docs_row_selection``, …).

        Args:
            rows: Neue Zeilen (iid → ``DocRow``) in Basisreihenfolge.
        """
        trees = self._docs_trees_by_pane()
        desired = set(rows)
        same_row_set = all(set(tree.get_children()) == desired for tree in trees.values())
        if same_row_set:
            for iid, row in rows.items():
                if self._doc_rows.get(iid) != row:
                    self._write_doc_row(row, insert=False)
            return
        for tree in trees.values():
            children = tree.get_children()
            if children:
                tree.delete(*children)
        for row in rows.values():
            self._write_doc_row(row, insert=True)

    def _write_doc_row(self, row: DocRow, *, insert: bool) -> None:
        """Schreibt die drei Projektionen einer Zeile in ihre Treeviews.

        Args:
            row: Zu schreibende Zeile.
            insert: ``True`` → am Ende einfügen, ``False`` → bestehendes Item aktualisieren.
        """
        text, name_values = row.names_projection()
        if insert:
            self.docs_name_tree.insert("", "end", iid=row.iid, text=text, values=name_values)
            self.docs_tree.insert("", "end", iid=row.iid, values=row.main_projection())
            self.docs_right_tree.insert("", "end", iid=row.iid, values=row.right_projection())
            return
        self.docs_name_tree.item(row.iid, text=text, values=name_values)
        self.docs_tree.item(row.iid, values=row.main_projection())
        self.docs_right_tree.item(row.iid, values=row.right_projection())

    def _apply_doc_row_order(self) -> None:
        """Berechnet die Zeilenreihenfolge und ordnet alle drei Treeviews danach.

        Ergebnis von ``sort_iids(_doc_rows, Sortierspezifikation)``; wird als
        ``self._doc_row_order`` gemerkt (Quelle für die visuelle Reihenfolge,
        z. B. bei ↑/↓).

        Die Reihenfolge wird ausschließlich aus ``self._doc_rows`` (Basisreihenfolge)
        und ``_doc_sort_column`` / ``_doc_sort_ascending`` berechnet; der
        Abgleich mit ``get_children()`` dient nur dazu, unnötige ``move()``-
        Aufrufe zu sparen.
        """
        order = sort_iids(self._doc_rows.values(), self._doc_sort_column, self._doc_sort_ascending, self._doc_axis)
        self._doc_row_order = order
        for tree in self._docs_trees_by_pane().values():
            if list(tree.get_children("")) == order:
                continue
            for index, iid in enumerate(order):
                tree.move(iid, "", index)
