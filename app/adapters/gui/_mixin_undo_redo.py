"""Undo/Redo- und Clipboard-Mixin für das Kartograph-Hauptfenster (v4 intent-basiert).

Stellt Undo/Redo-Operationen für Rasteränderungen sowie
Zwischenablage-Operationen (Kopieren, Ausschneiden, Einfügen) bereit.
"""

from __future__ import annotations

from app.adapters.gui.dialog_services import messagebox
from app.adapters.gui.main_window_constants import LIST_ACTIVE
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
        """Macht die letzte Änderung rückgängig (v4: UndoIntent)."""
        if not self.current_plan or not self.current_plan_path:
            if self.interaction_mode == LIST_ACTIVE:
                self._undo_plan_list_action()
            return
        self._controller.dispatch(UndoIntent())

    def undo_last_five_changes(self) -> None:
        """Macht die letzten fünf Rasteränderungen in einem Schritt rückgängig."""
        if not self.current_plan or not self.current_plan_path:
            return
        for _ in range(5):
            self._controller.dispatch(UndoIntent())

    def redo_last_change(self) -> None:
        """Wiederholt die zuletzt rückgängig gemachte Änderung (v4: RedoIntent)."""
        if not self.current_plan or not self.current_plan_path:
            if self.interaction_mode == LIST_ACTIVE:
                self._redo_plan_list_action()
            return
        self._controller.dispatch(RedoIntent())

    # Plan-Listen-Undo/Redo bleibt als Stub (Plan-Liste hat kein eigenes Intent-Undo mehr)
    def _undo_plan_list_action(self) -> bool:
        if not self._plan_list_undo_actions:
            self.status_var.set("Nichts zum Rueckgaengigmachen")
            return False
        action = self._plan_list_undo_actions.pop()
        kind = str(action.get("kind") or "")
        preferred_path = None
        try:
            if kind == "rename":
                source_path = action["after_path"]
                target_name = str(action["before_name"])
                restored_path, restored_plan = self.plan_repository.rename_plan(source_path, target_name, overwrite=True)
                action["before_path"] = restored_path
                if self.current_plan_path == source_path and self.current_plan is not None:
                    self.current_plan_path = restored_path
                    self.plan_name_var.set(f"Plan: {restored_plan.meta.name}")
                preferred_path = restored_path
            elif kind == "delete":
                deleted_path = action["deleted_path"]
                deleted_plan = action["deleted_plan"]
                self.plan_repository.save_plan(deleted_plan, deleted_path)
                preferred_path = deleted_path
            elif kind == "duplicate":
                duplicate_path = action["duplicate_path"]
                self.plan_repository.delete_plan(duplicate_path)
                if self.current_plan_path == duplicate_path:
                    self.current_plan_path = None
                    self.current_plan = None
                    self.plan_name_var.set("")
                preferred_path = self.current_plan_path
            else:
                self._plan_list_undo_actions.append(action)
                return False
        except Exception as exc:
            self._plan_list_undo_actions.append(action)
            self.status_var.set(f"Rueckgaengig fehlgeschlagen: {exc}")
            return False
        self._plan_list_redo_actions.append(action)
        self.refresh_plan_list()
        if preferred_path is not None:
            self._ensure_list_selection(preferred_path=preferred_path)
        self.status_var.set("Rueckgaengig")
        return True

    def _redo_plan_list_action(self) -> bool:
        if not self._plan_list_redo_actions:
            self.status_var.set("Nichts zum Wiederholen")
            return False
        action = self._plan_list_redo_actions.pop()
        kind = str(action.get("kind") or "")
        preferred_path = None
        try:
            if kind == "rename":
                source_path = action["before_path"]
                target_name = str(action["after_name"])
                restored_path, restored_plan = self.plan_repository.rename_plan(source_path, target_name, overwrite=True)
                action["after_path"] = restored_path
                if self.current_plan_path == source_path and self.current_plan is not None:
                    self.current_plan_path = restored_path
                    self.plan_name_var.set(f"Plan: {restored_plan.meta.name}")
                preferred_path = restored_path
            elif kind == "delete":
                deleted_path = action["deleted_path"]
                self.plan_repository.delete_plan(deleted_path)
                if self.current_plan_path == deleted_path:
                    self.current_plan_path = None
                    self.current_plan = None
                    self.plan_name_var.set("")
                preferred_path = self.current_plan_path
            elif kind == "duplicate":
                duplicate_path = action["duplicate_path"]
                duplicate_plan = action["duplicate_plan"]
                self.plan_repository.save_plan(duplicate_plan, duplicate_path)
                preferred_path = duplicate_path
            else:
                self._plan_list_redo_actions.append(action)
                return False
        except Exception as exc:
            self._plan_list_redo_actions.append(action)
            self.status_var.set(f"Wiederholen fehlgeschlagen: {exc}")
            return False
        self._plan_list_undo_actions.append(action)
        self.refresh_plan_list()
        if preferred_path is not None:
            self._ensure_list_selection(preferred_path=preferred_path)
        self.status_var.set("Wiederholt")
        return True

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
