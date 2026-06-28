"""Layout-Mixin für das Kartograph-Hauptfenster.

Enthält den Aufbau von Hauptrahmen, Listenansicht sowie die obere Editorleiste
(Toolbar-Buttons, Planname, Canvas-Panel) des Editorbereichs. Die Docs-Panel-
Widgets werden in ``_mixin_layout_docs.py`` ergänzt.
"""

from __future__ import annotations

from app.adapters.gui.ui_intents import UiIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui
from bw_gui.shortcuts import compose_hover_text as compose_shared_hover_text
from bw_gui.widgets import HoverTooltip as SharedHoverTooltip


class LayoutMixin:
    """Mixin: Grundstruktur, Listenansicht und Editor-Aufbau."""

    def _build_layout(self) -> None:
        """Erstellt den Hauptrahmen und delegiert an List- und Editor-Aufbau."""
        self.style = tui.Style(self)
        self.style.theme_use("clam")

        self.main_frame = tui.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

        self.list_view = tui.Frame(self.main_frame)
        self.editor_view = tui.Frame(self.main_frame)

        self._build_list_view()
        self._build_editor_view()

    def _attach_hover_help(self, widget: ui.Widget, *, label: str, shortcut: str | None = None) -> None:
        """Bindet einen geteilten Hover-Tooltip mit Tastaturkürzel-Hinweis an ein Widget.

        Args:
            widget: Ziel-Widget.
            label: Anzeigename der Aktion.
            shortcut: Optionales Tastaturkürzel als Text.
        """
        shortcut_text = (shortcut or "").strip()
        text = compose_shared_hover_text(label, shortcut_text)

        existing = getattr(widget, "_bw_hover_tooltip", None)
        if existing is not None:
            setattr(existing, "text", text)
            setattr(existing, "theme_key", self._shared_menu_theme_key())
            return

        tooltip = SharedHoverTooltip(widget, text, theme_key=self._shared_menu_theme_key())
        setattr(widget, "_bw_hover_tooltip", tooltip)
        self._hover_tooltips.append(tooltip)

    def _create_toolbar_shortcut_button(
        self,
        parent: ui.Widget,
        *,
        icon: str,
        shortcut: str,
        label: str,
        command,
        side: str = "left",
        padx=(0, 8),
        bind_editor_return: bool = False,
    ) -> tui.Button:
        """Erstellt einen kompakten Icon-Button für Toolbars mit Hover-Hilfe.

        Args:
            parent: Eltern-Widget.
            icon: Angezeigtes Icon-Zeichen.
            shortcut: Tastaturkürzel für die Hover-Hilfe.
            label: Beschriftung der Aktion für die Hover-Hilfe.
            command: Callback-Funktion.
            side: Pack-Seite (``"left"`` oder ``"right"``).
            padx: Horizontaler Außenabstand.
            bind_editor_return: Wenn True, wird Return/KP_Enter an den Button gebunden.

        Returns:
            Der erstellte Button.
        """
        caption = icon.strip() or label
        button = tui.Button(parent, text=caption, command=command)
        button.pack(side=side, padx=padx)
        if bind_editor_return:
            self._bind_editor_return_override(button)
        self._attach_hover_help(button, label=label, shortcut=shortcut)
        return button

    def _build_list_view(self) -> None:
        """Erstellt die Planlistenansicht mit Toolbar und scrollbarer Listbox."""
        self.list_toolbar = tui.Frame(self.list_view)
        self.list_toolbar.pack(fill="x", padx=14, pady=(14, 8))

        self._create_toolbar_shortcut_button(self.list_toolbar, icon="＋", shortcut="Ctrl+N", label="Neuen Sitzplan erstellen", command=lambda: self._handle_intent(UiIntent.NEW_PLAN))
        self._create_toolbar_shortcut_button(self.list_toolbar, icon="↩", shortcut="Enter", label="Ausgewaehlten Sitzplan oeffnen", command=lambda: self._handle_intent(UiIntent.LIST_OPEN_SELECTED))
        self._create_toolbar_shortcut_button(self.list_toolbar, icon="✎", shortcut="F2", label="Ausgewaehlten Sitzplan umbenennen", command=lambda: self._handle_intent(UiIntent.RENAME_SELECTED_PLAN))
        self._create_toolbar_shortcut_button(self.list_toolbar, icon="⌫", shortcut="Entf", label="Ausgewaehlten Sitzplan loeschen", command=lambda: self._handle_intent(UiIntent.DELETE_SELECTED_PLAN))
        self._create_toolbar_shortcut_button(self.list_toolbar, icon="⧉", shortcut="Ctrl+D", label="Ausgewaehlten Sitzplan duplizieren", command=lambda: self._handle_intent(UiIntent.DUPLICATE_SELECTED_PLAN), padx=(0, 0))

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
        self.plan_listbox.bind("<Double-Button-1>", lambda _event: self._handle_intent(UiIntent.LIST_OPEN_SELECTED))
        self.plan_listbox.bind("<Return>", lambda _event: self._handle_intent(UiIntent.LIST_OPEN_SELECTED))
        self.plan_listbox.bind("<<ListboxSelect>>", lambda _event: self._ensure_list_selection())

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

        self._create_toolbar_shortcut_button(self.editor_topbar, icon="≡", shortcut="Esc", label="Zur Planliste wechseln", command=lambda: self._handle_intent(UiIntent.GO_TO_LIST), bind_editor_return=True, padx=(0, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="⌫", shortcut="Entf", label="Ausgewaehlten Platz loeschen", command=lambda: self._handle_intent(UiIntent.DELETE_DESK), bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="★", shortcut="S", label="Symbol zum markierten Platz hinzufuegen", command=lambda: self._handle_intent(UiIntent.ADD_SYMBOL), bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="▦", shortcut="Ctrl+T", label="Tischgruppen-Einstellungen oeffnen", command=lambda: self._handle_intent(UiIntent.OPEN_TABLEGROUP_SETTINGS), bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="⤓", shortcut="Ctrl+E", label="Plan als PDF exportieren", command=lambda: self._handle_intent(UiIntent.EXPORT_PDF), bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="♛", shortcut="Ctrl+Enter", label="Ausgewaehlten Platz als Lehrertisch setzen", command=lambda: self._handle_intent(UiIntent.SET_TEACHER_DESK), bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="⌗", shortcut="Ctrl+Shift+D", label="Dokumentationsansicht ein- oder ausblenden", command=lambda: self._handle_intent(UiIntent.TOGGLE_DOCUMENTATION), bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="⚲", shortcut="Ctrl+Alt+S", label="Sichtbare Symbole im Grid filtern", command=self.open_grid_symbol_filter_dialog, bind_editor_return=True, padx=(8, 0))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="−", shortcut="Ctrl+-", label="Ansicht herauszoomen", command=lambda: self._handle_intent(UiIntent.ZOOM_OUT), side="right", bind_editor_return=True, padx=(0, 8))
        self._create_toolbar_shortcut_button(self.editor_topbar, icon="+", shortcut="Ctrl++", label="Ansicht hineinzoomen", command=lambda: self._handle_intent(UiIntent.ZOOM_IN), side="right", bind_editor_return=True, padx=(0, 0))

        self.plan_name_var = ui.StringVar(value="")
        tui.Label(self.editor_topbar, textvariable=self.plan_name_var).pack(side="right", padx=(0, 14))

    def _build_canvas_panel_widgets(self) -> None:
        """Erstellt Canvas, Scrollbars und den Grid-Stack des Editorbereichs."""
        self.grid_stack = tui.Frame(self.editor_view)
        self.grid_container = tui.Frame(self.grid_stack)

        self.canvas = ui.Canvas(self.grid_container, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.y_scroll = ui.Scrollbar(self.grid_container, orient="vertical", command=self._yview, highlightthickness=0, borderwidth=0, relief="flat", takefocus=0)
        self.y_scroll.pack(side="right", fill="y")
        self.x_scroll = ui.Scrollbar(self.grid_stack, orient="horizontal", command=self._xview, highlightthickness=0, borderwidth=0, relief="flat", takefocus=0)
        self.x_scroll.pack(fill="x")

        self.canvas.configure(
            xscrollcommand=lambda a, b: self._on_canvas_xscroll(a, b),
            yscrollcommand=lambda a, b: self._on_canvas_yscroll(a, b),
        )
        self._update_scroll_region()
