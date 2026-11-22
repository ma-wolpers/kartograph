"""Bereichsauswahl der Datenansicht (Mixin für das Kartograph-Hauptfenster).

Die Regeln (Reihenfolge, höchstens zwei Bereiche neben den Namen, Vorgabe,
Speicherform) stehen in ``core/domain/data_view_areas``; hier nur die
GUI-Seite:

- ``_doc_visible_areas``: sichtbare Bereiche des offenen Plans aus den Einstellungen.
- ``set_data_area_visible``: Schalter-Aktion; speichert über ``UpdateSettingsIntent``.
  ``apply_state`` erkennt die geänderte Auswahl und baut die Tabelle neu auf.
- ``_build_data_area_switches`` / ``_sync_data_area_controls``: die drei
  Schalter (bw-gui ``Switch``: sofortige Wirkung) und das Ausgrauen von
  Schaltern und Toolbar-Knöpfen.
- ``_doc_area_at``: Bereich einer Grid-Region (für Klicks).
- ``_report_hidden_area``: einziger Sperrhinweis für Aktionen ausgeblendeter Bereiche.
"""

from __future__ import annotations

from app.adapters.gui._mixin_layout_docs import regions_by_area
from app.core.domain.data_view_areas import (
    DEFAULT_VISIBLE_AREAS,
    TOGGLEABLE_AREAS,
    DataArea,
    can_enable,
    visible_areas_for,
    with_area,
)
from app.core.intents import UpdateSettingsIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui
from bw_gui.widgets import Switch
from bw_gui.widgets.data_grid import Region


class DataAreasMixin:
    """Mixin: ein-/ausblendbare Bereiche der Datenansicht (Schalter, Speichern, Sperren)."""

    def _doc_visible_areas(self) -> tuple[DataArea, ...]:
        """Sichtbare ausblendbare Bereiche des offenen Plans (ohne Plan: die Vorgabe).

        Returns:
            z. B. ``(DataArea.DOKU, DataArea.NOTEN)``.
        """
        if self.current_plan is None:
            return DEFAULT_VISIBLE_AREAS
        return visible_areas_for(self._controller.state.settings.data_view_areas, self.current_plan.plan_id)

    def set_data_area_visible(self, area: DataArea, shown: bool) -> None:
        """Blendet *area* für den offenen Plan ein oder aus und speichert die Auswahl.

        Ein Einblenden über das Maximum hinaus ändert nichts (der Schalter ist
        dann ohnehin ausgegraut). Die Tabelle baut ``apply_state`` neu auf,
        sobald es die geänderte Auswahl sieht -- nicht diese Methode, damit es
        nur einen Weg gibt.

        Args:
            area: Ausblendbarer Bereich.
            shown: Gewünschter Zustand.
        """
        if self.current_plan is None:
            return
        visible = self._doc_visible_areas()
        wanted = with_area(visible, area, shown)
        if wanted == visible:
            self._sync_data_area_controls()
            return
        settings = self._controller.state.settings
        self._controller.dispatch(UpdateSettingsIntent(settings=settings.with_data_view_areas(self.current_plan.plan_id, wanted)))

    def _build_data_area_switches(self, parent: object) -> None:
        """Baut "Bereiche:" und je ausblendbarem Bereich einen ``Switch`` in *parent*.

        Args:
            parent: Container (Bereichsleiste unter der Toolbar).
        """
        tui.Label(parent, text="Bereiche:").pack(side="left")
        self._data_area_vars: dict[DataArea, ui.BooleanVar] = {}
        self._data_area_switches: dict[DataArea, Switch] = {}
        for area in TOGGLEABLE_AREAS:
            variable = ui.BooleanVar(master=self, value=area in DEFAULT_VISIBLE_AREAS)
            switch = Switch(parent, text=area.label, variable=variable,
                            on_change=lambda shown, a=area: self.set_data_area_visible(a, shown))
            switch.pack(side="left", padx=(8, 0))
            self._data_area_vars[area] = variable
            self._data_area_switches[area] = switch

    def _sync_data_area_controls(self) -> None:
        """Zeigt die aktuelle Auswahl an: Schalterstellung, ausgegraute Schalter und Knöpfe.

        Ein Schalter ist ausgegraut, wenn sein Bereich nicht mehr dazukommen
        darf (``can_enable``); ein Toolbar-Knopf, wenn sein Bereich ausgeblendet
        ist. Programmatisches Setzen der Variablen löst ``on_change`` nicht aus.
        """
        visible = self._doc_visible_areas()
        for area, variable in self._data_area_vars.items():
            if variable.get() != (area in visible):
                variable.set(area in visible)
            self._data_area_switches[area].state(["!disabled"] if can_enable(area, visible) else ["disabled"])
        for area, button in self._docs_area_buttons:
            button.state(["!disabled"] if area in visible else ["disabled"])
        self._sync_docs_column_buttons()

    def _doc_area_at(self, region: Region) -> DataArea | None:
        """Bereich, der gerade in der Grid-Region *region* steht (``None``: Region leer).

        Args:
            region: Region eines Klicks.
        """
        return next((area for area, shown_in in regions_by_area(self._doc_axis.areas).items() if shown_in is region), None)

    def _report_hidden_area(self, area: DataArea) -> bool:
        """Meldet in der Statuszeile, dass *area* ausgeblendet ist.

        Einzige Stelle für diesen Hinweis (Intents eines Bereichs, Doku-Aktionen).

        Args:
            area: Bereich, in dem die Aktion wirken würde.

        Returns:
            ``True``, wenn der Bereich ausgeblendet ist und die Aktion unterbleiben muss.
        """
        if area in self._doc_visible_areas():
            return False
        self.status_var.set(f"Der Bereich „{area.label}“ ist ausgeblendet")
        return True
