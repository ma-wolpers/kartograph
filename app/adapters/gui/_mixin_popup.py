"""Popup-Mixin für das Kartograph-Hauptfenster: Overlay-Anmeldung und Fokus-Erkennung.

Toplevel-Dialoge melden sich im bw-gui-Overlay-Stack an (``OVERLAY_STACK_CONTRACT.md``);
die Anmeldung endet mit dem ``<Destroy>`` des Fensters. Bis 2026-10-15 führte Kartograph
dafür eine eigene ``PopupPolicyRegistry`` samt Scan der sichtbaren Kind-Toplevels
(``tests/test_overlay_gating_tk.py`` hält die Übereinstimmung fest).
"""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime.overlay_stack import OverlayCategory, register_overlay


class PopupMixin:
    """Mixin: Popup-Lebenszyklus und Fokus-Erkennung."""

    def _register_popup_window(self, window: ui.Toplevel, *, blocking_shortcuts: bool = True) -> None:
        """Meldet ein Toplevel-Fenster im bw-gui-Overlay-Stack an (endet mit seinem ``<Destroy>``).

        Args:
            window: Das anzumeldende Toplevel-Fenster.
            blocking_shortcuts: ``True`` (Standard) meldet einen ``MODAL_DIALOG`` an, der die
                Hauptfenster-Kürzel sperrt; ``False`` ein ``NON_MODAL_POPUP``-Werkzeugfenster
                (Snapshots, Symbol-Verwaltung, Shortcut-Debug), das sie nicht sperrt.
        """
        category = OverlayCategory.MODAL_DIALOG if blocking_shortcuts else OverlayCategory.NON_MODAL_POPUP
        register_overlay(window, category, toplevel=window)

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
