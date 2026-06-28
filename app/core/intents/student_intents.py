from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class CreateStudentIntent(Intent):
    """Legt einen neuen, unbenannten Schüler auf Zelle (*x*, *y*) an."""

    x: int
    y: int


@dataclass(frozen=True)
class MoveStudentIntent(Intent):
    """Verschiebt einen Schüler auf eine neue Zelle (*new_x*, *new_y*).

    Hat aktuell keinen eigenen GUI-Trigger (Architekturplan v2, Abschnitt
    13.2, T5): Verschieben läuft im Editor über Ausschneiden+Einfügen
    (``StudentClipboard``), nicht über diesen Usecase direkt. Bleibt als
    fertiger, getesteter Baustein bestehen.
    """

    student_id: StudentId
    new_x: int
    new_y: int


@dataclass(frozen=True)
class RenameStudentIntent(Intent):
    """Setzt Vor- und Nachname eines Schülers (immer beide gemeinsam, auch bei Einzelfeld-Edits)."""

    student_id: StudentId
    first_name: str
    last_name: str


@dataclass(frozen=True)
class DeleteStudentIntent(Intent):
    """Entfernt einen Schüler vollständig aus dem Plan (inkl. Diagnoseprofil)."""

    student_id: StudentId


@dataclass(frozen=True)
class SetTeacherSeatIntent(Intent):
    """Verschiebt den Lehrertisch auf Zelle (*x*, *y*)."""

    x: int
    y: int
