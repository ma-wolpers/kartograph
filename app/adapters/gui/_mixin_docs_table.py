"""Docs-Tabellen-Mixin für das Kartograph-Hauptfenster (v4-Modell).

Baut die logische Dokutabelle (``DocRow`` je Schüler + ``DocColumnAxis``)
aus den Domänendaten auf und übergibt sie dem bw-gui ``DataGrid``. Das Grid
ist reine Projektion: Zeileninhalt, Reihenfolge und Sortierung kommen
ausschließlich aus ``self._doc_rows`` und dem Sortierstapel
(``_doc_sort_stack``, s. ``docs_table_rules``).
"""

from __future__ import annotations

import time

from app.adapters.gui._mixin_layout_docs import regions_by_area
from app.adapters.gui.docs_table_model import (
    CATEGORY_TOTAL_KEYS,
    NACHNAME_KEY,
    NOTES_KEY,
    OVERALL_KEY,
    SUMMARY_KEY,
    VORNAME_KEY,
    DocColumnAxis,
    DocRow,
    grade_column_key,
)
from app.adapters.gui.docs_table_rules import retain_known_sort_keys, sort_iids
from app.adapters.gui.main_window_constants import LOGGER
from app.core.domain.data_view_areas import DataArea
from app.core.domain.grade_scale import scale_for
from app.core.domain.models_v4 import GRADE_CATEGORIES
from app.core.domain.permanent_absence import is_active
from app.core.domain.submission_status import CatalogSymbolMissing, submission_symbol_names
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
        # Teilnote "… gesamt" nur für Kategorien mit mehr als einer Spalte.
        total_categories = [
            category for category in GRADE_CATEGORIES
            if sum(1 for c in grade_columns if c.category == category) > 1
        ]

        fixed_columns: list[str] = [SUMMARY_KEY]
        fixed_columns.extend([grade_column_key(c.column_id) for c in grade_columns])
        fixed_columns.extend(CATEGORY_TOTAL_KEYS[category] for category in total_categories)
        fixed_columns.append(OVERALL_KEY)
        self._doc_fixed_column_ids = list(fixed_columns)
        visible_areas = self._doc_visible_areas()
        self._doc_axis = DocColumnAxis(self._doc_date_column_ids, fixed_columns, self._notes_area_columns(), visible_areas)
        self._validate_doc_sort_spec()
        show_dates, show_notes, show_grades = (area in visible_areas for area in (DataArea.DOKU, DataArea.NOTIZEN, DataArea.NOTEN))
        flag_keys = self._flag_keys() if show_notes else []

        self.docs_grid.set_columns(self._doc_grid_columns())

        # Einmalig vorberechnet statt pro Schüler x Spalte: session_for_date() als Dict.
        sessions_by_date = {s.date: s for s in self.current_plan.documentation.sessions}
        students_by_coord = {(s.seat.x, s.seat.y): s for s in self.current_plan.classroom.students}
        # Abgeleitete Notendaten aus der gemeinsamen Quelle (eine Berechnung pro
        # content_version, geteilt mit dem Raster) statt eigener Bulk-Aufrufe.
        derived = self._controller.derived()
        grades_by_student = self.current_plan.documentation.grades
        grade_scale = scale_for(self.current_plan.documentation.grade_scale)
        latest_symbols_by_student = derived.latest_symbols
        try:
            submission_names = submission_symbol_names(self._controller.state.symbol_catalog)
        except CatalogSymbolMissing:
            submission_names = None  # Abgabesymbol bewusst aus dem Katalog gelöscht: keine Bilanz
        submission_counts = derived.submission_counts(submission_names) if submission_names else {}
        overall_display_by_student = derived.grade_display
        subtotals_by_category = {category: derived.subtotal_display(category) for category in total_categories}

        rows: dict[str, DocRow] = {}
        iid_by_coord_index: dict[int, str] = {}

        for coord_index, (x, y) in enumerate(self._doc_student_coords):
            student = students_by_coord.get((x, y))
            if student is None:
                continue
            # Zellen nur für sichtbare Bereiche (die Datumszellen sind der teure Teil).
            cells: dict[str, str] = {}
            if show_dates:
                for column_id, date_key in zip(self._doc_date_column_ids, all_dates):
                    session = sessions_by_date.get(date_key)
                    entry = session.entry_for(student.student_id) if session else None
                    if entry:
                        cells[column_id] = self._documentation_cell_text(entry.symbols, entry.participation)
            if show_notes:
                cells.update(self._notes_area_cells(student, flag_keys))
            if show_grades:
                summary_symbols = latest_symbols_by_student.get(student.student_id, {})
                cells[SUMMARY_KEY] = self._documentation_summary_cell_text(
                    summary_symbols, submission_counts.get(student.student_id, {}), submission_names
                )
                student_grades = grades_by_student.get(student.student_id, {})
                for grade in grade_columns:
                    raw_grade = student_grades.get(grade.column_id)
                    if raw_grade is not None:
                        cells[grade_column_key(grade.column_id)] = grade_scale.format_value(raw_grade)
                for category in total_categories:
                    cells[CATEGORY_TOTAL_KEYS[category]] = subtotals_by_category[category].get(student.student_id, "")
                cells[OVERALL_KEY] = overall_display_by_student.get(student.student_id, "")

            iid = str(student.student_id)
            rows[iid] = DocRow(
                iid=iid,
                nachname=student.last_name.strip() or f"({x},{y})",
                vorname=student.first_name.strip(),
                cells=cells,
                inactive=not is_active(student),
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
        self._sync_data_area_controls()

        elapsed = time.perf_counter() - started
        if elapsed >= 0.2:
            LOGGER.info(
                "_refresh_documentation_table finished in %.3fs (students=%d dates=%d)",
                elapsed,
                len(self._doc_student_coords),
                len(self._doc_dates),
            )

    def _validate_doc_sort_spec(self) -> None:
        """Entfernt nach einem Rebuild die Sortierstufen, deren Spalte fehlt.

        Beispiel: Stapel ``(grade_x↑, nachname↑)`` und Notenspalte ``x`` wurde
        gelöscht → ``(nachname↑,)``; die übrigen Stufen bleiben erhalten
        (``retain_known_sort_keys``). Ohne Stufen gilt die Sitzordnung.
        """
        self._doc_sort_stack = retain_known_sort_keys(self._doc_sort_stack, self._doc_axis)

    def _doc_grid_columns(self) -> list[GridColumn]:
        """Leitet die Grid-Spalten aus der logischen Spaltenachse ab (Titel, Breite, Bereich).

        Breiten wie bisher: Nachname 150, Vorname 120, Zusammenfassung 180 px
        (linksbündig), alle übrigen Spalten 120 px zentriert; der globale
        Spaltenbreiten-Zoom skaliert sie im Grid.

        Returns:
            Spalten in Achsenreihenfolge.
        """
        layout = {NACHNAME_KEY: (150, "w"), VORNAME_KEY: (120, "w"), NOTES_KEY: (240, "w"), SUMMARY_KEY: (180, "w")}
        region_of = regions_by_area(self._doc_axis.areas)
        columns = []
        for key in self._doc_axis.keys:
            width, anchor = layout.get(key, (120, "center"))
            columns.append(GridColumn(key, self._doc_column_label(key), width, region_of[self._doc_axis.area_of(key)], anchor))
        return columns

    def _apply_doc_row_order(self) -> None:
        """Berechnet die Zeilenreihenfolge und übergibt die Zeilen samt Sortierpfeil an das Grid.

        Ergebnis von ``sort_iids(_doc_rows, _doc_sort_stack)``; wird als
        ``self._doc_row_order`` gemerkt (Quelle für die angezeigte Reihenfolge,
        z. B. bei ↑/↓). Das Grid gleicht selbst ab, welche sichtbaren Zellen sich
        geändert haben — ein einzelner Symbol-/Noten-Edit kostet daher nur die
        geänderten Zellen. Den Sortierpfeil trägt nur die wichtigste Stufe.
        """
        stack = self._doc_sort_stack
        order = sort_iids(self._doc_rows.values(), stack, self._doc_axis)
        self._doc_row_order = order
        rows = self._doc_rows
        self.docs_grid.set_rows([GridRow(iid, self._doc_axis.cells_of(rows[iid]), muted=rows[iid].inactive) for iid in order])
        head = stack[0] if stack else None
        self.docs_grid.set_sort_indicator(head.key if head else None, head.ascending if head else True)
