"""Formular „Symbol (alle Pläne)“: ein Katalogsymbol bearbeiten oder neu anlegen.

Bearbeiten: Name, Taste, aktiv, Standard-Kompetenzen (nur Diagnosesymbole).
Anlegen: zusätzlich das Zeichen aus der kuratierten Palette (nur freie Zeichen).
Geprüft wird vor dem Dispatch mit dem reinen Usecase selbst
(``catalog_usecases.update_symbol``/``add_symbol``, ohne Seiteneffekt) — der
Controller fängt Handler-Fehler ab, die Meldung muss also hier entstehen.
Verdrängt eine Taste ein eigenes Symbol des offenen Plans, sagt das die
Statuszeile nach dem Speichern (kein Verbot).
"""

from __future__ import annotations

from app.adapters.gui._local_keys import ENTER, ESCAPE, bind_action, dialog_keys
from app.adapters.gui._mixin_catalog_dialog import _shortcut_label
from app.adapters.gui._symbol_form_widgets import FORM_HINT_WRAP, build_competence_picker
from app.core.domain.catalog_validation import CatalogValidationError, custom_shortcut_conflicts
from app.core.domain.submission_status import is_required_symbol
from app.core.domain.symbol_glyph_palette import GLYPH_PALETTE
from app.core.intents.catalog_intents import AddCatalogSymbolIntent, UpdateCatalogSymbolIntent
from app.core.usecases.catalog_usecases import add_symbol, update_symbol
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui
from bw_gui.widgets import Checkbox, RadioGroup, ScrollableFrame

GLYPH_PICKER_HEIGHT = 150
"""Höhe der Zeichenauswahl beim Anlegen (px); darüber scrollt sie."""


class CatalogSymbolFormMixin:
    """Mixin: Formular für ein programmweites Symbol."""

    def _open_catalog_symbol_form(self, key: str | None) -> None:
        """Öffnet das Formular zum Bearbeiten (*key*) oder Anlegen (``None``).

        Args:
            key: Schlüssel des Katalogsymbols oder ``None`` für ein neues Diagnosesymbol.
        """
        state = self._controller.state
        current = next((d for d in state.symbol_catalog if d.key == key), None)
        title = f"Symbol „{current.name}“ (alle Pläne)" if current else "Neues Symbol (alle Pläne)"
        dialog = self._create_overlay_dialog(title, "480x640", parent=self._catalog_window)
        frame = tui.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)

        glyph_var = ui.StringVar(value="")
        if current is None:
            used = {d.glyph for d in state.symbol_catalog}
            options = [(cp, f"{chr(int(cp, 16))}  {label}") for cp, label in GLYPH_PALETTE if chr(int(cp, 16)) not in used]
            tui.Label(frame, text="Zeichen").pack(anchor="w")
            scroll = ScrollableFrame(frame)
            scroll.pack(fill="x", pady=(2, 8))
            RadioGroup(scroll.content, options=options, variable=glyph_var).pack(anchor="w")
            scroll.set_height_cap(GLYPH_PICKER_HEIGHT)

        name_var = ui.StringVar(value=current.name if current else "")
        shortcut_var = ui.StringVar(value=_shortcut_label(current.shortcut) if current else "")
        row = tui.Frame(frame)
        row.pack(fill="x")
        tui.Label(row, text="Name").pack(side="left")
        name_entry = tui.Entry(row, textvariable=name_var, width=30)
        name_entry.pack(side="left", padx=(6, 12))
        tui.Label(row, text="Taste").pack(side="left")
        tui.Entry(row, textvariable=shortcut_var, width=10).pack(side="left", padx=(6, 0))

        active_var = ui.BooleanVar(value=current.active if current else True)
        if current is not None:
            box = Checkbox(frame, text="aktiv (in allen Plänen setzbar)", variable=active_var)
            box.pack(anchor="w", pady=(8, 0))
            if is_required_symbol(current):
                box.state(["disabled"])

        picker = None
        if current is None or current.role == "diagnostic":
            picker = build_competence_picker(frame, state.competence_catalog, current.competence_ids if current else ())

        status_var = ui.StringVar(value="")
        tui.Label(frame, textvariable=status_var, style="Error.TLabel", wraplength=FORM_HINT_WRAP,
                  justify="left").pack(anchor="w", pady=(8, 0))

        def submit() -> None:
            ids = picker.selected_values() if picker is not None else ()
            try:
                if current is None:
                    add_symbol(state.symbol_catalog, state.competence_catalog, name_var.get(), glyph_var.get(),
                               shortcut_var.get(), ids)
                    intent = AddCatalogSymbolIntent(name_var.get(), glyph_var.get(), shortcut_var.get(), ids)
                else:
                    update_symbol(state.symbol_catalog, state.competence_catalog, current.key, name_var.get(),
                                  shortcut_var.get(), active_var.get(), ids)
                    intent = UpdateCatalogSymbolIntent(current.key, name_var.get(), shortcut_var.get(),
                                                       active_var.get(), ids)
            except CatalogValidationError as exc:
                status_var.set(str(exc))
                return
            self._controller.dispatch(intent)
            dialog.destroy()
            self._refresh_catalog_tables()
            self._report_displaced_custom_symbols(shortcut_var.get())

        bind_action(dialog_keys(dialog), ENTER, submit, binding_id="dialog.confirm")
        buttons = tui.Frame(frame)
        buttons.pack(fill="x", pady=(10, 0))
        cancel = tui.Button(buttons, text="Abbrechen", command=dialog.destroy)
        cancel.pack(side="right")
        self._attach_hover_help(cancel, label="Ohne Speichern schließen", shortcut=ESCAPE)
        save = tui.Button(buttons, text="Speichern", command=submit)
        save.pack(side="right", padx=(0, 8))
        self._attach_hover_help(save, label="Für alle Pläne speichern", shortcut=ENTER)
        self._focus_overlay_widget(dialog, name_entry)

    def _report_displaced_custom_symbols(self, shortcut: str) -> None:
        """Meldet eigene Symbole des offenen Plans, deren Taste jetzt ein Katalogsymbol belegt.

        Args:
            shortcut: Eben gespeicherte Taste (roh).
        """
        if not self.current_plan:
            return
        displaced = custom_shortcut_conflicts(shortcut.strip().lower() or None, self.current_plan.custom_symbols)
        if displaced:
            self.status_var.set("Taste jetzt belegt für eigene Symbole: " + ", ".join(displaced)
                                + " – in der Symbol-Verwaltung neu vergeben")
