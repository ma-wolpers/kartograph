"""Tests für v4 student_usecases."""

import pytest

from app.core.domain.models_v4 import GroupSeat, Session, SessionEntry, TableGroup
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.student_usecases import (
    create_student,
    delete_student,
    move_student,
    move_teacher_seat,
    rename_student,
)
from tests.conftest import make_plan, make_student


# ---------------------------------------------------------------------------
# create_student
# ---------------------------------------------------------------------------

class TestCreateStudent:
    def test_creates_student_at_empty_seat(self, plan):
        result = create_student(plan, x=1, y=0)
        assert result.student_at(1, 0) is not None

    def test_new_student_gets_unique_id(self, plan):
        r1 = create_student(plan, x=1, y=0)
        r2 = create_student(plan, x=2, y=0)
        ids = {s.student_id for s in r1.classroom.students + r2.classroom.students}
        assert len(ids) == 2

    def test_no_effect_when_seat_occupied(self):
        s = make_student(x=1, y=0)
        plan = make_plan(students=[s])
        result = create_student(plan, x=1, y=0)
        assert len(result.classroom.students) == 1

    def test_no_effect_at_teacher_seat(self, plan):
        result = create_student(plan, x=0, y=0)
        assert result.classroom.student_at(0, 0) is None

    def test_does_not_mutate_original(self, plan):
        create_student(plan, x=1, y=0)
        assert len(plan.classroom.students) == 0


# ---------------------------------------------------------------------------
# delete_student
# ---------------------------------------------------------------------------

class TestDeleteStudent:
    def test_removes_student(self, plan_with_anna, anna_id):
        result = delete_student(plan_with_anna, anna_id)
        assert result.student_by_id(anna_id) is None

    def test_clears_session_entries(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        session = Session(date="2025-09-01", entries={anna_id: SessionEntry(note="X")})
        plan.documentation.sessions.append(session)

        result = delete_student(plan, anna_id)
        assert anna_id not in result.documentation.sessions[0].entries

    def test_removes_from_tablegroup(self, anna_id):
        plan = make_plan(students=[make_student(x=1, y=0, student_id=anna_id)])
        plan.tablegroups = [TableGroup(group_id=1, seats=[
            GroupSeat(x=1, y=0),
            GroupSeat(x=2, y=0),
        ])]
        result = delete_student(plan, anna_id)
        assert len(result.tablegroups[0].seats) == 1
        assert result.tablegroups[0].seats[0].x == 2

    def test_drops_empty_tablegroup(self, anna_id):
        plan = make_plan(students=[make_student(x=1, y=0, student_id=anna_id)])
        plan.tablegroups = [TableGroup(group_id=1, seats=[GroupSeat(x=1, y=0)])]
        result = delete_student(plan, anna_id)
        assert result.tablegroups == []

    def test_no_effect_for_unknown_id(self, plan_with_anna):
        result = delete_student(plan_with_anna, StudentId.new())
        assert len(result.classroom.students) == 1


# ---------------------------------------------------------------------------
# move_student
# ---------------------------------------------------------------------------

class TestMoveStudent:
    def test_moves_to_free_seat(self, anna_id):
        plan = make_plan(students=[make_student(x=1, y=0, student_id=anna_id)])
        result = move_student(plan, anna_id, new_x=3, new_y=0)
        assert result.student_at(3, 0) is not None
        assert result.student_at(1, 0) is None

    def test_student_id_preserved_after_move(self, anna_id):
        plan = make_plan(students=[make_student(x=1, y=0, student_id=anna_id)])
        result = move_student(plan, anna_id, new_x=3, new_y=0)
        assert result.student_by_id(anna_id) is not None

    def test_no_effect_when_target_occupied(self, anna_id):
        ben_id = StudentId.new()
        plan = make_plan(students=[
            make_student(x=1, y=0, student_id=anna_id),
            make_student(x=2, y=0, student_id=ben_id),
        ])
        result = move_student(plan, anna_id, new_x=2, new_y=0)
        assert result.student_at(1, 0) is not None  # Anna blieb

    def test_no_effect_when_target_is_teacher_seat(self, anna_id):
        plan = make_plan(students=[make_student(x=1, y=0, student_id=anna_id)])
        result = move_student(plan, anna_id, new_x=0, new_y=0)
        assert result.student_at(1, 0) is not None

    def test_tablegroup_coordinates_follow_student(self, anna_id):
        plan = make_plan(students=[make_student(x=1, y=0, student_id=anna_id)])
        plan.tablegroups = [TableGroup(group_id=1, seats=[GroupSeat(x=1, y=0)])]
        result = move_student(plan, anna_id, new_x=3, new_y=0)
        assert result.tablegroups[0].seats[0].x == 3


# ---------------------------------------------------------------------------
# rename_student
# ---------------------------------------------------------------------------

class TestRenameStudent:
    def test_sets_names(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, first_name="", last_name="")])
        result = rename_student(plan, anna_id, "Clara", "Schmidt")
        s = result.student_by_id(anna_id)
        assert s.first_name == "Clara"
        assert s.last_name == "Schmidt"

    def test_trims_whitespace(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        result = rename_student(plan, anna_id, "  Ben  ", "  Koch  ")
        s = result.student_by_id(anna_id)
        assert s.first_name == "Ben"
        assert s.last_name == "Koch"

    def test_no_effect_for_unknown_id(self, plan_with_anna):
        result = rename_student(plan_with_anna, StudentId.new(), "X", "Y")
        assert len(result.classroom.students) == 1


# ---------------------------------------------------------------------------
# move_teacher_seat
# ---------------------------------------------------------------------------

class TestMoveTeacherSeat:
    def test_teacher_seat_stays_at_origin(self):
        plan = make_plan(students=[make_student(x=2, y=1)])
        result = move_teacher_seat(plan, new_x=1, new_y=0)
        assert result.classroom.teacher_seat.x == 0
        assert result.classroom.teacher_seat.y == 0

    def test_students_shifted_accordingly(self):
        plan = make_plan(students=[make_student(x=2, y=1)])
        result = move_teacher_seat(plan, new_x=1, new_y=0)
        assert result.student_at(1, 1) is not None  # (2-1, 1-0)

    def test_student_at_new_teacher_position_removed(self):
        block_id = StudentId.new()
        plan = make_plan(students=[
            make_student(x=1, y=0, student_id=block_id),
            make_student(x=2, y=0),
        ])
        result = move_teacher_seat(plan, new_x=1, new_y=0)
        assert result.student_by_id(block_id) is None
