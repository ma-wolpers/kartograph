"""Undo/Redo- und Clipboard-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Undo/Redo-Operationen für Rasteränderungen sowie
Zwischenablage-Operationen (Kopieren, Ausschneiden, Einfügen) bereit.
"""

from __future__ import annotations

from app.core.intents.edit_intents import (
    CopySelectionIntent,
    CutSelectionIntent,
    PasteSelectionIntent,
    RedoIntent,
    UndoIntent,
)


class UndoRedoMixin:
    """Mixin: Undo/Redo für Raster sowie Clipboard-Operationen (v4)."""

    def undo_last_change(self) -> None:
        """Macht die letzte Änderung rückgängig (v4: UndoIntent).

        Auch ohne offenen Plan (Listenansicht) dispatcht, damit ein zuvor
        gelöschter Sitzplan per Undo wiederhergestellt werden kann — der
        Handler selbst entscheidet, ob Raster-Undo, Lösch-Wiederherstellung
        oder "nichts zu tun" zutrifft.
        """
        self._controller.dispatch(UndoIntent())

    def undo_last_five_changes(self) -> None:
        """Macht die letzten fünf Rasteränderungen in einem Schritt rückgängig."""
        if not self.current_plan or not self.current_plan_path:
            return
        for _ in range(5):
            self._controller.dispatch(UndoIntent())

    def redo_last_change(self) -> None:
        """Wiederholt die zuletzt rückgängig gemachte Änderung (v4: RedoIntent).

        Auch ohne offenen Plan (Listenansicht) dispatcht, damit eine zuvor
        per Undo rückgängig gemachte Listenaktion (Rename/Delete/Duplicate)
        erneut angewendet werden kann — analog zu ``undo_last_change``.
        """
        self._controller.dispatch(RedoIntent())

    def copy_selection(self) -> None:
        """Kopiert alle Schüler der aktuellen Auswahl in die Zwischenablage (v4).

        Reine Zwischenablage-Operation; der Plan bleibt unverändert. Jedes
        spätere Einfügen erzeugt frische Kopien mit neuer ``StudentId``.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        if self._is_name_entry_focused():
            return
        self._controller.dispatch(CopySelectionIntent(cells=tuple(self.selection.cells())))

    def cut_selection(self) -> None:
        """Markiert alle Schüler der aktuellen Auswahl zum Verschieben (v4).

        Löscht noch nichts: die ausgewählten Schüler bleiben an ihrem Platz,
        bis ``paste_selection`` aufgerufen wird — erst dabei werden sie
        tatsächlich verschoben (unter Beibehaltung von ``StudentId`` und
        Dokumentationshistorie).
        """
        if not self.current_plan or not self.current_plan_path:
            return
        if self._is_name_entry_focused():
            return
        self._controller.dispatch(CutSelectionIntent(cells=tuple(self.selection.cells())))

    def paste_selection(self) -> None:
        """Fügt den Zwischenablage-Inhalt ab der aktuell ausgewählten Zelle ein (v4).

        Die ausgewählte Zelle (``self.selection.active_cell()``) bildet die
        linke obere Ankerzelle für den relativen Versatz aller im Puffer
        gemerkten Schüler.
        """
        if not self.current_plan or not self.current_plan_path:
            return
        if self._is_name_entry_focused():
            return
        target_x, target_y = self.selection.active_cell()
        self._controller.dispatch(PasteSelectionIntent(target_x=target_x, target_y=target_y))
