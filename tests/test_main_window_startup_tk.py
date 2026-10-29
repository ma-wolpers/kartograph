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


import pytest

from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.runtime.key_router import router_for
from bw_gui.testing.keys import press_key

SHIFT = 0x0001


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """Echtes Hauptfenster mit synthetischem, geöffnetem Plan."""
    app, close = open_isolated_window(tmp_path_factory.mktemp("kartograph_start"), build_synthetic_plan(3, 1, 0))
    yield app
    close()


def _show_surface(app, surface: str) -> None:
    app._controller.dispatch(SetEditorSurfaceIntent(surface=surface))
    app.tk_root.update()
    # Wächter: ein falscher Wert (z. B. "docs") fiele sonst still auf das Raster zurück.
    assert app._editor_surface == ("docs" if surface == "documentation" else "grid"), surface


def test_router_installed_without_foreign_all_bindings(window):
    assert router_for(window.tk_root).verify() == []


def test_canvas_arrows_move_and_expand_the_selection(window):
    _show_surface(window, "grid")
    window._set_selection_single(0, 0)
    assert press_key(window.canvas, "Right") is True
    assert window.selection.active_cell() == (1, 0)
    assert press_key(window.canvas, "Down", state=SHIFT) is True
    assert window.selection.bounds() == (1, 0, 1, 1)


def test_docs_grid_navigation_is_handled_by_the_widget_binder(window):
    _show_surface(window, "documentation")
    try:
        body = window.docs_grid.key_widgets[1]  # Datumsbereich
        window._doc_selected_student_index = 0
        assert press_key(body, "Down") is True
        assert window._doc_selected_student_index == 1
        assert press_key(body, "Up", state=SHIFT) is True  # Shift toleriert
        assert window._doc_selected_student_index == 0
    finally:
        _show_surface(window, "grid")


def test_overlay_dialog_closes_on_escape(window):
    dialog = window._create_overlay_dialog("Test", "200x100")
    window.tk_root.update()
    assert press_key(dialog, "Escape") is True
    window.tk_root.update()
    assert not dialog.winfo_exists()
