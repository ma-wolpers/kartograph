"""Zustandsanwendung für das Kartograph-Hauptfenster (Mixin).

Überträgt den AppState des Controllers auf die Oberfläche (apply_state, Planliste,
aktueller Plan, effektive Doku-Symbole und ihre Tastenkürzel) und leitet Intents an den
Controller weiter. Aus main_window.py ausgelagert (Dateigrößen-Regel); Methodenrümpfe
unverändert."""

from __future__ import annotations


from app.adapters.gui.main_window_constants import LIST_ACTIVE, GRID_SELECTED, NAME_EDITING
from app.adapters.gui.ui_theme import normalize_theme_key
from app.application.app_state import AppState, EditorSurface, InteractionMode, PlanListEntry
from app.core.domain.effective_symbol import build_effective_documentation_symbols
from app.core.domain.models_v4 import CustomSymbolDefinition
from app.core.domain.settings import resolve_plans_dir
from app.infrastructure.symbol_config_loader import SymbolDefinition
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import BwBaseWindow


class StateApplyMixin:
    """Zustandsanwendung für das Kartograph-Hauptfenster (Mixin)."""

    def dispatch(self, intent) -> None:
        """Delegiert einen Intent an den KartographAppController.

        Args:
            intent: Auszuführendes Intent-Objekt.
        """
        self._controller.dispatch(intent)

    @property
    def interaction_mode(self) -> str:
        """Aktueller Interaktionsmodus der GUI.

        LIST_ACTIVE/GRID_SELECTED werden live aus ``AppState.interaction_mode``
        abgeleitet (keine eigene GUI-Kopie). NAME_EDITING wird live an der
        echten Tk-Fokuslage erkannt statt gespeichert: ``AppState``s
        ``InteractionMode.NAME_EDIT`` markiert nur den Moment direkt nach dem
        Neuanlegen eines Schülers (s. ``handle_create_student``) und wird
        durch jeden Tastenanschlag beim Umbenennen sofort wieder auf
        ``GRID`` zurückgesetzt (s. ``handle_rename_student``) — es bildet
        also nicht "Cursor sitzt gerade im Namensfeld" ab, das ist ein
        reines UI-Fokusdetail ohne Entsprechung in der Domäne.
        """
        if self._is_name_entry_focused():
            return NAME_EDITING
        if self._controller.state.interaction_mode == InteractionMode.GRID:
            return GRID_SELECTED
        return LIST_ACTIVE

    @property
    def _documentation_only_symbols(self) -> set[str]:
        """Live abgeleitete Menge aller Doku-Symbol-Schlüssel (eingebaut + eigen).

        Reine Ableitung aus ``self.effective_documentation_symbols`` (das über
        ``_rebuild_effective_documentation_symbols_if_changed()`` bei jedem
        Planwechsel und jeder Symbol-Änderung aktuell gehalten wird) — bewusst
        kein eigener, potenziell veraltender Zustand.
        """
        return {s.key for s in self.effective_documentation_symbols}

    def apply_state(self, state: AppState) -> None:
        """Synct einen neuen AppState in die GUI und löst alle nötigen Re-Renders aus.

        Wird ausschließlich vom KartographAppController als Callback aufgerufen.

        Args:
            state: Neuer, vollständiger Anwendungszustand.
        """
        old_plan = self.current_plan
        self.current_plan = state.current_plan
        self.current_plan_path = state.current_plan_path
        self._rebuild_effective_documentation_symbols_if_changed(
            self.current_plan.custom_symbols if self.current_plan else {}
        )

        if state.settings.theme != self.theme_key:
            new_theme = normalize_theme_key(state.settings.theme)
            BwBaseWindow.apply_theme(self, new_theme)  # updates self.theme_key via the shell
            self.theme_var.set(self.theme_key)
            self._apply_kartograph_theme()
            self.redraw_grid()

        settings = state.settings
        self.canvas_radius = settings.canvas_radius
        self.symbol_strength = settings.symbol_strength
        self.viewport_follow_buffer = settings.viewport_follow_buffer
        self.name_format = settings.name_format
        self.disambiguate_colliding_names = settings.disambiguate_colliding_names
        self.sitzplan_popup_delay = settings.sitzplan_popup_delay
        self.save_delay = settings.save_delay
        self.details_overlay_position = settings.details_overlay_position
        self.tablegroup_overlay_position = settings.tablegroup_overlay_position
        self.plans_dir = resolve_plans_dir(settings.plans_dir, self.default_plans_dir)

        if state.status_message:
            self.status_var.set(state.status_message)

        self.selection = state.selection
        self.selected_cell = state.selection.active_cell()

        if state.cell_size != self.cell_size:
            self.cell_size = state.cell_size
            self._update_scroll_region()
            self.redraw_grid()
            self.center_on_cell(*state.selection.active_cell())

        new_editor_surface = "docs" if state.editor_surface == EditorSurface.DOCUMENTATION else "grid"
        editor_surface_changed = new_editor_surface != self._editor_surface
        self._editor_surface = new_editor_surface

        if state.current_plan is not None:
            self.plan_name_var.set(f"Plan: {state.current_plan.meta.name}")
        elif old_plan is not None:
            self.plan_name_var.set("")

        # Update plan listbox from state
        if state.plan_list is not None:
            self._apply_plan_list(state.plan_list)

        # View transition
        if old_plan is None and state.current_plan is not None:
            self.show_editor_view()
            self.center_on_cell(0, 0)
        elif old_plan is not None and state.current_plan is None:
            self.show_plan_list_view()
        elif editor_surface_changed and self.editor_view.winfo_ismapped():
            if self._editor_surface == "docs":
                self.show_documentation_surface()
            else:
                self.show_grid_surface()

        # Re-render editor if visible
        if hasattr(self, "editor_view") and self.editor_view.winfo_ismapped():
            self.redraw_grid()
            self._refresh_details_panel()
            if self._editor_surface == "docs" and state.current_plan is not None:
                self._refresh_documentation_table()
                if state.doc_selected_date is not None and state.doc_selected_date in self._doc_dates:
                    self._select_doc_date_column(self._doc_dates.index(state.doc_selected_date))
                self._apply_doc_column_heading_highlight()

        self._notify_sitzplan_popup(state.current_plan, self.theme_key, self.name_format)

    def _rebuild_effective_documentation_symbols_if_changed(
        self, custom_symbols: dict[str, CustomSymbolDefinition]
    ) -> None:
        """Baut ``self.effective_documentation_symbols`` neu, falls sich die eigenen Symbole geändert haben.

        Vergleicht *custom_symbols* gegen den zuletzt gesehenen Stand
        (``self._last_custom_symbols_snapshot``) und überspringt den Neubau,
        wenn sich nichts geändert hat — ein einfacher Dict-Vergleich (kleine
        Map, keine I/O), bewusst kein Caching-Subsystem für eine kleine
        Liste. Wird sowohl im Konstruktor (mit ``{}``, vor jedem geöffneten
        Plan) als auch bei jedem ``apply_state()``-Aufruf aufgerufen, sodass
        Planwechsel und Symbol-CRUD die Liste automatisch aktuell halten,
        ohne dass jede unabhängige Sitzplatz-/Dokumentationsmutation sie
        pauschal neu berechnet.

        Args:
            custom_symbols: Die eigenen Symbole des aktuell betrachteten
                Plans (``SeatingPlan.custom_symbols``), oder ``{}`` bei
                keinem offenen Plan.
        """
        if custom_symbols == self._last_custom_symbols_snapshot:
            return
        self.effective_documentation_symbols = build_effective_documentation_symbols(
            self.symbol_definitions, custom_symbols
        )
        self._effective_symbol_by_key = {s.key: s for s in self.effective_documentation_symbols}
        self._last_custom_symbols_snapshot = dict(custom_symbols)

        # self._grid_visible_symbols muss dieselbe Referenzmenge kennen wie der
        # Symbolfilter-Dialog (_mixin_export.py::open_grid_symbol_filter_dialog):
        # self.symbol_catalog allein enthaelt nur eingebaute Symbole -- ohne diese
        # Erweiterung waeren eigene Symbole selbst im unveraenderten "alles
        # sichtbar"-Standardzustand nie sichtbar (_normalize_grid_visible_symbols()
        # faellt bei leerer/ungueltiger Einstellung auf "alle aus der Referenzmenge"
        # zurueck -- ohne eigene Symbole in dieser Menge blieben sie dauerhaft
        # ausgeblendet, kein reiner Randfall).
        reference_catalog = self.symbol_catalog + [
            s.key for s in self.effective_documentation_symbols if s.is_custom
        ]
        self._grid_visible_symbols = self._normalize_grid_visible_symbols(
            list(self._controller.state.settings.grid_visible_symbols), reference_catalog
        )

    def _replace_current_plan(self, plan) -> None:
        """Ersetzt den aktuellen Plan im AppState und im GUI-Zustand synchron.

        Für History-freie Vorab-Anpassungen (z. B. Tischgruppen-Normalisierung,
        Farbpaletten-Bedeutung), die keinen ``on_state_changed``-Callback über
        ``apply_state()`` auslösen (s. ``KartographAppController.replace_plan_in_state``).
        Einziger Weg für diese Art Ersetzung, damit ``self.current_plan`` nie
        vergessen wird nachzuziehen.

        Args:
            plan: Neuer Planzustand, der den aktuellen ersetzt.
        """
        self.current_plan = plan
        self._controller.replace_plan_in_state(plan)

    def _apply_plan_list(self, plan_list: list[PlanListEntry]) -> None:
        """Aktualisiert die interne Planliste und die Listbox aus einem PlanListEntry-Array.

        Args:
            plan_list: Aktuelle Liste der Plan-Einträge aus dem AppState.
        """
        from bw_gui.runtime import ui as _ui
        self._plan_index = list(plan_list)
        if not hasattr(self, "plan_listbox"):
            return
        self.plan_listbox.delete(0, _ui.END)
        for entry in self._plan_index:
            display_name = f"({entry.name})" if entry.is_archived else entry.name
            self.plan_listbox.insert(_ui.END, f"{display_name}  |  {entry.student_count} Schülertische")
        self._ensure_list_selection(preferred_path=self.current_plan_path)

    def _build_symbol_shortcut_map(self, definitions: list[SymbolDefinition]) -> dict[str, str]:
        """Erstellt eine Mapping-Tabelle von Shortcut-Zeichen zu Symbol-Bezeichnern.

        Args:
            definitions: Vollständige Liste der Symbol-Definitionen.

        Returns:
            Dict ``{shortcut: meaning}``; bei Duplikaten gewinnt die erste Definition.
        """
        mapping: dict[str, str] = {}
        for definition in definitions:
            if definition.shortcut is None:
                continue
            if definition.shortcut in mapping:
                continue
            mapping[definition.shortcut] = definition.meaning
        return mapping
