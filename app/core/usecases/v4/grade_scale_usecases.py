"""Usecases für die planweite Notenskala (Schulnoten 1–6 / Punkte 0–15).

Eigene Datei neben ``grade_usecases.py``, damit dort das Zeilenlimit
eingehalten bleibt. Die Umrechnungsregeln selbst liegen ausschließlich in
``app/core/domain/grade_scale.py``; hier wird nur über den Plan iteriert.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.grade_scale import convert_value, scale_for
from app.core.domain.models_v4 import SeatingPlan


def count_grades(plan: SeatingPlan) -> int:
    """Zählt alle eingetragenen Notenwerte des Plans über alle Sessions.

    Grundlage für die Warnung vor einem Skalenwechsel: bei ``0`` kann ohne
    Rückfrage umgeschaltet werden, sonst nennt die Warnung die Anzahl.

    Args:
        plan: Plan, aus dem gelesen wird.
    """
    return sum(
        len(entry.grades)
        for session in plan.documentation.sessions
        for entry in session.entries.values()
    )


def set_grade_scale(plan: SeatingPlan, scale_id: str) -> SeatingPlan:
    """Stellt die Notenskala des Plans um und rechnet alle Werte mit um.

    Jeder Wert in ``SessionEntry.grades`` wird über
    :func:`~app.core.domain.grade_scale.convert_value` in die Zielskala
    übertragen (z. B. 3.2 → 7 Punkte, 3.15 → 7.5 Punkte). Die Gesamt- und
    Teilnoten folgen automatisch, da sie stets aus den Einzelwerten
    berechnet werden. Unbekannte IDs werden über ``scale_for`` auf die
    Standardskala normalisiert; bei gleicher Skala bleibt alles unverändert.

    Args:
        plan: Ausgangsplan.
        scale_id: ID der Zielskala.

    Returns:
        Neuer Plan in der Zielskala.
    """
    next_plan = deepcopy(plan)
    source = scale_for(plan.documentation.grade_scale).scale_id
    target = scale_for(scale_id).scale_id
    if source == target:
        return next_plan
    for session in next_plan.documentation.sessions:
        for entry in session.entries.values():
            entry.grades = {
                col_id: convert_value(value, source, target)
                for col_id, value in entry.grades.items()
            }
    next_plan.documentation.grade_scale = target
    return next_plan
