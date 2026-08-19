"""Tests für die reinen Grid-/Doku-Auswahl-Resolver aus _mixin_docs_view.py.

Deckt nur die Tk-freie Entscheidungslogik ab (welcher Index/welche Zelle
gehört zusammen, und wann bewusst nichts übernommen wird statt eines
erfundenen Ersatzes) -- die eigentliche Tk-Anbindung (Fokus, Treeview-
Selektion) ist nur manuell über die laufende App testbar.
"""

from app.adapters.gui._mixin_docs_view import (
    _resolve_doc_student_index_for_cell,
    _resolve_grid_cell_for_doc_index,
)

COORDS = [(0, 0), (1, 0), (2, 1)]


def test_resolve_doc_student_index_for_cell_hit():
    assert _resolve_doc_student_index_for_cell(COORDS, 1, 0) == 1


def test_resolve_doc_student_index_for_cell_empty_cell_returns_none():
    assert _resolve_doc_student_index_for_cell(COORDS, 5, 5) is None


def test_resolve_doc_student_index_for_cell_empty_coords_returns_none():
    assert _resolve_doc_student_index_for_cell([], 0, 0) is None


def test_resolve_grid_cell_for_doc_index_hit():
    assert _resolve_grid_cell_for_doc_index(COORDS, 2) == (2, 1)


def test_resolve_grid_cell_for_doc_index_negative_returns_none_not_zero():
    result = _resolve_grid_cell_for_doc_index(COORDS, -1)
    assert result is None
    assert result != COORDS[0]


def test_resolve_grid_cell_for_doc_index_too_large_returns_none_not_last():
    result = _resolve_grid_cell_for_doc_index(COORDS, 99)
    assert result is None
    assert result != COORDS[-1]


def test_resolve_grid_cell_for_doc_index_empty_coords_returns_none():
    assert _resolve_grid_cell_for_doc_index([], 0) is None
