"""Shortcut-Bindungstabelle für das Kartograph-Hauptfenster.

Einzige Stelle, an der Kartograph die Fenster-Tastaturkürzel deklariert --
ausnahmslos über ``_bind_runtime_shortcut()`` und damit über den bw-gui-
``WindowShortcutBinder`` (Mode-, Text-, Dialog- und Offline-Gating, exakte
Modifier, semantische Kollisionsprüfung; ``docs/KEYBINDING_CONTRACT.md`` in
bw-gui). Tasten werden ausschließlich als ``KeySpec`` in kanonischer Notation
beschrieben (``KeySpec.parse("Ctrl+Shift+D")``), nie als Tk-Sequenz.

Regeln der Tabelle (Migration von Tk-Sequenzen, ``docs/DEVELOPMENT_LOG.md``):

* **Groß-/Kleinschreibung:** Buchstaben folgen Shift, nie CapsLock. Die früheren
  Doppelbindungen ``<Control-Shift-D>``/``<Control-Shift-d>`` (CapsLock) sind eine
  Spec ``Ctrl+Shift+D``.
* **Ziffernblock:** ``KP_Enter`` ist ``Enter``, ``KP_Add``/``KP_Subtract`` sind die
  Zeichen ``+``/``-`` -- keine eigenen Bindungen mehr.
* **Shift-Toleranz:** Benannte Tasten tolerieren Shift wie unter dem alten Binder
  (Shift blockierte dort nie), außer eine eigene Shift-Variante existiert
  (``Ctrl+Delete`` vs. ``Ctrl+Shift+Delete``). Zeichen-Kürzel, die auch mit Shift
  wirken sollen (Symbolbuchstaben), tragen die Shift-Form als zweite Spec.

Die Pfeiltasten des Raster-Canvas sind widget-lokal (``WidgetShortcutBinder`` am
Canvas, ``_bind_canvas_navigation``).
"""

from __future__ import annotations

import string

from app.adapters.gui.main_window_constants import SPACE_SHORTCUT
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.custom_symbol_validation import reserved_symbol_letters
from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from bw_libs.ui_contract.keybinding import UI_MODE_DIALOG, UI_MODE_GLOBAL, UI_MODE_PREVIEW

ensure_bw_gui_on_path()
from bw_gui.contracts import KeySpec
from bw_gui.runtime import WidgetShortcutBinder

_k = KeySpec.parse
_G = (UI_MODE_GLOBAL,)
_P = (UI_MODE_PREVIEW,)
_GP = (UI_MODE_GLOBAL, UI_MODE_PREVIEW)
_GPD = (UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG)

# Mitarbeit: Zeichen -> Bewertung (Ziffernblock-+/- sind dieselben Zeichen).
_PARTICIPATION_KEYS = (("plus", "+", "+"), ("minus", "-", "-"), ("o", "o", "o"), ("s", "s", "☆"))

_CANVAS_NAVIGATION = (
    ("Up", UiIntent.MOVE_UP),
    ("Down", UiIntent.MOVE_DOWN),
    ("Left", UiIntent.MOVE_LEFT),
    ("Right", UiIntent.MOVE_RIGHT),
    ("Shift+Up", UiIntent.EXPAND_UP),
    ("Shift+Down", UiIntent.EXPAND_DOWN),
    ("Shift+Left", UiIntent.EXPAND_LEFT),
    ("Shift+Right", UiIntent.EXPAND_RIGHT),
)


def _letter_specs(letter: str) -> list[KeySpec]:
    """Spec(s) eines Einbuchstaben-Kürzels: Klein- und Großform (Shift) als Alternativen.

    Args:
        letter: Kürzelzeichen aus Katalog oder Buchstabenraum (beliebige Schreibung).

    Returns:
        ``[char(klein), char(groß)]`` für Buchstaben (die Kleinform ist die primäre,
        angezeigte Belegung), sonst genau eine Spec.
    """
    lower, upper = letter.lower(), letter.upper()
    return [KeySpec.char(lower)] if lower == upper else [KeySpec.char(lower), KeySpec.char(upper)]


class ShortcutBindingsMixin:
    """Mixin: deklariert alle Tastaturkürzel des Hauptfensters (Bindungstabelle)."""

    def _bind_shortcuts(self) -> None:
        """Bindet alle globalen und modus-spezifischen Tastaturkürzel über den bw-gui-Binder."""
        self._init_shortcut_binder()
        self._bind_global_shortcuts()
        self._bind_editor_shortcuts()
        self._bind_docs_shortcuts()
        self._bind_symbol_color_participation_shortcuts()
        self._bind_canvas_navigation()

    def _bind_canvas_navigation(self) -> None:
        """Pfeiltasten (Bewegen) und Shift+Pfeiltasten (Bereich erweitern) am Raster-Canvas.

        Widget-lokal: wirken nur, solange der Canvas die Tastenereignisse bekommt.
        Exakte Modifier -- Strg/Alt+Pfeil bewegen nicht (früher bewegte Tks
        Mindestmengen-Semantik auch damit; der Canvas hat keine native Pfeil-Belegung,
        an die das Ereignis stattdessen fiele).
        """
        self._canvas_keys = WidgetShortcutBinder(self.canvas)
        for notation, intent in _CANVAS_NAVIGATION:
            self._canvas_keys.bind(
                _k(notation),
                lambda _e, i=intent: self._handle_intent(i),
                binding_id=f"canvas.{intent}",
                intent=intent,
            )

    def _intent_binding(self, keys, *, intent: str, binding_id: str, modes: tuple[str, ...], text: bool = False) -> None:
        """Bindet *keys* direkt an ``_handle_intent(intent)`` (häufigster Fall).

        Args:
            keys: Eine ``KeySpec`` oder eine Liste alternativer Specs.
            intent: Auszulösender UiIntent.
            binding_id: Eindeutige Binding-ID.
            modes: Erlaubte UI-Modi.
            text: Kürzel auch bei fokussiertem Textfeld aktiv (``allow_when_text_input``).
        """
        self._bind_runtime_shortcut(
            keys,
            lambda _e, i=intent: self._handle_intent(i),
            binding_id=binding_id,
            intent=intent,
            modes=modes,
            allow_when_text_input=text,
        )

    def _bind_global_shortcuts(self) -> None:
        """Planlisten-/globale Kürzel, Undo/Redo, Einstellungen, Escape/Return/Delete."""
        b, ib = self._bind_runtime_shortcut, self._intent_binding
        ib(_k("Ctrl+N"), intent=UiIntent.NEW_PLAN, binding_id="global.new", modes=(UI_MODE_GLOBAL, UI_MODE_DIALOG), text=True)
        b(_k("Ctrl+D"), self._on_duplicate_shortcut, binding_id="global.duplicate", intent=UiIntent.DUPLICATE_SELECTED_PLAN, modes=_G, allow_when_text_input=True)
        b(_k("F2 (tolerate: Shift)"), self._on_rename_shortcut, binding_id="global.rename", intent=UiIntent.RENAME_SELECTED_PLAN, modes=_G, allow_when_text_input=True)
        ib(_k("Ctrl+E"), intent=UiIntent.EXPORT_PDF, binding_id="global.export", modes=_GP, text=True)
        ib(_k("Ctrl+,"), intent=UiIntent.OPEN_SETTINGS, binding_id="global.settings.comma", modes=_GP, text=True)
        ib(_k("Ctrl+Z"), intent=UiIntent.UNDO, binding_id="edit.undo", modes=_GP, text=True)
        ib(_k("Ctrl+Y"), intent=UiIntent.REDO, binding_id="edit.redo", modes=_GP, text=True)
        ib(_k("Ctrl+Shift+R"), intent=UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG, binding_id="debug.runtime.open", modes=_GPD, text=True)
        ib(_k("Ctrl+Shift+O"), intent=UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE, binding_id="debug.runtime.offline", modes=_GPD, text=True)
        b(_k("Delete (tolerate: Shift)"), self._on_delete_key, binding_id="global.delete", intent=UiIntent.GLOBAL_DELETE, modes=_GP)
        ib(_k("Escape (tolerate: Shift)"), intent=UiIntent.ESCAPE, binding_id="global.escape", modes=_GPD, text=True)
        b(_k("Enter (tolerate: Shift)"), self._on_return_key, binding_id="global.return", intent=UiIntent.GLOBAL_RETURN, modes=_GPD, allow_when_text_input=True)

    def _bind_editor_shortcuts(self) -> None:
        """Editor-Kürzel (Raster): Viewport, Lehrertisch, Tischgruppen, Filter, Zwischenablage."""
        ib = self._intent_binding
        ib(_k("Ctrl+0"), intent=UiIntent.RESET_VIEW, binding_id="viewport.reset", modes=_P)
        ib(_k("Ctrl+Enter (tolerate: Shift)"), intent=UiIntent.SET_TEACHER_DESK, binding_id="desk.teacher", modes=_P)
        ib([_k("Ctrl++"), _k("Ctrl+=")], intent=UiIntent.ZOOM_IN, binding_id="viewport.zoom.in", modes=_P)
        ib(_k("Ctrl+-"), intent=UiIntent.ZOOM_OUT, binding_id="viewport.zoom.out", modes=_P)
        ib(_k("Ctrl+T"), intent=UiIntent.OPEN_TABLEGROUP_SETTINGS, binding_id="tablegroup.settings", modes=_P)
        ib(_k("Ctrl+F"), intent=UiIntent.GRID_SYMBOL_FILTER, binding_id="grid.symbol_filter", modes=_P)
        ib(_k("Ctrl+Shift+D"), intent=UiIntent.TOGGLE_DOCUMENTATION, binding_id="view.docs.toggle", modes=_P)
        ib(_k("Ctrl+X"), intent=UiIntent.CUT, binding_id="edit.cut", modes=_P, text=True)
        ib(_k("Ctrl+C"), intent=UiIntent.COPY, binding_id="edit.copy", modes=_P, text=True)
        ib(_k("Ctrl+V"), intent=UiIntent.PASTE, binding_id="edit.paste", modes=_P, text=True)
        ib(_k("D"), intent=UiIntent.ADD_SYMBOL, binding_id="desk.add_symbol", modes=_P)

    def _bind_docs_shortcuts(self) -> None:
        """Dokuansicht-Kürzel: Note, Symbol, Löschen, Datumsnavigation, Spalten."""
        b, ib = self._bind_runtime_shortcut, self._intent_binding
        b(_k("Ctrl+G"), self._on_set_grade_shortcut, binding_id="docs.grade", intent=UiIntent.DOCS_GRADE, modes=_P)
        b(_k("Ctrl+Shift+S"), self._on_set_symbol_shortcut, binding_id="docs.symbol", intent=UiIntent.DOCS_SYMBOL, modes=_P)
        b(_k("Ctrl+Delete"), self._on_clear_symbol_shortcut, binding_id="docs.clear", intent=UiIntent.DOCS_CLEAR, modes=_P)
        b(_k("Ctrl+Backspace"), self._on_clear_symbol_shortcut, binding_id="docs.clear.backspace", intent=UiIntent.DOCS_CLEAR_BACKSPACE, modes=_P)
        b(_k("Ctrl+H"), self._on_docs_today_shortcut, binding_id="docs.today", intent=UiIntent.DOCS_TODAY, modes=_P)
        b(_k("Alt+Left (tolerate: Shift)"), self._on_docs_prev_date_shortcut, binding_id="docs.prev", intent=UiIntent.DOCS_PREV, modes=_P)
        b(_k("Alt+Right (tolerate: Shift)"), self._on_docs_next_date_shortcut, binding_id="docs.next", intent=UiIntent.DOCS_NEXT, modes=_P)
        ib(_k("Ctrl+Shift+U"), intent=UiIntent.RENAME_DOCUMENTATION_DATE, binding_id="docs.date.rename", modes=_P)
        ib(_k("Ctrl+Shift+Backspace"), intent=UiIntent.DELETE_DOCUMENTATION_DATE, binding_id="docs.date.delete", modes=_P)
        ib(_k("Ctrl+Shift+N"), intent=UiIntent.ADD_GRADE_COLUMN, binding_id="docs.grade_column.add", modes=_P)
        ib(_k("Ctrl+Shift+Delete"), intent=UiIntent.DELETE_GRADE_COLUMN, binding_id="docs.grade_column.delete", modes=_P)

    def _bind_symbol_color_participation_shortcuts(self) -> None:
        """Einbuchstaben-Kürzel für Symbole (eingebaut + eigene), Farbpunkte und Mitarbeit.

        Eigene Doku-Symbole: EINMALIG der gesamte freie Einzelbuchstaben-Raum
        (26 Buchstaben minus ``reserved_symbol_letters()`` -- eingebaute
        Symbol-Kürzel plus feste Systembuchstaben O/S/D, dieselbe Funktion wie
        Validierung und Anlage-Formular). Der Handler löst pro Tastendruck live
        gegen den aktuell offenen Plan auf, kein Rebind bei Planwechsel nötig.
        Buchstaben wirken klein und mit Shift (zwei Specs je Definition).
        """
        b = self._bind_runtime_shortcut
        for shortcut, symbol_name in self._shortcut_to_symbol.items():
            if shortcut == SPACE_SHORTCUT:
                continue  # Leertaste: dynamisch aufgelöst, s. unten
            b(
                _letter_specs(shortcut),
                lambda e, s=symbol_name: self._on_symbol_shortcut(e, s),
                binding_id=f"symbol.{shortcut.lower()}",
                intent=UiIntent.SYMBOL_SHORTCUT,
                modes=_P,
            )
        b(_k("Space (tolerate: Shift)"), self._on_space_symbol_shortcut, binding_id="symbol.space", intent=UiIntent.SYMBOL_SHORTCUT, modes=_P)

        for letter in sorted(set(string.ascii_uppercase) - reserved_symbol_letters(self.symbol_definitions)):
            b(
                _letter_specs(letter),
                lambda _e, l=letter: self._on_custom_symbol_shortcut(l),
                binding_id=f"custom_symbol.{letter.lower()}",
                intent=UiIntent.CUSTOM_SYMBOL_SHORTCUT,
                modes=_P,
            )

        for key, color_key, _label, _hex_color in self.color_palette:
            b(
                KeySpec.char(key),
                lambda e, ck=color_key: self._on_color_shortcut(e, ck),
                binding_id=f"color.{color_key}",
                intent=UiIntent.COLOR_SHORTCUT,
                modes=_P,
            )

        for name, character, rating in _PARTICIPATION_KEYS:
            b(
                KeySpec.char(character),
                lambda e, r=rating: self._on_participation_rating_shortcut(e, r),
                binding_id=f"participation.{name}",
                intent=UiIntent.PARTICIPATION_RATING,
                modes=_P,
            )
