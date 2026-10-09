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
from app.adapters.gui._mixin_snapshots import SnapshotsMixin
from app.adapters.gui._mixin_selection import SelectionMixin
from app.adapters.gui._mixin_settings import SettingsMixin
from app.adapters.gui._mixin_shortcut_handlers import ShortcutHandlersMixin
from app.adapters.gui._mixin_shortcut_bindings import ShortcutBindingsMixin
from app.adapters.gui._mixin_shortcuts import ShortcutMixin
from app.adapters.gui._mixin_tablegroup import TablegroupMixin
from app.adapters.gui._mixin_tablegroup_logic import TablegroupLogicMixin
from app.adapters.gui._mixin_theme import ThemeMixin
from app.adapters.gui._mixin_undo_redo import UndoRedoMixin
from app.adapters.gui._mixin_viewport import ViewportMixin
from app.adapters.gui._pending_field_save import PendingFieldSave
from app.adapters.gui.docs_table_model import DocColumnAxis, DocRow
from app.adapters.gui.main_window_constants import COLOR_MARKER_PALETTE, DEFAULT_CANVAS_RADIUS, DEFAULT_CELL_SIZE, DEFAULT_PERIODIC_BACKUP_INTERVAL_MS, DEFAULT_UI_WATCHDOG_INTERVAL_MS, LOGGER, DeskDetailMode, MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH, UI_WATCHDOG_WARN_DRIFT_SECONDS, _known_ui_intents, apply_window_icon, configure_windows_process_identity
from app.adapters.gui.ui_intents import UiIntent
from app.adapters.gui.ui_theme import normalize_theme_key
from app.application.app_controller import KartographAppController
from app.application.app_state import PlanListEntry
from app.core.domain.effective_symbol import EffectiveSymbol
from app.core.domain.models_v4 import CustomSymbolDefinition, SeatingPlan
from app.core.domain.plan_selection import RectSelection
from app.core.domain.settings import resolve_plans_dir
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter
from bw_libs.app_shell import AppShellConfig
from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from bw_libs.ui_contract.hsm import build_ui_hsm_contract
from bw_libs.ui_contract.keybinding import KeybindingRegistry
from bw_libs.ui_contract.popup import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry

ensure_bw_gui_on_path()
from bw_gui.contracts.screen_geometry import Size
from bw_gui.runtime.screen_placement import place_on_pointer_monitor
from bw_gui.runtime import BwBaseWindow, ui, widgets as tui
from bw_gui.menu import section_spec
from app.adapters.gui._mixin_state_apply import StateApplyMixin


class KartographMainWindow(
    StateApplyMixin,
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
    SnapshotsMixin,
    ShortcutHandlersMixin,
    ShortcutBindingsMixin,
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
        # Entitätsgebundene (StudentId) Pending Saves fürs Detail-Panel --
        # s. app/adapters/gui/_pending_field_save.py. Beide landen in
        # self._pending_edits, damit ein Kontextwechsel (Tischwechsel,
        # Panel schließen, Plan wechseln, App schließen) sie über den
        # einzigen zentralen Hook self._commit_pending_edits() (s.
        # _mixin_details.py) gebündelt und garantiert VOR dem eigentlichen
        # Kontextwechsel flushen kann, statt einzeln aufgezählt zu werden.
        self._name_pending_save = PendingFieldSave(
            self, capture=self._capture_name_fields, apply=self._apply_name_fields
        )
        self._accommodations_pending_save = PendingFieldSave(
            self, capture=self._capture_accommodations_field, apply=self._apply_accommodations_field
        )
        self._pending_edits: list[PendingFieldSave] = [
            self._name_pending_save,
            self._accommodations_pending_save,
        ]
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
        self._snapshot_window: ui.Toplevel | None = None
        self._snapshot_table: tui.Treeview | None = None
        self._snapshot_add_button: tui.Button | None = None
        self._snapshot_load_button: tui.Button | None = None
        self._snapshot_rename_button: tui.Button | None = None
        self._snapshot_delete_button: tui.Button | None = None
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
        self._doc_rows: dict[str, DocRow] = {}
        self._doc_axis: DocColumnAxis = DocColumnAxis((), ())
        self._doc_row_order: list[str] = []
        self._doc_date_column_ids: list[str] = []
        self._doc_fixed_column_ids: list[str] = []
        self._doc_selected_nondate_column_id: str | None = None
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
            self._commit_pending_edits()
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


    def _center_window_on_screen(self) -> None:
        """Zentriert das Fenster nach dem ersten Layout-Durchgang auf dem Monitor des Mauszeigers.

        Nutzt den Screen-Placement-Contract von bw-gui (Work-Area des Monitors unter
        dem Mauszeiger) statt ``winfo_screenwidth``, das unter Windows nur den
        Primärmonitor kennt.
        """
        self.update_idletasks()
        width = max(self.winfo_width(), 1000)
        height = max(self.winfo_height(), 680)
        self.geometry(f"{width}x{height}")
        position = place_on_pointer_monitor(self, size=Size(width, height))
        LOGGER.info("Window centered to %dx%d at %+d%+d", width, height, position.x, position.y)

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


