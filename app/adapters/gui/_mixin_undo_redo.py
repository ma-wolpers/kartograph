"""Undo/Redo- und Clipboard-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Undo/Redo-Operationen sowie Zwischenablage-Operationen (Kopieren,
Ausschneiden, Einfügen) bereit; diese leiten je nach Oberfläche ins Raster
(Schüler-Zwischenablage) oder in die Datenansicht (``DocsClipboardMixin``).
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
        """Macht die letzten fünf Änderungen auf einmal rückgängig."""
        if not self.current_plan or not self.current_plan_path:
            return
        self._controller.dispatch(UndoIntent(steps=5))

    def redo_last_change(self) -> None:
        """Wiederholt die zuletzt rückgängig gemachte Änderung (v4: RedoIntent).

        Auch ohne offenen Plan (Listenansicht) dispatcht, damit eine zuvor
        per Undo rückgängig gemachte Listenaktion (Rename/Delete/Duplicate)
        erneut angewendet werden kann — analog zu ``undo_last_change``.
        """
        self._controller.dispatch(RedoIntent())

    def _clipboard_blocked(self) -> bool:
        """Kein offener Plan oder ein Namensfeld hat den Fokus (dann kopiert das Feld selbst)."""
        return not self.current_plan or not self.current_plan_path or self._is_name_entry_focused()

    def copy_selection(self) -> None:
        """Kopiert die Auswahl der aktiven Oberfläche (Strg+C).

        Datenansicht: die ausgewählte Zelle (``copy_docs_cell``). Raster: alle
        Schüler der Auswahl in die Schüler-Zwischenablage; der Plan bleibt
        unverändert, jedes spätere Einfügen erzeugt frische Kopien mit neuer ``StudentId``.
        """
        if self._clipboard_blocked():
            return
        if self._editor_surface == "docs":
            self.copy_docs_cell()
            return
        self._controller.dispatch(CopySelectionIntent(cells=tuple(self.selection.cells())))

    def cut_selection(self) -> None:
        """Schneidet die Auswahl der aktiven Oberfläche aus (Strg+X).

        Datenansicht: Zelle kopieren und leeren (``cut_docs_cell``). Raster:
        markiert die Schüler der Auswahl nur zum Verschieben -- sie bleiben an
        ihrem Platz, bis ``paste_selection`` sie verschiebt (unter Beibehaltung
        von ``StudentId`` und Dokumentationshistorie).
        """
        if self._clipboard_blocked():
            return
        if self._editor_surface == "docs":
            self.cut_docs_cell()
            return
        self._controller.dispatch(CutSelectionIntent(cells=tuple(self.selection.cells())))

    def paste_selection(self) -> None:
        """Fügt in die Auswahl der aktiven Oberfläche ein (Strg+V).

        Datenansicht: in die ausgewählte Zelle (``paste_docs_cell``). Raster:
        die ausgewählte Zelle (``self.selection.active_cell()``) ist die linke
        obere Ankerzelle für den relativen Versatz aller gemerkten Schüler.
        """
        if self._clipboard_blocked():
            return
        if self._editor_surface == "docs":
            self.paste_docs_cell()
            return
        target_x, target_y = self.selection.active_cell()
        self._controller.dispatch(PasteSelectionIntent(target_x=target_x, target_y=target_y))
