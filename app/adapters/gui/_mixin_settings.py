"""Settings-Mixin für das Kartograph-Hauptfenster.

Stellt Normalisierungshelfer für konfigurierbare Einstellungen sowie den
Einstellungs-Dialog (spec, values, payload-Verarbeitung) bereit.
"""

from __future__ import annotations

import dataclasses

from app.adapters.gui.dialog_services import messagebox
from app.adapters.gui.main_window_constants import (
    DEFAULT_CANVAS_RADIUS,
    DEFAULT_DETAILS_OVERLAY_POSITION,
    DEFAULT_NAME_FORMAT,
    DEFAULT_SAVE_DELAY,
    DEFAULT_SITZPLAN_POPUP_DELAY,
    DEFAULT_SYMBOL_STRENGTH,
    DEFAULT_TABLEGROUP_OVERLAY_POSITION,
    DEFAULT_VIEWPORT_FOLLOW_BUFFER,
    NAME_FORMAT_OPTIONS,
    MAX_CANVAS_RADIUS,
    MAX_SAVE_DELAY,
    MAX_SITZPLAN_POPUP_DELAY,
    MIN_CANVAS_RADIUS,
    MIN_SAVE_DELAY,
    MIN_SITZPLAN_POPUP_DELAY,
    RECOMMENDED_MAX_SAVE_DELAY,
)
from app.core.domain.settings import resolve_plans_dir
from app.core.intents.view_intents import OpenSettingsIntent, UpdateSettingsIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.dialogs import SettingsDialogSpec as SharedSettingsDialogSpec
from bw_gui.dialogs import SettingsFieldSpec as SharedSettingsFieldSpec
from bw_gui.dialogs import SettingsSectionSpec as SharedSettingsSectionSpec
from bw_gui.dialogs import open_tabbed_settings_dialog as open_shared_tabbed_settings_dialog


class SettingsMixin:
    """Mixin: Einstellungs-Normalisierung, -Dialog-Spec und -Anwendung."""

    def _normalize_canvas_radius(self, value: object) -> int:
        """Klemmt den Canvas-Radius auf den gültigen Bereich.

        Args:
            value: Rohwert (wird in ``int`` umgewandelt).

        Returns:
            Geklemmter Radius zwischen ``MIN_CANVAS_RADIUS`` und ``MAX_CANVAS_RADIUS``.
        """
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = DEFAULT_CANVAS_RADIUS
        return max(MIN_CANVAS_RADIUS, min(MAX_CANVAS_RADIUS, parsed))

    def _normalize_symbol_strength(self, value: object) -> int:
        """Klemmt die Symbolstärke auf den gültigen Bereich 0–2.

        Args:
            value: Rohwert (0=Normal, 1=Fett, 2=Extra).
        """
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = DEFAULT_SYMBOL_STRENGTH
        return max(0, min(2, parsed))

    def _normalize_viewport_follow_buffer(self, value: object) -> int:
        """Klemmt den Sichtfenster-Puffer auf den Bereich 0–5.

        Args:
            value: Rohwert; 0 = immer zentrieren, 1 = 3×3-Zentrum bleibt frei.
        """
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            parsed = DEFAULT_VIEWPORT_FOLLOW_BUFFER
        return max(0, min(5, parsed))

    def _normalize_name_format(self, value: object) -> str:
        """Gibt das Namensformat für Grid, Sitzplan-Vorschau und PDF-Export zurück, falls gültig.

        Args:
            value: Rohwert; muss in ``NAME_FORMAT_OPTIONS`` enthalten sein.
        """
        raw = str(value or "").strip()
        return raw if raw in NAME_FORMAT_OPTIONS else DEFAULT_NAME_FORMAT

    def _normalize_grid_visible_symbols(self, raw_value: object, symbol_catalog: list[str]) -> set[str]:
        """Gibt die Menge der im Raster sichtbaren Symbole zurück.

        Bei leerer oder ungültiger Konfiguration werden alle Symbole angezeigt.

        Args:
            raw_value: Liste von Symbol-Bezeichnern aus den gespeicherten Einstellungen.
            symbol_catalog: Vollständiger Symbolkatalog als Referenz.
        """
        configured: set[str] = set()
        if isinstance(raw_value, list):
            for item in raw_value:
                meaning = str(item).strip()
                if meaning:
                    configured.add(meaning)
        valid = [meaning for meaning in symbol_catalog if meaning in configured]
        if valid:
            return set(valid)
        return set(symbol_catalog)

    def _normalize_details_overlay_position(self, value: object) -> str:
        """Gibt die Details-Overlay-Position zurück, falls gültig (left/right/bottom).

        Args:
            value: Roher Einstellungswert, z. B. aus der gespeicherten Konfiguration.
        """
        normalized = str(value or "").strip().lower()
        if normalized not in {"left", "right", "bottom"}:
            return DEFAULT_DETAILS_OVERLAY_POSITION
        return normalized

    def _normalize_tablegroup_overlay_position(self, value: object) -> str:
        """Gibt die Tischgruppen-Overlay-Position zurück, falls gültig (left/right/bottom).

        Args:
            value: Roher Einstellungswert, z. B. aus der gespeicherten Konfiguration.
        """
        normalized = str(value or "").strip().lower()
        if normalized not in {"left", "right", "bottom"}:
            return DEFAULT_TABLEGROUP_OVERLAY_POSITION
        return normalized

    def _build_settings_dialog_spec(self) -> SharedSettingsDialogSpec:
        """Erstellt das Spec-Objekt für den Einstellungs-Dialog.

        Definiert alle Sektionen und Felder mit ihren Typen, Standardwerten und Hinweistexten.
        """
        symbol_strength_labels = ("Normal", "Fett", "Extra")
        return SharedSettingsDialogSpec(
            sections=(
                SharedSettingsSectionSpec(
                    key="storage",
                    label="Speicher",
                    fields=(
                        SharedSettingsFieldSpec(
                            key="plans_dir",
                            label="Sitzplan-Ordner",
                            field_type="string",
                            default=str(self.plans_dir),
                            hint=f"leer => {self.default_plans_dir}",
                        ),
                    ),
                ),
                SharedSettingsSectionSpec(
                    key="editor",
                    label="Editor",
                    fields=(
                        SharedSettingsFieldSpec(
                            key="canvas_radius",
                            label="Canvas-Halbbreite",
                            field_type="int",
                            default=self.canvas_radius,
                            min_value=MIN_CANVAS_RADIUS,
                            max_value=MAX_CANVAS_RADIUS,
                            hint="entspricht (0,0) + Radius in jede Richtung",
                        ),
                        SharedSettingsFieldSpec(
                            key="symbol_strength",
                            label="Symbolstaerke",
                            field_type="enum",
                            enum_values=symbol_strength_labels,
                            default=symbol_strength_labels[min(max(self.symbol_strength, 0), 2)],
                        ),
                        SharedSettingsFieldSpec(
                            key="viewport_follow_buffer",
                            label="Sichtfenster-Puffer",
                            field_type="int",
                            default=self.viewport_follow_buffer,
                            min_value=0,
                            max_value=5,
                            hint="0 = immer zentrieren, 1 = 3x3-Zentrum",
                        ),
                        SharedSettingsFieldSpec(
                            key="name_format",
                            label="Namensanzeige (Grid, Vorschau, PDF-Export)",
                            field_type="enum",
                            enum_values=NAME_FORMAT_OPTIONS,
                            default=self.name_format,
                        ),
                        SharedSettingsFieldSpec(
                            key="disambiguate_colliding_names",
                            label="Nur so viel Nachname wie nötig zur Unterscheidung",
                            field_type="bool",
                            default=self.disambiguate_colliding_names,
                            hint="Bei gleichen Vornamen wird automatisch so viel vom Nachnamen ergänzt, bis eindeutig",
                        ),
                        SharedSettingsFieldSpec(
                            key="sitzplan_popup_delay",
                            label="Sitzplan-Vorschau: Verzoegerung (Sek.)",
                            field_type="int",
                            default=self.sitzplan_popup_delay,
                            min_value=MIN_SITZPLAN_POPUP_DELAY,
                            max_value=MAX_SITZPLAN_POPUP_DELAY,
                            hint="Sekunden Ruhe bis zur Aktualisierung der Vorschau",
                        ),
                        SharedSettingsFieldSpec(
                            key="save_delay",
                            label="Änderungen speichern: Verzögerung (Sek.)",
                            field_type="float",
                            default=self.save_delay,
                            min_value=MIN_SAVE_DELAY,
                            max_value=MAX_SAVE_DELAY,
                            hint=(
                                f"Ruhezeit bis Namen/Noten/Symbole/Farbmarkierungen gespeichert werden "
                                f"(Dezimalwerte erlaubt, z. B. 1.5); beim Verlassen des Feldes/Plans wird "
                                f"immer sofort gespeichert. Empfehlung: nicht höher als {RECOMMENDED_MAX_SAVE_DELAY:g}s, "
                                f"sonst bleiben bei einem Absturz mehr Änderungen ungespeichert"
                            ),
                        ),
                    ),
                ),
            )
        )

    def _settings_dialog_values(self) -> dict[str, object]:
        """Gibt die aktuellen Einstellungswerte für die Dialog-Initialisierung zurück."""
        symbol_strength_labels = {0: "Normal", 1: "Fett", 2: "Extra"}
        return {
            "plans_dir": str(self.plans_dir),
            "canvas_radius": self.canvas_radius,
            "symbol_strength": symbol_strength_labels.get(self.symbol_strength, "Fett"),
            "viewport_follow_buffer": self.viewport_follow_buffer,
            "name_format": self.name_format,
            "disambiguate_colliding_names": self.disambiguate_colliding_names,
            "sitzplan_popup_delay": self.sitzplan_popup_delay,
            "save_delay": self.save_delay,
        }

    def _apply_settings_dialog_payload(self, payload: dict[str, object], *, parent=None) -> bool:
        """Validiert und speichert die Einstellungen aus dem Dialog-Payload.

        Warnt bei Canvas-Radiusverkleinerung wenn Tische außerhalb fallen würden.

        Args:
            payload: Rohdaten aus dem Einstellungs-Dialog.
            parent: Optionales Elternfenster für Fehlermeldungen.

        Returns:
            ``True`` wenn alle Einstellungen erfolgreich gespeichert wurden.
        """
        if not isinstance(payload, dict):
            return False
        selected_text = str(payload.get("plans_dir") or "").strip()
        selected_path = resolve_plans_dir(selected_text, self.default_plans_dir)
        try:
            selected_path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showerror("Einstellungen", f"Sitzplan-Ordner konnte nicht angelegt werden: {exc}", parent=parent or self)
            return False
        new_radius = self._normalize_canvas_radius(payload.get("canvas_radius"))
        if self.current_plan and new_radius < self.canvas_radius:
            out_of_bounds = self._count_out_of_bounds_desks(self.current_plan, radius=new_radius)
            if out_of_bounds > 0:
                proceed = messagebox.askyesno(
                    "Warnung",
                    f"Bei Canvas-Radius {new_radius} waeren {out_of_bounds} Schuelertische nicht mehr sichtbar. Trotzdem speichern?",
                    parent=parent or self,
                )
                if not proceed:
                    self.status_var.set("Einstellungen unveraendert")
                    return False
        symbol_strength_values = {"Normal": 0, "Fett": 1, "Extra": 2}
        symbol_strength_key = str(payload.get("symbol_strength") or "Fett").strip()
        next_symbol_strength = symbol_strength_values.get(symbol_strength_key, DEFAULT_SYMBOL_STRENGTH)
        self.plans_dir = selected_path
        self.canvas_radius = new_radius
        self.symbol_strength = next_symbol_strength
        self.viewport_follow_buffer = self._normalize_viewport_follow_buffer(payload.get("viewport_follow_buffer"))
        self.name_format = self._normalize_name_format(payload.get("name_format"))
        self.disambiguate_colliding_names = bool(payload.get("disambiguate_colliding_names", False))
        try:
            self.sitzplan_popup_delay = max(MIN_SITZPLAN_POPUP_DELAY, min(MAX_SITZPLAN_POPUP_DELAY, int(payload.get("sitzplan_popup_delay", DEFAULT_SITZPLAN_POPUP_DELAY))))
        except (TypeError, ValueError):
            self.sitzplan_popup_delay = DEFAULT_SITZPLAN_POPUP_DELAY
        try:
            self.save_delay = max(MIN_SAVE_DELAY, min(MAX_SAVE_DELAY, float(payload.get("save_delay", DEFAULT_SAVE_DELAY))))
        except (TypeError, ValueError):
            self.save_delay = DEFAULT_SAVE_DELAY
        self._controller.dispatch(UpdateSettingsIntent(settings=dataclasses.replace(
            self._controller.state.settings,
            plans_dir=str(self.plans_dir),
            canvas_radius=self.canvas_radius,
            symbol_strength=self.symbol_strength,
            viewport_follow_buffer=self.viewport_follow_buffer,
            name_format=self.name_format,
            disambiguate_colliding_names=self.disambiguate_colliding_names,
            sitzplan_popup_delay=self.sitzplan_popup_delay,
            save_delay=self.save_delay,
        )))
        self._update_scroll_region()
        self._set_selection_single(*self.selection.active_cell())
        self.redraw_grid()
        self._refresh_details_panel()
        self.refresh_plan_list()
        self.status_var.set("Einstellungen aktualisiert")
        return True

    def open_settings_dialog(self) -> None:
        """Öffnet den tabbed Einstellungs-Dialog und wendet die Änderungen an.

        Lädt die Einstellungen vorab über ``OpenSettingsIntent`` frisch aus dem
        Repository (v4) und übernimmt die im Dialog angezeigten Felder aus dem
        aktualisierten AppState, bevor der Dialog aufgebaut wird.
        """
        self._controller.dispatch(OpenSettingsIntent())
        fresh = self._controller.state.settings
        self.plans_dir = resolve_plans_dir(fresh.plans_dir, self.plans_dir)
        self.canvas_radius = fresh.canvas_radius
        self.symbol_strength = fresh.symbol_strength
        self.viewport_follow_buffer = fresh.viewport_follow_buffer
        self.name_format = fresh.name_format
        self.disambiguate_colliding_names = fresh.disambiguate_colliding_names
        spec = self._build_settings_dialog_spec()
        payload = open_shared_tabbed_settings_dialog(
            self,
            title="Einstellungen",
            theme_key=self._shared_menu_theme_key(),
            spec=spec,
            initial_values=self._settings_dialog_values(),
            initial_section="editor",
        )
        if payload is None:
            return
        self._apply_settings_dialog_payload(payload, parent=self)
