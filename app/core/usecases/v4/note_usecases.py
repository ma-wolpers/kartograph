"""Usecases für Notizen an Schülern (``DiagnosticProfile.notes``).

Notizen sind freie Textzeilen (z. B. Absprachen oder "Zeitzuschlag 25 %"),
analog zu ``color_tags`` als einfache Liste statt strukturierter Daten. Die
Normalisierung steht einmalig in ``app/core/domain/student_notes.py``.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.permanent_absence import accepts_notes
from app.core.domain.student_id import StudentId
from app.core.domain.student_notes import normalize_note_lines


def set_notes(
    plan: SeatingPlan, student_id: StudentId, notes: list[str]
) -> SeatingPlan:
    """Ersetzt die Liste der Notizen eines Schülers vollständig.

    Normalisiert über ``normalize_note_lines`` (getrimmt, Leerzeilen verworfen,
    Reihenfolge bleibt erhalten).

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        notes: Neue, vollständige Liste der Notizen.

    Returns:
        Neuer Plan mit aktualisierten Notizen.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None or not accepts_notes(student):  # Notizen nur für Schüler:innen
        return next_plan
    student.diagnostic.notes = normalize_note_lines(notes)
    return next_plan
