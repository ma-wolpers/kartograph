from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.domain.submission_status import SubmissionStatus
from app.core.intents.base import Intent


@dataclass(frozen=True)
class ApplyMissingSubmissionsIntent(Intent):
    """Setzt an *date* X für alle Personen ohne Abgabe (ein Undo-Schritt pro Lauf).

    *mode* ist ``"replace"`` (alte X/✓/◐ des Tages vorher entfernen) oder
    ``"complement"`` (bereits Bewertete unverändert lassen).
    """

    date: str
    submitted: tuple[StudentId, ...]
    mark_absent: bool
    mode: str  # "replace" | "complement"


@dataclass(frozen=True)
class SetSubmissionStatusIntent(Intent):
    """Setzt für eine Person an *date* genau einen Abgabestatus (None = entfernen); ein Undo-Schritt."""

    student_id: StudentId
    date: str
    status: SubmissionStatus | None
