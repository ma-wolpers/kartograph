from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import SeatingPlan


class PlanHistory:
    def __init__(self, max_undo_steps: int = 20):
        self.max_undo_steps = max(1, int(max_undo_steps))
        self._states: list[SeatingPlan] = []
        self._action_kinds: list[str | None] = []
        self._redo_states: list[SeatingPlan] = []
        self._redo_kinds: list[str | None] = []

    def reset(self, plan: SeatingPlan) -> None:
        self._states = [deepcopy(plan)]
        self._action_kinds = [None]
        self._redo_states = []
        self._redo_kinds = []

    def record(self, plan: SeatingPlan, action_kind: str) -> None:
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
