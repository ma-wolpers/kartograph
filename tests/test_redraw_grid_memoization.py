"""Tests für die Redraw-Memoization (Kartograph Item 4, Performance-Fix 2026-08-28).

Nutzt einen echten Tk-Root, da ``redraw_grid()`` direkt auf einem echten
Canvas operiert (``winfo_width()``/``canvasx()`` etc.) — ein Mock würde nur
die eigene Erwartung zurückspiegeln. Der Root wird bewusst NICHT mit
``withdraw()`` versteckt (das lässt ``winfo_width()``/``winfo_height()`` bei
0/1 hängen, da das Fenster nie eine echte Geometrie bekommt — leerer
Viewport, keine Zellen sichtbar), sondern weit außerhalb des sichtbaren
Bildschirmbereichs positioniert, damit kein Fenster auf dem Bildschirm
aufblitzt, aber echte Canvas-Maße entstehen.

Deckt genau das ab, was Item 4 geändert hat: (1) läuft ``redraw_grid()``
nach der Umstrukturierung (viele neue Parameter zwischen den Methoden
durchgereicht) noch fehlerfrei, (2) wird bei unverändertem ``state_version``
tatsächlich der Cache wiederverwendet statt neu zu berechnen, (3) wird der
Cache bei einer echten Planänderung (neue ``state_version``) invalidiert.
"""

from __future__ import annotations

import tkinter as tk
from datetime import date

import pytest

from app.adapters.gui._mixin_grid_helpers import GridHelpersMixin
from app.adapters.gui._mixin_grid_render import GridRenderMixin
from app.core.domain.plan_selection import RectSelection
from app.core.domain.student_id import StudentId
from app.core.usecases.v4.grade_usecases import add_grade_column, record_grade
from app.application.plan_derived_data import PlanDerivedData
from bw_gui.widgets.canvas_item_pool import CanvasItemPool
from tests.conftest import make_plan, make_student


class _FakeController:
    """Wie KartographAppController: ein PlanDerivedData-Objekt pro content_version."""

    def __init__(self, window) -> None:
        self.content_version = 0
        self._window = window
        self._derived = None

    def derived(self) -> PlanDerivedData:
        plan = self._window.current_plan
        if self._derived is None or self._derived[0] != self.content_version or self._derived[1].plan is not plan:
            self._derived = (self.content_version, PlanDerivedData(plan))
        return self._derived[1]


class _GridTestWindow(tk.Frame, GridRenderMixin, GridHelpersMixin):
    """Minimales Test-Double: nur die für redraw_grid() nötigen Attribute/Methoden."""

    def __init__(self, root: tk.Tk, plan) -> None:
        super().__init__(root)
        self.canvas = tk.Canvas(self, width=400, height=300)
        self.canvas.pack()
        self.pack()
        root.update()

        self._controller = _FakeController(self)
        self.current_plan = plan
        self.theme_key = "light"
        self.name_format = "Vorname Nachname"
        self.disambiguate_colliding_names = False
        self.cell_size = 92
        self.canvas_radius = 10
        self.selection = RectSelection(0, 0)

        self._grid_content_key = None
        self._grid_font_size_cache_key = None
        self._grid_font_size_cache_value = None
        self._grid_tile_pool = CanvasItemPool(self.canvas, "rectangle", tags=("grid",))

        # Minimale Symbol-/Farb-Infrastruktur — der Synthetik-Plan nutzt keine.
        self._grid_visible_symbols: set[str] = set()
        self._documentation_only_symbols: set[str] = set()
        self.color_palette: list = []
        self._color_by_key: dict = {}
        self._color_order: list = []
        self.symbol_strength = 1
        self.symbol_catalog: list = []
        self._symbol_by_meaning: dict = {}
        self.effective_documentation_symbols: dict = {}

    def _grid_min(self) -> int:
        return -self.canvas_radius

    def _grid_max(self) -> int:
        return self.canvas_radius

    def _today_doc_date(self) -> str:
        return date.today().isoformat()


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    # Bewusst nicht withdraw(): das haelt winfo_width()/winfo_height() bei 1
    # haengen (nie real gemappt), wodurch redraw_grid() einen leeren Viewport
    # saehe. Weit ausserhalb des Bildschirms platziert, damit nichts aufblitzt.
    root.geometry("400x300+3000+3000")
    yield root
    root.destroy()


def _make_plan_with_grade() -> tuple:
    sid = StudentId.new()
    plan = make_plan(students=[make_student(student_id=sid, x=1, y=1)])
    plan, col = add_grade_column(plan, "schriftlich", "Arbeit")
    plan = record_grade(plan, sid, "2025-09-01", col, 2.0)
    return plan, sid, col


def test_redraw_grid_runs_without_error_and_draws_something(tk_root):
    plan, _sid, _col = _make_plan_with_grade()
    win = _GridTestWindow(tk_root, plan)
    try:
        win.redraw_grid()
        assert win.canvas.find_withtag("grid")
    finally:
        win.destroy()


def test_grade_is_rendered_on_desk(tk_root):
    plan, _sid, _col = _make_plan_with_grade()
    win = _GridTestWindow(tk_root, plan)
    try:
        win.redraw_grid()
        texts = [
            win.canvas.itemcget(item, "text")
            for item in win.canvas.find_withtag("grid")
            if win.canvas.type(item) == "text"
        ]
        # Eine einzelne schriftliche Note ohne sonstige Note ist vorlaeufig: "(2)".
        assert "(2)" in texts
    finally:
        win.destroy()


def _items(win, tag):
    return {(win.canvas.type(i), tuple(win.canvas.coords(i)), win.canvas.itemcget(i, "text") if win.canvas.type(i) == "text" else "")
            for i in win.canvas.find_withtag(tag)}


def test_derived_data_is_reused_while_content_version_is_unchanged(tk_root):
    plan, _sid, _col = _make_plan_with_grade()
    win = _GridTestWindow(tk_root, plan)
    try:
        win.redraw_grid()
        derived = win._controller.derived()
        geometries = derived.seat_geometries
        win.redraw_grid()
        assert win._controller.derived() is derived and derived.seat_geometries is geometries
    finally:
        win.destroy()


def test_new_content_version_redraws_with_new_values(tk_root):
    plan, sid, col = _make_plan_with_grade()
    win = _GridTestWindow(tk_root, plan)
    try:
        win.redraw_grid()
        # Echter Edit: neuer Plan + neue content_version (wie KartographAppController.dispatch()).
        win.current_plan = record_grade(plan, sid, "2025-09-01", col, 4.0)
        win._controller.content_version = 1
        win.redraw_grid(selection_only=True)  # Inhalt geändert -> Tische trotzdem neu
        texts = [t for kind, _c, t in _items(win, "grid_transient") if kind == "text"]
        assert "(4)" in texts
    finally:
        win.destroy()


def test_selection_only_redraw_keeps_desks_and_matches_full_redraw(tk_root):
    """Äquivalenztest: inkrementell (nur Auswahl) ergibt exakt dieselbe Darstellung wie komplett."""
    plan, _sid, _col = _make_plan_with_grade()
    win = _GridTestWindow(tk_root, plan)
    try:
        win.redraw_grid()
        desk_ids = set(win.canvas.find_withtag("grid_transient"))
        win.selection = RectSelection(1, 1)
        win.redraw_grid(selection_only=True)
        win.redraw_grid(selection_only=True)  # zweimal: Auswahl-Items dürfen sich nicht stapeln
        assert set(win.canvas.find_withtag("grid_transient")) == desk_ids  # Tische unangetastet
        incremental = (_items(win, "grid_transient"), _items(win, "grid_selection"), len(win.canvas.find_withtag("grid_selection")))
        win.redraw_grid()
        full = (_items(win, "grid_transient"), _items(win, "grid_selection"), len(win.canvas.find_withtag("grid_selection")))
        assert incremental == full
    finally:
        win.destroy()
