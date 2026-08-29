"""Perf-Benchmark für die Redraw-Memoization (Kartograph Item 4).

Vergleicht wiederholte ``redraw_grid()``-Aufrufe bei UNVERÄNDERTEM Plan
(der Normalfall bei reiner Cursor-Navigation/Drag/Scroll) mit und ohne
Cache-Wiederverwendung — "ohne Cache" simuliert dabei exakt das
Vorher-Verhalten, indem die Cache-Schlüssel vor jedem Aufruf zurückgesetzt
werden, sodass jeder Aufruf zwangsläufig neu rechnet (dieselbe Methode,
nicht eine zweite Implementierung — siehe ``perf_bench_docs_table.py`` für
dasselbe Prinzip bei Item 1).

Nutzt ausschließlich synthetische Testdaten — niemals echte Plandateien.

Aufruf:
    python -m app.tools.perf_bench_redraw_grid
    python -m app.tools.perf_bench_redraw_grid --students 30 --sessions 40 --redraws 50
"""

from __future__ import annotations

import argparse
import datetime
import random
import time
import tkinter as tk
from datetime import date

from app.adapters.gui._mixin_grid_helpers import GridHelpersMixin
from app.adapters.gui._mixin_grid_render import GridRenderMixin
from app.core.domain.models_v4 import (
    Classroom,
    DocumentationBlock,
    GradeColumn,
    PlanMeta,
    Seat,
    SeatingPlan,
    Session,
    SessionEntry,
    Student,
    TeacherSeat,
)
from app.core.domain.plan_selection import RectSelection
from app.core.domain.student_id import StudentId


class _FakeController:
    def __init__(self) -> None:
        self.state_version = 0


class _GridBenchWindow(tk.Frame, GridRenderMixin, GridHelpersMixin):
    """Wie tests/test_redraw_grid_memoization.py's Test-Double, für Timing statt Assertions."""

    def __init__(self, root: tk.Tk, plan: SeatingPlan) -> None:
        super().__init__(root)
        self.canvas = tk.Canvas(self, width=1200, height=800)
        self.canvas.pack()
        self.pack()
        root.update()

        self._controller = _FakeController()
        self.current_plan = plan
        self.theme_key = "light"
        self.name_format = "Vorname Nachname"
        self.disambiguate_colliding_names = False
        self.cell_size = 92
        self.canvas_radius = 15
        self.selection = RectSelection(0, 0)

        self._grid_names_cache_key = None
        self._grid_names_cache_value = None
        self._grid_geometry_cache_key = None
        self._grid_geometry_cache_value = None
        self._grid_font_size_cache_key = None
        self._grid_font_size_cache_value = None

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

    def invalidate_caches(self) -> None:
        """Simuliert den Vorher-Zustand: erzwingt bei jedem Aufruf volle Neuberechnung."""
        self._grid_names_cache_key = None
        self._grid_geometry_cache_key = None
        self._grid_font_size_cache_key = None


def build_synthetic_plan(num_students: int, num_sessions: int) -> SeatingPlan:
    """Baut einen rein synthetischen Plan (erfundene Namen) mit Sitzgeometrie und Noten."""
    students = [
        Student(
            student_id=StudentId.new(),
            first_name_official=f"Test{i}",
            last_name=f"Schueler{i}",
            seat=Seat(x=i % 10, y=i // 10),
        )
        for i in range(num_students)
    ]
    classroom = Classroom(teacher_seat=TeacherSeat(x=-1, y=-1), students=students)
    grade_columns = [GradeColumn(column_id="col0", category="schriftlich", title="Note")]

    rng = random.Random(42)
    base_date = datetime.date(2026, 1, 1)
    sessions: list[Session] = []
    for day in range(num_sessions):
        date_key = (base_date + datetime.timedelta(days=day)).isoformat()
        entries: dict[StudentId, SessionEntry] = {}
        for student in students:
            entry = SessionEntry()
            entry.grades["col0"] = round(rng.uniform(1.0, 6.0), 1)
            entries[student.student_id] = entry
        sessions.append(Session(date=date_key, entries=entries))

    documentation = DocumentationBlock(grade_columns=grade_columns, sessions=sessions)
    return SeatingPlan(
        format_version=4,
        plan_id="perf-bench-synthetic",
        meta=PlanMeta(name="Benchmark (synthetisch)"),
        classroom=classroom,
        documentation=documentation,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=30)
    parser.add_argument("--sessions", type=int, default=40)
    parser.add_argument("--redraws", type=int, default=50)
    args = parser.parse_args()

    print(f"Synthetischer Plan: {args.students} Schüler, {args.sessions} Sessions")
    plan = build_synthetic_plan(args.students, args.sessions)

    root = tk.Tk()
    root.geometry("1200x800+3000+3000")
    try:
        win = _GridBenchWindow(root, plan)
        win.redraw_grid()  # einmaliger Kalt-Aufruf (Cache-Aufbau), nicht mitgezählt

        start = time.perf_counter()
        for _ in range(args.redraws):
            win.redraw_grid()  # state_version unveraendert -> trifft den Cache
        cached_time = (time.perf_counter() - start) / args.redraws

        start = time.perf_counter()
        for _ in range(args.redraws):
            win.invalidate_caches()  # simuliert den Vorher-Zustand: jeder Aufruf rechnet neu
            win.redraw_grid()
        uncached_time = (time.perf_counter() - start) / args.redraws

        speedup = uncached_time / cached_time if cached_time > 0 else float("inf")
        print(
            f"redraw_grid() bei unveränderter state_version (z. B. reine Navigation) — "
            f"ohne Cache: {uncached_time * 1000:.2f} ms  mit Cache: {cached_time * 1000:.2f} ms  (×{speedup:.1f})"
        )
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
