"""Tk-Test: Die Symbol-Legende im Detailbereich zeigt je Symbol die Texte seiner Kompetenzen.

Format (Entscheidung der Nutzerin 2026-11-18): eine Zeile pro Symbol,
``"🎯🎯 Konzentration: Text a, Text b"``; zwischen zwei Symbolen ein Abstand.
Echtes Hauptfenster (``open_isolated_window``, temporärer Workspace, Standard-
katalog, synthetischer Plan -- keine echten Daten).
"""

from __future__ import annotations

import pytest

from app.adapters.gui.main_window_constants import DETAILS_SYMBOL_LEGEND_GAP
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    plan = build_synthetic_plan(3, 1, 0)
    student = plan.classroom.students[0]
    student.diagnostic.symbols = {"Konzentration": 2, "Beteiligung": 1}
    app, close = open_isolated_window(tmp_path_factory.mktemp("legend_competences"), plan)
    app.tk_root.geometry("1100x650+0+0")
    app._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
    student = app.current_plan.classroom.students[0]
    app._set_selection_single(student.seat.x, student.seat.y)
    app._reveal_details(student.seat.x, student.seat.y)
    app.tk_root.update()
    yield app
    close()


def _legend_labels(app):
    return app.symbol_legend_frame.winfo_children()


def test_one_line_per_symbol_with_texts_of_all_linked_competences(window):
    concentration = window._symbol_by_meaning["Konzentration"]
    expected_texts = [window.competences_by_id[cid].level_text(2) for cid in concentration.competence_ids]

    texts = [label.cget("text") for label in _legend_labels(window)]

    assert texts[0].startswith("👆 Beteiligung: ")
    assert texts[1] == f"🎯🎯 Konzentration: {', '.join(expected_texts)}"
    assert len(texts) == 2


def _top_pady(label) -> int:
    """Oberer ``pady``-Wert eines gepackten Labels (Tk liefert Zahl, Text oder Tupel)."""
    return int(str(label.pack_info()["pady"]).strip("()").replace(",", " ").split()[0])


def test_symbols_are_separated_by_a_gap(window):
    first, second = _legend_labels(window)
    assert _top_pady(first) == 0
    assert _top_pady(second) == DETAILS_SYMBOL_LEGEND_GAP
