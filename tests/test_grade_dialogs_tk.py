"""Tk-Integrationstest der Notendialoge am echten Hauptfenster (synthetischer Plan, keine echten Daten).

Prüft: Gewichtungsdialog rechnet Anteile live, OK schreibt Prozente und
Faktoren als genau einen Undo-Schritt, der Spaltenkopf zeigt den Faktor;
"Notenspalte hinzufügen" legt Kategorie, Titel und Faktor in einem Fenster an
und hält bei ungültigem Faktor offen.
"""

from __future__ import annotations

import pytest

from app.adapters.gui.docs_table_model import grade_column_key
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.models_v4 import GradeColumn
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from tests.conftest import make_plan, make_student


@pytest.fixture
def app(tmp_path):
    """Echtes Hauptfenster mit zwei sonstigen und einer schriftlichen Notenspalte."""
    plan = make_plan(students=[make_student(first_name="Anna", last_name="Beispiel", x=1)])
    plan.documentation.grade_columns = [
        GradeColumn("ka", "schriftlich", "KA 1"),
        GradeColumn("ref", "sonstig", "Referat"),
        GradeColumn("heft", "sonstig", "Heft"),
    ]
    workspace = tmp_path / "ws"
    workspace.mkdir()
    window, close = open_isolated_window(workspace, plan)
    window._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    window.tk_root.update()
    yield window
    close()


def _toplevel(app, title):
    for child in app.tk_root.winfo_children():
        if child.winfo_class() == "Toplevel" and child.title() == title:
            return child
    return None


def _widgets(widget, cls):
    found = [widget] if widget.winfo_class() == cls else []
    for child in widget.winfo_children():
        found.extend(_widgets(child, cls))
    return found


def _label_texts(dialog):
    """Angezeigte Texte aller Labels (bei ``textvariable`` deren aktueller Wert)."""
    texts = []
    for label in _widgets(dialog, "TLabel"):
        variable = str(label.cget("textvariable"))
        texts.append(str(label.getvar(variable)) if variable else str(label.cget("text")))
    return texts


def _button(dialog, text):
    return next(b for b in _widgets(dialog, "TButton") if str(b.cget("text")) == text)


def test_weighting_dialog_live_shares_one_undo_step_and_header(app):
    app.configure_grade_weighting_dialog()
    app.tk_root.update()
    dialog = _toplevel(app, "Gewichtung")
    assert dialog is not None
    entries = _widgets(dialog, "TEntry")  # Schriftlich, Sonstig, dann KA 1, Referat, Heft
    entries[3].delete(0, "end")
    entries[3].insert(0, "2")
    app.tk_root.update()
    assert "33.3 %" in _label_texts(dialog)  # Referat: 50 % * 2/3

    _button(dialog, "OK").invoke()
    app.tk_root.update()
    doc = app.current_plan.documentation
    assert doc.column_by_id("ref").weight == 2.0
    assert app._doc_column_label(grade_column_key("ref")) == "Referat ×2"

    app._handle_intent(UiIntent.UNDO)
    app.tk_root.update()
    assert app.current_plan.documentation.column_by_id("ref").weight == 1.0


def test_weighting_dialog_blocks_ok_on_invalid_factor(app):
    app.configure_grade_weighting_dialog()
    app.tk_root.update()
    dialog = _toplevel(app, "Gewichtung")
    entries = _widgets(dialog, "TEntry")
    entries[4].delete(0, "end")
    entries[4].insert(0, "abc")
    app.tk_root.update()
    assert _button(dialog, "OK").instate(["disabled"])
    assert any(text.startswith("Faktor bei „Heft“") for text in _label_texts(dialog))
    dialog.destroy()


def test_add_column_dialog_creates_column_with_category_and_factor(app):
    app.add_grade_column_dialog()
    app.tk_root.update()
    dialog = _toplevel(app, "Notenspalte hinzufügen")
    assert dialog is not None
    radios = _widgets(dialog, "TRadiobutton")
    radios[1].invoke()  # Sonstig
    title_entry, factor_entry = _widgets(dialog, "TEntry")
    title_entry.insert(0, "Vokabeltest")
    factor_entry.delete(0, "end")
    factor_entry.insert(0, "-1")
    _button(dialog, "OK").invoke()
    app.tk_root.update()
    assert int(dialog.winfo_exists())  # ungültiger Faktor: Dialog bleibt offen
    factor_entry.delete(0, "end")
    factor_entry.insert(0, "0,5")
    _button(dialog, "OK").invoke()
    app.tk_root.update()
    created = app.current_plan.documentation.grade_columns[-1]
    assert (created.category, created.title, created.weight) == ("sonstig", "Vokabeltest", 0.5)
