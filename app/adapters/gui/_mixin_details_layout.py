"""Details-Panel-Layout-Mixin für das Kartograph-Hauptfenster.

Erstellt alle Widgets des Details-Containers (Statusleiste, Symbol-Shortcuts-Bar,
Namensformular, Symbols/Farb-Frames, Notizen) und befüllt die Symbol-Shortcuts-Bar.
Unter der Kopfzeile liegt alles in einem bw-gui ``ScrollableFrame``; Kürzel-Leiste
und Namenszeile sind ``FlowFrame``s, die bei schmalem Panel umbrechen -- so bleibt
jedes Detail erreichbar, egal wie viele Symbole und Legenden Platz brauchen.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, ESCAPE, widget_keys
from app.adapters.gui._pending_field_save import PendingFieldSave
from app.core.domain.permanent_absence import PERMANENT_ABSENCE_LABEL
from app.core.domain.student_notes import NOTES_LABEL
from app.core.domain.symbol_legend import symbol_summary
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import on_focus_change, on_resize, on_text_modified, ui, widgets as tui
from bw_gui.widgets import FlowFrame, ScrollableFrame, Switch, WrappedTextField


class DetailsLayoutMixin:
    """Mixin: Widget-Konstruktion für das Details-Panel und die Symbol-Shortcuts-Leiste."""

    def _build_details_container_widgets(self) -> None:
        """Erstellt alle Widgets des Details-Containers.

        Legt ``details_container``, ``details_header``, ``_symbol_shortcuts_bar``,
        ``details_frame``, ``details_form``, ``name_entry``, ``last_name_entry`` sowie
        die Rahmen für Symbole, Farbpunkte und Notizen (``notes_field``)
        an. Ruft anschließend ``_apply_details_overlay_position`` auf, um die initiale
        Platzierung zu setzen.
        """
        self.details_container = tui.Frame(self.editor_view, style="Panel.TFrame")

        self.details_header = tui.Frame(self.details_container, style="Panel.TFrame")
        self.details_header.pack(fill="x", padx=12, pady=(8, 0))

        tui.Label(self.details_header, textvariable=self.status_var, style="Panel.TLabel").pack(side="left")
        tui.Label(self.details_header, textvariable=self._selected_marker_var, style="Panel.TLabel").pack(side="right")

        # Alles unter der Kopfzeile scrollt (bw-gui-Standard für Bereiche, die über die
        # verfügbare Höhe wachsen können): viele Symbole/Farben mit Legenden verdrängen
        # sonst die Notizen. Unten angedockt begrenzt _apply_details_overlay_position die Höhe.
        self._details_wrap_width = 500  # bis zur ersten Größenmeldung (s. _rewrap_detail_legends)
        self._details_height_cap: int | None = None  # s. _update_details_height_cap
        self.details_scroll = ScrollableFrame(self.details_container, style="Panel.TFrame")
        self.details_scroll.pack(fill="both", expand=True)
        body = self.details_scroll.content
        on_resize(body, lambda event: self._rewrap_detail_legends(event.width))

        # Badges brechen um statt rechts abgeschnitten zu werden (seitlich nur 560 px breit).
        self._symbol_shortcuts_bar = FlowFrame(body, style="Panel.TFrame", gap_x=10, gap_y=2)
        self._symbol_shortcuts_bar.pack(fill="x", padx=12, pady=(3, 2))
        self._build_symbol_shortcuts_bar()

        self.details_frame = tui.Frame(body)
        self.details_frame.pack(fill="x", padx=12, pady=(4, 12))

        self.details_form = FlowFrame(self.details_frame, style="Panel.TFrame", gap_x=16, gap_y=4)
        self.details_form.pack(fill="x", pady=(4, 0))

        # Änderungserkennung über trace_add auf den StringVars statt <KeyRelease>:
        # deckt Tippen, Paste und Kontextmenü einheitlich ab, da alle Eingabewege
        # am Ende über die Variable laufen (<KeyRelease> reagiert nicht auf Paste
        # per Kontextmenü/Maus). Das programmatische Befüllen in _load_detail_fields()
        # läuft in PendingFieldSave.suspended() und zählt daher nicht als Eingabe.
        self._name_var.trace_add("write", lambda *_args: self._name_pending_save.note_change())
        self._last_name_var.trace_add("write", lambda *_args: self._name_pending_save.note_change())
        self._nickname_var.trace_add("write", lambda *_args: self._name_pending_save.note_change())

        self.name_entry = self._add_name_field("Vorname", self._name_var)
        self.last_name_entry = self._add_name_field("Nachname", self._last_name_var)
        self.nickname_entry = self._add_name_field("Spitzname", self._nickname_var)

        # Geleerter Name einer Person mit Daten: eigener Halte-Slot mit eigener Frist
        # (s. _apply_name_fields); in _pending_edits, damit ihn Fensterschluss/Planwechsel
        # ausführen bzw. das Zerstören des Fensters seinen Timer abbricht.
        self._name_clear_hold = PendingFieldSave(
            self, apply=self._apply_name_clear,
            delay_seconds=lambda: self._controller.state.settings.name_clear_delay,
        )
        self._pending_edits.append(self._name_clear_hold)
        self._name_clear_warning = tui.Label(self.details_frame, style="Error.TLabel", wraplength=480, justify="left")

        # Schalter und Bearbeiten-Menü laufen über dieselbe Aktion (set_selected_permanent_absence).
        # Switch statt Checkbox: die Markierung wirkt sofort (bw-gui TOGGLE_CONTRACT); programmatisches
        # Setzen in _load_detail_fields löst on_change nicht aus.
        self._absent_var = ui.BooleanVar(master=self, value=False)
        self.absent_switch = Switch(
            self.details_frame, text=PERMANENT_ABSENCE_LABEL, variable=self._absent_var,
            on_change=self.set_selected_permanent_absence,
        )
        self.absent_switch.pack(anchor="w", pady=(6, 0))

        self.symbols_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.symbols_frame.pack(fill="x", pady=(6, 0))

        self.symbol_legend_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.symbol_legend_frame.pack(fill="x", pady=(4, 0))

        self.colors_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.colors_frame.pack(fill="x", pady=(6, 0))

        self.color_legend_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.color_legend_frame.pack(fill="x", pady=(4, 0))

        self.notes_frame = tui.Frame(self.details_frame, style="Panel.TFrame")
        self.notes_frame.pack(fill="x", pady=(6, 0))
        tui.Label(self.notes_frame, text=NOTES_LABEL, style="Panel.TLabel").pack(anchor="w")
        self.notes_field = WrappedTextField(self.notes_frame, height=3)
        self.notes_field.pack(fill="x")
        # Inhaltsaenderung statt Tastenloslassen: deckt auch Paste/Kontextmenue ab
        # (bw-gui on_text_modified prueft und setzt Tks Modified-Flag selbst zurueck).
        on_text_modified(self.notes_field.text, lambda _text: self._on_notes_text_modified())
        on_focus_change(
            self.notes_field.text,
            on_gained=lambda _change: self.details_scroll.see_widget(self.notes_frame),
            on_lost=lambda _change: self._commit_pending_edits(),
        )

        self._details_panel_visible = True
        self._details_loaded_student_id = None  # Felder zeigen noch niemanden (s. _field_needs_reload)

        on_resize(self.editor_view, lambda _event: self._update_details_height_cap())
        self._apply_details_overlay_position()

    def _add_name_field(self, label: str, variable) -> object:
        """Legt ein Namens-Paar (Beschriftung + Eingabefeld) als Element der Namenszeile an.

        Die Namenszeile ist ein bw-gui ``FlowFrame``: Ist das Panel zu schmal für
        alle drei Paare, rutscht das nächste Paar in die nächste Zeile.

        Args:
            label: Beschriftung ("Vorname", "Nachname", "Spitzname").
            variable: ``StringVar`` des Feldes.

        Returns:
            Das Eingabefeld (Fokusverlust speichert, Enter/Escape verlassen den Editor).
        """
        pair = self.details_form.add(tui.Frame(self.details_form, style="Panel.TFrame"))
        tui.Label(pair, text=label, style="Panel.TLabel").pack(side="left")
        entry = tui.Entry(pair, textvariable=variable, width=20)
        entry.pack(side="left", padx=(8, 0))
        on_focus_change(entry, on_lost=lambda _change: self._on_name_field_focus_out())
        self._bind_name_entry_keys(entry)
        return entry

    def _build_symbol_shortcuts_bar(self) -> None:
        """Befüllt die Symbol-Shortcuts-Leiste im Details-Panel neu.

        Zeigt alle Symbole mit definiertem Shortcut als Badge-Labels an.
        Diagnostische Symbole kommen zuerst; Doku-Only-Symbole werden mit
        dem Grad-Suffix ``°`` gekennzeichnet und durch ``|`` abgetrennt.
        Die Leiste ist ein ``FlowFrame``: Badges brechen bei Platzmangel um.
        """
        bar = self._symbol_shortcuts_bar
        bar.clear()

        symbols_with_shortcuts = [item for item in self.symbol_definitions if item.shortcut is not None]
        if not symbols_with_shortcuts:
            return

        bar.add(tui.Label(bar, text="Symbole:", style="Panel.TLabel"))
        diagnostic = [s for s in symbols_with_shortcuts if s.role == "diagnostic"]
        doc_only = [s for s in symbols_with_shortcuts if s.role != "diagnostic"]

        for item in diagnostic:
            key = item.shortcut.upper()
            badge = bar.add(tui.Label(bar, text=f"{item.glyph} {key}", style="Panel.TLabel"))
            self._attach_hover_help(badge, label=symbol_summary(item, self.competences_by_id), shortcut=key)

        if doc_only:
            bar.add(tui.Label(bar, text="|", style="Panel.TLabel"))
            for item in doc_only:
                key = item.shortcut.upper()
                badge = bar.add(tui.Label(bar, text=f"{item.glyph} {key}°", style="Panel.TLabel"))
                self._attach_hover_help(badge, label=f"(nur Doku) {symbol_summary(item, self.competences_by_id)}", shortcut=key)

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
