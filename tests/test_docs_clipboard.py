"""Tests für Doku-Eintrag setzen (``set_entry``) und die Einfüge-Regel der Doku-Zellen (nur synthetische Daten)."""

from __future__ import annotations

from app.adapters.gui.docs_clipboard import CopiedDocEntry, entry_to_paste
from app.core.domain.models_v4 import SessionEntry
from app.core.usecases.v4.session_usecases import set_entry
from tests.conftest import make_plan, make_student

DATE = "2026-03-02"


def test_paste_only_while_the_clipboard_still_holds_the_copied_text_of_this_plan():
    entry = SessionEntry(symbols={"Beteiligung": 1})
    copied = CopiedDocEntry("plan-a", "B", entry)
    assert entry_to_paste(copied, "plan-a", "B") is entry
    assert entry_to_paste(copied, "plan-a", "anderer Text") is None
    assert entry_to_paste(copied, "plan-b", "B") is None
    assert entry_to_paste(None, "plan-a", "B") is None


def test_empty_cell_matches_an_empty_or_missing_clipboard_text():
    copied = CopiedDocEntry("plan-a", "", SessionEntry())
    assert entry_to_paste(copied, "plan-a", None) == SessionEntry()


def test_set_entry_creates_the_session_and_stores_a_copy():
    student = make_student(first_name="Anna", last_name="A")
    entry = SessionEntry(symbols={"Beteiligung": 2}, note="kam spät")
    plan = set_entry(make_plan(students=[student]), student.student_id, DATE, entry)
    stored = plan.documentation.session_for_date(DATE).entry_for(student.student_id)
    assert stored == entry and stored is not entry


def test_set_entry_with_empty_entry_removes_without_creating_a_session():
    student = make_student(first_name="Anna", last_name="A")
    plan = make_plan(students=[student])
    assert set_entry(plan, student.student_id, DATE, SessionEntry()).documentation.session_for_date(DATE) is None
    filled = set_entry(plan, student.student_id, DATE, SessionEntry(symbols={"Beteiligung": 1}))
    cleared = set_entry(filled, student.student_id, DATE, SessionEntry())
    assert cleared.documentation.session_for_date(DATE).entry_for(student.student_id) is None
