"""Gruppen-Export im echten Hauptfenster (isolierter Workspace, synthetische Daten).

Prüft: Knopf nur bei einer Zelle im Notizenbereich anklickbar, Frage nach
Personen ohne Eintrag nur bei Bedarf, Export schreibt eine PDF (Dateidialog
durch einen festen Pfad ersetzt).
"""

from __future__ import annotations

import pytest

from app.adapters.gui import _mixin_note_groups_export
from app.adapters.gui.docs_table_model import NOTES_KEY, NACHNAME_KEY
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.data_view_areas import DataArea
from app.core.intents.note_intents import SetNotesIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


@pytest.fixture
def window(tmp_path):
    """Datenansicht mit eingeblendetem Notizenbereich (Notizen + Noten)."""
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(4, 2, 2))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app.tk_root.update()
    app._data_area_switches[DataArea.DOKU].invoke()
    app._data_area_switches[DataArea.NOTIZEN].invoke()
    app.tk_root.update()
    yield app
    close()


def _select(app, key: str) -> None:
    app._set_doc_active_column(key)
    app._sync_docs_cursor()


def _groups_button(app):
    return app._docs_column_buttons["groups"]


def _new_toplevels(app, before):
    return [w for w in app.tk_root.winfo_children() if w not in before and w.winfo_class() == "Toplevel"]


def test_button_is_only_enabled_in_the_notes_area(window):
    app = window
    _select(app, NOTES_KEY)
    assert not _groups_button(app).instate(["disabled"])
    assert app._docs_column_action_label("groups") == "Gruppen dieser Spalte als PDF exportieren"
    _select(app, NACHNAME_KEY)
    assert _groups_button(app).instate(["disabled"])
    _select(app, app._doc_axis.first_selectable_in(DataArea.NOTEN))
    assert _groups_button(app).instate(["disabled"])
    assert "Notizenbereich" in app._docs_column_action_label("groups")


def test_export_writes_the_pdf_and_asks_for_people_without_entry(window, tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    app = window
    first, second = app.current_plan.classroom.students[:2]
    for student in (first, second):
        app._controller.dispatch(SetNotesIntent(student_id=student.student_id, notes=["Gruppe A"]))
    app.tk_root.update()
    out = tmp_path / "gruppen.pdf"
    monkeypatch.setattr(_mixin_note_groups_export.filedialog, "asksaveasfilename", lambda **_k: str(out))
    _select(app, NOTES_KEY)
    before = set(app.tk_root.winfo_children())
    app._handle_intent(UiIntent.DOCS_COLUMN_GROUPS)
    app.tk_root.update()
    (dialog,) = _new_toplevels(app, before)
    texts = [w.cget("text") for w in _all_widgets(dialog) if "text" in w.keys()]
    assert any("2 Personen ohne Eintrag" in t for t in texts)
    export = next(w for w in _all_widgets(dialog) if "text" in w.keys() and w.cget("text") == "Exportieren")
    export.invoke()
    app.tk_root.update()
    assert out.read_bytes().startswith(b"%PDF")
    assert "Gruppen exportiert" in app.status_var.get()


def _all_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _all_widgets(child)
