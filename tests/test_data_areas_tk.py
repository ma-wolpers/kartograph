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


def _area_button(app, area: DataArea):
    """Symbolknopf mit festem Bereich (Doku: Heute, Noten: Gewichtung)."""
    return next(button for button_area, button in app._docs_area_buttons if button_area is area)


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
    assert _disabled(_area_button(app, DataArea.DOKU)) and not _disabled(_area_button(app, DataArea.NOTEN))
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
    assert app._handle_intent(UiIntent.DOCS_TODAY) is None
    assert app._doc_axis.area_of(app._doc_active_column_key()) is not DataArea.DOKU


@pytest.fixture
def notes_window(window):
    """Datenansicht mit eingeblendetem Notizenbereich (Doku aus, Notizen + Noten an)."""
    _toggle(window, DataArea.DOKU)
    _toggle(window, DataArea.NOTIZEN)
    return window


def _row_cells(app, student) -> dict:
    return dict(next(r for r in app.docs_grid._rows if r.row_id == str(student.student_id)).cells)


def test_flag_column_toggles_like_a_color_and_vanishes_with_its_last_mark(notes_window):
    app = notes_window
    student = app.current_plan.classroom.students[0]
    app._add_note_column("Material", "flag", "rot")
    app.tk_root.update()
    assert app._doc_column_label("mark_rot") == "Material (Rot)"
    assert app._doc_active_column_key() == "mark_rot"
    app._activate_docs_cell(str(student.student_id), "mark_rot")
    app.tk_root.update()
    assert "rot" in app.current_plan.student_by_id(student.student_id).diagnostic.color_tags
    assert _row_cells(app, student)["mark_rot"] == "✓"
    app._activate_docs_cell(str(student.student_id), "mark_rot")
    app.tk_root.update()
    assert "rot" not in app.current_plan.color_palette
    assert not app._doc_axis.has("mark_rot")


def test_flag_column_without_free_color_is_colorless(notes_window):
    app = notes_window
    for _shortcut, color_key, _label, _hex in app.color_palette:
        app._add_note_column(f"Spalte {color_key}", "flag", color_key)
    app._add_note_column("Ohne Farbe", "flag", None)
    app.tk_root.update()
    (colorless,) = [key for key in app.current_plan.color_palette if key.startswith("flag_")]
    assert app._doc_column_label(f"mark_{colorless}") == "Ohne Farbe"


def test_number_and_date_columns_edit_validate_sort_and_clear(notes_window):
    app = notes_window
    first, second = app.current_plan.classroom.students[:2]
    app._add_note_column("Punkte", "number", None)
    app._add_note_column("Abgabe", "date", None)
    app.tk_root.update()
    number_key, date_key = (f"note_{c.column_id}" for c in app.current_plan.note_columns)
    assert app._open_docs_inline_editor(str(first.student_id), number_key, "abc")
    assert not app._close_docs_inline_editor(apply_changes=True, keep_open_on_invalid=True)
    assert "Zahl" in app.status_var.get()
    app._close_docs_inline_editor(apply_changes=False)
    for student, number, when in ((first, "2,5", "3.11.2026"), (second, "10", "1.2.2026")):
        app._open_docs_inline_editor(str(student.student_id), number_key, number)
        app._close_docs_inline_editor(apply_changes=True)
        app._open_docs_inline_editor(str(student.student_id), date_key, when)
        app._close_docs_inline_editor(apply_changes=True)
    app.tk_root.update()
    assert _row_cells(app, first)[number_key] == "2.5" and _row_cells(app, first)[date_key] == "03.11.2026"
    app._sort_docs_table_by_key(date_key)
    order = app._doc_row_order
    assert order.index(str(second.student_id)) < order.index(str(first.student_id))
    app._doc_selected_student_index = app._doc_student_index_by_iid[str(first.student_id)]
    app._set_doc_active_column(number_key)
    app.clear_selected_documentation_symbol()
    app.tk_root.update()
    assert _row_cells(app, first)[number_key] == ""


def test_delete_note_column_after_confirmation(notes_window, monkeypatch):
    app = notes_window
    app._add_note_column("Weg damit", "text", None)
    app.tk_root.update()
    monkeypatch.setattr("app.adapters.gui._mixin_note_dialogs.messagebox.askyesno", lambda *a, **k: True)
    app.delete_note_column_dialog()
    app.tk_root.update()
    assert app.current_plan.note_columns == []


def test_note_dialogs_open(notes_window):
    app = notes_window
    student = app.current_plan.classroom.students[0]
    before = set(app.tk_root.winfo_children())
    app.add_note_column_dialog()
    assert app.edit_docs_general_notes_dialog(str(student.student_id))
    app.tk_root.update()
    opened = [w for w in app.tk_root.winfo_children() if w not in before and w.winfo_class() == "Toplevel"]
    assert len(opened) >= 1
    for widget in opened:
        widget.destroy()
