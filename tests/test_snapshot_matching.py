"""Tests für app.core.domain.snapshot_matching."""

from app.core.domain.models_v4 import Seat, TeacherSeat
from app.core.domain.snapshot_matching import is_full_match, positions_match
from app.core.domain.student_id import StudentId
from tests.conftest import make_plan, make_snapshot, make_student


class TestPositionsMatch:
    def test_full_match_true(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        assert positions_match(snapshot, plan) is True

    def test_extra_student_in_plan_still_matches(self, anna_id):
        extra = make_student(x=8, y=4)
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0), extra])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        assert positions_match(snapshot, plan) is True

    def test_student_since_removed_from_plan_still_matches_via_other_common_student(self, anna_id):
        gone_id = StudentId.new()
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0), gone_id: Seat(x=9, y=9)})
        assert positions_match(snapshot, plan) is True

    def test_different_position_of_common_student_no_match(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=2, y=0)])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        assert positions_match(snapshot, plan) is False

    def test_different_teacher_seat_no_match(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        plan.classroom.teacher_seat = TeacherSeat(x=5, y=5)
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)}, teacher_seat=Seat(x=0, y=0))
        assert positions_match(snapshot, plan) is False

    def test_no_common_students_in_nonempty_states_no_match(self, anna_id):
        other_id = anna_id
        plan = make_plan(students=[make_student(x=1, y=0)])
        snapshot = make_snapshot(seats={other_id: Seat(x=9, y=9)})
        assert positions_match(snapshot, plan) is False

    def test_both_empty_seats_match_on_teacher_seat_alone(self):
        plan = make_plan(students=[])
        snapshot = make_snapshot(seats={})
        assert positions_match(snapshot, plan) is True


class TestIsFullMatch:
    def test_true_when_roster_identical(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        assert is_full_match(snapshot, plan) is True

    def test_false_when_extra_student_in_plan(self, anna_id):
        extra = make_student(x=8, y=4)
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0), extra])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        assert is_full_match(snapshot, plan) is False

    def test_false_when_student_missing_from_plan(self, anna_id):
        plan = make_plan(students=[])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        assert is_full_match(snapshot, plan) is False

    def test_false_when_position_differs(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=2, y=0)])
        snapshot = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        assert is_full_match(snapshot, plan) is False
