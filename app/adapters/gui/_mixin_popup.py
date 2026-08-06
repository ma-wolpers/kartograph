"""Popup-Tracking-Mixin für das Kartograph-Hauptfenster.

Verwaltet die Registrierung, Synchronisation und Schließung von Toplevel-Dialogen
in der PopupPolicyRegistry und stellt Hilfsmethoden zur Fokus-Erkennung bereit.
"""

from __future__ import annotations

import time

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui


class PopupMixin:
    """Mixin: Popup-Lebenszyklus und Fokus-Erkennung."""

    def _track_popup_window(self, window: ui.Toplevel, *, policy_id: str = "dialog.modal") -> None:
        """Registriert ein Toplevel-Fenster in der PopupPolicyRegistry.

        Args:
            window: Das zu registrierende Toplevel-Fenster.
            policy_id: Policy-Bezeichner (z. B. ``"dialog.modal"`` oder ``"dialog.non_blocking"``).
        """
        popup_id = str(window)
        if popup_id in self._tracked_popup_ids:
            return
        self._popup_registry.open_popup(popup_id=popup_id, title=str(window.title() or ""), policy_id=policy_id)
        self._tracked_popup_ids.add(popup_id)

    def _run_modal_dialog_call(self, title: str, callback):
        """Führt einen nativen Dateidialog unter Popup-Tracking aus.

        Öffnet und schließt eine synthetische Popup-Session um den nativen Dialog,
        damit der UI-Modus korrekt auf ``"dialog.modal"`` gesetzt bleibt.

        Args:
            title: Anzeigename des Dialogs (wird als Popup-ID-Bestandteil genutzt).
            callback: Callable, der den nativen Dialog aufruft und dessen Rückgabe liefert.

        Returns:
            Rückgabewert des nativen Dialogs.
        """
        popup_id = f"dialog.native::{title}::{time.perf_counter_ns()}"
        self._popup_registry.open_popup(popup_id=popup_id, title=title, policy_id="dialog.modal")
        self._tracked_popup_ids.add(popup_id)
        try:
            return callback()
        finally:
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)

    def _sync_popup_sessions_from_windows(self) -> None:
        """Gleicht die Popup-Registry mit den tatsächlich sichtbaren Toplevel-Fenstern ab.

        Neue sichtbare Fenster werden registriert, geschlossene Fenster aus der
        Registry entfernt.
        """
        visible_popup_ids: set[str] = set()
        for child in self.winfo_children():
            if not isinstance(child, ui.Toplevel):
                continue
            try:
                if not int(child.winfo_exists()):
                    continue
                if str(child.state()).lower() == "withdrawn":
                    continue
            except Exception:
                continue

            popup_id = str(child)
            visible_popup_ids.add(popup_id)
            if popup_id in self._tracked_popup_ids:
                continue
            policy_id = "dialog.non_blocking" if bool(getattr(child, "_bw_menu_popup", False)) else "dialog.modal"
            self._popup_registry.open_popup(popup_id=popup_id, title=str(child.title() or ""), policy_id=policy_id)
            self._tracked_popup_ids.add(popup_id)

        stale_ids = self._tracked_popup_ids - visible_popup_ids
        for popup_id in tuple(stale_ids):
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)

    def _is_text_input_focused(self) -> bool:
        """Prüft, ob ein Texteingabe-Widget oder ein modaler Dialog den Fokus hält.

        Returns:
            True wenn ein Entry, Text, Combobox, Toplevel-Dialog oder das
            Tischgruppen-Overlay fokussiert ist.
        """
        focused_widget = self.focus_get()
        if focused_widget is None:
            return False

        widget_class = str(focused_widget.winfo_class())
        if widget_class in {"Entry", "TEntry", "Text", "Spinbox", "Listbox", "TCombobox", "Combobox"}:
            return True

        if self._is_tablegroup_overlay_focused():
            return True

        focused_toplevel = focused_widget.winfo_toplevel()
        if isinstance(focused_toplevel, ui.Toplevel) and focused_toplevel is not self.tk_root:
            return True

        return False

    def _is_name_entry_focused(self) -> bool:
        """Prüft, ob eines der Namenseingabefelder den Fokus hält.

        Returns:
            True wenn ``name_entry`` oder ``last_name_entry`` fokussiert ist.
        """
        focus = self.focus_get()
        return focus == self.name_entry or focus == self.last_name_entry

    def _is_tablegroup_overlay_focused(self) -> bool:
        """Prüft, ob das Tischgruppen-Overlay oder eines seiner Kinder den Fokus hält.

        Returns:
            True wenn das Overlay existiert und der Fokus darin liegt.
        """
        if not self._tablegroup_overlay or not self._tablegroup_overlay.winfo_exists():
            return False
        focused_widget = self.focus_get()
        if focused_widget is None:
            return False
        focused_path = str(focused_widget)
        return focused_path.startswith(str(self._tablegroup_overlay))
