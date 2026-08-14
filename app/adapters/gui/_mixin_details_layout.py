"""Details-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Erstellt alle Widgets des Details-Containers (Statusleiste, Symbol-Shortcuts-Bar,
Namensformular, Symbols/Farb-Frames) und befüllt die Symbol-Shortcuts-Bar.
"""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import WrappedTextField


class DetailsLayoutMixin:
    """Mixin: Widget-Konstruktion für das Details-Panel und die Symbol-Shortcuts-Leiste."""

    def _build_details_container_widgets(self) -> None:
        """Erstellt alle Widgets des Details-Containers.

        Legt ``details_container``, ``details_header``, ``_symbol_shortcuts_bar``,
        ``details_frame``, ``details_form``, ``name_entry``, ``last_name_entry`` sowie
        die Rahmen für Symbole, Farbpunkte und Nachteilsausgleiche (``accommodations_field``)
        an. Ruft anschließend ``_apply_details_overlay_position`` auf, um die initiale
        Platzierung zu setzen.
        """
        self.details_container = tui.Frame(self.editor_view, style="Panel.TFrame")

        self.details_header = tui.Frame(self.details_container, style="Panel.TFrame")
        self.details_header.pack(fill="x", padx=12, pady=(8, 0))

        tui.Label(self.details_header, textvariable=self.status_var, style="Panel.TLabel").pack(side="left")
        tui.Label(self.details_header, textvariable=self._selected_marker_var, style="Panel.TLabel").pack(side="right")

        self._symbol_shortcuts_bar = tui.Frame(self.details_container, style="Panel.TFrame")
        self._symbol_shortcuts_bar.pack(fill="x", padx=12, pady=(3, 2))
        self._build_symbol_shortcuts_bar()

        self.details_frame = tui.Frame(self.details_container)
        self.details_frame.pack(fill="x", padx=12, pady=(4, 12))

        self.details_form = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.details_form.pack(fill="x", pady=(4, 0))

        tui.Label(self.details_form, text="Vorname", style="Panel.TLabel").pack(side="left")
        self.name_entry = tui.Entry(self.details_form, textvariable=self._name_var, width=20)
        self.name_entry.pack(side="left", padx=(8, 16))
        self.name_entry.bind("<KeyRelease>", lambda _event: self._on_name_changed())
        self.name_entry.bind("<Escape>", self._on_name_entry_escape)
        self.name_entry.bind("<Return>", self._on_name_entry_return)

        tui.Label(self.details_form, text="Nachname", style="Panel.TLabel").pack(side="left")
        self.last_name_entry = tui.Entry(self.details_form, textvariable=self._last_name_var, width=20)
        self.last_name_entry.pack(side="left", padx=(8, 16))
        self.last_name_entry.bind("<KeyRelease>", lambda _event: self._on_last_name_changed())
        self.last_name_entry.bind("<Escape>", self._on_name_entry_escape)
        self.last_name_entry.bind("<Return>", self._on_name_entry_return)

        tui.Label(self.details_form, text="Spitzname", style="Panel.TLabel").pack(side="left")
        self.nickname_entry = tui.Entry(self.details_form, textvariable=self._nickname_var, width=20)
        self.nickname_entry.pack(side="left", padx=(8, 0))
        self.nickname_entry.bind("<KeyRelease>", lambda _event: self._on_nickname_changed())
        self.nickname_entry.bind("<Escape>", self._on_name_entry_escape)
        self.nickname_entry.bind("<Return>", self._on_name_entry_return)

        self.symbols_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.symbols_frame.pack(fill="x", pady=(6, 0))

        self.symbol_legend_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.symbol_legend_frame.pack(fill="x", pady=(4, 0))

        self.colors_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.colors_frame.pack(fill="x", pady=(6, 0))

        self.color_legend_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.color_legend_frame.pack(fill="x", pady=(4, 0))

        self.accommodations_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.accommodations_frame.pack(fill="x", pady=(6, 0))
        tui.Label(self.accommodations_frame, text="Nachteilsausgleiche", style="Panel.TLabel").pack(anchor="w")
        self.accommodations_field = WrappedTextField(self.accommodations_frame, height=3)
        self.accommodations_field.pack(fill="x")
        self.accommodations_field.bind("<FocusOut>", lambda _event: self._on_accommodations_changed())

        self._details_panel_visible = True

        self._apply_details_overlay_position()

    def _build_symbol_shortcuts_bar(self) -> None:
        """Befüllt die Symbol-Shortcuts-Leiste im Details-Panel neu.

        Zeigt alle Symbole mit definiertem Shortcut als Badge-Labels an.
        Diagnostische Symbole kommen zuerst; Doku-Only-Symbole werden mit
        dem Grad-Suffix ``°`` gekennzeichnet und durch ``|`` abgetrennt.
        """
        for child in self._symbol_shortcuts_bar.winfo_children():
            child.destroy()

        symbols_with_shortcuts = [item for item in self.symbol_definitions if item.shortcut is not None]
        if not symbols_with_shortcuts:
            return

        tui.Label(
            self._symbol_shortcuts_bar,
            text="Symbole:",
            style="Panel.TLabel",
        ).pack(side="left", padx=(0, 8))

        diagnostic = [s for s in symbols_with_shortcuts if s.role == "diagnostic"]
        doc_only = [s for s in symbols_with_shortcuts if s.role != "diagnostic"]

        for item in diagnostic:
            key = item.shortcut.upper()
            badge = tui.Label(
                self._symbol_shortcuts_bar,
                text=f"{item.glyph} {key}",
                style="Panel.TLabel",
            )
            badge.pack(side="left", padx=(0, 10))
            self._attach_hover_help(badge, label=f"{item.meaning} – {item.legend_one}", shortcut=key)

        if doc_only:
            tui.Label(
                self._symbol_shortcuts_bar,
                text=" |",
                style="Panel.TLabel",
            ).pack(side="left", padx=(0, 8))
            for item in doc_only:
                key = item.shortcut.upper()
                badge = tui.Label(
                    self._symbol_shortcuts_bar,
                    text=f"{item.glyph} {key}°",
                    style="Panel.TLabel",
                )
                badge.pack(side="left", padx=(0, 10))
                self._attach_hover_help(
                    badge,
                    label=f"{item.meaning} (nur Doku) – {item.legend_one}",
                    shortcut=key,
                )
