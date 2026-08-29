"""Perf-Benchmark für die Redraw-Memoization (Kartograph Item 4) und die
Kachel-Pool-Wiederverwendung (Item 5, Stufe A).

Vergleicht wiederholte ``redraw_grid()``-Aufrufe bei UNVERÄNDERTEM Plan
(der Normalfall bei reiner Cursor-Navigation/Drag/Scroll) mit und ohne
Cache-Wiederverwendung — "ohne Cache" simuliert dabei exakt das
Vorher-Verhalten, indem die Cache-Schlüssel vor jedem Aufruf zurückgesetzt
werden, sodass jeder Aufruf zwangsläufig neu rechnet (dieselbe Methode,
nicht eine zweite Implementierung — siehe ``perf_bench_docs_table.py`` für
dasselbe Prinzip bei Item 1).

Der zweite Teil misst denselben Trick für die Kachel-Pool-Wiederverwendung:
"ohne Pool" leert ``_grid_tile_pool`` (und löscht die zugehörigen
Canvas-Items) vor jedem Aufruf, was ``_sync_tile_pool()`` zwingt, jede
Kachel komplett neu zu erzeugen — exakt das Vorher-Verhalten von Item 5
Stufe A, wieder über dieselbe Methode simuliert statt über eine zweite
Implementierung. Läuft bei Standard- UND Worst-Case-Zoom (kleine
Zellgröße → deutlich mehr sichtbare Kacheln) und misst neben der Zeit auch
die Canvas-Item-Zahl als Speicher-Proxy (Ziel: bleibt über wiederholte
Zoom-Wechsel begrenzt, wächst nicht monoton).

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
        self._grid_tile_pool: list = []

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

    def simulate_no_tile_pool(self) -> None:
        """Simuliert den Vorher-Zustand von Item 5 Stufe A: erzwingt vollständige
        Kachel-Neuerzeugung bei jedem Aufruf statt Wiederverwendung."""
        for item_id in self._grid_tile_pool:
            self.canvas.delete(item_id)
        self._grid_tile_pool.clear()


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


def _bench_tile_pool(win: _GridBenchWindow, redraws: int, label: str) -> None:
    """Vergleicht gepoolte gegen simuliert ungepoolte Kachel-Erzeugung bei
    fester ``state_version`` (isoliert Item 5 Stufe A von Item 4 — dessen
    Caches bleiben in beiden Zweigen unverändert getroffen)."""
    win.redraw_grid()  # Kalt-Aufruf: baut den Kachel-Pool erstmalig auf.
    pool_size_after_warmup = len(win._grid_tile_pool)

    start = time.perf_counter()
    for _ in range(redraws):
        win.redraw_grid()  # Pool bereits gefüllt -> reine coords()/itemconfigure()-Wiederverwendung
    pooled_time = (time.perf_counter() - start) / redraws

    start = time.perf_counter()
    for _ in range(redraws):
        win.simulate_no_tile_pool()  # simuliert den Vorher-Zustand: jeder Aufruf erzeugt neu
        win.redraw_grid()
    unpooled_time = (time.perf_counter() - start) / redraws

    # Pool muss nach den ungepoolten Aufrufen wieder auf dieselbe Größe
    # zurückwachsen -- sonst wäre das kein fairer Vergleich.
    win.redraw_grid()
    pool_size_after_rebuild = len(win._grid_tile_pool)

    speedup = unpooled_time / pooled_time if pooled_time > 0 else float("inf")
    print(
        f"[{label}] Kacheln pro Aufruf: {pool_size_after_warmup}  "
        f"ohne Pool: {unpooled_time * 1000:.2f} ms  mit Pool: {pooled_time * 1000:.2f} ms  "
        f"(×{speedup:.1f})  Canvas-Items gesamt: {len(win.canvas.find_all())}"
    )
    assert pool_size_after_rebuild == pool_size_after_warmup, (
        "Pool-Größe nach Wiederaufbau weicht ab -- Kachelzahl sollte bei gleichem "
        "Viewport/Zoom stabil sein."
    )


def _bench_tile_pool_soak(win: _GridBenchWindow, cell_sizes: list[int], cycles: int) -> None:
    """Wechselt wiederholt zwischen mehreren Zoomstufen (Zellgrößen) und prüft,
    dass die Canvas-Item-Zahl auf das für die größte Stufe nötige Maximum
    konvergiert statt über die Zyklen hinweg unbegrenzt zu wachsen (Nachweis
    gegen einen Memory-Smell durch das Pooling, s. Plan-Leitplanken)."""
    max_items_seen = 0
    for _ in range(cycles):
        for cell_size in cell_sizes:
            win.cell_size = cell_size
            win.redraw_grid()
            max_items_seen = max(max_items_seen, len(win.canvas.find_all()))

    final_items = len(win.canvas.find_all())
    print(
        f"[Soak: {cycles} Zyklen über Zellgrößen {cell_sizes}] "
        f"max. gesehene Canvas-Items: {max_items_seen}  finale Canvas-Items: {final_items}"
    )
    assert final_items <= max_items_seen, (
        "Canvas-Item-Zahl nach dem Soak-Durchlauf übersteigt das jemals beobachtete "
        "Maximum -- deutet auf unbegrenztes Wachstum hin."
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

        print()
        print("Item 5 Stufe A (Kachel-Pool) — CPU:")
        win.cell_size = 92
        _bench_tile_pool(win, args.redraws, "typisch, cell_size=92")
        win.cell_size = 44
        _bench_tile_pool(win, args.redraws, "Worst-Case-Zoom, cell_size=44")

        print()
        print("Item 5 Stufe A (Kachel-Pool) — Memory-Stabilität über wiederholten Zoom-Wechsel:")
        _bench_tile_pool_soak(win, cell_sizes=[92, 44, 92, 160, 44], cycles=10)
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
