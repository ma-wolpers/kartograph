from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import SeatingPlan


class PlanHistory:
    """Undo/Redo-Verlauf für einen Sitzplan auf Basis vollständiger Plan-Snapshots."""

    def __init__(self, max_undo_steps: int = 20):
        self.max_undo_steps = max(1, int(max_undo_steps))
        self._states: list[SeatingPlan] = []
        self._action_kinds: list[str | None] = []
        self._redo_states: list[SeatingPlan] = []
        self._redo_kinds: list[str | None] = []

    def reset(self, plan: SeatingPlan) -> None:
        """Setzt den Verlauf auf *plan* als einzigen Zustand zurück; löscht Undo/Redo.

        Args:
            plan: Sitzplan, der als einziger Verlaufszustand gespeichert wird.
        """
        self._states = [deepcopy(plan)]
        self._action_kinds = [None]
        self._redo_states = []
        self._redo_kinds = []

    def record(self, plan: SeatingPlan, action_kind: str) -> None:
        """Merkt sich *plan* als neuen Verlaufszustand und löscht den Redo-Stack.

        Identische Zustände werden ignoriert. Folgen mehrere Aufrufe mit
        demselben *action_kind* unmittelbar aufeinander (z. B. Tippen),
        wird der letzte Zustand überschrieben statt einen neuen Schritt
        anzulegen, damit Undo nicht in Einzelbuchstaben zerfällt.

        Args:
            plan: Aktueller Sitzplan, der als Snapshot gespeichert wird.
            action_kind: Kennung der Aktion, die zur Zusammenfassung
                aufeinanderfolgender gleichartiger Schritte dient.
        """
        if not self._states:
            self.reset(plan)
            return

        candidate = deepcopy(plan)
        if candidate == self._states[-1]:
            return

        if len(self._states) > 1 and self._action_kinds[-1] == action_kind:
            self._states[-1] = candidate
        else:
            self._states.append(candidate)
            self._action_kinds.append(action_kind)
            overflow = len(self._states) - (self.max_undo_steps + 1)
            if overflow > 0:
                self._states = self._states[overflow:]
                self._action_kinds = self._action_kinds[overflow:]

        self._redo_states = []
        self._redo_kinds = []

    def undo(self, steps: int = 1) -> SeatingPlan | None:
        """Macht bis zu *steps* Verlaufsschritte rückgängig.

        Args:
            steps: Anzahl der rückgängig zu machenden Schritte.

        Returns:
            Kopie des Plans nach dem Undo, oder None, wenn nichts
            rückgängig gemacht werden konnte (z. B. kein Verlauf vorhanden).
        """
        if steps < 1:
            return None
        if len(self._states) <= 1:
            return None

        performed = 0
        while performed < steps and len(self._states) > 1:
            self._redo_states.append(self._states.pop())
            self._redo_kinds.append(self._action_kinds.pop())
            performed += 1

        return deepcopy(self._states[-1])

    def redo(self, steps: int = 1) -> SeatingPlan | None:
        """Stellt bis zu *steps* zuvor rückgängig gemachte Schritte wieder her.

        Args:
            steps: Anzahl der wiederherzustellenden Schritte.

        Returns:
            Kopie des Plans nach dem Redo, oder None, wenn kein
            Redo-Zustand vorhanden ist.
        """
        if steps < 1:
            return None
        if not self._redo_states:
            return None

        performed = 0
        while performed < steps and self._redo_states:
            self._states.append(self._redo_states.pop())
            self._action_kinds.append(self._redo_kinds.pop())
            performed += 1

        return deepcopy(self._states[-1])
