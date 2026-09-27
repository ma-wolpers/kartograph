"""Docs-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Stellt die Widget-Bausteine der Dokumentationsansicht bereit:
Toolbar (Aktionsbuttons, Status-Label), das fixierte Namens-Pane sowie den
Treeview-Splitter (Datums-/Fixspalten) — drei synchronisierte Projektionen
derselben logischen Dokutabelle.
"""

from __future__ import annotations

from app.adapters.gui.docs_table_model import VORNAME_KEY, DocsPane
from app.adapters.gui.ui_intents import UiIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui


class LayoutDocsMixin:
    """Mixin: Dokumentations-Panel mit Toolbar, Namens-Pane, Splitter und drei Treeviews."""

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
        """Erstellt Namens-Pane, Splitter, die drei Doku-Treeviews, Scrollbars und Event-Bindings.

        Die Dokutabelle ist eine logische Tabelle, die in drei Treeviews
        projiziert wird: ``docs_name_tree`` (NAMES: Nachname/Vorname),
        ``docs_tree`` (MAIN: Datumsspalten) und ``docs_right_tree`` (RIGHT:
        Zusammenfassung/Noten).

        UI-Invariante: Alle drei Treeviews nutzen denselben ttk-Style
        ``Treeview`` (gleiche Zeilen- und Kopfhöhe), und jedes Pane hat unten
        eine horizontale Scrollbar gleicher Höhe. Nur so bilden sie denselben
        vertikalen Dokumentraum ab und bleiben per ``yview_moveto``
        zeilengenau synchron — kein Tree darf einen eigenen Style/``rowheight``
        bekommen.

        Das Namens-Pane liegt außerhalb des Splitters links und scrollt nie
        mit den Datumsspalten mit ("fixiert"). Seine Breite ist die
        Startbreite der Namensspalten; werden diese per Spaltentrenner
        verbreitert, lässt sich der Inhalt innerhalb des Panes über dessen
        eigene Scrollbar verschieben.
        """
        self.docs_table_container = tui.Frame(self.docs_container)
        self.docs_table_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.docs_names_pane = tui.Frame(self.docs_table_container)
        self.docs_names_pane.pack(side="left", fill="y")
        self.docs_name_tree = tui.Treeview(self.docs_names_pane, show="tree headings", columns=(VORNAME_KEY,))
        self.docs_name_tree.pack(side="top", fill="both", expand=True)
        self.docs_names_x_scroll = tui.Scrollbar(
            self.docs_names_pane, orient="horizontal", command=self.docs_name_tree.xview
        )
        self.docs_names_x_scroll.pack(side="bottom", fill="x")
        self.docs_name_tree.column("#0", width=150, anchor="w", stretch=False)
        self.docs_name_tree.heading("#0", text="Nachname")
        self.docs_name_tree.column(VORNAME_KEY, width=120, anchor="w", stretch=False)
        self.docs_name_tree.heading(VORNAME_KEY, text="Vorname")

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

        self.docs_tree = tui.Treeview(self.docs_main_pane, show="headings")
        self.docs_tree.pack(side="top", fill="both", expand=True)
        self.docs_main_x_scroll = tui.Scrollbar(
            self.docs_main_pane, orient="horizontal", command=self._docs_main_xview
        )
        self.docs_main_x_scroll.pack(side="bottom", fill="x")

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
        self.docs_name_tree.configure(xscrollcommand=self.docs_names_x_scroll.set)
        self.docs_tree.configure(xscrollcommand=self.docs_main_x_scroll.set)
        self.docs_right_tree.configure(xscrollcommand=self.docs_right_x_scroll.set)
        for pane, tree in self._docs_trees_by_pane().items():
            self._bind_docs_pane_events(pane, tree)
        self.docs_right_tree.bind("<Double-Button-1>", self._on_docs_right_tree_double_click)

        self.docs_splitter.bind(
            "<Configure>",
            lambda _event: self._position_docs_splitter_initial(),
            add="+",
        )

    def _bind_docs_pane_events(self, pane: DocsPane, tree) -> None:
        """Bindet die für alle drei Panes identischen Ereignisse an *tree*.

        Die Handler bekommen das Pane mitgegeben, statt pro Pane eigene,
        kopierte Handler zu haben.

        Args:
            pane: Pane, das *tree* darstellt.
            tree: Der Treeview dieses Panes.
        """
        tree.configure(yscrollcommand=lambda first, last, p=pane: self._sync_docs_yscroll(p, first, last))
        tree.bind("<<TreeviewSelect>>", lambda _event, p=pane: self._on_docs_pane_select(p))
        tree.bind("<Button-1>", lambda event, p=pane: self._on_docs_pane_click(p, event))
        tree.bind("<Up>", lambda _event, p=pane: self._on_docs_vertical_nav(-1, source=p))
        tree.bind("<Down>", lambda _event, p=pane: self._on_docs_vertical_nav(1, source=p))
        tree.bind("<Left>", lambda _event: self._on_docs_horizontal_nav(-1))
        tree.bind("<Right>", lambda _event: self._on_docs_horizontal_nav(1))
        tree.bind("<KeyPress>", self._on_docs_pane_keypress, add="+")
        tree.bind("<MouseWheel>", lambda _event: self.after_idle(self._update_docs_cell_highlight))
        tree.bind("<Shift-MouseWheel>", self._on_docs_shift_mouse_wheel)

    def _docs_trees_by_pane(self) -> dict[DocsPane, object]:
        """Liefert die drei Doku-Treeviews, geordnet von links nach rechts.

        Returns:
            Dict ``DocsPane → Treeview``.
        """
        return {
            DocsPane.NAMES: self.docs_name_tree,
            DocsPane.MAIN: self.docs_tree,
            DocsPane.RIGHT: self.docs_right_tree,
        }

    def _pane_of_docs_widget(self, widget) -> DocsPane | None:
        """Ermittelt, welchem Pane ein Widget (Ereignisquelle) gehört.

        Args:
            widget: Beliebiges Tk-Widget.

        Returns:
            Das Pane des Treeviews oder ``None``, falls *widget* keiner der drei Trees ist.
        """
        for pane, tree in self._docs_trees_by_pane().items():
            if widget == tree:
                return pane
        return None

    def _focus_docs_pane(self, pane: DocsPane) -> None:
        """Setzt den Tk-Widget-Fokus auf den Treeview von *pane* (dünner Tk-Wrapper).

        Args:
            pane: Ziel-Pane.
        """
        self._docs_trees_by_pane()[pane].focus_set()
