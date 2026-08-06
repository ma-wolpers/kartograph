from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DeskType = Literal["teacher", "student"]
GradeCategory = Literal["schriftlich", "sonstig"]


@dataclass(slots=True)
class DocumentationEntry:
    """Dokumentationseintrag eines einzelnen Schülers für ein Datum: Symbole, Noten, Notiz."""

    symbols: dict[str, int] = field(default_factory=dict)
    grades: dict[str, float] = field(default_factory=dict)
    note: str = ""

    def has_content(self) -> bool:
        """Prüft, ob der Eintrag Symbole, Noten oder eine Notiz enthält."""
        return bool(self.symbols or self.grades or self.note.strip())


@dataclass(slots=True)
class GradeColumnDefinition:
    """Definition einer Notenspalte (z. B. „Mathearbeit 1")."""

    column_id: str
    category: GradeCategory
    title: str


@dataclass(slots=True)
class Desk:
    """Ein Tisch im v3-Sitzplanmodell: Lehrer- oder Schülertisch mit Position und Geometrie.

    Vereint, was in v4 auf ``Student``/``TeacherSeat`` (Person) und
    ``TableGroup``/``GroupSeat`` (Tischgruppen-Geometrie) aufgeteilt ist.
    """

    x: int
    y: int
    desk_type: DeskType
    student_name: str = ""
    student_last_name: str = ""
    symbols: dict[str, int] = field(default_factory=dict)
    color_markers: list[str] = field(default_factory=list)
    tablegroup_number: int = 0
    tablegroup_shift_x: float = 0.0
    tablegroup_shift_y: float = 0.0
    tablegroup_rotation: float = 0.0
    documentation_entries: dict[str, DocumentationEntry] = field(default_factory=dict)

    def is_student(self) -> bool:
        """Prüft, ob es sich um einen Schülertisch handelt."""
        return self.desk_type == "student"

    def is_named_student(self) -> bool:
        """Prüft, ob es sich um einen Schülertisch mit eingetragenem Namen handelt."""
        return self.is_student() and bool(self.student_name.strip())


@dataclass(slots=True)
class SeatingPlan:
    """Ein Sitzplan: Raster aus Tischen samt Dokumentations- und Notenstruktur."""

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
        """Gibt den Lehrertisch des Plans zurück.

        Raises:
            ValueError: Wenn der Plan keinen Lehrertisch enthält.
        """
        for desk in self.desks:
            if desk.desk_type == "teacher":
                return desk
        raise ValueError("Plan has no teacher desk")

    def desk_at(self, x: int, y: int) -> Desk | None:
        """Gibt den Tisch an Koordinate (x, y) zurück, oder None.

        Args:
            x: X-Rasterkoordinate des gesuchten Tisches.
            y: Y-Rasterkoordinate des gesuchten Tisches.
        """
        for desk in self.desks:
            if desk.x == x and desk.y == y:
                return desk
        return None

    def without_desk_at(self, x: int, y: int) -> None:
        """Entfernt den Tisch an Koordinate (x, y) aus dem Plan, falls vorhanden.

        Args:
            x: X-Rasterkoordinate des zu entfernenden Tisches.
            y: Y-Rasterkoordinate des zu entfernenden Tisches.
        """
        self.desks = [desk for desk in self.desks if not (desk.x == x and desk.y == y)]
