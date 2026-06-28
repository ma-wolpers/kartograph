from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class ToggleColorIntent(Intent):
    """Setzt oder entfernt einen Farbpunkt (*color_key*) bei einem Schüler."""

    student_id: StudentId
    color_key: str
