"""Usecases für Tisch-Operationen (Erstellen, Löschen, Umbenennen, Verschieben).

Jede Funktion erhält einen unveränderlichen ``SeatingPlan``, führt eine
Operation aus und gibt einen neuen ``SeatingPlan`` zurück (immutable-Update-
Muster via ``deepcopy``).
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import Desk, SeatingPlan
from app.core.domain.table_groups import normalize_tablegroups_in_place


def create_student_desk(plan: SeatingPlan, x: int, y: int) -> SeatingPlan:
    """Legt einen neuen Schülertisch an Position (*x*, *y*) an.

    Hat keinen Effekt, wenn die Zelle bereits belegt ist.

    Args:
        plan: Ausgangsplan.
        x: Spalte des neuen Tisches.
        y: Zeile des neuen Tisches.

    Returns:
        Neuer Plan mit dem angelegten Tisch.
    """
    next_plan = deepcopy(plan)
    existing = next_plan.desk_at(x, y)
    if existing and existing.desk_type in {"teacher", "student"}:
        return next_plan
    next_plan.desks.append(Desk(x=x, y=y, desk_type="student"))
    normalize_tablegroups_in_place(next_plan)
    return next_plan


def delete_desk(plan: SeatingPlan, x: int, y: int) -> SeatingPlan:
    """Entfernt den Schülertisch an (*x*, *y*).

    Der Lehrertisch kann nicht gelöscht werden. Hat keinen Effekt, wenn
    keine Zelle an dieser Position existiert.

    Args:
        plan: Ausgangsplan.
        x: Spalte des zu entfernenden Tisches.
        y: Zeile des zu entfernenden Tisches.

    Returns:
        Neuer Plan ohne den Tisch.
    """
    next_plan = deepcopy(plan)
    existing = next_plan.desk_at(x, y)
    if not existing or existing.desk_type == "teacher":
        return next_plan
    next_plan.without_desk_at(x, y)
    normalize_tablegroups_in_place(next_plan)
    return next_plan


def update_student_name(plan: SeatingPlan, x: int, y: int, name: str) -> SeatingPlan:
    """Setzt den Vornamen des Schülers an (*x*, *y*).

    Args:
        plan: Ausgangsplan.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        name: Neuer Vorname (wird getrimmt).

    Returns:
        Neuer Plan mit dem aktualisierten Vornamen.
    """
    next_plan = deepcopy(plan)
    desk = next_plan.desk_at(x, y)
    if not desk or desk.desk_type != "student":
        return next_plan
    desk.student_name = name.strip()
    return next_plan


def update_student_last_name(plan: SeatingPlan, x: int, y: int, last_name: str) -> SeatingPlan:
    """Setzt den Nachnamen des Schülers an (*x*, *y*).

    Args:
        plan: Ausgangsplan.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        last_name: Neuer Nachname (wird getrimmt).

    Returns:
        Neuer Plan mit dem aktualisierten Nachnamen.
    """
    next_plan = deepcopy(plan)
    desk = next_plan.desk_at(x, y)
    if not desk or desk.desk_type != "student":
        return next_plan
    desk.student_last_name = last_name.strip()
    return next_plan


def set_teacher_desk(plan: SeatingPlan, new_teacher_x: int, new_teacher_y: int) -> SeatingPlan:
    """Verschiebt den Lehrertisch auf (*new_teacher_x*, *new_teacher_y*).

    Alle anderen Tische werden relativ zur neuen Lehrerposition verschoben.
    Der bisherige Tisch an der Zielposition (falls vorhanden) wird entfernt.

    Args:
        plan: Ausgangsplan.
        new_teacher_x: Neue X-Koordinate des Lehrertisches.
        new_teacher_y: Neue Y-Koordinate des Lehrertisches.

    Returns:
        Neuer Plan mit verschobenem Lehrertisch.
    """
    next_plan = deepcopy(plan)
    transformed_students: dict[tuple[int, int], Desk] = {}

    for desk in next_plan.desks:
        if desk.x == new_teacher_x and desk.y == new_teacher_y:
            continue
        if desk.desk_type == "teacher":
            continue
        nx = desk.x - new_teacher_x
        ny = desk.y - new_teacher_y
        # deepcopy + Koordinaten anpassen; alle Felder werden übertragen.
        moved = deepcopy(desk)
        moved.x = nx
        moved.y = ny
        transformed_students[(nx, ny)] = moved

    next_plan.desks = [Desk(x=0, y=0, desk_type="teacher")]
    next_plan.desks.extend(transformed_students.values())
    normalize_tablegroups_in_place(next_plan)
    return next_plan
