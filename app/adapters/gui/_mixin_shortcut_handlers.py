"""Shortcut-Handler-Mixin für das Kartograph-Hauptfenster.

Enthält die konkreten Tastatur-Handler-Methoden, die über ``_bind_shortcuts``
(in ShortcutMixin) eingebunden werden. Ausgelagert um ShortcutMixin unter
200 Nicht-Dokumentations-Zeilen zu halten.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import LIST_ACTIVE
from app.adapters.gui.ui_intents import UiIntent
from app.core.intents.session_intents import NavigateSessionIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult


class ShortcutHandlersMixin:
    """Mixin: Konkrete Tastatur-Handler-Implementierungen (F2, Entf, Alt-Pfeile, etc.)."""

    def _on_rename_shortcut(self, _event) -> EventResult | None:
        """Handler für F2: umbenennen nur in der Listenansicht.

        Args:
            _event: bw-gui-``KeyEvent`` (unbenutzt).
        """
        if self.interaction_mode != LIST_ACTIVE:
            return None
        return self._handle_intent(UiIntent.RENAME_SELECTED_PLAN)

    def _on_duplicate_shortcut(self, _event) -> EventResult | None:
        """Handler für Ctrl+D: duplizieren nur in der Listenansicht.

        Args:
            _event: bw-gui-``KeyEvent`` (unbenutzt).
        """
        if self.interaction_mode != LIST_ACTIVE:
            return None
        return self._handle_intent(UiIntent.DUPLICATE_SELECTED_PLAN)

    def _on_delete_key(self, _event) -> EventResult | None:
        """Handler für Entf: kontextabhängiges Löschen in Liste, Docs oder Raster.

        Args:
            _event: bw-gui-``KeyEvent`` (unbenutzt).
        """
        if self.interaction_mode == LIST_ACTIVE:
            return self._handle_intent(UiIntent.DELETE_SELECTED_PLAN)
        if self._editor_surface == "docs":
            if self._is_text_input_focused():
                return None
            self.clear_selected_documentation_symbol()
            return EventResult.HANDLED
        return self._handle_intent(UiIntent.DELETE_DESK)

    def _on_clear_symbol_shortcut(self, _event) -> EventResult | None:
        """Handler für Ctrl+Entf / Ctrl+Backspace: Symbol der Doku-Zelle löschen.

        Args:
            _event: bw-gui-``KeyEvent`` (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        self.clear_selected_documentation_symbol()
        return EventResult.HANDLED

    def _on_docs_prev_date_shortcut(self, _event) -> EventResult | None:
        """Handler für Alt+Links: zum vorigen Dokumentationsdatum springen (v4: NavigateSessionIntent).

        Args:
            _event: bw-gui-``KeyEvent`` (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        if not self._doc_dates:
            return EventResult.HANDLED
        self._select_doc_nondate_column(None)
        self._controller.dispatch(NavigateSessionIntent(direction="prev"))
        return EventResult.HANDLED

    def _on_docs_next_date_shortcut(self, _event) -> EventResult | None:
        """Handler für Alt+Rechts: zum nächsten Dokumentationsdatum springen (v4: NavigateSessionIntent).

        Args:
            _event: bw-gui-``KeyEvent`` (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        if not self._doc_dates:
            return EventResult.HANDLED
        self._select_doc_nondate_column(None)
        self._controller.dispatch(NavigateSessionIntent(direction="next"))
        return EventResult.HANDLED
