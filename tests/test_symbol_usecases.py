"""Tests für v4 symbol_usecases."""

from app.core.domain.student_id import StudentId
from app.core.usecases.v4.symbol_usecases import (
    record_symbol,
    summarize_latest_symbols,
    toggle_diagnostic_symbol,
)
from tests.conftest import make_plan, make_student


DATE = "2025-09-01"
DATE2 = "2025-09-05"
SYM = "Beteiligung"


class TestToggleDiagnosticSymbol:
    def test_first_toggle_sets_1(self, anna_id, plan_with_anna):
        result = toggle_diagnostic_symbol(plan_with_anna, anna_id, "Laptop")
        s = result.student_by_id(anna_id)
        assert s.diagnostic.symbols.get("Laptop") == 1

    def test_cycles_1_2_3_then_removes(self, anna_id, plan_with_anna):
        plan = plan_with_anna
        for expected in [1, 2, 3]:
            plan = toggle_diagnostic_symbol(plan, anna_id, "Laptop")
            assert plan.student_by_id(anna_id).diagnostic.symbols.get("Laptop") == expected
        plan = toggle_diagnostic_symbol(plan, anna_id, "Laptop")
        assert "Laptop" not in plan.student_by_id(anna_id).diagnostic.symbols

    def test_no_effect_for_unknown_student(self, plan):
        result = toggle_diagnostic_symbol(plan, StudentId.new(), "Laptop")
        assert result.classroom.students == []


class TestRecordSymbol:
    def test_sets_symbol_in_session(self, anna_id, plan_with_anna):
        result = record_symbol(plan_with_anna, anna_id, DATE, SYM, 2)
        session = result.documentation.session_for_date(DATE)
        assert session is not None
        assert session.entries[anna_id].symbols[SYM] == 2

    def test_creates_session_if_missing(self, anna_id, plan_with_anna):
        result = record_symbol(plan_with_anna, anna_id, DATE, SYM, 1)
        assert result.documentation.session_for_date(DATE) is not None

    def test_strength_0_removes_entry(self, anna_id, plan_with_anna):
        r1 = record_symbol(plan_with_anna, anna_id, DATE, SYM, 2)
        r2 = record_symbol(r1, anna_id, DATE, SYM, 0)
        session = r2.documentation.session_for_date(DATE)
        assert anna_id not in session.entries

    def test_clamps_strength_above_3(self, anna_id, plan_with_anna):
        result = record_symbol(plan_with_anna, anna_id, DATE, SYM, 99)
        assert result.documentation.sessions[0].entries[anna_id].symbols[SYM] == 3

    def test_no_effect_for_unnamed_student(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(first_name="", last_name="", student_id=sid)])
        result = record_symbol(plan, sid, DATE, SYM, 2)
        session = result.documentation.session_for_date(DATE)
        assert sid not in (session.entries if session else {})


class TestSummarizeLatestSymbols:
    def test_returns_latest_value_per_symbol(self, anna_id, plan_with_anna):
        r1 = record_symbol(plan_with_anna, anna_id, DATE, SYM, 1)
        r2 = record_symbol(r1, anna_id, DATE2, SYM, 3)
        summary = summarize_latest_symbols(r2, anna_id)
        assert summary[SYM] == 3

    def test_empty_for_unnamed_student(self):
        sid = StudentId.new()
        plan = make_plan(students=[make_student(first_name="", student_id=sid)])
        assert summarize_latest_symbols(plan, sid) == {}
