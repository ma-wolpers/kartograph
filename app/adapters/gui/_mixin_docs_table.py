"""Docs-Tabellen-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Stellt die Hauptmethode ``_refresh_documentation_table`` bereit, die alle
Treeview-Spalten und -Zeilen neu aufbaut, sowie den Inline-Noten-Editor
und die Hilfsmethode für den letzten Notenwert einer Spalte.
"""

from __future__ import annotations

import time

from app.adapters.gui.main_window_constants import LOGGER
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.grade_usecases import compute_grade_display, compute_grade_subtotal_display
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui import ui
from bw_gui.runtime import widgets as tui


class DocsTableMixin:
    """Mixin: Dokumentations-Tabellenaufbau und Inline-Noten-Editor (v4)."""

    def _latest_grade_value_for_column(self, student_id: StudentId, column_id: str) -> str:
        """Gibt den zuletzt eingetragenen Notenwert für eine Spalte als formatierten String zurück.

        Args:
            student_id: ID des Schülers, dessen Notenverlauf durchsucht wird.
            column_id: ID der Notenspalte innerhalb der Dokumentationseinträge.
        """
        if not self.current_plan:
            return ""
        latest: float | None = None
        for session in sorted(self.current_plan.documentation.sessions, key=lambda s: s.date):
            entry = session.entry_for(student_id)
            if entry is None:
                continue
            value = entry.grades.get(column_id)
            if value is None:
                continue
            latest = float(value)
        if latest is None:
            return ""
        return f"{latest:.2f}"

    def _open_docs_inline_grade_editor(self, row_id: str, fixed_column_id: str) -> None:
        """Öffnet einen Entry-Inline-Editor in der Noten-Zelle des rechten Treeviews.

        Args:
            row_id: Treeview-Zeilen-ID (iid) der Zielzeile im rechten Treeview.
            fixed_column_id: ID der festen Spalte, z. B. ``"grade_<spalte>"``.
        """
        if not self.current_plan:
            return
        if not fixed_column_id.startswith("grade_"):
            return
        if row_id not in self.docs_right_tree.get_children():
            return

        self._close_docs_inline_editor(apply_changes=False)

        fixed_index = self._doc_fixed_column_ids.index(fixed_column_id)
        tree_column = f"#{fixed_index + 1}"
        bbox = self.docs_right_tree.bbox(row_id, tree_column)
        if not bbox:
            return
        x, y, width, height = bbox

        selected = self._selected_docs_coordinates_and_date()
        if selected is None:
            return
        coords_x, coords_y, date_key = selected
        model_column_id = fixed_column_id[len("grade_"):]

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

        editor = tui.Entry(self.docs_right_tree)
        editor.insert(0, current_text)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.selection_range(0, ui.END)
        editor.bind("<Return>", self._on_docs_inline_editor_return)
        editor.bind("<KP_Enter>", self._on_docs_inline_editor_return)
        editor.bind("<Escape>", self._on_docs_inline_editor_escape)
        editor.bind("<FocusOut>", lambda _event: self._close_docs_inline_editor(apply_changes=True))

        self._docs_inline_editor = editor
        self._docs_inline_editor_tree = self.docs_right_tree
        self._docs_inline_editor_row_id = row_id
        self._docs_inline_editor_kind = "grade"
        self._docs_inline_editor_model_column = model_column_id

    def _refresh_documentation_table(self) -> None:
        """Baut die gesamte Dokumentations-Tabelle (beide Treeviews) vollständig neu auf (v4)."""
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

        self.docs_tree.configure(columns=["vorname"] + self._doc_date_column_ids)
        self.docs_right_tree.configure(columns=fixed_columns)

        self.docs_tree.column("vorname", width=120, anchor="w", stretch=False)
        self.docs_tree.heading("vorname", text="Vorname")
        for idx, date_key in enumerate(all_dates):
            self.docs_tree.column(self._doc_date_column_ids[idx], width=120, anchor="center", stretch=False)
            self.docs_tree.heading(self._doc_date_column_ids[idx], text=date_key)

        self.docs_right_tree.column("summary", width=180, anchor="w", stretch=False)
        self.docs_right_tree.heading("summary", text="Zusammenfassung")
        for grade in grade_columns:
            col_id = f"grade_{grade.column_id}"
            self.docs_right_tree.column(col_id, width=120, anchor="center", stretch=False)
            self.docs_right_tree.heading(col_id, text=grade.title)
        if "written_total" in fixed_columns:
            self.docs_right_tree.column("written_total", width=120, anchor="center", stretch=False)
            self.docs_right_tree.heading("written_total", text="Schriftlich gesamt")
        if "sonstige_total" in fixed_columns:
            self.docs_right_tree.column("sonstige_total", width=120, anchor="center", stretch=False)
            self.docs_right_tree.heading("sonstige_total", text="Sonstig gesamt")
        self.docs_right_tree.column("overall", width=120, anchor="center", stretch=False)
        self.docs_right_tree.heading("overall", text="Gesamtnote")

        for row_id in self.docs_tree.get_children():
            self.docs_tree.delete(row_id)
        for row_id in self.docs_right_tree.get_children():
            self.docs_right_tree.delete(row_id)
        self._doc_tree_iid_by_student_index = {}
        self._doc_student_index_by_iid = {}

        for student_idx, (x, y) in enumerate(self._doc_student_coords):
            student = self.current_plan.student_at(x, y)
            if student is None:
                continue
            date_values: list[str] = []
            for date_key in all_dates:
                session = self.current_plan.documentation.session_for_date(date_key)
                entry = session.entry_for(student.student_id) if session else None
                date_values.append(self._documentation_cell_text(entry.symbols) if entry else "")
            fixed_values: list[str] = [self._documentation_summary_text(x, y)]
            fixed_values.extend(
                self._latest_grade_value_for_column(student.student_id, grade.column_id)
                for grade in grade_columns
            )
            if "written_total" in fixed_columns:
                fixed_values.append(compute_grade_subtotal_display(self.current_plan, student.student_id, "schriftlich"))
            if "sonstige_total" in fixed_columns:
                fixed_values.append(compute_grade_subtotal_display(self.current_plan, student.student_id, "sonstig"))
            fixed_values.append(compute_grade_display(self.current_plan, student.student_id))

            iid = f"student_{student_idx}"
            first_n = student.first_name.strip()
            last_n = student.last_name.strip()
            self.docs_tree.insert("", "end", iid=iid, text=last_n or f"({x},{y})", values=[first_n] + date_values)
            self.docs_right_tree.insert("", "end", iid=iid, values=fixed_values)
            self._doc_tree_iid_by_student_index[student_idx] = iid
            self._doc_student_index_by_iid[iid] = student_idx

        if self._doc_student_coords:
            self._doc_selected_student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
            self._doc_selected_date_index = max(0, min(self._doc_selected_date_index, max(0, len(all_dates) - 1)))
            selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
            if selected_iid is not None:
                self._set_docs_row_selection(selected_iid)
        else:
            self._doc_selected_student_index = 0
            self._doc_selected_date_index = 0

        if self._doc_selected_fixed_column_id not in set(self._doc_fixed_column_ids):
            self._doc_selected_fixed_column_id = None

        self._apply_doc_column_heading_highlight()
        self._apply_doc_sort_order()
        self._refresh_doc_selection_status()

        elapsed = time.perf_counter() - started
        if elapsed >= 0.2:
            LOGGER.info(
                "_refresh_documentation_table finished in %.3fs (students=%d dates=%d)",
                elapsed,
                len(self._doc_student_coords),
                len(self._doc_dates),
            )

    def _apply_doc_sort_order(self) -> None:
        """Sortiert beide Treeview-Zeilen gemäß dem aktuellen Sortierstatus."""
        if self._doc_sort_column is None:
            return
        sort_key = self._doc_sort_column
        iids = list(self.docs_tree.get_children(""))

        def get_sort_value(iid: str):
            if sort_key == "nachname":
                return (self.docs_tree.item(iid, "text").lower(),)
            if sort_key == "vorname":
                values = self.docs_tree.item(iid, "values")
                return (str(values[0]).lower() if values else "",)
            if sort_key in self._doc_date_column_ids:
                idx = self._doc_date_column_ids.index(sort_key)
                values = self.docs_tree.item(iid, "values")
                raw = str(values[idx + 1]) if values and idx + 1 < len(values) else ""
                return (raw,)
            if sort_key in self._doc_fixed_column_ids:
                idx = self._doc_fixed_column_ids.index(sort_key)
                values = self.docs_right_tree.item(iid, "values")
                raw = str(values[idx]) if values and idx < len(values) else ""
                try:
                    return (0, float(raw))
                except (ValueError, TypeError):
                    return (1, raw.lower())
            return ("",)

        sorted_iids = sorted(iids, key=get_sort_value, reverse=not self._doc_sort_ascending)
        for i, iid in enumerate(sorted_iids):
            self.docs_tree.move(iid, "", i)
            self.docs_right_tree.move(iid, "", i)
