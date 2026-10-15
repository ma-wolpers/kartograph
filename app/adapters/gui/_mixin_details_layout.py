"""Details-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Erstellt alle Widgets des Details-Containers (Statusleiste, Symbol-Shortcuts-Bar,
Namensformular, Symbols/Farb-Frames) und befüllt die Symbol-Shortcuts-Bar.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, ESCAPE, widget_keys
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import on_focus_change, on_text_modified, widgets as tui
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

        # Änderungserkennung über trace_add auf den StringVars statt <KeyRelease>:
        # deckt Tippen, Paste und Kontextmenü einheitlich ab, da alle Eingabewege
        # am Ende über die Variable laufen (<KeyRelease> reagiert nicht auf Paste
        # per Kontextmenü/Maus). Feuert auch beim programmatischen Neubefüllen in
        # _refresh_details_panel() -- harmlos, s. _apply_name_fields().
        self._name_var.trace_add("write", lambda *_args: self._name_pending_save.note_change())
        self._last_name_var.trace_add("write", lambda *_args: self._name_pending_save.note_change())
        self._nickname_var.trace_add("write", lambda *_args: self._name_pending_save.note_change())

        tui.Label(self.details_form, text="Vorname", style="Panel.TLabel").pack(side="left")
        self.name_entry = tui.Entry(self.details_form, textvariable=self._name_var, width=20)
        self.name_entry.pack(side="left", padx=(8, 16))
        on_focus_change(self.name_entry, on_lost=lambda _change: self._on_name_field_focus_out())
        self._bind_name_entry_keys(self.name_entry)

        tui.Label(self.details_form, text="Nachname", style="Panel.TLabel").pack(side="left")
        self.last_name_entry = tui.Entry(self.details_form, textvariable=self._last_name_var, width=20)
        self.last_name_entry.pack(side="left", padx=(8, 16))
        on_focus_change(self.last_name_entry, on_lost=lambda _change: self._on_name_field_focus_out())
        self._bind_name_entry_keys(self.last_name_entry)

        tui.Label(self.details_form, text="Spitzname", style="Panel.TLabel").pack(side="left")
        self.nickname_entry = tui.Entry(self.details_form, textvariable=self._nickname_var, width=20)
        self.nickname_entry.pack(side="left", padx=(8, 0))
        on_focus_change(self.nickname_entry, on_lost=lambda _change: self._on_name_field_focus_out())
        self._bind_name_entry_keys(self.nickname_entry)

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
        # Inhaltsaenderung statt Tastenloslassen: deckt auch Paste/Kontextmenue ab
        # (bw-gui on_text_modified prueft und setzt Tks Modified-Flag selbst zurueck).
        on_text_modified(self.accommodations_field.text, lambda _text: self._on_accommodations_text_modified())
        on_focus_change(self.accommodations_field.text, on_lost=lambda _change: self._commit_pending_edits())

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

    def _bind_name_entry_keys(self, entry) -> None:
        """Escape und Enter in einem Namensfeld verlassen den Namenseditor-Modus.

        Widget-lokal (``WidgetShortcutBinder``), aktiv trotz Texteingabe-Fokus --
        das Feld selbst ist die Texteingabe.

        Args:
            entry: Vor-, Nach- oder Spitznamenfeld.
        """
        keys = widget_keys(entry)
        keys.bind(ESCAPE, self._on_name_entry_escape, binding_id="name.escape", intent="name.escape", allow_when_text_input=True)
        keys.bind(ENTER, self._on_name_entry_return, binding_id="name.return", intent="name.return", allow_when_text_input=True)
