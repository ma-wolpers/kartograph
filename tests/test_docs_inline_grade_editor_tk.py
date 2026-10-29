"""Inline-Noteneditor der Doku-Tabelle: das Ziel steht beim Öffnen fest (echtes Fenster, synthetischer Plan).

Früher las das Speichern Schüler und Datum aus der *aktuellen* Auswahl: Ein
Klick in eine andere Zeile wählte diese zuerst aus, dann schloss der
Fokusverlust den Editor -- die Note landete beim falschen Schüler, die
bearbeitete Zelle zeigte weiter die alte Note.
"""

from __future__ import annotations

import pytest

from app.adapters.gui.docs_table_model import DocsPane
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


@pytest.fixture
def window(tmp_path):
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(4, 3, 1))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app.tk_root.update()
    assert app._editor_surface == "docs"
    yield app
    close()


def _grade(app, row_id: str, date: str, column: str = "col0"):
    student = next(s for s in app.current_plan.classroom.students if str(s.student_id) == row_id)
    session = app.current_plan.documentation.session_for_date(date)
    entry = session.entry_for(student.student_id) if session else None
    return entry.grades.get(column) if entry else None


def _open_editor(app, row_id: str, text: str):
    app._on_docs_cell_click(row_id, "grade_col0", DocsPane.RIGHT)
    app._open_docs_inline_grade_editor(row_id, "grade_col0")
    editor = app._docs_inline_editor
    editor.delete(0, "end")
    editor.insert(0, text)
    return editor


def test_focus_loss_after_clicking_another_row_saves_to_the_edited_row(window):
    first, second = window._doc_row_order[0], window._doc_row_order[1]
    date = window._doc_dates[window._doc_selected_date_index]
    before_second = _grade(window, second, date)
    _open_editor(window, first, "2,3")

    window._on_docs_cell_click(second, "vorname", DocsPane.NAMES)  # Klick wählt zuerst die andere Zeile
    window._close_docs_inline_editor(apply_changes=True)  # ... dann schließt der Fokusverlust

    assert _grade(window, first, date) == 2.3
    assert _grade(window, second, date) == before_second


def test_invalid_input_on_return_keeps_the_editor_open(window):
    row = window._doc_row_order[0]
    date = window._doc_dates[window._doc_selected_date_index]
    before = _grade(window, row, date)
    editor = _open_editor(window, row, "12")

    window._on_docs_inline_editor_return(None)

    assert window._docs_inline_editor is editor and editor.get() == "12"
    assert _grade(window, row, date) == before
    window._close_docs_inline_editor(apply_changes=False)


def test_reentrant_close_during_destroy_saves_once(window, monkeypatch):
    row = window._doc_row_order[0]
    editor = _open_editor(window, row, "1,7")
    dispatched = []
    original_dispatch, original_destroy = window._controller.dispatch, editor.destroy
    monkeypatch.setattr(window._controller, "dispatch", lambda intent: (dispatched.append(intent), original_dispatch(intent))[1])

    def destroy_with_focus_out():
        monkeypatch.setattr(editor, "destroy", original_destroy)  # nur einmal wiedereintreten (alter Code liefe endlos)
        window._close_docs_inline_editor(apply_changes=True)  # wie <FocusOut> beim Zerstören
        original_destroy()

    monkeypatch.setattr(editor, "destroy", destroy_with_focus_out)
    window._close_docs_inline_editor(apply_changes=True)
    assert len(dispatched) == 1
