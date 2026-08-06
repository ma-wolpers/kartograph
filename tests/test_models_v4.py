"""Tests für v4-Domänenmodelle (Verhalten, keine Serialisierung)."""

from app.core.domain.models_v4 import (
    Classroom,
    DocumentationBlock,
    PaletteEntry,
    SeatingPlan,
    Session,
    SessionEntry,
    TeacherSeat,
)
from app.core.domain.student_id import StudentId
from tests.conftest import make_plan, make_student


# ---------------------------------------------------------------------------
# Classroom
# ---------------------------------------------------------------------------

class TestClassroom:
    def test_student_at_returns_student(self):
        s = make_student(x=2, y=3)
        room = Classroom(teacher_seat=TeacherSeat(0, 0), students=[s])
        assert room.student_at(2, 3) is s

    def test_student_at_returns_none_for_empty(self):
        room = Classroom(teacher_seat=TeacherSeat(0, 0), students=[])
        assert room.student_at(1, 1) is None

    def test_student_by_id_returns_student(self):
        s = make_student()
        room = Classroom(teacher_seat=TeacherSeat(0, 0), students=[s])
        assert room.student_by_id(s.student_id) is s

    def test_student_by_id_returns_none_for_unknown(self):
        room = Classroom(teacher_seat=TeacherSeat(0, 0), students=[])
        assert room.student_by_id(StudentId.new()) is None


# ---------------------------------------------------------------------------
# Student.display_name
# ---------------------------------------------------------------------------

class TestStudentDisplayName:
    def test_full_name(self):
        s = make_student(first_name="Anna", last_name="Müller")
        assert s.display_name() == "Müller, Anna"

    def test_only_first_name(self):
        s = make_student(first_name="Anna", last_name="")
        assert s.display_name() == "Anna"

    def test_no_name_falls_back_to_coordinates(self):
        s = make_student(first_name="", last_name="", x=3, y=5)
        assert s.display_name() == "(3,5)"

    def test_is_named_true_when_first_name_set(self):
        s = make_student(first_name="X")
        assert s.is_named()

    def test_is_named_false_when_no_first_name(self):
        s = make_student(first_name="", last_name="Müller")
        assert not s.is_named()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class TestSession:
    def test_entry_for_returns_none_when_missing(self):
        session = Session(date="2025-09-01")
        assert session.entry_for(StudentId.new()) is None

    def test_ensure_entry_creates_new(self):
        session = Session(date="2025-09-01")
        sid = StudentId.new()
        entry = session.ensure_entry(sid)
        assert entry is session.entries[sid]

    def test_ensure_entry_returns_existing(self):
        session = Session(date="2025-09-01")
        sid = StudentId.new()
        first = session.ensure_entry(sid)
        first.note = "Notiz"
        second = session.ensure_entry(sid)
        assert second.note == "Notiz"


# ---------------------------------------------------------------------------
# DocumentationBlock
# ---------------------------------------------------------------------------

class TestDocumentationBlock:
    def test_session_for_date_finds_session(self):
        doc = DocumentationBlock(sessions=[Session(date="2025-09-01")])
        assert doc.session_for_date("2025-09-01") is not None

    def test_session_for_date_returns_none_when_missing(self):
        doc = DocumentationBlock()
        assert doc.session_for_date("2025-09-01") is None

    def test_all_dates_sorted(self):
        doc = DocumentationBlock(sessions=[
            Session(date="2025-09-03"),
            Session(date="2025-09-01"),
        ])
        assert doc.all_dates() == ["2025-09-01", "2025-09-03"]

    def test_column_by_id_finds_column(self):
        from app.core.domain.models_v4 import GradeColumn
        col = GradeColumn(column_id="abc12345", category="schriftlich", title="Test")
        doc = DocumentationBlock(grade_columns=[col])
        assert doc.column_by_id("abc12345") is col

    def test_column_by_id_returns_none_for_unknown(self):
        doc = DocumentationBlock()
        assert doc.column_by_id("nope") is None


# ---------------------------------------------------------------------------
# SeatingPlan convenience helpers
# ---------------------------------------------------------------------------

class TestSeatingPlanHelpers:
    def test_student_at_delegates_to_classroom(self):
        s = make_student(x=1, y=2)
        plan = make_plan(students=[s])
        assert plan.student_at(1, 2) is s

    def test_tablegroup_for_seat_finds_group(self):
        from app.core.domain.models_v4 import GroupSeat, TableGroup
        plan = make_plan()
        plan.tablegroups = [
            TableGroup(group_id=1, seats=[GroupSeat(x=1, y=0), GroupSeat(x=2, y=0)])
        ]
        group = plan.tablegroup_for_seat(2, 0)
        assert group is not None
        assert group.group_id == 1

    def test_tablegroup_for_seat_returns_none_when_no_match(self):
        plan = make_plan()
        assert plan.tablegroup_for_seat(5, 5) is None
