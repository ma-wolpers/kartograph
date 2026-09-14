"""Tests für v4 snapshot_usecases."""

from copy import deepcopy

from app.core.domain.models_v4 import Seat
from app.core.domain.plan_history import PlanHistory
from app.core.usecases.v4.snapshot_usecases import (
    SNAPSHOT_RESTORE_ROW_GAP,
    create_snapshot,
    delete_snapshot,
    rename_snapshot,
    restore_snapshot,
)
from tests.conftest import make_plan, make_snapshot, make_student


class TestCreateSnapshot:
    def test_creates_snapshot_from_current_positions(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        result = create_snapshot(plan, "Montag")
        assert result.created is True
        assert result.snapshot_id is not None
        snap = result.plan.snapshot_by_id(result.snapshot_id)
        assert snap.name == "Montag"
        assert snap.created_at == snap.last_used_at
        assert snap.seats[anna_id] == Seat(x=1, y=0)
        assert snap.teacher_seat == Seat(x=0, y=0)

    def test_blocked_on_full_match(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        existing = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        plan.snapshots = [existing]
        result = create_snapshot(plan, "Duplikat")
        assert result.created is False
        assert result.snapshot_id is None
        assert result.plan is plan
        assert len(result.plan.snapshots) == 1

    def test_not_blocked_when_only_roster_differs(self, anna_id):
        extra = make_student(x=8, y=4)
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0), extra])
        existing = make_snapshot(seats={anna_id: Seat(x=1, y=0)})
        plan.snapshots = [existing]
        result = create_snapshot(plan, "Neu")
        assert result.created is True
        assert len(result.plan.snapshots) == 2

    def test_falls_back_to_default_name(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        result = create_snapshot(plan, "   ")
        snap = result.plan.snapshot_by_id(result.snapshot_id)
        assert snap.name == "Unbenannter Snapshot"

    def test_does_not_mutate_original_plan(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        before = deepcopy(plan)
        create_snapshot(plan, "Montag")
        assert plan == before
        assert plan.snapshots == []


class TestDeleteSnapshot:
    def test_removes_matching_snapshot(self, anna_id):
        snap = make_snapshot(snapshot_id="a")
        plan = make_plan(students=[make_student(student_id=anna_id)])
        plan.snapshots = [snap]
        result = delete_snapshot(plan, "a")
        assert result.changed is True
        assert result.plan.snapshots == []

    def test_unknown_id_no_op(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        result = delete_snapshot(plan, "does-not-exist")
        assert result.changed is False
        assert result.plan is plan

    def test_does_not_affect_current_seating(self, anna_id):
        snap = make_snapshot(snapshot_id="a", seats={anna_id: Seat(x=9, y=9)})
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        plan.snapshots = [snap]
        result = delete_snapshot(plan, "a")
        assert result.plan.classroom.students[0].seat == Seat(x=1, y=0)

    def test_does_not_mutate_original_plan(self, anna_id):
        snap = make_snapshot(snapshot_id="a")
        plan = make_plan(students=[make_student(student_id=anna_id)])
        plan.snapshots = [snap]
        before = deepcopy(plan)
        delete_snapshot(plan, "a")
        assert plan == before


class TestRenameSnapshot:
    def test_renames(self, anna_id):
        snap = make_snapshot(snapshot_id="a", name="Alt")
        plan = make_plan(students=[make_student(student_id=anna_id)])
        plan.snapshots = [snap]
        result = rename_snapshot(plan, "a", "Neu")
        assert result.changed is True
        assert result.plan.snapshot_by_id("a").name == "Neu"

    def test_does_not_touch_last_used_at(self, anna_id):
        snap = make_snapshot(snapshot_id="a", created_at="2026-01-01T09:00:00", last_used_at="2026-01-02T09:00:00")
        plan = make_plan(students=[make_student(student_id=anna_id)])
        plan.snapshots = [snap]
        result = rename_snapshot(plan, "a", "Neu")
        assert result.plan.snapshot_by_id("a").last_used_at == "2026-01-02T09:00:00"

    def test_unknown_id_no_op(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        result = rename_snapshot(plan, "does-not-exist", "Neu")
        assert result.changed is False
        assert result.plan is plan

    def test_falls_back_to_default_name(self, anna_id):
        snap = make_snapshot(snapshot_id="a")
        plan = make_plan(students=[make_student(student_id=anna_id)])
        plan.snapshots = [snap]
        result = rename_snapshot(plan, "a", "   ")
        assert result.plan.snapshot_by_id("a").name == "Unbenannter Snapshot"


class TestRestoreSnapshot:
    def test_restores_matched_seat_and_teacher(self, anna_id):
        snap = make_snapshot(snapshot_id="a", seats={anna_id: Seat(x=3, y=3)}, teacher_seat=Seat(x=-1, y=-1))
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        plan.snapshots = [snap]
        result = restore_snapshot(plan, "a")
        assert result.changed is True
        student = result.plan.student_by_id(anna_id)
        assert student.seat == Seat(x=3, y=3)
        assert result.plan.classroom.teacher_seat.x == -1
        assert result.plan.classroom.teacher_seat.y == -1

    def test_unmatched_student_placed_in_spare_row_below(self, anna_id):
        bob = make_student(x=8, y=8)
        snap = make_snapshot(snapshot_id="a", seats={anna_id: Seat(x=1, y=2)}, teacher_seat=Seat(x=0, y=0))
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0), bob])
        plan.snapshots = [snap]
        result = restore_snapshot(plan, "a")
        bob_after = result.plan.student_by_id(bob.student_id)
        expected_row_y = max(2, 0) + SNAPSHOT_RESTORE_ROW_GAP + 1
        assert bob_after.seat.y == expected_row_y

    def test_unmatched_students_centered_around_zero(self):
        s1, s2, s3 = make_student(x=0, y=0), make_student(x=1, y=0), make_student(x=2, y=0)
        snap = make_snapshot(snapshot_id="a", seats={}, teacher_seat=Seat(x=0, y=0))
        plan = make_plan(students=[s1, s2, s3])
        plan.snapshots = [snap]
        result = restore_snapshot(plan, "a")
        xs = sorted(result.plan.student_by_id(s.student_id).seat.x for s in (s1, s2, s3))
        assert xs == [-1, 0, 1]

    def test_no_unmatched_students_no_spare_row_needed(self, anna_id):
        snap = make_snapshot(snapshot_id="a", seats={anna_id: Seat(x=1, y=1)}, teacher_seat=Seat(x=0, y=0))
        plan = make_plan(students=[make_student(student_id=anna_id, x=5, y=5)])
        plan.snapshots = [snap]
        result = restore_snapshot(plan, "a")
        assert result.plan.student_by_id(anna_id).seat == Seat(x=1, y=1)

    def test_updates_last_used_at(self, anna_id):
        snap = make_snapshot(snapshot_id="a", created_at="2026-01-01T09:00:00", last_used_at="2026-01-01T09:00:00")
        plan = make_plan(students=[make_student(student_id=anna_id)])
        plan.snapshots = [snap]
        result = restore_snapshot(plan, "a")
        assert result.plan.snapshot_by_id("a").last_used_at != "2026-01-01T09:00:00"
        assert result.plan.snapshot_by_id("a").created_at == "2026-01-01T09:00:00"

    def test_unknown_id_no_op(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id)])
        result = restore_snapshot(plan, "does-not-exist")
        assert result.changed is False
        assert result.plan is plan

    def test_does_not_mutate_original_plan(self, anna_id):
        snap = make_snapshot(snapshot_id="a", seats={anna_id: Seat(x=3, y=3)})
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        plan.snapshots = [snap]
        before = deepcopy(plan)
        restore_snapshot(plan, "a")
        assert plan == before
        assert plan.classroom.students[0].seat == Seat(x=1, y=0)


class TestSnapshotHistoryUndoRedo:
    def test_create_delete_rename_restore_are_undoable(self, anna_id):
        plan = make_plan(students=[make_student(student_id=anna_id, x=1, y=0)])
        history = PlanHistory()
        history.reset(plan, plan_path=None)

        created = create_snapshot(plan, "Montag")
        history.record(created.plan, "snapshot.create")
        assert len(created.plan.snapshots) == 1

        restored = restore_snapshot(created.plan, created.snapshot_id)
        # Move the student away, then restore -- ensures restore is a real change.
        restored.plan.student_by_id(anna_id).seat = Seat(x=9, y=9)
        history.record(restored.plan, "student.move")

        undone = history.undo()
        assert undone is not None
        assert undone.student_by_id(anna_id).seat == Seat(x=1, y=0)

        redone = history.redo()
        assert redone is not None
        assert redone.student_by_id(anna_id).seat == Seat(x=9, y=9)
