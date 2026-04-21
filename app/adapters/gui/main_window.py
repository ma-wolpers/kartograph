from __future__ import annotations

import tkinter as tk
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

from app.adapters.gui.ui_intent_controller import MainWindowUiIntentController
from app.adapters.gui.ui_intents import UiIntent
from app.adapters.gui.ui_theme import THEMES, normalize_theme_key, theme_names
from app.core.domain.models import SeatingPlan
from app.core.usecases.plan_usecases import (
    create_student_desk,
    delete_desk,
    set_teacher_desk,
    toggle_symbol,
    update_student_name,
)
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter
from app.infrastructure.symbol_config_loader import SymbolDefinition, load_symbol_definitions

SCROLL_REGION = 220000
LIST_ACTIVE = "list_active"
GRID_SELECTED = "grid_selected"
NAME_EDITING = "name_editing"

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
        self.cell_size = 92
        self._plan_index: list[tuple[Path, SeatingPlan]] = []
        self.interaction_mode = LIST_ACTIVE

        self._settings = self.settings_repository.load_settings()
        self.plans_dir = Path(self._settings.get("plans_dir") or self.default_plans_dir)
        self.theme_key = normalize_theme_key(self._settings.get("theme"))

        self.ui_intent_controller = MainWindowUiIntentController(self)

        self._name_var = tk.StringVar(value="")
        self._selected_marker_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Bereit")

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

        self.apply_theme()
        self.refresh_plan_list()
        self.show_plan_list_view()

    def _build_menu_bar(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Neu (Strg+N)", command=lambda: self._handle_intent(UiIntent.NEW_PLAN))
        file_menu.add_command(label="Export PDF", command=lambda: self._handle_intent(UiIntent.EXPORT_PDF))
        file_menu.add_command(label="Einstellungen", command=lambda: self._handle_intent(UiIntent.OPEN_SETTINGS))
        file_menu.add_separator()
        file_menu.add_command(label="Zur Planliste", command=lambda: self._handle_intent(UiIntent.GO_TO_LIST))
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.destroy)
        menubar.add_cascade(label="Datei", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=False)
        self.theme_var = tk.StringVar(value=self.theme_key)
        for key in theme_names():
            label = "Light" if key == "light" else "Dark"
            view_menu.add_radiobutton(label=label, value=key, variable=self.theme_var, command=self._on_theme_changed)
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
            text="Einstellungen",
            command=lambda: self._handle_intent(UiIntent.OPEN_SETTINGS),
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

        export_pdf_button = ttk.Button(
            self.editor_topbar,
            text="PDF exportieren",
            command=lambda: self._handle_intent(UiIntent.EXPORT_PDF),
        )
        export_pdf_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(export_pdf_button)

        set_teacher_button = ttk.Button(
            self.editor_topbar,
            text="Als Lehrertisch setzen",
            command=lambda: self._handle_intent(UiIntent.SET_TEACHER_DESK),
        )
        set_teacher_button.pack(side="left", padx=(8, 0))
        self._bind_editor_return_override(set_teacher_button)

        zoom_in_button = ttk.Button(self.editor_topbar, text="Zoom +", command=lambda: self._handle_intent(UiIntent.ZOOM_IN))
        zoom_in_button.pack(side="right")
        self._bind_editor_return_override(zoom_in_button)

        zoom_out_button = ttk.Button(self.editor_topbar, text="Zoom -", command=lambda: self._handle_intent(UiIntent.ZOOM_OUT))
        zoom_out_button.pack(side="right", padx=(0, 8))
        self._bind_editor_return_override(zoom_out_button)

        self.plan_name_var = tk.StringVar(value="")
        ttk.Label(self.editor_topbar, textvariable=self.plan_name_var).pack(side="right", padx=(0, 14))

        self.grid_container = ttk.Frame(self.editor_view)
        self.grid_container.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.canvas = tk.Canvas(self.grid_container, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.y_scroll = ttk.Scrollbar(self.grid_container, orient="vertical", command=self._yview)
        self.y_scroll.pack(side="right", fill="y")
        self.x_scroll = ttk.Scrollbar(self.editor_view, orient="horizontal", command=self._xview)
        self.x_scroll.pack(fill="x", padx=12)

        self.canvas.configure(
            xscrollcommand=lambda a, b: self._on_canvas_xscroll(a, b),
            yscrollcommand=lambda a, b: self._on_canvas_yscroll(a, b),
            scrollregion=(-SCROLL_REGION, -SCROLL_REGION, SCROLL_REGION, SCROLL_REGION),
        )

        self.details_frame = ttk.Frame(self.editor_view)
        self.details_frame.pack(fill="x", padx=12, pady=(8, 12))

        details_header = ttk.Frame(self.details_frame)
        details_header.pack(fill="x")

        ttk.Label(details_header, textvariable=self.status_var).pack(side="left")
        ttk.Label(details_header, textvariable=self._selected_marker_var).pack(side="right")

        form = ttk.Frame(self.details_frame)
        form.pack(fill="x", pady=(4, 0))

        ttk.Label(form, text="Name").pack(side="left")
        self.name_entry = ttk.Entry(form, textvariable=self._name_var, width=40)
        self.name_entry.pack(side="left", padx=(8, 16))
        self.name_entry.bind("<KeyRelease>", lambda _event: self._on_name_changed())
        self.name_entry.bind("<Escape>", self._on_name_entry_escape)
        self.name_entry.bind("<Return>", self._on_name_entry_return)
        self.name_entry.bind("<FocusIn>", self._on_name_entry_focus_in)
        self.name_entry.bind("<FocusOut>", self._on_name_entry_focus_out)

        self.symbols_frame = ttk.Frame(self.details_frame)
        self.symbols_frame.pack(fill="x", pady=(6, 0))

        self.symbol_legend_frame = ttk.Frame(self.details_frame)
        self.symbol_legend_frame.pack(fill="x", pady=(4, 0))

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<Configure>", lambda _event: self.redraw_grid())
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mouse_wheel)

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-n>", lambda _event: self._handle_intent(UiIntent.NEW_PLAN))
        self.bind("<Delete>", lambda _event: self._handle_intent(UiIntent.DELETE_DESK))
        self.bind("<Escape>", lambda _event: self._handle_intent(UiIntent.ESCAPE))
        self.bind("<Return>", self._on_return_key)
        self.bind("<KP_Enter>", self._on_return_key)

        self.canvas.bind("<Up>", lambda _event: self._handle_intent(UiIntent.MOVE_UP))
        self.canvas.bind("<Down>", lambda _event: self._handle_intent(UiIntent.MOVE_DOWN))
        self.canvas.bind("<Left>", lambda _event: self._handle_intent(UiIntent.MOVE_LEFT))
        self.canvas.bind("<Right>", lambda _event: self._handle_intent(UiIntent.MOVE_RIGHT))

        for shortcut, symbol_name in self._shortcut_to_symbol.items():
            self.bind_all(f"<KeyPress-{shortcut}>", lambda event, s=symbol_name: self._on_symbol_shortcut(event, s), add="+")
            self.bind_all(
                f"<KeyPress-{shortcut.upper()}>",
                lambda event, s=symbol_name: self._on_symbol_shortcut(event, s),
                add="+",
            )

    def _handle_intent(self, intent: str) -> str | None:
        return self.ui_intent_controller.handle_intent(intent)

    def _on_return_key(self, _event) -> str | None:
        if self._is_name_entry_focused():
            return "break"
        if self.editor_view.winfo_ismapped():
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
        if not self.editor_view.winfo_ismapped():
            return None
        if not self.current_plan or not self.current_plan_path:
            return None

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            return None

        self.current_plan = toggle_symbol(self.current_plan, x, y, symbol_name)
        self._save_current_plan(f"Symbol '{symbol_name}' aktualisiert")
        self.redraw_grid()
        self._refresh_details_panel()
        return "break"

    def _load_symbols(self) -> tuple[list[SymbolDefinition], str | None]:
        return load_symbol_definitions(self.symbols_path)

    def _on_theme_changed(self) -> None:
        self.theme_key = normalize_theme_key(self.theme_var.get())
        self._settings["theme"] = self.theme_key
        self.settings_repository.save_settings(self._settings)
        self.apply_theme()
        self.redraw_grid()

    def toggle_theme(self) -> None:
        self.theme_key = "dark" if self.theme_key == "light" else "light"
        self.theme_var.set(self.theme_key)
        self._on_theme_changed()

    def apply_theme(self) -> None:
        theme = THEMES[self.theme_key]

        self.configure(bg=theme["bg_main"])
        self.style.configure("Main.TFrame", background=theme["bg_main"])
        self.style.configure("Panel.TFrame", background=theme["bg_panel"])
        self.style.configure("StrongPanel.TFrame", background=theme["panel_strong"])

        self.style.configure("TLabel", background=theme["bg_main"], foreground=theme["fg_main"])
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

        self.main_frame.configure(style="Main.TFrame")
        self.list_view.configure(style="Panel.TFrame")
        self.list_toolbar.configure(style="StrongPanel.TFrame")
        self.list_body.configure(style="Panel.TFrame")
        self.editor_view.configure(style="Panel.TFrame")
        self.editor_topbar.configure(style="StrongPanel.TFrame")
        self.grid_container.configure(style="Panel.TFrame")
        self.details_frame.configure(style="Panel.TFrame")
        self.canvas.configure(bg=theme["bg_surface"])

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
            student_count = sum(1 for desk in plan.desks if desk.desk_type == "student")
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
        self.editor_view.pack_forget()
        self.list_view.pack(fill="both", expand=True)
        self.interaction_mode = LIST_ACTIVE
        self._ensure_list_selection(preferred_path=self.current_plan_path)
        self.plan_listbox.focus_set()

    def show_editor_view(self) -> None:
        self.list_view.pack_forget()
        self.editor_view.pack(fill="both", expand=True)
        self.interaction_mode = GRID_SELECTED
        if not self.selected_cell:
            self.selected_cell = (0, 0)
        self.canvas.focus_set()

    def open_selected_plan_from_list(self) -> None:
        self._ensure_list_selection(preferred_path=self.current_plan_path)
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

        self.current_plan_path = plan_path
        self.current_plan = plan
        self.plan_name_var.set(f"Plan: {plan.name}")
        self.selected_cell = (0, 0)

        self.show_editor_view()
        self.center_on_cell(0, 0)
        self.redraw_grid()
        self._refresh_details_panel()

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

    def open_settings_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Einstellungen")
        dialog.geometry("700x180")
        dialog.transient(self)
        dialog.grab_set()

        frame = ttk.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        path_var = tk.StringVar(value=str(self.plans_dir))
        ttk.Label(frame, text="Sitzplan-Ordner").pack(anchor="w")

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(6, 12))

        entry = ttk.Entry(row, textvariable=path_var)
        entry.pack(side="left", fill="x", expand=True)

        def browse() -> None:
            selected = filedialog.askdirectory(initialdir=str(self.plans_dir), parent=dialog)
            if selected:
                path_var.set(selected)

        ttk.Button(row, text="Durchsuchen", command=browse).pack(side="left", padx=(8, 0))

        def save() -> None:
            selected_path = Path(path_var.get().strip() or str(self.default_plans_dir))
            selected_path.mkdir(parents=True, exist_ok=True)
            self.plans_dir = selected_path
            self._settings["plans_dir"] = str(selected_path)
            self.settings_repository.save_settings(self._settings)
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
        self.selected_cell = (x, y)
        self.interaction_mode = GRID_SELECTED
        self.canvas.focus_set()
        self.redraw_grid()
        self._refresh_details_panel()

    def _on_canvas_double_click(self, event) -> None:
        x, y = self._event_to_cell(event)
        self.selected_cell = (x, y)
        self.confirm_selected_cell()
        self.enter_name_edit_mode()

    def _event_to_cell(self, event) -> tuple[int, int]:
        world_x = int((self.canvas.canvasx(event.x)) // self.cell_size)
        world_y = int((self.canvas.canvasy(event.y)) // self.cell_size)
        return world_x, world_y

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

        anchor_x, anchor_y = self.selected_cell
        self.cell_size = clamped
        self.redraw_grid()
        self.center_on_cell(anchor_x, anchor_y)

    def center_on_cell(self, x: int, y: int) -> None:
        self.update_idletasks()

        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())

        min_x, min_y, max_x, max_y = -SCROLL_REGION, -SCROLL_REGION, SCROLL_REGION, SCROLL_REGION
        total_w = max_x - min_x
        total_h = max_y - min_y

        target_x = x * self.cell_size + self.cell_size / 2
        target_y = y * self.cell_size + self.cell_size / 2

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

        theme = THEMES[self.theme_key]
        left = self.canvas.canvasx(0)
        top = self.canvas.canvasy(0)
        right = self.canvas.canvasx(self.canvas.winfo_width())
        bottom = self.canvas.canvasy(self.canvas.winfo_height())

        start_x = int(left // self.cell_size) - 1
        end_x = int(right // self.cell_size) + 1
        start_y = int(top // self.cell_size) - 1
        end_y = int(bottom // self.cell_size) + 1

        desks = {(desk.x, desk.y): desk for desk in self.current_plan.desks}
        student_name_font_size = self._compute_uniform_student_name_font_size()

        for cy in range(start_y, end_y + 1):
            for cx in range(start_x, end_x + 1):
                x1 = cx * self.cell_size
                y1 = cy * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                desk = desks.get((cx, cy))
                fill = theme["empty_fill"]
                text_color = theme["fg_muted"]
                main_text = ""
                symbol_lines: list[str] = []

                if desk:
                    if desk.desk_type == "teacher":
                        fill = theme["teacher_fill"]
                        main_text = "Lehrertisch"
                        text_color = theme["fg_main"]
                    else:
                        fill = theme["student_fill"]
                        main_text = desk.student_name or "Schülertisch"
                        symbol_lines = self._symbol_grid_lines(desk.symbols)
                        text_color = theme["fg_main"]

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=fill,
                    outline=theme["grid_line"],
                    width=1,
                    tags=("grid",),
                )

                if main_text:
                    if desk and desk.desk_type == "student":
                        anchor_y = y1 + self.cell_size * 0.24
                        font_size = student_name_font_size
                    else:
                        anchor_y = y1 + self.cell_size / 2
                        font_size = max(8, int(self.cell_size * 0.12))
                    self.canvas.create_text(
                        x1 + self.cell_size / 2,
                        anchor_y,
                        text=main_text,
                        fill=text_color,
                        font=("Segoe UI", font_size, "bold"),
                        tags=("grid",),
                    )

                if symbol_lines:
                    available_h = self.cell_size * 0.56
                    raw_symbol_font = int(available_h / max(1, len(symbol_lines)) - 1)
                    symbol_font = max(4, min(int(self.cell_size * 0.08), raw_symbol_font))
                    line_height = max(symbol_font + 1, 5)
                    start_y = y1 + self.cell_size * 0.42

                    for idx, line in enumerate(symbol_lines):
                        self.canvas.create_text(
                            x1 + self.cell_size / 2,
                            start_y + idx * line_height,
                            text=line,
                            fill=theme["fg_muted"],
                            font=("Segoe UI", symbol_font),
                            tags=("grid",),
                        )

        sx, sy = self.selected_cell
        x1 = sx * self.cell_size
        y1 = sy * self.cell_size
        x2 = x1 + self.cell_size
        y2 = y1 + self.cell_size
        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline=theme["focus_ring"],
            width=3,
            tags=("grid",),
        )

    def _compute_uniform_student_name_font_size(self) -> int:
        base_size = max(8, int(self.cell_size * 0.12))
        min_size = 5
        max_text_width = int(self.cell_size * 0.88)

        labels = [
            (desk.student_name or "Schuelertisch").strip() or "Schuelertisch"
            for desk in self.current_plan.desks
            if desk.desk_type == "student"
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

    def move_selection(self, dx: int, dy: int) -> None:
        if not self.editor_view.winfo_ismapped():
            return
        self.selected_cell = (self.selected_cell[0] + dx, self.selected_cell[1] + dy)
        self.interaction_mode = GRID_SELECTED
        self.center_on_cell(*self.selected_cell)
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

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if desk and desk.desk_type == "teacher":
            self.status_var.set("Lehrertisch ist nicht editierbar")
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            return

        if not desk:
            self.current_plan = create_student_desk(self.current_plan, x, y)
            self._save_current_plan("Schülertisch gesetzt")
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

        x, y = self.selected_cell
        self.current_plan = create_student_desk(self.current_plan, x, y)
        self._save_current_plan("Schülertisch gesetzt")
        self.redraw_grid()
        self._refresh_details_panel()

    def delete_selected_desk(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        x, y = self.selected_cell
        before = self.current_plan.desk_at(x, y)
        if before and before.desk_type == "teacher":
            self.status_var.set("Lehrertisch kann nicht gelöscht werden")
            return

        self.current_plan = delete_desk(self.current_plan, x, y)
        self.interaction_mode = GRID_SELECTED
        self._save_current_plan("Platz gelöscht")
        self.redraw_grid()
        self._refresh_details_panel()

    def set_selected_as_teacher_desk(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        x, y = self.selected_cell
        self.current_plan = set_teacher_desk(self.current_plan, x, y)
        self.selected_cell = (0, 0)
        self.interaction_mode = GRID_SELECTED
        self._save_current_plan("Lehrertisch neu gesetzt")
        self.center_on_cell(0, 0)
        self.redraw_grid()
        self._refresh_details_panel()

    def _refresh_details_panel(self) -> None:
        for child in self.symbols_frame.winfo_children():
            child.destroy()
        for child in self.symbol_legend_frame.winfo_children():
            child.destroy()

        if not self.current_plan:
            self._selected_marker_var.set("")
            self._name_var.set("")
            self.name_entry.configure(state="disabled")
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        self._selected_marker_var.set(f"Markierung: ({x}, {y})")

        if not desk:
            self._name_var.set("")
            self.name_entry.configure(state="disabled")
            if self.interaction_mode == NAME_EDITING:
                self.interaction_mode = GRID_SELECTED
            return

        if desk.desk_type == "teacher":
            self._name_var.set("Lehrertisch")
            self.name_entry.configure(state="disabled")
            if self.interaction_mode == NAME_EDITING:
                self.interaction_mode = GRID_SELECTED
            return

        self._name_var.set(desk.student_name)
        self.name_entry.configure(state="normal")

        ttk.Label(self.symbols_frame, text="Symbole").pack(side="left", padx=(0, 8))
        for symbol in self.symbol_catalog:
            count = int(desk.symbols.get(symbol, 0))
            icon = self._symbol_glyph(symbol)
            shortcut = self._symbol_by_meaning.get(symbol).shortcut if self._symbol_by_meaning.get(symbol) else None
            shortcut_suffix = f" [{shortcut.upper()}]" if shortcut else ""
            caption = f"{icon} {symbol}{shortcut_suffix}" if count == 0 else f"{icon} {symbol} x{count}{shortcut_suffix}"
            button = ttk.Button(
                self.symbols_frame,
                text=caption,
                command=lambda s=symbol: self._toggle_selected_symbol(s),
            )
            button.pack(side="left", padx=(0, 4))

        active_lines = self._symbol_legend_lines(desk.symbols)
        if active_lines:
            for line in active_lines:
                ttk.Label(self.symbol_legend_frame, text=line).pack(anchor="w")

    def _on_name_changed(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            return

        self.current_plan = update_student_name(self.current_plan, x, y, self._name_var.get())
        self._save_current_plan("Name geändert")
        self.redraw_grid()

    def _toggle_selected_symbol(self, symbol: str) -> None:
        if not self.current_plan or not self.current_plan_path:
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            self.status_var.set("Symbol nur für Schülertische")
            return

        self.current_plan = toggle_symbol(self.current_plan, x, y, symbol)
        self._save_current_plan(f"Symbol '{symbol}' aktualisiert")
        self.redraw_grid()
        self._refresh_details_panel()

    def add_symbol_to_selected_desk_dialog(self) -> None:
        if not self.current_plan:
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if not desk or desk.desk_type != "student":
            self.status_var.set("Symbol nur für Schülertische")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Symbol hinzufügen")
        dialog.geometry("350x360")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Symbol auswählen").pack(anchor="w", padx=12, pady=(12, 6))

        listbox = tk.Listbox(dialog, selectmode="browse", exportselection=False, font=("Segoe UI", 11))
        listbox.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        for symbol in self.symbol_catalog:
            listbox.insert(tk.END, symbol)
        if self.symbol_catalog:
            listbox.selection_set(0)

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

    def export_plan_pdf_dialog(self) -> None:
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geöffnet")
            return

        dialog = tk.Toplevel(self)
        dialog.title("PDF exportieren")
        dialog.geometry("420x190")
        dialog.transient(self)
        dialog.grab_set()

        mode_var = tk.StringVar(value="teacher_bottom")
        ttk.Label(dialog, text="Ansicht wählen").pack(anchor="w", padx=12, pady=(12, 6))
        ttk.Radiobutton(
            dialog,
            text="Lehrertisch unten (Standard)",
            value="teacher_bottom",
            variable=mode_var,
        ).pack(anchor="w", padx=12)
        ttk.Radiobutton(
            dialog,
            text="Lehrertisch oben (180° Perspektive)",
            value="teacher_top",
            variable=mode_var,
        ).pack(anchor="w", padx=12, pady=(4, 0))

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

    def _save_current_plan(self, status: str) -> None:
        if not self.current_plan or not self.current_plan_path:
            return
        try:
            self.plan_repository.save_plan(self.current_plan, self.current_plan_path)
            self.status_var.set(f"Gespeichert: {status}")
            self.refresh_plan_list()
        except Exception as exc:
            self.status_var.set(f"Speichern fehlgeschlagen: {exc}")
