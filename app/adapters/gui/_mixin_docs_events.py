"""Docs-Events-Mixin für das Kartograph-Hauptfenster.

Koordiniert Klick-, Auswahl- und Tastaturereignisse aller drei Doku-Treeviews
(NAMES / MAIN / RIGHT) über pane-parametrisierte Handler sowie die
horizontale und vertikale Tastaturnavigation in der Doku-Tabelle.

Zustände, die hier bewusst getrennt gehalten werden:
Zeilenauswahl (``tree.selection()``), Treeview-Item-Fokus (``tree.focus(iid)``),
aktive logische Spalte (``_doc_active_column_key()``) und Tk-Widget-Fokus
(``focus_set()``). Keiner wird aus der Widget-Auswahl eines einzelnen Trees
abgeleitet.
"""

from __future__ import annotations

from app.adapters.gui.docs_table_model import DocsPane
from app.adapters.gui.docs_table_rules import resolve_horizontal_target


class DocsEventsMixin:
    """Mixin: Treeview-Ereignisse und Tastaturnavigation in der Dokumentations-Ansicht."""

    def _resolve_docs_click_column(self, pane: DocsPane, event_x: int) -> str | None:
        """Übersetzt die x-Koordinate eines Klicks in *pane* in einen logischen Spaltenschlüssel.

        Args:
            pane: Pane, in dem geklickt wurde.
            event_x: X-Koordinate des Klick-Ereignisses.

        Returns:
            Spaltenschlüssel oder ``None`` bei Klick außerhalb einer Spalte.
        """
        tree = self._docs_trees_by_pane()[pane]
        return self._doc_axis.resolve_clicked(pane, tree.identify_column(event_x), tree["columns"])

    def _on_docs_pane_click(self, pane: DocsPane, event) -> None:
        """Behandelt einen Klick in einem der drei Doku-Treeviews.

        Kopfzeile → Sortierung nach der angeklickten logischen Spalte.
        Zeile → Zeilenauswahl in allen Trees; danach setzt MAIN die
        angeklickte Datumsspalte (bzw. den Datumsanker) und RIGHT die
        angeklickte Fixspalte (``summary`` → erste Notenspalte) aktiv.
        Ein Klick im NAMES-Pane ändert nur die Zeile — die aktive Spalte bleibt.

        Args:
            pane: Pane, in dem geklickt wurde.
            event: Tkinter-Mausereignis.
        """
        tree = self._docs_trees_by_pane()[pane]
        column_key = self._resolve_docs_click_column(pane, event.x)
        if tree.identify_region(event.x, event.y) == "heading":
            if column_key is not None:
                self._sort_docs_table_by_key(column_key)
            return
        row_id = tree.identify_row(event.y)
        if row_id:
            self._set_docs_row_selection(row_id, source=pane)
        if pane is DocsPane.NAMES:
            return
        axis = self._doc_axis
        if pane is DocsPane.MAIN:
            target = column_key if axis.is_date(column_key) else axis.date_key(self._doc_selected_date_index)
        else:
            if column_key is None:
                return
            target = column_key if axis.is_selectable(column_key) else axis.first_selectable_nondate_right()
        if target is not None:
            self._set_doc_active_column(target)
        self._apply_doc_column_heading_highlight()

    def _on_docs_pane_select(self, pane: DocsPane) -> None:
        """Übernimmt eine (nativ ausgelöste) Zeilenauswahl in *pane* in alle Trees.

        Ändert ausschließlich die Zeilenauswahl — die aktive Spalte bleibt
        unverändert, unabhängig davon, welcher Tree den Tk-Fokus hat.

        Args:
            pane: Pane, dessen Treeview ``<<TreeviewSelect>>`` ausgelöst hat.
        """
        if self._syncing_docs_selection:
            return
        selected = self._docs_trees_by_pane()[pane].selection()
        if not selected:
            return
        self._set_docs_row_selection(selected[0], source=pane)
        self._refresh_doc_selection_status()

    def _on_docs_pane_keypress(self, event) -> None:
        """Stellt nach Tasteneingabe in einem Doku-Tree die Spaltenauswahl wieder her (außer Pfeile).

        Args:
            event: Tkinter-Tastaturereignis (``keysym`` bestimmt, ob Pfeiltasten ignoriert werden).
        """
        if event.keysym in {"Left", "Right", "Up", "Down"}:
            return
        self._preserve_docs_column_selection_after_keypress()

    def _on_docs_right_tree_double_click(self, event) -> None:
        """Öffnet den Inline-Editor bei Doppelklick auf eine Noten-Zelle im RIGHT-Pane.

        Args:
            event: Tkinter-Mausereignis.
        """
        row_id = self.docs_right_tree.identify_row(event.y)
        if not row_id:
            return
        self._set_docs_row_selection(row_id, source=DocsPane.RIGHT)
        column_key = self._resolve_docs_click_column(DocsPane.RIGHT, event.x)
        if not self._doc_axis.is_selectable(column_key):
            return
        self._set_doc_active_column(column_key)
        self._apply_doc_column_heading_highlight()
        if self._doc_axis.is_grade(column_key):
            self._open_docs_inline_grade_editor(row_id, column_key)

    def _set_docs_row_selection(self, row_id: str, source: DocsPane | None = None) -> None:
        """Synchronisiert Zeilenauswahl und Treeview-Item-Fokus aller drei Trees auf ``row_id``.

        Setzt in jedem Tree außer *source* ``selection``, ``focus(iid)`` und
        ``see``. Rührt weder die aktive Spalte noch den Tk-Widget-Fokus an.

        Args:
            row_id: Zeilen-ID der Zielzeile (in allen Trees identisch).
            source: Pane, dessen Tree die Auswahl bereits trägt (wird nicht neu gesetzt).
        """
        if not row_id:
            return
        if self._syncing_docs_selection:
            return
        trees = self._docs_trees_by_pane()
        if not all(tree.exists(row_id) for tree in trees.values()):
            return
        self._syncing_docs_selection = True
        try:
            for pane, tree in trees.items():
                if pane is source:
                    continue
                selected = tree.selection()
                if len(selected) != 1 or selected[0] != row_id:
                    tree.selection_set(row_id)
                if tree.focus() != row_id:
                    tree.focus(row_id)
                tree.see(row_id)
        finally:
            self._syncing_docs_selection = False

        student_idx = self._doc_student_index_by_iid.get(row_id)
        if student_idx is not None:
            self._doc_selected_student_index = student_idx

    def _on_docs_vertical_nav(self, delta: int, *, source: DocsPane) -> str:
        """Navigiert in der Doku-Tabelle um ``delta`` Zeilen in visueller Reihenfolge.

        Die aktive Spalte bleibt unverändert (auch eine Namensspalte).

        Args:
            delta: Schrittweite (positiv = nach unten, negativ = nach oben).
            source: Pane, dessen Tree die Taste empfangen hat (behält den Tk-Fokus).

        Returns:
            ``"break"`` um die Standard-Tkinter-Navigation zu unterdrücken.
        """
        if not self._shortcut_scope_allows("docs"):
            return "break"
        if not self._doc_student_coords:
            return "break"

        nondate_column_id = self._doc_selected_nondate_column_id
        date_index = self._doc_selected_date_index

        all_iids = list(self._doc_row_order)
        if not all_iids:
            return "break"

        current_iid = self._doc_tree_iid_by_student_index.get(
            max(0, min(self._doc_selected_student_index, len(self._doc_student_coords) - 1))
        )
        visual_pos = all_iids.index(current_iid) if current_iid in all_iids else 0
        next_pos = max(0, min(visual_pos + delta, len(all_iids) - 1))
        row_id = all_iids[next_pos]

        self._set_docs_row_selection(row_id)
        self._focus_docs_pane(source)
        self._refresh_doc_selection_status()
        self.after_idle(lambda: self._restore_docs_column_selection(nondate_column_id, date_index))
        self.after_idle(self._update_docs_cell_highlight)
        return "break"

    def _on_docs_horizontal_nav(self, delta: int) -> str:
        """Bewegt die aktive Spalte entlang der logischen Spaltenachse (←/→).

        Die Zielspalte bestimmt die reine, Tk-freie Regel
        ``resolve_horizontal_target`` (Achse + Datumsanker); dieser Handler
        führt sie nur aus: aktive Spalte setzen, Tk-Fokus auf das Pane der
        Zielspalte legen, Überschriften/Markierung aktualisieren.

        Args:
            delta: ``1`` nach rechts, ``-1`` nach links.

        Returns:
            ``"break"`` um die Standard-Navigation zu unterdrücken.
        """
        if not self._shortcut_scope_allows("docs"):
            return "break"
        target = resolve_horizontal_target(
            self._doc_axis, self._doc_active_column_key(), self._doc_selected_date_index, delta
        )
        if target is None:
            return "break"
        self._set_doc_active_column(target)
        self._focus_docs_pane(self._doc_axis.pane_of(target))
        self._apply_doc_column_heading_highlight()
        return "break"
