from __future__ import annotations

import tkinter as tk
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

from app.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from app.adapters.gui.ui_intents import UiIntent
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
    create_student_desk,
    delete_desk,
    ensure_documentation_date,
    is_color_used,
    rename_documentation_date,
    set_color_meaning,
    set_documentation_symbol,
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
    ):
        super().__init__()
        configure_windows_process_identity()
        self.title("Kartograph")
        self.geometry("1320x860")
        self.minsize(1000, 680)
        apply_window_icon(self)

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
        self.details_overlay_position = self._normalize_details_overlay_position(
            self._settings.get("details_overlay_position")
        )
        self.tablegroup_overlay_position = self._normalize_tablegroup_overlay_position(
            self._settings.get("tablegroup_overlay_position")
        )

        self.ui_intent_controller = MainWindowUiIntentController(self)

        self._name_var = tk.StringVar(value="")
        self._selected_marker_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Bereit")
        self._tablegroup_overlay: tk.Toplevel | None = None
        self._tg_number_var: tk.StringVar | None = None
        self._tg_shift_x_var: tk.StringVar | None = None
        self._tg_shift_y_var: tk.StringVar | None = None
        self._tg_rotation_var: tk.StringVar | None = None
        self._tg_status_var: tk.StringVar | None = None
        self._tg_last_changed_field: str = "shift_x"
        self._color_marker_buttons: list[tk.Button] = []
        self._editor_surface: str = "grid"
        self._documentation_mode: str = "column"
        self._doc_selected_student_index: int = 0
        self._doc_selected_date_index: int = 0
        self._doc_student_coords: list[tuple[int, int]] = []
        self._doc_dates: list[str] = []
        self._doc_tree_iid_by_student_index: dict[int, str] = {}
        self._doc_date_column_ids: list[str] = []

        self.color_palette = COLOR_MARKER_PALETTE
        self._color_by_key = {color_key: (label, hex_color) for _key, color_key, label, hex_color in self.color_palette}

        self.symbol_definitions, warning = self._load_symbols()
        self.symbol_catalog = [item.meaning for item in self.symbol_definitions]
        self._symbol_by_meaning = {item.meaning: item for item in self.symbol_definitions}
        self._shortcut_to_symbol = self._build_symbol_shortcut_map(self.symbol_definitions)
        self.pdf_exporter = PdfSeatingPlanExporter(self.symbol_definitions)
        if warning:
            self.status_var.set(warning)

        self._build_menu_bar()
        self._build_layout()
        self._bind_shortcuts()
        self.bind("<Configure>", lambda _event: self._position_tablegroup_overlay(), add="+")

        self.apply_theme()
        self.refresh_plan_list()
        self.show_plan_list_view()

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

        self.docs_mode_var = tk.StringVar(value="Modus: Spalten")
        ttk.Button(
            self.docs_toolbar,
            text="Zur Rasteransicht",
            command=lambda: self._handle_intent(UiIntent.VIEW_GRID),
        ).pack(side="left")
        ttk.Button(
            self.docs_toolbar,
            text="Modus wechseln (Strg+M)",
            command=lambda: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION_MODE),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Datum umbenennen",
            command=lambda: self._handle_intent(UiIntent.RENAME_DOCUMENTATION_DATE),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            self.docs_toolbar,
            text="Notenspalte hinzufügen",
            command=lambda: self._handle_intent(UiIntent.ADD_GRADE_COLUMN),
        ).pack(side="left", padx=(8, 0))
        ttk.Label(self.docs_toolbar, textvariable=self.docs_mode_var).pack(side="right")

        self.docs_table_container = ttk.Frame(self.docs_container)
        self.docs_table_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.docs_tree = ttk.Treeview(self.docs_table_container, show="tree headings")
        self.docs_tree.pack(side="left", fill="both", expand=True)
        self.docs_tree.column("#0", width=220, anchor="w", stretch=False)
        self.docs_tree.heading("#0", text="Schüler:in")

        self.docs_y_scroll = ttk.Scrollbar(self.docs_table_container, orient="vertical", command=self.docs_tree.yview)
        self.docs_y_scroll.pack(side="right", fill="y")
        self.docs_x_scroll = ttk.Scrollbar(self.docs_container, orient="horizontal", command=self.docs_tree.xview)
        self.docs_x_scroll.pack(fill="x", padx=12, pady=(0, 12))
        self.docs_tree.configure(yscrollcommand=self.docs_y_scroll.set, xscrollcommand=self.docs_x_scroll.set)

        self.docs_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_docs_tree_select())
        self.docs_tree.bind("<Button-1>", self._on_docs_tree_click)

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<Configure>", lambda _event: self.redraw_grid())
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mouse_wheel)

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _event: self._handle_intent(UiIntent.NEW_PLAN))
        self.bind("<Control-d>", self._on_duplicate_shortcut)
        self.bind("<F2>", self._on_rename_shortcut)
        self.bind("<Control-e>", lambda _event: self._handle_intent(UiIntent.EXPORT_PDF))
        self.bind("<Control-comma>", lambda _event: self._handle_intent(UiIntent.OPEN_SETTINGS))
        self.bind("<Control-,>", lambda _event: self._handle_intent(UiIntent.OPEN_SETTINGS))
        self.bind("<Control-0>", lambda _event: self._handle_intent(UiIntent.RESET_VIEW))
        self.bind("<Control-Return>", lambda _event: self._handle_intent(UiIntent.SET_TEACHER_DESK))
        self.bind("<Control-KP_Enter>", lambda _event: self._handle_intent(UiIntent.SET_TEACHER_DESK))
        self.bind("<Control-plus>", lambda _event: self._handle_intent(UiIntent.ZOOM_IN))
        self.bind("<Control-equal>", lambda _event: self._handle_intent(UiIntent.ZOOM_IN))
        self.bind("<Control-KP_Add>", lambda _event: self._handle_intent(UiIntent.ZOOM_IN))
        self.bind("<Control-minus>", lambda _event: self._handle_intent(UiIntent.ZOOM_OUT))
        self.bind("<Control-KP_Subtract>", lambda _event: self._handle_intent(UiIntent.ZOOM_OUT))
        self.bind("<Control-z>", lambda _event: self._handle_intent(UiIntent.UNDO))
        self.bind("<Control-y>", lambda _event: self._handle_intent(UiIntent.REDO))
        self.bind("<Control-t>", lambda _event: self._handle_intent(UiIntent.OPEN_TABLEGROUP_SETTINGS))
        self.bind("<Control-Shift-D>", lambda _event: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION))
        self.bind("<Control-Shift-d>", lambda _event: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION))
        self.bind("<Control-m>", lambda _event: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION_MODE))
        self.bind("<Control-x>", lambda _event: self._handle_intent(UiIntent.CUT))
        self.bind("<Control-c>", lambda _event: self._handle_intent(UiIntent.COPY))
        self.bind("<Control-v>", lambda _event: self._handle_intent(UiIntent.PASTE))
        self.bind("<Delete>", self._on_delete_key)
        self.bind("<Escape>", lambda _event: self._handle_intent(UiIntent.ESCAPE))
        self.bind("<Return>", self._on_return_key)
        self.bind("<KP_Enter>", self._on_return_key)

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
        return self.ui_intent_controller.handle_intent(intent)

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
            return "break"
        return self._handle_intent(UiIntent.DELETE_DESK)

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
        self.current_plan = plan
        self.history.reset(self.current_plan)
        if hasattr(self, "docs_tree"):
            self._refresh_documentation_table()
        return plan

    def _on_return_key(self, _event) -> str | None:
        if self._is_name_entry_focused():
            return "break"
        if self.editor_view.winfo_ismapped():
            if self._editor_surface == "docs":
                self._move_doc_selection_on_enter()
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
        if self._is_name_entry_focused():
            return None
        if self._is_tablegroup_overlay_focused():
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

        self._toggle_selected_symbol(symbol_name)
        return "break"

    def _on_color_shortcut(self, event, color_key: str) -> str | None:
        if self._is_name_entry_focused():
            return None
        if self._is_tablegroup_overlay_focused():
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
        self.grid_stack.pack_forget()
        self.details_container.pack_forget()
        self._apply_details_overlay_position()
        self.interaction_mode = GRID_SELECTED
        self.canvas.focus_set()

    def show_documentation_surface(self) -> None:
        if not self.current_plan:
            return
        self._editor_surface = "docs"
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

    def toggle_documentation_mode(self) -> None:
        self._documentation_mode = "row" if self._documentation_mode == "column" else "column"
        if self._documentation_mode == "column":
            self.docs_mode_var.set("Modus: Spalten")
        else:
            self.docs_mode_var.set("Modus: Zeilen")

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
            if idx == self._doc_selected_date_index:
                title = f"> {date_key}"
            self.docs_tree.heading(col_id, text=title)

    def _refresh_documentation_table(self) -> None:
        if not self.current_plan:
            return

        self._doc_student_coords = [
            (desk.x, desk.y)
            for desk in sorted(self.current_plan.desks, key=lambda item: (item.y, item.x))
            if desk.desk_type == "student"
        ]

        all_dates = sorted(set(self.current_plan.documentation_dates) | {self._today_doc_date()})
        self._doc_dates = all_dates
        self._doc_date_column_ids = [f"date_{index}" for index in range(len(all_dates))]

        fixed_columns: list[str] = ["summary"]
        fixed_columns.extend([f"grade_{item.column_id}" for item in self.current_plan.grade_columns])
        fixed_columns.append("overall")
        columns = [*self._doc_date_column_ids, *fixed_columns]
        self.docs_tree.configure(columns=columns)

        for idx, date_key in enumerate(all_dates):
            self.docs_tree.column(self._doc_date_column_ids[idx], width=120, anchor="center", stretch=False)
            self.docs_tree.heading(self._doc_date_column_ids[idx], text=date_key)

        self.docs_tree.column("summary", width=180, anchor="w", stretch=False)
        self.docs_tree.heading("summary", text="Zusammenfassung")

        for grade in self.current_plan.grade_columns:
            col_id = f"grade_{grade.column_id}"
            self.docs_tree.column(col_id, width=120, anchor="center", stretch=False)
            self.docs_tree.heading(col_id, text=grade.title)

        self.docs_tree.column("overall", width=120, anchor="center", stretch=False)
        self.docs_tree.heading("overall", text="Gesamtnote")

        for row_id in self.docs_tree.get_children():
            self.docs_tree.delete(row_id)
        self._doc_tree_iid_by_student_index = {}

        for student_idx, (x, y) in enumerate(self._doc_student_coords):
            desk = self.current_plan.desk_at(x, y)
            if desk is None:
                continue
            values: list[str] = []
            for date_key in all_dates:
                entry = desk.documentation_entries.get(date_key)
                values.append(self._documentation_cell_text(entry.symbols) if entry else "")
            values.append(self._documentation_summary_text(x, y))
            for grade in self.current_plan.grade_columns:
                values.append(self._latest_grade_value_for_column(x, y, grade.column_id))
            values.append(compute_grade_display_for_student(self.current_plan, x, y))

            iid = self.docs_tree.insert("", "end", text=desk.student_name or f"({x},{y})", values=values)
            self._doc_tree_iid_by_student_index[student_idx] = iid

        if self._doc_student_coords:
            self._doc_selected_student_index = max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
            self._doc_selected_date_index = max(0, min(self._doc_selected_date_index, max(0, len(all_dates) - 1)))
            selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
            if selected_iid is not None:
                self.docs_tree.selection_set(selected_iid)
                self.docs_tree.focus(selected_iid)
                self.docs_tree.see(selected_iid)
        else:
            self._doc_selected_student_index = 0
            self._doc_selected_date_index = 0

        self._apply_doc_column_heading_highlight()

    def _on_docs_tree_click(self, event) -> None:
        row_id = self.docs_tree.identify_row(event.y)
        if row_id:
            self.docs_tree.selection_set(row_id)
            self.docs_tree.focus(row_id)
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
        selected = self.docs_tree.selection()
        if not selected:
            return
        row_id = selected[0]
        for student_idx, iid in self._doc_tree_iid_by_student_index.items():
            if iid == row_id:
                self._doc_selected_student_index = student_idx
                break

    def _move_doc_selection_on_enter(self) -> None:
        if not self._doc_student_coords or not self._doc_dates:
            return
        if self._documentation_mode == "column":
            self._doc_selected_student_index = (self._doc_selected_student_index + 1) % len(self._doc_student_coords)
        else:
            self._doc_selected_date_index = (self._doc_selected_date_index + 1) % len(self._doc_dates)
            self._apply_doc_column_heading_highlight()

        selected_iid = self._doc_tree_iid_by_student_index.get(self._doc_selected_student_index)
        if selected_iid is not None:
            self.docs_tree.selection_set(selected_iid)
            self.docs_tree.focus(selected_iid)
            self.docs_tree.see(selected_iid)

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
        try:
            plan = self.plan_repository.load_plan(plan_path)
        except Exception as exc:
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
        self._apply_loaded_plan(plan)
        self.plan_name_var.set(f"Plan: {plan.name}")
        self._set_selection_single(0, 0)

        self.show_editor_view()
        self.center_on_cell(0, 0)
        self.redraw_grid()
        self._refresh_details_panel()
        self._refresh_documentation_table()

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
            symbol_lines = self._symbol_grid_lines(desk.symbols)
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
        self.center_on_cell(*self.selection.active_cell())
        self.redraw_grid()
        self._refresh_details_panel()

    def expand_selection(self, dx: int, dy: int) -> None:
        if not self.editor_view.winfo_ismapped():
            return

        x, y = self.selection.active_cell()
        self._set_selection_focus(x + dx, y + dy)
        self.interaction_mode = GRID_SELECTED
        self.center_on_cell(*self.selection.active_cell())
        self.redraw_grid()
        self._refresh_details_panel()

    def handle_escape(self) -> None:
        if self._is_name_entry_focused():
            self.exit_name_edit_mode()
            return

        if self.interaction_mode == NAME_EDITING:
            self.exit_name_edit_mode()
            return

        if self.editor_view.winfo_ismapped():
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
        for symbol in self.symbol_catalog:
            count = int(desk.symbols.get(symbol, 0))
            icon = self._symbol_glyph(symbol)
            shortcut = self._symbol_by_meaning.get(symbol).shortcut if self._symbol_by_meaning.get(symbol) else None
            shortcut_suffix = f" [{shortcut.upper()}]" if shortcut else ""
            caption = f"{icon} {symbol}{shortcut_suffix}" if count == 0 else f"{icon} {symbol} x{count}{shortcut_suffix}"
            idx = self.symbol_catalog.index(symbol)
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
        if not desk or desk.desk_type != "student":
            self.status_var.set("Symbol nur für Schülertische")
            return

        next_plan = toggle_symbol(self.current_plan, x, y, symbol)
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
        if not desk or desk.desk_type != "student":
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
        for symbol in self.symbol_catalog:
            listbox.insert(tk.END, symbol)
        if self.symbol_catalog:
            listbox.selection_set(0)
        self._focus_overlay_widget(dialog, listbox)

        def apply_choice() -> None:
            selected = listbox.curselection()
            if not selected:
                return
            symbol = self.symbol_catalog[int(selected[0])]
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
        dialog.grab_set()
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self._focus_overlay_widget(dialog, dialog)
        return dialog

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
