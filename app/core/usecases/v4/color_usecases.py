"""Usecases für Farbmarkierungen (Color-Tags) an Schülern.

Color-Tags sind kurze Schlüssel wie ``"gelb"`` aus der ``color_palette`` des Plans.
Das Palette-Dict wird bereinigt, wenn eine Farbe von keinem Schüler mehr getragen wird.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.student_id import StudentId


def is_color_tag_used(plan: SeatingPlan, color_key: str) -> bool:
    """Prüft, ob *color_key* bei mindestens einem Schüler gesetzt ist.

    Args:
        plan: Plan, aus dem gelesen wird.
        color_key: Zu suchender Farbschlüssel.

    Returns:
        True, wenn mindestens ein Schüler den Tag trägt.
    """
    return any(
        color_key in s.diagnostic.color_tags
        for s in plan.classroom.students
    )


def set_palette_meaning(plan: SeatingPlan, color_key: str, meaning: str) -> SeatingPlan:
    """Weist *color_key* eine pädagogische Bedeutung zu oder entfernt sie.

    Leeres *meaning* entfernt nur den Bedeutungstext; der Palette-Eintrag bleibt.

    Args:
        plan: Ausgangsplan.
        color_key: Farbschlüssel aus ``plan.color_palette``.
        meaning: Textuelle Bedeutung; leer = löschen.

    Returns:
        Neuer Plan mit dem aktualisierten Bedeutungstext.
    """
    next_plan = deepcopy(plan)
    if color_key not in next_plan.color_palette:
        return next_plan
    next_plan.color_palette[color_key].meaning = meaning.strip()
    return next_plan


def toggle_color_tag(
    plan: SeatingPlan, student_id: StudentId, color_key: str
) -> SeatingPlan:
    """Schaltet *color_key* beim Schüler ein oder aus.

    War der Tag aktiv, wird er entfernt; andernfalls angehängt.

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        color_key: Zu toggelnder Farbschlüssel.

    Returns:
        Neuer Plan mit dem aktualisierten Color-Tag-Zustand.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan

    tags = student.diagnostic.color_tags
    if color_key in tags:
        student.diagnostic.color_tags = [t for t in tags if t != color_key]
    else:
        student.diagnostic.color_tags = tags + [color_key]

    return next_plan


def cleanup_unused_palette_entries(plan: SeatingPlan) -> SeatingPlan:
    """Entfernt Palette-Einträge, die kein Schüler mehr trägt.

    Wird typischerweise nach dem Entfernen eines Color-Tags aufgerufen.

    Args:
        plan: Ausgangsplan (kann bereits eine deepcopy sein).

    Returns:
        Neuer Plan ohne verwaiste Palette-Einträge.
    """
    next_plan = deepcopy(plan)
    used = {
        tag
        for s in next_plan.classroom.students
        for tag in s.diagnostic.color_tags
    }
    next_plan.color_palette = {
        key: entry
        for key, entry in next_plan.color_palette.items()
        if key in used
    }
    return next_plan
