from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class AddGradeColumnIntent(Intent):
    """Legt eine neue Notenspalte (*category*: "schriftlich" | "sonstig") mit *title* an."""

    category: str  # "schriftlich" | "sonstig"
    title: str


@dataclass(frozen=True)
class DeleteGradeColumnIntent(Intent):
    """Löscht die Notenspalte *column_id* inkl. aller darin erfassten Noten aus allen Sessions."""

    column_id: str


@dataclass(frozen=True)
class RecordGradeIntent(Intent):
    """Trägt für einen Schüler an *date* in Spalte *column_id* die Note *grade* ein (0.0 = löschen)."""

    student_id: StudentId
    date: str
    column_id: str
    grade: float  # 0.0 = löschen


@dataclass(frozen=True)
class UpdateGradeWeightingIntent(Intent):
    """Setzt die Gewichtung schriftlicher vs. sonstiger Noten in Prozent."""

    written_percent: int
    sonstige_percent: int
