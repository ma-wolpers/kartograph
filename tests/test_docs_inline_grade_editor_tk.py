"""Noten in der Doku-Tabelle: Editorziel, Tippen startet den Editor, Löschen der aktiven Zelle, Konfliktdialog (echtes Fenster, synthetischer Plan).

Früher las das Speichern Schüler und Datum aus der *aktuellen* Auswahl: Ein
Klick in eine andere Zeile wählte diese zuerst aus, dann schloss der
Fokusverlust den Editor -- die Note landete beim falschen Schüler, die
bearbeitete Zelle zeigte weiter die alte Note.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from app.adapters.gui.docs_table_model import DocsPane
from app.core.domain.grade_scale import scale_for
from app.core.domain.models_v4 import GradeConflict
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.testing.keys import press_key


@pytest.fixture
def window(tmp_path):
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(4, 3, 1))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app.tk_root.update()
    assert app._editor_surface == "docs"
    yield app
    close()


def _grade(app, row_id: str, column: str = "col0"):
    student = next(s for s in app.current_plan.classroom.students if str(s.student_id) == row_id)
    return app.current_plan.documentation.grade_of(student.student_id, column)


def _open_editor(app, row_id: str, text: str):
    app._on_docs_cell_click(row_id, "grade_col0", DocsPane.RIGHT)
    app._open_docs_inline_grade_editor(row_id, "grade_col0")
    editor = app._docs_inline_editor
    editor.delete(0, "end")
    editor.insert(0, text)
    return editor


def test_focus_loss_after_clicking_another_row_saves_to_the_edited_row(window):
    first, second = window._doc_row_order[0], window._doc_row_order[1]
    before_second = _grade(window, second)
    _open_editor(window, first, "2,3")

    window._on_docs_cell_click(second, "vorname", DocsPane.NAMES)  # Klick wählt zuerst die andere Zeile
    window._close_docs_inline_editor(apply_changes=True)  # ... dann schließt der Fokusverlust

    assert _grade(window, first) == 2.3
    assert _grade(window, second) == before_second


def test_invalid_input_on_return_keeps_the_editor_open(window):
    row = window._doc_row_order[0]
    before = _grade(window, row)
    editor = _open_editor(window, row, "12")

    window._on_docs_inline_editor_return(None)

    assert window._docs_inline_editor is editor and editor.get() == "12"
    assert _grade(window, row) == before
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


class TestUndoIsAtomicInTheRealWindow:
    def test_two_grades_in_the_editor_are_two_steps(self, window):
        row = window._doc_row_order[0]
        before = _grade(window, row)
        for text in ("2,3", "3,3"):
            _open_editor(window, row, text)
            window._close_docs_inline_editor(apply_changes=True)

        window.undo_last_change()
        assert _grade(window, row) == 2.3
        window.undo_last_change()
        assert _grade(window, row) == before

    def test_grid_symbol_is_undone_with_one_press(self, window):
        window._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
        student = window.current_plan.classroom.students[0]
        symbol = window.diagnostic_symbol_catalog[0]
        window._set_selection_single(student.seat.x, student.seat.y)
        date = window._today_doc_date()

        window._toggle_selected_symbol(symbol)
        current = window.current_plan.student_by_id(student.student_id)
        assert current.diagnostic.symbols[symbol] == 1
        assert window.current_plan.documentation.session_for_date(date).entry_for(student.student_id).symbols[symbol] == 1

        window.undo_last_change()
        current = window.current_plan.student_by_id(student.student_id)
        assert symbol not in current.diagnostic.symbols
        session = window.current_plan.documentation.session_for_date(date)
        entry = session.entry_for(student.student_id) if session else None
        assert entry is None or symbol not in entry.symbols


    def test_undo_within_the_save_delay_stays_undone_on_disk(self, window):
        row = window._doc_row_order[0]
        before = _grade(window, row)
        student = next(s for s in window.current_plan.classroom.students if str(s.student_id) == row)
        _open_editor(window, row, "3,3")
        window._close_docs_inline_editor(apply_changes=True)

        window.undo_last_change()  # noch innerhalb der Speicherverzögerung
        window._flush_pending_plan_save()  # das, was der Timer sonst danach täte

        saved = window._controller.plan_repository.load_plan(window.current_plan_path)
        assert saved.documentation.grade_of(student.student_id, "col0") == before


class TestTypingOnAGradeCellStartsTheEditor:
    """Ziffern auf der ausgewählten Notenzelle öffnen den Editor direkt -- ohne vorheriges Enter.

    Gedrückt wird über ``press_key``: dieselben bw-gui-Dispatcher in Bindtag-Reihenfolge
    wie im echten Fenster, also auch das Weiterreichen an die Fenster-Kürzel.
    """

    @staticmethod
    def _select_grade_cell(app):
        row = app._doc_row_order[0]
        app._on_docs_cell_click(row, "grade_col0", DocsPane.RIGHT)
        return row, app.docs_grid.key_widgets[-1]  # rechter Bereich mit den Notenspalten

    def test_digit_replaces_the_old_grade_and_typing_continues(self, window):
        row, pane = self._select_grade_cell(window)
        assert _grade(window, row) is not None  # es gibt eine alte Note, die ersetzt werden muss

        assert press_key(pane, "3", char="3")
        editor = window._docs_inline_editor
        assert editor is not None and editor.get() == "3" and not editor.selection_present()

        editor.insert("end", ",3")  # Cursor steht hinter der Ziffer
        window._on_docs_inline_editor_return(None)
        assert _grade(window, row) == 3.3

    def test_keypad_digit_counts_like_the_main_keyboard(self, window):
        _row, pane = self._select_grade_cell(window)
        assert press_key(pane, "KP_2", char="2")
        assert window._docs_inline_editor.get() == "2"
        window._close_docs_inline_editor(apply_changes=False)

    def test_digit_on_a_date_cell_changes_nothing(self, window):
        row = window._doc_row_order[0]
        window._on_docs_cell_click(row, window._doc_axis.date_key(window._doc_selected_date_index), DocsPane.MAIN)
        before = repr(window.current_plan)

        assert not press_key(window.docs_grid.key_widgets[1], "3", char="3")  # weitergereicht, niemand handelt
        assert window._docs_inline_editor is None and repr(window.current_plan) == before

    def test_enter_still_preselects_the_old_grade(self, window):
        row, _pane = self._select_grade_cell(window)
        doc = window.current_plan.documentation
        assert window._open_selected_docs_grade_cell_editor()
        editor = window._docs_inline_editor
        assert editor.get() == scale_for(doc.grade_scale).format_input(_grade(window, row))
        assert editor.selection_present()
        window._close_docs_inline_editor(apply_changes=False)


class TestDeleteActsOnTheActiveCell:
    def _entry(self, app, row_id, date):
        student = next(s for s in app.current_plan.classroom.students if str(s.student_id) == row_id)
        session = app.current_plan.documentation.session_for_date(date)
        return session.entry_for(student.student_id) if session else None

    def _with_symbol(self, app, row_id):
        """Setzt am Datumsanker ein Symbol für die Zeile, damit es dort etwas zu verlieren gibt."""
        student = next(s for s in app.current_plan.classroom.students if str(s.student_id) == row_id)
        date = app._doc_anchor_date()
        app._controller.dispatch(RecordDocumentationSymbolIntent(
            student_id=student.student_id, date=date, symbol="beteiligung", strength=1,
        ))
        assert self._entry(app, row_id, date).symbols
        return date

    def test_grade_column_deletes_only_this_grade(self, window):
        row = window._doc_row_order[0]
        date = self._with_symbol(window, row)
        window._on_docs_cell_click(row, "grade_col0", DocsPane.RIGHT)
        assert _grade(window, row) is not None

        window.clear_selected_documentation_symbol()

        assert _grade(window, row) is None
        assert self._entry(window, row, date).symbols  # die Datumsspalte daneben bleibt unberührt

    def test_date_column_clears_the_day_but_keeps_the_grade(self, window):
        row = window._doc_row_order[0]
        date = self._with_symbol(window, row)
        window._on_docs_cell_click(row, window._doc_axis.date_key(window._doc_selected_date_index), DocsPane.MAIN)
        before = _grade(window, row)

        window.clear_selected_documentation_symbol()

        assert self._entry(window, row, date) is None
        assert _grade(window, row) == before

    @pytest.mark.parametrize("key", ["vorname", "summary", "overall"])
    def test_other_columns_delete_nothing(self, window, key):
        row = window._doc_row_order[0]
        date = self._with_symbol(window, row)
        window._on_docs_cell_click(row, key, DocsPane.NAMES if key == "vorname" else DocsPane.RIGHT)
        window._set_doc_active_column(key)
        before = _grade(window, row)

        window.clear_selected_documentation_symbol()

        assert _grade(window, row) == before and self._entry(window, row, date).symbols
        assert "nichts zu löschen" in window.status_var.get()


def _widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from _widgets(child)


class TestConflictDialog:
    @pytest.fixture
    def conflicted(self, tmp_path):
        plan = build_synthetic_plan(3, 2, 1)
        sid = plan.classroom.students[0].student_id
        plan.documentation.set_grade(sid, "col0", 4.0)
        plan.documentation.grade_conflicts.append(GradeConflict(sid, "col0", (("2026-01-01", 2.0), ("2026-01-02", 4.0))))
        app, close = open_isolated_window(tmp_path, plan)
        yield app, sid
        close()

    @staticmethod
    def _dialog(app):
        return next(w for w in app.tk_root.winfo_children() if isinstance(w, tk.Toplevel))

    def _press(self, app, text):
        next(w for w in _widgets(self._dialog(app)) if isinstance(w, ttk.Button) and w.cget("text") == text).invoke()

    def test_later_changes_nothing(self, conflicted):
        app, sid = conflicted
        self._press(app, "Später")
        assert len(app.current_plan.documentation.grade_conflicts) == 1
        assert app.current_plan.documentation.grade_of(sid, "col0") == 4.0

    def test_choice_is_applied_and_can_be_undone(self, conflicted):
        app, sid = conflicted
        box = next(w for w in _widgets(self._dialog(app)) if isinstance(w, ttk.Combobox))
        assert box.get().startswith(scale_for(app.current_plan.documentation.grade_scale).format_value(4.0))  # neueste vorbelegt
        box.current(1)
        self._press(app, "Übernehmen")
        assert app.current_plan.documentation.grade_of(sid, "col0") == 2.0
        assert app.current_plan.documentation.grade_conflicts == []
        app._controller.dispatch(UndoIntent())
        assert app.current_plan.documentation.grade_of(sid, "col0") == 4.0
        assert len(app.current_plan.documentation.grade_conflicts) == 1
