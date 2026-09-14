"""Gemeinsame Fixtures für v4-Tests."""

from __future__ import annotations

import pytest

from app.core.domain.models_v4 import (
    Classroom,
    DiagnosticProfile,
    DocumentationBlock,
    GradeColumn,
    PlanMeta,
    SeatingPlan,
    SeatingSnapshot,
    Seat,
    Student,
    TeacherSeat,
)
from app.core.domain.student_id import StudentId


def make_plan(
    *,
    students: list[Student] | None = None,
    name: str = "Testplan",
) -> SeatingPlan:
    """Erzeugt einen minimalen v4-SeatingPlan für Tests."""
    return SeatingPlan(
        format_version=4,
        plan_id="deadbeef" * 4,
        meta=PlanMeta(name=name, school_year="2025/2026"),
        classroom=Classroom(
            teacher_seat=TeacherSeat(x=0, y=0),
            students=students or [],
        ),
        documentation=DocumentationBlock(),
    )


def make_student(
    *,
    x: int = 1,
    y: int = 0,
    first_name: str = "Anna",
    last_name: str = "Müller",
    nickname: str = "",
    student_id: StudentId | None = None,
) -> Student:
    return Student(
        student_id=student_id or StudentId.new(),
        first_name_official=first_name,
        last_name=last_name,
        seat=Seat(x=x, y=y),
        nickname=nickname,
        diagnostic=DiagnosticProfile(),
    )


def make_snapshot(
    *,
    snapshot_id: str = "snap0000000000000000000000000001",
    name: str = "Testsnapshot",
    created_at: str = "2026-01-01T09:00:00",
    last_used_at: str | None = None,
    teacher_seat: Seat | None = None,
    seats: dict[StudentId, Seat] | None = None,
) -> SeatingSnapshot:
    """Erzeugt einen minimalen ``SeatingSnapshot`` für Tests."""
    return SeatingSnapshot(
        snapshot_id=snapshot_id,
        name=name,
        created_at=created_at,
        last_used_at=last_used_at if last_used_at is not None else created_at,
        teacher_seat=teacher_seat or Seat(x=0, y=0),
        seats=seats or {},
    )


@pytest.fixture
def plan() -> SeatingPlan:
    return make_plan()


@pytest.fixture
def anna_id() -> StudentId:
    return StudentId.new()


@pytest.fixture
def plan_with_anna(anna_id: StudentId) -> SeatingPlan:
    return make_plan(students=[make_student(student_id=anna_id)])
