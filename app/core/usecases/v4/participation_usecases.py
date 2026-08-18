"""Usecases für die Mitarbeit-Tagesbewertung (+/o/-, session-/datumsgebunden).

Eigenständiges Konzept, kein Symbol: eine Bewertung ist ein einzelnes,
nullable Feld pro Schüler und Datum (``SessionEntry.participation``), keine
Stärke, kein Katalogeintrag. Exklusivität der drei Werte ist dadurch
strukturell garantiert statt durch Lösch-Logik hergestellt.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import ParticipationRating, SeatingPlan
from app.core.domain.student_id import StudentId
from app.core.usecases.v4._shared import _normalize_doc_date
from app.core.usecases.v4.session_usecases import ensure_session


def set_participation_rating(
    plan: SeatingPlan,
    student_id: StudentId,
    date: str | None,
    rating: ParticipationRating,
) -> SeatingPlan:
    """Setzt die Mitarbeit-Bewertung für *date* (None = heute).

    Erneutes Setzen derselben Bewertung löscht sie wieder (Toggle). Die
    Session wird nur bei gültigem, benanntem Schüler angelegt (kein leerer
    Session-Datensatz bei ungültiger Eingabe).

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        date: Datum im Format YYYY-MM-DD (None = heute).
        rating: Neue Bewertung ("+"/"o"/"-").

    Returns:
        Neuer Plan mit der aktualisierten Bewertung.
    """
    student = plan.classroom.student_by_id(student_id)
    if student is None or not student.is_named():
        return deepcopy(plan)

    next_plan = ensure_session(plan, date)
    date_key = _normalize_doc_date(date)
    session = next_plan.documentation.session_for_date(date_key)
    if session is None:
        return next_plan

    entry = session.ensure_entry(student_id)
    entry.participation = None if entry.participation == rating else rating
    if not entry.has_content():
        session.entries.pop(student_id, None)

    return next_plan
