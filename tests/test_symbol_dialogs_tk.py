"""Tk-Test: Dialog „Symbole und Kompetenzen“ (alle Pläne) und „Für diesen Plan anpassen“.

Echtes Hauptfenster (``open_isolated_window``: temporärer Workspace mit eigenen
Katalog-Arbeitskopien, synthetischer Plan -- keine echten Daten). Die Formulare
werden wie von Hand bedient: Felder füllen, Häkchen setzen, „Speichern“.
"""

from __future__ import annotations

import pytest

from app.core.intents.edit_intents import UndoIntent
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.widgets import CheckList, Checkbox


@pytest.fixture()
def window(tmp_path):
    plan = build_synthetic_plan(3, 1, 0)
    plan.classroom.students[0].diagnostic.symbols = {"Konzentration": 2, "Motivation": 1}
    app, close = open_isolated_window(tmp_path, plan)
    app.tk_root.geometry("1100x650+0+0")
    app._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
    student = app.current_plan.classroom.students[0]
    app._set_selection_single(student.seat.x, student.seat.y)
    app._reveal_details(student.seat.x, student.seat.y)
    app.tk_root.update()
    yield app
    close()


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _newest_dialog(app):
    toplevels = [w for w in _walk(app.tk_root) if w.winfo_class() == "Toplevel" and int(w.winfo_exists())]
    return toplevels[-1]


def _entries(dialog):
    return [w for w in _walk(dialog) if w.winfo_class() == "TEntry"]


def _button(dialog, text):
    return next(w for w in _walk(dialog) if w.winfo_class() == "TButton" and w.cget("text") == text)


def _fill(entry, value):
    entry.delete(0, "end")
    entry.insert(0, value)


def _legend(app):
    return [label.cget("text") for label in app.symbol_legend_frame.winfo_children()]


def test_rename_and_new_letter_apply_everywhere_at_once(window):
    window.open_catalog_dialog()
    window._open_catalog_symbol_form("Konzentration")
    dialog = _newest_dialog(window)
    name, shortcut = _entries(dialog)[:2]
    _fill(name, "Fokus")
    _fill(shortcut, "y")
    _button(dialog, "Speichern").invoke()
    window.tk_root.update()

    assert window._symbol_view.symbol_for_shortcut("y") == "Konzentration"
    assert window._symbol_view.symbol_for_shortcut("z") is None
    assert any(text.startswith("🎯🎯 Fokus: ") for text in _legend(window))
    assert window.current_plan.classroom.students[0].diagnostic.symbols["Konzentration"] == 2
    assert "Fokus" in window._catalog_symbol_table.item("Konzentration")["values"]


def test_deactivated_symbol_has_no_button_but_keeps_its_legend(window):
    window.open_catalog_dialog()
    window._open_catalog_symbol_form("Motivation")
    dialog = _newest_dialog(window)
    next(w for w in _walk(dialog) if isinstance(w, Checkbox)).invoke()
    _button(dialog, "Speichern").invoke()
    window.tk_root.update()

    assert "Motivation" not in window._symbol_buttons
    assert window._symbol_view.symbol_for_shortcut("h") is None
    assert any(text.startswith("🔥 Motivation: ") for text in _legend(window))


def test_new_symbol_needs_a_competence_and_is_then_settable(window):
    window.open_catalog_dialog()
    window._open_catalog_symbol_form(None)
    dialog = _newest_dialog(window)
    next(w for w in _walk(dialog) if w.winfo_class() == "TRadiobutton").invoke()
    _fill(_entries(dialog)[0], "Ausdauer")
    _fill(_entries(dialog)[1], "u")
    _button(dialog, "Speichern").invoke()
    assert int(dialog.winfo_exists())  # ohne Kompetenz abgelehnt, Dialog bleibt offen

    picker = next(w for w in _walk(dialog) if isinstance(w, CheckList))
    picker.checkboxes["lernvoraussetzung.motivation"].invoke()
    _button(dialog, "Speichern").invoke()
    window.tk_root.update()

    assert window._symbol_view.symbol_for_shortcut("u") == "Ausdauer"
    assert "Ausdauer" in window._symbol_buttons


def test_plan_override_changes_legend_only_in_this_plan_and_undo_restores(window):
    window.open_symbol_management_dialog()
    window._open_symbol_override_form("Konzentration")
    dialog = _newest_dialog(window)
    _fill(_entries(dialog)[0], "Bei der Sache")
    picker = next(w for w in _walk(dialog) if isinstance(w, CheckList))
    picker.set_selected(["konzentration.arbeiten"])
    _button(dialog, "Speichern").invoke()
    window.tk_root.update()

    competence = window.competences_by_id["konzentration.arbeiten"]
    assert f"🎯🎯 Bei der Sache: {competence.level_text(2)}" in _legend(window)
    program = next(d for d in window._controller.state.symbol_catalog if d.key == "Konzentration")
    assert program.name == "Konzentration"  # programmweit unverändert
    assert "angepasst" in " ".join(window._symbol_management_table.item("builtin:Konzentration")["values"])

    window._controller.dispatch(UndoIntent())
    window.tk_root.update()
    assert window.current_plan.symbol_overrides == {}
    assert any(text.startswith("🎯🎯 Konzentration: ") for text in _legend(window))
