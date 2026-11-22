"""Bereichsauswahl der Datenansicht im echten Hauptfenster (isolierter Workspace, synthetische Daten).

Prüft: Schalter und Ausgrauen (höchstens zwei Bereiche neben den Namen),
Grid-Regionen je Auswahl, Notizenspalte, Speicherung pro Plan in den
Einstellungen (nicht im Plan: Rückgängig dreht die Ansicht nicht zurück),
Sperren für Aktionen ausgeblendeter Bereiche.
"""

from __future__ import annotations

import pytest

from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.data_view_areas import DataArea
from app.core.domain.settings import KartographSettings
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.note_intents import SetNotesIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.widgets.data_grid import Region


@pytest.fixture
def window(tmp_path):
    """Hauptfenster in der Datenansicht mit einem synthetischen Plan."""
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(4, 2, 2))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app.tk_root.update()
    yield app
    close()


def _toggle(app, area: DataArea) -> None:
    """Klickt den Schalter von *area* (wie die Nutzerin) und lässt Tk rendern."""
    app._data_area_switches[area].invoke()
    app.tk_root.update()


def _disabled(widget) -> bool:
    return widget.instate(["disabled"])


def _button(app, text: str):
    return next(button for _area, button in app._docs_area_buttons if button.cget("text") == text)


def test_default_shows_doku_and_grades_and_greys_out_notes(window):
    app = window
    assert app._doc_axis.areas == (DataArea.NAMEN, DataArea.DOKU, DataArea.NOTEN)
    assert app.docs_grid.shown_regions == (Region.LEFT, Region.SCROLL, Region.RIGHT)
    assert _disabled(app._data_area_switches[DataArea.NOTIZEN])
    assert not _disabled(app._data_area_switches[DataArea.DOKU])


def test_hiding_doku_moves_grades_to_the_middle_and_keeps_an_active_column(window):
    app = window
    _toggle(app, DataArea.DOKU)
    assert app._doc_axis.areas == (DataArea.NAMEN, DataArea.NOTEN)
    assert app.docs_grid.shown_regions == (Region.LEFT, Region.SCROLL)
    assert app.docs_grid.region_of_column(app._doc_axis.first_selectable_in(DataArea.NOTEN)) is Region.SCROLL
    assert not _disabled(app._data_area_switches[DataArea.NOTIZEN])
    assert _disabled(_button(app, "Datum umbenennen")) and not _disabled(_button(app, "Note setzen"))
    assert app._doc_axis.has(app._doc_active_column_key())


def test_notes_area_shows_the_general_notes(window):
    app = window
    student = app.current_plan.classroom.students[0]
    app._controller.dispatch(SetNotesIntent(student_id=student.student_id, notes=["braucht Zeit", "sitzt vorne"]))
    _toggle(app, DataArea.DOKU)
    _toggle(app, DataArea.NOTIZEN)
    assert app._doc_axis.areas == (DataArea.NAMEN, DataArea.NOTIZEN, DataArea.NOTEN)
    assert app.docs_grid.region_of_column("notes") is Region.SCROLL
    row = next(r for r in app.docs_grid._rows if r.row_id == str(student.student_id))
    assert row.cells["notes"] == "braucht Zeit · sitzt vorne"


def test_selection_is_saved_per_plan_in_the_settings_and_survives_undo(window):
    app = window
    plan_id = app.current_plan.plan_id
    student = app.current_plan.classroom.students[0]
    app._controller.dispatch(SetNotesIntent(student_id=student.student_id, notes=["x"]))
    _toggle(app, DataArea.DOKU)
    stored = KartographSettings.from_dict(app._controller.settings_repository.load_settings())
    assert stored.data_view_areas == {plan_id: (DataArea.NOTEN,)}
    app._controller.dispatch(UndoIntent())
    app.tk_root.update()
    assert app._doc_axis.areas == (DataArea.NAMEN, DataArea.NOTEN)


def test_actions_of_a_hidden_area_are_blocked_with_a_hint(window):
    app = window
    _toggle(app, DataArea.DOKU)
    assert app._doc_action_target("Symbole") is None
    assert "Doku" in app.status_var.get() and "ausgeblendet" in app.status_var.get()
    sessions_before = list(app.current_plan.documentation.sessions)
    assert app._handle_intent(UiIntent.DELETE_DOCUMENTATION_DATE) is None
    assert app.current_plan.documentation.sessions == sessions_before
