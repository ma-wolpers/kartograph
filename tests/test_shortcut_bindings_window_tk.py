"""Opt-in-Tk-Integrationstest: Kürzel im echten Kartograph-Hauptfenster (NumLock + Migration).

Nur mit ``TK_FOCUS_TESTS=1`` aktiv (öffnet Fenster, übernimmt den Tastaturfokus).

Baut das vollständige ``KartographMainWindow`` in einem temporären Workspace
(``tmp_path``) mit einem rein synthetischen Plan (erfundene Namen,
``build_synthetic_plan``) -- keine echten Nutzerdaten. ``APPDATA`` zeigt ebenfalls
in ``tmp_path``, damit auch Backups nur dort landen.

Abgesichert werden:
* NumLock-Regression: Symbol-, Mitarbeit-, Farbpunkt- und Leertasten-Kürzel feuern
  mit gesetztem NumLock-Bit (win32: ``0x0008``); Strg/Alt blockieren sie.
* Migration ``bind_all`` -> bw-gui-Binder (Fenster-Bindtag): Raster und Dokuansicht
  feuern, Texteingabe und fremde Toplevels nicht, ein blockiertes Alt+Buchstabe
  erreicht weiterhin den ``all``-Router (Menü-Mnemonics, Beobachter), ausgeführte
  Kürzel beenden die Verarbeitung (``HANDLED``); keine semantischen Binding-Kollisionen.
"""

from __future__ import annotations

import os
import sys

import pytest

if sys.platform != "win32":  # Zustandsbits unten sind die gemessenen win32-Werte
    pytest.skip("win32-spezifische Tk-Zustandsbits", allow_module_level=True)
if os.environ.get("TK_FOCUS_TESTS") != "1":
    # Öffnet das maximierte Hauptfenster und muss den Tastaturfokus übernehmen --
    # würde laufende Eingaben des Nutzers in anderen Fenstern abfangen. Die
    # fensterlose Abdeckung liegt in test_shortcut_bindings_headless.py.
    pytest.skip("öffnet Fenster und übernimmt den Fokus; mit TK_FOCUS_TESTS=1 ausführen", allow_module_level=True)

from app.adapters.gui import _mixin_edit
from app.core.intents.view_intents import SetEditorSurfaceIntent
from app.tools.isolated_window import open_isolated_window
from app.tools.perf_bench_docs_table import build_synthetic_plan

NUMLOCK, CONTROL, ALT = 0x0008, 0x0004, 0x20000


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """Echtes Hauptfenster mit synthetischem Plan; Farbbedeutungs-Dialog gestubbt."""
    workspace = tmp_path_factory.mktemp("kartograph_ws")
    patcher = pytest.MonkeyPatch()
    patcher.setattr(_mixin_edit.simpledialog, "askstring", lambda *a, **k: "Test")
    app, close = open_isolated_window(workspace, build_synthetic_plan(3, 1, 0))
    app.selection.set_single(0, 0)
    app.selected_cell = (0, 0)
    yield app
    close()
    patcher.undo()


def _plan_repr(app) -> str:
    return repr(app._controller.state.current_plan)


def _press(app, widget, keysym: str, state: int = 0):
    """Übernimmt den Tastaturfokus für *widget*, sendet KeyPress, meldet Planänderung.

    ``focus_force()`` ist nötig: ohne Tastaturfokus verwirft Tk synthetische
    Tastendrücke. Deshalb ist dieses Modul nur per ``TK_FOCUS_TESTS=1`` aktiv.
    """
    widget.focus_force()
    app.tk_root.update()
    before = _plan_repr(app)
    widget.event_generate(f"<KeyPress-{keysym}>", state=state, when="now")
    app.tk_root.update()
    return before != _plan_repr(app)


def _show_surface(app, surface: str):
    app._controller.dispatch(SetEditorSurfaceIntent(surface=surface))
    app.tk_root.update()
    # Wächter: ein falscher Wert (z. B. "docs") fiele sonst still auf das Raster zurück.
    assert app._editor_surface == ("docs" if surface == "documentation" else "grid"), surface


def test_no_semantic_binding_conflicts(window):
    assert window._runtime_shortcuts.find_conflicts() == []


@pytest.mark.parametrize("keysym", ["a", "plus", "1", "space"])
def test_grid_shortcuts_fire_with_numlock_and_are_blocked_by_ctrl_alt(window, keysym):
    _show_surface(window, "grid")
    assert _press(window, window.canvas, keysym, NUMLOCK)
    assert _press(window, window.canvas, keysym, 0)  # zurück-toggeln
    # Strg blockiert (Alt separat in test_blocked_alt_letter..., weil Alt das Menü öffnet).
    assert not _press(window, window.canvas, keysym, CONTROL | NUMLOCK)


def test_docs_symbol_shortcut_fires_with_numlock(window):
    _show_surface(window, "documentation")
    try:
        tree = window.docs_grid.key_widgets[1]  # Datumsbereich der Doku-Tabelle
        assert _press(window, tree, "a", NUMLOCK)
        assert _press(window, tree, "a", 0)
        assert not _press(window, tree, "a", CONTROL)
    finally:
        _show_surface(window, "grid")


def test_text_input_and_foreign_toplevel_are_gated(window):
    from bw_gui.runtime import ui

    entry = ui.Entry(window.tk_root)
    entry.place(x=0, y=0)
    top = ui.Toplevel(window.tk_root)
    other = ui.Canvas(top)
    other.pack()
    try:
        assert not _press(window, entry, "a", NUMLOCK)
        assert not _press(window, other, "a", NUMLOCK)
    finally:
        entry.destroy()
        top.destroy()
        window.canvas.focus_force()


def test_blocked_alt_letter_still_reaches_global_handlers_and_executed_breaks(window):
    _show_surface(window, "grid")
    from bw_gui.contracts import Key
    from bw_gui.runtime.key_router import ROLE_OBSERVER, router_for

    seen: list[bool] = []
    root = window.tk_root
    observer = router_for(root).register(
        ROLE_OBSERVER, lambda item: seen.append(item.event.modifiers.alt) if item.event.key is Key.CHARACTER else None
    )
    try:
        assert not _press(window, window.canvas, "a", ALT)  # blockiert -> läuft bis zum all-Router
        assert _press(window, window.canvas, "a", 0)  # ausgeführt -> HANDLED, Router sieht nichts
        _press(window, window.canvas, "a", 0)  # Plan zurück-toggeln
    finally:
        observer.remove()
        # Alt+Buchstabe darf das Menü öffnen (globaler <Alt-KeyPress>-Handler) -- schließen.
        window.handle_escape()
        root.update()
    assert seen == [True]
