"""Add/Edit-Formular für eigene Doku-Symbole (Symbol-Verwaltung-Popup).

Getrennt von ``_mixin_symbol_management.py`` (Listenansicht), damit keine
der beiden Dateien über das 300-Zeilen-Richtmaß wächst.
"""

from __future__ import annotations

from app.core.domain.custom_symbol_validation import (
    CustomSymbolValidationError,
    validate_custom_symbol_glyph,
    validate_custom_symbol_meaning,
    validate_custom_symbol_shortcut,
)
from app.core.intents.custom_symbol_intents import AddCustomSymbolIntent, UpdateCustomSymbolIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui


class SymbolManagementFormMixin:
    """Mixin: Add/Edit-Formular-Dialog für eigene Doku-Symbole."""

    def _new_custom_symbol_dialog(self) -> None:
        """Öffnet das Formular zum Anlegen eines neuen eigenen Doku-Symbols."""
        if not self.current_plan or not self.current_plan_path:
            self.status_var.set("Kein Plan geöffnet")
            return
        self._open_custom_symbol_form(symbol_id=None, glyph="", meaning="", shortcut="")

    def _edit_selected_custom_symbol_dialog(self) -> None:
        """Öffnet das Formular zum Bearbeiten des in der Symbol-Verwaltung ausgewählten eigenen Symbols."""
        symbol_id = self._selected_custom_symbol_id()
        if symbol_id is None or not self.current_plan:
            return
        symbol = self.current_plan.custom_symbols.get(symbol_id)
        if symbol is None:
            return
        self._open_custom_symbol_form(
            symbol_id=symbol_id, glyph=symbol.glyph, meaning=symbol.meaning, shortcut=symbol.shortcut
        )

    def _open_custom_symbol_form(
        self, *, symbol_id: str | None, glyph: str, meaning: str, shortcut: str
    ) -> None:
        """Baut den Add/Edit-Formular-Dialog auf und verdrahtet Validierung + Übernehmen.

        Ein einziges Formular für Anlegen (``symbol_id=None``) und Bearbeiten
        (``symbol_id`` gesetzt) — im Bearbeiten-Fall ist das Bedeutungsfeld
        schreibgeschützt (die ``id``, nicht der Text, ist die stabile
        Identität; eine Umbenennung läuft bewusst über Löschen + Neuanlegen,
        siehe ``CustomSymbolDefinition``-Docstring).

        Validierung läuft VOR dem Dispatch direkt in der GUI, über exakt
        dieselben Funktionen wie ``custom_symbol_usecases.py``
        (``validate_custom_symbol_*``) — nicht als ``try/except`` um den
        Intent-Dispatch herum: ``KartographAppController.dispatch()`` fängt
        Handler-Exceptions global ab (``IntentRegistry.dispatch()`` loggt sie
        nur und verwirft den State-Wechsel, s. dortiger Docstring), eine
        Exception aus dem Usecase käme also nie bis hierher zurück. Die
        Usecase-eigene Validierung bleibt trotzdem als Absicherung bestehen
        (falls ``AddCustomSymbolIntent``/``UpdateCustomSymbolIntent`` je aus
        einem anderen, nicht vorvalidierenden Kontext dispatcht würde), nur
        eben nicht als Fehlerquelle, auf die sich die GUI verlassen kann.
        Ansonsten dasselbe Retry-Muster wie
        ``_mixin_plan_crud.py::rename_selected_plan_dialog()``: Fehler
        erscheint sofort als Statuszeile, der Dialog bleibt offen.

        Args:
            symbol_id: ``None`` beim Anlegen, sonst die ID des bearbeiteten Symbols.
            glyph: Vorbelegung des Glyph-Feldes.
            meaning: Vorbelegung des Bedeutungsfeldes.
            shortcut: Vorbelegung des Tastenkürzel-Feldes.
        """
        is_edit = symbol_id is not None
        title = "Symbol bearbeiten" if is_edit else "Symbol anlegen"
        dialog = self._create_overlay_dialog(title, "440x320", parent=self._symbol_management_window)
        frame = tui.Frame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        glyph_var = ui.StringVar(value=glyph)
        meaning_var = ui.StringVar(value=meaning)
        shortcut_var = ui.StringVar(value=shortcut)

        tui.Label(frame, text="Symbol (Zeichen/Emoji hier einfügen)").grid(row=0, column=0, sticky="w", pady=(0, 4))
        glyph_entry = tui.Entry(frame, textvariable=glyph_var, width=6, font=("Segoe UI", 14))
        glyph_entry.grid(row=0, column=1, sticky="w", pady=(0, 4))

        tui.Label(frame, text="Bedeutung").grid(row=1, column=0, sticky="w", pady=(0, 4))
        meaning_entry = tui.Entry(
            frame, textvariable=meaning_var, width=28, state=("readonly" if is_edit else "normal")
        )
        meaning_entry.grid(row=1, column=1, sticky="w", pady=(0, 4))

        tui.Label(frame, text="Tastenkürzel (z. B. Ctrl+Shift+T)").grid(row=2, column=0, sticky="w", pady=(0, 4))
        shortcut_entry = tui.Entry(frame, textvariable=shortcut_var, width=22)
        shortcut_entry.grid(row=2, column=1, sticky="w", pady=(0, 4))

        if is_edit:
            tui.Label(
                frame,
                text="Die Bedeutung kann nicht geändert werden (nur Symbol/Kürzel) —\nfür eine Umbenennung: löschen und neu anlegen.",
                foreground="#666666",
                justify="left",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        status_var = ui.StringVar(value="")
        tui.Label(
            frame, textvariable=status_var, foreground="#b00020", justify="left", wraplength=400
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 4))

        def submit() -> None:
            existing_symbols = self.current_plan.custom_symbols if self.current_plan else {}
            other_shortcuts = [cs.shortcut for sid, cs in existing_symbols.items() if sid != symbol_id]
            try:
                clean_glyph = validate_custom_symbol_glyph(glyph_var.get())
                clean_meaning = validate_custom_symbol_meaning(meaning_var.get())
                clean_shortcut = validate_custom_symbol_shortcut(shortcut_var.get(), other_shortcuts)
            except CustomSymbolValidationError as exc:
                status_var.set(str(exc))
                return

            if is_edit:
                self._controller.dispatch(
                    UpdateCustomSymbolIntent(
                        symbol_id=symbol_id, glyph=clean_glyph, meaning=clean_meaning, shortcut=clean_shortcut
                    )
                )
            else:
                self._controller.dispatch(
                    AddCustomSymbolIntent(glyph=clean_glyph, meaning=clean_meaning, shortcut=clean_shortcut)
                )
            dialog.destroy()
            self._refresh_symbol_management_table()

        dialog.bind("<Return>", lambda _e: submit())

        button_row = tui.Frame(frame)
        button_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        cancel_button = tui.Button(button_row, text="Abbrechen", command=dialog.destroy)
        cancel_button.pack(side="right")
        self._attach_hover_help(cancel_button, label="Formular ohne Speichern schließen", shortcut="Esc")
        submit_button = tui.Button(button_row, text="Übernehmen", command=submit)
        submit_button.pack(side="right", padx=(0, 8))
        self._attach_hover_help(submit_button, label="Symbol speichern", shortcut="Enter")

        self._focus_overlay_widget(dialog, glyph_entry)
