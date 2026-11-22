"""Spaltenknöpfe der Datenansicht im echten Hauptfenster (isolierter Workspace, synthetische Daten).

Dialoge sind durch feste Antworten ersetzt; geprüft werden Ausgrauen, Hover-Text
und je Bereich hinzufügen / umbenennen / löschen samt Rückgängig.
"""

from __future__ import annotations

import pytest

from app.adapters.gui import dialog_services
from app.adapters.gui.docs_table_model import NACHNAME_KEY, grade_column_key
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.data_view_areas import DataArea
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


@pytest.fixture
def window(tmp_path, monkeypatch):
    """Datenansicht (Doku + Noten) mit festen Dialogantworten."""
    answers: list[str] = []
    monkeypatch.setattr(dialog_services.simpledialog, "askstring", lambda *a, **k: answers.pop(0))
    monkeypatch.setattr(dialog_services.messagebox, "askyesno", lambda *a, **k: True)
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(3, 2, 2))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app.tk_root.update()
    yield app, answers
    close()


def _select(app, key: str) -> None:
    app._set_doc_active_column(key)
    app._sync_docs_cursor()


def _do(app, intent: str) -> None:
    app._handle_intent(intent)
    app.tk_root.update()


def _undo(app) -> None:
    app._controller.dispatch(UndoIntent())
    app.tk_root.update()


def _disabled(button) -> bool:
    return button.instate(["disabled"])


def test_toolbar_has_six_icon_buttons_and_greys_out_column_buttons_for_names(window):
    app, _ = window
    assert len(app.docs_toolbar.winfo_children()) == 6
    _select(app, NACHNAME_KEY)
    assert all(_disabled(button) for button in app._docs_column_buttons.values())
    _select(app, grade_column_key("col0"))
    assert not any(_disabled(button) for button in app._docs_column_buttons.values())
    assert app._docs_column_action_label("rename") == "Notenspalte umbenennen"


def test_dates_are_added_moved_and_deleted_with_undo(window):
    app, answers = window
    _select(app, app._doc_axis.date_key(0))
    answers.append("05.03.2031")
    _do(app, UiIntent.DOCS_COLUMN_ADD)
    assert app.current_plan.documentation.session_for_date("2031-03-05") is not None
    _select(app, app._doc_axis.date_key(app._doc_dates.index("2031-03-05")))
    answers.append("06.03.2031")
    _do(app, UiIntent.DOCS_COLUMN_RENAME)
    documentation = app.current_plan.documentation
    assert documentation.session_for_date("2031-03-05") is None and documentation.session_for_date("2031-03-06")
    _undo(app)
    assert app.current_plan.documentation.session_for_date("2031-03-05") is not None
    _select(app, app._doc_axis.date_key(app._doc_dates.index("2031-03-05")))
    _do(app, UiIntent.DOCS_COLUMN_DELETE)
    assert app.current_plan.documentation.session_for_date("2031-03-05") is None


def test_grade_column_rename_and_delete(window):
    app, answers = window
    _select(app, grade_column_key("col0"))
    answers.append("Klassenarbeit 1")
    _do(app, UiIntent.DOCS_COLUMN_RENAME)
    assert app.current_plan.documentation.grade_columns[0].title == "Klassenarbeit 1"
    _undo(app)
    assert app.current_plan.documentation.grade_columns[0].title == "Note 0"
    _select(app, grade_column_key("col0"))
    _do(app, UiIntent.DOCS_COLUMN_DELETE)
    assert [c.column_id for c in app.current_plan.documentation.grade_columns] == ["col1"]


def test_note_and_flag_columns_are_renamed(window):
    app, answers = window
    app._data_area_switches[DataArea.DOKU].invoke()
    app._data_area_switches[DataArea.NOTIZEN].invoke()
    app._add_note_column("Punkte", "number", None)
    app._add_note_column("Material", "flag", "rot")
    app.tk_root.update()
    note_key = f"note_{app.current_plan.note_columns[0].column_id}"
    _select(app, note_key)
    answers.append("Bonus")
    _do(app, UiIntent.DOCS_COLUMN_RENAME)
    assert app.current_plan.note_columns[0].title == "Bonus"
    _select(app, "mark_rot")
    answers.append("Heft")
    _do(app, UiIntent.DOCS_COLUMN_RENAME)
    assert app.current_plan.color_palette["rot"].meaning == "Heft"
    assert app._docs_column_action_label("delete") == "Ja/Nein-Spalte samt Markierungen löschen"


def test_add_in_grades_opens_the_grade_column_dialog(window, monkeypatch):
    app, _ = window
    opened = []
    monkeypatch.setattr(app, "add_grade_column_dialog", lambda: opened.append("grade"))
    _select(app, grade_column_key("col1"))
    _do(app, UiIntent.DOCS_COLUMN_ADD)
    assert opened == ["grade"]


def test_enter_on_a_date_cell_opens_the_symbol_dialog(window, monkeypatch):
    app, _ = window
    opened = []
    monkeypatch.setattr(app, "set_selected_documentation_symbol_dialog", lambda: opened.append("symbol"))
    _select(app, app._doc_axis.date_key(0))
    _do(app, UiIntent.DOCS_EDIT_CELL)
    assert opened == ["symbol"]
