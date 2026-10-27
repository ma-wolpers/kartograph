"""Einstellungsdialog der Sitzplan-Live-Vorschau.

Reduziertes Gegenstück zum PDF-Export-Dialog (``_mixin_pdf.py``): keine
Noten, Symbole oder Legende, dafür Ansicht, Auswahl einzelner Farben (nur
im Plan vergebene) und Farbstaffelung. Ist schon eine Vorschau offen, ist
der Dialog genau mit deren Einstellungen vorbelegt, und Bestätigen
aktualisiert diese Vorschau, statt eine zweite zu öffnen
(``SitzplanPopupMixin._apply_sitzplan_preview_options``).
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, bind_action, dialog_keys
from app.core.domain.color_order import palette_shortcut_by_key
from app.core.domain.preview_color_frames import PreviewOptions, selectable_color_keys
from app.core.usecases.v4.color_usecases import used_color_tags
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.runtime import widgets as tui
from bw_gui.widgets import Checkbox


class SitzplanPreviewDialogMixin:
    """Mixin: Einstellungsdialog vor dem Öffnen bzw. Aktualisieren der Sitzplan-Vorschau."""

    def open_sitzplan_popup(self) -> None:
        """Öffnet den Vorschau-Dialog (Menü "Sitzplan-Vorschau oeffnen").

        Vorbelegung: die Einstellungen der offenen Vorschau, sonst
        ``PreviewOptions()`` (Lehrertisch oben, keine Farben, Staffelung an).
        Von früher gewählten Farben bleiben nur die angehakt, die im Plan
        noch vergeben sind. Neu vergebene sind zunächst abgewählt.
        """
        popup = self._live_sitzplan_popup()
        current = popup.options if popup is not None else PreviewOptions()
        plan = self.current_plan
        selectable = selectable_color_keys(used_color_tags(plan), self._color_order) if plan else []

        dialog = self._create_overlay_dialog("Sitzplan-Vorschau", "440x600")
        container = tui.Frame(dialog)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        orientation_var = ui.StringVar(value=current.orientation)
        first_button = self._build_orientation_radios(container, orientation_var)
        color_vars = self._build_preview_color_section(container, selectable, current.selected_colors)
        staggered_var = ui.BooleanVar(value=current.staggered)
        Checkbox(
            container, text="Farbstaffelung (mehrere Farben als Rahmen, Farbe 1 ganz innen)",
            variable=staggered_var,
        ).pack(anchor="w", pady=(6, 0))
        self._focus_overlay_widget(dialog, first_button)

        def confirm() -> None:
            options = PreviewOptions(
                orientation=orientation_var.get(),
                selected_colors=frozenset(key for key, var in color_vars.items() if var.get()),
                staggered=staggered_var.get(),
            )
            dialog.destroy()
            self._apply_sitzplan_preview_options(options)

        bind_action(dialog_keys(dialog), ENTER, confirm, binding_id="dialog.confirm")
        self._build_preview_dialog_buttons(container, dialog, confirm, updates_open_preview=popup is not None)

    def _build_preview_color_section(
        self, container: ui.Widget, selectable: list[str], preselected: frozenset[str]
    ) -> dict[str, ui.BooleanVar]:
        """Baut die Farbauswahl: eine Checkbox je vergebener Farbe, dazu "Alle"/"Keine".

        Beschriftung ``"<Nummer>  <Name>"`` aus der Palette (Tastenkürzel und
        Label); es gibt keine eigene Farbzuordnung im Dialog.

        Args:
            container: Eltern-Widget.
            selectable: Wählbare Farbschlüssel in Palettenreihenfolge.
            preselected: Bisher gewählte Farbschlüssel.

        Returns:
            ``color_key -> BooleanVar`` für alle angebotenen Farben (leer, wenn keine vergeben sind).
        """
        tui.Label(container, text="Farben als Tischrahmen (nur im Plan vergebene)").pack(anchor="w", pady=(0, 6))
        if not selectable:
            tui.Label(container, text="Im Plan sind aktuell keine Farben vergeben.").pack(anchor="w", pady=(0, 8))
            return {}
        shortcut_by_key = palette_shortcut_by_key(self.color_palette)
        color_vars: dict[str, ui.BooleanVar] = {}
        for color_key in selectable:
            label, _hex_color = self._color_by_key[color_key]
            var = ui.BooleanVar(value=color_key in preselected)
            color_vars[color_key] = var
            Checkbox(container, text=f"{shortcut_by_key[color_key]}  {label}", variable=var).pack(anchor="w", pady=(0, 2))
        row = tui.Frame(container)
        row.pack(fill="x", pady=(4, 8))
        all_button = tui.Button(row, text="Alle Farben", command=lambda: [v.set(True) for v in color_vars.values()])
        all_button.pack(side="left")
        self._attach_hover_help(all_button, label="Alle vergebenen Farben als Rahmen zeigen", shortcut=None)
        none_button = tui.Button(row, text="Keine Farben", command=lambda: [v.set(False) for v in color_vars.values()])
        none_button.pack(side="left", padx=(6, 0))
        self._attach_hover_help(none_button, label="Alle Farbauswahlen deaktivieren", shortcut=None)
        return color_vars

    def _build_preview_dialog_buttons(self, container: ui.Widget, dialog: ui.Toplevel, confirm, *, updates_open_preview: bool) -> None:
        """Baut die Buttonzeile "Abbrechen" / "Vorschau öffnen" bzw. "Übernehmen".

        Args:
            container: Eltern-Widget.
            dialog: Der Dialog (für "Abbrechen").
            confirm: Bestätigungs-Callback.
            updates_open_preview: True, wenn eine Vorschau offen ist (Button heißt dann "Übernehmen").
        """
        button_row = tui.Frame(container)
        button_row.pack(fill="x", pady=(12, 0))
        cancel_button = tui.Button(button_row, text="Abbrechen", command=dialog.destroy)
        cancel_button.pack(side="right")
        self._attach_hover_help(cancel_button, label="Dialog ohne Änderung schließen", shortcut="Esc")
        confirm_text = "Übernehmen" if updates_open_preview else "Vorschau öffnen"
        confirm_help = "Offene Vorschau mit diesen Einstellungen aktualisieren" if updates_open_preview else "Sitzplan-Vorschau mit diesen Einstellungen öffnen"
        confirm_button = tui.Button(button_row, text=confirm_text, command=confirm)
        confirm_button.pack(side="right", padx=(0, 8))
        self._attach_hover_help(confirm_button, label=confirm_help, shortcut="Enter")
