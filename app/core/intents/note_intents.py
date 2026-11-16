from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class SetNotesIntent(Intent):
    """Ersetzt die Liste der Notizen eines Schülers vollständig."""

    student_id: StudentId
    notes: list[str]
