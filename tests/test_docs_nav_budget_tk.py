"""Budget-Test am echten Hauptfenster: Doku-Navigation kostet unabhängig von der Spaltenzahl gleich viel.

Gezählt werden Tcl-Aufrufe (deterministisch), nicht Millisekunden. Vor dem
DataGrid wuchs ein ↓-Schritt mit jeder Datumsspalte (74 Aufrufe bei 10, 146
bei 80 Doku-Tagen), weil die Treeviews bei jeder Bewegung alle Spaltenköpfe
neu setzten. Beide Plangrößen laufen in *einem* Fenster (ein Tk-Interpreter).
"""

from __future__ import annotations

from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan
from app.tools.perf_bench_gui_nav import measure_docs_navigation

BUDGET_PER_STEP = 80


def test_docs_navigation_cost_does_not_grow_with_columns(tmp_path):
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(30, 10, 3))
    try:
        results = {}
        for sessions in (10, 40):
            path = tmp_path / "plans" / f"budget_{sessions}.json"
            JsonSeatingPlanRepositoryV4().save_plan(build_synthetic_plan(30, sessions, 3), path)
            app.open_plan(path)
            app.tk_root.update()
            results[sessions] = {m.scenario: m.tcl_calls_per_step for m in measure_docs_navigation(app, 6)}
        for scenario, calls_small in results[10].items():
            calls_large = results[40][scenario]
            assert abs(calls_large - calls_small) <= 5, (scenario, calls_small, calls_large)
            assert calls_large <= BUDGET_PER_STEP, (scenario, calls_large)
    finally:
        close()
