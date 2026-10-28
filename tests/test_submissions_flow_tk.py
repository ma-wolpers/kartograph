"""Tk-Integrationstest "Abgaben zählen" am echten Hauptfenster (synthetischer Plan, synthetische ZIP).

Treibt den echten Ablauf: Extras-Menü → ZIP → Startdialog ("Starten") → X für
Fehlende → Viewer → Bewertung per Taste 1/2 → Undo → Viewer schließt bei
Planwechsel. Dateidialog ist gepatcht; keine echten Daten.
"""

from __future__ import annotations

import gc
from io import BytesIO
import zipfile

from PIL import Image
import pytest

import app.adapters.gui._mixin_submissions as submissions_module
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.models_v4 import Session, SessionEntry
from app.core.intents.view_intents import SetEditorSurfaceIntent
from bw_gui.testing.keys import press_key
from tests.conftest import make_plan, make_student
from app.tools.isolated_window import open_isolated_window

DATE = "2026-10-28"


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    anna = make_student(first_name="Anna", last_name="Beispiel", x=1)
    ben = make_student(first_name="Ben", last_name="Muster", x=2)
    cem = make_student(first_name="Cem", last_name="Probe", x=3)
    plan = make_plan(students=[anna, ben, cem])
    # Ein Inhalt hält den Tag am Leben (leere Doku-Tage werden beim Speichern verworfen).
    plan.documentation.sessions.append(Session(date=DATE, entries={cem.student_id: SessionEntry(note="Stunde")}))
    archive = tmp_path / "abgaben.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Anna Beispiel/seite.png", _png())
        zf.writestr("Ben Lukas Muster/aufsatz.docx", b"nur docx")  # zählt als Abgabe
    workspace = tmp_path / "ws"
    workspace.mkdir()
    app, close = open_isolated_window(workspace, plan)
    monkeypatch.setattr(submissions_module.filedialog, "askopenfilename", lambda **_kw: str(archive))
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app._select_doc_date_column(0)
    app.tk_root.update()
    yield app, anna, ben, cem
    app._close_submission_viewer()
    gc.collect()  # PhotoImages des Viewers freigeben, solange Tk noch lebt
    close()


def _symbols(app, student):
    session = app.current_plan.documentation.session_for_date(DATE)
    entry = session.entry_for(student.student_id) if session else None
    return dict(entry.symbols) if entry else {}


def _find(widget, predicate):
    if predicate(widget):
        return widget
    for child in widget.winfo_children():
        found = _find(child, predicate)
        if found is not None:
            return found
    return None


def _click_start(app):
    button = _find(app.tk_root, lambda w: w.winfo_class() == "TButton" and str(w.cget("text")) == "Starten")
    assert button is not None, "Startdialog nicht gefunden"
    button.invoke()
    app.tk_root.update()


def test_menu_entry_requires_an_active_date_column(setup):
    app, *_ = setup
    assert app._menu_items_extras()[0].type == "command"
    app._select_doc_nondate_column("summary")
    assert app._menu_items_extras()[0].type == "disabled"


def test_full_run_marks_missing_rates_live_and_undoes_singly(setup):
    app, anna, ben, cem = setup
    app.count_submissions_dialog()
    app.tk_root.update()
    _click_start(app)

    assert _symbols(app, cem) == {"Nicht abgegeben / verweigert": 1}
    assert _symbols(app, anna) == {} and _symbols(app, ben) == {}
    viewer = app._submission_viewer
    assert viewer is not None and int(viewer.winfo_exists())

    some_widget = viewer.winfo_children()[0]
    press_key(some_widget, "1", char="1")  # Anna (erste Person) vollständig
    press_key(some_widget, "2", char="2")  # Ben lückenhaft (Ordner nur .docx → Hinweisseite)
    app.tk_root.update()
    assert _symbols(app, anna) == {"Abgabe vollständig": 1}
    assert _symbols(app, ben) == {"Abgabe lückenhaft": 1}

    app._handle_intent(UiIntent.UNDO)
    app.tk_root.update()
    assert _symbols(app, ben) == {}
    assert _symbols(app, anna) == {"Abgabe vollständig": 1}


def test_viewer_closes_when_the_plan_is_left(setup):
    app, *_ = setup
    app.count_submissions_dialog()
    app.tk_root.update()
    _click_start(app)
    viewer = app._submission_viewer
    app._handle_intent(UiIntent.GO_TO_LIST)
    app.tk_root.update()
    assert app._submission_viewer is None
    assert not int(viewer.winfo_exists())


def test_custom_symbol_on_new_builtin_letter_is_reported_on_open(tmp_path, monkeypatch):
    """Ein eigenes Symbol auf "E" (jetzt ✓) wird beim Öffnen gemeldet; das Formular öffnet sich."""
    from app.core.domain.models_v4 import CustomSymbolDefinition
    import app.adapters.gui._mixin_symbol_management_form as form_module

    plan = make_plan(students=[make_student()])
    plan.custom_symbols["sym1"] = CustomSymbolDefinition(id="sym1", glyph="★", meaning="Eigenes", shortcut="E")
    shown: list[str] = []
    monkeypatch.setattr(form_module.messagebox, "showinfo", lambda _title, message, **_kw: shown.append(message))
    opened: list[str | None] = []
    monkeypatch.setattr(
        form_module.SymbolManagementFormMixin,
        "_open_custom_symbol_form",
        lambda self, *, symbol_id, glyph, meaning, shortcut: opened.append(symbol_id),
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    app, close = open_isolated_window(workspace, plan)
    try:
        assert len(shown) == 1 and "„Eigenes“ (E)" in shown[0]
        assert opened == ["sym1"]
    finally:
        close()
