"""Tests für v4 grade_usecases."""

from app.core.domain.grade_scale import SCALE_POINTS_0_15
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.grade_usecases import (
    add_grade_column,
    collect_grade_value_lists_by_student,
    compute_grade_display,
    compute_grade_display_by_student,
    compute_grade_subtotal_display,
    compute_grade_subtotal_display_by_student,
    record_grade,
    set_grade_weighting,
)
from tests.conftest import make_plan, make_student


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

    def test_records_grade(self):
        plan, sid, col_id = self._setup()
        assert record_grade(plan, sid, col_id, 2.0).documentation.grade_of(sid, col_id) == 2.0

    def test_clamps_grade_below_one_plus(self):
        plan, sid, col_id = self._setup()
        assert record_grade(plan, sid, col_id, 0.0).documentation.grade_of(sid, col_id) == 0.7

    def test_points_scale_keeps_zero_and_clamps_above_15(self):
        plan, sid, col_id = self._setup()
        plan.documentation.grade_scale = SCALE_POINTS_0_15
        result = record_grade(plan, sid, col_id, 0.0)
        assert result.documentation.grade_of(sid, col_id) == 0.0
        result = record_grade(result, sid, col_id, 16.0)
        assert result.documentation.grade_of(sid, col_id) == 15.0

    def test_clamps_grade_above_6(self):
        plan, sid, col_id = self._setup()
        assert record_grade(plan, sid, col_id, 9.0).documentation.grade_of(sid, col_id) == 6.0

    def test_no_effect_for_unknown_column(self):
        plan, sid, _ = self._setup()
        assert record_grade(plan, sid, "unbekannt", 3.0).documentation.grades == {}

    def test_no_effect_for_unnamed_student(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(first_name="", student_id=sid)])
        plan, col_id = add_grade_column(plan, "schriftlich", "A")
        assert record_grade(plan, sid, col_id, 3.0).documentation.grades == {}


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
            plan = record_grade(plan, sid, col_w, written)
        if sonstige is not None:
            plan, col_s = add_grade_column(plan, "sonstig", "S")
            plan = record_grade(plan, sid, col_s, sonstige)
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
        plan = record_grade(plan, sid_a, col_w, 2.0)
        plan = record_grade(plan, sid_a, col_s, 3.0)
        plan = record_grade(plan, sid_b, col_w, 5.0)
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
        plan = record_grade(plan, sid, col, 3.0)

        without_shared = compute_grade_display_by_student(plan)
        value_lists = collect_grade_value_lists_by_student(plan)
        with_shared = compute_grade_display_by_student(plan, value_lists=value_lists)

        assert without_shared == with_shared

    def test_unnamed_student_excluded(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(first_name="", last_name="", student_id=sid)])
        plan, col = add_grade_column(plan, "schriftlich", "W")
        plan = record_grade(plan, sid, col, 3.0)
        assert compute_grade_display_by_student(plan).get(sid, "") == ""


class TestColumnWeights:
    """Spaltenfaktoren innerhalb einer Kategorie (``GradeColumn.weight``)."""

    def _plan(self, sonstige: list[tuple[float, float | None]], written: float | None = None):
        """Plan mit einer Person; *sonstige* = [(Faktor, Note oder None)], optional eine schriftliche Note."""
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        if written is not None:
            plan, col_w = add_grade_column(plan, "schriftlich", "W")
            plan = record_grade(plan, sid, col_w, written)
        for index, (weight, grade) in enumerate(sonstige):
            plan, col = add_grade_column(plan, "sonstig", f"S{index}", weight)
            if grade is not None:
                plan = record_grade(plan, sid, col, grade)
        return set_grade_weighting(plan, 60, 40), sid

    def test_factor_weights_the_category_mean(self):
        # (1*2 + 4*1) / 3 = 2; ungewichtet wäre 2.5 -> 3
        plan, sid = self._plan([(2.0, 1.0), (1.0, 4.0)])
        assert compute_grade_subtotal_display(plan, sid, "sonstig") == "2"

    def test_factor_zero_does_not_count(self):
        plan, sid = self._plan([(0.0, 6.0), (1.0, 2.0)])
        assert compute_grade_subtotal_display(plan, sid, "sonstig") == "2"

    def test_category_with_only_zero_factors_counts_as_empty(self):
        plan, sid = self._plan([(0.0, 2.0)], written=3.0)
        assert compute_grade_subtotal_display(plan, sid, "sonstig") == ""
        assert compute_grade_display(plan, sid) == "(3)"

    def test_missing_grade_redistributes_its_weight(self):
        plan, sid = self._plan([(2.0, None), (1.0, 4.0)])
        assert compute_grade_subtotal_display(plan, sid, "sonstig") == "4"

    def test_overall_uses_weighted_category_mean(self):
        # sonstig (1*2 + 4*1) / 3 = 2; 60 % * 3 + 40 % * 2 = 2.6
        plan, sid = self._plan([(2.0, 1.0), (1.0, 4.0)], written=3.0)
        assert compute_grade_display(plan, sid) == "2.60"
        assert compute_grade_display_by_student(plan)[sid] == "2.60"
        assert compute_grade_subtotal_display_by_student(plan, "sonstig")[sid] == "2"

    def test_add_grade_column_stores_normalized_weight(self, plan):
        result, col_id = add_grade_column(plan, "sonstig", "Referat", 2.5)
        assert result.documentation.column_by_id(col_id).weight == 2.5
        result, col_id = add_grade_column(result, "sonstig", "Heft", -1.0)
        assert result.documentation.column_by_id(col_id).weight == 0.0

    def test_set_grade_weighting_applies_column_weights_in_one_step(self, plan):
        plan, col_a = add_grade_column(plan, "sonstig", "A")
        plan, col_b = add_grade_column(plan, "sonstig", "B", 3.0)
        result = set_grade_weighting(plan, 70, 30, {col_a: 2.0, "unbekannt": 5.0})
        assert result.documentation.weighting.written_percent == 70
        assert result.documentation.column_by_id(col_a).weight == 2.0
        assert result.documentation.column_by_id(col_b).weight == 3.0  # nicht genannt -> unverändert
        assert plan.documentation.column_by_id(col_a).weight == 1.0  # Ausgangsplan unverändert
