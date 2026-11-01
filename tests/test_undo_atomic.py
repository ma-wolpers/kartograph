"""Undo in Einzelschritten: jedes Symbol und jede Note ist genau eine Änderung.

Früher fasste die History gleichartige Schritte zusammen, egal für wen: Zehn Symbole
waren ein Schritt. Ein Raster-Symbol waren dagegen zwei Schritte (Profil, Doku-Eintrag).
"""

from __future__ import annotations

import pytest

from app.application.app_state import AppState
from app.application.handlers.accommodation_handlers import handle_set_accommodations
from app.application.handlers.edit_handlers import handle_redo, handle_undo
from app.application.handlers.grade_handlers import handle_record_grade
from app.application.handlers.student_handlers import (
    handle_delete_students,
    handle_rename_student,
    handle_set_nickname,
)
from app.application.handlers.symbol_handlers import (
    handle_record_documentation_symbol,
    handle_toggle_diagnostic_symbol,
)
from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.intents.edit_intents import RedoIntent, UndoIntent
from app.core.intents.grade_intents import RecordGradeIntent
from app.core.intents.student_intents import DeleteStudentsIntent, RenameStudentIntent, SetNicknameIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent, ToggleDiagnosticSymbolIntent
from app.core.usecases.v4.grade_usecases import add_grade_column
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR, make_ctx, make_state_with_plan

DATE = "2025-09-01"
SYMBOL = "Beteiligung"
PATH = PLANS_DIR / "test.json"


@pytest.fixture
def setup():
    """Plan mit zwei benannten Personen, einer Notenspalte und frischem Verlauf."""
    first, second = make_student(first_name="Anna", last_name="A"), make_student(first_name="Ben", last_name="B")
    plan, column_id = add_grade_column(make_plan(students=[first, second]), "schriftlich", "Arbeit")
    ctx = make_ctx({PATH: plan})
    ctx.history.reset(plan, PATH)
    return ctx, make_state_with_plan(plan, PATH), first.student_id, second.student_id, column_id


def _symbol(state, ctx, student_id, strength=1):
    return handle_record_documentation_symbol(
        RecordDocumentationSymbolIntent(student_id=student_id, date=DATE, symbol=SYMBOL, strength=strength), state, ctx
    )


def _doc_strength(state, student_id):
    session = state.current_plan.documentation.session_for_date(DATE)
    entry = session.entry_for(student_id) if session else None
    return entry.symbols.get(SYMBOL, 0) if entry else 0


def _undo(state, ctx, steps=1):
    return handle_undo(UndoIntent(steps=steps), state, ctx)


def test_every_symbol_is_its_own_step_also_for_the_same_person(setup):
    ctx, state, first, second, _ = setup
    for student_id, strength in ((first, 1), (second, 1), (first, 2)):
        state = _symbol(state, ctx, student_id, strength)

    state = _undo(state, ctx)
    assert (_doc_strength(state, first), _doc_strength(state, second)) == (1, 1)
    state = _undo(state, ctx)
    assert (_doc_strength(state, first), _doc_strength(state, second)) == (1, 0)
    state = _undo(state, ctx)
    assert (_doc_strength(state, first), _doc_strength(state, second)) == (0, 0)
    assert not state.can_undo

    state = handle_redo(RedoIntent(), state, ctx)
    assert (_doc_strength(state, first), _doc_strength(state, second)) == (1, 0)


def test_every_grade_is_its_own_step_also_for_the_same_person(setup):
    ctx, state, first, second, column_id = setup
    for student_id, grade in ((first, 1.0), (second, 2.0), (first, 3.0)):
        state = handle_record_grade(RecordGradeIntent(student_id=student_id, column_id=column_id, grade=grade), state, ctx)

    def grades(current):
        documentation = current.current_plan.documentation
        return documentation.grade_of(first, column_id), documentation.grade_of(second, column_id)

    state = _undo(state, ctx)
    assert grades(state) == (1.0, 2.0)
    state = _undo(state, ctx)
    assert grades(state) == (1.0, None)
    state = _undo(state, ctx)
    assert grades(state) == (None, None)


def test_grid_symbol_is_one_step_covering_profile_and_doc_entry(setup):
    ctx, state, first, _, _ = setup
    state = handle_toggle_diagnostic_symbol(
        ToggleDiagnosticSymbolIntent(student_id=first, date=DATE, symbol=SYMBOL), state, ctx
    )
    assert state.current_plan.student_by_id(first).diagnostic.symbols[SYMBOL] == 1
    assert _doc_strength(state, first) == 1

    state = _undo(state, ctx)

    assert SYMBOL not in state.current_plan.student_by_id(first).diagnostic.symbols
    assert _doc_strength(state, first) == 0
    assert not state.can_undo


def test_grid_symbol_back_to_zero_clears_profile_and_doc_entry(setup):
    ctx, state, first, _, _ = setup
    for _ in range(4):
        state = handle_toggle_diagnostic_symbol(
            ToggleDiagnosticSymbolIntent(student_id=first, date=DATE, symbol=SYMBOL), state, ctx
        )
    assert SYMBOL not in state.current_plan.student_by_id(first).diagnostic.symbols
    assert _doc_strength(state, first) == 0


def test_deleting_a_selection_is_one_step(setup):
    ctx, state, first, second, _ = setup
    state = handle_delete_students(DeleteStudentsIntent(student_ids=(first, second)), state, ctx)
    assert state.current_plan.classroom.students == []

    state = _undo(state, ctx)

    assert {s.student_id for s in state.current_plan.classroom.students} == {first, second}
    assert not state.can_undo


def _rename(state, ctx, student_id, first_name):
    return handle_rename_student(
        RenameStudentIntent(student_id=student_id, first_name=first_name, last_name="X"), state, ctx
    )


def test_typing_a_name_is_one_step_per_person(setup):
    ctx, state, first, second, _ = setup
    state = _rename(state, ctx, first, "Ann")
    state = _rename(state, ctx, first, "Annika")
    state = _rename(state, ctx, second, "Benno")

    state = _undo(state, ctx)
    assert state.current_plan.student_by_id(first).first_name_official == "Annika"
    assert state.current_plan.student_by_id(second).first_name_official == "Ben"
    state = _undo(state, ctx)
    assert state.current_plan.student_by_id(first).first_name_official == "Anna"
    assert not state.can_undo


def test_different_text_fields_of_one_person_are_separate_steps(setup):
    ctx, state, first, _, _ = setup
    state = handle_set_nickname(SetNicknameIntent(student_id=first, nickname="Anni"), state, ctx)
    state = handle_set_accommodations(SetAccommodationsIntent(student_id=first, accommodations=["Zeit"]), state, ctx)

    state = _undo(state, ctx)

    assert state.current_plan.student_by_id(first).nickname == "Anni"
    assert state.current_plan.student_by_id(first).diagnostic.accommodations == []


def test_undo_and_redo_replace_a_pending_delayed_save(setup):
    """Früher schrieb Undo direkt und ließ das verzögerte Speichern stehen, das danach den alten Stand zurückschrieb."""
    ctx, state, first, _, _ = setup
    scheduled = []
    ctx.plan_save_scheduler = lambda plan, _path: scheduled.append(plan)
    state = _symbol(state, ctx, first)

    state = _undo(state, ctx)
    assert scheduled[-1] == state.current_plan

    state = handle_redo(RedoIntent(), state, ctx)
    assert scheduled[-1] == state.current_plan


def test_handlers_leave_the_state_alone_without_an_open_plan(setup):
    ctx, _, first, _, column_id = setup
    state = AppState()
    intent = RecordGradeIntent(student_id=first, column_id=column_id, grade=1.0)
    assert handle_record_grade(intent, state, ctx) is state
    assert handle_record_grade.__name__ == "handle_record_grade"  # der Dekorator verdeckt die Funktion nicht
    assert not ctx.history.can_undo


def test_undo_with_steps_goes_back_that_far_at_once(setup):
    ctx, state, first, _, _ = setup
    for strength in (1, 2, 3):
        state = _symbol(state, ctx, first, strength)
    assert _doc_strength(_undo(state, ctx, steps=2), first) == 1
