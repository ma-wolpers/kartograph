"""Symbol-Verwaltung-Popup-Mixin für das Kartograph-Hauptfenster.

Listenansicht aller Symbole (eingebaute mit ihren drei Legendenstufen +
eigene Doku-Symbole des aktuellen Plans mit ihrem einzelnen Bedeutungstext)
mit Neu/Bearbeiten/Löschen — Letztere zwei nur für eigene Symbole aktiv,
eingebaute sind reine Referenz (nur über ``config/symbols.json`` änderbar).
Das Add/Edit-Formular liegt in ``_mixin_symbol_management_form.py``.
"""

from __future__ import annotations

from app.adapters.gui.dialog_services import messagebox
from app.adapters.gui.main_window_constants import SPACE_SHORTCUT
from app.core.intents.custom_symbol_intents import DeleteCustomSymbolIntent
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets as tui

_ROLE_LABELS = {"diagnostic": "Diagnose", "documentation_only": "Doku"}


class SymbolManagementMixin:
    """Mixin: Popup zur Ansicht/Verwaltung aller Symbole (eingebaut + eigen)."""

    def open_symbol_management_dialog(self) -> None:
        """Öffnet das Symbol-Verwaltung-Popup oder bringt es in den Vordergrund."""
        if self._symbol_management_window is not None and int(self._symbol_management_window.winfo_exists()):
            self._refresh_symbol_management_table()
            self._symbol_management_window.deiconify()
            self._symbol_management_window.lift()
            self._symbol_management_window.focus_force()
            return

        window = ui.Toplevel(self)
        window.title("Symbol-Verwaltung")
        window.geometry("760x480")
        window.minsize(620, 360)
        self._track_popup_window(window, policy_id="dialog.non_blocking")

        toolbar = tui.Frame(window, padding=(10, 8))
        toolbar.pack(fill="x")
        new_button = tui.Button(toolbar, text="Neu", command=self._new_custom_symbol_dialog)
        new_button.pack(side="left")
        self._attach_hover_help(new_button, label="Eigenes Doku-Symbol anlegen", shortcut=None)
        self._symbol_management_edit_button = tui.Button(
            toolbar, text="Bearbeiten", command=self._edit_selected_custom_symbol_dialog, state="disabled"
        )
        self._symbol_management_edit_button.pack(side="left", padx=(8, 0))
        self._symbol_management_delete_button = tui.Button(
            toolbar, text="Löschen", command=self._delete_selected_custom_symbol, state="disabled"
        )
        self._symbol_management_delete_button.pack(side="left", padx=(8, 0))

        body = tui.Frame(window, padding=(10, 0, 10, 8))
        body.pack(fill="both", expand=True)
        columns = ("glyph", "meaning", "origin", "shortcut")
        table = tui.Treeview(body, columns=columns, show="headings")
        table.heading("glyph", text="Symbol")
        table.heading("meaning", text="Bedeutung / Erklärung")
        table.heading("origin", text="Herkunft")
        table.heading("shortcut", text="Tastenkürzel")
        table.column("glyph", width=60, anchor="center", stretch=False)
        table.column("meaning", width=420, anchor="w", stretch=True)
        table.column("origin", width=90, anchor="center", stretch=False)
        table.column("shortcut", width=140, anchor="center", stretch=False)
        table.pack(side="left", fill="both", expand=True)
        y_scroll = tui.Scrollbar(body, orient="vertical", command=table.yview)
        y_scroll.pack(side="right", fill="y")
        table.configure(yscrollcommand=y_scroll.set)
        table.bind("<<TreeviewSelect>>", lambda _e: self._on_symbol_management_selection_changed())
        table.bind("<Double-Button-1>", lambda _e: self._edit_selected_custom_symbol_dialog())

        self._symbol_management_window = window
        self._symbol_management_table = table
        window.protocol("WM_DELETE_WINDOW", self._close_symbol_management_dialog)
        self._refresh_symbol_management_table()

    def _close_symbol_management_dialog(self) -> None:
        """Schließt das Symbol-Verwaltung-Popup und meldet es aus der Popup-Registry ab."""
        if self._symbol_management_window is not None and int(self._symbol_management_window.winfo_exists()):
            popup_id = str(self._symbol_management_window)
            self._popup_registry.close_popup(popup_id)
            self._tracked_popup_ids.discard(popup_id)
            self._symbol_management_window.destroy()
        self._symbol_management_window = None
        self._symbol_management_table = None
        self._symbol_management_edit_button = None
        self._symbol_management_delete_button = None

    def _refresh_symbol_management_table(self) -> None:
        """Baut die Symbol-Tabelle aus dem eingebauten Katalog und den eigenen Symbolen des aktuellen Plans neu auf.

        Zeileninhalt je Herkunft bewusst unterschiedlich: eingebaute Symbole
        zeigen ihre drei zusammengefassten Legendenstufen (Stärke 1/2/3),
        eigene Symbole nur ihren einzelnen Bedeutungstext — kein Vortäuschen
        einer Struktur, die für eigene Symbole nicht existiert.
        """
        table = self._symbol_management_table
        if table is None:
            return
        table.delete(*table.get_children())
        for definition in self.symbol_definitions:
            legend = f"{definition.legend_one} / {definition.legend_two} / {definition.legend_three}"
            table.insert(
                "", ui.END,
                iid=f"builtin:{definition.meaning}",
                values=(
                    definition.glyph,
                    f"{definition.meaning} — {legend}",
                    _ROLE_LABELS.get(definition.role, definition.role),
                    "Leertaste" if definition.shortcut == SPACE_SHORTCUT else (definition.shortcut or ""),
                ),
            )
        for effective in self.effective_documentation_symbols:
            if not effective.is_custom:
                continue
            table.insert(
                "", ui.END,
                iid=f"custom:{effective.key}",
                values=(effective.glyph, effective.display_name, "eigen", effective.shortcut or ""),
            )
        self._on_symbol_management_selection_changed()

    def _selected_custom_symbol_id(self) -> str | None:
        """Gibt die ID des in der Tabelle ausgewählten EIGENEN Symbols zurück, oder ``None``.

        Eingebaute Zeilen (``iid`` beginnt mit ``"builtin:"``) liefern
        bewusst ``None`` — sie sind reine Referenz, nicht editierbar/löschbar.
        """
        table = self._symbol_management_table
        if table is None:
            return None
        selected = table.selection()
        if not selected:
            return None
        iid = selected[0]
        if not iid.startswith("custom:"):
            return None
        return iid.removeprefix("custom:")

    def _on_symbol_management_selection_changed(self) -> None:
        """Aktiviert die Bearbeiten-/Löschen-Buttons nur, wenn ein eigenes Symbol ausgewählt ist."""
        state = "normal" if self._selected_custom_symbol_id() is not None else "disabled"
        if self._symbol_management_edit_button is not None:
            self._symbol_management_edit_button.configure(state=state)
        if self._symbol_management_delete_button is not None:
            self._symbol_management_delete_button.configure(state=state)

    def _delete_selected_custom_symbol(self) -> None:
        """Löscht das ausgewählte eigene Symbol nach Bestätigung.

        Historische Dokumentationsdaten, die dieses Symbol referenzieren,
        bleiben erhalten (``delete_custom_symbol()`` rührt ``SessionEntry``
        nicht an) — der Bestätigungstext weist explizit darauf hin.
        """
        symbol_id = self._selected_custom_symbol_id()
        if symbol_id is None or not self.current_plan:
            return
        symbol = self.current_plan.custom_symbols.get(symbol_id)
        meaning = symbol.meaning if symbol is not None else symbol_id
        confirmed = messagebox.askyesno(
            "Symbol löschen",
            f"'{meaning}' aus dem Symbolkatalog dieses Plans entfernen?\n\n"
            "Bereits erfasste Dokumentationstage, die dieses Symbol verwenden, "
            "bleiben erhalten (sie zeigen es danach als \"Gelöschtes Symbol\" an).",
            parent=self._symbol_management_window,
        )
        if not confirmed:
            return
        self._controller.dispatch(DeleteCustomSymbolIntent(symbol_id=symbol_id))
        self._refresh_symbol_management_table()
