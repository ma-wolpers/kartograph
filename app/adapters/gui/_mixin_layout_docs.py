"""Docs-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Stellt die Widget-Bausteine der Datenansicht bereit: Symbol-Toolbar (Tabelle
``_DOCS_TOOLBAR``; Spaltenknöpfe wirken auf die Spalte der ausgewählten Zelle), Bereichsleiste (Schalter Doku / Notizen /
Noten, ``DataAreasMixin``) mit Status-Label und die Datentabelle als bw-gui
``DataGrid``. Welche Region ein Bereich belegt, leitet ``regions_by_area`` aus
den angezeigten Bereichen ab.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import widget_keys
from app.adapters.gui.main_window_constants import DOCS_COLUMN_ACTIONS, DOCS_INTENT_AREAS
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


# (Symbolschlüssel in toolbar_icon_styler, Ersatzzeichen ohne PNG, Hover-Text, Intent). Hover-Text
# ``None``: Spaltenaktion -- der Text kommt bei jedem Anzeigen aus der Auswahl (docs_column_actions).
# Bereich (Ausgrauen) und Aktion stehen nicht hier, sondern in DOCS_INTENT_AREAS / DOCS_COLUMN_ACTIONS.
# Zellen bearbeiten/leeren hat bewusst keinen Knopf: Enter/Doppelklick bzw. Entf (Nutzerin 2026-11-22).
_DOCS_TOOLBAR: tuple[tuple[str, str, str | None, str], ...] = (
    ("toggle_documentation", "⌗", "Zur Rasteransicht wechseln", UiIntent.TOGGLE_DOCUMENTATION),
    ("docs_column_add", "＋", None, UiIntent.DOCS_COLUMN_ADD),
    ("docs_column_rename", "✎", None, UiIntent.DOCS_COLUMN_RENAME),
    ("docs_column_delete", "⌫", None, UiIntent.DOCS_COLUMN_DELETE),
    ("docs_column_groups", "▦", None, UiIntent.DOCS_COLUMN_GROUPS),
    ("docs_today", "◷", "Auf heutiges Datum springen", UiIntent.DOCS_TODAY),
    ("docs_weighting", "⚖", "Gewichtung der Noten einstellen", UiIntent.DOCS_WEIGHTING),
)
_GROUP_STARTS = (UiIntent.DOCS_COLUMN_ADD, UiIntent.DOCS_TODAY)
"""Erster Knopf einer Gruppe bekommt mehr Abstand: Ansicht | Spalten | Doku/Noten."""


class LayoutDocsMixin:
    """Mixin: Daten-Panel mit Toolbar, Bereichsleiste und Datentabelle (``DataGrid``)."""

    def _build_docs_panel_widgets(self) -> None:
        """Orchestriert den Aufbau des Daten-Panels: Toolbar, Bereichsleiste, Tabelle."""
        self.docs_container = tui.Frame(self.editor_view)
        self._build_docs_toolbar_widgets()
        self._build_docs_tree_widgets()

    def _build_docs_toolbar_widgets(self) -> None:
        """Erstellt die Symbol-Toolbar aus ``_DOCS_TOOLBAR`` und darunter die Bereichsleiste mit Statuslabel.

        Dieselben Symbolknöpfe wie in der Tischansicht (``_create_toolbar_shortcut_button``).
        Knöpfe mit festem Bereich merkt sich ``self._docs_area_buttons``
        (``_sync_data_area_controls`` graut sie bei ausgeblendetem Bereich aus);
        Spaltenknöpfe ``self._docs_column_buttons`` (``_sync_docs_column_buttons``
        graut sie je nach ausgewählter Zelle aus, ihr Hover-Text folgt der Auswahl).
        """
        self.docs_toolbar = tui.Frame(self.docs_container)
        self.docs_toolbar.pack(fill="x", padx=12, pady=(0, 4))
        self._docs_area_buttons: list[tuple[DataArea, object]] = []
        self._docs_column_buttons: dict[str, object] = {}
        for index, (icon_key, glyph, hover, intent) in enumerate(_DOCS_TOOLBAR):
            action = DOCS_COLUMN_ACTIONS.get(intent)
            label = hover if action is None else (lambda a=action: self._docs_column_action_label(a))
            button = self._create_toolbar_shortcut_button(
                self.docs_toolbar, icon_key=icon_key, icon=glyph, intent=intent, label=label,
                padx=(0 if index == 0 else 16 if intent in _GROUP_STARTS else 8, 0),
            )
            if action is not None:
                self._docs_column_buttons[action] = button
            if DOCS_INTENT_AREAS.get(intent) is not None:
                self._docs_area_buttons.append((DOCS_INTENT_AREAS[intent], button))

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
