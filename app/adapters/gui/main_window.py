from __future__ import annotations

import logging
import tkinter as tk
import sys
import time
from copy import deepcopy
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

from app.app_info import APP_INFO
from app.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from app.adapters.gui.ui_intents import UiIntent
from bw_libs.app_shell import AppShellConfig, TkinterAppShell
from bw_libs.ui_contract.hsm import (
    ESCAPE_CLOSE_POPUP,
    ESCAPE_EXIT_INLINE_EDITOR,
    ESCAPE_POP_PARENT,
    build_ui_hsm_contract,
)
from bw_libs.ui_contract.keybinding import (
    UI_MODE_DIALOG,
    UI_MODE_EDITOR,
    UI_MODE_GLOBAL,
    UI_MODE_OFFLINE,
    UI_MODE_PREVIEW,
    KeyBindingDefinition,
    KeybindingRegistry,
    KeybindingRuntimeContext,
)
from bw_libs.ui_contract.popup import POPUP_KIND_MODAL, POPUP_KIND_NON_MODAL, PopupPolicy, PopupPolicyRegistry
from app.adapters.gui.ui_theme import THEMES, normalize_theme_key, theme_names
from app.core.domain.desk_clipboard import DeskClipboard
from app.core.domain.models import SeatingPlan
from app.core.domain.plan_history import PlanHistory
from app.core.domain.plan_selection import RectSelection
from app.core.domain.table_groups import (
    TG_ROTATION_LIMIT,
    TG_SHIFT_LIMIT,
    build_desk_geometries,
    detect_overlaps_for_tablegroup,
    get_tablegroup_settings,
    group_bounds_from_geometries,
    list_tablegroup_numbers,
    normalize_tablegroups_in_place,
    selection_bounds_from_geometries,
    set_tablegroup_number_with_cascade_in_place,
    set_tablegroup_transforms_in_place,
    tablegroup_number_at,
)
from app.core.usecases.plan_usecases import (
    add_grade_column,
    cleanup_unused_color_meanings,
    compute_grade_display_for_student,
    compute_grade_subtotal_display_for_student,
    create_student_desk,
    delete_desk,
    ensure_documentation_date,
    is_color_used,
    rename_documentation_date,
    set_color_meaning,
    set_documentation_grade,
    set_documentation_symbol,
    set_grade_weighting,
    set_teacher_desk,
    summarize_latest_symbols_for_student,
    toggle_color_marker,
    toggle_symbol,
    update_student_name,
)
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter
from app.infrastructure.symbol_config_loader import SymbolDefinition, load_symbol_definitions

MAX_CANVAS_RADIUS = 50
MIN_CANVAS_RADIUS = 1
DEFAULT_CANVAS_RADIUS = 50
DEFAULT_CELL_SIZE = 92
DEFAULT_SYMBOL_STRENGTH = 1
DEFAULT_VIEWPORT_FOLLOW_BUFFER = 0
DEFAULT_PERIODIC_BACKUP_INTERVAL_MS = 5 * 60 * 1000
DEFAULT_UI_WATCHDOG_INTERVAL_MS = 1000
UI_WATCHDOG_WARN_DRIFT_SECONDS = 2.5
DEFAULT_DETAILS_OVERLAY_POSITION = "bottom"
DEFAULT_TABLEGROUP_OVERLAY_POSITION = "right"
LIST_ACTIVE = "list_active"
GRID_SELECTED = "grid_selected"
NAME_EDITING = "name_editing"

COLOR_MARKER_PALETTE: list[tuple[str, str, str, str]] = [
    ("1", "gelb", "Gelb", "#f4d35e"),
    ("2", "orange", "Orange", "#ee964b"),
    ("3", "rot", "Rot", "#f95738"),
    ("4", "magenta", "Magenta", "#d81159"),
    ("5", "lila", "Lila", "#7b2cbf"),
    ("6", "marine", "Marine", "#1d3557"),
    ("7", "cyan", "Cyan", "#4cc9f0"),
    ("8", "tuerkis", "Tuerkis", "#2a9d8f"),
    ("9", "gruen", "Gruen", "#6a994e"),
]

APP_USER_MODEL_ID = "7thCloud.Kartograph"
ICON_PATH = Path(__file__).resolve().parents[3] / "assets" / "kartograph.ico"
LOGGER = logging.getLogger("kartograph.ui")

GRID_ONLY_INTENTS = {
    UiIntent.DELETE_DESK,
    UiIntent.SET_TEACHER_DESK,
    UiIntent.ADD_SYMBOL,
    UiIntent.OPEN_TABLEGROUP_SETTINGS,
    UiIntent.MOVE_UP,
    UiIntent.MOVE_DOWN,
    UiIntent.MOVE_LEFT,
    UiIntent.MOVE_RIGHT,
    UiIntent.EXPAND_UP,
    UiIntent.EXPAND_DOWN,
    UiIntent.EXPAND_LEFT,
    UiIntent.EXPAND_RIGHT,
    UiIntent.ZOOM_IN,
    UiIntent.ZOOM_OUT,
    UiIntent.RESET_VIEW,
}

DOCS_ONLY_INTENTS = {
    UiIntent.RENAME_DOCUMENTATION_DATE,
    UiIntent.ADD_GRADE_COLUMN,
}


def _known_ui_intents() -> tuple[str, ...]:
    """Return all declared UiIntent string values."""

    values: list[str] = []
    for key, value in UiIntent.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, str):
            values.append(value)
    return tuple(sorted(set(values)))


def configure_windows_process_identity() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        return


def apply_window_icon(window: tk.Tk) -> None:
    if not sys.platform.startswith("win") or not ICON_PATH.exists():
        return
    try:
        window.iconbitmap(default=str(ICON_PATH))
    except Exception:
        return


class KartographMainWindow(tk.Tk):
    def __init__(
        self,
        settings_repository,
        plan_repository,
        default_plans_dir: Path,
        symbols_path: Path,
        shell_config: AppShellConfig | None = None,
    ):
        startup_started = time.perf_counter()
        super().__init__()
        LOGGER.info("Main window __init__ start")
        configure_windows_process_identity()
        resolved_shell_config = shell_config or AppShellConfig(
            title=APP_INFO.window_title,
            geometry="1320x860",
            min_width=1000,
            min_height=680,
        )
        self.app_shell = TkinterAppShell(self, resolved_shell_config, on_close=self._on_shell_close)
        apply_window_icon(self)
        self.report_callback_exception = self._report_tk_callback_exception

        self.settings_repository = settings_repository
        self.plan_repository = plan_repository
        self.default_plans_dir = default_plans_dir
        self.symbols_path = symbols_path

        self.current_plan_path: Path | None = None
        self.current_plan: SeatingPlan | None = None
        self.selected_cell: tuple[int, int] = (0, 0)
        self.selection = RectSelection(0, 0)
        self._drag_active = False
        self.cell_size = DEFAULT_CELL_SIZE
        self._plan_index: list[tuple[Path, SeatingPlan]] = []
        self.interaction_mode = LIST_ACTIVE
        self.history = PlanHistory(max_undo_steps=20)
        self._plan_list_undo_actions: list[dict[str, object]] = []
        self._plan_list_redo_actions: list[dict[str, object]] = []
        self._desk_clipboard = DeskClipboard()

        self._settings = self.settings_repository.load_settings()
        self.plans_dir = Path(self._settings.get("plans_dir") or self.default_plans_dir)
        self.theme_key = normalize_theme_key(self._settings.get("theme"))
        self.canvas_radius = self._normalize_canvas_radius(self._settings.get("canvas_radius"))
        self.symbol_strength = self._normalize_symbol_strength(self._settings.get("symbol_strength"))
        self.viewport_follow_buffer = self._normalize_viewport_follow_buffer(
            self._settings.get("viewport_follow_buffer")
        )
        self.details_overlay_position = self._normalize_details_overlay_position(
            self._settings.get("details_overlay_position")
        )
        self.tablegroup_overlay_position = self._normalize_tablegroup_overlay_position(
            self._settings.get("tablegroup_overlay_position")
        )

        self.ui_intent_controller = MainWindowUiIntentController(self)
        self._hsm_contract = build_ui_hsm_contract(intents=_known_ui_intents())

        self._name_var = tk.StringVar(value="")
        self._selected_marker_var = tk.StringVar(value="")
        self._doc_selection_status_var = tk.StringVar(value="Doku-Zelle: -")
        self.status_var = tk.StringVar(value="Bereit")
        self._runtime_shortcuts = KeybindingRegistry()
        self._popup_registry = PopupPolicyRegistry()
        self._popup_registry.register_policy(PopupPolicy(policy_id="dialog.modal", kind=POPUP_KIND_MODAL))
        self._popup_registry.register_policy(
            PopupPolicy(
                policy_id="dialog.non_blocking",
                kind=POPUP_KIND_NON_MODAL,
                trap_focus=False,
                affects_mode=False,
            )
        )
        self._tracked_popup_ids: set[str] = set()
        self._shortcut_runtime_offline = False
        self._shortcut_runtime_debug_window: tk.Toplevel | None = None
        self._shortcut_runtime_debug_table: ttk.Treeview | None = None
        self._shortcut_runtime_debug_context_var = tk.StringVar(value="")
        self._shortcut_runtime_debug_summary_var = tk.StringVar(value="")
        self._shortcut_runtime_debug_offline_var = tk.BooleanVar(value=False)
        self._tablegroup_overlay: tk.Toplevel | None = None
        self._tg_number_var: tk.StringVar | None = None
        self._tg_shift_x_var: tk.StringVar | None = None
        self._tg_shift_y_var: tk.StringVar | None = None
        self._tg_rotation_var: tk.StringVar | None = None
        self._tg_status_var: tk.StringVar | None = None
        self._tg_last_changed_field: str = "shift_x"
        self._color_marker_buttons: list[tk.Button] = []
        self._editor_surface: str = "grid"
        self._doc_selected_student_index: int = 0
        self._doc_selected_date_index: int = 0
        self._doc_student_coords: list[tuple[int, int]] = []
        self._doc_dates: list[str] = []
        self._doc_tree_iid_by_student_index: dict[int, str] = {}
        self._doc_student_index_by_iid: dict[str, int] = {}
        self._doc_date_column_ids: list[str] = []
        self._doc_fixed_column_ids: list[str] = []
        self._doc_selected_fixed_column_id: str | None = None
        self._docs_inline_editor: ttk.Entry | None = None
        self._docs_inline_editor_tree: ttk.Treeview | None = None
        self._docs_inline_editor_row_id: str | None = None
        self._docs_inline_editor_kind: str | None = None
        self._docs_inline_editor_model_column: str | None = None
        self._docs_cell_overlay: tk.Label | None = None
        self._docs_symbol_dialog_last_index: int = 0
        self._ui_watchdog_last_tick = time.perf_counter()
        self._ui_watchdog_tick_count = 0

        self.color_palette = COLOR_MARKER_PALETTE
        self._color_by_key = {color_key: (label, hex_color) for _key, color_key, label, hex_color in self.color_palette}

        self.symbol_definitions, warning = self._load_symbols()
        self.symbol_catalog = [item.meaning for item in self.symbol_definitions]
        self.diagnostic_symbol_catalog = [item.meaning for item in self.symbol_definitions if item.role == "diagnostic"]
        self._documentation_only_symbols = {
            item.meaning for item in self.symbol_definitions if item.role == "documentation_only"
        }
        self._symbol_by_meaning = {item.meaning: item for item in self.symbol_definitions}
        self._shortcut_to_symbol = self._build_symbol_shortcut_map(self.symbol_definitions)
        self._grid_visible_symbols = self._normalize_grid_visible_symbols(
            self._settings.get("grid_visible_symbols"),
            self.symbol_catalog,
        )
        self.pdf_exporter = PdfSeatingPlanExporter(self.symbol_definitions)
        if warning:
            self.status_var.set(warning)

        self._build_menu_bar()
        self._build_layout()
        self._bind_shortcuts()
        self.bind("<Configure>", lambda _event: self._position_tablegroup_overlay(), add="+")
        self.after(DEFAULT_PERIODIC_BACKUP_INTERVAL_MS, self._periodic_backup_tick)
        self.after(DEFAULT_UI_WATCHDOG_INTERVAL_MS, self._ui_watchdog_tick)

        self.apply_theme()
        self.after_idle(self._initialize_startup_view)
        LOGGER.info("Main window __init__ finished in %.3fs", time.perf_counter() - startup_started)

    def _on_shell_close(self) -> bool:
        """Close tracked overlays before the shell destroys the root window."""

        try:
            self._close_shortcut_runtime_debug_dialog()
        except Exception:
            pass

        try:
            self._close_tablegroup_overlay()
        except Exception:
            pass

        return True

    def _report_tk_callback_exception(self, exc_type, exc_value, exc_traceback) -> None:
        LOGGER.exception(
            "Unhandled Tk callback exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _initialize_startup_view(self) -> None:
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
        self.update_idletasks()
        width = max(self.winfo_width(), 1000)
        height = max(self.winfo_height(), 680)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_pos = max(0, (screen_width - width) // 2)
        y_pos = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
        LOGGER.info(
            "Window centered to %dx%d at +%d+%d on screen %dx%d",
            width,
            height,
            x_pos,
            y_pos,
            screen_width,
            screen_height,
        )

    def _ui_watchdog_tick(self) -> None:
        now = time.perf_counter()
        expected_interval = DEFAULT_UI_WATCHDOG_INTERVAL_MS / 1000.0
        drift = max(0.0, now - self._ui_watchdog_last_tick - expected_interval)
        if drift > UI_WATCHDOG_WARN_DRIFT_SECONDS:
            LOGGER.warning(
                "UI watchdog detected delayed mainloop tick: drift=%.3fs mode=%s surface=%s plan=%s",
                drift,
                self.interaction_mode,
                self._editor_surface,
                self.current_plan_path,
            )

        self._ui_watchdog_last_tick = now
        self._ui_watchdog_tick_count += 1
        if self._ui_watchdog_tick_count % 60 == 0:
            LOGGER.info(
                "UI watchdog heartbeat ok: mode=%s surface=%s plan=%s",
                self.interaction_mode,
                self._editor_surface,
                self.current_plan_path,
            )

        self.after(DEFAULT_UI_WATCHDOG_INTERVAL_MS, self._ui_watchdog_tick)

    def _build_menu_bar(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Neu (Strg+N)", command=lambda: self._handle_intent(UiIntent.NEW_PLAN))
        file_menu.add_command(
            label="Plan umbenennen (F2)",
            command=lambda: self._handle_intent(UiIntent.RENAME_SELECTED_PLAN),
        )
        file_menu.add_command(
            label="Plan loeschen (Entf in Liste)",
            command=lambda: self._handle_intent(UiIntent.DELETE_SELECTED_PLAN),
        )
        file_menu.add_command(
            label="Plan duplizieren (Strg+D)",
            command=lambda: self._handle_intent(UiIntent.DUPLICATE_SELECTED_PLAN),
        )
        file_menu.add_separator()
        file_menu.add_command(label="Export PDF (Strg+E)", command=lambda: self._handle_intent(UiIntent.EXPORT_PDF))
        file_menu.add_command(label="Einstellungen (Strg+,)", command=lambda: self._handle_intent(UiIntent.OPEN_SETTINGS))
        file_menu.add_separator()
        file_menu.add_command(label="Zur Planliste", command=lambda: self._handle_intent(UiIntent.GO_TO_LIST))
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.destroy)
        menubar.add_cascade(label="Datei", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="Rueckgaengig (Strg+Z)", command=lambda: self._handle_intent(UiIntent.UNDO))
        edit_menu.add_command(label="Wiederholen (Strg+Y)", command=lambda: self._handle_intent(UiIntent.REDO))
        edit_menu.add_command(label="Letzte 5 rueckgaengig", command=lambda: self._handle_intent(UiIntent.UNDO_LAST_FIVE))
        edit_menu.add_separator()
        edit_menu.add_command(label="Ausschneiden (Strg+X)", command=lambda: self._handle_intent(UiIntent.CUT))
        edit_menu.add_command(label="Kopieren (Strg+C)", command=lambda: self._handle_intent(UiIntent.COPY))
        edit_menu.add_command(label="Einfuegen (Strg+V)", command=lambda: self._handle_intent(UiIntent.PASTE))
        menubar.add_cascade(label="Bearbeiten", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=False)
        self.theme_var = tk.StringVar(value=self.theme_key)
        for key in theme_names():
            label = THEMES[key].get("label", key)
            view_menu.add_radiobutton(label=label, value=key, variable=self.theme_var, command=self._on_theme_changed)
        view_menu.add_separator()
        view_menu.add_command(
            label="Dokumentationssicht umschalten (Strg+Shift+D)",
            command=lambda: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION),
        )
        view_menu.add_command(
            label="Shortcut-Runtime-Debug anzeigen (Strg+Shift+R)",
            command=lambda: self._handle_intent(UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG),
        )
        view_menu.add_command(
            label="Offline-Simulation umschalten (Strg+Shift+O)",
            command=lambda: self._handle_intent(UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE),
        )
        view_menu.add_separator()
        view_menu.add_command(label="Tisch-Overlay (S:S)", state="disabled")
        self.details_overlay_position_var = tk.StringVar(value=self.details_overlay_position)
        view_menu.add_radiobutton(
            label="Links",
            value="left",
            variable=self.details_overlay_position_var,
            command=self._on_details_overlay_position_changed,
        )
        view_menu.add_radiobutton(
            label="Rechts",
            value="right",
            variable=self.details_overlay_position_var,
            command=self._on_details_overlay_position_changed,
        )
        view_menu.add_radiobutton(
            label="Unten",
            value="bottom",
            variable=self.details_overlay_position_var,
            command=self._on_details_overlay_position_changed,
        )
        view_menu.add_separator()
        view_menu.add_command(label="Tischgruppen-Overlay", state="disabled")
        self.tablegroup_overlay_position_var = tk.StringVar(value=self.tablegroup_overlay_position)
        view_menu.add_radiobutton(
            label="Links (Tischgruppen)",
            value="left",
            variable=self.tablegroup_overlay_position_var,
            command=self._on_tablegroup_overlay_position_changed,
        )
        view_menu.add_radiobutton(
            label="Rechts (Tischgruppen)",
            value="right",
            variable=self.tablegroup_overlay_position_var,
            command=self._on_tablegroup_overlay_position_changed,
        )
        view_menu.add_radiobutton(
            label="Unten (Tischgruppen)",
            value="bottom",
            variable=self.tablegroup_overlay_position_var,
            command=self._on_tablegroup_overlay_position_changed,
        )
        menubar.add_cascade(label="Ansicht", menu=view_menu)

        self.config(menu=menubar)

    def _build_layout(self) -> None:
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

        self.list_view = ttk.Frame(self.main_frame)
        self.editor_view = ttk.Frame(self.main_frame)

        self._build_list_view()
        self._build_editor_view()

    def _build_list_view(self) -> None:
        self.list_toolbar = ttk.Frame(self.list_view)
        self.list_toolbar.pack(fill="x", padx=14, pady=(14, 8))

        ttk.Button(
            self.list_toolbar,
            text="Neuer Sitzplan (Strg+N)",
            command=lambda: self._handle_intent(UiIntent.NEW_PLAN),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            self.list_toolbar,
            text="Öffnen (Enter)",
            command=lambda: self._handle_intent(UiIntent.LIST_OPEN_SELECTED),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            self.list_toolbar,
            text="Umbenennen (F2)",
            command=lambda: self._handle_intent(UiIntent.RENAME_SELECTED_PLAN),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            self.list_toolbar,
            text="Löschen (Entf)",
            command=lambda: self._handle_intent(UiIntent.DELETE_SELECTED_PLAN),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            self.list_toolbar,
            text="Duplizieren (Strg+D)",
            command=lambda: self._handle_intent(UiIntent.DUPLICATE_SELECTED_PLAN),
        ).pack(side="left")

        self.list_body = ttk.Frame(self.list_view)
        self.list_body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.plan_listbox = tk.Listbox(
            self.list_body,
            selectmode="browse",
            activestyle="none",
            font=("Segoe UI", 12),
            exportselection=False,
            borderwidth=1,
        )
        self.plan_listbox.pack(side="left", fill="both", expand=True)
        self.plan_listbox.bind("<Double-Button-1>", lambda _event: self._handle_intent(UiIntent.LIST_OPEN_SELECTED))
        self.plan_listbox.bind("<Return>", lambda _event: self._handle_intent(UiIntent.LIST_OPEN_SELECTED))
        self.plan_listbox.bind("<<ListboxSelect>>", lambda _event: self._ensure_list_selection())

        scroll = ttk.Scrollbar(self.list_body, orient="vertical", command=self.plan_listbox.yview)
        scroll.pack(side="right", fill="y")
        self.plan_listbox.configure(yscrollcommand=scroll.set)

    def _build_editor_view(self) -> None:
        self.editor_topbar = ttk.Frame(self.editor_view)
        self.editor_topbar.pack(fill="x", padx=12, pady=(12, 8))

        go_to_list_button = ttk.Button(
            self.editor_topbar,
            text="Zur Liste",
            command=lambda: self._handle_intent(UiIntent.GO_TO_LIST),
        )
        go_to_list_button.pack(side="left")
        self._bind_editor_return_override(go_to_list_button)

        delete_button = ttk.Button(
            self.editor_topbar,
            text="Platz löschen (Entf)",
            command=lambda: self._handle_intent(UiIntent.DELETE_DESK),
        )
        delete_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(delete_button)

        add_symbol_button = ttk.Button(
            self.editor_topbar,
            text="Symbol hinzufügen",
            command=lambda: self._handle_intent(UiIntent.ADD_SYMBOL),
        )
        add_symbol_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(add_symbol_button)

        tablegroup_button = ttk.Button(
            self.editor_topbar,
            text="Tischeinstellungen (Strg+T)",
            command=lambda: self._handle_intent(UiIntent.OPEN_TABLEGROUP_SETTINGS),
        )
        tablegroup_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(tablegroup_button)

        export_pdf_button = ttk.Button(
            self.editor_topbar,
            text="PDF exportieren",
            command=lambda: self._handle_intent(UiIntent.EXPORT_PDF),
        )
        export_pdf_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(export_pdf_button)

        set_teacher_button = ttk.Button(
            self.editor_topbar,
            text="Als Lehrertisch setzen (Strg+Enter)",
            command=lambda: self._handle_intent(UiIntent.SET_TEACHER_DESK),
        )
        set_teacher_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(set_teacher_button)

        docs_toggle_button = ttk.Button(
            self.editor_topbar,
            text="Dokuansicht (Strg+Shift+D)",
            command=lambda: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION),
        )
        docs_toggle_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(docs_toggle_button)

        grid_filter_button = ttk.Button(
            self.editor_topbar,
            text="Symbole filtern",
            command=self.open_grid_symbol_filter_dialog,
        )
        grid_filter_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(grid_filter_button)

        zoom_in_button = ttk.Button(
            self.editor_topbar,
            text="Zoom + (Strg++)",
            command=lambda: self._handle_intent(UiIntent.ZOOM_IN),
        )
        zoom_in_button.pack(side="right")
        self._bind_editor_return_override(zoom_in_button)

        zoom_out_button = ttk.Button(
            self.editor_topbar,
            text="Zoom - (Strg+-)",
            command=lambda: self._handle_intent(UiIntent.ZOOM_OUT),
        )
        zoom_out_button.pack(side="right", padx=(0, 8))
        self._bind_editor_return_override(zoom_out_button)

        self.plan_name_var = tk.StringVar(value="")
        ttk.Label(self.editor_topbar, textvariable=self.plan_name_var).pack(side="right", padx=(0, 14))

        self.grid_stack = ttk.Frame(self.editor_view)
        self.grid_container = ttk.Frame(self.grid_stack)

        self.canvas = tk.Canvas(self.grid_container, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.y_scroll = tk.Scrollbar(
            self.grid_container,
            orient="vertical",
            command=self._yview,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            takefocus=0,
        )
        self.y_scroll.pack(side="right", fill="y")
        self.x_scroll = tk.Scrollbar(
            self.grid_stack,
            orient="horizontal",
            command=self._xview,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            takefocus=0,
        )
        self.x_scroll.pack(fill="x")

        self.canvas.configure(
            xscrollcommand=lambda a, b: self._on_canvas_xscroll(a, b),
            yscrollcommand=lambda a, b: self._on_canvas_yscroll(a, b),
        )
        self._update_scroll_region()

        self.details_container = ttk.Frame(self.editor_view, style="Panel.TFrame")

        self.details_header = ttk.Frame(self.details_container, style="Panel.TFrame")
        self.details_header.pack(fill="x", padx=12, pady=(8, 0))

        ttk.Label(self.details_header, textvariable=self.status_var, style="Panel.TLabel").pack(side="left")
        ttk.Label(self.details_header, textvariable=self._selected_marker_var, style="Panel.TLabel").pack(side="right")

        self.details_frame = ttk.Frame(self.details_container)
        self.details_frame.pack(fill="x", padx=12, pady=(4, 12))

        self.details_form = ttk.Frame(self.details_frame, style="Panel.TFrame")
        self.details_form.pack(fill="x", pady=(4, 0))

        ttk.Label(self.details_form, text="Name", style="Panel.TLabel").pack(side="left")
        self.name_entry = ttk.Entry(self.details_form, textvariable=self._name_var, width=40)
        self.name_entry.pack(side="left", padx=(8, 16))
        self.name_entry.bind("<KeyRelease>", lambda _event: self._on_name_changed())
        self.name_entry.bind("<Escape>", self._on_name_entry_escape)
        self.name_entry.bind("<Return>", self._on_name_entry_return)
        self.name_entry.bind("<FocusIn>", self._on_name_entry_focus_in)
        self.name_entry.bind("<FocusOut>", self._on_name_entry_focus_out)

        self.symbols_frame = ttk.Frame(self.details_frame, style="Panel.TFrame")
        self.symbols_frame.pack(fill="x", pady=(6, 0))

        self.symbol_legend_frame = ttk.Frame(self.details_frame, style="Panel.TFrame")
        self.symbol_legend_frame.pack(fill="x", pady=(4, 0))

        self.colors_frame = ttk.Frame(self.details_frame, style="Panel.TFrame")
        self.colors_frame.pack(fill="x", pady=(6, 0))

        self.color_legend_frame = ttk.Frame(self.details_frame, style="Panel.TFrame")
        self.color_legend_frame.pack(fill="x", pady=(4, 0))
        self._details_panel_visible = True

        self._apply_details_overlay_position()

        self.docs_container = ttk.Frame(self.editor_view)

        self.docs_toolbar = ttk.Frame(self.docs_container)
        self.docs_toolbar.pack(fill="x", padx=12, pady=(0, 8))

        ttk.Button(
            self.docs_toolbar,
            text="Zur Rasteransicht",
            command=lambda: self._handle_intent(UiIntent.VIEW_GRID),
        ).pack(side="left")
        ttk.Button(
            self.docs_toolbar,
            text="Datum umbenennen",
            command=lambda: self._handle_intent(UiIntent.RENAME_DOCUMENTATION_DATE),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Heute",
            command=self.select_today_documentation_date,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Notenspalte hinzufügen",
            command=lambda: self._handle_intent(UiIntent.ADD_GRADE_COLUMN),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Gewichtung",
            command=self.configure_grade_weighting_dialog,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Symbol setzen",
            command=self.set_selected_documentation_symbol_dialog,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Symbol loeschen (Strg+Entf/Backspace)",
            command=self.clear_selected_documentation_symbol,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Note setzen (Strg+G)",
            command=self.set_selected_documentation_grade_dialog,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(
            self.docs_toolbar,
            text="Datum: Alt+Links/Rechts, Strg+H=Heute, Strg+Shift+S=Symbol, Strg+Entf/Backspace=Loeschen",
        ).pack(
            side="right", padx=(0, 12)
        )
        ttk.Label(self.docs_toolbar, textvariable=self._doc_selection_status_var).pack(side="right", padx=(0, 12))

        self.docs_table_container = ttk.Frame(self.docs_container)
        self.docs_table_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.docs_tree = ttk.Treeview(self.docs_table_container, show="tree headings")
        self.docs_tree.pack(side="left", fill="both", expand=True)
        self.docs_tree.column("#0", width=220, anchor="w", stretch=False)
        self.docs_tree.heading("#0", text="Schüler:in")

        self.docs_right_tree = ttk.Treeview(self.docs_table_container, show="headings")
        self.docs_right_tree.pack(side="left", fill="y")

        self.docs_y_scroll = ttk.Scrollbar(self.docs_table_container, orient="vertical", command=self._docs_yview)
        self.docs_y_scroll.pack(side="right", fill="y")
        self.docs_x_scroll = ttk.Scrollbar(self.docs_container, orient="horizontal", command=self.docs_tree.xview)
        self.docs_x_scroll.pack(fill="x", padx=12, pady=(0, 12))
        self._syncing_docs_scroll = False
        self._syncing_docs_selection = False
        self.docs_tree.configure(yscrollcommand=self._on_docs_main_yscroll, xscrollcommand=self.docs_x_scroll.set)
        self.docs_right_tree.configure(yscrollcommand=self._on_docs_right_yscroll)

        self.docs_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_docs_tree_select())
        self.docs_tree.bind("<Button-1>", self._on_docs_tree_click)
        self.docs_tree.bind("<Left>", lambda _event: self._on_docs_horizontal_nav(-1))
        self.docs_tree.bind("<Right>", lambda _event: self._on_docs_horizontal_nav(1))
        self.docs_tree.bind("<MouseWheel>", lambda _event: self.after_idle(self._update_docs_cell_highlight))
        self.docs_right_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_docs_right_tree_select())
        self.docs_right_tree.bind("<Button-1>", self._on_docs_right_tree_click)
        self.docs_right_tree.bind("<Double-Button-1>", self._on_docs_right_tree_double_click)
        self.docs_right_tree.bind("<Left>", lambda _event: self._on_docs_horizontal_nav(-1))
        self.docs_right_tree.bind("<Right>", lambda _event: self._on_docs_horizontal_nav(1))
        self.docs_right_tree.bind("<MouseWheel>", lambda _event: self.after_idle(self._update_docs_cell_highlight))

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<Configure>", lambda _event: self.redraw_grid())
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mouse_wheel)

    def _bind_shortcuts(self) -> None:
        self._bind_runtime_shortcut("<Control-n>", lambda _event: self._handle_intent(UiIntent.NEW_PLAN), binding_id="global.new", intent=UiIntent.NEW_PLAN, modes=(UI_MODE_GLOBAL, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-d>", self._on_duplicate_shortcut, binding_id="global.duplicate", intent=UiIntent.DUPLICATE_SELECTED_PLAN, modes=(UI_MODE_GLOBAL,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<F2>", self._on_rename_shortcut, binding_id="global.rename", intent=UiIntent.RENAME_SELECTED_PLAN, modes=(UI_MODE_GLOBAL,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-e>", lambda _event: self._handle_intent(UiIntent.EXPORT_PDF), binding_id="global.export", intent=UiIntent.EXPORT_PDF, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-comma>", lambda _event: self._handle_intent(UiIntent.OPEN_SETTINGS), binding_id="global.settings.comma", intent=UiIntent.OPEN_SETTINGS, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-,>", lambda _event: self._handle_intent(UiIntent.OPEN_SETTINGS), binding_id="global.settings.comma.alt", intent=UiIntent.OPEN_SETTINGS, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-0>", lambda _event: self._handle_intent(UiIntent.RESET_VIEW), binding_id="viewport.reset", intent=UiIntent.RESET_VIEW, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Return>", lambda _event: self._handle_intent(UiIntent.SET_TEACHER_DESK), binding_id="desk.teacher", intent=UiIntent.SET_TEACHER_DESK, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-KP_Enter>", lambda _event: self._handle_intent(UiIntent.SET_TEACHER_DESK), binding_id="desk.teacher.numpad", intent=UiIntent.SET_TEACHER_DESK, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-plus>", lambda _event: self._handle_intent(UiIntent.ZOOM_IN), binding_id="viewport.zoom.in", intent=UiIntent.ZOOM_IN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-equal>", lambda _event: self._handle_intent(UiIntent.ZOOM_IN), binding_id="viewport.zoom.in.equal", intent=UiIntent.ZOOM_IN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-KP_Add>", lambda _event: self._handle_intent(UiIntent.ZOOM_IN), binding_id="viewport.zoom.in.numpad", intent=UiIntent.ZOOM_IN, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-minus>", lambda _event: self._handle_intent(UiIntent.ZOOM_OUT), binding_id="viewport.zoom.out", intent=UiIntent.ZOOM_OUT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-KP_Subtract>", lambda _event: self._handle_intent(UiIntent.ZOOM_OUT), binding_id="viewport.zoom.out.numpad", intent=UiIntent.ZOOM_OUT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-z>", lambda _event: self._handle_intent(UiIntent.UNDO), binding_id="edit.undo", intent=UiIntent.UNDO, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-y>", lambda _event: self._handle_intent(UiIntent.REDO), binding_id="edit.redo", intent=UiIntent.REDO, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-t>", lambda _event: self._handle_intent(UiIntent.OPEN_TABLEGROUP_SETTINGS), binding_id="tablegroup.settings", intent=UiIntent.OPEN_TABLEGROUP_SETTINGS, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-D>", lambda _event: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION), binding_id="view.docs.toggle", intent=UiIntent.TOGGLE_DOCUMENTATION, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-d>", lambda _event: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION), binding_id="view.docs.toggle.lower", intent=UiIntent.TOGGLE_DOCUMENTATION, modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-r>", lambda _event: self._handle_intent(UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG), binding_id="debug.runtime.open", intent=UiIntent.OPEN_SHORTCUT_RUNTIME_DEBUG, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-Shift-o>", lambda _event: self._handle_intent(UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE), binding_id="debug.runtime.offline", intent=UiIntent.TOGGLE_SHORTCUT_RUNTIME_OFFLINE, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-g>", self._on_set_grade_shortcut, binding_id="docs.grade", intent="docs.grade", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-S>", self._on_set_symbol_shortcut, binding_id="docs.symbol", intent="docs.symbol", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Shift-s>", self._on_set_symbol_shortcut, binding_id="docs.symbol.lower", intent="docs.symbol.lower", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-Delete>", self._on_clear_symbol_shortcut, binding_id="docs.clear", intent="docs.clear", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-BackSpace>", self._on_clear_symbol_shortcut, binding_id="docs.clear.backspace", intent="docs.clear.backspace", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-h>", self._on_docs_today_shortcut, binding_id="docs.today", intent="docs.today", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Alt-Left>", self._on_docs_prev_date_shortcut, binding_id="docs.prev", intent="docs.prev", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Alt-Right>", self._on_docs_next_date_shortcut, binding_id="docs.next", intent="docs.next", modes=(UI_MODE_PREVIEW,), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Control-x>", lambda _event: self._handle_intent(UiIntent.CUT), binding_id="edit.cut", intent=UiIntent.CUT, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-c>", lambda _event: self._handle_intent(UiIntent.COPY), binding_id="edit.copy", intent=UiIntent.COPY, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Control-v>", lambda _event: self._handle_intent(UiIntent.PASTE), binding_id="edit.paste", intent=UiIntent.PASTE, modes=(UI_MODE_PREVIEW,), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Delete>", self._on_delete_key, binding_id="global.delete", intent="global.delete", modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW), allow_when_text_input=False)
        self._bind_runtime_shortcut("<Escape>", lambda _event: self._handle_intent(UiIntent.ESCAPE), binding_id="global.escape", intent=UiIntent.ESCAPE, modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<Return>", self._on_return_key, binding_id="global.return", intent="global.return", modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)
        self._bind_runtime_shortcut("<KP_Enter>", self._on_return_key, binding_id="global.return.numpad", intent="global.return.numpad", modes=(UI_MODE_GLOBAL, UI_MODE_PREVIEW, UI_MODE_DIALOG), allow_when_text_input=True)

        self.canvas.bind("<Up>", lambda _event: self._handle_intent(UiIntent.MOVE_UP))
        self.canvas.bind("<Down>", lambda _event: self._handle_intent(UiIntent.MOVE_DOWN))
        self.canvas.bind("<Left>", lambda _event: self._handle_intent(UiIntent.MOVE_LEFT))
        self.canvas.bind("<Right>", lambda _event: self._handle_intent(UiIntent.MOVE_RIGHT))
        self.canvas.bind("<Shift-Up>", lambda _event: self._handle_intent(UiIntent.EXPAND_UP))
        self.canvas.bind("<Shift-Down>", lambda _event: self._handle_intent(UiIntent.EXPAND_DOWN))
        self.canvas.bind("<Shift-Left>", lambda _event: self._handle_intent(UiIntent.EXPAND_LEFT))
        self.canvas.bind("<Shift-Right>", lambda _event: self._handle_intent(UiIntent.EXPAND_RIGHT))

        for shortcut, symbol_name in self._shortcut_to_symbol.items():
            self.bind_all(f"<KeyPress-{shortcut}>", lambda event, s=symbol_name: self._on_symbol_shortcut(event, s), add="+")
            self.bind_all(
                f"<KeyPress-{shortcut.upper()}>",
                lambda event, s=symbol_name: self._on_symbol_shortcut(event, s),
                add="+",
            )

        for key, _color_key, _label, _hex_color in self.color_palette:
            self.bind_all(f"<KeyPress-{key}>", lambda event, color_key=_color_key: self._on_color_shortcut(event, color_key), add="+")

    def _register_runtime_shortcut(
        self,
        *,
        binding_id: str,
        sequence: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
    ) -> KeyBindingDefinition:
        intent_ok, _intent_reason = self._hsm_contract.validate_intent(intent)
        if not intent_ok:
            raise ValueError(f"Unknown runtime shortcut intent: {intent}")

        definition = KeyBindingDefinition(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )
        self._runtime_shortcuts.register(definition)
        return definition

    def _track_popup_window(self, window: tk.Toplevel, *, policy_id: str = "dialog.modal") -> None:
        popup_id = str(window)
        if popup_id in self._tracked_popup_ids:
            return
        self._popup_registry.open_popup(popup_id=popup_id, title=str(window.title() or ""), policy_id=policy_id)
        self._tracked_popup_ids.add(popup_id)

    def _sync_popup_sessions_from_windows(self) -> None:
        visible_popup_ids: set[str] = set()
        for child in self.winfo_children():
            if not isinstance(child, tk.Toplevel):
                continue
            try:
                if not int(child.winfo_exists()):
                    continue
                if str(child.state()).lower() == "withdrawn":
                    continue
            except Exception:
                continue

            popup_id = str(child)
            visible_popup_ids.add(popup_id)
            if popup_id in self._tracked_popup_ids:
                continue
            self._popup_registry.open_popup(popup_id=popup_id, title=str(child.title() or ""), policy_id="dialog.modal")
            self._tracked_popup_ids.add(popup_id)

        stale_ids = self._tracked_popup_ids - visible_popup_ids
        for popup_id in tuple(stale_ids):
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)

    def _build_runtime_context(self, event: tk.Event[tk.Misc] | None = None) -> KeybindingRuntimeContext:
        self._sync_popup_sessions_from_windows()
        text_input_focused = self._is_text_input_focused()
        dialog_open = self._popup_registry.has_mode_blocking_popup()
        offline = bool(self._shortcut_runtime_offline)

        if offline:
            active_mode = UI_MODE_OFFLINE
        elif dialog_open:
            active_mode = UI_MODE_DIALOG
        elif text_input_focused:
            active_mode = UI_MODE_EDITOR
        elif self.editor_view.winfo_ismapped():
            active_mode = UI_MODE_PREVIEW
        else:
            active_mode = UI_MODE_GLOBAL

        return KeybindingRuntimeContext(
            active_mode=active_mode,
            offline=offline,
            text_input_focused=text_input_focused,
            dialog_open=dialog_open,
        )

    def _bind_runtime_shortcut(
        self,
        sequence: str,
        handler,
        *,
        binding_id: str,
        intent: str,
        modes: tuple[str, ...],
        allow_when_text_input: bool = False,
        allow_when_offline: bool = True,
    ) -> None:
        definition = self._register_runtime_shortcut(
            binding_id=binding_id,
            sequence=sequence,
            intent=intent,
            modes=modes,
            allow_when_text_input=allow_when_text_input,
            allow_when_offline=allow_when_offline,
        )

        def _wrapped(event):
            context = self._build_runtime_context(event)
            can_execute, _reason = self._runtime_shortcuts.evaluate_runtime(definition, context)
            if not can_execute:
                return None
            return handler(event)

        self.bind(sequence, _wrapped)

    def toggle_shortcut_runtime_offline(self) -> None:
        self._shortcut_runtime_offline = not bool(self._shortcut_runtime_offline)
        self._shortcut_runtime_debug_offline_var.set(bool(self._shortcut_runtime_offline))
        self._refresh_shortcut_runtime_debug_dialog()

    def _on_shortcut_runtime_offline_var_changed(self) -> None:
        self._shortcut_runtime_offline = bool(self._shortcut_runtime_debug_offline_var.get())
        self._refresh_shortcut_runtime_debug_dialog()

    def open_shortcut_runtime_debug_dialog(self) -> None:
        if self._shortcut_runtime_debug_window is not None and int(self._shortcut_runtime_debug_window.winfo_exists()):
            self._refresh_shortcut_runtime_debug_dialog()
            self._shortcut_runtime_debug_window.deiconify()
            self._shortcut_runtime_debug_window.lift()
            self._shortcut_runtime_debug_window.focus_force()
            return

        window = tk.Toplevel(self)
        window.title("Shortcut Runtime Debug")
        window.geometry("980x520")
        window.minsize(820, 420)
        self._track_popup_window(window, policy_id="dialog.non_blocking")

        toolbar = ttk.Frame(window, padding=(10, 8))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, textvariable=self._shortcut_runtime_debug_context_var, style="Muted.TLabel").pack(
            side="left", fill="x", expand=True
        )
        ttk.Checkbutton(
            toolbar,
            text="Offline simulieren",
            variable=self._shortcut_runtime_debug_offline_var,
            command=self._on_shortcut_runtime_offline_var_changed,
        ).pack(side="left", padx=(12, 0))
        ttk.Button(toolbar, text="Aktualisieren", command=self._refresh_shortcut_runtime_debug_dialog).pack(
            side="left", padx=(8, 0)
        )

        body = ttk.Frame(window, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)
        columns = ("mode", "key", "binding", "status", "reason")
        table = ttk.Treeview(body, columns=columns, show="headings")
        table.heading("mode", text="Mode")
        table.heading("key", text="Key")
        table.heading("binding", text="Binding")
        table.heading("status", text="Status")
        table.heading("reason", text="Reason")
        table.column("mode", width=100, anchor="center", stretch=False)
        table.column("key", width=130, anchor="center", stretch=False)
        table.column("binding", width=300, anchor="w", stretch=True)
        table.column("status", width=90, anchor="center", stretch=False)
        table.column("reason", width=180, anchor="w", stretch=True)
        table.pack(side="left", fill="both", expand=True)
        y_scroll = ttk.Scrollbar(body, orient="vertical", command=table.yview)
        y_scroll.pack(side="right", fill="y")
        table.configure(yscrollcommand=y_scroll.set)

        ttk.Label(window, textvariable=self._shortcut_runtime_debug_summary_var, style="Muted.TLabel").pack(
            fill="x", padx=10, pady=(0, 8)
        )

        self._shortcut_runtime_debug_window = window
        self._shortcut_runtime_debug_table = table
        window.protocol("WM_DELETE_WINDOW", self._close_shortcut_runtime_debug_dialog)
        self._refresh_shortcut_runtime_debug_dialog()

    def _close_shortcut_runtime_debug_dialog(self) -> None:
        if self._shortcut_runtime_debug_window is not None and int(self._shortcut_runtime_debug_window.winfo_exists()):
            popup_id = str(self._shortcut_runtime_debug_window)
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)
            self._shortcut_runtime_debug_window.destroy()
        self._shortcut_runtime_debug_window = None
        self._shortcut_runtime_debug_table = None

    def _refresh_shortcut_runtime_debug_dialog(self) -> None:
        table = self._shortcut_runtime_debug_table
        if table is None:
            return

        context = self._build_runtime_context()
        self._shortcut_runtime_debug_context_var.set(
            f"mode={context.active_mode} | offline={context.offline} | dialog={context.dialog_open} | text-focus={context.text_input_focused}"
        )

        for item_id in table.get_children(""):
            table.delete(item_id)

        active_count = 0
        disabled_count = 0
        for mode in (UI_MODE_GLOBAL, UI_MODE_EDITOR, UI_MODE_PREVIEW, UI_MODE_DIALOG, UI_MODE_OFFLINE):
            for definition in self._runtime_shortcuts.all():
                if mode not in definition.modes and UI_MODE_GLOBAL not in definition.modes:
                    continue
                can_execute, reason = self._runtime_shortcuts.evaluate_runtime(
                    definition,
                    context,
                    active_mode_override=mode,
                )
                status = "active" if can_execute else "disabled"
                if can_execute:
                    active_count += 1
                else:
                    disabled_count += 1
                table.insert(
                    "",
                    tk.END,
                    values=(mode, definition.sequence, definition.binding_id, status, "" if can_execute else reason),
                )

        total = active_count + disabled_count
        self._shortcut_runtime_debug_summary_var.set(
            f"Bindings: {total} total | {active_count} active | {disabled_count} disabled"
        )

    def _apply_details_overlay_position(self) -> None:
        if not hasattr(self, "grid_stack"):
            return

        self.grid_stack.pack_forget()
        self.details_container.pack_forget()

        self.grid_container.pack_forget()
        self.x_scroll.pack_forget()
        self.grid_container.pack(fill="both", expand=True)
        self.x_scroll.pack(fill="x")

        position = self.details_overlay_position
        if position == "left":
            self.details_container.configure(width=560)
            self.details_container.pack_propagate(False)
            self.details_container.pack(side="left", fill="y", padx=(12, 8), pady=(0, 8))
            self.grid_stack.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=(0, 8))
            return

        if position == "right":
            self.details_container.configure(width=560)
            self.details_container.pack_propagate(False)
            self.grid_stack.pack(side="left", fill="both", expand=True, padx=(12, 8), pady=(0, 8))
            self.details_container.pack(side="left", fill="y", padx=(0, 12), pady=(0, 8))
            return

        self.details_container.pack_propagate(True)
        self.grid_stack.pack(fill="both", expand=True, padx=12, pady=(0, 0))
        self.details_container.pack(fill="x", padx=12, pady=(8, 12))

    def _on_details_overlay_position_changed(self) -> None:
        self.details_overlay_position = self._normalize_details_overlay_position(self.details_overlay_position_var.get())
        self._settings["details_overlay_position"] = self.details_overlay_position
        self.settings_repository.save_settings(self._settings)
        self._apply_details_overlay_position()
        if self._details_panel_visible:
            fill_mode = "both" if self.details_overlay_position in {"left", "right"} else "x"
            self.details_frame.pack_forget()
            self.details_frame.pack(fill=fill_mode, padx=12, pady=(4, 12))
        self._refresh_details_panel()

    def _on_tablegroup_overlay_position_changed(self) -> None:
        self.tablegroup_overlay_position = self._normalize_tablegroup_overlay_position(
            self.tablegroup_overlay_position_var.get()
        )
        self._settings["tablegroup_overlay_position"] = self.tablegroup_overlay_position
        self.settings_repository.save_settings(self._settings)
        self._position_tablegroup_overlay()

    def _handle_intent(self, intent: str) -> str | None:
        intent_ok, intent_reason = self._hsm_contract.validate_intent(intent)
        if not intent_ok:
            self.status_var.set(f"Unbekannter Intent blockiert: {intent_reason}")
            return None

        if intent in GRID_ONLY_INTENTS and not self._shortcut_scope_allows("grid"):
            return None
        if intent in DOCS_ONLY_INTENTS and not self._shortcut_scope_allows("docs"):
            return None
        return self.ui_intent_controller.handle_intent(intent)

    def _shortcut_scope_allows(self, scope: str) -> bool:
        if scope == "global":
            return True
        if scope == "list":
            return self.interaction_mode == LIST_ACTIVE
        if scope == "grid":
            return self.editor_view.winfo_ismapped() and self._editor_surface == "grid" and not self._is_text_input_focused()
        if scope == "docs":
            return self.editor_view.winfo_ismapped() and self._editor_surface == "docs" and not self._is_text_input_focused()
        return False

    def _on_rename_shortcut(self, _event) -> str | None:
        if self.interaction_mode != LIST_ACTIVE:
            return None
        return self._handle_intent(UiIntent.RENAME_SELECTED_PLAN)

    def _on_duplicate_shortcut(self, _event) -> str | None:
        if self.interaction_mode != LIST_ACTIVE:
            return None
        return self._handle_intent(UiIntent.DUPLICATE_SELECTED_PLAN)

    def _on_delete_key(self, _event) -> str | None:
        if self.interaction_mode == LIST_ACTIVE:
            return self._handle_intent(UiIntent.DELETE_SELECTED_PLAN)
        if self._editor_surface == "docs":
            if self._is_text_input_focused():
                return None
            self.clear_selected_documentation_symbol()
            return "break"
        return self._handle_intent(UiIntent.DELETE_DESK)

    def _on_set_grade_shortcut(self, _event) -> str | None:
        if not self._shortcut_scope_allows("docs"):
            return None
        self.set_selected_documentation_grade_dialog()
        return "break"

    def _on_set_symbol_shortcut(self, _event) -> str | None:
        if not self._shortcut_scope_allows("docs"):
            return None
        self.set_selected_documentation_symbol_dialog()
        return "break"

    def _on_clear_symbol_shortcut(self, _event) -> str | None:
        if not self._shortcut_scope_allows("docs"):
            return None
        self.clear_selected_documentation_symbol()
        return "break"

    def clear_selected_documentation_symbol(self) -> None:
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            self.status_var.set("Kein Symbol geloescht: keine aktive Doku-Auswahl")
            return

        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        date_key = self._doc_dates[date_index]
        desk = self.current_plan.desk_at(x, y)
        if not desk or not desk.is_named_student():
            self.status_var.set("Kein Symbol geloescht: Zelle ist kein Schuelertisch")
            return

        if self._doc_selected_fixed_column_id:
            if self._doc_selected_fixed_column_id.startswith("grade_"):
                column_id = self._doc_selected_fixed_column_id[len("grade_") :]
                updated = set_documentation_grade(self.current_plan, x, y, column_id, None, date_key)
                self._record_and_save(updated, "documentation.grade.clear", "Note geloescht")
                self._refresh_documentation_table()
                return
            self.status_var.set("Kein Eintrag geloescht: Spalte ist schreibgeschuetzt")
            return

        entry = desk.documentation_entries.get(date_key)
        if not entry:
            self.status_var.set("Kein Symbol geloescht: fuer dieses Datum kein Doku-Eintrag")
            return

        active_symbols = [symbol for symbol in self.symbol_catalog if int(entry.symbols.get(symbol, 0)) > 0]
        if not active_symbols:
            self.status_var.set("Kein Symbol geloescht: kein aktives Symbol in der Doku-Zelle")
            return

        symbol_name = active_symbols[0]
        updated = set_documentation_symbol(self.current_plan, x, y, symbol_name, 0, date_key)
        self._record_and_save(updated, "documentation.symbol.clear.shortcut", f"Dokumentation '{symbol_name}' geloescht")
        self._refresh_documentation_table()

    def _on_docs_prev_date_shortcut(self, _event) -> str | None:
        if not self._shortcut_scope_allows("docs"):
            return None
        if not self._doc_dates:
            return "break"
        self._doc_selected_fixed_column_id = None
        self._doc_selected_date_index = max(0, self._doc_selected_date_index - 1)
        self._apply_doc_column_heading_highlight()
        return "break"

    def _on_docs_next_date_shortcut(self, _event) -> str | None:
        if not self._shortcut_scope_allows("docs"):
            return None
        if not self._doc_dates:
            return "break"
        self._doc_selected_fixed_column_id = None
        self._doc_selected_date_index = min(len(self._doc_dates) - 1, self._doc_selected_date_index + 1)
        self._apply_doc_column_heading_highlight()
        return "break"

    def _on_docs_today_shortcut(self, _event) -> str | None:
        if not self._shortcut_scope_allows("docs"):
            return None
        self.select_today_documentation_date()
        return "break"

    def _normalize_canvas_radius(self, value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = DEFAULT_CANVAS_RADIUS
        return max(MIN_CANVAS_RADIUS, min(MAX_CANVAS_RADIUS, parsed))

    def _normalize_symbol_strength(self, value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = DEFAULT_SYMBOL_STRENGTH
        return max(0, min(2, parsed))

    def _normalize_viewport_follow_buffer(self, value: object) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = DEFAULT_VIEWPORT_FOLLOW_BUFFER
        return max(0, min(5, parsed))

    def _normalize_grid_visible_symbols(self, raw_value: object, symbol_catalog: list[str]) -> set[str]:
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
        normalized = str(value or "").strip().lower()
        if normalized not in {"left", "right", "bottom"}:
            return DEFAULT_DETAILS_OVERLAY_POSITION
        return normalized

    def _normalize_tablegroup_overlay_position(self, value: object) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in {"left", "right", "bottom"}:
            return DEFAULT_TABLEGROUP_OVERLAY_POSITION
        return normalized

    def _grid_min(self) -> int:
        return -self.canvas_radius

    def _grid_max(self) -> int:
        return self.canvas_radius

    def _count_out_of_bounds_desks(self, plan: SeatingPlan, radius: int | None = None) -> int:
        effective_radius = self.canvas_radius if radius is None else self._normalize_canvas_radius(radius)
        min_grid = -effective_radius
        max_grid = effective_radius
        count = 0
        for desk in plan.desks:
            if desk.desk_type != "student":
                continue
            if desk.x < min_grid or desk.x > max_grid or desk.y < min_grid or desk.y > max_grid:
                count += 1
        return count

    def _grid_pixel_bounds(self) -> tuple[float, float, float, float]:
        min_grid = self._grid_min()
        max_grid = self._grid_max()
        min_x = min_grid * self.cell_size
        min_y = min_grid * self.cell_size
        max_x = (max_grid + 1) * self.cell_size
        max_y = (max_grid + 1) * self.cell_size
        return min_x, min_y, max_x, max_y

    def _update_scroll_region(self) -> None:
        min_x, min_y, max_x, max_y = self._grid_pixel_bounds()
        self.canvas.configure(scrollregion=(min_x, min_y, max_x, max_y))

    def _clamp_cell(self, x: int, y: int) -> tuple[int, int]:
        min_grid = self._grid_min()
        max_grid = self._grid_max()
        return max(min_grid, min(max_grid, x)), max(min_grid, min(max_grid, y))

    def _set_selection_single(self, x: int, y: int) -> None:
        cx, cy = self._clamp_cell(x, y)
        self.selection.set_single(cx, cy)
        self.selected_cell = (cx, cy)

    def _set_selection_focus(self, x: int, y: int) -> None:
        cx, cy = self._clamp_cell(x, y)
        self.selection.set_focus(cx, cy)
        self.selected_cell = (cx, cy)

    def _collapse_selection_to_anchor(self) -> None:
        self.selection.collapse_to_anchor()
        self.selected_cell = self.selection.anchor_cell()

    def _record_and_save(self, new_plan: SeatingPlan, action_kind: str, status: str) -> None:
        new_plan = cleanup_unused_color_meanings(new_plan)
        normalize_tablegroups_in_place(new_plan)
        if not self.current_plan:
            self.current_plan = new_plan
            return
        if new_plan == self.current_plan:
            return
        self.current_plan = new_plan
        self.history.record(self.current_plan, action_kind)
        self._save_current_plan(status)
        if hasattr(self, "docs_tree"):
            self._refresh_documentation_table()

    def _apply_loaded_plan(self, plan: SeatingPlan) -> SeatingPlan:
        plan = cleanup_unused_color_meanings(plan)
        normalize_tablegroups_in_place(plan)
        plan = ensure_documentation_date(plan, self._today_doc_date())
        self.current_plan = plan
        self.history.reset(self.current_plan)
        if hasattr(self, "docs_tree"):
            self._refresh_documentation_table()
        return plan

    def _on_return_key(self, _event) -> str | None:
        if self._is_text_input_focused():
            return "break"
        if self.editor_view.winfo_ismapped():
            if self._editor_surface == "docs":
                if self._doc_selected_fixed_column_id and self._doc_selected_fixed_column_id.startswith("grade_"):
                    self._open_selected_docs_grade_cell_editor()
                    return "break"
                return "break"
            if not self.selection.is_single():
                self._collapse_selection_to_anchor()
                self.redraw_grid()
                self._refresh_details_panel()
            return self._handle_intent(UiIntent.CONFIRM_SELECTION)
        if self.interaction_mode == LIST_ACTIVE:
            return self._handle_intent(UiIntent.LIST_OPEN_SELECTED)
        return self._handle_intent(UiIntent.CONFIRM_SELECTION)

    def _on_name_entry_escape(self, _event) -> str:
        self.exit_name_edit_mode()
        return "break"

    def _on_name_entry_return(self, _event) -> str:
        self.exit_name_edit_mode()
        return "break"

    def _bind_editor_return_override(self, widget: tk.Widget) -> None:
        widget.bind("<Return>", self._on_return_key)
        widget.bind("<KP_Enter>", self._on_return_key)

    def _on_name_entry_focus_in(self, _event) -> None:
        if (
            self.editor_view.winfo_exists()
            and self.editor_view.winfo_ismapped()
            and self.name_entry.winfo_exists()
            and self.name_entry.instate(["!disabled"])
        ):
            self.interaction_mode = NAME_EDITING

    def _on_name_entry_focus_out(self, _event) -> None:
        if self.editor_view.winfo_exists() and self.editor_view.winfo_ismapped() and self.interaction_mode == NAME_EDITING:
            self.interaction_mode = GRID_SELECTED

    def _is_name_entry_focused(self) -> bool:
        return self.focus_get() == self.name_entry

    def _is_text_input_focused(self) -> bool:
        focused_widget = self.focus_get()
        if focused_widget is None:
            return False

        widget_class = str(focused_widget.winfo_class())
        if widget_class in {"Entry", "TEntry", "Text", "Spinbox", "Listbox", "TCombobox", "Combobox"}:
            return True

        if self._is_tablegroup_overlay_focused():
            return True

        focused_toplevel = focused_widget.winfo_toplevel()
        if isinstance(focused_toplevel, tk.Toplevel) and focused_toplevel is not self:
            return True

        return False

    def _is_tablegroup_overlay_focused(self) -> bool:
        if not self._tablegroup_overlay or not self._tablegroup_overlay.winfo_exists():
            return False
        focused_widget = self.focus_get()
        if focused_widget is None:
            return False
        focused_path = str(focused_widget)
        return focused_path.startswith(str(self._tablegroup_overlay))

    def open_tablegroup_settings_overlay(self) -> None:
        if not self.editor_view.winfo_ismapped():
            self.status_var.set("Tischeinstellungen nur im Editor verfuegbar")
            return
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geoeffnet")
            return

        if self._tablegroup_overlay and self._tablegroup_overlay.winfo_exists():
            self._position_tablegroup_overlay()
            self._refresh_tablegroup_overlay()
            self._tablegroup_overlay.deiconify()
            self._tablegroup_overlay.lift()
            self._tablegroup_overlay.focus_force()
            return

        overlay = tk.Toplevel(self)
        overlay.title("Tischeinstellungen")
        overlay.resizable(False, False)
        overlay.transient(self)
        self._track_popup_window(overlay)
        overlay.protocol("WM_DELETE_WINDOW", self._close_tablegroup_overlay)
        overlay.bind("<Escape>", lambda _event: self._close_tablegroup_overlay())
        self._tablegroup_overlay = overlay
        self._position_tablegroup_overlay()

        body = ttk.Frame(overlay)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        self._tg_number_var = tk.StringVar(value="")
        self._tg_shift_x_var = tk.StringVar(value="0.00")
        self._tg_shift_y_var = tk.StringVar(value="0.00")
        self._tg_rotation_var = tk.StringVar(value="0.00")
        self._tg_status_var = tk.StringVar(value="")

        ttk.Label(body, text="TG-Nummer").grid(row=0, column=0, sticky="w", pady=(0, 4))
        number_entry = ttk.Entry(body, textvariable=self._tg_number_var, width=10)
        number_entry.grid(row=0, column=1, sticky="w", pady=(0, 4))
        number_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("number"))

        ttk.Label(body, text=f"x-shift (-{TG_SHIFT_LIMIT:.2f}..{TG_SHIFT_LIMIT:.2f})").grid(
            row=1, column=0, sticky="w", pady=(0, 4)
        )
        shift_x_entry = ttk.Entry(body, textvariable=self._tg_shift_x_var, width=10)
        shift_x_entry.grid(row=1, column=1, sticky="w", pady=(0, 4))
        shift_x_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("shift_x"))

        ttk.Label(body, text=f"y-shift (-{TG_SHIFT_LIMIT:.2f}..{TG_SHIFT_LIMIT:.2f})").grid(
            row=2, column=0, sticky="w", pady=(0, 4)
        )
        shift_y_entry = ttk.Entry(body, textvariable=self._tg_shift_y_var, width=10)
        shift_y_entry.grid(row=2, column=1, sticky="w", pady=(0, 4))
        shift_y_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("shift_y"))

        ttk.Label(body, text=f"Rotation (-{int(TG_ROTATION_LIMIT)}..{int(TG_ROTATION_LIMIT)})").grid(
            row=3, column=0, sticky="w", pady=(0, 4)
        )
        rotation_entry = ttk.Entry(body, textvariable=self._tg_rotation_var, width=10)
        rotation_entry.grid(row=3, column=1, sticky="w", pady=(0, 4))
        rotation_entry.bind("<FocusIn>", lambda _event: self._set_tg_last_changed("rotation"))

        ttk.Label(body, textvariable=self._tg_status_var, style="Panel.TLabel").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 8)
        )

        button_row = ttk.Frame(body)
        button_row.grid(row=5, column=0, columnspan=2, sticky="ew")
        ttk.Button(button_row, text="Schliessen", command=self._close_tablegroup_overlay).pack(side="right")
        ttk.Button(button_row, text="Uebernehmen", command=self._apply_tablegroup_overlay_values).pack(
            side="right", padx=(0, 8)
        )

        overlay.bind("<Return>", lambda _event: self._apply_tablegroup_overlay_values())
        self._focus_overlay_widget(overlay, number_entry)
        self._refresh_tablegroup_overlay()

    def _set_tg_last_changed(self, field: str) -> None:
        self._tg_last_changed_field = field

    def _position_tablegroup_overlay(self) -> None:
        if not self._tablegroup_overlay or not self._tablegroup_overlay.winfo_exists():
            return
        self.update_idletasks()
        width = 340
        height = 250
        position = self.tablegroup_overlay_position

        if position == "left":
            x_pos = self.winfo_rootx() + 20
            y_pos = self.winfo_rooty() + 90
        elif position == "bottom":
            x_pos = self.winfo_rootx() + max(20, (self.winfo_width() - width) // 2)
            y_pos = self.winfo_rooty() + self.winfo_height() - height - 20
        else:
            x_pos = self.winfo_rootx() + self.winfo_width() - width - 20
            y_pos = self.winfo_rooty() + 90

        x_pos = max(10, min(x_pos, self.winfo_rootx() + self.winfo_width() - width - 10))
        y_pos = max(10, min(y_pos, self.winfo_rooty() + self.winfo_height() - height - 10))
        self._tablegroup_overlay.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

    def _close_tablegroup_overlay(self) -> None:
        if self._tablegroup_overlay and self._tablegroup_overlay.winfo_exists():
            popup_id = str(self._tablegroup_overlay)
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)
            self._tablegroup_overlay.destroy()
        self._tablegroup_overlay = None
        self._tg_number_var = None
        self._tg_shift_x_var = None
        self._tg_shift_y_var = None
        self._tg_rotation_var = None
        self._tg_status_var = None

    def _refresh_tablegroup_overlay(self) -> None:
        if not self._tablegroup_overlay or not self._tablegroup_overlay.winfo_exists():
            return
        if not self.current_plan or not self.current_plan_path:
            return
        if not self._tg_number_var or not self._tg_shift_x_var or not self._tg_shift_y_var or not self._tg_rotation_var:
            return

        normalize_tablegroups_in_place(self.current_plan)
        x, y = self.selection.active_cell()
        number = tablegroup_number_at(self.current_plan, x, y)
        if number is None:
            self._tg_number_var.set("")
            self._tg_shift_x_var.set("0.00")
            self._tg_shift_y_var.set("0.00")
            self._tg_rotation_var.set("0.00")
            if self._tg_status_var:
                self._tg_status_var.set("Waehle einen Schuelertisch aus")
            return

        settings = get_tablegroup_settings(self.current_plan, number)
        if settings is None:
            return

        self._tg_number_var.set(str(settings.number))
        self._tg_shift_x_var.set(f"{settings.shift_x:.2f}")
        self._tg_shift_y_var.set(f"{settings.shift_y:.2f}")
        self._tg_rotation_var.set(f"{settings.rotation:.2f}")
        if self._tg_status_var:
            self._tg_status_var.set(f"Aktive Gruppe: TG {settings.number}")

    def _parse_tablegroup_overlay_values(self) -> tuple[int, float, float, float] | None:
        if not self._tg_number_var or not self._tg_shift_x_var or not self._tg_shift_y_var or not self._tg_rotation_var:
            return None

        try:
            number = int(self._tg_number_var.get().strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "TG-Nummer muss eine ganze Zahl sein.", parent=self)
            return None
        if number <= 0:
            messagebox.showerror("Ungueltige Eingabe", "TG-Nummer muss groesser als 0 sein.", parent=self)
            return None

        try:
            shift_x = float(self._tg_shift_x_var.get().strip())
            shift_y = float(self._tg_shift_y_var.get().strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "x-shift und y-shift muessen Zahlen sein.", parent=self)
            return None

        if not (-0.5 < shift_x < 0.5) or not (-0.5 < shift_y < 0.5):
            messagebox.showerror(
                "Ungueltige Eingabe",
                "x-shift und y-shift muessen strikt zwischen -0.5 und 0.5 liegen.",
                parent=self,
            )
            return None

        try:
            rotation = float(self._tg_rotation_var.get().strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "Rotation muss eine Zahl sein.", parent=self)
            return None
        if rotation < -TG_ROTATION_LIMIT or rotation > TG_ROTATION_LIMIT:
            messagebox.showerror(
                "Ungueltige Eingabe",
                f"Rotation muss zwischen {-TG_ROTATION_LIMIT:.0f} und {TG_ROTATION_LIMIT:.0f} liegen.",
                parent=self,
            )
            return None

        return number, shift_x, shift_y, rotation

    def _apply_tablegroup_overlay_values(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        parsed = self._parse_tablegroup_overlay_values()
        if parsed is None:
            return

        target_number, shift_x, shift_y, rotation = parsed
        x, y = self.selection.active_cell()

        next_plan = deepcopy(self.current_plan)
        normalize_tablegroups_in_place(next_plan)

        source_number = tablegroup_number_at(next_plan, x, y)
        if source_number is None:
            if self._tg_status_var:
                self._tg_status_var.set("Nur Schuelertische gehoeren zu Tischgruppen")
            return

        if source_number != target_number:
            set_tablegroup_number_with_cascade_in_place(next_plan, source_number, target_number)
            source_number = target_number

        set_tablegroup_transforms_in_place(
            next_plan,
            source_number,
            shift_x=shift_x,
            shift_y=shift_y,
            rotation=rotation,
        )

        teacher_overlap, student_overlap = detect_overlaps_for_tablegroup(next_plan, source_number)
        if teacher_overlap or student_overlap:
            if self._tg_last_changed_field == "shift_y":
                set_tablegroup_transforms_in_place(next_plan, source_number, shift_y=0.0)
                reset_label = "y-shift"
            elif self._tg_last_changed_field == "rotation":
                set_tablegroup_transforms_in_place(next_plan, source_number, rotation=0.0)
                reset_label = "rotation"
            else:
                set_tablegroup_transforms_in_place(next_plan, source_number, shift_x=0.0)
                reset_label = "x-shift"

            teacher_overlap, student_overlap = detect_overlaps_for_tablegroup(next_plan, source_number)
            if teacher_overlap or student_overlap:
                set_tablegroup_transforms_in_place(next_plan, source_number, shift_x=0.0, shift_y=0.0, rotation=0.0)
                reset_label = "x/y-shift und rotation"

            self._record_and_save(
                next_plan,
                "tablegroup.edit",
                f"Tischgruppe aktualisiert, {reset_label} auf 0 zurueckgesetzt",
            )
            if self._tg_status_var:
                self._tg_status_var.set(f"Ueberlappung erkannt: {reset_label} auf 0 gesetzt")
        else:
            self._record_and_save(next_plan, "tablegroup.edit", "Tischgruppe aktualisiert")
            if self._tg_status_var:
                self._tg_status_var.set(f"TG {source_number} gespeichert")

        self.redraw_grid()
        self._refresh_details_panel()
        self._refresh_tablegroup_overlay()

    def _build_symbol_shortcut_map(self, definitions: list[SymbolDefinition]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for definition in definitions:
            if definition.shortcut is None:
                continue
            if definition.shortcut in mapping:
                continue
            mapping[definition.shortcut] = definition.meaning
        return mapping

    def _on_symbol_shortcut(self, _event, symbol_name: str) -> str | None:
        if not self._shortcut_scope_allows("docs") and not self._shortcut_scope_allows("grid"):
            return None
        # Ignore control/alt-modified keys so shortcuts like Ctrl+C remain unaffected.
        if _event.state & 0x0004 or _event.state & 0x0008:
            return None
        if not self.editor_view.winfo_ismapped():
            return None
        if not self.current_plan or not self.current_plan_path:
            return None

        if self._editor_surface == "docs":
            self._toggle_documentation_symbol(symbol_name)
            return "break"

        if self._editor_surface != "grid":
            return None
        if symbol_name not in self.diagnostic_symbol_catalog:
            return None

        self._toggle_selected_symbol(symbol_name)
        return "break"

    def _on_color_shortcut(self, event, color_key: str) -> str | None:
        if not self._shortcut_scope_allows("grid"):
            return None
        if event.state & 0x0004 or event.state & 0x0008:
            return None
        if not self.editor_view.winfo_ismapped():
            return None
        if self._editor_surface != "grid":
            return None
        if not self.current_plan or not self.current_plan_path:
            return None

        self._toggle_selected_color(color_key)
        return "break"

    def _toggle_selected_color(self, color_key: str) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self.status_var.set("Farbpunkte nur bei Einzelauswahl")
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            self.status_var.set("Farbpunkte nur fuer Schuelertische")
            return

        currently_active = color_key in desk.color_markers
        requires_meaning = (not currently_active) and (not is_color_used(self.current_plan, color_key))
        color_label, _hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))

        next_plan = self.current_plan
        if requires_meaning:
            meaning = simpledialog.askstring(
                "Bedeutung fuer Farbe",
                f"Was bedeutet {color_label} in diesem Plan?",
                parent=self,
            )
            if meaning is None:
                self.status_var.set("Farbpunkt abgebrochen")
                self.canvas.focus_set()
                return
            clean = meaning.strip()
            if not clean:
                self.status_var.set("Bedeutung darf nicht leer sein")
                self.canvas.focus_set()
                return
            next_plan = set_color_meaning(next_plan, color_key, clean)

        next_plan = toggle_color_marker(next_plan, x, y, color_key)

        if next_plan == self.current_plan:
            return

        if color_key in next_plan.color_meanings:
            status = f"Farbpunkt {color_label} aktualisiert"
        else:
            status = f"Farbpunkt {color_label} entfernt"

        self._record_and_save(next_plan, "color.toggle", status)
        self.redraw_grid()
        self._refresh_details_panel()
        self.canvas.focus_set()

    def _load_symbols(self) -> tuple[list[SymbolDefinition], str | None]:
        return load_symbol_definitions(self.symbols_path)

    def _on_theme_changed(self) -> None:
        self.theme_key = normalize_theme_key(self.theme_var.get())
        self._settings["theme"] = self.theme_key
        self.settings_repository.save_settings(self._settings)
        self.apply_theme()
        self.redraw_grid()

    def toggle_theme(self) -> None:
        names = theme_names()
        current_index = names.index(self.theme_key) if self.theme_key in names else 0
        self.theme_key = names[(current_index + 1) % len(names)]
        self.theme_var.set(self.theme_key)
        self._on_theme_changed()

    def apply_theme(self) -> None:
        theme = THEMES[self.theme_key]

        self.configure(bg=theme["bg_main"])
        self.style.configure("TFrame", background=theme["bg_panel"])
        self.style.configure("Main.TFrame", background=theme["bg_main"])
        self.style.configure("Panel.TFrame", background=theme["bg_panel"])
        self.style.configure("StrongPanel.TFrame", background=theme["panel_strong"])

        self.style.configure("TLabel", background=theme["bg_panel"], foreground=theme["fg_main"])
        self.style.configure("Main.TLabel", background=theme["bg_main"], foreground=theme["fg_main"])
        self.style.configure("Panel.TLabel", background=theme["bg_panel"], foreground=theme["fg_main"])
        self.style.configure("StrongPanel.TLabel", background=theme["panel_strong"], foreground=theme["fg_main"])

        self.style.configure("TButton", padding=(10, 6), background=theme["bg_panel"], foreground=theme["fg_main"])
        self.style.map(
            "TButton",
            background=[("active", theme["bg_selected"])],
            foreground=[("active", theme["fg_main"])],
        )

        self.style.configure(
            "TEntry",
            fieldbackground=theme["bg_surface"],
            foreground=theme["fg_main"],
            insertcolor=theme["fg_main"],
        )

        self.style.configure(
            "Horizontal.TScrollbar",
            troughcolor=theme["scroll_trough"],
            background=theme["scroll_thumb"],
            bordercolor=theme["grid_line"],
            arrowcolor=theme["fg_muted"],
        )
        self.style.map("Horizontal.TScrollbar", background=[("active", theme["scroll_thumb_active"])])
        self.style.configure(
            "Vertical.TScrollbar",
            troughcolor=theme["scroll_trough"],
            background=theme["scroll_thumb"],
            bordercolor=theme["grid_line"],
            arrowcolor=theme["fg_muted"],
        )
        self.style.map("Vertical.TScrollbar", background=[("active", theme["scroll_thumb_active"])])

        self.main_frame.configure(style="Main.TFrame")
        self.list_view.configure(style="Panel.TFrame")
        self.list_toolbar.configure(style="StrongPanel.TFrame")
        self.list_body.configure(style="Panel.TFrame")
        self.editor_view.configure(style="Panel.TFrame")
        self.editor_topbar.configure(style="StrongPanel.TFrame")
        self.grid_stack.configure(style="Panel.TFrame")
        self.grid_container.configure(style="Panel.TFrame")
        self.details_container.configure(style="Panel.TFrame")
        self.details_header.configure(style="Panel.TFrame")
        self.details_frame.configure(style="Panel.TFrame")
        self.docs_container.configure(style="Panel.TFrame")
        self.docs_toolbar.configure(style="StrongPanel.TFrame")
        self.docs_table_container.configure(style="Panel.TFrame")
        self.canvas.configure(bg=theme["bg_surface"])
        self.x_scroll.configure(
            bg=theme["scroll_thumb"],
            activebackground=theme["scroll_thumb_active"],
            troughcolor=theme["scroll_trough"],
            highlightbackground=theme["scroll_trough"],
            highlightcolor=theme["scroll_trough"],
            relief="flat",
            bd=0,
        )
        self.y_scroll.configure(
            bg=theme["scroll_thumb"],
            activebackground=theme["scroll_thumb_active"],
            troughcolor=theme["scroll_trough"],
            highlightbackground=theme["scroll_trough"],
            highlightcolor=theme["scroll_trough"],
            relief="flat",
            bd=0,
        )

        self.plan_listbox.configure(
            bg=theme["bg_panel"],
            fg=theme["fg_main"],
            selectbackground=theme["accent"],
            selectforeground="#FFFFFF",
            highlightbackground=theme["grid_line"],
            highlightcolor=theme["focus_ring"],
            borderwidth=1,
            relief="solid",
        )

        self.style.configure(
            "Treeview",
            background=theme["bg_surface"],
            fieldbackground=theme["bg_surface"],
            foreground=theme["fg_main"],
            bordercolor=theme["grid_line"],
        )
        self.style.configure(
            "Treeview.Heading",
            background=theme["bg_panel"],
            foreground=theme["fg_main"],
        )
        self.style.map("Treeview", background=[("selected", theme["accent"])], foreground=[("selected", "#FFFFFF")])

        self._apply_color_button_theme()

    def _apply_color_button_theme(self) -> None:
        theme = THEMES[self.theme_key]
        for button in self._color_marker_buttons:
            button.configure(
                bg=theme["bg_panel"],
                activebackground=theme["bg_selected"],
                activeforeground=theme["fg_main"],
                highlightbackground=theme["grid_line"],
                bd=1,
            )

    def refresh_plan_list(self) -> None:
        started = time.perf_counter()
        LOGGER.info("refresh_plan_list started")
        preferred_path = self.current_plan_path
        selected = self.plan_listbox.curselection()
        if selected and 0 <= int(selected[0]) < len(self._plan_index):
            preferred_path = self._plan_index[int(selected[0])][0]

        self._plan_index = self.plan_repository.list_plans(self.plans_dir)
        if not self._plan_index:
            try:
                self.plan_repository.create_new_plan(self.plans_dir, "Neuer Sitzplan")
                self._plan_index = self.plan_repository.list_plans(self.plans_dir)
            except Exception as exc:
                self.status_var.set(f"Konnte keinen Startplan erstellen: {exc}")

        self.plan_listbox.delete(0, tk.END)
        for path, plan in self._plan_index:
            student_count = sum(
                1 for desk in plan.desks if desk.desk_type == "student" and desk.student_name.strip()
            )
            label = f"{plan.name}  |  {student_count} Schülertische"
            self.plan_listbox.insert(tk.END, label)

        self._ensure_list_selection(preferred_path=preferred_path)
        LOGGER.info("refresh_plan_list finished in %.3fs with %d plans", time.perf_counter() - started, len(self._plan_index))

    def _ensure_list_selection(self, preferred_path: Path | None = None) -> None:
        if not self._plan_index:
            return

        desired_index = 0
        if preferred_path is not None:
            for idx, (path, _plan) in enumerate(self._plan_index):
                if path == preferred_path:
                    desired_index = idx
                    break
        elif self.plan_listbox.curselection():
            desired_index = int(self.plan_listbox.curselection()[0])

        desired_index = max(0, min(desired_index, len(self._plan_index) - 1))
        self.plan_listbox.selection_clear(0, tk.END)
        self.plan_listbox.selection_set(desired_index)
        self.plan_listbox.activate(desired_index)
        self.plan_listbox.see(desired_index)

    def show_plan_list_view(self) -> None:
        self._close_tablegroup_overlay()
        self.editor_view.pack_forget()
        self.list_view.pack(fill="both", expand=True)
        self.interaction_mode = LIST_ACTIVE
        self._ensure_list_selection(preferred_path=self.current_plan_path)
        self.plan_listbox.focus_set()

    def show_editor_view(self) -> None:
        self.list_view.pack_forget()
        self.editor_view.pack(fill="both", expand=True)
        self.interaction_mode = GRID_SELECTED
        self._set_selection_single(*self.selection.active_cell())
        if self._editor_surface == "docs":
            self.show_documentation_surface()
        else:
            self.show_grid_surface()
        self._position_tablegroup_overlay()

    def show_grid_surface(self) -> None:
        self._editor_surface = "grid"
        self.docs_container.pack_forget()
        if not self.editor_topbar.winfo_ismapped():
            self.editor_topbar.pack(fill="x", padx=12, pady=(12, 8))
        self.grid_stack.pack_forget()
        self.details_container.pack_forget()
        self._apply_details_overlay_position()
        self.interaction_mode = GRID_SELECTED
        self.canvas.focus_set()

    def show_documentation_surface(self) -> None:
        if not self.current_plan:
            return
        self._editor_surface = "docs"
        self.editor_topbar.pack_forget()
        self.grid_stack.pack_forget()
        self.details_container.pack_forget()
        self.docs_container.pack(fill="both", expand=True)
        self._refresh_documentation_table()
        self.docs_tree.focus_set()

    def toggle_documentation_surface(self) -> None:
        if not self.editor_view.winfo_ismapped():
            return
        if self._editor_surface == "docs":
            self.show_grid_surface()
        else:
            self.show_documentation_surface()

    def _today_doc_date(self) -> str:
        return date.today().isoformat()

    def _documentation_cell_text(self, symbols: dict[str, int]) -> str:
        chunks: list[str] = []
        for symbol, strength in sorted(symbols.items()):
            glyph = self._symbol_glyph(symbol)
            chunks.append(glyph * max(1, min(3, int(strength))))
        return " ".join(chunks)

    def _documentation_summary_text(self, x: int, y: int) -> str:
        if not self.current_plan:
            return ""
        summary = summarize_latest_symbols_for_student(self.current_plan, x, y)
        return self._documentation_cell_text(summary)

    def _effective_grid_symbols(self, x: int, y: int, fallback_symbols: dict[str, int]) -> dict[str, int]:
        if not self.current_plan:
            return {
                key: value
                for key, value in fallback_symbols.items()
                if key in self._grid_visible_symbols
            }
        summary = summarize_latest_symbols_for_student(self.current_plan, x, y)
        source = summary if summary else dict(fallback_symbols)
        effective = {
            key: value
            for key, value in source.items()
            if key not in self._documentation_only_symbols
            if key in self._grid_visible_symbols
        }

        desk = self.current_plan.desk_at(x, y)
        today_entry = None
        if desk and desk.is_named_student():
            today_entry = desk.documentation_entries.get(self._today_doc_date())
        if today_entry:
            for key, value in today_entry.symbols.items():
                if key not in self._documentation_only_symbols:
                    continue
                if key not in self._grid_visible_symbols:
                    continue
                effective[key] = int(value)

        return effective

    def open_grid_symbol_filter_dialog(self) -> None:
        dialog = self._create_overlay_dialog("Sichtbare Symbole", "420x480")

        container = ttk.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(container, text="Welche Symbole sollen im Sitzraster angezeigt werden?").pack(anchor="w", pady=(0, 8))

        vars_by_symbol: dict[str, tk.BooleanVar] = {}
        for symbol in self.symbol_catalog:
            var = tk.BooleanVar(value=symbol in self._grid_visible_symbols)
            vars_by_symbol[symbol] = var
            ttk.Checkbutton(container, text=symbol, variable=var).pack(anchor="w", pady=(0, 2))

        def apply_filter() -> None:
            selected = [symbol for symbol, var in vars_by_symbol.items() if var.get()]
            if not selected:
                selected = list(self.symbol_catalog)
            self._grid_visible_symbols = set(selected)
            self._settings["grid_visible_symbols"] = selected
            self.settings_repository.save_settings(self._settings)
            dialog.destroy()
            self.redraw_grid()
            self._refresh_details_panel()

        button_row = ttk.Frame(container)
        button_row.pack(fill="x", pady=(10, 0))
        ttk.Button(button_row, text="Alle", command=lambda: [var.set(True) for var in vars_by_symbol.values()]).pack(side="left")
        ttk.Button(button_row, text="Speichern", command=apply_filter).pack(side="right")

    def _latest_grade_value_for_column(self, x: int, y: int, column_id: str) -> str:
        if not self.current_plan:
            return ""
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            return ""
        latest: float | None = None
        for date_key in sorted(desk.documentation_entries.keys()):
            entry = desk.documentation_entries[date_key]
            value = entry.grades.get(column_id)
            if value is None:
                continue
            latest = float(value)
        if latest is None:
            return ""
        return f"{latest:.2f}"

    def _apply_doc_column_heading_highlight(self) -> None:
        if not hasattr(self, "docs_tree"):
            return
        for idx, date_key in enumerate(self._doc_dates):
            col_id = self._doc_date_column_ids[idx]
            title = date_key
            if idx == self._doc_selected_date_index and not self._doc_selected_fixed_column_id:
                title = f"> {date_key}"
            self.docs_tree.heading(col_id, text=title)
        if hasattr(self, "docs_right_tree") and hasattr(self, "_doc_fixed_column_ids"):
            for idx, fixed_col_id in enumerate(self._doc_fixed_column_ids):
                col_id = fixed_col_id
                base_label = self._doc_fixed_column_label(fixed_col_id)
                if fixed_col_id == self._doc_selected_fixed_column_id:
                    label = f"> {base_label}"
                else:
                    label = base_label
                self.docs_right_tree.heading(col_id, text=label)
        self._refresh_doc_selection_status()

    def _update_docs_cell_highlight(self) -> None:
        """Place a visible overlay label on the currently active docs cell."""
        if self._docs_cell_overlay is not None:
            try:
                if self._docs_cell_overlay.winfo_exists():
                    self._docs_cell_overlay.destroy()
            except Exception:
                pass
            self._docs_cell_overlay = None

        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        if self._docs_inline_editor is not None:
            return

        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        row_iid = self._doc_tree_iid_by_student_index.get(student_index)
        if row_iid is None:
            return

        if self._doc_selected_fixed_column_id:
            tree = self.docs_right_tree
            try:
                col_index = self._doc_fixed_column_ids.index(self._doc_selected_fixed_column_id)
                tree_col = f"#{col_index + 1}"
            except (ValueError, AttributeError):
                return
            if row_iid not in tree.get_children():
                return
            values = tree.item(row_iid, "values")
            cell_text = str(values[col_index]) if values and col_index < len(values) else ""
        else:
            tree = self.docs_tree
            date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
            if date_index >= len(self._doc_date_column_ids):
                return
            tree_col = self._doc_date_column_ids[date_index]
            if row_iid not in tree.get_children():
                return
            values = tree.item(row_iid, "values")
            cell_text = str(values[date_index]) if values and date_index < len(values) else ""

        bbox = tree.bbox(row_iid, tree_col)
        if not bbox:
            return
        bx, by, bw, bh = bbox

        theme = THEMES.get(self.theme_key, THEMES[list(THEMES.keys())[0]])
        cell_bg = theme.get("accent_soft", "#fffde7")
        cell_fg = theme.get("fg_primary", "#000000")

        label = tk.Label(
            tree,
            text=cell_text,
            background=cell_bg,
            foreground=cell_fg,
            bd=1,
            relief="solid",
            anchor="w",
            padx=4,
            pady=0,
        )
        label.place(x=bx, y=by, width=bw, height=bh)
        self._docs_cell_overlay = label

    def _refresh_doc_selection_status(self) -> None:
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            self._doc_selection_status_var.set("Doku-Zelle: -")
            return
        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        desk = self.current_plan.desk_at(x, y)
        name = ""
        if desk is not None and desk.is_named_student():
            name = desk.student_name.strip()
        display_name = name or f"({x},{y})"
        if self._doc_selected_fixed_column_id:
            label = self._doc_fixed_column_label(self._doc_selected_fixed_column_id)
            self._doc_selection_status_var.set(f"Doku-Zelle: {display_name} | {label}")
            self.after_idle(self._update_docs_cell_highlight)
            return
        self._doc_selection_status_var.set(f"Doku-Zelle: {display_name} | {self._doc_dates[date_index]}")
        self.after_idle(self._update_docs_cell_highlight)

    def _selected_docs_coordinates_and_date(self) -> tuple[int, int, str] | None:
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return None
        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        return x, y, self._doc_dates[date_index]

    def _close_docs_inline_editor(self, apply_changes: bool = False) -> None:
        editor = self._docs_inline_editor
        if editor is None:
            return

        if apply_changes:
            self._apply_docs_inline_editor_value()

        if editor.winfo_exists():
            editor.destroy()
        self._docs_inline_editor = None
        self._docs_inline_editor_tree = None
        self._docs_inline_editor_row_id = None
        self._docs_inline_editor_kind = None
        self._docs_inline_editor_model_column = None
        self.after_idle(self._update_docs_cell_highlight)

    def _apply_docs_inline_editor_value(self) -> None:
        if not self.current_plan:
            return
        if self._docs_inline_editor is None or self._docs_inline_editor_kind != "grade":
            return

        selected = self._selected_docs_coordinates_and_date()
        if selected is None:
            return
        x, y, date_key = selected

        column_id = self._docs_inline_editor_model_column
        if not column_id:
            return
        raw_text = self._docs_inline_editor.get().strip()
        grade_value: float | None
        if not raw_text:
            grade_value = None
        else:
            try:
                grade_value = float(raw_text.replace(",", "."))
            except ValueError:
                self.status_var.set("Ungueltige Note: bitte Zahl zwischen 1 und 6 eingeben")
                return

        updated = set_documentation_grade(self.current_plan, x, y, column_id, grade_value, date_key)
        status = "Note geloescht" if grade_value is None else "Note aktualisiert"
        self._record_and_save(updated, "documentation.grade.inline", status)
        self._refresh_documentation_table()

    def _on_docs_inline_editor_return(self, _event) -> str:
        self._close_docs_inline_editor(apply_changes=True)
        if self.docs_right_tree.winfo_exists():
            self.docs_right_tree.focus_set()
        return "break"

    def _on_docs_inline_editor_escape(self, _event) -> str:
        self._close_docs_inline_editor(apply_changes=False)
        if self.docs_right_tree.winfo_exists():
            self.docs_right_tree.focus_set()
        return "break"

    def _open_docs_inline_grade_editor(self, row_id: str, fixed_column_id: str) -> None:
        if not self.current_plan:
            return
        if not fixed_column_id.startswith("grade_"):
            return
        if row_id not in self.docs_right_tree.get_children():
            return

        self._close_docs_inline_editor(apply_changes=False)

        fixed_index = self._doc_fixed_column_ids.index(fixed_column_id)
        tree_column = f"#{fixed_index + 1}"
        bbox = self.docs_right_tree.bbox(row_id, tree_column)
        if not bbox:
            return
        x, y, width, height = bbox

        selected = self._selected_docs_coordinates_and_date()
        if selected is None:
            return
        coords_x, coords_y, date_key = selected
        model_column_id = fixed_column_id[len("grade_") :]

        current_text = ""
        desk = self.current_plan.desk_at(coords_x, coords_y)
        if desk and desk.is_named_student():
            entry = desk.documentation_entries.get(date_key)
            if entry:
                value = entry.grades.get(model_column_id)
                if value is not None:
                    current_text = f"{float(value):.2f}".rstrip("0").rstrip(".")

        editor = ttk.Entry(self.docs_right_tree)
        editor.insert(0, current_text)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        editor.selection_range(0, tk.END)
        editor.bind("<Return>", self._on_docs_inline_editor_return)
        editor.bind("<KP_Enter>", self._on_docs_inline_editor_return)
        editor.bind("<Escape>", self._on_docs_inline_editor_escape)
        editor.bind("<FocusOut>", lambda _event: self._close_docs_inline_editor(apply_changes=True))

        self._docs_inline_editor = editor
        self._docs_inline_editor_tree = self.docs_right_tree
        self._docs_inline_editor_row_id = row_id
        self._docs_inline_editor_kind = "grade"
        self._docs_inline_editor_model_column = model_column_id

    def _open_selected_docs_grade_cell_editor(self) -> None:
        if not self._doc_selected_fixed_column_id or not self._doc_selected_fixed_column_id.startswith("grade_"):
            return
        selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
        if selected_iid is None:
            return
        self._open_docs_inline_grade_editor(selected_iid, self._doc_selected_fixed_column_id)

    def _refresh_documentation_table(self) -> None:
        started = time.perf_counter()
        if not self.current_plan:
            return
        self._close_docs_inline_editor(apply_changes=False)

        self._doc_student_coords = [
            (desk.x, desk.y)
            for desk in sorted(self.current_plan.desks, key=lambda item: (item.y, item.x))
            if desk.is_named_student()
        ]

        all_dates = sorted(set(self.current_plan.documentation_dates) | {self._today_doc_date()})
        self._doc_dates = all_dates
        self._doc_date_column_ids = [f"date_{index}" for index in range(len(all_dates))]

        written_columns = [item for item in self.current_plan.grade_columns if item.category == "schriftlich"]
        sonstige_columns = [item for item in self.current_plan.grade_columns if item.category == "sonstig"]

        fixed_columns: list[str] = ["summary"]
        fixed_columns.extend([f"grade_{item.column_id}" for item in self.current_plan.grade_columns])
        if len(written_columns) > 1:
            fixed_columns.append("written_total")
        if len(sonstige_columns) > 1:
            fixed_columns.append("sonstige_total")
        fixed_columns.append("overall")
        self._doc_fixed_column_ids = list(fixed_columns)
        self.docs_tree.configure(columns=self._doc_date_column_ids)
        self.docs_right_tree.configure(columns=fixed_columns)

        for idx, date_key in enumerate(all_dates):
            self.docs_tree.column(self._doc_date_column_ids[idx], width=120, anchor="center", stretch=False)
            self.docs_tree.heading(self._doc_date_column_ids[idx], text=date_key)

        self.docs_right_tree.column("summary", width=180, anchor="w", stretch=False)
        self.docs_right_tree.heading("summary", text="Zusammenfassung")

        for grade in self.current_plan.grade_columns:
            col_id = f"grade_{grade.column_id}"
            self.docs_right_tree.column(col_id, width=120, anchor="center", stretch=False)
            self.docs_right_tree.heading(col_id, text=grade.title)

        if "written_total" in fixed_columns:
            self.docs_right_tree.column("written_total", width=120, anchor="center", stretch=False)
            self.docs_right_tree.heading("written_total", text="Schriftlich gesamt")
        if "sonstige_total" in fixed_columns:
            self.docs_right_tree.column("sonstige_total", width=120, anchor="center", stretch=False)
            self.docs_right_tree.heading("sonstige_total", text="Sonstig gesamt")

        self.docs_right_tree.column("overall", width=120, anchor="center", stretch=False)
        self.docs_right_tree.heading("overall", text="Gesamtnote")

        for row_id in self.docs_tree.get_children():
            self.docs_tree.delete(row_id)
        for row_id in self.docs_right_tree.get_children():
            self.docs_right_tree.delete(row_id)
        self._doc_tree_iid_by_student_index = {}
        self._doc_student_index_by_iid = {}

        for student_idx, (x, y) in enumerate(self._doc_student_coords):
            desk = self.current_plan.desk_at(x, y)
            if desk is None:
                continue
            date_values: list[str] = []
            for date_key in all_dates:
                entry = desk.documentation_entries.get(date_key)
                date_values.append(self._documentation_cell_text(entry.symbols) if entry else "")

            fixed_values: list[str] = []
            fixed_values.append(self._documentation_summary_text(x, y))
            for grade in self.current_plan.grade_columns:
                fixed_values.append(self._latest_grade_value_for_column(x, y, grade.column_id))
            if "written_total" in fixed_columns:
                fixed_values.append(compute_grade_subtotal_display_for_student(self.current_plan, x, y, "schriftlich"))
            if "sonstige_total" in fixed_columns:
                fixed_values.append(compute_grade_subtotal_display_for_student(self.current_plan, x, y, "sonstig"))
            fixed_values.append(compute_grade_display_for_student(self.current_plan, x, y))

            iid = f"student_{student_idx}"
            self.docs_tree.insert("", "end", iid=iid, text=desk.student_name or f"({x},{y})", values=date_values)
            self.docs_right_tree.insert("", "end", iid=iid, values=fixed_values)
            self._doc_tree_iid_by_student_index[student_idx] = iid
            self._doc_student_index_by_iid[iid] = student_idx

        if self._doc_student_coords:
            self._doc_selected_student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
            self._doc_selected_date_index = max(0, min(self._doc_selected_date_index, max(0, len(all_dates) - 1)))
            selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
            if selected_iid is not None:
                self._set_docs_row_selection(selected_iid)
        else:
            self._doc_selected_student_index = 0
            self._doc_selected_date_index = 0

        if self._doc_selected_fixed_column_id not in set(self._doc_fixed_column_ids):
            self._doc_selected_fixed_column_id = None

        self._apply_doc_column_heading_highlight()
        self._refresh_doc_selection_status()
        elapsed = time.perf_counter() - started
        if elapsed >= 0.2:
            LOGGER.info(
                "_refresh_documentation_table finished in %.3fs (students=%d dates=%d)",
                elapsed,
                len(self._doc_student_coords),
                len(self._doc_dates),
            )

    def _on_docs_tree_click(self, event) -> None:
        row_id = self.docs_tree.identify_row(event.y)
        if row_id:
            self._set_docs_row_selection(row_id, source="main")
        self._doc_selected_fixed_column_id = None
        col_id = self.docs_tree.identify_column(event.x)
        if col_id.startswith("#"):
            try:
                col_index = int(col_id[1:]) - 1
            except ValueError:
                col_index = -1
            if 0 <= col_index < len(self._doc_dates):
                self._doc_selected_date_index = col_index
                self._apply_doc_column_heading_highlight()

    def _on_docs_tree_select(self) -> None:
        if self._syncing_docs_selection:
            return
        selected = self.docs_tree.selection()
        if not selected:
            return
        row_id = selected[0]
        self._set_docs_row_selection(row_id, source="main")
        self._doc_selected_fixed_column_id = None
        self._refresh_doc_selection_status()

    def _on_docs_right_tree_click(self, event) -> None:
        row_id = self.docs_right_tree.identify_row(event.y)
        if row_id:
            self._set_docs_row_selection(row_id, source="right")
        col_id = self.docs_right_tree.identify_column(event.x)
        if col_id.startswith("#"):
            try:
                col_index = int(col_id[1:]) - 1
            except ValueError:
                col_index = -1
            if 0 <= col_index < len(self._doc_fixed_column_ids):
                self._doc_selected_fixed_column_id = self._doc_fixed_column_ids[col_index]
                self._apply_doc_column_heading_highlight()

    def _on_docs_right_tree_double_click(self, event) -> None:
        row_id = self.docs_right_tree.identify_row(event.y)
        if not row_id:
            return
        self._set_docs_row_selection(row_id, source="right")
        col_id = self.docs_right_tree.identify_column(event.x)
        if not col_id.startswith("#"):
            return
        try:
            col_index = int(col_id[1:]) - 1
        except ValueError:
            return
        if not (0 <= col_index < len(self._doc_fixed_column_ids)):
            return
        fixed_column_id = self._doc_fixed_column_ids[col_index]
        self._doc_selected_fixed_column_id = fixed_column_id
        self._apply_doc_column_heading_highlight()
        if fixed_column_id.startswith("grade_"):
            self._open_docs_inline_grade_editor(row_id, fixed_column_id)

    def _on_docs_right_tree_select(self) -> None:
        if self._syncing_docs_selection:
            return
        selected = self.docs_right_tree.selection()
        if not selected:
            return
        row_id = selected[0]
        self._set_docs_row_selection(row_id, source="right")
        if self._doc_selected_fixed_column_id not in set(self._doc_fixed_column_ids):
            self._doc_selected_fixed_column_id = None
        if self._doc_selected_fixed_column_id is None:
            grade_columns = [item for item in self._doc_fixed_column_ids if item.startswith("grade_")]
            if grade_columns:
                self._doc_selected_fixed_column_id = grade_columns[0]
        self._apply_doc_column_heading_highlight()

    def _set_docs_row_selection(self, row_id: str, source: str | None = None) -> None:
        if not row_id:
            return
        if self._syncing_docs_selection:
            return
        if not self.docs_tree.exists(row_id) or not self.docs_right_tree.exists(row_id):
            return
        self._syncing_docs_selection = True
        try:
            if source != "main":
                main_selected = self.docs_tree.selection()
                if len(main_selected) != 1 or main_selected[0] != row_id:
                    self.docs_tree.selection_set(row_id)
                if self.docs_tree.focus() != row_id:
                    self.docs_tree.focus(row_id)
                self.docs_tree.see(row_id)

            if source != "right":
                right_selected = self.docs_right_tree.selection()
                if len(right_selected) != 1 or right_selected[0] != row_id:
                    self.docs_right_tree.selection_set(row_id)
                if self.docs_right_tree.focus() != row_id:
                    self.docs_right_tree.focus(row_id)
                self.docs_right_tree.see(row_id)
        finally:
            self._syncing_docs_selection = False

        student_idx = self._doc_student_index_by_iid.get(row_id)
        if student_idx is not None:
            self._doc_selected_student_index = student_idx

    def _doc_fixed_column_label(self, column_id: str) -> str:
        if column_id == "summary":
            return "Zusammenfassung"
        if column_id == "overall":
            return "Gesamtnote"
        if column_id == "written_total":
            return "Schriftlich gesamt"
        if column_id == "sonstige_total":
            return "Sonstig gesamt"
        if column_id.startswith("grade_"):
            raw_id = column_id[len("grade_") :]
            for grade in self.current_plan.grade_columns if self.current_plan else []:
                if grade.column_id == raw_id:
                    return grade.title
        return column_id

    def _on_docs_horizontal_nav(self, delta: int) -> str:
        if not self._shortcut_scope_allows("docs"):
            return "break"

        if delta > 0:
            if self._doc_selected_fixed_column_id is None:
                if self._doc_dates and self._doc_selected_date_index < len(self._doc_dates) - 1:
                    self._doc_selected_date_index += 1
                elif self._doc_fixed_column_ids:
                    self._doc_selected_fixed_column_id = self._doc_fixed_column_ids[0]
                self._apply_doc_column_heading_highlight()
                return "break"
            if self._doc_selected_fixed_column_id not in self._doc_fixed_column_ids:
                self._doc_selected_fixed_column_id = self._doc_fixed_column_ids[0] if self._doc_fixed_column_ids else None
                self._apply_doc_column_heading_highlight()
                return "break"
            idx = self._doc_fixed_column_ids.index(self._doc_selected_fixed_column_id)
            if idx < len(self._doc_fixed_column_ids) - 1:
                self._doc_selected_fixed_column_id = self._doc_fixed_column_ids[idx + 1]
            self._apply_doc_column_heading_highlight()
            return "break"

        if self._doc_selected_fixed_column_id is None:
            if self._doc_dates:
                self._doc_selected_date_index = max(0, self._doc_selected_date_index - 1)
                self._apply_doc_column_heading_highlight()
            return "break"

        if self._doc_selected_fixed_column_id not in self._doc_fixed_column_ids:
            self._doc_selected_fixed_column_id = None
            self._apply_doc_column_heading_highlight()
            return "break"
        idx = self._doc_fixed_column_ids.index(self._doc_selected_fixed_column_id)
        if idx > 0:
            self._doc_selected_fixed_column_id = self._doc_fixed_column_ids[idx - 1]
        else:
            self._doc_selected_fixed_column_id = None
        self._apply_doc_column_heading_highlight()
        return "break"

    def rename_selected_documentation_date_dialog(self) -> None:
        if not self.current_plan or not self._doc_dates:
            return
        old_date = self._doc_dates[self._doc_selected_date_index]
        new_date = simpledialog.askstring(
            "Datum umbenennen",
            "Neues Datum (YYYY-MM-DD):",
            parent=self,
            initialvalue=old_date,
        )
        if new_date is None:
            return
        updated = rename_documentation_date(self.current_plan, old_date, new_date)
        updated = ensure_documentation_date(updated, new_date)
        self._record_and_save(updated, "documentation.date.rename", "Dokudatum umbenannt")
        self._refresh_documentation_table()

    def select_today_documentation_date(self) -> None:
        if not self._doc_dates:
            return
        self._doc_selected_fixed_column_id = None
        today = self._today_doc_date()
        if today in self._doc_dates:
            self._doc_selected_date_index = self._doc_dates.index(today)
        else:
            self._doc_selected_date_index = len(self._doc_dates) - 1
        self._apply_doc_column_heading_highlight()

    def add_grade_column_dialog(self) -> None:
        if not self.current_plan:
            return
        category = simpledialog.askstring(
            "Notenspalte",
            "Typ eingeben: schriftlich oder sonstig",
            parent=self,
        )
        if category is None:
            return
        title = simpledialog.askstring("Notenspalte", "Kurzer Titel:", parent=self)
        if title is None:
            return
        updated, column_id = add_grade_column(self.current_plan, category.strip().lower(), title)
        if not column_id:
            messagebox.showerror("Ungueltige Eingabe", "Typ muss 'schriftlich' oder 'sonstig' sein.", parent=self)
            return
        self._record_and_save(updated, "documentation.grade_column.add", "Notenspalte hinzugefuegt")
        self._refresh_documentation_table()

    def set_selected_documentation_grade_dialog(self, selected_column_id: str | None = None) -> None:
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        if not self.current_plan.grade_columns:
            messagebox.showinfo("Keine Notenspalten", "Bitte zuerst eine Notenspalte hinzufügen.", parent=self)
            return
        column = None
        if selected_column_id:
            for item in self.current_plan.grade_columns:
                if item.column_id == selected_column_id:
                    column = item
                    break

        if column is None:
            if self._doc_selected_fixed_column_id and self._doc_selected_fixed_column_id.startswith("grade_"):
                selected_column_id = self._doc_selected_fixed_column_id[len("grade_") :]
                for item in self.current_plan.grade_columns:
                    if item.column_id == selected_column_id:
                        column = item
                        break
            if column is None:
                column = self.current_plan.grade_columns[0]

        self._doc_selected_fixed_column_id = f"grade_{column.column_id}"
        self._refresh_doc_selection_status()
        self._open_selected_docs_grade_cell_editor()

    def set_selected_documentation_symbol_dialog(self) -> None:
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return
        if not self.symbol_catalog:
            messagebox.showinfo("Keine Symbole", "Es sind keine Symbole konfiguriert.", parent=self)
            return

        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        date_key = self._doc_dates[date_index]
        preferred_symbol: str | None = None
        desk = self.current_plan.desk_at(x, y)
        if desk and desk.desk_type == "student":
            entry = desk.documentation_entries.get(date_key)
            if entry and entry.symbols:
                non_zero_symbols = [
                    symbol for symbol in self.symbol_catalog if int(entry.symbols.get(symbol, 0)) > 0
                ]
                if non_zero_symbols:
                    preferred_symbol = non_zero_symbols[0]

        dialog = self._create_overlay_dialog("Symbol setzen", "360x420")
        frame = ttk.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(frame, text="Symbol auswählen").pack(anchor="w", pady=(0, 6))
        ttk.Label(
            frame,
            text="Tastatur: 1-9 waehlt, 0 loescht, Enter uebernimmt, Entf/Backspace loescht, Esc schliesst",
            foreground="#666666",
        ).pack(
            anchor="w", pady=(0, 6)
        )

        symbol_listbox = tk.Listbox(frame, selectmode="browse", exportselection=False, font=("Segoe UI", 11))
        symbol_listbox.pack(fill="both", expand=True)

        for symbol in self.symbol_catalog:
            shortcut = self._symbol_by_meaning.get(symbol).shortcut if self._symbol_by_meaning.get(symbol) else None
            shortcut_suffix = f" [{shortcut.upper()}]" if shortcut else ""
            symbol_listbox.insert(tk.END, f"{self._symbol_glyph(symbol)} {symbol}{shortcut_suffix}")

        if self.symbol_catalog:
            selected_index = max(0, min(self._docs_symbol_dialog_last_index, len(self.symbol_catalog) - 1))
            if preferred_symbol in self.symbol_catalog:
                selected_index = self.symbol_catalog.index(preferred_symbol)
            symbol_listbox.selection_set(selected_index)
            symbol_listbox.activate(selected_index)
            symbol_listbox.see(selected_index)
        self._focus_overlay_widget(dialog, symbol_listbox)

        def apply_symbol() -> None:
            selected = symbol_listbox.curselection()
            if not selected:
                return
            selected_index = int(selected[0])
            self._docs_symbol_dialog_last_index = selected_index
            symbol_name = self.symbol_catalog[selected_index]
            self._toggle_documentation_symbol(symbol_name)
            dialog.destroy()

        def clear_symbol() -> None:
            if not self.current_plan:
                return
            selected = symbol_listbox.curselection()
            if not selected:
                return
            selected_index = int(selected[0])
            self._docs_symbol_dialog_last_index = selected_index
            symbol_name = self.symbol_catalog[selected_index]
            updated = set_documentation_symbol(self.current_plan, x, y, symbol_name, 0, date_key)
            self._record_and_save(updated, "documentation.symbol.clear", f"Dokumentation '{symbol_name}' geloescht")
            self._refresh_documentation_table()
            dialog.destroy()

        dialog.bind("<Delete>", lambda _event: clear_symbol())
        dialog.bind("<BackSpace>", lambda _event: clear_symbol())
        dialog.bind("<0>", lambda _event: clear_symbol())
        dialog.bind("<KP_0>", lambda _event: clear_symbol())

        symbol_listbox.bind("<Double-Button-1>", lambda _event: apply_symbol())
        symbol_listbox.bind("<Return>", lambda _event: apply_symbol())
        symbol_listbox.bind("<KP_Enter>", lambda _event: apply_symbol())

        def select_by_digit(index: int) -> None:
            if index < 0 or index >= len(self.symbol_catalog):
                return
            symbol_listbox.selection_clear(0, tk.END)
            symbol_listbox.selection_set(index)
            symbol_listbox.activate(index)
            symbol_listbox.see(index)

        for digit in range(1, 10):
            select_index = digit - 1
            dialog.bind(f"<{digit}>", lambda _event, i=select_index: select_by_digit(i))
            dialog.bind(f"<KP_{digit}>", lambda _event, i=select_index: select_by_digit(i))

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(8, 0))
        ttk.Button(button_row, text="Abbrechen", command=dialog.destroy).pack(side="right")
        ttk.Button(button_row, text="Übernehmen", command=apply_symbol).pack(side="right", padx=(0, 8))
        ttk.Button(button_row, text="Loeschen", command=clear_symbol).pack(side="left")

    def configure_grade_weighting_dialog(self) -> None:
        if not self.current_plan:
            return

        written_text = simpledialog.askstring(
            "Gewichtung",
            "Anteil schriftlich in %:",
            parent=self,
            initialvalue=str(self.current_plan.written_weight_percent),
        )
        if written_text is None:
            return
        sonstige_text = simpledialog.askstring(
            "Gewichtung",
            "Anteil sonstig in %:",
            parent=self,
            initialvalue=str(self.current_plan.sonstige_weight_percent),
        )
        if sonstige_text is None:
            return

        try:
            written_percent = int(written_text.strip())
            sonstige_percent = int(sonstige_text.strip())
        except ValueError:
            messagebox.showerror("Ungueltige Eingabe", "Bitte ganze Prozentzahlen eingeben.", parent=self)
            return

        updated = set_grade_weighting(self.current_plan, written_percent, sonstige_percent)
        self._record_and_save(updated, "documentation.weighting.set", "Gewichtung aktualisiert")
        self._refresh_documentation_table()

    def open_selected_plan_from_list(self) -> None:
        self._ensure_list_selection()
        selected = self.plan_listbox.curselection()
        if not selected:
            return

        index = int(selected[0])
        if index < 0 or index >= len(self._plan_index):
            return

        plan_path, _ = self._plan_index[index]
        self.open_plan(plan_path)

    def open_plan(self, plan_path: Path) -> None:
        started = time.perf_counter()
        LOGGER.info("open_plan started: %s", plan_path)
        try:
            load_started = time.perf_counter()
            plan = self.plan_repository.load_plan(plan_path)
            LOGGER.info("open_plan load_plan finished in %.3fs", time.perf_counter() - load_started)
        except Exception as exc:
            LOGGER.exception("open_plan failed while loading %s", plan_path)
            messagebox.showerror("Fehler beim Öffnen", str(exc))
            return

        out_of_bounds = self._count_out_of_bounds_desks(plan)
        if out_of_bounds > 0:
            messagebox.showwarning(
                "Plan nur teilweise darstellbar",
                f"{out_of_bounds} Schuelertische liegen ausserhalb des aktuellen Canvas-Bereichs (+/-{self.canvas_radius}) und koennen nicht angezeigt werden.",
                parent=self,
            )

        self.current_plan_path = plan_path
        apply_started = time.perf_counter()
        self._apply_loaded_plan(plan)
        LOGGER.info("open_plan _apply_loaded_plan finished in %.3fs", time.perf_counter() - apply_started)
        self.plan_name_var.set(f"Plan: {plan.name}")
        self._set_selection_single(0, 0)

        render_started = time.perf_counter()
        self.show_editor_view()
        self.center_on_cell(0, 0)
        self.redraw_grid()
        self._refresh_details_panel()
        self._refresh_documentation_table()
        LOGGER.info(
            "open_plan UI render stage finished in %.3fs", time.perf_counter() - render_started
        )
        LOGGER.info("open_plan finished in %.3fs", time.perf_counter() - started)

    def create_new_plan_dialog(self) -> None:
        while True:
            plan_name = simpledialog.askstring("Neuer Sitzplan", "Name der Lerngruppe:", parent=self)
            if plan_name is None:
                return

            try:
                plan_path, _plan = self.plan_repository.create_new_plan(self.plans_dir, plan_name)
                self.refresh_plan_list()
                self.open_plan(plan_path)
                return
            except FileExistsError:
                overwrite = messagebox.askyesnocancel(
                    "Datei existiert bereits",
                    "Für diese Lerngruppe existiert bereits ein Plan. Überschreiben?",
                    parent=self,
                )
                if overwrite is None:
                    return
                if overwrite:
                    plan_path, _plan = self.plan_repository.create_new_plan(self.plans_dir, plan_name, overwrite=True)
                    self.refresh_plan_list()
                    self.open_plan(plan_path)
                    return
                # overwrite == False: erneut Namen fragen
                continue
            except Exception as exc:
                messagebox.showerror("Fehler", f"Neuer Sitzplan konnte nicht erstellt werden:\n{exc}")
                return

    def _selected_plan_list_entry(self) -> tuple[int, Path, SeatingPlan] | None:
        self._ensure_list_selection()
        selected = self.plan_listbox.curselection()
        if not selected:
            return None
        index = int(selected[0])
        if index < 0 or index >= len(self._plan_index):
            return None
        path, plan = self._plan_index[index]
        return index, path, plan

    def _record_plan_list_action(self, action: dict[str, object]) -> None:
        self._plan_list_undo_actions.append(action)
        max_steps = max(1, int(self.history.max_undo_steps))
        overflow = len(self._plan_list_undo_actions) - max_steps
        if overflow > 0:
            self._plan_list_undo_actions = self._plan_list_undo_actions[overflow:]
        self._plan_list_redo_actions = []

    def _default_duplicate_name(self, source_name: str) -> str:
        base = source_name.strip() or "Neuer Sitzplan"
        return f"{base} Kopie"

    def _clear_current_plan_if_matches(self, plan_path: Path) -> None:
        if self.current_plan_path != plan_path:
            return
        self.current_plan_path = None
        self.current_plan = None
        self.plan_name_var.set("")
        self._set_selection_single(0, 0)
        self._refresh_details_panel()

    def rename_selected_plan_dialog(self) -> None:
        selected = self._selected_plan_list_entry()
        if not selected:
            self.status_var.set("Kein Sitzplan ausgewaehlt")
            return

        _index, plan_path, plan = selected

        while True:
            plan_name = simpledialog.askstring(
                "Sitzplan umbenennen",
                "Neuer Name der Lerngruppe:",
                parent=self,
                initialvalue=plan.name,
            )
            if plan_name is None:
                return
            if not plan_name.strip():
                messagebox.showerror("Fehler", "Bitte gib einen Namen ein.", parent=self)
                continue

            try:
                new_path, renamed_plan = self.plan_repository.rename_plan(plan_path, plan_name)
                if self.current_plan_path == plan_path and self.current_plan is not None:
                    self.current_plan_path = new_path
                    self.current_plan.name = renamed_plan.name
                    self.plan_name_var.set(f"Plan: {renamed_plan.name}")
                self._record_plan_list_action(
                    {
                        "kind": "rename",
                        "before_path": plan_path,
                        "after_path": new_path,
                        "before_name": plan.name,
                        "after_name": renamed_plan.name,
                    }
                )
                self.refresh_plan_list()
                self._ensure_list_selection(preferred_path=new_path)
                self.status_var.set(f"Plan umbenannt: {renamed_plan.name}")
                return
            except FileExistsError:
                overwrite = messagebox.askyesnocancel(
                    "Datei existiert bereits",
                    "Für diese Lerngruppe existiert bereits ein Plan. Überschreiben?",
                    parent=self,
                )
                if overwrite is None:
                    return
                if overwrite:
                    try:
                        new_path, renamed_plan = self.plan_repository.rename_plan(plan_path, plan_name, overwrite=True)
                        if self.current_plan_path == plan_path and self.current_plan is not None:
                            self.current_plan_path = new_path
                            self.current_plan.name = renamed_plan.name
                            self.plan_name_var.set(f"Plan: {renamed_plan.name}")
                        self._record_plan_list_action(
                            {
                                "kind": "rename",
                                "before_path": plan_path,
                                "after_path": new_path,
                                "before_name": plan.name,
                                "after_name": renamed_plan.name,
                            }
                        )
                        self.refresh_plan_list()
                        self._ensure_list_selection(preferred_path=new_path)
                        self.status_var.set(f"Plan umbenannt: {renamed_plan.name}")
                        return
                    except Exception as exc:
                        messagebox.showerror("Fehler", f"Sitzplan konnte nicht umbenannt werden:\n{exc}", parent=self)
                        return
                continue
            except Exception as exc:
                messagebox.showerror("Fehler", f"Sitzplan konnte nicht umbenannt werden:\n{exc}", parent=self)
                return

    def delete_selected_plan_dialog(self) -> None:
        selected = self._selected_plan_list_entry()
        if not selected:
            self.status_var.set("Kein Sitzplan ausgewaehlt")
            return

        index, plan_path, plan = selected
        confirm = messagebox.askyesno(
            "Sitzplan loeschen",
            f"Moechtest du den Sitzplan '{plan.name}' wirklich loeschen?",
            parent=self,
        )
        if not confirm:
            return

        try:
            deleted_plan = deepcopy(self.plan_repository.load_plan(plan_path))
            self.plan_repository.delete_plan(plan_path)
            self._clear_current_plan_if_matches(plan_path)
            self._record_plan_list_action(
                {
                    "kind": "delete",
                    "deleted_path": plan_path,
                    "deleted_plan": deleted_plan,
                }
            )
            self.refresh_plan_list()
            if self._plan_index:
                preferred_index = max(0, min(index, len(self._plan_index) - 1))
                self._ensure_list_selection(preferred_path=self._plan_index[preferred_index][0])
            self.status_var.set(f"Plan geloescht: {plan.name}")
        except Exception as exc:
            messagebox.showerror("Fehler", f"Sitzplan konnte nicht geloescht werden:\n{exc}", parent=self)

    def duplicate_selected_plan_dialog(self) -> None:
        selected = self._selected_plan_list_entry()
        if not selected:
            self.status_var.set("Kein Sitzplan ausgewaehlt")
            return

        _index, plan_path, plan = selected
        suggested_name = self._default_duplicate_name(plan.name)

        while True:
            plan_name = simpledialog.askstring(
                "Sitzplan duplizieren",
                "Name der Lerngruppe:",
                parent=self,
                initialvalue=suggested_name,
            )
            if plan_name is None:
                return
            if not plan_name.strip():
                messagebox.showerror("Fehler", "Bitte gib einen Namen ein.", parent=self)
                continue

            try:
                duplicate_path, duplicate_plan = self.plan_repository.duplicate_plan(plan_path, plan_name)
                self._record_plan_list_action(
                    {
                        "kind": "duplicate",
                        "duplicate_path": duplicate_path,
                        "duplicate_plan": deepcopy(duplicate_plan),
                    }
                )
                self.refresh_plan_list()
                self._ensure_list_selection(preferred_path=duplicate_path)
                self.status_var.set(f"Plan dupliziert: {duplicate_plan.name}")
                return
            except FileExistsError:
                overwrite = messagebox.askyesnocancel(
                    "Datei existiert bereits",
                    "Für diese Lerngruppe existiert bereits ein Plan. Überschreiben?",
                    parent=self,
                )
                if overwrite is None:
                    return
                if overwrite:
                    try:
                        duplicate_path, duplicate_plan = self.plan_repository.duplicate_plan(
                            plan_path,
                            plan_name,
                            overwrite=True,
                        )
                        self._record_plan_list_action(
                            {
                                "kind": "duplicate",
                                "duplicate_path": duplicate_path,
                                "duplicate_plan": deepcopy(duplicate_plan),
                            }
                        )
                        self.refresh_plan_list()
                        self._ensure_list_selection(preferred_path=duplicate_path)
                        self.status_var.set(f"Plan dupliziert: {duplicate_plan.name}")
                        return
                    except Exception as exc:
                        messagebox.showerror("Fehler", f"Sitzplan konnte nicht dupliziert werden:\n{exc}", parent=self)
                        return
                continue
            except Exception as exc:
                messagebox.showerror("Fehler", f"Sitzplan konnte nicht dupliziert werden:\n{exc}", parent=self)
                return

    def _undo_plan_list_action(self) -> bool:
        if not self._plan_list_undo_actions:
            return False

        action = self._plan_list_undo_actions.pop()
        kind = str(action.get("kind") or "")
        try:
            if kind == "rename":
                source_path = action["after_path"]
                target_name = str(action["before_name"])
                restored_path, restored_plan = self.plan_repository.rename_plan(source_path, target_name, overwrite=True)
                action["before_path"] = restored_path
                if self.current_plan_path == source_path and self.current_plan is not None:
                    self.current_plan_path = restored_path
                    self.current_plan.name = restored_plan.name
                    self.plan_name_var.set(f"Plan: {restored_plan.name}")
                preferred_path = restored_path
            elif kind == "delete":
                deleted_path = action["deleted_path"]
                deleted_plan = deepcopy(action["deleted_plan"])
                self.plan_repository.save_plan(deleted_plan, deleted_path)
                preferred_path = deleted_path
            elif kind == "duplicate":
                duplicate_path = action["duplicate_path"]
                self.plan_repository.delete_plan(duplicate_path)
                self._clear_current_plan_if_matches(duplicate_path)
                preferred_path = self.current_plan_path
            else:
                self._plan_list_undo_actions.append(action)
                return False
        except Exception as exc:
            self._plan_list_undo_actions.append(action)
            self.status_var.set(f"Rueckgaengig fehlgeschlagen: {exc}")
            return False

        self._plan_list_redo_actions.append(action)
        self.refresh_plan_list()
        if preferred_path is not None:
            self._ensure_list_selection(preferred_path=preferred_path)
        self.status_var.set("Rueckgaengig")
        return True

    def _redo_plan_list_action(self) -> bool:
        if not self._plan_list_redo_actions:
            return False

        action = self._plan_list_redo_actions.pop()
        kind = str(action.get("kind") or "")
        try:
            if kind == "rename":
                source_path = action["before_path"]
                target_name = str(action["after_name"])
                restored_path, restored_plan = self.plan_repository.rename_plan(source_path, target_name, overwrite=True)
                action["after_path"] = restored_path
                if self.current_plan_path == source_path and self.current_plan is not None:
                    self.current_plan_path = restored_path
                    self.current_plan.name = restored_plan.name
                    self.plan_name_var.set(f"Plan: {restored_plan.name}")
                preferred_path = restored_path
            elif kind == "delete":
                deleted_path = action["deleted_path"]
                self.plan_repository.delete_plan(deleted_path)
                self._clear_current_plan_if_matches(deleted_path)
                preferred_path = self.current_plan_path
            elif kind == "duplicate":
                duplicate_path = action["duplicate_path"]
                duplicate_plan = deepcopy(action["duplicate_plan"])
                self.plan_repository.save_plan(duplicate_plan, duplicate_path)
                preferred_path = duplicate_path
            else:
                self._plan_list_redo_actions.append(action)
                return False
        except Exception as exc:
            self._plan_list_redo_actions.append(action)
            self.status_var.set(f"Wiederholen fehlgeschlagen: {exc}")
            return False

        self._plan_list_undo_actions.append(action)
        self.refresh_plan_list()
        if preferred_path is not None:
            self._ensure_list_selection(preferred_path=preferred_path)
        self.status_var.set("Wiederholt")
        return True

    def open_settings_dialog(self) -> None:
        dialog = self._create_overlay_dialog("Einstellungen", "700x320")

        frame = ttk.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        path_var = tk.StringVar(value=str(self.plans_dir))
        ttk.Label(frame, text="Sitzplan-Ordner").pack(anchor="w")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(6, 12))

        entry = ttk.Entry(row, textvariable=path_var)
        entry.pack(side="left", fill="x", expand=True)
        self._focus_overlay_widget(dialog, entry)

        def browse() -> None:
            selected = filedialog.askdirectory(initialdir=str(self.plans_dir), parent=dialog)
            if selected:
                path_var.set(selected)

        ttk.Button(row, text="Durchsuchen", command=browse).pack(side="left", padx=(8, 0))

        canvas_row = ttk.Frame(frame)
        canvas_row.pack(fill="x", pady=(0, 12))
        ttk.Label(canvas_row, text="Canvas-Halbbreite (1-50)").pack(side="left")
        radius_var = tk.StringVar(value=str(self.canvas_radius))
        radius_spin = ttk.Spinbox(
            canvas_row,
            from_=MIN_CANVAS_RADIUS,
            to=MAX_CANVAS_RADIUS,
            textvariable=radius_var,
            width=8,
        )
        radius_spin.pack(side="left", padx=(10, 0))
        ttk.Label(canvas_row, text="entspricht (0,0) + Radius in jede Richtung").pack(side="left", padx=(10, 0))

        symbol_row = ttk.Frame(frame)
        symbol_row.pack(fill="x", pady=(0, 12))
        ttk.Label(symbol_row, text="Symbolstaerke").pack(side="left")
        symbol_strength_labels = {0: "Normal", 1: "Fett", 2: "Extra"}
        symbol_strength_values = {"Normal": 0, "Fett": 1, "Extra": 2}
        symbol_strength_var = tk.StringVar(value=symbol_strength_labels.get(self.symbol_strength, "Fett"))
        symbol_strength_combo = ttk.Combobox(
            symbol_row,
            textvariable=symbol_strength_var,
            values=["Normal", "Fett", "Extra"],
            state="readonly",
            width=12,
        )
        symbol_strength_combo.pack(side="left", padx=(10, 0))

        follow_row = ttk.Frame(frame)
        follow_row.pack(fill="x", pady=(0, 12))
        ttk.Label(follow_row, text="Sichtfenster-Puffer (0-5)").pack(side="left")
        follow_buffer_var = tk.StringVar(value=str(self.viewport_follow_buffer))
        follow_spin = ttk.Spinbox(
            follow_row,
            from_=0,
            to=5,
            textvariable=follow_buffer_var,
            width=8,
        )
        follow_spin.pack(side="left", padx=(10, 0))
        ttk.Label(follow_row, text="0 = immer zentrieren, 1 = 3x3-Zentrum").pack(side="left", padx=(10, 0))

        def save() -> None:
            selected_path = Path(path_var.get().strip() or str(self.default_plans_dir))
            selected_path.mkdir(parents=True, exist_ok=True)
            new_radius = self._normalize_canvas_radius(radius_var.get())

            if self.current_plan and new_radius < self.canvas_radius:
                out_of_bounds = self._count_out_of_bounds_desks(self.current_plan, radius=new_radius)
                if out_of_bounds > 0:
                    proceed = messagebox.askyesno(
                        "Warnung",
                        f"Bei Canvas-Radius {new_radius} waeren {out_of_bounds} Schuelertische nicht mehr sichtbar. Trotzdem speichern?",
                        parent=dialog,
                    )
                    if not proceed:
                        return

            self.plans_dir = selected_path
            self._settings["plans_dir"] = str(selected_path)
            self.canvas_radius = new_radius
            self._settings["canvas_radius"] = new_radius
            self.symbol_strength = symbol_strength_values.get(symbol_strength_var.get(), DEFAULT_SYMBOL_STRENGTH)
            self._settings["symbol_strength"] = self.symbol_strength
            self.viewport_follow_buffer = self._normalize_viewport_follow_buffer(follow_buffer_var.get())
            self._settings["viewport_follow_buffer"] = self.viewport_follow_buffer
            self.settings_repository.save_settings(self._settings)
            self._update_scroll_region()
            self._set_selection_single(*self.selection.active_cell())
            self.redraw_grid()
            self._refresh_details_panel()
            self.refresh_plan_list()
            dialog.destroy()

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x")
        ttk.Button(button_row, text="Speichern", command=save).pack(side="right")

    def _xview(self, *args) -> None:
        self.canvas.xview(*args)
        self.redraw_grid()

    def _yview(self, *args) -> None:
        self.canvas.yview(*args)
        self.redraw_grid()

    def _docs_yview(self, *args) -> None:
        self.docs_tree.yview(*args)
        self.docs_right_tree.yview(*args)

    def _on_docs_main_yscroll(self, first: str, last: str) -> None:
        self.docs_y_scroll.set(first, last)
        if self._syncing_docs_scroll:
            return
        self._syncing_docs_scroll = True
        try:
            self.docs_right_tree.yview_moveto(float(first))
        finally:
            self._syncing_docs_scroll = False

    def _on_docs_right_yscroll(self, first: str, last: str) -> None:
        self.docs_y_scroll.set(first, last)
        if self._syncing_docs_scroll:
            return
        self._syncing_docs_scroll = True
        try:
            self.docs_tree.yview_moveto(float(first))
        finally:
            self._syncing_docs_scroll = False

    def _on_canvas_xscroll(self, first: str, last: str) -> None:
        self.x_scroll.set(first, last)
        self.redraw_grid()

    def _on_canvas_yscroll(self, first: str, last: str) -> None:
        self.y_scroll.set(first, last)
        self.redraw_grid()

    def _on_canvas_click(self, event) -> None:
        x, y = self._event_to_cell(event)
        self._set_selection_single(x, y)
        self._drag_active = True
        self.interaction_mode = GRID_SELECTED
        self.canvas.focus_set()
        self.redraw_grid()
        self._refresh_details_panel()

    def _on_canvas_drag(self, event) -> None:
        if not self._drag_active:
            return
        x, y = self._event_to_cell(event)
        self._set_selection_focus(x, y)
        self.redraw_grid()
        self._refresh_details_panel()

    def _on_canvas_release(self, event) -> None:
        if not self._drag_active:
            return
        self._drag_active = False
        x, y = self._event_to_cell(event)
        self._set_selection_focus(x, y)
        self.redraw_grid()
        self._refresh_details_panel()

    def _on_canvas_double_click(self, event) -> None:
        x, y = self._event_to_cell(event)
        self._set_selection_single(x, y)
        self.confirm_selected_cell()
        self.enter_name_edit_mode()

    def _event_to_cell(self, event) -> tuple[int, int]:
        world_x = int((self.canvas.canvasx(event.x)) // self.cell_size)
        world_y = int((self.canvas.canvasy(event.y)) // self.cell_size)
        return self._clamp_cell(world_x, world_y)

    def _on_mouse_wheel(self, event) -> None:
        steps = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(steps, "units")
        self.redraw_grid()

    def _on_shift_mouse_wheel(self, event) -> None:
        steps = -1 if event.delta > 0 else 1
        self.canvas.xview_scroll(steps, "units")
        self.redraw_grid()

    def _on_ctrl_mouse_wheel(self, event) -> None:
        if event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self) -> None:
        self._apply_zoom(self.cell_size + 8)

    def zoom_out(self) -> None:
        self._apply_zoom(self.cell_size - 8)

    def _apply_zoom(self, new_size: int) -> None:
        clamped = max(44, min(160, new_size))
        if clamped == self.cell_size:
            return

        anchor_x, anchor_y = self.selection.active_cell()
        self.cell_size = clamped
        self._update_scroll_region()
        self.redraw_grid()
        self.center_on_cell(anchor_x, anchor_y)

    def reset_viewport(self) -> None:
        self.cell_size = DEFAULT_CELL_SIZE
        self._update_scroll_region()
        self._set_selection_single(0, 0)
        self.center_on_cell(0, 0)
        self.redraw_grid()
        self._refresh_details_panel()

    def center_on_cell(self, x: int, y: int) -> None:
        self.update_idletasks()

        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        min_x, min_y, max_x, max_y = self._grid_pixel_bounds()
        total_w = max_x - min_x
        total_h = max_y - min_y

        cx, cy = self._clamp_cell(x, y)
        target_x = cx * self.cell_size + self.cell_size / 2
        target_y = cy * self.cell_size + self.cell_size / 2

        left = target_x - width / 2
        top = target_y - height / 2

        x_fraction = (left - min_x) / max(1, total_w)
        y_fraction = (top - min_y) / max(1, total_h)

        self.canvas.xview_moveto(max(0.0, min(1.0, x_fraction)))
        self.canvas.yview_moveto(max(0.0, min(1.0, y_fraction)))

    def redraw_grid(self) -> None:
        self.canvas.delete("grid")
        if not self.current_plan:
            return

        normalize_tablegroups_in_place(self.current_plan)

        theme = THEMES[self.theme_key]
        left = self.canvas.canvasx(0)
        top = self.canvas.canvasy(0)
        right = self.canvas.canvasx(self.canvas.winfo_width())
        bottom = self.canvas.canvasy(self.canvas.winfo_height())

        start_x = int(left // self.cell_size) - 1
        end_x = int(right // self.cell_size) + 1
        start_y = int(top // self.cell_size) - 1
        end_y = int(bottom // self.cell_size) + 1

        min_grid = self._grid_min()
        max_grid = self._grid_max()
        start_x = max(min_grid, start_x)
        end_x = min(max_grid, end_x)
        start_y = max(min_grid, start_y)
        end_y = min(max_grid, end_y)

        geometries = build_desk_geometries(self.current_plan)
        geometry_by_coord = {
            (geometry.desk.x, geometry.desk.y): geometry
            for geometry in geometries
            if geometry.desk.desk_type == "student"
        }
        selected_cells = set(self.selection.cells())
        selected_tablegroups: set[int] = set()
        for cell_x, cell_y in selected_cells:
            number = tablegroup_number_at(self.current_plan, cell_x, cell_y)
            if number is not None:
                selected_tablegroups.add(number)

        student_name_font_size = self._compute_uniform_student_name_font_size()

        for cy in range(start_y, end_y + 1):
            for cx in range(start_x, end_x + 1):
                x1 = cx * self.cell_size
                y1 = cy * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=theme["empty_fill"],
                    outline=theme["grid_line"],
                    width=1,
                    tags=("grid",),
                )

        for desk in self.current_plan.desks:
            if desk.desk_type == "teacher":
                x1 = desk.x * self.cell_size
                y1 = desk.y * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                if x2 < left - self.cell_size or x1 > right + self.cell_size or y2 < top - self.cell_size or y1 > bottom + self.cell_size:
                    continue

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=theme["teacher_fill"],
                    outline=theme["grid_line"],
                    width=1,
                    tags=("grid",),
                )
                self.canvas.create_text(
                    x1 + self.cell_size / 2,
                    y1 + self.cell_size / 2,
                    text="Lehrertisch",
                    fill=theme["teacher_text"],
                    font=("Segoe UI", max(8, int(self.cell_size * 0.12)), "bold"),
                    tags=("grid",),
                )
                continue

            geometry = geometry_by_coord.get((desk.x, desk.y))
            if geometry is None:
                continue
            polygon_points: list[float] = []
            min_px = float("inf")
            min_py = float("inf")
            max_px = float("-inf")
            max_py = float("-inf")

            for world_x, world_y in geometry.polygon:
                px = world_x * self.cell_size
                py = world_y * self.cell_size
                polygon_points.extend((px, py))
                min_px = min(min_px, px)
                min_py = min(min_py, py)
                max_px = max(max_px, px)
                max_py = max(max_py, py)

            if max_px < left - self.cell_size or min_px > right + self.cell_size or max_py < top - self.cell_size or min_py > bottom + self.cell_size:
                continue

            self.canvas.create_polygon(
                polygon_points,
                fill=theme["student_fill"],
                outline=theme["grid_line"],
                width=1,
                tags=("grid",),
            )

            main_text = (desk.student_name or "").strip()
            effective_symbols = self._effective_grid_symbols(desk.x, desk.y, desk.symbols)
            symbol_lines = self._symbol_grid_lines(effective_symbols)
            desk_color_markers = self._ordered_color_markers(desk.color_markers)
            center_px = geometry.center_x * self.cell_size

            if desk_color_markers:
                radius = max(3, int(self.cell_size * 0.03))
                spacing = radius * 2 + 3
                start_x = center_px + self.cell_size * 0.17
                circles_y = min_py + self.cell_size * 0.12
                for idx, color_key in enumerate(desk_color_markers[:9]):
                    _label, hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
                    cx = start_x + idx * spacing
                    self.canvas.create_oval(
                        cx - radius,
                        circles_y - radius,
                        cx + radius,
                        circles_y + radius,
                        fill=hex_color,
                        outline=theme["grid_line"],
                        width=1,
                        tags=("grid",),
                    )

            overall_grade = compute_grade_display_for_student(self.current_plan, desk.x, desk.y)
            if overall_grade:
                self.canvas.create_text(
                    min_px + self.cell_size * 0.08,
                    min_py + self.cell_size * 0.09,
                    text=overall_grade,
                    fill=theme["fg_muted"],
                    font=("Segoe UI", max(6, int(self.cell_size * 0.085)), "bold"),
                    anchor="nw",
                    tags=("grid",),
                )

            if main_text:
                self.canvas.create_text(
                    center_px,
                    min_py + self.cell_size * 0.24,
                    text=main_text,
                    fill=theme["fg_main"],
                    font=("Segoe UI", student_name_font_size, "bold"),
                    tags=("grid",),
                )

            if symbol_lines:
                available_h = self.cell_size * 0.56
                raw_symbol_font = int(available_h / max(1, len(symbol_lines)) - 1)
                symbol_font = max(5, min(int(self.cell_size * 0.09), raw_symbol_font))
                symbol_size, symbol_weight = self._symbol_font_style(symbol_font)
                line_height = max(symbol_size + 2, 6)
                symbols_start_y = min_py + self.cell_size * 0.42

                for idx, line in enumerate(symbol_lines):
                    self.canvas.create_text(
                        center_px,
                        symbols_start_y + idx * line_height,
                        text=line,
                        fill=theme["fg_muted"],
                        font=("Segoe UI", symbol_size, symbol_weight),
                        tags=("grid",),
                    )

        for number in sorted(selected_tablegroups):
            bounds = group_bounds_from_geometries(geometries, number)
            if bounds is None:
                continue
            min_x, min_y, max_x, max_y = bounds
            self.canvas.create_rectangle(
                min_x * self.cell_size,
                min_y * self.cell_size,
                max_x * self.cell_size,
                max_y * self.cell_size,
                outline=theme["fg_muted"],
                width=1,
                dash=(4, 2),
                tags=("grid",),
            )

        for number in list_tablegroup_numbers(self.current_plan):
            bounds = group_bounds_from_geometries(geometries, number)
            if bounds is None:
                continue
            min_x, _min_y, max_x, max_y = bounds
            label_x = (min_x + max_x) / 2
            label_y = max_y + 0.12
            self.canvas.create_text(
                label_x * self.cell_size,
                label_y * self.cell_size,
                text=f"TG {number}",
                fill=theme["fg_muted"],
                font=("Segoe UI", max(7, int(self.cell_size * 0.09)), "bold"),
                tags=("grid",),
            )

        selection_bounds = selection_bounds_from_geometries(geometries, selected_cells)
        if selection_bounds is not None:
            min_sel_x, min_sel_y, max_sel_x, max_sel_y = selection_bounds
            x1 = min_sel_x * self.cell_size
            y1 = min_sel_y * self.cell_size
            x2 = max_sel_x * self.cell_size
            y2 = max_sel_y * self.cell_size
        else:
            min_sel_x, min_sel_y, max_sel_x, max_sel_y = self.selection.bounds()
            x1 = min_sel_x * self.cell_size
            y1 = min_sel_y * self.cell_size
            x2 = (max_sel_x + 1) * self.cell_size
            y2 = (max_sel_y + 1) * self.cell_size

        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline=theme["focus_ring"],
            width=3,
            tags=("grid",),
        )

    def _symbol_font_style(self, base_size: int) -> tuple[int, str]:
        if self.symbol_strength <= 0:
            return base_size, "normal"
        if self.symbol_strength == 1:
            return base_size + 1, "bold"
        return base_size + 2, "bold"

    def _compute_uniform_student_name_font_size(self) -> int:
        base_size = max(8, int(self.cell_size * 0.12))
        min_size = 5
        max_text_width = int(self.cell_size * 0.88)

        labels = [
            (desk.student_name or "").strip()
            for desk in self.current_plan.desks
            if desk.desk_type == "student" and (desk.student_name or "").strip()
        ]
        if not labels:
            return base_size

        size = base_size
        while size > min_size:
            font = tkfont.Font(family="Segoe UI", size=size, weight="bold")
            if all(font.measure(label) <= max_text_width for label in labels):
                return size
            size -= 1

        return min_size

    def _symbol_glyph(self, symbol_name: str) -> str:
        symbol = self._symbol_by_meaning.get(symbol_name)
        if symbol is None:
            return "•"
        return symbol.glyph

    def _iter_symbol_counts(self, symbols: dict[str, int]) -> list[tuple[str, int]]:
        entries: list[tuple[str, int]] = []

        for symbol_name in self.symbol_catalog:
            count = int(symbols.get(symbol_name, 0))
            if count < 1:
                continue
            entries.append((symbol_name, min(3, count)))

        for symbol_name, raw_count in sorted(symbols.items()):
            if symbol_name in self.symbol_catalog:
                continue
            count = int(raw_count)
            if count < 1:
                continue
            entries.append((symbol_name, min(3, count)))

        return entries

    def _symbol_grid_lines(self, symbols: dict[str, int]) -> list[str]:
        """Render only symbols in the tile, max 6 glyphs per line, symbol groups stay intact."""
        entries = self._iter_symbol_counts(symbols)
        if not entries:
            return []

        lines: list[str] = []
        line_tokens: list[str] = []
        used_slots = 0

        for symbol_name, count in entries:
            token = self._symbol_glyph(symbol_name) * count
            token_slots = len(token)
            if line_tokens and used_slots + token_slots > 6:
                lines.append(" ".join(line_tokens))
                line_tokens = [token]
                used_slots = token_slots
            else:
                line_tokens.append(token)
                used_slots += token_slots

        if line_tokens:
            lines.append(" ".join(line_tokens))

        return lines

    def _symbol_legend_lines(self, symbols: dict[str, int]) -> list[str]:
        if not symbols:
            return []

        lines: list[str] = []
        for symbol_name, count in self._iter_symbol_counts(symbols):
            glyph = self._symbol_glyph(symbol_name)
            definition = self._symbol_by_meaning.get(symbol_name)
            if definition is None:
                legend_text = symbol_name
            else:
                legend_text = definition.legend_for_count(count)
            lines.append(f"{glyph * count} {legend_text}".strip())

        return lines

    def _ordered_color_markers(self, color_markers: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        configured_order = [color_key for _key, color_key, _label, _hex_color in self.color_palette]

        for color_key in configured_order:
            if color_key in color_markers and color_key not in seen:
                ordered.append(color_key)
                seen.add(color_key)

        for color_key in color_markers:
            if color_key not in seen:
                ordered.append(color_key)
                seen.add(color_key)

        return ordered

    def _color_legend_lines(self, plan: SeatingPlan, desk_color_markers: list[str]) -> list[str]:
        lines: list[str] = []
        for color_key in self._ordered_color_markers(desk_color_markers):
            meaning = plan.color_meanings.get(color_key, "")
            if not meaning:
                continue
            label, _hex_color = self._color_by_key.get(color_key, (color_key, "#999999"))
            lines.append(f"● {label}: {meaning}")
        return lines

    def _details_button_columns(self) -> int:
        if self.details_overlay_position in {"left", "right"}:
            return 2
        return 5

    def _details_legend_wraplength(self) -> int:
        if self.details_overlay_position in {"left", "right"}:
            return 500
        return 980

    def move_selection(self, dx: int, dy: int) -> None:
        if not self.editor_view.winfo_ismapped():
            return

        x, y = self.selection.active_cell()
        self._set_selection_single(x + dx, y + dy)
        self.interaction_mode = GRID_SELECTED
        self._follow_selection_viewport(*self.selection.active_cell())
        self.redraw_grid()
        self._refresh_details_panel()

    def expand_selection(self, dx: int, dy: int) -> None:
        if not self.editor_view.winfo_ismapped():
            return

        x, y = self.selection.active_cell()
        self._set_selection_focus(x + dx, y + dy)
        self.interaction_mode = GRID_SELECTED
        self._follow_selection_viewport(*self.selection.active_cell())
        self.redraw_grid()
        self._refresh_details_panel()

    def _follow_selection_viewport(self, x: int, y: int) -> None:
        buffer_cells = self.viewport_follow_buffer
        if buffer_cells <= 0:
            self.center_on_cell(x, y)
            return

        self.update_idletasks()
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        left_cell = int(self.canvas.canvasx(0) // self.cell_size)
        right_cell = int(self.canvas.canvasx(width - 1) // self.cell_size)
        top_cell = int(self.canvas.canvasy(0) // self.cell_size)
        bottom_cell = int(self.canvas.canvasy(height - 1) // self.cell_size)

        if right_cell - left_cell < buffer_cells * 2 or bottom_cell - top_cell < buffer_cells * 2:
            self.center_on_cell(x, y)
            return

        safe_min_x = left_cell + buffer_cells
        safe_max_x = right_cell - buffer_cells
        safe_min_y = top_cell + buffer_cells
        safe_max_y = bottom_cell - buffer_cells

        if x < safe_min_x or x > safe_max_x or y < safe_min_y or y > safe_max_y:
            self.center_on_cell(x, y)

    def handle_escape(self) -> None:
        self._sync_popup_sessions_from_windows()
        has_popup = self._popup_registry.has_active_popup()
        has_inline_editor = self._is_name_entry_focused() or self.interaction_mode == NAME_EDITING
        has_parent_state = self.editor_view.winfo_ismapped()

        action = self._hsm_contract.resolve_escape_action(
            has_popup=has_popup,
            has_inline_editor=has_inline_editor,
            has_parent_state=has_parent_state,
        )

        if action == ESCAPE_CLOSE_POPUP:
            active_popup = self._popup_registry.active_popup()
            if active_popup is not None:
                popup_id = active_popup.popup_id
                for child in self.winfo_children():
                    if not isinstance(child, tk.Toplevel):
                        continue
                    if str(child) != popup_id:
                        continue
                    self._destroy_tracked_dialog(child)
                    return
                self._popup_registry.close_popup(popup_id)
                self._tracked_popup_ids.discard(popup_id)
                return

        if action == ESCAPE_EXIT_INLINE_EDITOR:
            self.exit_name_edit_mode()
            return

        if action == ESCAPE_POP_PARENT:
            self.show_plan_list_view()
            return

        self._ensure_list_selection(preferred_path=self.current_plan_path)
        self.plan_listbox.focus_set()
        self.interaction_mode = LIST_ACTIVE

    def enter_name_edit_mode(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()
            self.redraw_grid()
            self._refresh_details_panel()

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if desk and desk.desk_type == "teacher":
            self.status_var.set("Lehrertisch ist nicht editierbar")
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            return

        if not desk:
            next_plan = create_student_desk(self.current_plan, x, y)
            self._record_and_save(next_plan, "desk.create", "Schuelertisch gesetzt")
            self.redraw_grid()

        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            return

        self._refresh_details_panel()
        self.name_entry.state(["!disabled"])
        if self.name_entry.instate(["!disabled"]):
            self.interaction_mode = NAME_EDITING
            self.name_entry.focus_set()
            self.name_entry.selection_clear()
            self.name_entry.icursor(tk.END)

    def exit_name_edit_mode(self) -> None:
        if self.editor_view.winfo_ismapped():
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            self._refresh_details_panel()

    def confirm_selected_cell(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self._collapse_selection_to_anchor()

        x, y = self.selected_cell
        next_plan = create_student_desk(self.current_plan, x, y)
        self._record_and_save(next_plan, "desk.create", "Schuelertisch gesetzt")
        self.redraw_grid()
        self._refresh_details_panel()

    def delete_selected_desk(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        targets = self.selection.cells()
        has_teacher = any(
            (desk := self.current_plan.desk_at(x, y)) is not None and desk.desk_type == "teacher"
            for x, y in targets
        )
        if has_teacher:
            self.status_var.set("Lehrertisch kann nicht geloescht werden")

        next_plan = self.current_plan
        for x, y in targets:
            next_plan = delete_desk(next_plan, x, y)

        self.interaction_mode = GRID_SELECTED
        self._record_and_save(next_plan, "desk.delete", "Platz geloescht")
        self._set_selection_single(*self.selection.anchor_cell())
        self.redraw_grid()
        self._refresh_details_panel()

    def set_selected_as_teacher_desk(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        x, y = self.selected_cell
        moved_plan = set_teacher_desk(self.current_plan, x, y)
        out_of_bounds = self._count_out_of_bounds_desks(moved_plan)
        if out_of_bounds > 0:
            proceed = messagebox.askyesno(
                "Warnung",
                f"Nach dem Verschieben des Lehrertischs waeren {out_of_bounds} Schuelertische ausserhalb des aktuellen Canvas-Bereichs (+/-{self.canvas_radius}) und damit unsichtbar. Trotzdem fortfahren?",
                parent=self,
            )
            if not proceed:
                return

        self.current_plan = moved_plan
        self.history.record(self.current_plan, "teacher.move")
        self.interaction_mode = GRID_SELECTED
        self._save_current_plan("Lehrertisch neu gesetzt")
        self._set_selection_single(0, 0)
        self.center_on_cell(0, 0)
        self.redraw_grid()
        self._refresh_details_panel()

    def _refresh_details_panel(self) -> None:
        self._color_marker_buttons = []
        for child in self.symbols_frame.winfo_children():
            child.destroy()
        for child in self.symbol_legend_frame.winfo_children():
            child.destroy()
        for child in self.colors_frame.winfo_children():
            child.destroy()
        for child in self.color_legend_frame.winfo_children():
            child.destroy()

        if not self.current_plan:
            self._set_details_panel_visible(False)
            self._selected_marker_var.set("")
            self._name_var.set("")
            self.name_entry.configure(state="disabled")
            self._refresh_tablegroup_overlay()
            return

        x, y = self.selection.active_cell()
        desk = self.current_plan.desk_at(x, y)
        min_x, min_y, max_x, max_y = self.selection.bounds()
        if self.selection.is_single():
            self._selected_marker_var.set(f"Markierung: ({x}, {y})")
        else:
            count = (max_x - min_x + 1) * (max_y - min_y + 1)
            self._selected_marker_var.set(f"Bereich: ({min_x}, {min_y}) bis ({max_x}, {max_y}) | {count} Zellen")

        is_student_single_selection = bool(self.selection.is_single() and desk and desk.desk_type == "student")
        self._set_details_panel_visible(is_student_single_selection)

        if not is_student_single_selection:
            self._name_var.set("")
            self.name_entry.configure(state="disabled")
            if self.interaction_mode == NAME_EDITING:
                self.interaction_mode = GRID_SELECTED
                self.canvas.focus_set()
            self._refresh_tablegroup_overlay()
            return

        self._name_var.set(desk.student_name)
        self.name_entry.configure(state="normal")

        ttk.Label(self.symbols_frame, text="Symbole").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        symbol_cols = self._details_button_columns()
        for symbol in self.diagnostic_symbol_catalog:
            count = int(desk.symbols.get(symbol, 0))
            icon = self._symbol_glyph(symbol)
            shortcut = self._symbol_by_meaning.get(symbol).shortcut if self._symbol_by_meaning.get(symbol) else None
            shortcut_suffix = f" [{shortcut.upper()}]" if shortcut else ""
            caption = f"{icon} {symbol}{shortcut_suffix}" if count == 0 else f"{icon} {symbol} x{count}{shortcut_suffix}"
            idx = self.diagnostic_symbol_catalog.index(symbol)
            row = 1 + (idx // symbol_cols)
            col = idx % symbol_cols
            button = ttk.Button(
                self.symbols_frame,
                text=caption,
                command=lambda s=symbol: self._toggle_selected_symbol(s),
            )
            button.grid(row=row, column=col, sticky="ew", padx=(0, 6), pady=(0, 4))

        for col in range(symbol_cols):
            self.symbols_frame.columnconfigure(col, weight=1)

        active_lines = self._symbol_legend_lines(desk.symbols)
        if active_lines:
            for line in active_lines:
                ttk.Label(self.symbol_legend_frame, text=line, wraplength=self._details_legend_wraplength(), justify="left").pack(anchor="w")

        ttk.Label(self.colors_frame, text="Farbpunkte").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 4))
        color_cols = self._details_button_columns()
        for key, color_key, label, hex_color in self.color_palette:
            active = color_key in desk.color_markers
            caption = f"{key}:{label}" if not active else f"{key}:{label}*"
            idx = int(key) - 1
            row = 1 + (idx // color_cols)
            col = idx % color_cols
            button = tk.Button(
                self.colors_frame,
                text=caption,
                command=lambda ck=color_key: self._toggle_selected_color(ck),
                fg=hex_color,
                relief="sunken" if active else "raised",
                padx=6,
                pady=2,
            )
            button.grid(row=row, column=col, sticky="ew", padx=(0, 6), pady=(0, 4))
            self._color_marker_buttons.append(button)

        for col in range(color_cols):
            self.colors_frame.columnconfigure(col, weight=1)

        self._apply_color_button_theme()

        for line in self._color_legend_lines(self.current_plan, desk.color_markers):
            ttk.Label(self.color_legend_frame, text=line, wraplength=self._details_legend_wraplength(), justify="left").pack(anchor="w")

        self._refresh_tablegroup_overlay()

    def _set_details_panel_visible(self, visible: bool) -> None:
        fill_mode = "both" if self.details_overlay_position in {"left", "right"} else "x"
        if visible and not self._details_panel_visible:
            self.details_frame.pack(fill=fill_mode, padx=12, pady=(4, 12))
            self._details_panel_visible = True
            return
        if not visible and self._details_panel_visible:
            self.details_frame.pack_forget()
            self._details_panel_visible = False

    def _on_name_changed(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            return

        next_plan = update_student_name(self.current_plan, x, y, self._name_var.get())
        self._record_and_save(next_plan, "name.edit", "Name geaendert")
        self.redraw_grid()

    def _toggle_selected_symbol(self, symbol: str) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        if not self.selection.is_single():
            self.status_var.set("Symbole nur bei Einzelauswahl")
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or not desk.is_named_student():
            self.status_var.set("Symbol nur für Schülertische")
            return
        if symbol not in self.diagnostic_symbol_catalog:
            self.status_var.set("Dieses Symbol ist nur fuer die Dokumentation verfuegbar")
            return

        next_plan = toggle_symbol(self.current_plan, x, y, symbol)
        updated_desk = next_plan.desk_at(x, y)
        next_strength = 0
        if updated_desk is not None and updated_desk.desk_type == "student":
            next_strength = int(updated_desk.symbols.get(symbol, 0))
        next_plan = set_documentation_symbol(next_plan, x, y, symbol, next_strength, self._today_doc_date())
        self._record_and_save(next_plan, "symbol.toggle", f"Symbol '{symbol}' aktualisiert")
        self.redraw_grid()
        self._refresh_details_panel()

    def _toggle_documentation_symbol(self, symbol: str) -> None:
        if not self.current_plan or not self._doc_student_coords or not self._doc_dates:
            return

        student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        date_index = max(0, min(self._doc_selected_date_index, len(self._doc_dates) - 1))
        x, y = self._doc_student_coords[student_index]
        date_key = self._doc_dates[date_index]

        desk = self.current_plan.desk_at(x, y)
        if not desk or not desk.is_named_student():
            return

        entry = desk.documentation_entries.get(date_key)
        current_count = 0 if entry is None else int(entry.symbols.get(symbol, 0))
        next_count = (current_count + 1) % 4
        updated = set_documentation_symbol(self.current_plan, x, y, symbol, next_count, date_key)
        self._record_and_save(updated, "documentation.symbol.toggle", f"Dokumentation '{symbol}' aktualisiert")
        self._refresh_documentation_table()

    def add_symbol_to_selected_desk_dialog(self) -> None:
        if not self.current_plan:
            return

        if not self.selection.is_single():
            self.status_var.set("Symbole nur bei Einzelauswahl")
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            self.status_var.set("Symbol nur für Schülertische")
            return

        dialog = self._create_overlay_dialog("Symbol hinzufügen", "350x360")

        ttk.Label(dialog, text="Symbol auswählen").pack(anchor="w", padx=12, pady=(12, 6))

        listbox = tk.Listbox(dialog, selectmode="browse", exportselection=False, font=("Segoe UI", 11))
        listbox.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        for symbol in self.diagnostic_symbol_catalog:
            listbox.insert(tk.END, symbol)
        if self.diagnostic_symbol_catalog:
            listbox.selection_set(0)
        self._focus_overlay_widget(dialog, listbox)

        def apply_choice() -> None:
            selected = listbox.curselection()
            if not selected:
                return
            symbol = self.diagnostic_symbol_catalog[int(selected[0])]
            self._toggle_selected_symbol(symbol)
            dialog.destroy()

        button_row = ttk.Frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(button_row, text="Übernehmen", command=apply_choice).pack(side="right")

    def undo_last_change(self) -> None:
        if self.interaction_mode == LIST_ACTIVE and self._undo_plan_list_action():
            return
        if not self.current_plan or not self.current_plan_path:
            if not self._undo_plan_list_action():
                self.status_var.set("Nichts zum Rueckgaengigmachen")
            return
        restored = self.history.undo(steps=1)
        if restored is None:
            if not self._undo_plan_list_action():
                self.status_var.set("Nichts zum Rueckgaengigmachen")
            return
        self.current_plan = restored
        self._save_current_plan("Rueckgaengig")
        self.redraw_grid()
        self._refresh_details_panel()

    def undo_last_five_changes(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return
        restored = self.history.undo(steps=5)
        if restored is None:
            self.status_var.set("Nichts zum Rueckgaengigmachen")
            return
        self.current_plan = restored
        self._save_current_plan("Letzte 5 Aenderungen rueckgaengig")
        self.redraw_grid()
        self._refresh_details_panel()

    def redo_last_change(self) -> None:
        if self.interaction_mode == LIST_ACTIVE and self._redo_plan_list_action():
            return
        if not self.current_plan or not self.current_plan_path:
            if not self._redo_plan_list_action():
                self.status_var.set("Nichts zum Wiederholen")
            return
        restored = self.history.redo(steps=1)
        if restored is None:
            if not self._redo_plan_list_action():
                self.status_var.set("Nichts zum Wiederholen")
            return
        self.current_plan = restored
        self._save_current_plan("Wiederholt")
        self.redraw_grid()
        self._refresh_details_panel()

    def copy_selection(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return
        if self._is_name_entry_focused():
            return
        copied = self._desk_clipboard.copy_from_plan(self.current_plan, self.selection.cells())
        self.status_var.set(f"Kopiert: {copied} Schuelertische")

    def cut_selection(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return
        if self._is_name_entry_focused():
            return
        next_plan, copied, removed = self._desk_clipboard.cut_from_plan(self.current_plan, self.selection.cells())
        self._record_and_save(next_plan, "selection.cut", f"Ausgeschnitten: {removed} Schuelertische")
        self.status_var.set(f"Ausgeschnitten: {removed} Schuelertische (Kopiert: {copied})")
        self.redraw_grid()
        self._refresh_details_panel()

    def paste_selection(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return
        if self._is_name_entry_focused():
            return
        if not self._desk_clipboard.has_content():
            self.status_var.set("Clipboard ist leer")
            return
        target_x, target_y = self.selection.active_cell()
        next_plan, pasted, teacher_conflict = self._desk_clipboard.paste_into_plan(
            self.current_plan,
            target_x,
            target_y,
            self._grid_min(),
            self._grid_max(),
        )
        normalize_tablegroups_in_place(next_plan)
        self._record_and_save(next_plan, "selection.paste", f"Eingefuegt: {pasted} Schuelertische")
        if teacher_conflict:
            messagebox.showwarning(
                "Lehrertisch geschuetzt",
                "Einzufuegende Daten haetten den Lehrertisch ueberschrieben. Der Lehrertisch blieb unveraendert.",
                parent=self,
            )
        self.redraw_grid()
        self._refresh_details_panel()

    def export_plan_pdf_dialog(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geöffnet")
            return

        dialog = self._create_overlay_dialog("PDF exportieren", "420x190")

        mode_var = tk.StringVar(value="teacher_bottom")
        ttk.Label(dialog, text="Ansicht wählen").pack(anchor="w", padx=12, pady=(12, 6))
        first_mode_button = ttk.Radiobutton(
            dialog,
            text="Lehrertisch unten (Standard)",
            value="teacher_bottom",
            variable=mode_var,
        )
        first_mode_button.pack(anchor="w", padx=12)
        ttk.Radiobutton(
            dialog,
            text="Lehrertisch oben (180° Perspektive)",
            value="teacher_top",
            variable=mode_var,
        ).pack(anchor="w", padx=12, pady=(4, 0))
        self._focus_overlay_widget(dialog, first_mode_button)

        def do_export() -> None:
            output = filedialog.asksaveasfilename(
                parent=dialog,
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile=f"{self.current_plan.name}.pdf",
            )
            if not output:
                return

            try:
                self.pdf_exporter.export_plan(self.current_plan, Path(output), mode_var.get())
                self.status_var.set(f"PDF exportiert: {Path(output).name}")
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("PDF-Export fehlgeschlagen", str(exc), parent=dialog)

        button_row = ttk.Frame(dialog)
        button_row.pack(fill="x", padx=12, pady=(12, 12))
        ttk.Button(button_row, text="Abbrechen", command=dialog.destroy).pack(side="right")
        ttk.Button(button_row, text="Exportieren", command=do_export).pack(side="right", padx=(0, 8))

    def _create_overlay_dialog(self, title: str, geometry: str) -> tk.Toplevel:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry(geometry)
        dialog.transient(self)
        self._track_popup_window(dialog)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: self._destroy_tracked_dialog(dialog))
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._destroy_tracked_dialog(dialog))
        self._focus_overlay_widget(dialog, dialog)
        return dialog

    def _destroy_tracked_dialog(self, dialog: tk.Toplevel) -> None:
        popup_id = str(dialog)
        self._popup_registry.close_popup(popup_id)
        self._tracked_popup_ids.discard(popup_id)
        dialog.destroy()

    def _focus_overlay_widget(self, dialog: tk.Toplevel, widget: tk.Widget) -> None:
        def _apply_focus() -> None:
            if not dialog.winfo_exists() or not widget.winfo_exists():
                return
            dialog.focus_force()
            widget.focus_set()

        dialog.after(1, _apply_focus)

    def _save_current_plan(self, status: str) -> None:
        if not self.current_plan or not self.current_plan_path:
            return
        try:
            self.plan_repository.save_plan(self.current_plan, self.current_plan_path)
            self.status_var.set(f"Gespeichert: {status}")
            self.refresh_plan_list()
        except Exception as exc:
            self.status_var.set(f"Speichern fehlgeschlagen: {exc}")

    def _periodic_backup_tick(self) -> None:
        try:
            if self.current_plan and self.current_plan_path:
                self.plan_repository.backup_plan_snapshot(self.current_plan, self.current_plan_path)
        except Exception:
            pass
        finally:
            if self.winfo_exists():
                self.after(DEFAULT_PERIODIC_BACKUP_INTERVAL_MS, self._periodic_backup_tick)

