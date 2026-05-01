from __future__ import annotations

from app.core.domain.models import Desk, SeatingPlan
from app.core.usecases.plan_usecases import (
    add_grade_column,
    compute_grade_display_for_student,
    rename_documentation_date,
    set_documentation_grade,
    set_documentation_symbol,
    summarize_latest_symbols_for_student,
)


def _base_plan() -> SeatingPlan:
    return SeatingPlan(
        version=3,
        plan_id="test",
        name="Klasse 7A",
        desks=[
            Desk(x=0, y=0, desk_type="teacher"),
            Desk(x=1, y=1, desk_type="student", student_name="Alice"),
        ],
    )


def test_summary_prefers_latest_date_value() -> None:
    plan = _base_plan()
    plan = set_documentation_symbol(plan, 1, 1, "Beteiligung", 1, "2026-05-01")
    plan = set_documentation_symbol(plan, 1, 1, "Beteiligung", 3, "2026-05-02")

    summary = summarize_latest_symbols_for_student(plan, 1, 1)

    assert summary["Beteiligung"] == 3


def test_rename_date_moves_entries() -> None:
    plan = _base_plan()
    plan = set_documentation_symbol(plan, 1, 1, "Kooperation", 2, "2026-05-01")

    moved = rename_documentation_date(plan, "2026-05-01", "2026-05-03")

    student = moved.desk_at(1, 1)
    assert student is not None
    assert "2026-05-01" not in student.documentation_entries
    assert "2026-05-03" in student.documentation_entries


def test_grade_display_uses_weighted_rounded_subtotals() -> None:
    plan = _base_plan()
    plan, written_col = add_grade_column(plan, "schriftlich", "KA 1")
    plan, oral_col = add_grade_column(plan, "sonstig", "Mitarbeit")

    plan = set_documentation_grade(plan, 1, 1, written_col, 2.4, "2026-05-01")
    plan = set_documentation_grade(plan, 1, 1, written_col, 2.4, "2026-05-02")
    plan = set_documentation_grade(plan, 1, 1, oral_col, 3.6, "2026-05-01")

    display = compute_grade_display_for_student(plan, 1, 1)

    assert display == "3.00"


def test_grade_display_partial_data_in_parentheses() -> None:
    plan = _base_plan()
    plan, written_col = add_grade_column(plan, "schriftlich", "KA 1")
    plan = set_documentation_grade(plan, 1, 1, written_col, 2.4, "2026-05-01")

    display = compute_grade_display_for_student(plan, 1, 1)

    assert display == "(2)"


def test_documentation_symbols_ignore_unnamed_student_desks() -> None:
    plan = SeatingPlan(
        version=3,
        plan_id="test",
        name="Klasse 7A",
        desks=[
            Desk(x=0, y=0, desk_type="teacher"),
            Desk(x=1, y=1, desk_type="student", student_name=""),
        ],
    )

    updated = set_documentation_symbol(plan, 1, 1, "Beteiligung", 2, "2026-05-01")
    desk = updated.desk_at(1, 1)
    assert desk is not None
    assert desk.documentation_entries == {}


def test_grade_display_empty_for_unnamed_student_desks() -> None:
    plan = SeatingPlan(
        version=3,
        plan_id="test",
        name="Klasse 7A",
        desks=[
            Desk(x=0, y=0, desk_type="teacher"),
            Desk(x=1, y=1, desk_type="student", student_name=""),
        ],
    )
    plan, written_col = add_grade_column(plan, "schriftlich", "KA 1")
    plan = set_documentation_grade(plan, 1, 1, written_col, 3.0, "2026-05-01")

    display = compute_grade_display_for_student(plan, 1, 1)

    assert display == ""
