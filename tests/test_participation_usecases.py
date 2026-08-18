"""Tests für v4 participation_usecases."""

from app.core.domain.student_id import StudentId
from app.core.usecases.v4.participation_usecases import set_participation_rating
from tests.conftest import make_plan, make_student


DATE = "2025-09-01"
DATE2 = "2025-09-05"


class TestSetParticipationRating:
    def test_sets_rating_from_none(self, anna_id, plan_with_anna):
        result = set_participation_rating(plan_with_anna, anna_id, DATE, "+")
        entry = result.documentation.session_for_date(DATE).entries[anna_id]
        assert entry.participation == "+"

    def test_setting_same_rating_again_clears_it(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "+")
        r2 = set_participation_rating(r1, anna_id, DATE, "+")
        session = r2.documentation.session_for_date(DATE)
        assert anna_id not in session.entries

    def test_setting_o_again_clears_it(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "o")
        r2 = set_participation_rating(r1, anna_id, DATE, "o")
        session = r2.documentation.session_for_date(DATE)
        assert anna_id not in session.entries

    def test_setting_minus_again_clears_it(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "-")
        r2 = set_participation_rating(r1, anna_id, DATE, "-")
        session = r2.documentation.session_for_date(DATE)
        assert anna_id not in session.entries

    def test_setting_star_again_clears_it(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "☆")
        r2 = set_participation_rating(r1, anna_id, DATE, "☆")
        session = r2.documentation.session_for_date(DATE)
        assert anna_id not in session.entries

    def test_cross_transitions_replace_previous_rating(self, anna_id, plan_with_anna):
        transitions = [
            ("+", "o"), ("+", "-"), ("o", "+"), ("o", "-"), ("-", "+"), ("-", "o"),
            ("☆", "+"), ("+", "☆"), ("☆", "o"), ("o", "☆"), ("☆", "-"), ("-", "☆"),
        ]
        for first, second in transitions:
            r1 = set_participation_rating(plan_with_anna, anna_id, DATE, first)
            r2 = set_participation_rating(r1, anna_id, DATE, second)
            entry = r2.documentation.session_for_date(DATE).entries[anna_id]
            assert entry.participation == second, f"{first} -> {second} failed"

    def test_date_isolation(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "+")
        r2 = set_participation_rating(r1, anna_id, DATE2, "-")
        entry_date1 = r2.documentation.session_for_date(DATE).entries[anna_id]
        entry_date2 = r2.documentation.session_for_date(DATE2).entries[anna_id]
        assert entry_date1.participation == "+"
        assert entry_date2.participation == "-"

    def test_student_isolation(self):
        sid_a = StudentId.new()
        sid_b = StudentId.new()
        plan = make_plan(students=[
            make_student(student_id=sid_a, first_name="Anna"),
            make_student(student_id=sid_b, first_name="Ben", x=2, y=0),
        ])
        r1 = set_participation_rating(plan, sid_a, DATE, "+")
        r2 = set_participation_rating(r1, sid_b, DATE, "-")
        session = r2.documentation.session_for_date(DATE)
        assert session.entries[sid_a].participation == "+"
        assert session.entries[sid_b].participation == "-"

    def test_no_effect_for_unnamed_student(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(first_name="", last_name="", student_id=sid)])
        result = set_participation_rating(plan, sid, DATE, "+")
        session = result.documentation.session_for_date(DATE)
        assert session is None

    def test_no_effect_for_unknown_student(self, plan):
        result = set_participation_rating(plan, StudentId.new(), DATE, "+")
        assert result.documentation.sessions == []

    def test_creates_session_if_missing(self, anna_id, plan_with_anna):
        result = set_participation_rating(plan_with_anna, anna_id, DATE, "+")
        assert result.documentation.session_for_date(DATE) is not None

    def test_entry_removed_when_only_participation_was_set(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "+")
        r2 = set_participation_rating(r1, anna_id, DATE, "+")  # toggle off
        session = r2.documentation.session_for_date(DATE)
        assert anna_id not in session.entries

    def test_entry_survives_when_symbols_remain(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "+")
        session = r1.documentation.session_for_date(DATE)
        session.entries[anna_id].symbols["Beteiligung"] = 2
        r2 = set_participation_rating(r1, anna_id, DATE, "+")  # toggle off participation
        entry = r2.documentation.session_for_date(DATE).entries.get(anna_id)
        assert entry is not None
        assert entry.participation is None
        assert entry.symbols == {"Beteiligung": 2}

    def test_entry_survives_when_note_remains(self, anna_id, plan_with_anna):
        r1 = set_participation_rating(plan_with_anna, anna_id, DATE, "-")
        session = r1.documentation.session_for_date(DATE)
        session.entries[anna_id].note = "Notiz"
        r2 = set_participation_rating(r1, anna_id, DATE, "-")  # toggle off participation
        entry = r2.documentation.session_for_date(DATE).entries.get(anna_id)
        assert entry is not None
        assert entry.participation is None
        assert entry.note == "Notiz"
