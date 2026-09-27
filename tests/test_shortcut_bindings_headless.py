"""Fensterloser Test der echten Kartograph-Bindungstabelle am echten bw-gui-Binder.

``ShortcutMixin`` + ``ShortcutBindingsMixin`` binden gegen ein Fenster-Double, das
Tk-Bindungen nur aufzeichnet -- es öffnet sich kein Fenster und niemandem wird der
Tastaturfokus genommen. Abgesichert:

* die komplette Tabelle registriert sich ohne semantische Kollision (der Binder
  würde sonst schon beim Binden ``ValueError`` werfen) und ohne Rest-``bind_all``;
* NumLock-Regression: Symbol-, Leertasten-, Farb- und Mitarbeit-Kürzel erreichen ihre
  Handler mit gesetztem NumLock-Bit (win32 ``0x0008``), Strg/Alt blockieren;
* der Modus kommt aus ``AppState`` (ohne offenen Plan feuern Editor-Kürzel nicht).

Tk-Tastatur-Routing im echten Hauptfenster: ``test_shortcut_bindings_window_tk.py``
(Opt-in, ``TK_FOCUS_TESTS=1``).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.gui._mixin_shortcut_bindings import ShortcutBindingsMixin
from app.adapters.gui._mixin_shortcuts import ShortcutMixin
from app.adapters.gui.main_window_constants import COLOR_MARKER_PALETTE, _known_ui_intents
from app.application.app_state import AppState, InteractionMode
from app.infrastructure.symbol_config_loader import load_symbol_definitions
from app.tools.perf_bench_docs_table import build_synthetic_plan
from bw_gui.contracts import TkBackend, build_ui_hsm_contract
from bw_libs.ui_contract.keybinding import KeybindingRegistry

NUMLOCK, CONTROL, ALT_WIN32 = 0x0008, 0x0004, 0x20000
SYMBOLS_PATH = Path(__file__).resolve().parents[1] / "config" / "symbols.json"


class _FakeWindow:
    """Zeichnet ``bind``-Aufrufe wie ein Tk-Fenster auf (ein Skript pro Sequenz)."""

    def __init__(self) -> None:
        self.scripts: dict[str, object] = {}
        self.bind_all_calls: list[str] = []

    def bind(self, sequence, func):
        """Speichert *func* für *sequence* (Tk-Semantik: letzter gewinnt)."""
        self.scripts[sequence] = func

    def bind_all(self, sequence, *_args, **_kwargs):
        """Darf für Kürzel nicht mehr benutzt werden -- nur protokollieren."""
        self.bind_all_calls.append(sequence)

    def focus_get(self):
        """Kein fokussiertes Widget."""
        return None

    def fire(self, sequence, state=0):
        """Ruft das an *sequence* gebundene Skript mit einem synthetischen Event auf."""
        return self.scripts[sequence](SimpleNamespace(state=state, widget=None))


class _Host(ShortcutBindingsMixin, ShortcutMixin):
    """Minimaler Host: echte Shortcut-Mixins, Handler zeichnen nur Aufrufe auf."""

    def __init__(self, state: AppState) -> None:
        self.calls: list[tuple] = []
        self.tk_root = _FakeWindow()
        self.canvas = SimpleNamespace(bind=lambda *_a, **_k: None)
        self._runtime_shortcuts = KeybindingRegistry()
        self._hsm_contract = build_ui_hsm_contract(intents=_known_ui_intents())
        self._controller = SimpleNamespace(state=state)
        self._shortcut_runtime_offline = False
        self._popup_registry = SimpleNamespace(has_mode_blocking_popup=lambda: False)
        self.symbol_definitions, _warning = load_symbol_definitions(SYMBOLS_PATH)
        self._shortcut_to_symbol = {d.shortcut: d.meaning for d in self.symbol_definitions if d.shortcut}
        self.color_palette = COLOR_MARKER_PALETTE

    def _init_shortcut_binder(self) -> None:
        """Wie produktiv, aber mit festem win32-Backend (Test-Double hat kein Tk)."""
        super()._init_shortcut_binder()
        self._shortcut_binder.backend = TkBackend.WIN32

    def _sync_popup_sessions_from_windows(self) -> None:
        """Keine echten Popups im Test."""

    def _is_text_input_focused(self) -> bool:
        """Kein Textfeld fokussiert."""
        return False

    def _handle_intent(self, intent: str):
        """Intent-Dispatch nur aufzeichnen (Fachlogik ist nicht Gegenstand dieses Tests)."""
        self.calls.append(("_handle_intent", (intent,)))
        return "break"

    def __getattr__(self, name):
        """Alle übrigen ``_on_*``-Handler als aufzeichnende Stubs bereitstellen."""
        if name.startswith("_on_"):
            return lambda *args: self.calls.append((name, args))
        raise AttributeError(name)


def _open_plan_state() -> AppState:
    plan = build_synthetic_plan(num_students=2, num_sessions=0, num_grade_columns=0)
    return AppState(current_plan=plan, interaction_mode=InteractionMode.GRID)


@pytest.fixture
def host() -> _Host:
    instance = _Host(_open_plan_state())
    instance._bind_shortcuts()
    return instance


def test_full_table_binds_without_conflicts_and_without_bind_all(host):
    assert host._runtime_shortcuts.find_conflicts(TkBackend.WIN32) == []
    assert host.tk_root.bind_all_calls == []


@pytest.mark.parametrize(
    ("sequence", "handler"),
    [
        ("<KeyPress-a>", "_on_symbol_shortcut"),
        ("<KeyPress-space>", "_on_space_symbol_shortcut"),
        ("<KeyPress-1>", "_on_color_shortcut"),
        ("<KeyPress-plus>", "_on_participation_rating_shortcut"),
        ("<KeyPress-l>", "_on_custom_symbol_shortcut"),
    ],
)
def test_numlock_regression_ctrl_and_alt_block(host, sequence, handler):
    for state in (NUMLOCK, 0, CONTROL, ALT_WIN32, CONTROL | NUMLOCK):
        host.tk_root.fire(sequence, state)
    assert [call[0] for call in host.calls] == [handler, handler]


def test_editor_shortcuts_need_an_open_plan_in_app_state():
    host = _Host(AppState())
    host._bind_shortcuts()
    host.tk_root.fire("<KeyPress-a>", NUMLOCK)
    assert host.calls == []


def test_declared_ctrl_shortcut_fires_with_numlock(host):
    host.tk_root.fire("<Control-f>", CONTROL | NUMLOCK)
    assert host.calls and host.calls[0][0] == "_handle_intent"
