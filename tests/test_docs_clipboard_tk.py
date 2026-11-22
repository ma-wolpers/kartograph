"""Kopieren, Ausschneiden, Einfügen in der Datenansicht (echtes Hauptfenster, synthetische Daten).

Die echte Zwischenablage bleibt unberührt (``MemoryTextClipboard``). Geprüft
wird über ``_handle_intent`` (wie Strg+C/X/V und das Bearbeiten-Menü): Notizen,
Notizspalten, Noten und Doku-Zellen, jeweils mit Rückgängig.
"""

from __future__ import annotations

import pytest

from app.adapters.gui.docs_table_model import NACHNAME_KEY, NOTES_KEY, grade_column_key
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.data_view_areas import DataArea
from app.core.domain.grade_scale import scale_for
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.note_intents import SetNotesIntent
from app.core.intents.session_intents import ClearDocEntryIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.runtime import MemoryTextClipboard


@pytest.fixture
def window(tmp_path):
    """Hauptfenster in der Datenansicht (Doku + Noten) mit Speicher-Zwischenablage."""
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(4, 2, 2))
    app._text_clipboard = MemoryTextClipboard()
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app.tk_root.update()
    yield app
    close()


def _students(app):
    return app.current_plan.classroom.students[:2]


def _select(app, student, key: str) -> None:
    """Wählt die Zelle (Person, Spalte) aus wie per Klick."""
    app._doc_selected_student_index = app._doc_student_index_by_iid[str(student.student_id)]
    app._set_doc_active_column(key)


def _do(app, intent: str) -> None:
    app._handle_intent(intent)
    app.tk_root.update()


def _undo(app) -> None:
    app._controller.dispatch(UndoIntent())
    app.tk_root.update()


def _notes(app, student) -> list[str]:
    return app.current_plan.student_by_id(student.student_id).diagnostic.notes


def test_general_notes_copy_and_paste_with_undo(window):
    app = window
    first, second = _students(app)
    app._data_area_switches[DataArea.DOKU].invoke()
    app._data_area_switches[DataArea.NOTIZEN].invoke()
    app._controller.dispatch(SetNotesIntent(student_id=first.student_id, notes=["braucht Zeit", "sitzt vorne"]))
    app.tk_root.update()
    _select(app, first, NOTES_KEY)
    _do(app, UiIntent.COPY)
    assert app._text_clipboard.text == "braucht Zeit\nsitzt vorne"
    _select(app, second, NOTES_KEY)
    _do(app, UiIntent.PASTE)
    assert _notes(app, second) == ["braucht Zeit", "sitzt vorne"]
    _do(app, UiIntent.PASTE)  # zweites Einfügen: kein neuer Stand, also auch kein Undo-Schritt
    _undo(app)
    assert _notes(app, second) == [] and _notes(app, first) == ["braucht Zeit", "sitzt vorne"]


def test_note_column_cut_and_paste_are_one_undo_step_each(window):
    app = window
    first, second = _students(app)
    app._data_area_switches[DataArea.DOKU].invoke()
    app._data_area_switches[DataArea.NOTIZEN].invoke()
    app._add_note_column("Punkte", "number", None)
    app.tk_root.update()
    key = f"note_{app.current_plan.note_columns[0].column_id}"
    app._open_docs_inline_editor(str(first.student_id), key, "2,5")
    app._close_docs_inline_editor(apply_changes=True)
    app.tk_root.update()
    _select(app, first, key)
    _do(app, UiIntent.CUT)
    assert app._text_clipboard.text == "2.5"
    assert app.current_plan.student_by_id(first.student_id).diagnostic.note_values == {}
    _select(app, second, key)
    _do(app, UiIntent.PASTE)
    column_id = app.current_plan.note_columns[0].column_id
    assert app.current_plan.student_by_id(second.student_id).diagnostic.note_values == {column_id: "2.5"}
    _undo(app)
    assert app.current_plan.student_by_id(second.student_id).diagnostic.note_values == {}
    _undo(app)
    assert app.current_plan.student_by_id(first.student_id).diagnostic.note_values == {column_id: "2.5"}


def test_grades_paste_validates_like_the_editor(window):
    app = window
    first, second = _students(app)
    key = grade_column_key("col0")
    app._open_docs_inline_editor(str(first.student_id), key, "2,3")
    app._close_docs_inline_editor(apply_changes=True)
    app.tk_root.update()
    _select(app, first, key)
    _do(app, UiIntent.COPY)
    _select(app, second, key)
    _do(app, UiIntent.PASTE)
    pasted = app.current_plan.documentation.grade_of(second.student_id, "col0")
    assert pasted is not None and pasted == app.current_plan.documentation.grade_of(first.student_id, "col0")
    app._text_clipboard.write_text("abc")
    _do(app, UiIntent.PASTE)
    assert app.current_plan.documentation.grade_of(second.student_id, "col0") == pasted
    assert app.status_var.get() == scale_for(app.current_plan.documentation.grade_scale).input_hint


def test_doku_cell_copies_the_whole_entry_and_paste_is_undoable(window):
    app = window
    first, second = _students(app)
    date = app._doc_dates[0]
    app._controller.dispatch(ClearDocEntryIntent(student_id=second.student_id, date=date))
    app._controller.dispatch(
        RecordDocumentationSymbolIntent(student_id=first.student_id, date=date, symbol="Beteiligung", strength=2)
    )
    app.tk_root.update()
    expected = app.current_plan.documentation.session_for_date(date).entry_for(first.student_id)
    _select(app, first, app._doc_axis.date_key(0))
    _do(app, UiIntent.COPY)
    _select(app, second, app._doc_axis.date_key(0))
    _do(app, UiIntent.PASTE)
    assert app.current_plan.documentation.session_for_date(date).entry_for(second.student_id) == expected
    _undo(app)
    assert app.current_plan.documentation.session_for_date(date).entry_for(second.student_id) is None


def test_doku_paste_refuses_when_something_else_was_copied_meanwhile(window):
    app = window
    first, second = _students(app)
    date = app._doc_dates[0]
    app._controller.dispatch(ClearDocEntryIntent(student_id=second.student_id, date=date))
    app.tk_root.update()
    _select(app, first, app._doc_axis.date_key(0))
    _do(app, UiIntent.COPY)
    app._text_clipboard.write_text("Text aus einem anderen Programm")
    _select(app, second, app._doc_axis.date_key(0))
    _do(app, UiIntent.PASTE)
    assert app.current_plan.documentation.session_for_date(date).entry_for(second.student_id) is None
    assert "Doku-Zelle" in app.status_var.get()


def test_names_copy_but_do_not_cut(window):
    app = window
    first, _ = _students(app)
    _select(app, first, NACHNAME_KEY)
    _do(app, UiIntent.CUT)
    assert app._text_clipboard.text is None
    assert "nur in" in app.status_var.get()
    _do(app, UiIntent.COPY)
    assert app._text_clipboard.text == first.last_name
