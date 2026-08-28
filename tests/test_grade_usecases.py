"""Tests für v4 grade_usecases."""

from app.core.domain.student_id import StudentId
from app.core.usecases.v4.grade_usecases import (
    add_grade_column,
    collect_grade_value_lists_by_student,
    compute_grade_display,
    compute_grade_display_by_student,
    compute_grade_subtotal_display,
    compute_grade_subtotal_display_by_student,
    compute_latest_grades_by_student,
    record_grade,
    set_grade_weighting,
)
from tests.conftest import make_plan, make_student


DATE = "2025-09-01"


class TestAddGradeColumn:
    def test_adds_column_with_valid_category(self, plan):
        result, col_id = add_grade_column(plan, "schriftlich", "Mathearbeit 1")
        assert col_id
        assert result.documentation.column_by_id(col_id) is not None

    def test_returns_empty_id_for_invalid_category(self, plan):
        _, col_id = add_grade_column(plan, "falsch", "Titel")
        assert col_id == ""

    def test_generates_unique_ids(self, plan):
        _, id1 = add_grade_column(plan, "schriftlich", "A")
        _, id2 = add_grade_column(plan, "schriftlich", "B")
        assert id1 != id2


class TestRecordGrade:
    def _setup(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        plan, col_id = add_grade_column(plan, "schriftlich", "Arbeit 1")
        return plan, sid, col_id

    def test_records_grade_in_session(self):
        plan, sid, col_id = self._setup()
        result = record_grade(plan, sid, DATE, col_id, 2.0)
        entry = result.documentation.sessions[0].entries[sid]
        assert entry.grades[col_id] == 2.0

    def test_clamps_grade_below_1(self):
        plan, sid, col_id = self._setup()
        result = record_grade(plan, sid, DATE, col_id, 0.0)
        entry = result.documentation.sessions[0].entries[sid]
        assert entry.grades[col_id] == 1.0

    def test_clamps_grade_above_6(self):
        plan, sid, col_id = self._setup()
        result = record_grade(plan, sid, DATE, col_id, 9.0)
        entry = result.documentation.sessions[0].entries[sid]
        assert entry.grades[col_id] == 6.0

    def test_none_removes_grade(self):
        plan, sid, col_id = self._setup()
        r1 = record_grade(plan, sid, DATE, col_id, 3.0)
        r2 = record_grade(r1, sid, DATE, col_id, None)
        session = r2.documentation.session_for_date(DATE)
        assert sid not in session.entries

    def test_no_effect_for_unknown_column(self):
        plan, sid, _ = self._setup()
        result = record_grade(plan, sid, DATE, "unbekannt", 3.0)
        assert result.documentation.sessions == []

    def test_no_effect_for_unnamed_student(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(first_name="", student_id=sid)])
        plan, col_id = add_grade_column(plan, "schriftlich", "A")
        result = record_grade(plan, sid, DATE, col_id, 3.0)
        session = result.documentation.session_for_date(DATE)
        assert sid not in (session.entries if session else {})


class TestSetGradeWeighting:
    def test_sets_weighting(self, plan):
        result = set_grade_weighting(plan, 60, 40)
        assert result.documentation.weighting.written_percent == 60
        assert result.documentation.weighting.sonstige_percent == 40

    def test_clamps_negative(self, plan):
        result = set_grade_weighting(plan, -10, 50)
        assert result.documentation.weighting.written_percent == 0

    def test_fallback_for_zero_total(self, plan):
        result = set_grade_weighting(plan, 0, 0)
        assert result.documentation.weighting.written_percent == 50


class TestComputeGradeDisplay:
    def _plan_with_grades(self, written: float | None, sonstige: float | None):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        if written is not None:
            plan, col_w = add_grade_column(plan, "schriftlich", "W")
            plan = record_grade(plan, sid, DATE, col_w, written)
        if sonstige is not None:
            plan, col_s = add_grade_column(plan, "sonstig", "S")
            plan = record_grade(plan, sid, "2025-09-02", col_s, sonstige)
        plan = set_grade_weighting(plan, 60, 40)
        return plan, sid

    def test_returns_empty_when_no_grades(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        assert compute_grade_display(plan, sid) == ""

    def test_provisional_when_only_written(self):
        plan, sid = self._plan_with_grades(written=3.0, sonstige=None)
        display = compute_grade_display(plan, sid)
        assert display == "(3)"

    def test_provisional_when_only_sonstige(self):
        plan, sid = self._plan_with_grades(written=None, sonstige=2.0)
        display = compute_grade_display(plan, sid)
        assert display == "(2)"

    def test_weighted_total_with_both(self):
        plan, sid = self._plan_with_grades(written=3.0, sonstige=2.0)
        # 60% * 3 + 40% * 2 = 1.8 + 0.8 = 2.6
        display = compute_grade_display(plan, sid)
        assert display == "2.60"

    def test_no_provisional_when_flag_false(self):
        plan, sid = self._plan_with_grades(written=3.0, sonstige=None)
        display = compute_grade_display(plan, sid, allow_provisional=False)
        assert display == ""


class TestComputeLatestGradesByStudent:
    """Regressionstest für den Doku-Tabellen-Perf-Fix (2026-08-28).

    ``compute_latest_grades_by_student`` ersetzt eine pro (Schüler, Spalte)
    neu sortierende Berechnung durch einen einzigen Durchlauf über alle
    Sessions. Muss für jede (Schüler, Spalte)-Kombination denselben Wert
    liefern wie die (bewusst langsame) Referenzimplementierung unten.
    """

    @staticmethod
    def _reference_latest(plan, student_id, column_id) -> float | None:
        latest = None
        for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
            entry = session.entry_for(student_id)
            if entry is None:
                continue
            value = entry.grades.get(column_id)
            if value is None:
                continue
            latest = float(value)
        return latest

    def test_matches_reference_for_multiple_students(self):
        sid_a, sid_b = StudentId.new(), StudentId.new()
        plan = make_plan(students=[
            make_student(student_id=sid_a, x=0),
            make_student(student_id=sid_b, x=1),
        ])
        plan, col = add_grade_column(plan, "schriftlich", "Arbeit")
        plan = record_grade(plan, sid_a, "2025-09-01", col, 2.0)
        plan = record_grade(plan, sid_a, "2025-09-05", col, 4.0)
        plan = record_grade(plan, sid_b, "2025-09-03", col, 1.0)

        result = compute_latest_grades_by_student(plan)

        assert result[sid_a][col] == self._reference_latest(plan, sid_a, col) == 4.0
        assert result[sid_b][col] == self._reference_latest(plan, sid_b, col) == 1.0

    def test_sorts_by_date_not_insertion_order(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        plan, col = add_grade_column(plan, "schriftlich", "Arbeit")
        plan = record_grade(plan, sid, "2025-09-10", col, 5.0)
        plan = record_grade(plan, sid, "2025-09-02", col, 1.0)  # später eingefügt, aber früheres Datum
        assert compute_latest_grades_by_student(plan)[sid][col] == 5.0

    def test_student_without_grades_missing_from_result(self, anna_id, plan_with_anna):
        assert anna_id not in compute_latest_grades_by_student(plan_with_anna)


class TestBulkGradeDisplay:
    """Regressionstest: Bulk-Varianten müssen dieselben Werte liefern wie die

    Einzelschüler-Funktionen, sowohl mit als auch ohne vorberechnete
    ``value_lists`` (geteilte Sessions-Sammlung).
    """

    def test_matches_single_student_functions_across_multiple_students(self):
        sid_a, sid_b, sid_c = StudentId.new(), StudentId.new(), StudentId.new()
        plan = make_plan(students=[
            make_student(student_id=sid_a, x=0),
            make_student(student_id=sid_b, x=1),
            make_student(student_id=sid_c, x=2),
        ])
        plan, col_w = add_grade_column(plan, "schriftlich", "W")
        plan, col_s = add_grade_column(plan, "sonstig", "S")
        plan = record_grade(plan, sid_a, "2025-09-01", col_w, 2.0)
        plan = record_grade(plan, sid_a, "2025-09-02", col_s, 3.0)
        plan = record_grade(plan, sid_b, "2025-09-01", col_w, 5.0)
        # sid_c bekommt bewusst keine Note.
        plan = set_grade_weighting(plan, 60, 40)

        overall = compute_grade_display_by_student(plan)
        written = compute_grade_subtotal_display_by_student(plan, "schriftlich")
        sonstig = compute_grade_subtotal_display_by_student(plan, "sonstig")

        for sid in (sid_a, sid_b, sid_c):
            assert overall.get(sid, "") == compute_grade_display(plan, sid)
            assert written.get(sid, "") == compute_grade_subtotal_display(plan, sid, "schriftlich")
            assert sonstig.get(sid, "") == compute_grade_subtotal_display(plan, sid, "sonstig")

    def test_shared_value_lists_gives_identical_results(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        plan, col = add_grade_column(plan, "schriftlich", "W")
        plan = record_grade(plan, sid, DATE, col, 3.0)

        without_shared = compute_grade_display_by_student(plan)
        value_lists = collect_grade_value_lists_by_student(plan)
        with_shared = compute_grade_display_by_student(plan, value_lists=value_lists)

        assert without_shared == with_shared

    def test_unnamed_student_excluded(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(first_name="", last_name="", student_id=sid)])
        plan, col = add_grade_column(plan, "schriftlich", "W")
        plan = record_grade(plan, sid, DATE, col, 3.0)
        assert compute_grade_display_by_student(plan).get(sid, "") == ""
