from __future__ import annotations

import json
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

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

SCROLL_REGION = 220000
LIST_ACTIVE = "list_active"
GRID_SELECTED = "grid_selected"
NAME_EDITING = "name_editing"

SYMBOL_GLYPH_MAP: dict[str, str] = {
    "Laptop": "💻",
    "Tablet": "📱",
    "Hilfe": "❗",
    "Teamleiter": "⭐",
    "Leise": "🤫",
    "Aktiv": "⚡",
    "Foerderbedarf": "🧩",
    "Praesentation": "🎤",
}

ENTER_DEBUG_LOG = True
ENTER_DEBUG_FILE = Path(__file__).resolve().parents[3] / "Temp" / "enter_debug.log"


class KartographMainWindow(tk.Tk):
    def __init__(
        self,
        settings_repository,
        plan_repository,
        default_plans_dir: Path,
        symbols_path: Path,
    ):
        super().__init__()
        self.title("Kartograph")
        self.geometry("1320x860")
        self.minsize(1000, 680)

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
        self.symbol_catalog = self._load_symbols()

        self.ui_intent_controller = MainWindowUiIntentController(self)

        self._name_var = tk.StringVar(value="")
        self._selected_info_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Bereit")

        self._build_menu_bar()
        self._build_layout()
        self._bind_shortcuts()

        self._initialize_enter_debug_file()

        self.apply_theme()
        self.refresh_plan_list()
        self.show_plan_list_view()

    def _build_menu_bar(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Neu (Strg+N)", command=lambda: self._handle_intent(UiIntent.NEW_PLAN))
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

        ttk.Label(self.details_frame, textvariable=self._selected_info_var).pack(anchor="w")

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

        ttk.Label(self.editor_view, textvariable=self.status_var).pack(anchor="w", padx=12, pady=(0, 8))

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
        self.bind_all("<Return>", self._on_global_return_key, add="+")
        self.bind_all("<KP_Enter>", self._on_global_return_key, add="+")

        self.canvas.bind("<Up>", lambda _event: self._handle_intent(UiIntent.MOVE_UP))
        self.canvas.bind("<Down>", lambda _event: self._handle_intent(UiIntent.MOVE_DOWN))
        self.canvas.bind("<Left>", lambda _event: self._handle_intent(UiIntent.MOVE_LEFT))
        self.canvas.bind("<Right>", lambda _event: self._handle_intent(UiIntent.MOVE_RIGHT))

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

    def _on_global_return_key(self, event) -> str | None:
        self._log_enter_debug("global.enter.start", event)
        widget = event.widget
        if not isinstance(widget, tk.Widget):
            self._log_enter_debug("global.enter.skip.non_widget", event)
            return None

        # Only handle Enter for this main window; dialogs keep their own behavior.
        if widget.winfo_toplevel() is not self:
            self._log_enter_debug("global.enter.skip.foreign_toplevel", event)
            return None

        if widget is self.name_entry:
            self._log_enter_debug("global.enter.skip.name_entry", event)
            return None

        if self.editor_view.winfo_ismapped():
            self._log_enter_debug("global.enter.route.editor_confirm", event)
            return self._handle_intent(UiIntent.CONFIRM_SELECTION)

        if self.interaction_mode == LIST_ACTIVE:
            self._log_enter_debug("global.enter.route.list_open", event)
            return self._handle_intent(UiIntent.LIST_OPEN_SELECTED)

        self._log_enter_debug("global.enter.no_route", event)
        return None

    def _bind_editor_return_override(self, widget: tk.Widget) -> None:
        widget.bind("<Return>", self._on_return_key)
        widget.bind("<KP_Enter>", self._on_return_key)

    def _on_name_entry_focus_in(self, _event) -> None:
        if (
            self.editor_view.winfo_exists()
            and self.editor_view.winfo_ismapped()
            and self.name_entry.winfo_exists()
            and self.name_entry.cget("state") == "normal"
        ):
            self.interaction_mode = NAME_EDITING

    def _on_name_entry_focus_out(self, _event) -> None:
        if self.editor_view.winfo_exists() and self.editor_view.winfo_ismapped() and self.interaction_mode == NAME_EDITING:
            self.interaction_mode = GRID_SELECTED

    def _is_name_entry_focused(self) -> bool:
        return self.focus_get() == self.name_entry

    def _focus_name_entry_cursor_end(self) -> None:
        self._log_enter_debug("focus_name_entry.start")
        if not self.name_entry.winfo_exists():
            self._log_enter_debug("focus_name_entry.skip.no_widget")
            return
        if self.name_entry.cget("state") != "normal":
            self._log_enter_debug("focus_name_entry.skip.not_normal")
            return
        self.interaction_mode = NAME_EDITING
        self.name_entry.focus_set()
        self.name_entry.selection_clear()
        self.name_entry.icursor(tk.END)
        self._log_enter_debug("focus_name_entry.done")

    def _load_symbols(self) -> list[str]:
        try:
            payload = json.loads(self.symbols_path.read_text(encoding="utf-8"))
            symbols = payload.get("symbols")
            if isinstance(symbols, list):
                values = [str(value).strip() for value in symbols if str(value).strip()]
                if values:
                    return values
        except Exception:
            pass
        return ["Laptop", "Tablet", "Hilfe"]

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
            label = f"{plan.name}  |  {student_count} Schülertische  |  {path.name}"
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
        plan_name = simpledialog.askstring("Neuer Sitzplan", "Name des neuen Sitzplans:", parent=self)
        if plan_name is None:
            return

        try:
            plan_path, _plan = self.plan_repository.create_new_plan(self.plans_dir, plan_name)
        except Exception as exc:
            messagebox.showerror("Fehler", f"Neuer Sitzplan konnte nicht erstellt werden:\n{exc}")
            return

        self.refresh_plan_list()
        self.open_plan(plan_path)

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
                symbol_text = ""

                if desk:
                    if desk.desk_type == "teacher":
                        fill = theme["teacher_fill"]
                        main_text = "Lehrertisch"
                        text_color = theme["fg_main"]
                    else:
                        fill = theme["student_fill"]
                        main_text = desk.student_name or "Schülertisch"
                        symbol_text = self._symbol_line(desk.symbols)
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
                    anchor_y = y1 + self.cell_size / 2 if not symbol_text else y1 + self.cell_size * 0.35
                    self.canvas.create_text(
                        x1 + self.cell_size / 2,
                        anchor_y,
                        text=main_text,
                        fill=text_color,
                        font=("Segoe UI", max(8, int(self.cell_size * 0.12)), "bold"),
                        tags=("grid",),
                    )

                if symbol_text:
                    self.canvas.create_text(
                        x1 + self.cell_size / 2,
                        y1 + self.cell_size * 0.72,
                        text=symbol_text,
                        fill=theme["fg_muted"],
                        font=("Segoe UI", max(7, int(self.cell_size * 0.1))),
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

    def _symbol_glyph(self, symbol_name: str) -> str:
        return SYMBOL_GLYPH_MAP.get(symbol_name, "•")

    def _symbol_line(self, symbols: dict[str, int]) -> str:
        if not symbols:
            return ""

        chunks: list[str] = []
        for symbol_name in self.symbol_catalog:
            count = int(symbols.get(symbol_name, 0))
            if 1 <= count <= 3:
                chunks.append(self._symbol_glyph(symbol_name) * count)

        for symbol_name, raw_count in sorted(symbols.items()):
            if symbol_name in self.symbol_catalog:
                continue
            count = int(raw_count)
            if 1 <= count <= 3:
                chunks.append(self._symbol_glyph(symbol_name) * count)

        return "  ".join(chunks)

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
        self._log_enter_debug("enter_name_edit_mode.start")
        if not self.current_plan or not self.current_plan_path:
            self._log_enter_debug("enter_name_edit_mode.skip.no_plan")
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        if desk and desk.desk_type == "teacher":
            self.status_var.set("Lehrertisch ist nicht editierbar")
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            self._log_enter_debug("enter_name_edit_mode.skip.teacher")
            return

        if not desk:
            self.current_plan = create_student_desk(self.current_plan, x, y)
            self._save_current_plan("Schülertisch gesetzt")
            self.redraw_grid()
            self._log_enter_debug("enter_name_edit_mode.created_student_desk")

        self._refresh_details_panel()
        if self.name_entry.cget("state") == "normal":
            self.after_idle(self._focus_name_entry_cursor_end)
            self._log_enter_debug("enter_name_edit_mode.schedule_focus")
        else:
            self._log_enter_debug("enter_name_edit_mode.skip.name_entry_disabled")

    def exit_name_edit_mode(self) -> None:
        if self.editor_view.winfo_ismapped():
            self.interaction_mode = GRID_SELECTED
            self.canvas.focus_set()
            self._refresh_details_panel()

    def _log_enter_debug(self, stage: str, event=None) -> None:
        if not ENTER_DEBUG_LOG:
            return
        try:
            widget = getattr(event, "widget", None) if event is not None else None
            focus_widget = self.focus_get()
            widget_info = f"{type(widget).__name__}:{str(widget)}" if widget is not None else "None"
            focus_info = f"{type(focus_widget).__name__}:{str(focus_widget)}" if focus_widget is not None else "None"
            line = (
                f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] ENTER_DEBUG "
                f"stage={stage} mode={self.interaction_mode} editor_mapped={self.editor_view.winfo_ismapped()} "
                f"widget={widget_info} focus={focus_info} name_state={self.name_entry.cget('state')}"
            )
            print(line)
            self._append_enter_debug_line(line)
            self.status_var.set(line[-200:])
        except Exception:
            pass

    def _initialize_enter_debug_file(self) -> None:
        if not ENTER_DEBUG_LOG:
            return
        try:
            ENTER_DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
            ENTER_DEBUG_FILE.write_text("", encoding="utf-8")
        except Exception:
            pass

    def _append_enter_debug_line(self, line: str) -> None:
        if not ENTER_DEBUG_LOG:
            return
        try:
            with ENTER_DEBUG_FILE.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception:
            pass

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

        if not self.current_plan:
            self._selected_info_var.set("Kein Plan geöffnet")
            self._name_var.set("")
            self.name_entry.configure(state="disabled")
            return

        x, y = self.selected_cell
        desk = self.current_plan.desk_at(x, y)
        self._selected_info_var.set(f"Markierung: ({x}, {y})")

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
            caption = symbol if count == 0 else f"{symbol} {icon * count}"
            button = ttk.Button(
                self.symbols_frame,
                text=caption,
                command=lambda s=symbol: self._toggle_selected_symbol(s),
            )
            button.pack(side="left", padx=(0, 4))
            self._bind_editor_return_override(button)

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

    def _save_current_plan(self, status: str) -> None:
        if not self.current_plan or not self.current_plan_path:
            return
        try:
            self.plan_repository.save_plan(self.current_plan, self.current_plan_path)
            self.status_var.set(f"Gespeichert: {status}")
            self.refresh_plan_list()
        except Exception as exc:
            self.status_var.set(f"Speichern fehlgeschlagen: {exc}")
