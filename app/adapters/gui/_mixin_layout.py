"""Layout-Mixin für das Kartograph-Hauptfenster.

Enthält den Aufbau von Hauptrahmen, Listenansicht sowie die obere Editorleiste
(Toolbar-Buttons, Planname, Canvas-Panel) des Editorbereichs. Die Docs-Panel-
Widgets werden in ``_mixin_layout_docs.py`` ergänzt.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, bind_action, widget_keys
from app.adapters.gui.toolbar_icon_styler import ToolbarIconStyler
from app.adapters.gui.ui_intents import UiIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import bind_click, on_listbox_select, ui, widgets as tui
from bw_gui.contracts import KeySpec
from bw_gui.shortcuts import compose_hover_text as compose_shared_hover_text, compose_hover_text_for_intent
from bw_gui.widgets import HoverTooltip as SharedHoverTooltip
from bw_gui.runtime.idle_render import IdleRenderScheduler
from bw_gui.widgets.canvas_item_pool import CanvasItemPool


class LayoutMixin:
    """Mixin: Grundstruktur, Listenansicht und Editor-Aufbau."""

    def _build_layout(self, frame=None) -> None:
        """Erstellt den Hauptrahmen und delegiert an List- und Editor-Aufbau."""
        self._toolbar_icons = ToolbarIconStyler()
        self.style = tui.Style(self)
        self.style.theme_use("clam")

        self.main_frame = tui.Frame(frame if frame is not None else self)
        self.main_frame.pack(fill="both", expand=True)

        self.list_view = tui.Frame(self.main_frame)
        self.editor_view = tui.Frame(self.main_frame)

        self._build_list_view()
        self._build_editor_view()

    def _attach_hover_help(
        self,
        widget: ui.Widget,
        *,
        label: str,
        intent: str | tuple[str, ...] | None = None,
        shortcut: KeySpec | str | None = None,
    ) -> None:
        """Bindet einen geteilten Hover-Tooltip mit Tastaturkürzel-Hinweis an ein Widget.

        Die Taste steht nie als Text im Aufruf: Mit *intent* liest der Tooltip sie beim
        Anzeigen aus der Laufzeit-Registry (``self._runtime_shortcuts``; die Bindungen
        entstehen erst nach dem Layout), sonst kommt sie aus der lokalen Bindung selbst.

        Args:
            widget: Ziel-Widget.
            label: Anzeigename der Aktion.
            intent: Intent der Registry-Bindung; mehrere zeigen ihre Tasten als Alternativen.
            shortcut: Taste einer dialog-/widgetlokalen Bindung (``_local_keys.ENTER``)
                oder eines Datenkürzels (Symbolbuchstabe).
        """
        provider = None
        text = compose_shared_hover_text(label, shortcut)
        if intent is not None:
            text = ""

            def provider() -> str:
                return compose_hover_text_for_intent(label, intent=intent, shortcuts=self._runtime_shortcuts)

        existing = getattr(widget, "_bw_hover_tooltip", None)
        if existing is not None:
            setattr(existing, "text", text)
            setattr(existing, "text_provider", provider)
            setattr(existing, "theme_key", self._shared_menu_theme_key())
            return

        tooltip = SharedHoverTooltip(widget, text, theme_key=self._shared_menu_theme_key(), text_provider=provider)
        setattr(widget, "_bw_hover_tooltip", tooltip)
        self._hover_tooltips.append(tooltip)

    def _create_toolbar_shortcut_button(
        self,
        parent: ui.Widget,
        *,
        icon_key: str,
        icon: str,
        intent: str,
        label: str,
        shortcut_intent: str | None = None,
        side: str = "left",
        padx=(0, 8),
        bind_editor_return: bool = False,
    ) -> tui.Button:
        """Erstellt einen kompakten Icon-Button für Toolbars mit Hover-Hilfe.

        Args:
            parent: Eltern-Widget.
            icon_key: Schlüssel des PNG-Icons in ``assets/toolbar`` (siehe
                ``ToolbarIconStyler``). Zeigt der zugehörige Button ein PNG.
            icon: Unicode-Ersatzzeichen, falls das PNG-Icon fehlt. Wird in
                einem schmalen ``width=2``-Button dargestellt (siehe
                Funktionskörper), damit er trotz des ttk-Standardstils
                genauso kompakt wirkt wie die PNG-Icon-Buttons -- ttk
                reserviert für einen ``text=``-Button ohne explizite
                ``width`` sonst deutlich mehr Platz, als ein einzelnes
                Zeichen braucht.
            intent: Ausgelöster UiIntent; zugleich Quelle der Taste in der Hover-Hilfe.
            label: Beschriftung der Aktion für die Hover-Hilfe.
            shortcut_intent: Intent der Tastenbindung, falls sie nicht *intent* auslöst,
                sondern eine kontextabhängige Taste (Enter/Entf/Esc über ``GLOBAL_*``).
            side: Pack-Seite (``"left"`` oder ``"right"``).
            padx: Horizontaler Außenabstand.
            bind_editor_return: Wenn True, wird Return/KP_Enter an den Button gebunden.

        Returns:
            Der erstellte Button.
        """

        def command() -> None:
            self._handle_intent(intent)

        button = self._toolbar_icons.create_button(parent, icon_key, command)
        if button is None:
            caption = icon.strip() or label
            button = tui.Button(parent, text=caption, command=command, width=2)
        button.pack(side=side, padx=padx)
        if bind_editor_return:
            self._bind_editor_return_override(button)
        self._attach_hover_help(button, label=label, intent=shortcut_intent or intent)
        return button

    def _build_list_view(self) -> None:
        """Erstellt die Planlistenansicht mit Toolbar und scrollbarer Listbox."""
        self.list_toolbar = tui.Frame(self.list_view)
        self.list_toolbar.pack(fill="x", padx=14, pady=(14, 8))

        self._create_toolbar_shortcut_button(self.list_toolbar, icon_key="new_plan", icon="＋", intent=UiIntent.NEW_PLAN, label="Neuen Sitzplan erstellen")
        self._create_toolbar_shortcut_button(self.list_toolbar, icon_key="open_plan", icon="↩", intent=UiIntent.LIST_OPEN_SELECTED, label="Ausgewaehlten Sitzplan oeffnen", shortcut_intent=UiIntent.GLOBAL_RETURN)
        self._create_toolbar_shortcut_button(self.list_toolbar, icon_key="rename_plan", icon="✎", intent=UiIntent.RENAME_SELECTED_PLAN, label="Ausgewaehlten Sitzplan umbenennen")
        self._create_toolbar_shortcut_button(self.list_toolbar, icon_key="delete_plan", icon="⌫", intent=UiIntent.DELETE_SELECTED_PLAN, label="Ausgewaehlten Sitzplan loeschen", shortcut_intent=UiIntent.GLOBAL_DELETE)
        self._create_toolbar_shortcut_button(self.list_toolbar, icon_key="duplicate_plan", icon="⧉", intent=UiIntent.DUPLICATE_SELECTED_PLAN, label="Ausgewaehlten Sitzplan duplizieren")
        self._create_toolbar_shortcut_button(self.list_toolbar, icon_key="archive_plan", icon="🗄", intent=UiIntent.ARCHIVE_SELECTED_PLAN, label="Ausgewaehlten Sitzplan archivieren/wiederherstellen", padx=(0, 0))

        self.list_body = tui.Frame(self.list_view)
        self.list_body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.plan_listbox = ui.Listbox(
            self.list_body,
            selectmode="browse",
            activestyle="none",
            font=("Segoe UI", 12),
            exportselection=False,
            borderwidth=1,
        )
        self.plan_listbox.pack(side="left", fill="both", expand=True)
        bind_click(self.plan_listbox, lambda _event: self._handle_intent(UiIntent.LIST_OPEN_SELECTED), count=2)
        bind_action(
            widget_keys(self.plan_listbox),
            ENTER,
            lambda: self._handle_intent(UiIntent.LIST_OPEN_SELECTED),
            binding_id="list.open",
        )
        on_listbox_select(self.plan_listbox, lambda _change: self._ensure_list_selection())

        scroll = tui.Scrollbar(self.list_body, orient="vertical", command=self.plan_listbox.yview)
        scroll.pack(side="right", fill="y")
        self.plan_listbox.configure(yscrollcommand=scroll.set)

    def _build_editor_view(self) -> None:
        """Orchestriert den Aufbau des gesamten Editorbereichs in vier Phasen."""
        self._build_editor_topbar()
        self._build_canvas_panel_widgets()
        self._build_details_container_widgets()
        self._build_docs_panel_widgets()

    def _build_editor_topbar(self) -> None:
        """Erstellt die Editor-Toolbar mit allen Aktions-Buttons und dem Plannamen."""
        self.editor_topbar = tui.Frame(self.editor_view)
        self.editor_topbar.pack(fill="x", padx=12, pady=(12, 8))

        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="go_to_list", icon="≡", intent=UiIntent.GO_TO_LIST, label="Zur Planliste wechseln", shortcut_intent=UiIntent.ESCAPE, bind_editor_return=True, padx=(0, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="delete_desk", icon="⌫", intent=UiIntent.DELETE_DESK, label="Ausgewaehlten Platz loeschen", shortcut_intent=UiIntent.GLOBAL_DELETE, bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="add_symbol", icon="★", intent=UiIntent.ADD_SYMBOL, label="Symbol zum markierten Platz hinzufuegen", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="tablegroup_settings", icon="▦", intent=UiIntent.OPEN_TABLEGROUP_SETTINGS, label="Tischgruppen-Einstellungen oeffnen", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="export_pdf", icon="⤓", intent=UiIntent.EXPORT_PDF, label="Plan als PDF exportieren", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="export_namenfit_csv", icon="▤", intent=UiIntent.EXPORT_NAMENFIT_CSV, label="Plan fuer Namenfit als CSV exportieren", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="export_student_pngs", icon="▭", intent=UiIntent.EXPORT_STUDENT_PNGS_ZIP, label="Sitzkaertchen je Schueler als ZIP exportieren", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="teacher_desk", icon="♛", intent=UiIntent.SET_TEACHER_DESK, label="Ausgewaehlten Platz als Lehrertisch setzen", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="toggle_documentation", icon="⌗", intent=UiIntent.TOGGLE_DOCUMENTATION, label="Dokumentationsansicht ein- oder ausblenden", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="symbol_filter", icon="⚲", intent=UiIntent.GRID_SYMBOL_FILTER, label="Sichtbare Symbole im Grid filtern", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="manage_symbols", icon="❖", intent=UiIntent.MANAGE_SYMBOLS, label="Symbol-Verwaltung oeffnen (alle Symbole einsehen, eigene anlegen/bearbeiten)", bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="zoom_out", icon="−", intent=UiIntent.ZOOM_OUT, label="Ansicht herauszoomen", side="right", bind_editor_return=True, padx=(0, 8))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon_key="zoom_in", icon="+", intent=UiIntent.ZOOM_IN, label="Ansicht hineinzoomen", side="right", bind_editor_return=True, padx=(0, 0))

        self.plan_name_var = ui.StringVar(value="")
        tui.Label(self.editor_topbar, textvariable=self.plan_name_var).pack(side="right", padx=(0, 14))

    def _build_canvas_panel_widgets(self) -> None:
        """Erstellt Canvas, Scrollbars und den Grid-Stack des Editorbereichs."""
        self.grid_stack = tui.Frame(self.editor_view)
        self.grid_container = tui.Frame(self.grid_stack)

        self.canvas = ui.Canvas(self.grid_container, highlightthickness=0)
        # Hintergrundkacheln über den bw-gui CanvasItemPool: über Aufrufe hinweg
        # wiederverwendet, Tk bekommt nur Änderungen. Andere Raster-Items (Pulte,
        # Auswahl) tragen noch "grid_transient" und werden je Redraw neu gezeichnet.
        self._grid_tile_pool = CanvasItemPool(self.canvas, "rectangle", tags=("grid",))
        self._grid_scheduler = IdleRenderScheduler(self.canvas)  # s. _request_grid_redraw
        self.canvas.pack(side="left", fill="both", expand=True)

        self.y_scroll = tui.Scrollbar(self.grid_container, orient="vertical", command=self._yview, takefocus=False)
        self.y_scroll.pack(side="right", fill="y")
        self.x_scroll = tui.Scrollbar(self.grid_stack, orient="horizontal", command=self._xview, takefocus=False)
        self.x_scroll.pack(fill="x")

        self.canvas.configure(
            xscrollcommand=lambda a, b: self._on_canvas_xscroll(a, b),
            yscrollcommand=lambda a, b: self._on_canvas_yscroll(a, b),
        )
        self._update_scroll_region()
