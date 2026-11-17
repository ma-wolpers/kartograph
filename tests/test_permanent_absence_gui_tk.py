"""Tk-Test: "dauerhaft abwesend" im echten Hauptfenster bedienen.

Schalter im Detail-Panel und Bearbeiten-Menü markieren/heben auf (eine Aktion),
gesperrte Einträge melden sich in der Statuszeile, Undo nimmt die Markierung
zurück, die Spaltenansicht zeigt Abwesende ausgegraut ganz unten -- bei jeder
Sortierung. ``open_isolated_window``: temporärer Workspace, synthetischer Plan.
"""

from __future__ import annotations

import pytest

from app.core.domain.permanent_absence import LOCKED_MESSAGE, MARK_ABSENT_LABEL, UNMARK_ABSENT_LABEL
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


@pytest.fixture
def window(tmp_path):
    """Hauptfenster im Raster, Details der ersten Person aufgedeckt."""
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(4, 2, 1))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
    student = app.current_plan.classroom.students[0]
    app._set_selection_single(student.seat.x, student.seat.y)
    app._reveal_details(student.seat.x, student.seat.y)
    app.tk_root.update()
    yield app, student.student_id
    close()


def _absent(app, sid) -> bool:
    return app.current_plan.student_by_id(sid).permanently_absent


def test_switch_marks_and_undo_restores(window):
    app, sid = window
    app.absent_switch.invoke()
    app.tk_root.update()
    assert _absent(app, sid)
    assert app._absent_var.get() is True

    app._controller.dispatch(UndoIntent())
    app.tk_root.update()
    assert not _absent(app, sid)
    assert app._absent_var.get() is False


def test_menu_entry_label_follows_the_state(window):
    app, sid = window
    assert app._permanent_absence_menu_item().label == MARK_ABSENT_LABEL
    app.set_selected_permanent_absence(None)
    app.tk_root.update()
    assert app._permanent_absence_menu_item().label == UNMARK_ABSENT_LABEL
    app.set_selected_permanent_absence(None)
    assert not _absent(app, sid)


def test_entries_are_locked_with_a_status_message(window):
    app, sid = window
    app.set_selected_permanent_absence(True)
    app.tk_root.update()
    colors_before = list(app.current_plan.student_by_id(sid).diagnostic.color_tags)

    app._toggle_selected_color("gelb")
    assert app.status_var.get() == LOCKED_MESSAGE
    assert app.current_plan.student_by_id(sid).diagnostic.color_tags == colors_before
    assert app._doc_action_target("Symbole") is None


def test_docs_view_shows_absent_rows_greyed_at_the_bottom(window):
    app, sid = window
    app.set_selected_permanent_absence(True)
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app.tk_root.update()
    for ascending in (True, False):
        app._doc_sort_column, app._doc_sort_ascending = "nachname", ascending
        app._apply_doc_row_order()
        app.tk_root.update()
        assert app._doc_row_order[-1] == str(sid)
        muted = {row.row_id for row in app.docs_grid._rows if row.muted}
        assert muted == {str(sid)}
