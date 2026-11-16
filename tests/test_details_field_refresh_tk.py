"""Tk-Test: Speichern während der Eingabe darf Detail-Felder nicht neu befüllen.

Hintergrund: Nach einer Tipp-Pause (``save_delay``) speichert ``PendingFieldSave``
den Feldwert; der Dispatch löst ``apply_state`` → ``_refresh_details_panel`` aus.
Früher schrieb dieser Refresh das gerade bearbeitete Feld mit dem *normalisierten*
gespeicherten Wert neu -- Leerzeichen am Ende und eine begonnene Leerzeile
verschwanden, der Cursor sprang ans Ende ("Braucht " + Pause + "mehr" →
"Brauchtmehr"). Geprüft am echten Hauptfenster (``open_isolated_window``,
temporärer Workspace, synthetischer Plan -- keine echten Daten).
"""

from __future__ import annotations

import pytest

from app.core.intents.edit_intents import UndoIntent
from app.core.intents.note_intents import SetNotesIntent
from app.core.intents.student_intents import RenameStudentIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


@pytest.fixture
def window(tmp_path):
    """Echtes Hauptfenster, Rasteransicht, Details des ersten Schülers aufgedeckt."""
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(3, 1, 0))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
    student = app.current_plan.classroom.students[0]
    app._set_selection_single(student.seat.x, student.seat.y)
    app._reveal_details(student.seat.x, student.seat.y)
    app.tk_root.update()
    yield app
    close()


def _type_notes(app, text: str) -> None:
    """Ersetzt den Inhalt des Notizfelds wie eine Tastatureingabe und lässt Tk die Änderung melden."""
    field = app.notes_field.text
    field.delete("1.0", "end")
    field.insert("1.0", text)
    field.mark_set("insert", "end-1c")
    app.tk_root.update()


def test_notes_save_keeps_trailing_space_and_cursor(window):
    _type_notes(window, "Braucht ")
    window._notes_pending_save.flush()  # wie der abgelaufene Debounce-Timer
    window.tk_root.update()

    assert window.current_plan.classroom.students[0].diagnostic.notes == ["Braucht"]
    assert window.notes_field.get_raw() == "Braucht "
    assert window.notes_field.text.index("insert") == "1.8"


def test_notes_save_keeps_started_empty_line(window):
    _type_notes(window, "Zeile 1\n")
    window._notes_pending_save.flush()
    window.tk_root.update()

    assert window.notes_field.get_raw() == "Zeile 1\n"


def test_name_save_keeps_trailing_space(window):
    window._name_var.set("Anna ")
    window._name_pending_save.flush()
    window.tk_root.update()

    assert window.current_plan.classroom.students[0].first_name_official == "Anna"
    assert window._name_var.get() == "Anna "


def test_undo_still_reloads_the_fields(window):
    _type_notes(window, "Neu")
    window._notes_pending_save.flush()
    window.tk_root.update()

    window._controller.dispatch(UndoIntent())
    window.tk_root.update()

    assert window.notes_field.get_raw() == ""


def test_external_name_change_is_shown(window):
    student = window.current_plan.classroom.students[0]
    window._controller.dispatch(RenameStudentIntent(student_id=student.student_id, first_name="Berta", last_name="Beispiel"))
    window.tk_root.update()

    assert window._name_var.get() == "Berta"
    assert window._last_name_var.get() == "Beispiel"
    assert not window._name_pending_save.has_pending_for(student.student_id)


def test_switching_desk_loads_the_other_persons_notes(window):
    first, second = window.current_plan.classroom.students[:2]
    window._controller.dispatch(SetNotesIntent(student_id=second.student_id, notes=["Absprache"]))
    _type_notes(window, "Erste ")

    window._set_selection_single(second.seat.x, second.seat.y)
    window.tk_root.update()

    assert window.current_plan.student_by_id(first.student_id).diagnostic.notes == ["Erste"]
    assert window.notes_field.get_raw() == "Absprache"
