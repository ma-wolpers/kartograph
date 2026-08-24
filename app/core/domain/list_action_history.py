from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.domain.models_v4 import SeatingPlan


@dataclass(frozen=True)
class RenamePlanAction:
    """Aufgezeichnete Umbenennung einer Plandatei."""

    before_path: Path
    after_path: Path
    before_name: str
    after_name: str


@dataclass(frozen=True)
class DeletePlanAction:
    """Aufgezeichnete Löschung einer Plandatei samt Snapshot zum Löschzeitpunkt."""

    path: Path
    plan: SeatingPlan


@dataclass(frozen=True)
class DuplicatePlanAction:
    """Aufgezeichnetes Duplizieren; ``plan`` ist der beim Duplizieren entstandene Snapshot."""

    path: Path
    plan: SeatingPlan


ListAction = RenamePlanAction | DeletePlanAction | DuplicatePlanAction


class ListActionHistory:
    """Gemeinsamer Undo/Redo-Stack für Rename-/Delete-/Duplicate-Aktionen auf Plandateien.

    Anders als ``PlanHistory`` (Änderungen innerhalb eines geöffneten Plans)
    ist dies eine Historie von Operationen auf der Plan-Sammlung selbst —
    ein einziger nach Aktionsart gemischter LIFO-Stack, damit "rückgängig"
    in der Listenansicht immer die zuletzt ausgeführte Aktion trifft,
    unabhängig davon, ob es ein Umbenennen, Löschen oder Duplizieren war.
    """

    def __init__(self, max_steps: int = 20):
        self.max_steps = max(1, int(max_steps))
        self._undo_stack: list[ListAction] = []
        self._redo_stack: list[ListAction] = []

    def record(self, action: ListAction) -> None:
        """Merkt sich *action* als neuesten Schritt und löscht den Redo-Stack.

        Args:
            action: Die soeben erfolgreich ausgeführte Rename-/Delete-/
                Duplicate-Aktion.
        """
        self._undo_stack.append(action)
        overflow = len(self._undo_stack) - self.max_steps
        if overflow > 0:
            self._undo_stack = self._undo_stack[overflow:]
        self._redo_stack = []

    def peek_undo(self) -> ListAction | None:
        """Liefert die zuletzt aufgezeichnete Aktion, ohne die History zu verändern."""
        return self._undo_stack[-1] if self._undo_stack else None

    def confirm_undo(self) -> None:
        """Verschiebt die zuletzt gepeekte Undo-Aktion auf den Redo-Stack.

        Nur aufrufen, nachdem die Umkehrung dieser Aktion tatsächlich
        erfolgreich angewendet wurde (siehe ``peek_undo``).
        """
        self._redo_stack.append(self._undo_stack.pop())

    def peek_redo(self) -> ListAction | None:
        """Liefert die zuletzt rückgängig gemachte Aktion, ohne die History zu verändern."""
        return self._redo_stack[-1] if self._redo_stack else None

    def confirm_redo(self) -> None:
        """Verschiebt die zuletzt gepeekte Redo-Aktion zurück auf den Undo-Stack.

        Nur aufrufen, nachdem die Aktion tatsächlich erfolgreich erneut
        angewendet wurde (siehe ``peek_redo``).
        """
        self._undo_stack.append(self._redo_stack.pop())
