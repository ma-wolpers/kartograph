"""Tastaturkürzel-Mixin für das Kartograph-Hauptfenster.

Enthält den bw-gui-``WindowShortcutBinder`` (Registrierung + Runtime-Gating),
den fachlichen Shortcut-Modus und den zentralen Intent-Dispatcher. Die
Bindungstabelle selbst steht in ``_mixin_shortcut_bindings.py``; Symbol-,
Farb- und Mitarbeit-Handler in ``_mixin_edit.py``; der Return-Key-Handler in
``_mixin_selection.py``.
"""

from __future__ import annotations

from typing import Callable

from app.adapters.gui.main_window_constants import DOCS_ONLY_INTENTS, GRID_ONLY_INTENTS, LIST_ACTIVE
from app.adapters.gui.ui_intents import UiIntent
from app.application.shortcut_scope import is_preview_shortcut_scope
from app.core.intents.view_intents import SetEditorSurfaceIntent, ToggleEditorSurfaceIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from bw_libs.ui_contract.keybinding import UI_MODE_GLOBAL, UI_MODE_PREVIEW, KeyBindingDefinition

ensure_bw_gui_on_path()
from bw_gui.runtime import WindowShortcutBinder


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

    def _init_shortcut_binder(self) -> None:
        """Erzeugt den einzigen ``WindowShortcutBinder`` dieses Fensters.

        Der Binder übernimmt Mode-, Text-, Dialog-, Offline- und Modifier-Gating
        sowie die semantische Kollisionsprüfung (bw-gui-Keybinding-Contract);
        Kartograph liefert nur seine Zustandsquellen. Der Grundmodus kommt
        fachlich aus ``AppState`` (``_shortcut_base_mode``), nicht aus der
        Tk-Sichtbarkeit eines Widgets.
        """
        self._shortcut_binder = WindowShortcutBinder(
            self.tk_root,
            registry=self._runtime_shortcuts,
            hsm_contract=self._hsm_contract,
            is_text_input=lambda _widget: self._is_text_input_focused(),
            dialog_open=self._shortcut_dialog_open,
            offline=lambda: bool(self._shortcut_runtime_offline),
            mode_provider=self._shortcut_base_mode,
        )

    def _shortcut_base_mode(self) -> str:
        """Fachlicher Grundmodus für den Binder: PREVIEW im Editor-Scope, sonst GLOBAL."""
        return UI_MODE_PREVIEW if is_preview_shortcut_scope(self._controller.state) else UI_MODE_GLOBAL

    def _shortcut_dialog_open(self) -> bool:
        """Synchronisiert Popup-Sitzungen und meldet, ob ein modus-blockierendes Popup offen ist."""
        self._sync_popup_sessions_from_windows()
        return self._popup_registry.has_mode_blocking_popup()

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
    ) -> KeyBindingDefinition:
        """Registriert ein Kürzel über den bw-gui-Binder (dünne Delegation).

        Args:
            sequence: Tk-Tastatursequenz (Keyboard-Contract von bw-gui).
            handler: Callback, erhält das Tk-Event.
            binding_id: Eindeutige Binding-ID.
            intent: UiIntent-String (muss im HSM-Vertrag bekannt sein).
            modes: Erlaubte UI-Modi.
            allow_when_text_input: Kürzel auch bei fokussiertem Texteingabe-Widget aktiv.
            allow_when_offline: Kürzel auch im Offline-Simulationsmodus aktiv.

        Returns:
            Die registrierte ``KeyBindingDefinition``.
        """
        return self._shortcut_binder.bind(
            sequence,
            handler,
            binding_id=binding_id,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )

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
        if scope in ("grid", "docs"):
            return (
                is_preview_shortcut_scope(self._controller.state)
                and self._editor_surface == scope
                and not self._is_text_input_focused()
            )
        return False

