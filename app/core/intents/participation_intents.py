from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.models_v4 import ParticipationRating
from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class SetParticipationRatingIntent(Intent):
    """Setzt/löscht (Toggle) die Mitarbeit-Bewertung eines Schülers für ein Datum."""

    student_id: StudentId
    date: str
    rating: ParticipationRating
