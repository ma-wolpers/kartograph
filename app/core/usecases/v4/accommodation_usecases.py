"""Usecases für Nachteilsausgleiche (Accommodations) an Schülern.

Nachteilsausgleiche sind Freitext-Einträge (z. B. "Zeitzuschlag 25 %"),
analog zu ``color_tags`` als einfache Liste statt strukturierter Daten.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.student_id import StudentId


def set_accommodations(
    plan: SeatingPlan, student_id: StudentId, accommodations: list[str]
) -> SeatingPlan:
    """Ersetzt die Liste der Nachteilsausgleiche eines Schülers vollständig.

    Leere/nur-Leerzeichen-Einträge werden verworfen, Reihenfolge bleibt erhalten.

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        accommodations: Neue, vollständige Liste der Nachteilsausgleiche.

    Returns:
        Neuer Plan mit aktualisierten Nachteilsausgleichen.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan
    student.diagnostic.accommodations = [a.strip() for a in accommodations if a.strip()]
    return next_plan
