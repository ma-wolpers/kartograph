"""Shortcut-Handler-Mixin für das Kartograph-Hauptfenster.

Enthält die konkreten Tastatur-Handler-Methoden, die über ``_bind_shortcuts``
(in ShortcutMixin) eingebunden werden. Ausgelagert um ShortcutMixin unter
200 Nicht-Dokumentations-Zeilen zu halten.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import LIST_ACTIVE
from app.adapters.gui.ui_intents import UiIntent
from app.core.intents.session_intents import NavigateSessionIntent
from app.core.usecases.v4.custom_symbol_usecases import resolve_custom_symbol_shortcut


class ShortcutHandlersMixin:
    """Mixin: Konkrete Tastatur-Handler-Implementierungen (F2, Entf, Alt-Pfeile, etc.)."""

    def _on_rename_shortcut(self, _event) -> str | None:
        """Handler für F2: umbenennen nur in der Listenansicht.

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if self.interaction_mode != LIST_ACTIVE:
            return None
        return self._handle_intent(UiIntent.RENAME_SELECTED_PLAN)

    def _on_duplicate_shortcut(self, _event) -> str | None:
        """Handler für Ctrl+D: duplizieren nur in der Listenansicht.

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if self.interaction_mode != LIST_ACTIVE:
            return None
        return self._handle_intent(UiIntent.DUPLICATE_SELECTED_PLAN)

    def _on_delete_key(self, _event) -> str | None:
        """Handler für Entf: kontextabhängiges Löschen in Liste, Docs oder Raster.

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if self.interaction_mode == LIST_ACTIVE:
            return self._handle_intent(UiIntent.DELETE_SELECTED_PLAN)
        if self._editor_surface == "docs":
            if self._is_text_input_focused():
                return None
            self.clear_selected_documentation_symbol()
            return "break"
        return self._handle_intent(UiIntent.DELETE_DESK)

    def _on_set_grade_shortcut(self, _event) -> str | None:
        """Handler für Ctrl+G: Noten-Inline-Editor in der Docs-Ansicht öffnen.

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        self.set_selected_documentation_grade_dialog()
        return "break"

    def _on_set_symbol_shortcut(self, _event) -> str | None:
        """Handler für Ctrl+Shift+S: Symbol-Dialog in der Docs-Ansicht öffnen.

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        self.set_selected_documentation_symbol_dialog()
        return "break"

    def _on_clear_symbol_shortcut(self, _event) -> str | None:
        """Handler für Ctrl+Entf / Ctrl+Backspace: Symbol der Doku-Zelle löschen.

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        self.clear_selected_documentation_symbol()
        return "break"

    def _on_docs_prev_date_shortcut(self, _event) -> str | None:
        """Handler für Alt+Links: zum vorigen Dokumentationsdatum springen (v4: NavigateSessionIntent).

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        if not self._doc_dates:
            return "break"
        self._select_doc_fixed_column(None)
        self._controller.dispatch(NavigateSessionIntent(direction="prev"))
        return "break"

    def _on_docs_next_date_shortcut(self, _event) -> str | None:
        """Handler für Alt+Rechts: zum nächsten Dokumentationsdatum springen (v4: NavigateSessionIntent).

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        if not self._doc_dates:
            return "break"
        self._select_doc_fixed_column(None)
        self._controller.dispatch(NavigateSessionIntent(direction="next"))
        return "break"

    def _on_docs_today_shortcut(self, _event) -> str | None:
        """Handler für Ctrl+H: heutiges Datum in der Docs-Ansicht ansteuern.

        Args:
            _event: Tkinter-Tastaturereignis (unbenutzt).
        """
        if not self._shortcut_scope_allows("docs"):
            return None
        self.select_today_documentation_date()
        return "break"

    def _on_custom_symbol_shortcut(self, letter: str) -> str | None:
        """Handler für einen einzelnen Buchstaben: eigenes Doku-Symbol togglen.

        Löst *letter* live gegen die eigenen Symbole des AKTUELL offenen Plans
        auf (``resolve_custom_symbol_shortcut()``) — kein Rebind bei
        Planwechsel nötig, derselbe physische Tastenraum wird einmalig in
        ``_mixin_shortcuts.py::_bind_shortcuts()`` gebunden (nur die aktuell
        freien Buchstaben, s. ``reserved_symbol_letters()``). In der
        Dokuansicht wirkt der Toggle auf die dort gewählte Datumsspalte
        (``_toggle_documentation_symbol``); im Raster (kein Datums-Wähler)
        auf das heutige Datum (``_toggle_documentation_symbol_today_grid``,
        analog zu eingebauten Doku-Symbolen in ``_on_symbol_shortcut``,
        ``_mixin_edit.py`` — eigene Symbole sind immer documentation-only).

        Args:
            letter: Der gedrückte Großbuchstabe (z. B. ``"K"``).
        """
        if not self._shortcut_scope_allows("docs") and not self._shortcut_scope_allows("grid"):
            return None
        if not self.current_plan or not self.current_plan_path:
            return None
        custom = resolve_custom_symbol_shortcut(self.current_plan, letter)
        if custom is None:
            return None
        if self._editor_surface == "docs":
            self._toggle_documentation_symbol(custom.id)
        elif self._editor_surface == "grid":
            self._toggle_documentation_symbol_today_grid(custom.id)
        else:
            return None
        return "break"
