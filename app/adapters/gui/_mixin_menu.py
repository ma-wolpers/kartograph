"""Menüleisten-Mixin für das Kartograph-Hauptfenster.

Stellt die Methoden zum Aufbau der geteilten Menüleiste (Datei, Bearbeiten,
Ansicht) sowie die dazugehörigen Radiobutton-Callbacks für Theme- und
Overlay-Position-Wechsel bereit.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import DOCS_ONLY_INTENTS, GRID_ONLY_INTENTS
from app.adapters.gui.ui_intents import UiIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.menu import MenuItem as SharedMenuItem


class MenuMixin:
    """Mixin: Menüleiste und deren Hilfsmethoden."""

    def _shared_menu_theme_key(self) -> str:
        """Gibt den für die bw_gui-Menükomponente passenden Theme-Schlüssel zurück."""
        if self.theme_key in {"mono_day", "porcelain", "mono_night", "charcoal"}:
            return self.theme_key
        if self.theme_key in {"graphite_core", "blackforge"}:
            return "charcoal"
        return "mono_day"

    def _set_theme_from_menu(self, key: str) -> None:
        """Setzt das Theme aus einem Menü-Radiobutton heraus.

        Args:
            key: Theme-Schlüssel.
        """
        self.theme_var.set(key)
        self._on_theme_changed()

    def _set_details_overlay_position(self, value: str) -> None:
        """Setzt die Tisch-Overlay-Position aus einem Menü-Radiobutton heraus.

        Args:
            value: Positionsstring (``"left"``, ``"right"`` oder ``"bottom"``).
        """
        self.details_overlay_position_var.set(value)
        self._on_details_overlay_position_changed()

    def _set_tablegroup_overlay_position(self, value: str) -> None:
        """Setzt die Tischgruppen-Overlay-Position aus einem Menü-Radiobutton heraus.

        Args:
            value: Positionsstring (``"left"``, ``"right"`` oder ``"bottom"``).
        """
        self.tablegroup_overlay_position_var.set(value)
        self._on_tablegroup_overlay_position_changed()

    def _menu_items_file(self):
        """Liefert die Menüeinträge für das Datei-Menü."""
        return (
            SharedMenuItem(type="command", label="Neu (Strg+N)", command=lambda: self._handle_intent(UiIntent.NEW_PLAN)),
            SharedMenuItem(type="command", label="Plan umbenennen (F2)", command=lambda: self._handle_intent(UiIntent.RENAME_SELECTED_PLAN)),
            SharedMenuItem(type="command", label="Plan loeschen (Entf in Liste)", command=lambda: self._handle_intent(UiIntent.DELETE_SELECTED_PLAN)),
            SharedMenuItem(type="command", label="Plan duplizieren (Strg+D)", command=lambda: self._handle_intent(UiIntent.DUPLICATE_SELECTED_PLAN)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Export PDF (Strg+E)", command=lambda: self._handle_intent(UiIntent.EXPORT_PDF)),
            SharedMenuItem(type="command", label="Für Namenfit exportieren (CSV)", command=lambda: self._handle_intent(UiIntent.EXPORT_NAMENFIT_CSV)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Zur Planliste", command=lambda: self._handle_intent(UiIntent.GO_TO_LIST)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Beenden", command=self.destroy),
        )

    def _menu_items_edit(self):
        """Liefert die Menüeinträge für das Bearbeiten-Menü."""
        return (
            SharedMenuItem(type="command", label="Rueckgaengig (Strg+Z)", command=lambda: self._handle_intent(UiIntent.UNDO)),
            SharedMenuItem(type="command", label="Wiederholen (Strg+Y)", command=lambda: self._handle_intent(UiIntent.REDO)),
            SharedMenuItem(type="command", label="Letzte 5 rueckgaengig", command=lambda: self._handle_intent(UiIntent.UNDO_LAST_FIVE)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Ausschneiden (Strg+X)", command=lambda: self._handle_intent(UiIntent.CUT)),
            SharedMenuItem(type="command", label="Kopieren (Strg+C)", command=lambda: self._handle_intent(UiIntent.COPY)),
            SharedMenuItem(type="command", label="Einfuegen (Strg+V)", command=lambda: self._handle_intent(UiIntent.PASTE)),
        )

    def _menu_items_view(self):
        """Liefert die Menüeinträge für das Ansicht-Menü (Overlays, Debug)."""
        details_position = self.details_overlay_position_var.get()
        tablegroup_position = self.tablegroup_overlay_position_var.get()

        return [
            SharedMenuItem(type="command", label="Sitzplan-Vorschau oeffnen", command=self.open_sitzplan_popup),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="command", label="Dokumentationssicht umschalten (Strg+Shift+D)", command=lambda: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION)),
            SharedMenuItem(type="command", label="Shortcut-Runtime-Debug anzeigen (Strg+Shift+R)", command=lambda: self._handle_intent(UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG)),
            SharedMenuItem(type="command", label="Offline-Simulation umschalten (Strg+Shift+O)", command=lambda: self._handle_intent(UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE)),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="disabled", label="Tisch-Overlay (S:S)"),
            SharedMenuItem(type="radio", label="Links", checked=(details_position == "left"), command=lambda: self._set_details_overlay_position("left")),
            SharedMenuItem(type="radio", label="Rechts", checked=(details_position == "right"), command=lambda: self._set_details_overlay_position("right")),
            SharedMenuItem(type="radio", label="Unten", checked=(details_position == "bottom"), command=lambda: self._set_details_overlay_position("bottom")),
            SharedMenuItem(type="separator"),
            SharedMenuItem(type="disabled", label="Tischgruppen-Overlay"),
            SharedMenuItem(type="radio", label="Links (Tischgruppen)", checked=(tablegroup_position == "left"), command=lambda: self._set_tablegroup_overlay_position("left")),
            SharedMenuItem(type="radio", label="Rechts (Tischgruppen)", checked=(tablegroup_position == "right"), command=lambda: self._set_tablegroup_overlay_position("right")),
            SharedMenuItem(type="radio", label="Unten (Tischgruppen)", checked=(tablegroup_position == "bottom"), command=lambda: self._set_tablegroup_overlay_position("bottom")),
        ]
