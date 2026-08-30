"""Kartograph-Hauptfenster.

Definiert ``KartographMainWindow`` als Integration aller Mixin-Klassen via
Python-Mehrfachvererbung. Der ``__init__`` initialisiert den gesamten Instanzzustand;
alle Methoden sind in thematisch getrennten Mixin-Modulen implementiert.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.app_info import APP_INFO
from app.adapters.gui._mixin_canvas_events import CanvasEventsMixin
from app.adapters.gui._mixin_details import DetailsMixin
from app.adapters.gui._mixin_details_layout import DetailsLayoutMixin
from app.adapters.gui._mixin_docs_dialogs import DocsDialogsMixin
from app.adapters.gui._mixin_docs_edit import DocsEditMixin
from app.adapters.gui._mixin_docs_events import DocsEventsMixin
from app.adapters.gui._mixin_docs_nav import DocsNavMixin
from app.adapters.gui._mixin_docs_table import DocsTableMixin
from app.adapters.gui._mixin_docs_view import DocsViewMixin
from app.adapters.gui._mixin_edit import EditMixin
from app.adapters.gui._mixin_export import ExportMixin
from app.adapters.gui._mixin_grid_helpers import GridHelpersMixin
from app.adapters.gui._mixin_grid_render import GridRenderMixin
from app.adapters.gui._mixin_laufkern import LaufkernMixin
from app.adapters.gui._mixin_layout import LayoutMixin
from app.adapters.gui._mixin_layout_docs import LayoutDocsMixin
from app.adapters.gui._mixin_menu import MenuMixin
from app.adapters.gui._mixin_namenfit_export import NamenfitExportMixin
from app.adapters.gui._mixin_pdf import PdfMixin
from app.adapters.gui._mixin_student_png_export import StudentPngExportMixin
from app.adapters.gui._mixin_symbol_management import SymbolManagementMixin
from app.adapters.gui._mixin_symbol_management_form import SymbolManagementFormMixin
from app.adapters.gui._mixin_plan_crud import PlanCrudMixin
from app.adapters.gui._mixin_plan_list import PlanListMixin
from app.adapters.gui._mixin_plan_save import PlanSaveMixin
from app.adapters.gui._mixin_popup import PopupMixin
from app.adapters.gui._mixin_sitzplan_popup import SitzplanPopupMixin
from app.adapters.gui._mixin_selection import SelectionMixin
from app.adapters.gui._mixin_settings import SettingsMixin
from app.adapters.gui._mixin_shortcut_handlers import ShortcutHandlersMixin
from app.adapters.gui._mixin_shortcuts import ShortcutMixin
from app.adapters.gui._mixin_tablegroup import TablegroupMixin
from app.adapters.gui._mixin_tablegroup_logic import TablegroupLogicMixin
from app.adapters.gui._mixin_theme import ThemeMixin
from app.adapters.gui._mixin_undo_redo import UndoRedoMixin
from app.adapters.gui._mixin_viewport import ViewportMixin
from app.adapters.gui.main_window_constants import (
    COLOR_MARKER_PALETTE,
    DEFAULT_CANVAS_RADIUS,
    DEFAULT_CELL_SIZE,
    DEFAULT_PERIODIC_BACKUP_INTERVAL_MS,
    DEFAULT_UI_WATCHDOG_INTERVAL_MS,
    LOGGER,
    LIST_ACTIVE,
    GRID_SELECTED,
    NAME_EDITING,
    DeskDetailMode,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    UI_WATCHDOG_WARN_DRIFT_SECONDS,
    _known_ui_intents,
    apply_window_icon,
    configure_windows_process_identity,
)
from app.adapters.gui.ui_intents import UiIntent
from app.adapters.gui.ui_theme import normalize_theme_key
from app.application.app_controller import KartographAppController
from app.application.app_state import AppState, EditorSurface, InteractionMode, PlanListEntry
from app.core.domain.effective_symbol import EffectiveSymbol, build_effective_documentation_symbols
from app.core.domain.models_v4 import CustomSymbolDefinition, SeatingPlan
from app.core.domain.plan_selection import RectSelection
from app.core.domain.settings import resolve_plans_dir
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter
from app.infrastructure.symbol_config_loader import SymbolDefinition
from bw_libs.app_shell import AppShellConfig
from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from bw_libs.ui_contract.hsm import build_ui_hsm_contract
from bw_libs.ui_contract.keybinding import KeybindingRegistry
from bw_libs.ui_contract.popup import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry

ensure_bw_gui_on_path()
from bw_gui.runtime import BwBaseWindow, ui, widgets as tui
from bw_gui.menu import section_spec


class KartographMainWindow(
    PdfMixin,
    NamenfitExportMixin,
    StudentPngExportMixin,
    SymbolManagementMixin,
    SymbolManagementFormMixin,
    ExportMixin,
    SettingsMixin,
    UndoRedoMixin,
    EditMixin,
    DocsEditMixin,
    PlanCrudMixin,
    PlanListMixin,
    PlanSaveMixin,
    DocsDialogsMixin,
    DocsEventsMixin,
    DocsTableMixin,
    DocsNavMixin,
    DocsViewMixin,
    DetailsMixin,
    DetailsLayoutMixin,
    SelectionMixin,
    GridHelpersMixin,
    GridRenderMixin,
    CanvasEventsMixin,
    ViewportMixin,
    TablegroupLogicMixin,
    TablegroupMixin,
    ThemeMixin,
    LaufkernMixin,
    PopupMixin,
    SitzplanPopupMixin,
    ShortcutHandlersMixin,
    ShortcutMixin,
    LayoutDocsMixin,
    LayoutMixin,
    MenuMixin,
    BwBaseWindow,
):
    """Haupt-GUI-Klasse für den Kartograph-Sitzplan-Editor.

    Alle Methoden sind in thematisch getrennten Mixin-Klassen implementiert.
    Diese Klasse ist nur für ``__init__`` und die Kernlebenszyklus-Methoden zuständig.
    """

    def __init__(
        self,
        controller: KartographAppController,
        shell_config: AppShellConfig | None = None,
    ) -> None:
        """Initialisiert das Hauptfenster und alle Subsysteme.

        Args:
            controller: Zentraler Application-Service-Controller (lädt Settings
                und Symbol-Katalog bereits selbst, s. ``AppState.settings``/
                ``AppState.symbol_catalog``).
            shell_config: Optionale App-Shell-Konfiguration.
        """
        self._init_start_time = time.perf_counter()
        LOGGER.info("Main window __init__ start")
        configure_windows_process_identity()

        self._controller = controller
        self._controller._on_state_changed = self.apply_state
        # Expose repo for unmigrated mixins (pdf, export, plan-list, undo-redo)
        self.plan_repository = controller.plan_repository
        self.default_plans_dir = controller.default_plans_dir

        # Redraw-Memoization (_mixin_grid_render.py): über state_version +
        # relevante Einstellungen gekeyte Caches, damit reine Cursor-
        # Navigation/Drag/Scroll nicht bei jedem Tick Namen/Geometrie/
        # Schriftgröße neu berechnet. Cache-Wert ist erst nach dem ersten
        # redraw_grid()-Aufruf gültig; der Key-Vergleich schlägt beim
        # allerersten Aufruf immer fehl (None != echter Schlüssel), das
        # erzwingt korrekt eine initiale Berechnung.
        self._grid_names_cache_key: tuple | None = None
        self._grid_names_cache_value: dict | None = None
        self._grid_geometry_cache_key: int | None = None
        self._grid_geometry_cache_value: list | None = None
        self._grid_font_size_cache_key: tuple | None = None
        self._grid_font_size_cache_value: int | None = None

        # Canvas-Item-Pool für Hintergrundkacheln (Item 5, Stufe A): Kacheln
        # werden über Aufrufe hinweg wiederverwendet (coords()/itemconfigure())
        # statt bei jedem redraw_grid() gelöscht und neu erzeugt. Andere
        # Canvas-Items (Pulte, Auswahl-Indikatoren) sind noch nicht gepoolt --
        # deren Tag "grid_transient" wird weiterhin bei jedem Aufruf gelöscht.
        self._grid_tile_pool: list[int] = []

        # Debounced Speichern (_mixin_plan_save.py): State muss vor dem
        # ersten möglichen Dispatch stehen, da set_plan_save_scheduler()
        # unten ctx.plan_save_scheduler sofort scharf schaltet.
        self._pending_plan_save: tuple[SeatingPlan, Path] | None = None
        self._plan_save_after_id: str | None = None
        self._controller.set_plan_save_scheduler(self._schedule_plan_save)

        # AppState.settings ist beim Controller-Start bereits aus dem
        # Settings-Repository geladen und normalisiert (Phase D1) — die GUI
        # übernimmt nur noch die Werte, statt sie selbst erneut zu laden.
        settings = self._controller.state.settings
        self.plans_dir = resolve_plans_dir(settings.plans_dir, self.default_plans_dir)
        initial_theme_key = normalize_theme_key(settings.theme)
        self.canvas_radius = settings.canvas_radius
        self.symbol_strength = settings.symbol_strength
        self.viewport_follow_buffer = settings.viewport_follow_buffer
        self.details_overlay_position = settings.details_overlay_position
        self.tablegroup_overlay_position = settings.tablegroup_overlay_position
        self.name_format = settings.name_format
        self.disambiguate_colliding_names = settings.disambiguate_colliding_names
        self.sitzplan_popup_delay = settings.sitzplan_popup_delay
        self.save_delay = settings.save_delay

        resolved_shell_config = shell_config or AppShellConfig(
            title=APP_INFO.window_title, geometry="1320x860", min_width=MIN_WINDOW_WIDTH, min_height=MIN_WINDOW_HEIGHT
        )
        super().__init__(
            title=resolved_shell_config.title,
            geometry=resolved_shell_config.geometry,
            theme_key=initial_theme_key,
            min_width=resolved_shell_config.min_width,
            min_height=resolved_shell_config.min_height,
            on_close=self._on_shell_close,
        )
        # self.theme_key is a read-only BwBaseWindow property backed by the shell
        # from here on (set above via theme_key=initial_theme_key); it must not be
        # assigned to directly.

    def build_menu(self) -> list:
        """Liefert die Menüstruktur für BwBaseWindow."""
        return [
            section_spec("file", label="Datei", alt="d", items_provider=self._menu_items_file),
            section_spec("edit", label="Bearbeiten", alt="b", items_provider=self._menu_items_edit),
            section_spec("view", label="Ansicht", alt="a", items_provider=self._menu_items_view),
        ]

    def build_content(self, frame) -> None:
        """Erzeugt alle UI-Komponenten nach Fenster-Setup durch BwBaseWindow."""
        apply_window_icon(self.tk_root)
        self.tk_root.report_callback_exception = self._report_tk_callback_exception

        self.current_plan_path: Path | None = None
        self.current_plan: SeatingPlan | None = None
        self._display_names: dict = {}
        self.selected_cell: tuple[int, int] = (0, 0)
        self.selection = RectSelection(0, 0)
        self._drag_active = False
        self.cell_size = DEFAULT_CELL_SIZE
        self._plan_index: list[PlanListEntry] = []
        # None = HIDDEN. Sonst (x, y, mode): Detail-Panel fuer Zelle (x, y) sichtbar,
        # mode = DESK_DETAIL_REVEALED (lesend) oder DESK_DETAIL_EDITING (Namensfelder
        # aktiv). EDITING ist der semantische Quellzustand; Tk-Fokus auf name_entry
        # folgt daraus, nicht umgekehrt. Einzige Schreibzugriffe: _set_desk_detail_state(),
        # _clear_desk_detail_state(), _reconcile_desk_detail_state() in _mixin_details.py.
        self._desk_detail_state: tuple[int, int, DeskDetailMode] | None = None

        self._ui_action_registry = self._build_ui_action_registry()
        self._hsm_contract = build_ui_hsm_contract(intents=_known_ui_intents())

        self._name_var = ui.StringVar(value="")
        self._last_name_var = ui.StringVar(value="")
        self._nickname_var = ui.StringVar(value="")
        self._name_save_after_id: str | None = None
        self._pending_name_save: dict | None = None
        self._selected_marker_var = ui.StringVar(value="")
        self._doc_selection_status_var = ui.StringVar(value="Doku-Zelle: -")
        self.status_var = ui.StringVar(value="Bereit")
        self._runtime_shortcuts = KeybindingRegistry()
        self._popup_registry = PopupPolicyRegistry()
        self._popup_registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
        self._popup_registry.register_policy(
            PopupPolicy(policy_id="dialog.non_blocking", kind=POPUP_KIND_NON_MODAL, trap_focus=False, affects_mode=False)
        )
        self._tracked_popup_ids: set[str] = set()
        self._hover_tooltips: list[object] = []
        self._shortcut_runtime_offline = False
        self._shortcut_runtime_debug_window: ui.Toplevel | None = None
        self._shortcut_runtime_debug_table: tui.Treeview | None = None
        self._symbol_management_window: ui.Toplevel | None = None
        self._symbol_management_table: tui.Treeview | None = None
        self._symbol_management_edit_button: tui.Button | None = None
        self._symbol_management_delete_button: tui.Button | None = None
        self._shortcut_runtime_debug_context_var = ui.StringVar(value="")
        self._shortcut_runtime_debug_summary_var = ui.StringVar(value="")
        self._shortcut_runtime_debug_offline_var = ui.BooleanVar(value=False)
        self._laufkern_tracking_run_id = "runtime-intents"
        self._laufkern_tracking_sequence = 0
        self._laufkern_tracking_step_ids: dict[str, str] = {}
        self._laufkern_tracking_artifacts = []
        self._init_sitzplan_popup_state()
        self._tablegroup_overlay: ui.Toplevel | None = None
        self._tg_number_var: ui.StringVar | None = None
        self._tg_shift_x_var: ui.StringVar | None = None
        self._tg_shift_y_var: ui.StringVar | None = None
        self._tg_rotation_var: ui.StringVar | None = None
        self._tg_status_var: ui.StringVar | None = None
        self._tg_last_changed_field: str = "shift_x"
        self._color_marker_buttons: list[ui.Button] = []
        self._editor_surface: str = "grid"
        self._doc_selected_student_index: int = 0
        self._doc_selected_date_index: int = 0
        self._doc_student_coords: list[tuple[int, int]] = []
        self._doc_dates: list[str] = []
        self._doc_tree_iid_by_student_index: dict[int, str] = {}
        self._doc_student_index_by_iid: dict[str, int] = {}
        self._doc_row_values_cache: dict[str, tuple[str, tuple, tuple]] = {}
        self._doc_date_column_ids: list[str] = []
        self._doc_fixed_column_ids: list[str] = []
        self._doc_selected_fixed_column_id: str | None = None
        self._doc_sort_column: str | None = None
        self._doc_sort_ascending: bool = True
        self._docs_splitter_positioned: bool = False
        self._docs_inline_editor: tui.Entry | None = None
        self._docs_inline_editor_tree: tui.Treeview | None = None
        self._docs_inline_editor_row_id: str | None = None
        self._docs_inline_editor_kind: str | None = None
        self._docs_inline_editor_model_column: str | None = None
        self._docs_cell_overlay: ui.Label | None = None
        self._docs_symbol_dialog_last_index: int = 0
        self._ui_watchdog_last_tick = time.perf_counter()
        self._ui_watchdog_tick_count = 0

        self.color_palette = COLOR_MARKER_PALETTE
        self._color_by_key = {color_key: (label, hex_color) for _key, color_key, label, hex_color in self.color_palette}

        # AppState.symbol_catalog ist beim Controller-Start bereits geladen
        # (Phase D3) — die GUI liest nur noch daraus statt selbst erneut
        # die Symbol-Konfigurationsdatei zu öffnen.
        self.symbol_definitions = list(self._controller.state.symbol_catalog)
        warning = self._controller.symbol_catalog_warning
        self.symbol_catalog = [item.meaning for item in self.symbol_definitions]
        self.diagnostic_symbol_catalog = [item.meaning for item in self.symbol_definitions if item.role == "diagnostic"]
        self._symbol_by_meaning = {item.meaning: item for item in self.symbol_definitions}
        self._shortcut_to_symbol = self._build_symbol_shortcut_map(self.symbol_definitions)
        self.effective_documentation_symbols: list[EffectiveSymbol] = []
        self._effective_symbol_by_key: dict[str, EffectiveSymbol] = {}
        # None (nicht {}) als "noch nie berechnet"-Sentinel -- sonst wuerde der
        # Aenderungs-Waechter unten den allerersten Aufruf mit {} faelschlich
        # als "unveraendert" ueberspringen.
        self._last_custom_symbols_snapshot: dict[str, CustomSymbolDefinition] | None = None
        self._grid_visible_symbols: set[str] = set()
        self._rebuild_effective_documentation_symbols_if_changed({})
        self.pdf_exporter = PdfSeatingPlanExporter(self.symbol_definitions, color_palette=self.color_palette)
        if warning:
            self.status_var.set(warning)

        self.theme_var = ui.StringVar(value=self.theme_key)
        self.details_overlay_position_var = ui.StringVar(value=self.details_overlay_position)
        self.tablegroup_overlay_position_var = ui.StringVar(value=self.tablegroup_overlay_position)

        self._build_layout(frame)
        self._register_canvas_event_bindings()
        self._bind_shortcuts()
        self.bind("<Configure>", lambda _event: self._position_tablegroup_overlay(), add="+")
        self.after(DEFAULT_PERIODIC_BACKUP_INTERVAL_MS, self._periodic_backup_tick)
        self.after(DEFAULT_UI_WATCHDOG_INTERVAL_MS, self._ui_watchdog_tick)

        self._apply_kartograph_theme()
        self.after_idle(self._initialize_startup_view)
        LOGGER.info("Main window __init__ finished in %.3fs", time.perf_counter() - self._init_start_time)

    def open_settings(self) -> None:
        """Öffnet den Einstellungen-Dialog."""
        self._handle_intent(UiIntent.OPEN_SETTINGS)

    def apply_theme(self, theme_key: str | None = None) -> None:
        """Wechselt Theme und synchronisiert alle kartograph-spezifischen Flächen.

        Accepts an optional theme_key for BwBaseWindow compatibility (View menu radio).
        When called without arguments, re-applies the shell's current self.theme_key
        (``apply_state`` handles its own theme-change branch directly instead, so it
        does not re-trigger the persist step in this method).
        """
        if theme_key is not None:
            theme_key = normalize_theme_key(theme_key)
            BwBaseWindow.apply_theme(self, theme_key)  # updates self.theme_key via the shell
            self.theme_var.set(self.theme_key)
            self._on_theme_changed()  # persists via UpdateSettingsIntent; won't re-trigger (theme_key already set)
        else:
            BwBaseWindow.apply_theme(self, self.theme_key)
        self._apply_kartograph_theme()

    def _on_shell_close(self) -> bool:
        """Schließt Overlay-Fenster bevor die Shell das Root-Fenster zerstört."""
        try:
            self._flush_pending_name_save()
        except Exception:
            pass
        try:
            self._flush_pending_plan_save()
        except Exception:
            pass
        try:
            self._close_shortcut_runtime_debug_dialog()
        except Exception:
            pass
        try:
            self._close_tablegroup_overlay()
        except Exception:
            pass
        try:
            self._close_sitzplan_popup()
        except Exception:
            pass
        return True

    def _report_tk_callback_exception(self, exc_type, exc_value, exc_traceback) -> None:
        """Loggt nicht abgefangene Tkinter-Callback-Exceptions.

        Args:
            exc_type: Exception-Klasse.
            exc_value: Exception-Instanz.
            exc_traceback: Zugehöriger Traceback.
        """
        LOGGER.exception("Unhandled Tk callback exception", exc_info=(exc_type, exc_value, exc_traceback))

    def _initialize_startup_view(self) -> None:
        """Initialisiert die Startansicht nach dem Idle-Cycle.

        Zentriert das Fenster, lädt die Planliste und zeigt die Planlistenansicht.
        """
        started = time.perf_counter()
        LOGGER.info("Deferred startup view initialization started")
        try:
            self._center_window_on_screen()
            self.refresh_plan_list()
            self.show_plan_list_view()
        except Exception:
            LOGGER.exception("Deferred startup view initialization failed")
            raise
        LOGGER.info("Deferred startup view initialization finished in %.3fs", time.perf_counter() - started)

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

    def _center_window_on_screen(self) -> None:
        """Zentriert das Fenster auf dem Bildschirm nach dem ersten Layout-Durchgang."""
        self.update_idletasks()
        width = max(self.winfo_width(), 1000)
        height = max(self.winfo_height(), 680)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = max(0, (screen_width - width) // 2)
        y_pos = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
        LOGGER.info("Window centered to %dx%d at +%d+%d on screen %dx%d", width, height, x_pos, y_pos, screen_width, screen_height)

    def _ui_watchdog_tick(self) -> None:
        """Erkennt und loggt UI-Thread-Blockierungen durch Vergleich des Timer-Drifts."""
        now = time.perf_counter()
        expected_interval = DEFAULT_UI_WATCHDOG_INTERVAL_MS / 1000.0
        drift = max(0.0, now - self._ui_watchdog_last_tick - expected_interval)
        if drift > UI_WATCHDOG_WARN_DRIFT_SECONDS:
            LOGGER.warning(
                "UI watchdog detected delayed mainloop tick: drift=%.3fs mode=%s surface=%s plan=%s",
                drift, self.interaction_mode, self._editor_surface, self.current_plan_path,
            )
        self._ui_watchdog_last_tick = now
        self._ui_watchdog_tick_count += 1
        if self._ui_watchdog_tick_count % 60 == 0:
            LOGGER.info("UI watchdog heartbeat ok: mode=%s surface=%s plan=%s", self.interaction_mode, self._editor_surface, self.current_plan_path)
        self.after(DEFAULT_UI_WATCHDOG_INTERVAL_MS, self._ui_watchdog_tick)

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
        from bw_gui import ui as _ui
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
