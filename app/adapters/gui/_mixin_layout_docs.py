"""Docs-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Stellt die Widget-Bausteine der Datenansicht bereit: Toolbar (Aktionsbuttons
aus der Tabelle ``_DOCS_TOOLBAR``), Bereichsleiste (Schalter Doku / Notizen /
Noten, ``DataAreasMixin``) mit Status-Label und die Datentabelle als bw-gui
``DataGrid``. Welche Region ein Bereich belegt, leitet ``regions_by_area`` aus
den angezeigten Bereichen ab.
"""

from __future__ import annotations

from typing import Callable

from app.adapters.gui._local_keys import widget_keys
from app.adapters.gui.main_window_constants import DOCS_INTENT_AREAS
from app.adapters.gui.ui_intents import UiIntent
from app.core.domain.data_view_areas import DataArea
from app.core.domain.grade_scale import GRADE_INPUT_START_CHARACTERS
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import KeySpec
from bw_gui.runtime import widgets as tui
from bw_gui.widgets.data_grid import DataGrid, Region

# Pfeiltasten der Doku-Tabelle: tolerierte Zusatz-Modifier (Shift+↑ navigiert wie ↑).
# Alt+←/→ bleibt bewusst frei: das ist das Fenster-Kürzel "voriges/nächstes Datum".
_DOCS_VERTICAL_TOLERANCE = "(tolerate: Ctrl, Alt, Shift)"
_DOCS_HORIZONTAL_TOLERANCE = "(tolerate: Ctrl, Shift)"

_REGIONS_LEFT_TO_RIGHT = (Region.LEFT, Region.SCROLL, Region.RIGHT)


def regions_by_area(areas: tuple[DataArea, ...]) -> dict[DataArea, Region]:
    """Einzige Zuordnung angezeigter Bereich → ``DataGrid``-Region.

    Der n-te angezeigte Bereich belegt die n-te Region: Namen links, der erste
    sichtbare Bereich in der mitwachsenden Mitte, der zweite rechts. Eine Region
    ohne Bereich bleibt leer (das Grid blendet leere Randregionen aus). Passt,
    weil ``data_view_areas`` höchstens zwei Bereiche neben den Namen zulässt.

    Args:
        areas: Angezeigte Bereiche links → rechts (``DocColumnAxis.areas``).

    Returns:
        Bereich → Region, z. B. ``{NAMEN: LEFT, NOTIZEN: SCROLL, NOTEN: RIGHT}``.
    """
    return dict(zip(areas, _REGIONS_LEFT_TO_RIGHT))


_ToolbarAction = tuple[str, Callable[..., object], str, "str | tuple[str, ...] | None", "DataArea | None"]
# (Beschriftung, Aktion(fenster), Hover-Text, Intent für den Kürzel-Hinweis, Bereich oder None = immer aktiv)
_DOCS_TOOLBAR: tuple[_ToolbarAction, ...] = (
    ("Zur Rasteransicht", lambda w: w._handle_intent(UiIntent.VIEW_GRID), "Zur Rasteransicht wechseln",
     UiIntent.TOGGLE_DOCUMENTATION, None),
    ("Datum umbenennen", lambda w: w._handle_intent(UiIntent.RENAME_DOCUMENTATION_DATE), "Ausgewaehltes Datum umbenennen",
     UiIntent.RENAME_DOCUMENTATION_DATE, DOCS_INTENT_AREAS[UiIntent.RENAME_DOCUMENTATION_DATE]),
    ("Datum loeschen", lambda w: w._handle_intent(UiIntent.DELETE_DOCUMENTATION_DATE),
     "Ausgewaehltes Datum inkl. Eintraegen loeschen", UiIntent.DELETE_DOCUMENTATION_DATE,
     DOCS_INTENT_AREAS[UiIntent.DELETE_DOCUMENTATION_DATE]),
    ("Heute", lambda w: w.select_today_documentation_date(), "Auf heutiges Datum springen", UiIntent.DOCS_TODAY, DataArea.DOKU),
    ("Notenspalte hinzufuegen", lambda w: w._handle_intent(UiIntent.ADD_GRADE_COLUMN), "Neue Notenspalte anlegen",
     UiIntent.ADD_GRADE_COLUMN, DOCS_INTENT_AREAS[UiIntent.ADD_GRADE_COLUMN]),
    ("Notenspalte loeschen", lambda w: w._handle_intent(UiIntent.DELETE_GRADE_COLUMN), "Ausgewaehlte Notenspalte loeschen",
     UiIntent.DELETE_GRADE_COLUMN, DOCS_INTENT_AREAS[UiIntent.DELETE_GRADE_COLUMN]),
    ("Gewichtung", lambda w: w.configure_grade_weighting_dialog(), "Gewichtung konfigurieren", None, DataArea.NOTEN),
    ("Symbol setzen", lambda w: w.set_selected_documentation_symbol_dialog(), "Dokumentationssymbol setzen",
     UiIntent.DOCS_SYMBOL, DataArea.DOKU),
    ("Symbol loeschen", lambda w: w.clear_selected_documentation_symbol(), "Dokumentationssymbol loeschen",
     (UiIntent.DOCS_CLEAR, UiIntent.DOCS_CLEAR_BACKSPACE), DataArea.DOKU),
    ("Note setzen", lambda w: w.set_selected_documentation_grade_dialog(), "Note setzen", UiIntent.DOCS_GRADE, DataArea.NOTEN),
    ("Notizspalte hinzufuegen", lambda w: w.add_note_column_dialog(), "Neue Notiz- oder Ja/Nein-Spalte anlegen",
     None, DataArea.NOTIZEN),
    ("Notizspalte loeschen", lambda w: w.delete_note_column_dialog(), "Ausgewaehlte Notiz- oder Ja/Nein-Spalte loeschen",
     None, DataArea.NOTIZEN),
)


class LayoutDocsMixin:
    """Mixin: Daten-Panel mit Toolbar, Bereichsleiste und Datentabelle (``DataGrid``)."""

    def _build_docs_panel_widgets(self) -> None:
        """Orchestriert den Aufbau des Daten-Panels: Toolbar, Bereichsleiste, Tabelle."""
        self.docs_container = tui.Frame(self.editor_view)
        self._build_docs_toolbar_widgets()
        self._build_docs_tree_widgets()

    def _build_docs_toolbar_widgets(self) -> None:
        """Erstellt die Toolbar aus ``_DOCS_TOOLBAR`` und darunter die Bereichsleiste mit Statuslabel.

        Jeder Knopf merkt sich seinen Bereich (``self._docs_area_buttons``);
        ``_sync_data_area_controls`` graut Knöpfe ausgeblendeter Bereiche aus.
        """
        self.docs_toolbar = tui.Frame(self.docs_container)
        self.docs_toolbar.pack(fill="x", padx=12, pady=(0, 4))
        self._docs_area_buttons: list[tuple[DataArea, object]] = []
        for index, (text, action, hover, intent, area) in enumerate(_DOCS_TOOLBAR):
            button = tui.Button(self.docs_toolbar, text=text, command=lambda a=action: a(self))
            button.pack(side="left", padx=(0 if index == 0 else 8, 0))
            self._attach_hover_help(button, label=hover, **({"intent": intent} if intent is not None else {}))
            if area is not None:
                self._docs_area_buttons.append((area, button))

        area_bar = tui.Frame(self.docs_container)
        area_bar.pack(fill="x", padx=12, pady=(0, 8))
        self._build_data_area_switches(area_bar)
        tui.Label(area_bar, textvariable=self._doc_selection_status_var).pack(side="right", padx=(0, 12))

    def _build_docs_tree_widgets(self) -> None:
        """Erstellt die Datentabelle als bw-gui ``DataGrid`` und bindet Pfeiltasten und Noten-Tippen.

        Ein Grid mit bis zu drei Regionen (Namen | erster sichtbarer Bereich |
        zweiter sichtbarer Bereich) und verschiebbaren Trennern: eine
        Zeilenposition für alle Bereiche, nur sichtbare Zellen als Canvas-Items.
        Klicks, Doppelklicks und Kopfklicks meldet das Grid als (Zeile,
        Spaltenschlüssel); Klicks werden über ``_doc_area_at`` dem Bereich der
        Region zugeordnet. Die Tasten bindet Kartograph selbst (``widget_keys``
        auf ``docs_grid.key_widgets``).
        """
        self.docs_grid = DataGrid(
            self.docs_container,
            on_cell_click=lambda row_id, key, region: self._on_docs_cell_click(row_id, key, self._doc_area_at(region)),
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
            # Tippen auf einer Notenzelle startet den Editor (widget-lokal, also vor den Fenster-Kürzeln).
            for character in GRADE_INPUT_START_CHARACTERS:
                keys.bind(
                    KeySpec.char(character),
                    lambda _e, c=character: self._on_docs_grade_type_in(c),
                    binding_id=f"docs.type_in.{character}",
                    intent="docs.type_in",
                )
