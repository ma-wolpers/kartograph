"""Docs-Tabellen-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Baut die logische Dokutabelle (``DocRow`` je Schüler + ``DocColumnAxis``)
aus den Domänendaten auf und übergibt sie dem bw-gui ``DataGrid``. Das Grid
ist reine Projektion: Zeileninhalt, Reihenfolge und Sortierung kommen
ausschließlich aus ``self._doc_rows`` und der Sortierspezifikation
(``_doc_sort_column`` / ``_doc_sort_ascending``).
"""

from __future__ import annotations

import time

from app.adapters.gui._mixin_layout_docs import REGION_BY_PANE
from app.adapters.gui.docs_table_model import NACHNAME_KEY, SUMMARY_KEY, VORNAME_KEY, DocColumnAxis, DocRow
from app.adapters.gui.docs_table_rules import sort_iids
from app.adapters.gui.main_window_constants import LOGGER
from app.core.domain.grade_scale import scale_for
from app.core.usecases.v4.grade_usecases import (
    collect_grade_value_lists_by_student,
    compute_grade_display_by_student,
    compute_grade_subtotal_display_by_student,
    compute_latest_grades_by_student,
)
from app.core.usecases.v4.symbol_usecases import summarize_latest_symbols_by_student
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.widgets.data_grid import GridColumn, GridRow


class DocsTableMixin:
    """Mixin: Aufbau der logischen Dokutabelle und ihre Projektion ins ``DataGrid`` (v4)."""

    def _refresh_documentation_table(self) -> None:
        """Baut die logische Dokutabelle neu auf und übergibt sie dem ``DataGrid`` (v4).

        Ablauf: Domänendaten → ``DocRow``s (Basisreihenfolge = Sitzordnung) →
        neue ``DocColumnAxis`` → Sortierspezifikation validieren → Grid-Spalten →
        ``_apply_doc_row_order`` (Zeilen in Anzeigereihenfolge) → aktive
        Spalte gültig halten → ``_sync_docs_cursor``.
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

        self.docs_grid.set_columns(self._doc_grid_columns())

        # Einmalig vorberechnen statt (wie zuvor) pro Schüler x Spalte erneut zu
        # sortieren/scannen: session_for_date() als Dict, sowie die jeweils
        # neuesten Noten/Symbole für ALLE Schüler in einem Durchlauf. Das ist
        # der Kern des O(Schüler x Sessions²)-Fixes — siehe compute_latest_grades_by_student
        # und summarize_latest_symbols_by_student.
        sessions_by_date = {s.date: s for s in self.current_plan.documentation.sessions}
        students_by_coord = {(s.seat.x, s.seat.y): s for s in self.current_plan.classroom.students}
        latest_grades_by_student = compute_latest_grades_by_student(self.current_plan)
        grade_scale = scale_for(self.current_plan.documentation.grade_scale)
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
                fixed_values.append(grade_scale.format_value(raw_grade) if raw_grade is not None else "")
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

        self._doc_rows = rows
        self._doc_row_id_by_student_index = iid_by_coord_index
        self._doc_student_index_by_iid = {iid: idx for idx, iid in iid_by_coord_index.items()}
        self._apply_doc_row_order()

        if self._doc_student_coords:
            self._doc_selected_student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        else:
            self._doc_selected_student_index = 0
            self._doc_selected_date_index = 0

        self._clamp_doc_column_selection_after_rebuild(len(all_dates))
        self._sync_docs_cursor()

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

    def _doc_grid_columns(self) -> list[GridColumn]:
        """Leitet die Grid-Spalten aus der logischen Spaltenachse ab (Titel, Breite, Bereich).

        Breiten wie bisher: Nachname 150, Vorname 120, Zusammenfassung 180 px
        (linksbündig), alle übrigen Spalten 120 px zentriert; der globale
        Spaltenbreiten-Zoom skaliert sie im Grid.

        Returns:
            Spalten in Achsenreihenfolge.
        """
        layout = {NACHNAME_KEY: (150, "w"), VORNAME_KEY: (120, "w"), SUMMARY_KEY: (180, "w")}
        columns = []
        for key in self._doc_axis.keys:
            width, anchor = layout.get(key, (120, "center"))
            region = REGION_BY_PANE[self._doc_axis.pane_of(key)]
            columns.append(GridColumn(key, self._doc_column_label(key), width, region, anchor))
        return columns

    def _apply_doc_row_order(self) -> None:
        """Berechnet die Zeilenreihenfolge und übergibt die Zeilen samt Sortierpfeil an das Grid.

        Ergebnis von ``sort_iids(_doc_rows, Sortierspezifikation)``; wird als
        ``self._doc_row_order`` gemerkt (Quelle für die angezeigte Reihenfolge,
        z. B. bei ↑/↓). Das Grid gleicht selbst ab, welche sichtbaren Zellen sich
        geändert haben — ein einzelner Symbol-/Noten-Edit kostet daher nur die
        geänderten Zellen.
        """
        order = sort_iids(self._doc_rows.values(), self._doc_sort_column, self._doc_sort_ascending, self._doc_axis)
        self._doc_row_order = order
        self.docs_grid.set_rows([GridRow(iid, self._doc_axis.cells_of(self._doc_rows[iid])) for iid in order])
        self.docs_grid.set_sort_indicator(self._doc_sort_column, self._doc_sort_ascending)
