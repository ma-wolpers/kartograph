"""Tests für v4 grade_scale_usecases (Skalenwechsel inkl. Umrechnung)."""

from app.core.domain.grade_scale import SCALE_POINTS_0_15, SCALE_SCHOOL_1_6
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.grade_scale_usecases import count_grades, set_grade_scale
from app.core.usecases.v4.grade_usecases import add_grade_column, record_grade
from tests.conftest import make_plan, make_student


def _plan_with_grades():
    sid = StudentId.new()
    plan = make_plan(students=[make_student(student_id=sid)])
    plan, col = add_grade_column(plan, "schriftlich", "Arbeit 1")
    plan = record_grade(plan, sid, "2025-09-01", col, 3.2)
    plan = record_grade(plan, sid, "2025-09-08", col, 3.15)
    plan = record_grade(plan, sid, "2025-09-15", col, 2.5)
    return plan, sid, col


def _values(plan, sid, col):
    return [
        plan.documentation.session_for_date(d).entries[sid].grades[col]
        for d in ("2025-09-01", "2025-09-08", "2025-09-15")
    ]


def test_count_grades_over_all_sessions():
    plan, _, _ = _plan_with_grades()
    assert count_grades(plan) == 3
    assert count_grades(make_plan()) == 0


def test_switch_to_points_converts_every_session():
    plan, sid, col = _plan_with_grades()
    result = set_grade_scale(plan, SCALE_POINTS_0_15)
    assert result.documentation.grade_scale == SCALE_POINTS_0_15
    assert _values(result, sid, col) == [7.0, 7.5, 9.5]
    assert _values(plan, sid, col) == [3.2, 3.15, 2.5]  # Original unverändert


def test_switch_back_to_school_grades():
    plan, sid, col = _plan_with_grades()
    back = set_grade_scale(set_grade_scale(plan, SCALE_POINTS_0_15), SCALE_SCHOOL_1_6)
    assert back.documentation.grade_scale == SCALE_SCHOOL_1_6
    assert _values(back, sid, col) == [3.3, 3.15, 2.5]


def test_same_scale_is_noop():
    plan, sid, col = _plan_with_grades()
    result = set_grade_scale(plan, SCALE_SCHOOL_1_6)
    assert _values(result, sid, col) == [3.2, 3.15, 2.5]
