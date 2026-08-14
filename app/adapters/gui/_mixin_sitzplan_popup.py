"""Sitzplan-Vorschau-Popup-Mixin für das Kartograph-Hauptfenster."""

from __future__ import annotations

from app.adapters.gui._sitzplan_popup import SitzplanPopup
from app.core.domain.models_v4 import SeatingPlan


class SitzplanPopupMixin:
    """Mixin: Sitzplan-Vorschau-Popup öffnen, debounced aktualisieren und schließen."""

    def _init_sitzplan_popup_state(self) -> None:
        """Initialisiert den Popup-Zustand (im __init__ des Hauptfensters aufrufen)."""
        self._sitzplan_popup: SitzplanPopup | None = None
        self._sitzplan_popup_after_id: str | None = None
        self._sitzplan_popup_pending_plan: SeatingPlan | None = None
        self._sitzplan_popup_pending_theme: str = "mono_day"
        self._sitzplan_popup_pending_fmt: str = "Vorname Nachname"
        self._sitzplan_popup_pending_disambiguate: bool = False

    def open_sitzplan_popup(self) -> None:
        """Öffnet das Vorschaufenster oder bringt es bei erneutem Aufruf in den Vordergrund."""
        if self._sitzplan_popup is not None:
            try:
                if self._sitzplan_popup.window.winfo_exists():
                    self._sitzplan_popup.window.lift()
                    self._sitzplan_popup.window.focus_set()
                    return
            except Exception:
                pass
            self._sitzplan_popup = None

        popup = SitzplanPopup(self, theme_key=self.theme_key, name_format=self.name_format)
        popup.window.protocol("WM_DELETE_WINDOW", self._close_sitzplan_popup)
        self._sitzplan_popup = popup
        self._sitzplan_popup.update(
            self.current_plan, self.theme_key, self.name_format, self.disambiguate_colliding_names
        )

    def _close_sitzplan_popup(self) -> None:
        """Schließt das Vorschaufenster und bricht ausstehende Timer ab."""
        if self._sitzplan_popup_after_id is not None:
            try:
                self.after_cancel(self._sitzplan_popup_after_id)
            except Exception:
                pass
            self._sitzplan_popup_after_id = None
        if self._sitzplan_popup is not None:
            try:
                self._sitzplan_popup.window.destroy()
            except Exception:
                pass
            self._sitzplan_popup = None

    def _notify_sitzplan_popup(self, plan: SeatingPlan | None, theme_key: str, name_format: str) -> None:
        """Plant eine debounced Aktualisierung des Popups.

        Wird bei jeder Zustandsänderung aufgerufen. Das Popup aktualisiert sich
        erst, wenn `sitzplan_popup_delay` Sekunden lang keine weitere Änderung kam.
        """
        if self._sitzplan_popup is None:
            return
        try:
            if not self._sitzplan_popup.window.winfo_exists():
                self._sitzplan_popup = None
                return
        except Exception:
            self._sitzplan_popup = None
            return

        self._sitzplan_popup_pending_plan = plan
        self._sitzplan_popup_pending_theme = theme_key
        self._sitzplan_popup_pending_fmt = name_format
        self._sitzplan_popup_pending_disambiguate = self.disambiguate_colliding_names

        if self._sitzplan_popup_after_id is not None:
            try:
                self.after_cancel(self._sitzplan_popup_after_id)
            except Exception:
                pass

        delay_ms = int(getattr(self, "sitzplan_popup_delay", 3) * 1000)
        self._sitzplan_popup_after_id = self.after(delay_ms, self._sitzplan_popup_fire_update)

    def _sitzplan_popup_fire_update(self) -> None:
        """Führt die aufgeschobene Popup-Aktualisierung aus."""
        self._sitzplan_popup_after_id = None
        if self._sitzplan_popup is None:
            return
        try:
            if not self._sitzplan_popup.window.winfo_exists():
                self._sitzplan_popup = None
                return
        except Exception:
            self._sitzplan_popup = None
            return
        self._sitzplan_popup.update(
            self._sitzplan_popup_pending_plan,
            self._sitzplan_popup_pending_theme,
            self._sitzplan_popup_pending_fmt,
            self._sitzplan_popup_pending_disambiguate,
        )
