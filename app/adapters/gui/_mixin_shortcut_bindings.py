"""Shortcut-Bindungstabelle für das Kartograph-Hauptfenster.

Einzige Stelle, an der Kartograph Tastaturkürzel an Tk bindet -- ausnahmslos
über ``_bind_runtime_shortcut()`` und damit über den bw-gui-
``WindowShortcutBinder`` (Mode-, Text-, Dialog-, Offline- und Modifier-Gating,
semantische Kollisionsprüfung). Kein ``bind_all`` und keine eigene Auswertung
von ``event.state`` für Kürzel: Symbol-, Farb- und Mitarbeit-Kürzel liefen
früher per ``bind_all`` an der Registry vorbei und prüften ``state & 0x0008``
als "Alt" -- unter Windows ist das aber das NumLock-Bit, weshalb die Kürzel bei
eingeschaltetem NumLock wirkungslos waren. Die Semantik dafür liegt jetzt
vollständig in bw-gui (``docs/KEYBINDING_CONTRACT.md`` dort).

Ausnahme: die Pfeiltasten-Bindungen am Raster-Canvas sind widget-lokale
Navigation (``canvas.bind``) und laufen weiter direkt -- inventarisiert in
bw-gui ``docs/TK_USAGE_INVENTORY.md`` als Folgeplan-Punkt.
"""

from __future__ import annotations

import string

from app.adapters.gui.main_window_constants import SPACE_SHORTCUT
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.custom_symbol_validation import reserved_symbol_letters
from bw_libs.ui_contract.keybinding import UI_MODE_DIALOG, UI_MODE_GLOBAL, UI_MODE_PREVIEW

_G = (UI_MODE_GLOBAL,)
_P = (UI_MODE_PREVIEW,)
_GP = (UI_MODE_GLOBAL, UI_MODE_PREVIEW)
_GPD = (UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG)

_PARTICIPATION_KEYS = (
    ("plus", "+"),
    ("KP_Add", "+"),
    ("minus", "-"),
    ("KP_Subtract", "-"),
    ("o", "o"),
    ("s", "☆"),
)


class ShortcutBindingsMixin:
    """Mixin: deklariert alle Tastaturkürzel des Hauptfensters (Bindungstabelle)."""

    def _bind_shortcuts(self) -> None:
        """Bindet alle globalen und modus-spezifischen Tastaturkürzel über den bw-gui-Binder."""
        self._init_shortcut_binder()
        self._bind_global_shortcuts()
        self._bind_editor_shortcuts()
        self._bind_docs_shortcuts()
        self._bind_symbol_color_participation_shortcuts()

        self.canvas.bind("<Up>", lambda _e: self._handle_intent(UiIntent.MOVE_UP))
        self.canvas.bind("<Down>", lambda _e: self._handle_intent(UiIntent.MOVE_DOWN))
        self.canvas.bind("<Left>", lambda _e: self._handle_intent(UiIntent.MOVE_LEFT))
        self.canvas.bind("<Right>", lambda _e: self._handle_intent(UiIntent.MOVE_RIGHT))
        self.canvas.bind("<Shift-Up>", lambda _e: self._handle_intent(UiIntent.EXPAND_UP))
        self.canvas.bind("<Shift-Down>", lambda _e: self._handle_intent(UiIntent.EXPAND_DOWN))
        self.canvas.bind("<Shift-Left>", lambda _e: self._handle_intent(UiIntent.EXPAND_LEFT))
        self.canvas.bind("<Shift-Right>", lambda _e: self._handle_intent(UiIntent.EXPAND_RIGHT))

    def _intent_binding(self, sequence: str, *, intent: str, binding_id: str, modes: tuple[str, ...], text: bool = False) -> None:
        """Bindet *sequence* direkt an ``_handle_intent(intent)`` (häufigster Fall).

        Args:
            sequence: Tk-Tastatursequenz.
            intent: Auszulösender UiIntent.
            binding_id: Eindeutige Binding-ID.
            modes: Erlaubte UI-Modi.
            text: Kürzel auch bei fokussiertem Textfeld aktiv (``allow_when_text_input``).
        """
        self._bind_runtime_shortcut(
            sequence,
            lambda _e, i=intent: self._handle_intent(i),
            binding_id=binding_id,
            intent=intent,
            modes=modes,
            allow_when_text_input=text,
        )

    def _bind_global_shortcuts(self) -> None:
        """Planlisten-/globale Kürzel, Undo/Redo, Einstellungen, Escape/Return/Delete."""
        b, ib = self._bind_runtime_shortcut, self._intent_binding
        ib("<Control-n>", intent=UiIntent.NEW_PLAN, binding_id="global.new", modes=(UI_MODE_GLOBAL, UI_MODE_DIALOG), text=True)
        b("<Control-d>", self._on_duplicate_shortcut, binding_id="global.duplicate", intent=UiIntent.DUPLICATE_SELECTED_PLAN, modes=_G, allow_when_text_input=True)
        b("<F2>", self._on_rename_shortcut, binding_id="global.rename", intent=UiIntent.RENAME_SELECTED_PLAN, modes=_G, allow_when_text_input=True)
        ib("<Control-e>", intent=UiIntent.EXPORT_PDF, binding_id="global.export", modes=_GP, text=True)
        # Früher zusätzlich "<Control-,>" -- semantisch identisch zu <Control-comma>
        # (gleiche binding_signature), vom bw-gui-Binder als Kollision abgelehnt.
        ib("<Control-comma>", intent=UiIntent.OPEN_SETTINGS, binding_id="global.settings.comma", modes=_GP, text=True)
        ib("<Control-z>", intent=UiIntent.UNDO, binding_id="edit.undo", modes=_GP, text=True)
        ib("<Control-y>", intent=UiIntent.REDO, binding_id="edit.redo", modes=_GP, text=True)
        ib("<Control-Shift-r>", intent=UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG, binding_id="debug.runtime.open", modes=_GPD, text=True)
        ib("<Control-Shift-o>", intent=UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE, binding_id="debug.runtime.offline", modes=_GPD, text=True)
        b("<Delete>", self._on_delete_key, binding_id="global.delete", intent=UiIntent.GLOBAL_DELETE, modes=_GP)
        ib("<Escape>", intent=UiIntent.ESCAPE, binding_id="global.escape", modes=_GPD, text=True)
        b("<Return>", self._on_return_key, binding_id="global.return", intent=UiIntent.GLOBAL_RETURN, modes=_GPD, allow_when_text_input=True)
        b("<KP_Enter>", self._on_return_key, binding_id="global.return.numpad", intent=UiIntent.GLOBAL_RETURN_NUMPAD, modes=_GPD, allow_when_text_input=True)

    def _bind_editor_shortcuts(self) -> None:
        """Editor-Kürzel (Raster): Viewport, Lehrertisch, Tischgruppen, Filter, Zwischenablage."""
        ib = self._intent_binding
        ib("<Control-0>", intent=UiIntent.RESET_VIEW, binding_id="viewport.reset", modes=_P)
        ib("<Control-Return>", intent=UiIntent.SET_TEACHER_DESK, binding_id="desk.teacher", modes=_P)
        ib("<Control-KP_Enter>", intent=UiIntent.SET_TEACHER_DESK, binding_id="desk.teacher.numpad", modes=_P)
        ib("<Control-plus>", intent=UiIntent.ZOOM_IN, binding_id="viewport.zoom.in", modes=_P)
        ib("<Control-equal>", intent=UiIntent.ZOOM_IN, binding_id="viewport.zoom.in.equal", modes=_P)
        ib("<Control-KP_Add>", intent=UiIntent.ZOOM_IN, binding_id="viewport.zoom.in.numpad", modes=_P)
        ib("<Control-minus>", intent=UiIntent.ZOOM_OUT, binding_id="viewport.zoom.out", modes=_P)
        ib("<Control-KP_Subtract>", intent=UiIntent.ZOOM_OUT, binding_id="viewport.zoom.out.numpad", modes=_P)
        ib("<Control-t>", intent=UiIntent.OPEN_TABLEGROUP_SETTINGS, binding_id="tablegroup.settings", modes=_P)
        ib("<Control-f>", intent=UiIntent.GRID_SYMBOL_FILTER, binding_id="grid.symbol_filter", modes=_P)
        ib("<Control-Shift-D>", intent=UiIntent.TOGGLE_DOCUMENTATION, binding_id="view.docs.toggle", modes=_P)
        ib("<Control-Shift-d>", intent=UiIntent.TOGGLE_DOCUMENTATION, binding_id="view.docs.toggle.lower", modes=_P)
        ib("<Control-x>", intent=UiIntent.CUT, binding_id="edit.cut", modes=_P, text=True)
        ib("<Control-c>", intent=UiIntent.COPY, binding_id="edit.copy", modes=_P, text=True)
        ib("<Control-v>", intent=UiIntent.PASTE, binding_id="edit.paste", modes=_P, text=True)
        ib("<KeyPress-d>", intent=UiIntent.ADD_SYMBOL, binding_id="desk.add_symbol", modes=_P)

    def _bind_docs_shortcuts(self) -> None:
        """Dokuansicht-Kürzel: Note, Symbol, Löschen, Datumsnavigation, Spalten."""
        b, ib = self._bind_runtime_shortcut, self._intent_binding
        b("<Control-g>", self._on_set_grade_shortcut, binding_id="docs.grade", intent=UiIntent.DOCS_GRADE, modes=_P)
        b("<Control-Shift-S>", self._on_set_symbol_shortcut, binding_id="docs.symbol", intent=UiIntent.DOCS_SYMBOL, modes=_P)
        b("<Control-Shift-s>", self._on_set_symbol_shortcut, binding_id="docs.symbol.lower", intent=UiIntent.DOCS_SYMBOL_LOWER, modes=_P)
        b("<Control-Delete>", self._on_clear_symbol_shortcut, binding_id="docs.clear", intent=UiIntent.DOCS_CLEAR, modes=_P)
        b("<Control-BackSpace>", self._on_clear_symbol_shortcut, binding_id="docs.clear.backspace", intent=UiIntent.DOCS_CLEAR_BACKSPACE, modes=_P)
        b("<Control-h>", self._on_docs_today_shortcut, binding_id="docs.today", intent=UiIntent.DOCS_TODAY, modes=_P)
        b("<Alt-Left>", self._on_docs_prev_date_shortcut, binding_id="docs.prev", intent=UiIntent.DOCS_PREV, modes=_P)
        b("<Alt-Right>", self._on_docs_next_date_shortcut, binding_id="docs.next", intent=UiIntent.DOCS_NEXT, modes=_P)
        ib("<Control-Shift-U>", intent=UiIntent.RENAME_DOCUMENTATION_DATE, binding_id="docs.date.rename", modes=_P)
        ib("<Control-Shift-u>", intent=UiIntent.RENAME_DOCUMENTATION_DATE, binding_id="docs.date.rename.lower", modes=_P)
        ib("<Control-Shift-BackSpace>", intent=UiIntent.DELETE_DOCUMENTATION_DATE, binding_id="docs.date.delete", modes=_P)
        ib("<Control-Shift-N>", intent=UiIntent.ADD_GRADE_COLUMN, binding_id="docs.grade_column.add", modes=_P)
        ib("<Control-Shift-n>", intent=UiIntent.ADD_GRADE_COLUMN, binding_id="docs.grade_column.add.lower", modes=_P)
        ib("<Control-Shift-Delete>", intent=UiIntent.DELETE_GRADE_COLUMN, binding_id="docs.grade_column.delete", modes=_P)

    def _bind_symbol_color_participation_shortcuts(self) -> None:
        """Einbuchstaben-Kürzel für Symbole (eingebaut + eigene), Farbpunkte und Mitarbeit.

        Eigene Doku-Symbole: EINMALIG der gesamte freie Einzelbuchstaben-Raum
        (26 Buchstaben minus ``reserved_symbol_letters()`` -- eingebaute
        Symbol-Kürzel plus feste Systembuchstaben O/S/D, dieselbe Funktion wie
        Validierung und Anlage-Formular). Der Handler löst pro Tastendruck live
        gegen den aktuell offenen Plan auf, kein Rebind bei Planwechsel nötig.
        """
        b = self._bind_runtime_shortcut
        for shortcut, symbol_name in self._shortcut_to_symbol.items():
            if shortcut == SPACE_SHORTCUT:
                continue  # Leertaste: dynamisch aufgelöst, s. unten
            for key in sorted({shortcut, shortcut.upper()}):
                b(
                    f"<KeyPress-{key}>",
                    lambda e, s=symbol_name: self._on_symbol_shortcut(e, s),
                    binding_id=f"symbol.{key}",
                    intent=UiIntent.SYMBOL_SHORTCUT,
                    modes=_P,
                )
        b("<KeyPress-space>", self._on_space_symbol_shortcut, binding_id="symbol.space", intent=UiIntent.SYMBOL_SHORTCUT, modes=_P)

        for letter in sorted(set(string.ascii_uppercase) - reserved_symbol_letters(self.symbol_definitions)):
            for key in (letter, letter.lower()):
                b(
                    f"<KeyPress-{key}>",
                    lambda _e, l=letter: self._on_custom_symbol_shortcut(l),
                    binding_id=f"custom_symbol.{letter.lower()}" + ("" if key == letter else ".lower"),
                    intent=UiIntent.CUSTOM_SYMBOL_SHORTCUT,
                    modes=_P,
                )

        for key, color_key, _label, _hex_color in self.color_palette:
            b(
                f"<KeyPress-{key}>",
                lambda e, ck=color_key: self._on_color_shortcut(e, ck),
                binding_id=f"color.{color_key}",
                intent=UiIntent.COLOR_SHORTCUT,
                modes=_P,
            )

        for keysym, rating in _PARTICIPATION_KEYS:
            b(
                f"<KeyPress-{keysym}>",
                lambda e, r=rating: self._on_participation_rating_shortcut(e, r),
                binding_id=f"participation.{keysym}",
                intent=UiIntent.PARTICIPATION_RATING,
                modes=_P,
            )
