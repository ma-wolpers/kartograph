"""Starttest: echtes Kartograph-Hauptfenster mit synthetischem Plan, Tasten ohne OS-Fokus.

Baut ``KartographMainWindow`` in einem temporären Workspace (``tmp_path``, auch
``APPDATA``) mit einem rein synthetischen Plan (``build_synthetic_plan``, erfundene
Namen) -- keine echten Nutzerdaten. Tastendrücke laufen über
``bw_gui.testing.keys.press_key`` durch die bw-gui-Dispatcher (kein Fokus nötig; das
``background_windows``-Plugin gibt den OS-Vordergrund sofort zurück).

Abgesichert: der Start über ``BwBaseWindow``/``TkRootHost`` mit installiertem Router
ohne fremde ``all``-Tastaturbindungen, die Canvas-Navigation, die Doku-Tabellen-
Navigation und ein Overlay-Dialog mit Escape über seinen eigenen Fenster-Binder.
"""

from __future__ import annotations

import json
import shutil
import tkinter
from pathlib import Path

import pytest

from app.adapters.bootstrap.wiring import build_gui_dependencies
from app.adapters.gui.main_window import KartographMainWindow
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.infrastructure.repositories.v4.json_plan_repository_v4 import JsonSeatingPlanRepositoryV4
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.runtime.key_router import router_for
from bw_gui.testing.keys import press_key

SHIFT = 0x0001
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """Echtes Hauptfenster mit synthetischem, geöffnetem Plan."""
    workspace = tmp_path_factory.mktemp("kartograph_start")
    patcher = pytest.MonkeyPatch()
    patcher.setenv("APPDATA", str(workspace / "appdata"))
    (workspace / "config").mkdir()
    shutil.copy(REPO_ROOT / "config" / "symbols.json", workspace / "config" / "symbols.json")
    plans_dir = workspace / "plans"
    plans_dir.mkdir()
    (workspace / "config" / "kartograph_settings.json").write_text(
        json.dumps({"plans_dir": str(plans_dir)}), encoding="utf-8"
    )
    plan_path = plans_dir / "synthetisch.json"
    JsonSeatingPlanRepositoryV4().save_plan(build_synthetic_plan(3, 1, 0), plan_path)

    app = _create_window_with_retry(workspace)
    app.tk_root.update()
    app.open_plan(plan_path)
    app.tk_root.update()
    yield app
    app.tk_root.destroy()
    patcher.undo()


def _create_window_with_retry(workspace: Path, attempts: int = 3) -> KartographMainWindow:
    """Baut das Hauptfenster; wiederholt nur bei der bekannten Tcl-Init-Race unter Windows."""
    for attempt in range(attempts):
        try:
            deps = build_gui_dependencies(workspace)
            return KartographMainWindow(controller=deps.controller, shell_config=deps.shell_config)
        except tkinter.TclError as exc:
            if not any(m in str(exc) for m in ("usable", "tcl_findLibrary", "init.tcl")) or attempt == attempts - 1:
                raise
    raise AssertionError("unreachable")


def _show_surface(app, surface: str) -> None:
    app._controller.dispatch(SetEditorSurfaceIntent(surface=surface))
    app.tk_root.update()


def test_router_installed_without_foreign_all_bindings(window):
    assert router_for(window.tk_root).verify() == []


def test_canvas_arrows_move_and_expand_the_selection(window):
    _show_surface(window, "grid")
    window._set_selection_single(0, 0)
    assert press_key(window.canvas, "Right") is True
    assert window.selection.active_cell() == (1, 0)
    assert press_key(window.canvas, "Down", state=SHIFT) is True
    assert window.selection.bounds() == (1, 0, 1, 1)


def test_docs_tree_navigation_is_handled_by_the_widget_binder(window):
    _show_surface(window, "docs")
    try:
        assert press_key(window.docs_tree, "Down") is True
        assert press_key(window.docs_tree, "Up", state=SHIFT) is True  # toleriert, nicht nativ
    finally:
        _show_surface(window, "grid")


def test_overlay_dialog_closes_on_escape(window):
    dialog = window._create_overlay_dialog("Test", "200x100")
    window.tk_root.update()
    assert press_key(dialog, "Escape") is True
    window.tk_root.update()
    assert not dialog.winfo_exists()
