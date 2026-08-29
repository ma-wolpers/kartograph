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
from tests.conftest import make_plan, make_student


class _FakeController:
    def __init__(self) -> None:
        self.state_version = 0


class _GridTestWindow(tk.Frame, GridRenderMixin, GridHelpersMixin):
    """Minimales Test-Double: nur die für redraw_grid() nötigen Attribute/Methoden."""

    def __init__(self, root: tk.Tk, plan) -> None:
        super().__init__(root)
        self.canvas = tk.Canvas(self, width=400, height=300)
        self.canvas.pack()
        self.pack()
        root.update()

        self._controller = _FakeController()
        self.current_plan = plan
        self.theme_key = "light"
        self.name_format = "Vorname Nachname"
        self.disambiguate_colliding_names = False
        self.cell_size = 92
        self.canvas_radius = 10
        self.selection = RectSelection(0, 0)

        self._grid_names_cache_key = None
        self._grid_names_cache_value = None
        self._grid_geometry_cache_key = None
        self._grid_geometry_cache_value = None
        self._grid_font_size_cache_key = None
        self._grid_font_size_cache_value = None

        # Minimale Symbol-/Farb-Infrastruktur — der Synthetik-Plan nutzt keine.
        self._grid_visible_symbols: set[str] = set()
        self._documentation_only_symbols: set[str] = set()
        self.color_palette: list = []
        self._color_by_key: dict = {}
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


def test_cache_is_reused_when_state_version_unchanged(tk_root):
    plan, _sid, _col = _make_plan_with_grade()
    win = _GridTestWindow(tk_root, plan)
    try:
        win.redraw_grid()
        names_value_1 = win._grid_names_cache_value
        geometry_value_1 = win._grid_geometry_cache_value
        font_value_1 = win._grid_font_size_cache_value

        win.redraw_grid()  # state_version unveraendert (0) -> muss denselben Cache treffen

        assert win._grid_names_cache_value is names_value_1
        assert win._grid_geometry_cache_value is geometry_value_1
        assert win._grid_font_size_cache_value == font_value_1
    finally:
        win.destroy()


def test_cache_invalidates_when_state_version_changes(tk_root):
    plan, sid, col = _make_plan_with_grade()
    win = _GridTestWindow(tk_root, plan)
    try:
        win.redraw_grid()
        names_value_1 = win._grid_names_cache_value
        geometry_value_1 = win._grid_geometry_cache_value

        # Simuliert einen echten Edit: neuer Planzustand + gebumpter Versionszaehler
        # (KartographAppController.dispatch() macht beides zusammen, s. app_controller.py).
        # Gleiches Datum wie beim urspruenglichen Grade -> ueberschreibt ihn (statt
        # eine zweite Note hinzuzufuegen, die gemittelt wuerde und "(3)" ergaebe).
        win.current_plan = record_grade(plan, sid, "2025-09-01", col, 4.0)
        win._controller.state_version = 1
        win.redraw_grid()

        assert win._grid_names_cache_value is not names_value_1
        assert win._grid_geometry_cache_value is not geometry_value_1

        texts = [
            win.canvas.itemcget(item, "text")
            for item in win.canvas.find_withtag("grid")
            if win.canvas.type(item) == "text"
        ]
        assert "(4)" in texts  # neuer Wert wird tatsaechlich gezeichnet, nicht der gecachte alte
    finally:
        win.destroy()
