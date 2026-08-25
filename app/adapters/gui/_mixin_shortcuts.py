"""Tastaturkürzel-Mixin für das Kartograph-Hauptfenster.

Enthält Registrierung und Auswertung aller Runtime-Shortcuts sowie den
zentralen Intent-Dispatcher. Symbol- und Farb-Shortcuts sind in
``_mixin_edit.py`` implementiert; der Return-Key-Handler in ``_mixin_selection.py``.
"""

from __future__ import annotations

import string
from typing import Callable

from app.adapters.gui.main_window_constants import DOCS_ONLY_INTENTS, GRID_ONLY_INTENTS, LIST_ACTIVE
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.custom_symbol_validation import RESERVED_CTRL_SHIFT_LETTERS
from app.core.intents.view_intents import SetEditorSurfaceIntent, ToggleEditorSurfaceIntent
from bw_libs.ui_contract.keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRuntimeContext,
)


class ShortcutMixin:
    """Mixin: Shortcut-Registrierung, Runtime-Auswertung und Intent-Dispatch."""

    def _build_ui_action_registry(self) -> dict[str, Callable[[], object]]:
        """Baut die Zuordnung von UiIntent-String zu auszuführender GUI-Aktion.

        Ersetzt die frühere if/elif-Kette in ``MainWindowUiIntentController``
        durch eine echte Registry; neue Intents werden per Dict-Eintrag statt
        per Kettenerweiterung angebunden. Alle Werte sind Lambdas (statt
        direkter Methodenreferenzen), damit die Methodenauflösung wie zuvor
        erst beim tatsächlichen Dispatch erfolgt, nicht schon beim Bauen der
        Registry — ein einzelner (vorbestehender) Methodenname ohne
        Implementierung darf den Programmstart nicht verhindern.
        """
        return {
            UiIntent.LIST_OPEN_SELECTED: lambda: self.open_selected_plan_from_list(),
            UiIntent.NEW_PLAN: lambda: self.create_new_plan_dialog(),
            UiIntent.RENAME_SELECTED_PLAN: lambda: self.rename_selected_plan_dialog(),
            UiIntent.DELETE_SELECTED_PLAN: lambda: self.delete_selected_plan_dialog(),
            UiIntent.DUPLICATE_SELECTED_PLAN: lambda: self.duplicate_selected_plan_dialog(),
            UiIntent.ARCHIVE_SELECTED_PLAN: lambda: self.archive_or_restore_selected_plan_dialog(),
            UiIntent.OPEN_SETTINGS: lambda: self.open_settings_dialog(),
            UiIntent.DELETE_DESK: lambda: self.delete_selected_desk(),
            UiIntent.SET_TEACHER_DESK: lambda: self.set_selected_as_teacher_desk(),
            UiIntent.ADD_SYMBOL: lambda: self.add_symbol_to_selected_desk_dialog(),
            UiIntent.OPEN_TABLEGROUP_SETTINGS: lambda: self.open_tablegroup_settings_overlay(),
            UiIntent.GRID_SYMBOL_FILTER: lambda: self.open_grid_symbol_filter_dialog(),
            UiIntent.MANAGE_SYMBOLS: lambda: self.open_symbol_management_dialog(),
            UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG: lambda: self.open_shortcut_runtime_debug_dialog(),
            UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE: lambda: self.toggle_shortcut_runtime_offline(),
            UiIntent.ESCAPE: lambda: self.handle_escape(),
            UiIntent.CONFIRM_SELECTION: lambda: self._confirm_selected_desk(),
            UiIntent.MOVE_UP: lambda: self.move_selection(0, -1),
            UiIntent.MOVE_DOWN: lambda: self.move_selection(0, 1),
            UiIntent.MOVE_LEFT: lambda: self.move_selection(-1, 0),
            UiIntent.MOVE_RIGHT: lambda: self.move_selection(1, 0),
            UiIntent.ZOOM_IN: lambda: self.zoom_in(),
            UiIntent.ZOOM_OUT: lambda: self.zoom_out(),
            UiIntent.RESET_VIEW: lambda: self.reset_viewport(),
            UiIntent.GO_TO_LIST: lambda: self._return_to_plan_list(),
            UiIntent.VIEW_GRID: lambda: self._controller.dispatch(SetEditorSurfaceIntent(surface="grid")),
            UiIntent.VIEW_DOCUMENTATION: lambda: self._controller.dispatch(SetEditorSurfaceIntent(surface="documentation")),
            UiIntent.TOGGLE_DOCUMENTATION: lambda: self._controller.dispatch(ToggleEditorSurfaceIntent()),
            UiIntent.RENAME_DOCUMENTATION_DATE: lambda: self.rename_selected_documentation_date_dialog(),
            UiIntent.DELETE_DOCUMENTATION_DATE: lambda: self.delete_selected_documentation_date_dialog(),
            UiIntent.ADD_GRADE_COLUMN: lambda: self.add_grade_column_dialog(),
            UiIntent.DELETE_GRADE_COLUMN: lambda: self.delete_grade_column_dialog(),
            UiIntent.TOGGLE_THEME: lambda: self.toggle_theme(),
            UiIntent.EXPORT_PDF: lambda: self.export_plan_pdf_dialog(),
            UiIntent.EXPORT_NAMENFIT_CSV: lambda: self.export_plan_namenfit_csv_dialog(),
            UiIntent.EXPORT_STUDENT_PNGS_ZIP: lambda: self.export_plan_student_pngs_dialog(),
            UiIntent.UNDO: lambda: self.undo_last_change(),
            UiIntent.REDO: lambda: self.redo_last_change(),
            UiIntent.UNDO_LAST_FIVE: lambda: self.undo_last_five_changes(),
            UiIntent.COPY: lambda: self.copy_selection(),
            UiIntent.CUT: lambda: self.cut_selection(),
            UiIntent.PASTE: lambda: self.paste_selection(),
            UiIntent.EXPAND_UP: lambda: self.expand_selection(0, -1),
            UiIntent.EXPAND_DOWN: lambda: self.expand_selection(0, 1),
            UiIntent.EXPAND_LEFT: lambda: self.expand_selection(-1, 0),
            UiIntent.EXPAND_RIGHT: lambda: self.expand_selection(1, 0),
        }

    def _bind_shortcuts(self) -> None:
        """Bindet alle globalen und modus-spezifischen Tastaturkürzel an den Runtime-Resolver."""
        self._bind_runtime_shortcut("<Control-n>", lambda _e: self._handle_intent(UiIntent.NEW_PLAN), binding_id="global.new", intent=UiIntent.NEW_PLAN, modes=(UI_MODE_GLOBAL, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-d>", self._on_duplicate_shortcut, binding_id="global.duplicate", intent=UiIntent.DUPLICATE_SELECTED_PLAN, modes=(UI_MODE_GLOBAL,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<F2>", self._on_rename_shortcut, binding_id="global.rename", intent=UiIntent.RENAME_SELECTED_PLAN, modes=(UI_MODE_GLOBAL,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-e>", lambda _e: self._handle_intent(UiIntent.EXPORT_PDF), binding_id="global.export", intent=UiIntent.EXPORT_PDF, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-comma>", lambda _e: self._handle_intent(UiIntent.OPEN_SETTINGS), binding_id="global.settings.comma", intent=UiIntent.OPEN_SETTINGS, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-,>", lambda _e: self._handle_intent(UiIntent.OPEN_SETTINGS), binding_id="global.settings.comma.alt", intent=UiIntent.OPEN_SETTINGS, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-0>", lambda _e: self._handle_intent(UiIntent.RESET_VIEW), binding_id="viewport.reset", intent=UiIntent.RESET_VIEW, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Return>", lambda _e: self._handle_intent(UiIntent.SET_TEACHER_DESK), binding_id="desk.teacher", intent=UiIntent.SET_TEACHER_DESK, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-KP_Enter>", lambda _e: self._handle_intent(UiIntent.SET_TEACHER_DESK), binding_id="desk.teacher.numpad", intent=UiIntent.SET_TEACHER_DESK, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-plus>", lambda _e: self._handle_intent(UiIntent.ZOOM_IN), binding_id="viewport.zoom.in", intent=UiIntent.ZOOM_IN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-equal>", lambda _e: self._handle_intent(UiIntent.ZOOM_IN), binding_id="viewport.zoom.in.equal", intent=UiIntent.ZOOM_IN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-KP_Add>", lambda _e: self._handle_intent(UiIntent.ZOOM_IN), binding_id="viewport.zoom.in.numpad", intent=UiIntent.ZOOM_IN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-minus>", lambda _e: self._handle_intent(UiIntent.ZOOM_OUT), binding_id="viewport.zoom.out", intent=UiIntent.ZOOM_OUT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-KP_Subtract>", lambda _e: self._handle_intent(UiIntent.ZOOM_OUT), binding_id="viewport.zoom.out.numpad", intent=UiIntent.ZOOM_OUT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-z>", lambda _e: self._handle_intent(UiIntent.UNDO), binding_id="edit.undo", intent=UiIntent.UNDO, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-y>", lambda _e: self._handle_intent(UiIntent.REDO), binding_id="edit.redo", intent=UiIntent.REDO, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-t>", lambda _e: self._handle_intent(UiIntent.OPEN_TABLEGROUP_SETTINGS), binding_id="tablegroup.settings", intent=UiIntent.OPEN_TABLEGROUP_SETTINGS, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-f>", lambda _e: self._handle_intent(UiIntent.GRID_SYMBOL_FILTER), binding_id="grid.symbol_filter", intent=UiIntent.GRID_SYMBOL_FILTER, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-D>", lambda _e: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION), binding_id="view.docs.toggle", intent=UiIntent.TOGGLE_DOCUMENTATION, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-d>", lambda _e: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION), binding_id="view.docs.toggle.lower", intent=UiIntent.TOGGLE_DOCUMENTATION, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-r>", lambda _e: self._handle_intent(UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG), binding_id="debug.runtime.open", intent=UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-Shift-o>", lambda _e: self._handle_intent(UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE), binding_id="debug.runtime.offline", intent=UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-g>", self._on_set_grade_shortcut, binding_id="docs.grade", intent=UiIntent.DOCS_GRADE, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-S>", self._on_set_symbol_shortcut, binding_id="docs.symbol", intent=UiIntent.DOCS_SYMBOL, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-s>", self._on_set_symbol_shortcut, binding_id="docs.symbol.lower", intent=UiIntent.DOCS_SYMBOL_LOWER, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Delete>", self._on_clear_symbol_shortcut, binding_id="docs.clear", intent=UiIntent.DOCS_CLEAR, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-BackSpace>", self._on_clear_symbol_shortcut, binding_id="docs.clear.backspace", intent=UiIntent.DOCS_CLEAR_BACKSPACE, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-h>", self._on_docs_today_shortcut, binding_id="docs.today", intent=UiIntent.DOCS_TODAY, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Alt-Left>", self._on_docs_prev_date_shortcut, binding_id="docs.prev", intent=UiIntent.DOCS_PREV, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Alt-Right>", self._on_docs_next_date_shortcut, binding_id="docs.next", intent=UiIntent.DOCS_NEXT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-U>", lambda _e: self._handle_intent(UiIntent.RENAME_DOCUMENTATION_DATE), binding_id="docs.date.rename", intent=UiIntent.RENAME_DOCUMENTATION_DATE, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-u>", lambda _e: self._handle_intent(UiIntent.RENAME_DOCUMENTATION_DATE), binding_id="docs.date.rename.lower", intent=UiIntent.RENAME_DOCUMENTATION_DATE, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-BackSpace>", lambda _e: self._handle_intent(UiIntent.DELETE_DOCUMENTATION_DATE), binding_id="docs.date.delete", intent=UiIntent.DELETE_DOCUMENTATION_DATE, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-N>", lambda _e: self._handle_intent(UiIntent.ADD_GRADE_COLUMN), binding_id="docs.grade_column.add", intent=UiIntent.ADD_GRADE_COLUMN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-n>", lambda _e: self._handle_intent(UiIntent.ADD_GRADE_COLUMN), binding_id="docs.grade_column.add.lower", intent=UiIntent.ADD_GRADE_COLUMN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-Delete>", lambda _e: self._handle_intent(UiIntent.DELETE_GRADE_COLUMN), binding_id="docs.grade_column.delete", intent=UiIntent.DELETE_GRADE_COLUMN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-x>", lambda _e: self._handle_intent(UiIntent.CUT), binding_id="edit.cut", intent=UiIntent.CUT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-c>", lambda _e: self._handle_intent(UiIntent.COPY), binding_id="edit.copy", intent=UiIntent.COPY, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-v>", lambda _e: self._handle_intent(UiIntent.PASTE), binding_id="edit.paste", intent=UiIntent.PASTE, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Delete>", self._on_delete_key, binding_id="global.delete", intent=UiIntent.GLOBAL_DELETE, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Escape>", lambda _e: self._handle_intent(UiIntent.ESCAPE), binding_id="global.escape", intent=UiIntent.ESCAPE, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Return>", self._on_return_key, binding_id="global.return", intent=UiIntent.GLOBAL_RETURN, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<KP_Enter>", self._on_return_key, binding_id="global.return.numpad", intent=UiIntent.GLOBAL_RETURN_NUMPAD, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)

        self.canvas.bind("<Up>", lambda _e: self._handle_intent(UiIntent.MOVE_UP))
        self.canvas.bind("<Down>", lambda _e: self._handle_intent(UiIntent.MOVE_DOWN))
        self.canvas.bind("<Left>", lambda _e: self._handle_intent(UiIntent.MOVE_LEFT))
        self.canvas.bind("<Right>", lambda _e: self._handle_intent(UiIntent.MOVE_RIGHT))
        self.canvas.bind("<Shift-Up>", lambda _e: self._handle_intent(UiIntent.EXPAND_UP))
        self.canvas.bind("<Shift-Down>", lambda _e: self._handle_intent(UiIntent.EXPAND_DOWN))
        self.canvas.bind("<Shift-Left>", lambda _e: self._handle_intent(UiIntent.EXPAND_LEFT))
        self.canvas.bind("<Shift-Right>", lambda _e: self._handle_intent(UiIntent.EXPAND_RIGHT))

        for shortcut, symbol_name in self._shortcut_to_symbol.items():
            self.bind_all(f"<KeyPress-{shortcut}>", lambda event, s=symbol_name: self._on_symbol_shortcut(event, s), add="+")
            self.bind_all(f"<KeyPress-{shortcut.upper()}>", lambda event, s=symbol_name: self._on_symbol_shortcut(event, s), add="+")

        # Eigene Doku-Symbole: EINMALIG der gesamte freie Ctrl+Shift+<Buchstabe>-
        # Tastenraum gebunden (26 Buchstaben minus die 6 fest belegten Systemkuerzel,
        # RESERVED_CTRL_SHIFT_LETTERS aus custom_symbol_validation.py -- einzige
        # Quelle der Wahrheit fuer beide Seiten). Der Handler loest pro Tastendruck
        # live gegen den AKTUELL offenen Plan auf (resolve_custom_symbol_shortcut()),
        # kein Rebind bei Planwechsel noetig.
        for letter in sorted(set(string.ascii_uppercase) - RESERVED_CTRL_SHIFT_LETTERS):
            self._bind_runtime_shortcut(
                f"<Control-Shift-{letter}>",
                lambda _e, l=letter: self._on_custom_symbol_shortcut(l),
                binding_id=f"custom_symbol.{letter.lower()}",
                intent=UiIntent.CUSTOM_SYMBOL_SHORTCUT,
                modes=(UI_MODE_PREVIEW,),
                allow_when_text_input=False,
            )

        for key, _color_key, _label, _hex_color in self.color_palette:
            self.bind_all(f"<KeyPress-{key}>", lambda event, ck=_color_key: self._on_color_shortcut(event, ck), add="+")

        self.bind_all("<KeyPress-space>", self._on_attendance_shortcut, add="+")

        self.bind_all("<KeyPress-plus>", lambda e: self._on_participation_rating_shortcut(e, "+"), add="+")
        self.bind_all("<KeyPress-KP_Add>", lambda e: self._on_participation_rating_shortcut(e, "+"), add="+")
        self.bind_all("<KeyPress-minus>", lambda e: self._on_participation_rating_shortcut(e, "-"), add="+")
        self.bind_all("<KeyPress-KP_Subtract>", lambda e: self._on_participation_rating_shortcut(e, "-"), add="+")
        self.bind_all("<KeyPress-o>", lambda e: self._on_participation_rating_shortcut(e, "o"), add="+")
        self.bind_all("<KeyPress-s>", lambda e: self._on_participation_rating_shortcut(e, "☆"), add="+")
        self._bind_runtime_shortcut("<KeyPress-d>", lambda _e: self._handle_intent(UiIntent.ADD_SYMBOL), binding_id="desk.add_symbol", intent=UiIntent.ADD_SYMBOL, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)

    def _register_runtime_shortcut(
        self,
        *,
        binding_id: str,
        sequence: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
    ) -> KeyBindingDefinition:
        """Validiert den Intent und registriert einen Runtime-Shortcut in der Registry.

        Args:
            binding_id: Eindeutige Binding-ID.
            sequence: Tkinter-Event-Sequenz.
            intent: UiIntent-String (muss im HSM-Vertrag bekannt sein).
            modes: Erlaubte UI-Modi.
            allow_when_text_input: Shortcut auch bei fokussiertem Texteingabe-Widget aktiv.
            allow_when_offline: Shortcut auch im Offline-Simulationsmodus aktiv.

        Returns:
            Die registrierte KeyBindingDefinition.
        """
        intent_ok, _intent_reason = self._hsm_contract.validate_intent(intent)
        if not intent_ok:
            raise ValueError(f"Unknown runtime shortcut intent: {intent}")
        definition = KeyBindingDefinition(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )
        self._runtime_shortcuts.register(definition)
        return definition

    def _build_runtime_context(self, event=None) -> KeybindingRuntimeContext:
        """Ermittelt den aktuellen Runtime-Kontext für die Shortcut-Auswertung.

        Args:
            event: Optionales Tkinter-Event (wird derzeit nicht ausgewertet).

        Returns:
            Aktueller KeybindingRuntimeContext.
        """
        self._sync_popup_sessions_from_windows()
        text_input_focused = self._is_text_input_focused()
        dialog_open = self._popup_registry.has_mode_blocking_popup()
        offline = bool(self._shortcut_runtime_offline)

        if offline:
            active_mode = UI_MODE_OFFLINE
        elif dialog_open:
            active_mode = UI_MODE_DIALOG
        elif text_input_focused:
            active_mode = UI_MODE_EDITOR
        elif self.editor_view.winfo_ismapped():
            active_mode = UI_MODE_PREVIEW
        else:
            active_mode = UI_MODE_GLOBAL

        return KeybindingRuntimeContext(
            active_mode=active_mode,
            offline=offline,
            text_input_focused=text_input_focused,
            dialog_open=dialog_open,
        )

    def _bind_runtime_shortcut(
        self,
        sequence: str,
        handler,
        *,
        binding_id: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
    ) -> None:
        """Registriert einen Shortcut und umhüllt den Handler mit Runtime-Prüfung.

        Args:
            sequence: Tkinter-Event-Sequenz.
            handler: Auszuführende Callback-Funktion.
            binding_id: Eindeutige Binding-ID.
            intent: UiIntent-String.
            modes: Erlaubte UI-Modi.
            allow_when_text_input: Shortcut auch bei fokussiertem Texteingabe-Widget aktiv.
            allow_when_offline: Shortcut auch im Offline-Simulationsmodus aktiv.
        """
        definition = self._register_runtime_shortcut(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )

        def _wrapped(event):
            context = self._build_runtime_context(event)
            can_execute, _reason = self._runtime_shortcuts.evaluate_runtime(definition, context)
            if not can_execute:
                return None
            return handler(event)

        self.bind(sequence, _wrapped)

    def _handle_intent(self, intent: str) -> str | None:
        """Leitet einen Intent an den UiIntentController weiter und trackt das Ergebnis.

        Args:
            intent: UiIntent-String.

        Returns:
            Rückgabewert des Controllers oder None bei blockiertem Intent.
        """
        intent_ok, intent_reason = self._hsm_contract.validate_intent(intent)
        if not intent_ok:
            self.status_var.set(f"Unbekannter Intent blockiert: {intent_reason}")
            self._record_laufkern_intent_dispatch(intent, success=False)
            return None

        if intent in GRID_ONLY_INTENTS and not self._shortcut_scope_allows("grid"):
            self._record_laufkern_intent_dispatch(intent, success=False)
            return None
        if intent in DOCS_ONLY_INTENTS and not self._shortcut_scope_allows("docs"):
            self._record_laufkern_intent_dispatch(intent, success=False)
            return None

        handler = self._ui_action_registry.get(intent)
        try:
            result = None
            if handler is not None:
                handler()
                result = "break"
        except Exception:
            self._record_laufkern_intent_dispatch(intent, success=False)
            raise

        self._record_laufkern_intent_dispatch(intent, success=True)
        return result

    def _shortcut_scope_allows(self, scope: str) -> bool:
        """Prüft, ob der angegebene Shortcut-Scope im aktuellen UI-Zustand erlaubt ist.

        Args:
            scope: Einer von ``"global"``, ``"list"``, ``"grid"``, ``"docs"``.

        Returns:
            True wenn der Scope aktiv und nicht blockiert ist.
        """
        if scope == "global":
            return True
        if scope == "list":
            return self.interaction_mode == LIST_ACTIVE
        if scope == "grid":
            return self.editor_view.winfo_ismapped() and self._editor_surface == "grid" and not self._is_text_input_focused()
        if scope == "docs":
            return self.editor_view.winfo_ismapped() and self._editor_surface == "docs" and not self._is_text_input_focused()
        return False

