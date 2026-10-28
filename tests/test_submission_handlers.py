"""Handler-Tests für "Abgaben zählen": Katalog-Auflösung, Speichern, Undo pro Schritt."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from app.application.app_state import AppState
from app.application.handlers.edit_handlers import handle_undo
from app.application.handlers.plan_handlers import handle_open_plan
from app.application.handlers.submission_handlers import (
    handle_apply_missing_submissions,
    handle_set_submission_status,
)
from app.core.domain.submission_status import SubmissionStatus
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.plan_intents import OpenPlanIntent
from app.core.intents.submission_intents import ApplyMissingSubmissionsIntent, SetSubmissionStatusIntent
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR, make_ctx

DATE = "2026-10-28"
CATALOG = (
    SimpleNamespace(glyph="✓", meaning="Abgabe vollständig"),
    SimpleNamespace(glyph="◐", meaning="Abgabe lückenhaft"),
    SimpleNamespace(glyph="X", meaning="Nicht abgegeben / verweigert"),
    SimpleNamespace(glyph="∅", meaning="Abwesend"),
)


def _opened(catalog=CATALOG):
    anna, ben = make_student(first_name="Anna"), make_student(first_name="Ben", x=2)
    path = PLANS_DIR / "test.json"
    ctx = make_ctx({path: make_plan(students=[anna, ben])})
    state = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)
    return dataclasses.replace(state, symbol_catalog=catalog), ctx, anna, ben


def _symbols(state, sid):
    session = state.current_plan.documentation.session_for_date(DATE)
    entry = session.entry_for(sid) if session else None
    return dict(entry.symbols) if entry else {}


def test_each_rating_is_its_own_undo_step():
    state, ctx, anna, ben = _opened()
    state = handle_apply_missing_submissions(
        ApplyMissingSubmissionsIntent(date=DATE, submitted=(anna.student_id,), mark_absent=True, mode="replace"), state, ctx
    )
    state = handle_set_submission_status(SetSubmissionStatusIntent(anna.student_id, DATE, SubmissionStatus.PARTIAL), state, ctx)
    state = handle_set_submission_status(SetSubmissionStatusIntent(anna.student_id, DATE, SubmissionStatus.COMPLETE), state, ctx)
    assert _symbols(state, anna.student_id) == {"Abgabe vollständig": 1}
    assert _symbols(state, ben.student_id) == {"Nicht abgegeben / verweigert": 1}

    state = handle_undo(UndoIntent(), state, ctx)
    assert _symbols(state, anna.student_id) == {"Abgabe lückenhaft": 1}
    state = handle_undo(UndoIntent(), state, ctx)
    assert _symbols(state, anna.student_id) == {}
    assert _symbols(state, ben.student_id) == {"Nicht abgegeben / verweigert": 1}
    state = handle_undo(UndoIntent(), state, ctx)
    assert _symbols(state, ben.student_id) == {}


def test_missing_catalog_symbol_leaves_plan_and_reports():
    state, ctx, anna, _ben = _opened(catalog=CATALOG[1:])
    result = handle_set_submission_status(SetSubmissionStatusIntent(anna.student_id, DATE, SubmissionStatus.COMPLETE), state, ctx)
    assert result.current_plan is state.current_plan
    assert "U+2713" in result.status_message
