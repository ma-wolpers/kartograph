from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DeskType = Literal["teacher", "student"]
GradeCategory = Literal["schriftlich", "sonstig"]


@dataclass(slots=True)
class DocumentationEntry:
    symbols: dict[str, int] = field(default_factory=dict)
    grades: dict[str, float] = field(default_factory=dict)
    note: str = ""

    def has_content(self) -> bool:
        return bool(self.symbols or self.grades or self.note.strip())


@dataclass(slots=True)
class GradeColumnDefinition:
    column_id: str
    category: GradeCategory
    title: str


@dataclass(slots=True)
class Desk:
    x: int
    y: int
    desk_type: DeskType
    student_name: str = ""
    symbols: dict[str, int] = field(default_factory=dict)
    color_markers: list[str] = field(default_factory=list)
    tablegroup_number: int = 0
    tablegroup_shift_x: float = 0.0
    tablegroup_shift_y: float = 0.0
    tablegroup_rotation: float = 0.0
    documentation_entries: dict[str, DocumentationEntry] = field(default_factory=dict)


@dataclass(slots=True)
class SeatingPlan:
    version: int
    plan_id: str
    name: str
    desks: list[Desk]
    color_meanings: dict[str, str] = field(default_factory=dict)
    documentation_dates: list[str] = field(default_factory=list)
    grade_columns: list[GradeColumnDefinition] = field(default_factory=list)
    written_weight_percent: int = 50
    sonstige_weight_percent: int = 50

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
