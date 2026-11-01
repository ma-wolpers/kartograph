from __future__ import annotations

from collections.abc import Hashable
from copy import deepcopy
from pathlib import Path

from app.core.domain.models_v4 import SeatingPlan

DEFAULT_MAX_UNDO_STEPS = 100


class PlanHistory:
    """Undo/Redo-Verlauf für einen Sitzplan auf Basis vollständiger Plan-Snapshots.

    Grundsatz: ein Schritt je Nutzeraktion. Zusammengefasst wird nur, was der
    Aufrufer ausdrücklich als dieselbe laufende Eingabe kennzeichnet (``merge_key``).
    """

    def __init__(self, max_undo_steps: int = DEFAULT_MAX_UNDO_STEPS):
        self.max_undo_steps = max(1, int(max_undo_steps))
        self.plan_path: Path | None = None
        self._states: list[SeatingPlan] = []
        self._redo_states: list[SeatingPlan] = []
        self._open_merge_key: Hashable | None = None

    @property
    def can_undo(self) -> bool:
        """Ob es mehr als den Ausgangszustand gibt, also etwas rückgängig zu machen ist."""
        return len(self._states) > 1

    @property
    def can_redo(self) -> bool:
        """Ob rückgängig gemachte Zustände zum Wiederholen bereitliegen."""
        return bool(self._redo_states)

    def reset(self, plan: SeatingPlan, plan_path: Path) -> None:
        """Setzt den Verlauf auf *plan* als einzigen Zustand zurück; löscht Undo/Redo.

        *plan_path* verankert die History an einer Plan-Identität: ein erneutes
        ``reset()`` mit demselben Pfad (z. B. nach Verlassen und Wiederbetreten
        desselben Kurses) kann so von einem echten Planwechsel unterschieden
        werden, statt den Verlauf grundlos zu verwerfen.

        Args:
            plan: Sitzplan, der als einziger Verlaufszustand gespeichert wird.
            plan_path: Pfad der Plandatei, zu der dieser Verlauf gehört.
        """
        self.plan_path = plan_path
        self._states = [deepcopy(plan)]
        self._redo_states = []
        self._open_merge_key = None

    def discard(self) -> None:
        """Verwirft den gesamten Verlauf und die Plan-Identität (kein Plan mehr getrackt).

        Wird aufgerufen, wenn der Plan, zu dem dieser Verlauf gehört, gelöscht
        wurde, damit ein später unter demselben Pfad neu angelegter Plan nicht
        versehentlich den Verlauf des gelöschten Plans erbt.
        """
        self.plan_path = None
        self._states = []
        self._redo_states = []
        self._open_merge_key = None

    def rename(self, new_path: Path) -> None:
        """Aktualisiert den getrackten Pfad nach einer Umbenennung; Verlauf bleibt erhalten.

        Anders als ``discard()`` (für einen gelöschten Plan gedacht) ändert
        sich bei einer Umbenennung nur der Dateipfad, nicht der Plan-Inhalt
        — der Undo/Redo-Verlauf bleibt deshalb vollständig nutzbar, nur die
        Plan-Identität muss mitwandern, sonst würde ein später unter dem
        alten Pfad neu angelegter Plan versehentlich diesen Verlauf erben.

        Args:
            new_path: Neuer Pfad der umbenannten Plandatei.
        """
        self.plan_path = new_path

    def record(self, plan: SeatingPlan, *, merge_key: Hashable | None = None) -> None:
        """Legt *plan* als eigenen Verlaufsschritt an und löscht den Redo-Stack.

        Identische Zustände werden ignoriert. Nur wenn *merge_key* gesetzt ist und
        dem unmittelbar vorigen Aufruf entspricht, wird dessen Schritt überschrieben.
        Jeder andere Schritt und jedes Undo oder Redo beendet das Zusammenfassen.

        Args:
            plan: Aktueller Sitzplan, der als Snapshot gespeichert wird.
            merge_key: Kennzeichnet eine laufende Eingabe, z. B. Tippen in dasselbe
                Feld derselben Person, damit Undo nicht in Wortteile zerfällt.
        """
        if not self._states:
            self.reset(plan, self.plan_path)
            return

        candidate = deepcopy(plan)
        if candidate == self._states[-1]:
            return

        if merge_key is not None and merge_key == self._open_merge_key:
            self._states[-1] = candidate
        else:
            self._states.append(candidate)
            overflow = len(self._states) - (self.max_undo_steps + 1)
            if overflow > 0:
                self._states = self._states[overflow:]

        self._open_merge_key = merge_key
        self._redo_states = []

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
            performed += 1

        self._open_merge_key = None
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
            performed += 1

        self._open_merge_key = None
        return deepcopy(self._states[-1])
