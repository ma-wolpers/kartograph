"""Tests für v4 session_usecases."""

from app.core.domain.models_v4 import Session, SessionEntry
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.session_usecases import ensure_session, rename_session_date
from tests.conftest import make_plan, make_student


DATE = "2025-09-01"
DATE2 = "2025-09-02"


class TestEnsureSession:
    def test_creates_session_when_missing(self, plan):
        result = ensure_session(plan, DATE)
        assert result.documentation.session_for_date(DATE) is not None

    def test_no_duplicate_when_already_exists(self, plan):
        r1 = ensure_session(plan, DATE)
        r2 = ensure_session(r1, DATE)
        assert len(r2.documentation.sessions) == 1

    def test_sessions_sorted_by_date(self, plan):
        r1 = ensure_session(plan, DATE2)
        r2 = ensure_session(r1, DATE)
        dates = [s.date for s in r2.documentation.sessions]
        assert dates == [DATE, DATE2]

    def test_does_not_mutate_original(self, plan):
        ensure_session(plan, DATE)
        assert len(plan.documentation.sessions) == 0


class TestRenameSessionDate:
    def _plan_with_session(self, sid, date=DATE):
        plan = make_plan(students=[make_student(student_id=sid)])
        plan.documentation.sessions.append(
            Session(date=date, entries={sid: SessionEntry(note="Notiz")})
        )
        return plan

    def test_simple_rename(self):
        sid = StudentId.new()
        plan = self._plan_with_session(sid)
        result = rename_session_date(plan, DATE, DATE2)
        assert result.documentation.session_for_date(DATE) is None
        assert result.documentation.session_for_date(DATE2) is not None

    def test_entries_preserved_on_rename(self):
        sid = StudentId.new()
        plan = self._plan_with_session(sid)
        result = rename_session_date(plan, DATE, DATE2)
        entry = result.documentation.session_for_date(DATE2).entries.get(sid)
        assert entry is not None
        assert entry.note == "Notiz"

    def test_no_effect_when_old_not_found(self):
        plan = make_plan()
        result = rename_session_date(plan, DATE, DATE2)
        assert result.documentation.sessions == []

    def test_no_effect_when_dates_identical(self):
        sid = StudentId.new()
        plan = self._plan_with_session(sid)
        result = rename_session_date(plan, DATE, DATE)
        assert len(result.documentation.sessions) == 1

    def test_merge_into_existing_target(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(student_id=sid)])
        plan.documentation.sessions.extend([
            Session(date=DATE,  entries={sid: SessionEntry(note="Alt")}),
            Session(date=DATE2, entries={sid: SessionEntry(note="Neu")}),
        ])
        result = rename_session_date(plan, DATE, DATE2)
        assert len(result.documentation.sessions) == 1
        entry = result.documentation.session_for_date(DATE2).entries[sid]
        assert entry.note == "Neu"  # bestehender Wert bleibt erhalten
