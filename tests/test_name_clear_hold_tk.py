"""Tk-Test: Geleerter Name einer Person mit Daten wird gehalten und angekündigt.

Personendaten gehören nur zu benannten Tischen; ohne Namen löscht die Invariante
sie. Deshalb hält Kartograph einen geleerten Namen in ``_name_clear_hold`` (eigene
Frist ``settings.name_clear_delay``), zeigt eine Warnung und führt ihn erst nach
der Frist bzw. beim Plan-/Programmschluss aus. Ein neuer Name hebt das auf.
Echtes Hauptfenster (``open_isolated_window``), synthetischer Plan.
"""

from __future__ import annotations

import pytest

from app.core.intents.edit_intents import UndoIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from tests.conftest import make_plan, make_student


@pytest.fixture
def window(tmp_path):
    """Anna (mit Notiz) auf (1,0), Ben (ohne Daten) auf (3,0); Details von Anna offen."""
    anna = make_student(x=1, y=0, first_name="Anna", last_name="Alt")
    anna.diagnostic.notes = ["Absprache"]
    ben = make_student(x=3, y=0, first_name="Ben", last_name="Berg")
    app, close = open_isolated_window(tmp_path, make_plan(students=[anna, ben]))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
    _select(app, anna)
    yield app, anna.student_id, ben
    close()


def _select(app, student) -> None:
    app._set_selection_single(student.seat.x, student.seat.y)
    app._reveal_details(student.seat.x, student.seat.y)
    app.tk_root.update()


def _type_names(app, first: str, last: str = "", nickname: str = "") -> None:
    app._name_var.set(first)
    app._last_name_var.set(last)
    app._nickname_var.set(nickname)
    app._name_pending_save.flush()  # wie die abgelaufene normale Speicherfrist
    app.tk_root.update()


def test_clearing_the_name_holds_and_warns(window):
    app, anna_id, _ben = window
    _type_names(app, "")
    student = app.current_plan.student_by_id(anna_id)
    assert student.first_name_official == "Anna" and student.diagnostic.notes == ["Absprache"]
    assert app._name_clear_hold.has_pending_for(anna_id)
    assert app._name_clear_warning.winfo_ismapped()


def test_new_name_cancels_the_hold(window):
    app, anna_id, _ben = window
    _type_names(app, "")
    _type_names(app, "Anni", "Alt")
    student = app.current_plan.student_by_id(anna_id)
    assert student.first_name_official == "Anni" and student.diagnostic.notes == ["Absprache"]
    assert not app._name_clear_hold.has_pending_for(anna_id)
    assert not app._name_clear_warning.winfo_ismapped()


def test_expired_hold_clears_and_undo_restores(window):
    app, anna_id, _ben = window
    _type_names(app, "")
    app._name_clear_hold.flush()  # wie die abgelaufene Löschfrist
    app.tk_root.update()
    assert app.current_plan.student_by_id(anna_id).diagnostic.notes == []
    assert not app._name_clear_warning.winfo_ismapped()

    app._controller.dispatch(UndoIntent())
    app.tk_root.update()
    restored = app.current_plan.student_by_id(anna_id)
    assert restored.first_name_official == "Anna" and restored.diagnostic.notes == ["Absprache"]


def test_desk_change_keeps_the_hold_leaving_the_plan_executes_it(window):
    app, anna_id, ben = window
    _type_names(app, "")
    _select(app, ben)
    app._commit_pending_edits()
    assert app._name_clear_hold.has_pending_for(anna_id)
    assert app.current_plan.student_by_id(anna_id).diagnostic.notes == ["Absprache"]

    app._commit_pending_edits(final=True)
    assert app.current_plan.student_by_id(anna_id).diagnostic.notes == []


def test_returning_to_the_desk_shows_the_cleared_fields_and_warning(window):
    app, anna_id, ben = window
    anna = app.current_plan.student_by_id(anna_id)
    _type_names(app, "")
    _select(app, ben)
    _select(app, anna)
    assert app._name_var.get() == "" and app._last_name_var.get() == ""
    assert app._name_clear_warning.winfo_ismapped()


def test_person_without_data_is_renamed_at_once(window):
    app, _anna_id, ben = window
    _select(app, ben)
    _type_names(app, "")
    assert not app.current_plan.student_by_id(ben.student_id).is_named()
    assert not app._name_clear_hold.has_pending_for(ben.student_id)
