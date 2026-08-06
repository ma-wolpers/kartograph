"""Usecases für Farbmarkierungen an Schülertischen.

Farbmarker sind kurze Schlüssel wie ``"red"`` oder ``"#ff0000"``, die einem
Tisch optional Bedeutungen zuordnen (z.B. ``"Förderbedarf"``). Das
``color_meanings``-Dict im Plan wird automatisch bereinigt, wenn eine Farbe
nicht mehr in Gebrauch ist.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import SeatingPlan


def is_color_used(plan: SeatingPlan, color_key: str) -> bool:
    """Prüft, ob *color_key* auf mindestens einem Schülertisch verwendet wird.

    Args:
        plan: Plan, aus dem gelesen wird.
        color_key: Zu suchender Farbschlüssel.

    Returns:
        True, wenn der Farbschlüssel bei mindestens einem Tisch vergeben ist.
    """
    for desk in plan.desks:
        if desk.desk_type != "student":
            continue
        if color_key in desk.color_markers:
            return True
    return False


def set_color_meaning(plan: SeatingPlan, color_key: str, meaning: str) -> SeatingPlan:
    """Weist *color_key* eine Bedeutung zu oder entfernt sie.

    Leerem *meaning* entfernt den Eintrag aus ``color_meanings``.

    Args:
        plan: Ausgangsplan.
        color_key: Farbschlüssel, dem die Bedeutung zugeordnet wird.
        meaning: Textuelle Bedeutung (z.B. ``"Förderbedarf"``); leer = entfernen.

    Returns:
        Neuer Plan mit dem aktualisierten Bedeutungs-Dict.
    """
    next_plan = deepcopy(plan)
    clean = meaning.strip()
    if clean:
        next_plan.color_meanings[color_key] = clean
    else:
        next_plan.color_meanings.pop(color_key, None)
    return next_plan


def cleanup_unused_color_meanings(plan: SeatingPlan) -> SeatingPlan:
    """Entfernt Bedeutungen für Farben, die kein Tisch mehr trägt.

    Wird typischerweise nach dem Entfernen einer Farbmarkierung aufgerufen.

    Args:
        plan: Ausgangsplan (kann bereits eine deepcopy sein).

    Returns:
        Neuer Plan ohne verwaiste Einträge in ``color_meanings``.
    """
    next_plan = deepcopy(plan)
    used_colors = {
        color_key
        for desk in next_plan.desks
        if desk.desk_type == "student"
        for color_key in desk.color_markers
    }
    next_plan.color_meanings = {
        color_key: meaning
        for color_key, meaning in next_plan.color_meanings.items()
        if color_key in used_colors
    }
    return next_plan


def toggle_color_marker(plan: SeatingPlan, x: int, y: int, color_key: str) -> SeatingPlan:
    """Schaltet *color_key* am Tisch (*x*, *y*) ein oder aus.

    War der Marker aktiv, wird er entfernt; andernfalls angehängt. Nach dem
    Entfernen werden verwaiste ``color_meanings`` automatisch bereinigt.

    Args:
        plan: Ausgangsplan.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        color_key: Zu toggelnder Farbschlüssel.

    Returns:
        Neuer Plan mit dem aktualisierten Farbmarker-Zustand.
    """
    next_plan = deepcopy(plan)
    desk = next_plan.desk_at(x, y)
    if not desk or desk.desk_type != "student":
        return next_plan

    markers = [key for key in desk.color_markers if key]
    if color_key in markers:
        desk.color_markers = [key for key in markers if key != color_key]
    else:
        desk.color_markers = markers + [color_key]

    return cleanup_unused_color_meanings(next_plan)
