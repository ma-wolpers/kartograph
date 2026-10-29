"""Benchmark der GUI-Navigation am echten Hauptfenster (Doku-Tabelle ↑↓←→, Raster-Auswahl).

Misst pro Schritt die Zeit inklusive ``update()`` (also inklusive dessen, was
Tk danach zeichnet) und die Zahl der Tcl-Aufrufe (``count_tcl_calls``).
Nutzt ausschließlich synthetische Pläne in einem isolierten Workspace
(``open_isolated_window``) — nie echte Daten. Öffnet kurz ein Fenster.

Aufruf:
    python -m app.tools.perf_bench_gui_nav
    python -m app.tools.perf_bench_gui_nav --students 30 --sessions 10 40 80 --steps 10
"""

from __future__ import annotations

import argparse
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.testing.tcl_calls import count_tcl_calls  # bw_gui-Pfad ist über die app-Importe gesetzt


@dataclass(frozen=True)
class StepMeasurement:
    """Durchschnitt pro Schritt für ein Szenario."""

    scenario: str
    ms_per_step: float
    tcl_calls_per_step: int


def measure_steps(app, scenario: str, step: Callable[[int], object], steps: int) -> StepMeasurement:
    """Misst *steps* Ausführungen von *step* (je mit ``update()``) nach Zeit und Tcl-Aufrufen.

    Hin- und Rückweg wechseln sich ab (erste Hälfte vorwärts), damit der
    Cursor im sichtbaren Bereich bleibt und Läufe vergleichbar sind.

    Args:
        app: Geöffnetes Hauptfenster.
        scenario: Bezeichnung für die Ausgabe.
        step: Bekommt den Schrittindex und führt einen Schritt aus.
        steps: Anzahl der Schritte.
    """
    def run_all() -> None:
        for index in range(steps):
            step(index)
            app.tk_root.update()

    # Aufwärmen (ungemessen): einmalige Arbeit nach Plan-/Oberflächenwechsel
    # (erster Render, Splitter-Platzierung) gehört nicht zum Schritt-Preis.
    for index in (0, steps - 1):
        step(index)
        app.tk_root.update()
    started = time.perf_counter()
    calls = count_tcl_calls(run_all)
    elapsed = time.perf_counter() - started
    return StepMeasurement(scenario, elapsed / steps * 1000, calls // steps)


def measure_docs_navigation(app, steps: int) -> list[StepMeasurement]:
    """Misst ↓/↑ und →/← in der Doku-Tabelle des geöffneten Plans.

    Args:
        app: Geöffnetes Hauptfenster (Plan mit Doku-Tagen).
        steps: Schritte je Szenario.
    """
    app._controller.dispatch(SetEditorSurfaceIntent(surface="documentation"))
    app._select_doc_date_column(0)
    app.tk_root.update()
    half = steps // 2
    return [
        measure_steps(app, "Doku runter/hoch", lambda i: app._on_docs_vertical_nav(1 if i < half else -1), steps),
        measure_steps(app, "Doku rechts/links", lambda i: app._on_docs_horizontal_nav(1 if i < half else -1), steps),
    ]


def measure_grid_selection(app, steps: int) -> StepMeasurement:
    """Misst das Verschieben der Auswahl im Sitzplan-Raster (→/←).

    Args:
        app: Geöffnetes Hauptfenster.
        steps: Schritte.
    """
    app._controller.dispatch(SetEditorSurfaceIntent(surface="grid"))
    app._set_selection_single(0, 0)
    app.tk_root.update()
    half = steps // 2
    return measure_steps(app, "Raster rechts/links", lambda i: app._set_selection_single(i + 1 if i < half else steps - i, 0), steps)


def main() -> None:
    """Führt den Benchmark für mehrere Plangrößen aus und druckt eine Tabelle."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=30)
    parser.add_argument("--sessions", type=int, nargs="+", default=[10, 40, 80])
    parser.add_argument("--steps", type=int, default=10)
    args = parser.parse_args()
    print(f"{'Doku-Tage':>9}  {'Szenario':<20} {'ms/Schritt':>11} {'Tcl/Schritt':>12}")
    # Ein Fenster für alle Plangrößen: ein zweiter Tk-Interpreter im selben Prozess
    # löst Lebenszyklus-Meldungen zerstörter Widgets aus und verfälscht die Messung.
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        app, close = open_isolated_window(workspace, build_synthetic_plan(args.students, args.sessions[0], 3))
        try:
            for sessions in args.sessions:
                plan_path = workspace / "plans" / f"bench_{sessions}.json"
                JsonSeatingPlanRepositoryV4().save_plan(build_synthetic_plan(args.students, sessions, 3), plan_path)
                app.open_plan(plan_path)
                app.tk_root.update()
                for result in [*measure_docs_navigation(app, args.steps), measure_grid_selection(app, args.steps)]:
                    print(f"{sessions:>9}  {result.scenario:<20} {result.ms_per_step:>11.1f} {result.tcl_calls_per_step:>12}")
        finally:
            close()


if __name__ == "__main__":
    main()
