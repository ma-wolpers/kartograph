"""Docs-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Stellt die Widget-Bausteine der Dokumentationsansicht bereit: Toolbar
(Aktionsbuttons, Status-Label) und die Doku-Tabelle als bw-gui ``DataGrid``
mit den Bereichen Namen | Datumsspalten | feste Spalten.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import widget_keys
from app.adapters.gui.docs_table_model import DocsPane
from app.adapters.gui.ui_intents import UiIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import KeySpec
from bw_gui.runtime import widgets as tui
from bw_gui.widgets.data_grid import DataGrid, Region

# Pfeiltasten der Doku-Tabelle: tolerierte Zusatz-Modifier (Shift+↑ navigiert wie ↑).
# Alt+←/→ bleibt bewusst frei: das ist das Fenster-Kürzel "voriges/nächstes Datum".
_DOCS_VERTICAL_TOLERANCE = "(tolerate: Ctrl, Alt, Shift)"
_DOCS_HORIZONTAL_TOLERANCE = "(tolerate: Ctrl, Shift)"

# Einzige Zuordnung der fachlichen Doku-Bereiche zu den DataGrid-Regionen.
REGION_BY_PANE: dict[DocsPane, Region] = {DocsPane.NAMES: Region.LEFT, DocsPane.MAIN: Region.SCROLL, DocsPane.RIGHT: Region.RIGHT}
PANE_BY_REGION: dict[Region, DocsPane] = {region: pane for pane, region in REGION_BY_PANE.items()}


class LayoutDocsMixin:
    """Mixin: Dokumentations-Panel mit Toolbar und Doku-Tabelle (``DataGrid``)."""

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
        """Erstellt die Doku-Tabelle als bw-gui ``DataGrid`` und bindet die Pfeiltasten.

        Ein Grid mit drei Bereichen (Namen | Datumsspalten | feste Spalten) und
        zwei verschiebbaren Trennern ersetzt die früheren drei synchronisierten
        Treeviews: eine Zeilenposition für alle Bereiche, nur sichtbare Zellen
        als Canvas-Items. Klicks, Doppelklicks und Kopfklicks meldet das Grid
        als (Zeile, Spaltenschlüssel); die Tasten bindet Kartograph selbst
        (``widget_keys`` auf ``docs_grid.key_widgets``).
        """
        self.docs_grid = DataGrid(
            self.docs_container,
            on_cell_click=lambda row_id, key, region: self._on_docs_cell_click(row_id, key, PANE_BY_REGION[region]),
            on_cell_double_click=lambda row_id, key, region: self._on_docs_cell_double_click(row_id, key),
            on_header_click=self._sort_docs_table_by_key,
        )
        self.docs_grid.frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for widget in self.docs_grid.key_widgets:
            keys = widget_keys(widget)
            for name, handler in (
                (f"Up {_DOCS_VERTICAL_TOLERANCE}", lambda _e: self._on_docs_vertical_nav(-1)),
                (f"Down {_DOCS_VERTICAL_TOLERANCE}", lambda _e: self._on_docs_vertical_nav(1)),
                (f"Left {_DOCS_HORIZONTAL_TOLERANCE}", lambda _e: self._on_docs_horizontal_nav(-1)),
                (f"Right {_DOCS_HORIZONTAL_TOLERANCE}", lambda _e: self._on_docs_horizontal_nav(1)),
            ):
                spec = KeySpec.parse(name)
                keys.bind(spec, handler, binding_id=f"docs.nav.{spec.key.value}", intent="docs.nav")
