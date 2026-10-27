"""Sitzplan-Vorschau-Popup-Mixin für das Kartograph-Hauptfenster.

Verwaltet den Lebenszyklus des Vorschaufensters: mit Einstellungen anlegen
oder ein offenes Fenster aktualisieren, debounced bei Planänderungen neu
zeichnen, schließen. Den Einstellungsdialog davor baut
``_mixin_sitzplan_preview_dialog.py``.
"""

from __future__ import annotations

from app.adapters.gui._sitzplan_popup import SitzplanPopup
from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.preview_color_frames import PreviewOptions


class SitzplanPopupMixin:
    """Mixin: Sitzplan-Vorschau-Popup anlegen/aktualisieren, debounced neu zeichnen und schließen."""

    def _init_sitzplan_popup_state(self) -> None:
        """Initialisiert den Popup-Zustand (im __init__ des Hauptfensters aufrufen)."""
        self._sitzplan_popup: SitzplanPopup | None = None
        self._sitzplan_popup_after_id: str | None = None
        self._sitzplan_popup_pending_plan: SeatingPlan | None = None
        self._sitzplan_popup_pending_theme: str = "mono_day"
        self._sitzplan_popup_pending_fmt: str = "Vorname Nachname"
        self._sitzplan_popup_pending_disambiguate: bool = False

    def _live_sitzplan_popup(self) -> SitzplanPopup | None:
        """Gibt das offene Vorschaufenster zurück oder ``None``, wenn keins (mehr) existiert.

        Einzige Stelle, die prüft, ob das Fenster noch lebt. Ein vom
        Fenstermanager bereits zerstörtes Fenster wird dabei vergessen.
        """
        if self._sitzplan_popup is None:
            return None
        try:
            if self._sitzplan_popup.window.winfo_exists():
                return self._sitzplan_popup
        except Exception:
            pass
        self._sitzplan_popup = None
        return None

    def _apply_sitzplan_preview_options(self, options: PreviewOptions) -> None:
        """Zeigt die Vorschau mit *options*: aktualisiert ein offenes Fenster oder öffnet eines.

        Ist schon eine Vorschau offen, öffnet sich bewusst keine zweite. Die
        bestehende übernimmt die Einstellungen und kommt in den Vordergrund.

        Args:
            options: Im Dialog bestätigte Einstellungen.
        """
        popup = self._live_sitzplan_popup()
        if popup is not None:
            popup.set_options(options)
            popup.window.lift()
            popup.window.focus_set()
            return

        popup = SitzplanPopup(
            self, color_palette=self.color_palette, options=options,
            theme_key=self.theme_key, name_format=self.name_format,
        )
        # Live-Vorschau neben dem Bearbeiten: Werkzeugfenster, sperrt die Kuerzel des Hauptfensters
        # nicht (bis 2026-10-15 sperrte sie, weil der fruehere Scan sie als Dialog zaehlte).
        self._register_popup_window(popup.window, blocking_shortcuts=False)
        popup.window.protocol("WM_DELETE_WINDOW", self._close_sitzplan_popup)
        self._sitzplan_popup = popup
        popup.update(self.current_plan, self.theme_key, self.name_format, self.disambiguate_colliding_names)

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

        Args:
            plan: Neuer Planzustand.
            theme_key: Aktives Theme.
            name_format: Aktives Namensformat.
        """
        if self._live_sitzplan_popup() is None:
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
        popup = self._live_sitzplan_popup()
        if popup is None:
            return
        popup.update(
            self._sitzplan_popup_pending_plan,
            self._sitzplan_popup_pending_theme,
            self._sitzplan_popup_pending_fmt,
            self._sitzplan_popup_pending_disambiguate,
        )
