"""Zustandsanwendung für das Kartograph-Hauptfenster (Mixin).

Überträgt den AppState des Controllers auf die Oberfläche (apply_state, Planliste,
aktueller Plan, effektive Doku-Symbole und ihre Tastenkürzel) und leitet Intents an den
Controller weiter. Aus main_window.py ausgelagert (Dateigrößen-Regel); Methodenrümpfe
unverändert."""

from __future__ import annotations


from app.adapters.gui.main_window_constants import LIST_ACTIVE, GRID_SELECTED, NAME_EDITING
from app.adapters.gui.ui_theme import normalize_theme_key
from app.application.app_state import AppState, EditorSurface, InteractionMode, PlanListEntry
from app.core.domain.settings import resolve_plans_dir
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

    def apply_state(self, state: AppState) -> None:
        """Synct einen neuen AppState in die GUI und löst alle nötigen Re-Renders aus.

        Wird ausschließlich vom KartographAppController als Callback aufgerufen.

        Args:
            state: Neuer, vollständiger Anwendungszustand.
        """
        old_plan = self.current_plan
        old_plan_path = self.current_plan_path
        old_selection = self.selection
        # Nur Auswahl/Status geändert? Dann bleiben Tische, Doku-Modell und Details stehen.
        content_same = self._controller.content_version == self._applied_content_version
        self.current_plan = state.current_plan
        self.current_plan_path = state.current_plan_path
        self._close_submission_viewer_if_plan_changed()
        self._apply_symbol_view_if_changed()

        if state.settings.theme != self.theme_key:
            new_theme = normalize_theme_key(state.settings.theme)
            BwBaseWindow.apply_theme(self, new_theme)  # updates self.theme_key via the shell
            self.theme_var.set(self.theme_key)
            self._apply_kartograph_theme()  # Raster: Theme steht im Inhaltsschlüssel, s. Render-Block unten

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

        if hasattr(self, "docs_grid"):
            self.docs_grid.set_width_scale(state.docs_width_scale)  # unveränderter Wert = No-op im Grid
        if state.cell_size != self.cell_size:
            self.cell_size = state.cell_size
            self._update_scroll_region()  # Raster: Zellgröße steht im Inhaltsschlüssel, s. Render-Block unten
            self.center_on_cell(*state.selection.active_cell())

        new_editor_surface = "docs" if state.editor_surface == EditorSurface.DOCUMENTATION else "grid"
        editor_surface_changed = new_editor_surface != self._editor_surface
        self._editor_surface = new_editor_surface

        if state.current_plan is not None:
            self.plan_name_var.set(f"Plan: {state.current_plan.meta.name}")
        elif old_plan is not None:
            self.plan_name_var.set("")

        # Planliste nur bei geänderter Liste oder anderem Plan neu befüllen (nicht bei jedem Dispatch).
        if state.plan_list is not None and (state.plan_list is not self._applied_plan_list or old_plan_path != self.current_plan_path):
            self._apply_plan_list(state.plan_list)
            self._applied_plan_list = state.plan_list

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

        # Re-render editor if visible — nur, was sich geändert hat und sichtbar ist.
        if hasattr(self, "editor_view") and self.editor_view.winfo_ismapped():
            if self._editor_surface == "grid":
                self.redraw_grid(selection_only=content_same)
            if not content_same or state.selection != old_selection:
                self._refresh_details_panel()
            if self._editor_surface == "docs" and state.current_plan is not None:
                if not content_same:
                    self._refresh_documentation_table()
                if state.doc_selected_date is not None and state.doc_selected_date in self._doc_dates:
                    self._select_doc_date_column(self._doc_dates.index(state.doc_selected_date))
                self._sync_docs_cursor()
        self._applied_content_version = self._controller.content_version

        self._notify_sitzplan_popup(state.current_plan, self.theme_key, self.name_format)

    def _replace_current_plan(self, plan) -> None:
        """Ersetzt den aktuellen Plan im AppState und im GUI-Zustand synchron.

        Für History-freie Vorab-Anpassungen (z. B. Farbpaletten-Bedeutung, die der
        nächste Intent mit aufzeichnet), die keinen ``on_state_changed``-Callback über
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
