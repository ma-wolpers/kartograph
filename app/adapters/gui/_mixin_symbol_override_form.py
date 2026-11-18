"""Formular „Für diesen Plan anpassen“: lokaler Name und Kompetenzen eines programmweiten Symbols.

Aus der Symbol-Verwaltung des Plans geöffnet. Vorbelegt mit den Werten, die
im Plan gerade gelten; „Programmstandard verwenden“ entfernt die Anpassung.
Geprüft wird vor dem Dispatch mit dem reinen Usecase
``symbol_override_usecases.set_symbol_override`` (ohne Seiteneffekt); die
Änderung selbst läuft über ``SetSymbolOverrideIntent`` und lässt sich mit
Strg+Z zurücknehmen. Die Diagnose bleibt unter dem Symbolschlüssel gespeichert.
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, ESCAPE, bind_action, dialog_keys
from app.adapters.gui._symbol_form_widgets import FORM_HINT_WRAP, build_competence_picker
from app.core.domain.catalog_validation import CatalogValidationError
from app.core.intents.custom_symbol_intents import SetSymbolOverrideIntent
from app.core.usecases.v4.symbol_override_usecases import set_symbol_override
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui


class SymbolOverrideFormMixin:
    """Mixin: Plan-Anpassung eines programmweiten Symbols."""

    def _open_symbol_override_form(self, key: str) -> None:
        """Öffnet das Formular für das Katalogsymbol *key* im offenen Plan.

        Args:
            key: Schlüssel des Katalogsymbols.
        """
        state = self._controller.state
        program = next((d for d in state.symbol_catalog if d.key == key), None)
        if program is None or self.current_plan is None:
            return
        effective = self._symbol_by_meaning.get(key, program)
        dialog = self._create_overlay_dialog(f"{program.glyph} Für diesen Plan anpassen", "480x560",
                                             parent=self._symbol_management_window)
        frame = tui.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        tui.Label(frame, text=f"Programmstandard: „{program.name}“ · gilt nur für diesen Plan",
                  style="Muted.TLabel", wraplength=FORM_HINT_WRAP, justify="left").pack(anchor="w", pady=(0, 6))
        name_var = ui.StringVar(value=effective.name)
        row = tui.Frame(frame)
        row.pack(fill="x")
        tui.Label(row, text="Name im Plan").pack(side="left")
        name_entry = tui.Entry(row, textvariable=name_var, width=32)
        name_entry.pack(side="left", padx=(6, 0))
        picker = None
        if program.role == "diagnostic":
            picker = build_competence_picker(frame, state.competence_catalog, effective.competence_ids)
        status_var = ui.StringVar(value="")
        tui.Label(frame, textvariable=status_var, style="Error.TLabel", wraplength=FORM_HINT_WRAP,
                  justify="left").pack(anchor="w", pady=(8, 0))

        def apply(name: str | None, ids: tuple[str, ...] | None) -> None:
            try:
                set_symbol_override(self.current_plan, state.symbol_catalog, state.competence_catalog, key, name, ids)
            except CatalogValidationError as exc:
                status_var.set(str(exc))
                return
            self._controller.dispatch(SetSymbolOverrideIntent(symbol_key=key, name=name, competence_ids=ids))
            dialog.destroy()
            self._refresh_symbol_management_table()

        def submit() -> None:
            apply(name_var.get(), picker.selected_values() if picker is not None else None)

        bind_action(dialog_keys(dialog), ENTER, submit, binding_id="dialog.confirm")
        buttons = tui.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        reset = tui.Button(buttons, text="Programmstandard verwenden", command=lambda: apply(None, None))
        reset.pack(side="left")
        self._attach_hover_help(reset, label="Anpassung in diesem Plan entfernen", shortcut=None)
        cancel = tui.Button(buttons, text="Abbrechen", command=dialog.destroy)
        cancel.pack(side="right")
        self._attach_hover_help(cancel, label="Ohne Speichern schließen", shortcut=ESCAPE)
        save = tui.Button(buttons, text="Speichern", command=submit)
        save.pack(side="right", padx=(0, 8))
        self._attach_hover_help(save, label="Für diesen Plan speichern (rückgängig machbar)", shortcut=ENTER)
        self._focus_overlay_widget(dialog, name_entry)
