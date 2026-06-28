"""Usecases für Schüler-Operationen (Anlegen, Löschen, Umbenennen, Verschieben).

Schüler werden über ihre stabile ``StudentId`` adressiert. Koordinaten (x, y)
dienen nur noch als initiale Platzierung beim Anlegen oder als Konvenienz für
die GUI, nicht als primärer Schlüssel.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import (
    Classroom,
    Seat,
    SeatingPlan,
    Student,
    TableGroup,
    TeacherSeat,
)
from app.core.domain.student_id import StudentId


def create_student(plan: SeatingPlan, x: int, y: int) -> SeatingPlan:
    """Legt einen neuen, unbenannten Schüler an Position (*x*, *y*) an.

    Hat keinen Effekt, wenn an dieser Position bereits ein Schüler oder der
    Lehrertisch sitzt.

    Args:
        plan: Ausgangsplan.
        x: Spalte des neuen Sitzplatzes.
        y: Zeile des neuen Sitzplatzes.

    Returns:
        Neuer Plan mit dem angelegten Schüler.
    """
    next_plan = deepcopy(plan)
    ts = next_plan.classroom.teacher_seat
    if ts.x == x and ts.y == y:
        return next_plan
    if next_plan.classroom.student_at(x, y) is not None:
        return next_plan
    next_plan.classroom.students.append(
        Student(
            student_id=StudentId.new(),
            first_name="",
            last_name="",
            seat=Seat(x=x, y=y),
        )
    )
    return next_plan


def delete_student(plan: SeatingPlan, student_id: StudentId) -> SeatingPlan:
    """Entfernt den Schüler mit *student_id* aus dem Plan.

    Löscht auch alle Session-Einträge dieses Schülers sowie seine
    Tischgruppen-Mitgliedschaft.

    Args:
        plan: Ausgangsplan.
        student_id: ID des zu löschenden Schülers.

    Returns:
        Neuer Plan ohne den Schüler.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan

    seat_x, seat_y = student.seat.x, student.seat.y
    next_plan.classroom.students = [
        s for s in next_plan.classroom.students if s.student_id != student_id
    ]

    # Tischgruppen-Sitzplatz entfernen
    for group in next_plan.tablegroups:
        group.seats = [s for s in group.seats if not (s.x == seat_x and s.y == seat_y)]
    next_plan.tablegroups = [g for g in next_plan.tablegroups if g.seats]

    # Session-Einträge bereinigen
    for session in next_plan.documentation.sessions:
        session.entries.pop(student_id, None)

    return next_plan


def move_student(plan: SeatingPlan, student_id: StudentId, new_x: int, new_y: int) -> SeatingPlan:
    """Verschiebt den Schüler auf einen anderen Sitzplatz.

    Hat keinen Effekt, wenn der Zielplatz bereits besetzt ist oder dem
    Lehrertisch entspricht.

    Args:
        plan: Ausgangsplan.
        student_id: ID des zu verschiebenden Schülers.
        new_x: Neue Spalte.
        new_y: Neue Zeile.

    Returns:
        Neuer Plan mit dem verschobenen Schüler.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan
    ts = next_plan.classroom.teacher_seat
    if ts.x == new_x and ts.y == new_y:
        return next_plan
    if next_plan.classroom.student_at(new_x, new_y) is not None:
        return next_plan

    old_x, old_y = student.seat.x, student.seat.y
    student.seat = Seat(x=new_x, y=new_y)

    # Tischgruppen-Koordinaten mitziehen
    for group in next_plan.tablegroups:
        for gs in group.seats:
            if gs.x == old_x and gs.y == old_y:
                gs.x, gs.y = new_x, new_y

    return next_plan


def rename_student(
    plan: SeatingPlan,
    student_id: StudentId,
    first_name: str,
    last_name: str,
) -> SeatingPlan:
    """Setzt Vor- und Nachname eines Schülers.

    Args:
        plan: Ausgangsplan.
        student_id: ID des Schülers.
        first_name: Neuer Vorname (wird getrimmt).
        last_name: Neuer Nachname (wird getrimmt).

    Returns:
        Neuer Plan mit aktualisiertem Namen.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan
    student.first_name = first_name.strip()
    student.last_name = last_name.strip()
    return next_plan


def move_teacher_seat(plan: SeatingPlan, new_x: int, new_y: int) -> SeatingPlan:
    """Verschiebt den Lehrertisch; alle Schüler werden relativ mitbewegt.

    Der Schüler an (*new_x*, *new_y*) (falls vorhanden) wird entfernt.
    Alle Koordinaten werden so angepasst, dass der Lehrertisch wieder bei (0, 0) liegt.

    Args:
        plan: Ausgangsplan.
        new_x: Neue X-Position des Lehrertisches.
        new_y: Neue Y-Position des Lehrertisches.

    Returns:
        Neuer Plan mit verschobenem Lehrertisch.
    """
    next_plan = deepcopy(plan)
    dx, dy = -new_x, -new_y

    # Schüler am neuen Lehrerplatz entfernen, dann alle verschieben
    next_plan.classroom.students = [
        s for s in next_plan.classroom.students
        if not (s.seat.x == new_x and s.seat.y == new_y)
    ]
    for s in next_plan.classroom.students:
        s.seat = Seat(x=s.seat.x + dx, y=s.seat.y + dy)

    next_plan.classroom.teacher_seat = TeacherSeat(x=0, y=0)

    # Tischgruppen-Koordinaten mitziehen und leere Gruppen entfernen
    for group in next_plan.tablegroups:
        group.seats = [
            gs for gs in group.seats
            if not (gs.x == new_x and gs.y == new_y)
        ]
        for gs in group.seats:
            gs.x += dx
            gs.y += dy
    next_plan.tablegroups = [g for g in next_plan.tablegroups if g.seats]

    return next_plan
