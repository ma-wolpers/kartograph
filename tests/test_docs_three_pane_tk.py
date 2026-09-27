"""Tk-Integrationstests für die Drei-Pane-Dokutabelle (NAMES / MAIN / RIGHT).

Prüft die gemeinsamen Invarianten der drei Treeview-Projektionen an echten
Tk-Widgets: gleiche iids und Reihenfolge, gleiche vertikale Position (aus
jeder Quelle), synchrone Zeilenauswahl/Item-Fokus unabhängig von der aktiven
Spalte, Sortierung über Rebuilds hinweg und Kopfklick-Sortierung.

Robuster Aufbau: sichtbares Root-Fenster mit fester Geometrie, Widgets
vollständig angelegt, ``update()`` vor jeder Geometrie-/Scroll-/Fokusprüfung.
Den Tk-Widget-Fokus liest ``focus_lastfor()`` (unabhängig davon, ob die
Test-App gerade den Desktop-Fokus hat).
"""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

import pytest

from app.adapters.gui._mixin_docs_edit import DocsEditMixin
from app.adapters.gui._mixin_docs_events import DocsEventsMixin
from app.adapters.gui._mixin_docs_nav import DocsNavMixin
from app.adapters.gui._mixin_docs_table import DocsTableMixin
from app.adapters.gui._mixin_docs_view import DocsViewMixin
from app.adapters.gui._mixin_layout_docs import LayoutDocsMixin
from app.adapters.gui._mixin_viewport import ViewportMixin
from app.adapters.gui.docs_table_model import DocColumnAxis, DocsPane
from app.adapters.gui.docs_table_rules import sort_iids
from app.core.domain.models_v4 import Seat, Student, StudentId
from app.tools.perf_bench_docs_table import build_synthetic_plan

TODAY = "2026-01-01"


class _DocsHost(
    tk.Frame,
    LayoutDocsMixin,
    ViewportMixin,
    DocsTableMixin,
    DocsEventsMixin,
    DocsNavMixin,
    DocsViewMixin,
    DocsEditMixin,
):
    """Schlanker Host: echte Doku-Widgets + Doku-Mixins, ohne restliches Hauptfenster."""

    def __init__(self, root: tk.Tk, plan) -> None:
        super().__init__(root)
        self.current_plan = plan
        self.theme_key = None
        self._doc_selection_status_var = tk.StringVar(master=root, value="")
        self._doc_selected_student_index = 0
        self._doc_selected_date_index = 0
        self._doc_student_coords = []
        self._doc_dates = []
        self._doc_tree_iid_by_student_index = {}
        self._doc_student_index_by_iid = {}
        self._doc_rows = {}
        self._doc_axis = DocColumnAxis((), ())
        self._doc_row_order = []
        self._doc_date_column_ids = []
        self._doc_fixed_column_ids = []
        self._doc_selected_nondate_column_id = None
        self._doc_sort_column = None
        self._doc_sort_ascending = True
        self._docs_splitter_positioned = False
        self._docs_inline_editor = None
        self._docs_inline_editor_tree = None
        self._docs_inline_editor_row_id = None
        self._docs_inline_editor_kind = None
        self._docs_inline_editor_model_column = None
        self._docs_cell_overlay = None
        self.docs_container = tk.Frame(self)
        self.docs_container.pack(fill="both", expand=True)
        self._build_docs_tree_widgets()

    def _symbol_glyph(self, symbol_name: str) -> str:
        return "*"

    def _today_doc_date(self) -> str:
        return TODAY

    def _shortcut_scope_allows(self, scope: str) -> bool:
        return True


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.geometry("900x400+0+0")
    yield root
    root.destroy()


@pytest.fixture
def host(tk_root):
    plan = build_synthetic_plan(num_students=60, num_sessions=12, num_grade_columns=3)
    win = _DocsHost(tk_root, plan)
    win.pack(fill="both", expand=True)
    win._refresh_documentation_table()
    tk_root.update()
    yield win
    win.destroy()
    tk_root.update()


def _trees(host):
    return host._docs_trees_by_pane()


def _assert_projection_consistent(host):
    """Invarianten 1+2: gleiche iids, gleiche Reihenfolge = sort_iids, _doc_rows passt zum Tree-Inhalt."""
    expected = sort_iids(host._doc_rows.values(), host._doc_sort_column, host._doc_sort_ascending, host._doc_axis)
    for tree in _trees(host).values():
        assert list(tree.get_children()) == expected
    for iid, row in host._doc_rows.items():
        assert host.docs_name_tree.item(iid, "text") == row.nachname
        assert [str(v) for v in host.docs_tree.item(iid, "values")] == list(row.date_cells)


class TestVerticalScrollSync:
    @pytest.mark.parametrize("source", list(DocsPane))
    def test_scrolling_any_pane_moves_all_three(self, host, tk_root, source):
        calls = {"total": 0, "depth": 0, "max_depth": 0}
        original = host._sync_docs_yscroll

        def counting_sync(pane, first, last):
            calls["total"] += 1
            calls["depth"] += 1
            calls["max_depth"] = max(calls["max_depth"], calls["depth"])
            try:
                original(pane, first, last)
            finally:
                calls["depth"] -= 1

        host._sync_docs_yscroll = counting_sync
        for pane, tree in _trees(host).items():
            tree.configure(yscrollcommand=lambda f, l, p=pane: host._sync_docs_yscroll(p, f, l))

        _trees(host)[source].yview_moveto(0.5)
        tk_root.update()

        firsts = {pane: round(tree.yview()[0], 6) for pane, tree in _trees(host).items()}
        assert len(set(firsts.values())) == 1, firsts
        assert firsts[source] > 0
        assert round(float(host.docs_y_scroll.get()[0]), 6) == firsts[source]
        assert calls["max_depth"] == 1  # kein rekursives Selbst-Auslösen
        assert calls["total"] <= 6  # konvergiert, kein Ping-Pong

    def test_shared_scrollbar_moves_all_three(self, host, tk_root):
        host._docs_yview("moveto", "0.4")
        tk_root.update()
        firsts = {round(tree.yview()[0], 6) for tree in _trees(host).values()}
        assert len(firsts) == 1 and firsts.pop() > 0


class TestRowSelectionVsActiveColumn:
    @pytest.mark.parametrize("active_key", ["date_4", "grade_col1"])
    def test_click_on_name_changes_only_row(self, host, tk_root, active_key):
        host._select_doc_date_column(4)
        host._set_doc_active_column(active_key)
        anchor_before = host._doc_selected_date_index
        nondate_before = host._doc_selected_nondate_column_id
        iid = host._doc_row_order[3]
        host.docs_name_tree.see(iid)
        tk_root.update()
        x, y, _w, h = host.docs_name_tree.bbox(iid, "#0")
        host.docs_name_tree.event_generate("<Button-1>", x=x + 5, y=y + h // 2)
        tk_root.update()

        for tree in _trees(host).values():
            assert tree.selection() == (iid,)  # Zeilenauswahl
            assert tree.focus() == iid  # Treeview-Item-Fokus
        assert host._doc_active_column_key() == active_key
        assert host._doc_selected_date_index == anchor_before
        assert host._doc_selected_nondate_column_id == nondate_before


class TestHorizontalNavigationFocus:
    def test_focus_follows_active_column_across_panes(self, host, tk_root):
        host._select_doc_date_column(0)
        host.docs_tree.focus_set()
        tk_root.update()

        host._on_docs_horizontal_nav(-1)
        tk_root.update()
        assert host._doc_active_column_key() == "vorname"
        assert tk_root.focus_lastfor() == host.docs_name_tree

        host._on_docs_horizontal_nav(-1)
        assert host._doc_active_column_key() == "nachname"
        host._on_docs_horizontal_nav(1)
        host._on_docs_horizontal_nav(1)
        tk_root.update()
        assert host._doc_active_column_key() == "date_0"
        assert tk_root.focus_lastfor() == host.docs_tree

    def test_left_from_first_grade_returns_to_current_anchor(self, host, tk_root):
        host._select_doc_date_column(7)
        host._set_doc_active_column(host._doc_axis.first_selectable_nondate_right())
        host._on_docs_horizontal_nav(-1)
        tk_root.update()
        assert host._doc_active_column_key() == "date_7"
        assert tk_root.focus_lastfor() == host.docs_tree


class TestRebuild:
    def test_insert_delete_update_keep_three_trees_consistent(self, host, tk_root):
        plan = host.current_plan
        removed = plan.classroom.students.pop(5)
        plan.classroom.students.append(
            Student(student_id=StudentId.new(), first_name_official="Neu", last_name="Zuletzt", seat=Seat(x=9, y=9))
        )
        host._refresh_documentation_table()
        tk_root.update()
        assert str(removed.student_id) not in host._doc_rows
        _assert_projection_consistent(host)

        first_session = plan.documentation.sessions[0]
        some_student = plan.classroom.students[0]
        first_session.entries[some_student.student_id].symbols["beteiligung"] = 3
        first_session.entries[some_student.student_id].grades["col0"] = 1.0
        host._refresh_documentation_table()
        tk_root.update()
        _assert_projection_consistent(host)

    def test_sort_survives_rebuild(self, host, tk_root):
        host._sort_docs_table_by_key("nachname")
        host._sort_docs_table_by_key("nachname")  # -> absteigend
        assert (host._doc_sort_column, host._doc_sort_ascending) == ("nachname", False)
        order_before = list(host._doc_row_order)

        plan = host.current_plan
        student = plan.classroom.students[0]
        plan.documentation.sessions[0].entries[student.student_id].symbols["beteiligung"] = 1
        host._refresh_documentation_table()  # Fast Path
        tk_root.update()
        assert (host._doc_sort_column, host._doc_sort_ascending) == ("nachname", False)
        assert host._doc_row_order == order_before
        _assert_projection_consistent(host)

        plan.classroom.students.pop(0)  # Neuaufbau
        host._refresh_documentation_table()
        tk_root.update()
        assert (host._doc_sort_column, host._doc_sort_ascending) == ("nachname", False)
        assert host._doc_row_order == [iid for iid in order_before if iid != str(student.student_id)]
        _assert_projection_consistent(host)

    def test_vanished_sort_and_active_column_fall_back(self, host, tk_root):
        host._select_doc_date_column(11)
        host._set_doc_active_column("grade_col2")
        host._sort_docs_table_by_key("grade_col2")
        plan = host.current_plan
        plan.documentation.grade_columns.pop()  # col2 weg
        plan.documentation.sessions[:] = plan.documentation.sessions[:5]  # Datumsachse schrumpft
        host._refresh_documentation_table()
        tk_root.update()
        assert host._doc_sort_column is None and host._doc_sort_ascending is True
        assert host._doc_selected_nondate_column_id is None
        assert host._doc_active_column_key() == host._doc_axis.date_key(len(host._doc_dates) - 1)
        _assert_projection_consistent(host)


class TestHeadingClickSort:
    @pytest.mark.parametrize(
        ("pane", "x", "expected_key"),
        [
            (DocsPane.NAMES, 10, "nachname"),
            (DocsPane.NAMES, 160, "vorname"),
            (DocsPane.MAIN, 130, "date_1"),
            (DocsPane.RIGHT, 190, "grade_col0"),
        ],
    )
    def test_heading_click_sorts_all_three_trees(self, host, tk_root, pane, x, expected_key):
        host._on_docs_pane_click(pane, SimpleNamespace(x=x, y=5))
        tk_root.update()
        assert (host._doc_sort_column, host._doc_sort_ascending) == (expected_key, True)
        _assert_projection_consistent(host)
        host._on_docs_pane_click(pane, SimpleNamespace(x=x, y=5))
        assert (host._doc_sort_column, host._doc_sort_ascending) == (expected_key, False)
        _assert_projection_consistent(host)
