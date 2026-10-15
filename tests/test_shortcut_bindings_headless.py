"""Fensterloser Test der echten Kartograph-Bindungstabelle am echten bw-gui-Binder.

``ShortcutMixin`` + ``ShortcutBindingsMixin`` binden an einen echten, nie gezeigten
Tk-Root (mit bw-gui-Router, ``create_root``). Tastendrücke laufen über
``bw_gui.testing.keys.press_key`` durch die bw-gui-Dispatcher in Bindtag-Reihenfolge
-- ohne OS-Fokus, es öffnet sich kein Fenster. Abgesichert:

* die komplette Tabelle registriert sich ohne semantische Kollision (der Binder
  würde sonst schon beim Binden ``ValueError`` werfen);
* NumLock-Regression: Symbol-, Leertasten-, Farb- und Mitarbeit-Kürzel erreichen ihre
  Handler mit gesetztem NumLock-Bit (win32 ``0x0008``), Strg/Alt blockieren;
* Migrationsregeln der ``KeySpec``-Tabelle: CapsLock ändert keine Kürzel, Shift-Form
  der Symbolbuchstaben, Ziffernblock = Haupttastatur, ``Ctrl+Shift+R`` (früher als
  ``<Control-Shift-r>`` nur mit CapsLock erreichbar), Canvas-Pfeile exakt;
* der Modus kommt aus ``AppState`` (ohne offenen Plan feuern Editor-Kürzel nicht);
* das LaufKern-Manifest trägt die kanonische Tastennotation.

Tk-Tastatur-Routing im echten Hauptfenster: ``test_shortcut_bindings_window_tk.py``
(Opt-in, ``TK_FOCUS_TESTS=1``).
"""

from __future__ import annotations

import tkinter
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.gui._mixin_shortcut_bindings import ShortcutBindingsMixin
from app.adapters.gui._mixin_shortcuts import ShortcutMixin
from app.adapters.gui.laufkern_manifest_provider import build_runtime_shortcut_manifest
from app.adapters.gui.main_window_constants import COLOR_MARKER_PALETTE, _known_ui_intents
from app.adapters.gui.ui_intents import UiIntent
from app.application.app_state import AppState, InteractionMode
from app.infrastructure.symbol_config_loader import load_symbol_definitions
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.contracts import EventResult, TkBackend, build_ui_hsm_contract
from bw_gui.runtime import create_root, ui
from bw_gui.testing.keys import press_key
from bw_libs.ui_contract.keybinding import KeybindingRegistry

SHIFT, CAPSLOCK, CONTROL, NUMLOCK, ALT_WIN32 = 0x0001, 0x0002, 0x0004, 0x0008, 0x20000
SYMBOLS_PATH = Path(__file__).resolve().parents[1] / "config" / "symbols.json"


@pytest.fixture(scope="module")
def root():
    """Ein echter, zurückgezogener Tk-Root (Router installiert) für das ganze Modul.

    Wiederholt bei der bekannten Tcl-Init-Race unter Windows (``Can't find a usable
    tk.tcl``, s. bw-gui ``tests/conftest.py``).
    """
    for attempt in range(3):
        try:
            instance = create_root()
            break
        except tkinter.TclError as exc:
            if "usable" not in str(exc) or attempt == 2:
                raise
    instance.withdraw()
    yield instance
    instance.destroy()


class _Host(ShortcutBindingsMixin, ShortcutMixin):
    """Minimaler Host: echte Shortcut-Mixins, Handler zeichnen nur Aufrufe auf."""

    def __init__(self, root, state: AppState) -> None:
        self.calls: list[tuple] = []
        self.tk_root = root
        self.canvas = ui.Canvas(root)
        self._runtime_shortcuts = KeybindingRegistry()
        self._hsm_contract = build_ui_hsm_contract(intents=_known_ui_intents())
        self._controller = SimpleNamespace(state=state)
        self._shortcut_runtime_offline = False
        self.symbol_definitions, _warning = load_symbol_definitions(SYMBOLS_PATH)
        self._shortcut_to_symbol = {d.shortcut: d.meaning for d in self.symbol_definitions if d.shortcut}
        self.color_palette = COLOR_MARKER_PALETTE

    def _init_shortcut_binder(self) -> None:
        """Wie produktiv, aber mit festem win32-Backend (Zustandsbits unten sind win32)."""
        super()._init_shortcut_binder()
        self._shortcut_binder.backend = TkBackend.WIN32

    def dispose(self) -> None:
        """Gibt Fenster-Binder und Canvas frei (der Root lebt modulweit weiter)."""
        self._shortcut_binder.dispose()
        self.canvas.destroy()

    def _is_text_input_focused(self) -> bool:
        """Kein Textfeld fokussiert."""
        return False

    def _handle_intent(self, intent: str):
        """Intent-Dispatch nur aufzeichnen (Fachlogik ist nicht Gegenstand dieses Tests)."""
        self.calls.append(("_handle_intent", (intent,)))
        return EventResult.HANDLED

    def __getattr__(self, name):
        """Alle übrigen ``_on_*``-Handler als aufzeichnende Stubs bereitstellen."""
        if name.startswith("_on_"):
            return lambda *args: self.calls.append((name, args))
        raise AttributeError(name)


def _open_plan_state() -> AppState:
    plan = build_synthetic_plan(num_students=2, num_sessions=0, num_grade_columns=0)
    return AppState(current_plan=plan, interaction_mode=InteractionMode.GRID)


@pytest.fixture
def host(root):
    instance = _Host(root, _open_plan_state())
    instance._bind_shortcuts()
    yield instance
    instance.dispose()


def _names(host) -> list[str]:
    return [call[0] if call[0] != "_handle_intent" else call[1][0] for call in host.calls]


def test_full_table_binds_without_conflicts(host):
    assert host._runtime_shortcuts.find_conflicts() == []


@pytest.mark.parametrize(
    ("keysym", "char", "handler"),
    [
        ("a", "a", "_on_symbol_shortcut"),
        ("space", " ", "_on_space_symbol_shortcut"),
        ("1", "1", "_on_color_shortcut"),
        ("plus", "+", "_on_participation_rating_shortcut"),
        ("l", "l", "_on_custom_symbol_shortcut"),
    ],
)
def test_numlock_regression_ctrl_and_alt_block(host, keysym, char, handler):
    for state in (NUMLOCK, 0):
        press_key(host.canvas, keysym, char=char, state=state)
    for state in (CONTROL, ALT_WIN32, CONTROL | NUMLOCK):
        press_key(host.canvas, keysym, state=state)  # Ctrl++ ist Zoom, nicht Mitarbeit
    assert [name for name in _names(host) if name.startswith("_on_")] == [handler, handler]


def test_capslock_and_shift_forms_of_symbol_letters(host):
    press_key(host.canvas, "A", char="A", state=CAPSLOCK)
    press_key(host.canvas, "A", char="A", state=SHIFT)
    press_key(host.canvas, "L", char="L", state=SHIFT | NUMLOCK)
    assert _names(host) == ["_on_symbol_shortcut", "_on_symbol_shortcut", "_on_custom_symbol_shortcut"]


def test_keypad_is_the_same_character_or_key(host):
    press_key(host.canvas, "KP_Add", char="+", state=NUMLOCK)
    press_key(host.canvas, "KP_Subtract", char="-", state=NUMLOCK)
    press_key(host.canvas, "KP_Enter", char="\r", state=NUMLOCK)
    press_key(host.canvas, "KP_Add", state=CONTROL | NUMLOCK)
    assert _names(host) == [
        "_on_participation_rating_shortcut",
        "_on_participation_rating_shortcut",
        "_on_return_key",
        UiIntent.ZOOM_IN,
    ]


def test_ctrl_shift_letters_ignore_capslock(host):
    press_key(host.canvas, "R", state=CONTROL | SHIFT)
    press_key(host.canvas, "d", state=CONTROL | SHIFT | CAPSLOCK)
    press_key(host.canvas, "equal", state=CONTROL | SHIFT)  # deutsches Layout: = ist Shift+0
    assert _names(host) == [UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG, UiIntent.TOGGLE_DOCUMENTATION, UiIntent.ZOOM_IN]


def test_canvas_arrows_are_exact(host):
    press_key(host.canvas, "Up")
    press_key(host.canvas, "Up", state=SHIFT)
    press_key(host.canvas, "Up", state=CONTROL)
    assert _names(host) == [UiIntent.MOVE_UP, UiIntent.EXPAND_UP]


def test_editor_shortcuts_need_an_open_plan_in_app_state(root):
    host = _Host(root, AppState())
    host._bind_shortcuts()
    try:
        press_key(host.canvas, "a", char="a", state=NUMLOCK)
        assert host.calls == []
    finally:
        host.dispose()


def test_declared_ctrl_shortcut_fires_with_numlock(host):
    press_key(host.canvas, "f", state=CONTROL | NUMLOCK)
    assert _names(host) == [UiIntent.GRID_SYMBOL_FILTER]


def test_manifest_carries_canonical_key_notation(host):
    manifest = build_runtime_shortcut_manifest(host._runtime_shortcuts)
    keys = {route.binding_id: route.metadata["keys"] for route in manifest.routes}
    assert keys["view.docs.toggle"] == ("Ctrl+Shift+D",)
    assert keys["viewport.zoom.in"] == ("Ctrl++", "Ctrl+=")
    assert keys["symbol.a"] == ("A", "Shift+A")
