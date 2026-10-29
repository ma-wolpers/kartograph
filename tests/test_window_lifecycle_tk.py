"""Lebenszyklus: kein geplanter Rückruf des Hauptfensters überlebt dessen Zerstörung.

Vorher planten Watchdog und Backup sich ohne gemerkte ID neu ein, und die
Speicher-Timer wurden beim Zerstören nicht abgemeldet — ein zweiter
Tk-Interpreter im selben Prozess (Tests/Benchmarks) bekam dann Fehler wie
``invalid command name "..._ui_watchdog_tick"``.
"""

from __future__ import annotations

from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan


def _pending_after_ids(app) -> set[str]:
    return set(str(item) for item in app.tk_root.tk.splitlist(app.tk_root.tk.call("after", "info")))


def test_destroy_cancels_recurring_and_save_callbacks(tmp_path):
    app, close = open_isolated_window(tmp_path, build_synthetic_plan(3, 1, 0))
    try:
        app._name_pending_save._pending = None
        app._name_pending_save._after_id = app.after(60_000, lambda: None)  # wie ein ausstehender Feld-Save
        ours = {*app._recurring_after_ids.values(), app._name_pending_save._after_id}
        assert {"watchdog", "backup"} <= set(app._recurring_after_ids)
        assert ours <= _pending_after_ids(app)

        app._cancel_scheduled_callbacks()  # läuft automatisch beim <Destroy> der Wurzel

        assert not (ours & _pending_after_ids(app))
        assert app._recurring_after_ids == {} and app._name_pending_save._after_id is None
    finally:
        close()
