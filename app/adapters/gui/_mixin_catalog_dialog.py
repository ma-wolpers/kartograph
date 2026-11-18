"""Fenster „Symbole und Kompetenzen“: programmweiter Katalog (gilt für alle Pläne).

Zwei Reiter mit je einer Tabelle und „Neu“/„Bearbeiten“ (Doppelklick =
Bearbeiten). Die Formulare liegen in ``_mixin_catalog_symbol_form.py`` und
``_mixin_catalog_competence_form.py``. Änderungen werden sofort gespeichert und
lassen sich nicht rückgängig machen — der Hinweis oben sagt das. Gelöscht wird
nichts; Symbole lassen sich deaktivieren.
"""

from __future__ import annotations

from app.adapters.gui.main_window_constants import SPACE_SHORTCUT
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import bind_click, on_treeview_select, ui, widgets as tui

CATALOG_HINT = "Gilt für alle Pläne · wird sofort gespeichert · nicht rückgängig zu machen"


def _shortcut_label(shortcut: str | None) -> str:
    """Anzeige eines Kürzels in Tabellen (``"Leertaste"``, Großbuchstabe oder leer).

    Args:
        shortcut: Gespeichertes Kürzel.
    """
    return "Leertaste" if shortcut == SPACE_SHORTCUT else (shortcut or "").upper()


class CatalogDialogMixin:
    """Mixin: nicht-modales Fenster zum Bearbeiten des programmweiten Katalogs."""

    _catalog_window = None  # offenes Fenster oder None (Klassen-Default statt Init im Hauptfenster)

    def open_catalog_dialog(self) -> None:
        """Öffnet das Fenster oder holt ein offenes nach vorn."""
        window = self._catalog_window
        if window is not None and int(window.winfo_exists()):
            self._refresh_catalog_tables()
            window.deiconify()
            window.lift()
            window.focus_force()
            return
        window = ui.Toplevel(self)
        window.title("Symbole und Kompetenzen")
        window.geometry("820x520")
        window.minsize(640, 380)
        self._register_popup_window(window, blocking_shortcuts=False)
        tui.Label(window, text=CATALOG_HINT, style="Muted.TLabel").pack(anchor="w", padx=10, pady=(8, 4))
        notebook = tui.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._catalog_window = window
        self._catalog_symbol_table = self._build_catalog_tab(
            notebook, "Symbole",
            (("glyph", "Zeichen", 60, False), ("name", "Name", 200, False), ("shortcut", "Taste", 70, False),
             ("state", "Art", 110, False), ("competences", "Kompetenzen", 360, True)),
            new=lambda: self._open_catalog_symbol_form(None),
            edit=lambda iid: self._open_catalog_symbol_form(iid),
        )
        self._catalog_competence_table = self._build_catalog_tab(
            notebook, "Kompetenzen",
            (("group", "Gruppe", 170, False), ("name", "Name", 260, False), ("used", "Verwendet von", 320, True)),
            new=lambda: self._open_catalog_competence_form(None),
            edit=lambda iid: self._open_catalog_competence_form(iid),
        )
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        self._refresh_catalog_tables()

    def _build_catalog_tab(self, notebook, title: str, columns, *, new, edit):
        """Baut einen Reiter mit Werkzeugleiste und Tabelle und gibt die Tabelle zurück.

        Args:
            notebook: Das ``Notebook`` des Fensters.
            title: Reitertitel.
            columns: ``(id, Überschrift, Breite, dehnbar)`` je Spalte.
            new: Aktion für „Neu“.
            edit: Aktion für „Bearbeiten“, bekommt die ``iid`` der gewählten Zeile.
        """
        tab = tui.Frame(notebook, padding=(0, 8, 0, 0))
        notebook.add(tab, text=title)
        toolbar = tui.Frame(tab)
        toolbar.pack(fill="x", pady=(0, 6))
        table = tui.Treeview(tab, columns=[c[0] for c in columns], show="headings", selectmode="browse")

        def edit_selected() -> None:
            selection = table.selection()
            if selection:
                edit(selection[0])

        tui.Button(toolbar, text="Neu", command=new).pack(side="left")
        edit_button = tui.Button(toolbar, text="Bearbeiten", command=edit_selected, state="disabled")
        edit_button.pack(side="left", padx=(8, 0))
        for column_id, heading, width, stretch in columns:
            table.heading(column_id, text=heading)
            table.column(column_id, width=width, anchor="w", stretch=stretch)
        table.pack(side="left", fill="both", expand=True)
        scroll = tui.Scrollbar(tab, orient="vertical", command=table.yview)
        scroll.pack(side="right", fill="y")
        table.configure(yscrollcommand=scroll.set)
        on_treeview_select(table, lambda _c: edit_button.configure(state="normal" if table.selection() else "disabled"))
        bind_click(table, lambda _e: edit_selected(), count=2)
        return table

    def _refresh_catalog_tables(self) -> None:
        """Füllt beide Tabellen aus dem programmweiten Katalog (ohne Plan-Anpassungen)."""
        window = self._catalog_window
        if window is None or not int(window.winfo_exists()):
            return
        state = self._controller.state
        names = {c.id: c.name for c in state.competence_catalog}
        symbols = self._catalog_symbol_table
        symbols.delete(*symbols.get_children())
        for definition in state.symbol_catalog:
            kind = "Diagnose" if definition.role == "diagnostic" else "Doku"
            if not definition.active:
                kind += " · deaktiviert"
            detail = ", ".join(names.get(cid, cid) for cid in definition.competence_ids)
            symbols.insert("", ui.END, iid=definition.key, values=(
                definition.glyph, definition.name, _shortcut_label(definition.shortcut), kind, detail))
        competences = self._catalog_competence_table
        competences.delete(*competences.get_children())
        for competence in state.competence_catalog:
            users = [d.name for d in state.symbol_catalog if competence.id in d.competence_ids]
            competences.insert("", ui.END, iid=competence.id, values=(
                competence.group, competence.name, ", ".join(users) or "–"))
