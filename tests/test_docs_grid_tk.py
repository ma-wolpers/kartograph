"""Tk-Integrationstests der Doku-Tabelle auf dem bw-gui ``DataGrid`` (Namen | Daten | feste Spalten).

Prüft die fachlichen Invarianten an echten Widgets: angezeigte Reihenfolge =
``sort_iids``, Zellinhalte = ``_doc_rows``, Zeilenauswahl unabhängig von der
aktiven Spalte, Fokus folgt der aktiven Spalte über die Bereiche, Sortierung
über Rebuilds hinweg, Kopfklick-Sortierung und Inline-Editor auf der Zelle.
Die frühere Treeview-Mechanik (Scroll-Abgleich dreier Trees, Item-Fokus) gibt
es nicht mehr — das Grid hat nur eine Zeilenposition.
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
from app.adapters.gui.docs_table_model import DocColumnAxis
from app.adapters.gui.docs_table_rules import sort_iids
from app.application.plan_derived_data import PlanDerivedData
from app.core.domain.models_v4 import Seat, Student, StudentId
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.widgets.data_grid import Region

TODAY = "2026-01-01"


class _DocsHost(tk.Frame, LayoutDocsMixin, DocsTableMixin, DocsEventsMixin, DocsNavMixin, DocsViewMixin, DocsEditMixin):
    """Schlanker Host: echte Doku-Tabelle + Doku-Mixins, ohne restliches Hauptfenster."""

    def __init__(self, root: tk.Tk, plan) -> None:
        super().__init__(root)
        self.current_plan = plan
        self.theme_key = None
        # Wie der Controller: abgeleitete Plandaten (hier ohne Versions-Cache, frisch je Aufruf).
        self._controller = SimpleNamespace(derived=lambda: PlanDerivedData(self.current_plan))
        self.status_var = tk.StringVar(master=root, value="")
        self._doc_selection_status_var = tk.StringVar(master=root, value="")
        self._doc_selected_student_index = 0
        self._doc_selected_date_index = 0
        self._doc_student_coords = []
        self._doc_dates = []
        self._doc_row_id_by_student_index = {}
        self._doc_student_index_by_iid = {}
        self._doc_rows = {}
        self._doc_axis = DocColumnAxis((), ())
        self._doc_row_order = []
        self._doc_date_column_ids = []
        self._doc_fixed_column_ids = []
        self._doc_selected_nondate_column_id = None
        self._doc_sort_column = None
        self._doc_sort_ascending = True
        self._docs_inline_editor = None
        self._docs_inline_editor_target = None
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
    root.geometry("1000x420+0+0")
    yield root
    root.destroy()


@pytest.fixture
def host(tk_root):
    plan = build_synthetic_plan(num_students=60, num_sessions=12, num_grade_columns=3)
    win = _DocsHost(tk_root, plan)
    win.pack(fill="both", expand=True)
    win._refresh_documentation_table()
    tk_root.update()
    tk_root.update()
    yield win
    win.destroy()
    tk_root.update()


def _assert_projection_consistent(host):
    """Angezeigte Reihenfolge = sort_iids, und jede Zelle zeigt den Modellwert."""
    expected = sort_iids(host._doc_rows.values(), host._doc_sort_column, host._doc_sort_ascending, host._doc_axis)
    assert list(host.docs_grid.row_ids) == expected
    for grid_row in host.docs_grid._rows:
        assert dict(grid_row.cells) == host._doc_axis.cells_of(host._doc_rows[grid_row.row_id])


def _row_y(host, visible_index: int) -> int:
    return host.docs_grid._row_h * visible_index + 1


class TestRowSelectionVsActiveColumn:
    @pytest.mark.parametrize("active_key", ["date_4", "grade_col1"])
    def test_click_on_name_changes_only_row(self, host, tk_root, active_key):
        host._select_doc_date_column(4)
        host._set_doc_active_column(active_key)
        anchor_before = host._doc_selected_date_index
        nondate_before = host._doc_selected_nondate_column_id
        host.docs_grid._on_body_click(Region.LEFT, SimpleNamespace(x=5, y=_row_y(host, 3)), 0)
        tk_root.update()
        iid = host._doc_row_order[3]
        assert host.docs_grid._selected_id == iid
        assert host._doc_active_column_key() == active_key
        assert host._doc_selected_date_index == anchor_before
        assert host._doc_selected_nondate_column_id == nondate_before

    def test_vertical_nav_follows_display_order(self, host, tk_root):
        host._sort_docs_table_by_key("nachname")
        host._sort_docs_table_by_key("nachname")  # absteigend
        host._select_docs_row(host._doc_row_order[0])
        host._on_docs_vertical_nav(1)
        tk_root.update()
        assert host.docs_grid._selected_id == host._doc_row_order[1]


class TestHorizontalNavigationFocus:
    def test_focus_follows_active_column_across_regions(self, host, tk_root):
        regions = host.docs_grid.regions
        host._select_doc_date_column(0)
        host._on_docs_horizontal_nav(-1)
        tk_root.update()
        assert host._doc_active_column_key() == "vorname"
        assert tk_root.focus_lastfor() == regions[Region.LEFT].body
        host._on_docs_horizontal_nav(-1)
        assert host._doc_active_column_key() == "nachname"
        host._on_docs_horizontal_nav(1)
        host._on_docs_horizontal_nav(1)
        tk_root.update()
        assert host._doc_active_column_key() == "date_0"
        assert tk_root.focus_lastfor() == regions[Region.SCROLL].body
        assert host.docs_grid._cursor_key == "date_0"

    def test_left_from_first_grade_returns_to_current_anchor(self, host, tk_root):
        host._select_doc_date_column(7)
        host._set_doc_active_column(host._doc_axis.first_selectable_nondate_right())
        host._on_docs_horizontal_nav(-1)
        tk_root.update()
        assert host._doc_active_column_key() == "date_7"
        assert tk_root.focus_lastfor() == host.docs_grid.regions[Region.SCROLL].body


class TestRebuild:
    def test_insert_delete_update_keep_grid_consistent(self, host, tk_root):
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
        host._sort_docs_table_by_key("nachname")
        order_before = list(host._doc_row_order)
        plan = host.current_plan
        student = plan.classroom.students[0]
        plan.documentation.sessions[0].entries[student.student_id].symbols["beteiligung"] = 1
        host._refresh_documentation_table()
        assert (host._doc_sort_column, host._doc_sort_ascending) == ("nachname", False)
        assert host._doc_row_order == order_before
        assert host.docs_grid._sort == ("nachname", False)
        plan.classroom.students.pop(0)
        host._refresh_documentation_table()
        tk_root.update()
        assert host._doc_row_order == [iid for iid in order_before if iid != str(student.student_id)]
        _assert_projection_consistent(host)

    def test_vanished_sort_and_active_column_fall_back(self, host, tk_root):
        host._select_doc_date_column(11)
        host._set_doc_active_column("grade_col2")
        host._sort_docs_table_by_key("grade_col2")
        plan = host.current_plan
        plan.documentation.grade_columns.pop()
        plan.documentation.sessions[:] = plan.documentation.sessions[:5]
        host._refresh_documentation_table()
        tk_root.update()
        assert host._doc_sort_column is None and host._doc_sort_ascending is True
        assert host._doc_selected_nondate_column_id is None
        assert host._doc_active_column_key() == host._doc_axis.date_key(len(host._doc_dates) - 1)
        _assert_projection_consistent(host)


class TestHeaderClickSortAndEditor:
    @pytest.mark.parametrize(
        ("region", "x", "expected_key"),
        [(Region.LEFT, 10, "nachname"), (Region.LEFT, 160, "vorname"), (Region.SCROLL, 130, "date_1"),
         (Region.RIGHT, 190, "grade_col0")],
    )
    def test_header_click_sorts(self, host, tk_root, region, x, expected_key):
        view = host.docs_grid.regions[region]
        host.docs_grid._on_header_click(view, SimpleNamespace(x=x))
        tk_root.update()
        assert (host._doc_sort_column, host._doc_sort_ascending) == (expected_key, True)
        _assert_projection_consistent(host)
        host.docs_grid._on_header_click(view, SimpleNamespace(x=x))
        assert (host._doc_sort_column, host._doc_sort_ascending) == (expected_key, False)

    def test_double_click_on_grade_opens_editor_on_the_cell(self, host, tk_root):
        host.docs_grid._on_body_click(Region.RIGHT, SimpleNamespace(x=190, y=_row_y(host, 2)), 1)
        tk_root.update()
        editor = host._docs_inline_editor
        assert editor is not None and host._docs_inline_editor_target.column_id == "col0"
        assert editor.master == host.docs_grid.regions[Region.RIGHT].body
        assert int(editor.place_info()["y"]) == 2 * host.docs_grid._row_h
        host._close_docs_inline_editor(apply_changes=False)
