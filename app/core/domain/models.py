from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DeskType = Literal["teacher", "student"]


@dataclass(slots=True)
class Desk:
    x: int
    y: int
    desk_type: DeskType
    student_name: str = ""
    symbols: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class SeatingPlan:
    version: int
    plan_id: str
    name: str
    desks: list[Desk]

    def teacher_desk(self) -> Desk:
        for desk in self.desks:
            if desk.desk_type == "teacher":
                return desk
        raise ValueError("Plan has no teacher desk")

    def desk_at(self, x: int, y: int) -> Desk | None:
        for desk in self.desks:
            if desk.x == x and desk.y == y:
                return desk
        return None

    def without_desk_at(self, x: int, y: int) -> None:
        self.desks = [desk for desk in self.desks if not (desk.x == x and desk.y == y)]
