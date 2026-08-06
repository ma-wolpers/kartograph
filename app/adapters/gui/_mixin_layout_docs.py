"""Docs-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Stellt die Widget-Bausteine der Dokumentationsansicht bereit:
Toolbar (Aktionsbuttons, Status-Label) sowie den doppelten Treeview-Splitter
mit synchronisiertem Scrolling.
"""

from __future__ import annotations

from app.adapters.gui.ui_intents import UiIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui


class LayoutDocsMixin:
    """Mixin: Dokumentations-Panel mit Toolbar, Splitter und Treeviews."""

    def _build_docs_panel_widgets(self) -> None:
        """Orchestriert den Aufbau des Dokumentations-Panels in zwei Phasen."""
        self.docs_container = tui.Frame(self.editor_view)
        self._build_docs_toolbar_widgets()
        self._build_docs_tree_widgets()

    def _build_docs_toolbar_widgets(self) -> None:
        """Erstellt die Dokumentations-Toolbar mit Aktionsbuttons und Statuslabel."""
        self.docs_toolbar = tui.Frame(self.docs_container)
        self.docs_toolbar.pack(fill="x", padx=12, pady=(0, 8))

        docs_grid_button = tui.Button(
            self.docs_toolbar,
            text="Zur Rasteransicht",
            command=lambda: self._handle_intent(UiIntent.VIEW_GRID),
        )
        docs_grid_button.pack(side="left")
        self._attach_hover_help(docs_grid_button, label="Zur Rasteransicht wechseln", shortcut="Ctrl+Shift+D")

        docs_rename_date_button = tui.Button(
            self.docs_toolbar,
            text="Datum umbenennen",
            command=lambda: self._handle_intent(UiIntent.RENAME_DOCUMENTATION_DATE),
        )
        docs_rename_date_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_rename_date_button, label="Ausgewaehltes Datum umbenennen", shortcut="Ctrl+Shift+U")

        docs_delete_date_button = tui.Button(
            self.docs_toolbar,
            text="Datum loeschen",
            command=lambda: self._handle_intent(UiIntent.DELETE_DOCUMENTATION_DATE),
        )
        docs_delete_date_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_delete_date_button, label="Ausgewaehltes Datum inkl. Eintraegen loeschen", shortcut="Ctrl+Shift+Backspace")

        docs_today_button = tui.Button(
            self.docs_toolbar,
            text="Heute",
            command=self.select_today_documentation_date,
        )
        docs_today_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_today_button, label="Auf heutiges Datum springen", shortcut="Ctrl+H")

        docs_add_grade_column_button = tui.Button(
            self.docs_toolbar,
            text="Notenspalte hinzufuegen",
            command=lambda: self._handle_intent(UiIntent.ADD_GRADE_COLUMN),
        )
        docs_add_grade_column_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_add_grade_column_button, label="Neue Notenspalte anlegen", shortcut="Ctrl+Shift+N")

        docs_delete_grade_column_button = tui.Button(
            self.docs_toolbar,
            text="Notenspalte loeschen",
            command=lambda: self._handle_intent(UiIntent.DELETE_GRADE_COLUMN),
        )
        docs_delete_grade_column_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_delete_grade_column_button, label="Ausgewaehlte Notenspalte loeschen", shortcut="Ctrl+Shift+Delete")

        docs_weighting_button = tui.Button(
            self.docs_toolbar,
            text="Gewichtung",
            command=self.configure_grade_weighting_dialog,
        )
        docs_weighting_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_weighting_button, label="Gewichtung konfigurieren")

        docs_set_symbol_button = tui.Button(
            self.docs_toolbar,
            text="Symbol setzen",
            command=self.set_selected_documentation_symbol_dialog,
        )
        docs_set_symbol_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_set_symbol_button, label="Dokumentationssymbol setzen", shortcut="Ctrl+Shift+S")

        docs_clear_symbol_button = tui.Button(
            self.docs_toolbar,
            text="Symbol loeschen",
            command=self.clear_selected_documentation_symbol,
        )
        docs_clear_symbol_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_clear_symbol_button, label="Dokumentationssymbol loeschen", shortcut="Ctrl+Entf oder Ctrl+Backspace")

        docs_set_grade_button = tui.Button(
            self.docs_toolbar,
            text="Note setzen",
            command=self.set_selected_documentation_grade_dialog,
        )
        docs_set_grade_button.pack(side="left", padx=(8, 0))
        self._attach_hover_help(docs_set_grade_button, label="Note setzen", shortcut="Ctrl+G")

        tui.Label(self.docs_toolbar, textvariable=self._doc_selection_status_var).pack(side="right", padx=(0, 12))

    def _build_docs_tree_widgets(self) -> None:
        """Erstellt Splitter, doppelten Treeview, Scrollbars und alle Event-Bindings."""
        self.docs_table_container = tui.Frame(self.docs_container)
        self.docs_table_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.docs_splitter = ui.PanedWindow(
            self.docs_table_container,
            orient="horizontal",
            sashwidth=10,
            sashrelief="raised",
            bd=0,
        )
        self.docs_splitter.pack(side="left", fill="both", expand=True)

        self.docs_main_pane = tui.Frame(self.docs_splitter)
        self.docs_fixed_pane = tui.Frame(self.docs_splitter)
        self.docs_splitter.add(self.docs_main_pane, minsize=320)
        self.docs_splitter.add(self.docs_fixed_pane, minsize=240)

        self.docs_tree = tui.Treeview(self.docs_main_pane, show="tree headings")
        self.docs_tree.pack(side="top", fill="both", expand=True)
        self.docs_main_x_scroll = tui.Scrollbar(
            self.docs_main_pane, orient="horizontal", command=self._docs_main_xview
        )
        self.docs_main_x_scroll.pack(side="bottom", fill="x")
        self.docs_tree.column("#0", width=150, anchor="w", stretch=False)
        self.docs_tree.heading("#0", text="Nachname")

        self.docs_right_tree = tui.Treeview(self.docs_fixed_pane, show="headings")
        self.docs_right_tree.pack(side="top", fill="both", expand=True)
        self.docs_right_x_scroll = tui.Scrollbar(
            self.docs_fixed_pane, orient="horizontal", command=self._docs_right_xview
        )
        self.docs_right_x_scroll.pack(side="bottom", fill="x")

        self.docs_y_scroll = tui.Scrollbar(
            self.docs_table_container, orient="vertical", command=self._docs_yview
        )
        self.docs_y_scroll.pack(side="right", fill="y")

        self._syncing_docs_scroll = False
        self._syncing_docs_selection = False
        self.docs_tree.configure(
            yscrollcommand=self._on_docs_main_yscroll,
            xscrollcommand=self.docs_main_x_scroll.set,
        )
        self.docs_right_tree.configure(
            yscrollcommand=self._on_docs_right_yscroll,
            xscrollcommand=self.docs_right_x_scroll.set,
        )

        self.docs_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_docs_tree_select())
        self.docs_tree.bind("<Button-1>", self._on_docs_tree_click)
        self.docs_tree.bind("<Up>", lambda _event: self._on_docs_vertical_nav(-1, source="main"))
        self.docs_tree.bind("<Down>", lambda _event: self._on_docs_vertical_nav(1, source="main"))
        self.docs_tree.bind("<Left>", lambda _event: self._on_docs_horizontal_nav(-1))
        self.docs_tree.bind("<Right>", lambda _event: self._on_docs_horizontal_nav(1))
        self.docs_tree.bind("<KeyPress>", self._on_docs_tree_keypress, add="+")
        self.docs_tree.bind("<MouseWheel>", lambda _event: self.after_idle(self._update_docs_cell_highlight))
        self.docs_tree.bind("<Shift-MouseWheel>", self._on_docs_shift_mouse_wheel)

        self.docs_right_tree.bind("<<TreeviewSelect>>", lambda _event: self._on_docs_right_tree_select())
        self.docs_right_tree.bind("<Button-1>", self._on_docs_right_tree_click)
        self.docs_right_tree.bind("<Double-Button-1>", self._on_docs_right_tree_double_click)
        self.docs_right_tree.bind("<Up>", lambda _event: self._on_docs_vertical_nav(-1, source="right"))
        self.docs_right_tree.bind("<Down>", lambda _event: self._on_docs_vertical_nav(1, source="right"))
        self.docs_right_tree.bind("<Left>", lambda _event: self._on_docs_horizontal_nav(-1))
        self.docs_right_tree.bind("<Right>", lambda _event: self._on_docs_horizontal_nav(1))
        self.docs_right_tree.bind("<KeyPress>", self._on_docs_right_tree_keypress, add="+")
        self.docs_right_tree.bind("<MouseWheel>", lambda _event: self.after_idle(self._update_docs_cell_highlight))
        self.docs_right_tree.bind("<Shift-MouseWheel>", self._on_docs_shift_mouse_wheel)

        self.docs_splitter.bind(
            "<Configure>",
            lambda _event: self._position_docs_splitter_initial(),
            add="+",
        )
