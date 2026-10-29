"""Docs-Events-Mixin für das Kartograph-Hauptfenster.

Übersetzt die Ereignisse der Doku-Tabelle (bw-gui ``DataGrid``: Klick,
Doppelklick, ↑↓←→) in Auswahländerungen. Das Grid meldet bereits
(Zeile, Spaltenschlüssel, Bereich); hier stehen nur die fachlichen Regeln
(Namensbereich ändert nur die Zeile, Datumsanker, Zusammenfassung nicht
auswählbar) — die Spalten-/Navigationsregeln selbst liegen in
``DocColumnAxis`` und ``docs_table_rules``.

Zustände, die bewusst getrennt bleiben: ausgewählte Zeile
(``_doc_selected_student_index``), aktive logische Spalte
(``_doc_active_column_key()``) und Tk-Widget-Fokus (``docs_grid.focus``).
Angezeigt werden die ersten beiden ausschließlich über ``_sync_docs_cursor``.
"""

from __future__ import annotations

from app.adapters.gui.docs_table_model import DocsPane
from app.adapters.gui.docs_table_rules import resolve_horizontal_target
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult


class DocsEventsMixin:
    """Mixin: Klicks und Tastaturnavigation in der Doku-Tabelle."""

    def _on_docs_cell_click(self, row_id: str, column_key: str | None, pane: DocsPane) -> None:
        """Behandelt einen Klick in eine Zelle (Kopfklicks sortieren, s. ``_sort_docs_table_by_key``).

        Zeile wird immer ausgewählt. Im Namensbereich bleibt die aktive Spalte;
        in den Datumsspalten wird die angeklickte Datumsspalte (bzw. der
        Datumsanker) aktiv, im rechten Bereich die angeklickte Fixspalte
        (``summary`` → erste auswählbare Fixspalte).

        Args:
            row_id: Zeilen-ID der angeklickten Zeile.
            column_key: Spaltenschlüssel unter dem Mauszeiger oder ``None``.
            pane: Bereich, in dem geklickt wurde.
        """
        self._select_docs_row(row_id)
        axis = self._doc_axis
        target: str | None = None
        if pane is DocsPane.MAIN:
            target = column_key if axis.is_date(column_key) else axis.date_key(self._doc_selected_date_index)
        elif pane is DocsPane.RIGHT and column_key is not None:
            target = column_key if axis.is_selectable(column_key) else axis.first_selectable_nondate_right()
        if target is not None:
            self._set_doc_active_column(target)
        self._sync_docs_cursor()

    def _on_docs_cell_double_click(self, row_id: str, column_key: str | None) -> None:
        """Doppelklick: Zelle aktivieren; auf einer Notenzelle den Inline-Editor öffnen.

        Args:
            row_id: Zeilen-ID der angeklickten Zeile.
            column_key: Spaltenschlüssel unter dem Mauszeiger oder ``None``.
        """
        self._select_docs_row(row_id)
        if self._doc_axis.is_selectable(column_key):
            self._set_doc_active_column(column_key)
        self._sync_docs_cursor()
        if self._doc_axis.is_grade(column_key):
            self._open_docs_inline_grade_editor(row_id, column_key)

    def _select_docs_row(self, row_id: str) -> None:
        """Macht die Zeile *row_id* zur ausgewählten Schülerzeile (unbekannte IDs werden ignoriert).

        Args:
            row_id: Zeilen-ID (Schüler-ID als String).
        """
        student_index = self._doc_student_index_by_iid.get(row_id)
        if student_index is not None:
            self._doc_selected_student_index = student_index

    def _on_docs_vertical_nav(self, delta: int) -> EventResult:
        """Navigiert um ``delta`` Zeilen in der angezeigten (ggf. sortierten) Reihenfolge.

        Die aktive Spalte bleibt unverändert (auch eine Namensspalte).

        Args:
            delta: Schrittweite (positiv = nach unten, negativ = nach oben).

        Returns:
            ``EventResult.HANDLED``.
        """
        if not self._shortcut_scope_allows("docs") or not self._doc_row_order:
            return EventResult.HANDLED
        order = self._doc_row_order
        current = self._doc_row_id_by_student_index.get(self._selected_docs_student_index())
        position = order.index(current) if current in order else 0
        self._select_docs_row(order[max(0, min(position + delta, len(order) - 1))])
        self._sync_docs_cursor()
        return EventResult.HANDLED

    def _on_docs_horizontal_nav(self, delta: int) -> EventResult:
        """Bewegt die aktive Spalte entlang der logischen Spaltenachse (←/→).

        Die Zielspalte bestimmt die reine Regel ``resolve_horizontal_target``
        (Achse + Datumsanker); hier wird sie nur gesetzt, der Tastaturfokus
        folgt dem Bereich der Zielspalte.

        Args:
            delta: ``1`` nach rechts, ``-1`` nach links.

        Returns:
            ``EventResult.HANDLED``.
        """
        if not self._shortcut_scope_allows("docs"):
            return EventResult.HANDLED
        previous = self._doc_active_column_key()
        target = resolve_horizontal_target(self._doc_axis, previous, self._doc_selected_date_index, delta)
        if target is None:
            return EventResult.HANDLED
        self._set_doc_active_column(target)
        # Fokus nur beim Wechsel des Bereichs umsetzen: jeder focus_set löst Fokus-Ereignisse aus.
        if previous is None or self._doc_axis.pane_of(previous) is not self._doc_axis.pane_of(target):
            self.docs_grid.focus(target)
        self._sync_docs_cursor()
        return EventResult.HANDLED
