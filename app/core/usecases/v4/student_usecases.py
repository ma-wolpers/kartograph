"""Usecases für Schüler-Operationen (Anlegen, Löschen, Umbenennen, Verschieben).

Schüler werden über ihre stabile ``StudentId`` adressiert. Koordinaten (x, y)
dienen nur noch als initiale Platzierung beim Anlegen oder als Konvenienz für
die GUI, nicht als primärer Schlüssel.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy

from app.core.domain.models_v4 import (
    DiagnosticProfile,
    Seat,
    SeatingPlan,
    Student,
    TeacherSeat,
)
from app.core.domain.student_id import StudentId
from app.core.domain.student_naming import normalize_name_part


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
            first_name_official="",
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
    return delete_students(plan, (student_id,))


def delete_students(plan: SeatingPlan, student_ids: Iterable[StudentId]) -> SeatingPlan:
    """Entfernt mehrere Schüler mit einer einzigen Plankopie (siehe ``delete_student``).

    Args:
        plan: Ausgangsplan.
        student_ids: IDs der zu löschenden Schüler; unbekannte werden übergangen.

    Returns:
        Neuer Plan ohne diese Schüler.
    """
    next_plan = deepcopy(plan)
    for student_id in student_ids:
        _delete_student_in_place(next_plan, student_id)
    return next_plan


def _delete_student_in_place(plan: SeatingPlan, student_id: StudentId) -> None:
    """Entfernt einen Schüler direkt aus dem bereits kopierten *plan*.

    Args:
        plan: Bereits kopierter Plan, der verändert wird.
        student_id: ID des zu löschenden Schülers.
    """
    student = plan.classroom.student_by_id(student_id)
    if student is None:
        return

    seat_x, seat_y = student.seat.x, student.seat.y
    plan.classroom.students = [s for s in plan.classroom.students if s.student_id != student_id]

    # Tischgruppen-Sitzplatz entfernen
    for group in plan.tablegroups:
        group.seats = [s for s in group.seats if not (s.x == seat_x and s.y == seat_y)]
    plan.tablegroups = [g for g in plan.tablegroups if g.seats]

    _remove_documentation_in_place(plan, student_id)


def _remove_documentation_in_place(plan: SeatingPlan, student_id: StudentId) -> None:
    """Entfernt alle Tageseinträge und Noten einer Person (Löschen und Namen-Entfernen teilen das).

    Args:
        plan: Bereits kopierter Plan, der verändert wird.
        student_id: Betroffene Person.
    """
    for session in plan.documentation.sessions:
        session.entries.pop(student_id, None)
    plan.documentation.remove_student_grades(student_id)


def drop_unnamed_desk_data(plan: SeatingPlan) -> None:
    """Invariante: Personendaten gibt es nur an benannten Tischen (in-place).

    Farbpunkte, Notizen, Diagnose-Symbole, Tageseinträge, Noten und die
    Markierung "dauerhaft abwesend" gehören zu Schüler:innen, nicht zu leeren
    Tischen. Wird der Name entfernt, fallen sie mit weg (Undo stellt sie
    wieder her); Altdateien mit Daten an leeren Tischen werden beim Öffnen
    bereinigt. Durchgesetzt über ``handlers/_shared.py::_apply_plan_invariants``
    -- Usecases räumen dafür nicht selbst auf.

    Args:
        plan: Plan, der direkt verändert wird.
    """
    for student in plan.classroom.students:
        if student.is_named() or not has_person_data(plan, student):
            continue
        student.diagnostic = DiagnosticProfile()
        student.permanently_absent = False
        _remove_documentation_in_place(plan, student.student_id)


def has_person_data(plan: SeatingPlan, student: Student) -> bool:
    """Trägt *student* Personendaten, die ohne Namen verloren gingen?

    Einzige Definition dafür: Farbpunkte, Notizen, Diagnose-Symbole,
    Abwesend-Markierung, Tageseinträge oder Noten. Genutzt von
    ``drop_unnamed_desk_data`` und der GUI-Warnung vor dem Leeren des Namens.

    Args:
        plan: Plan mit der Dokumentation.
        student: Zu prüfender Schülertisch.

    Returns:
        ``True``, wenn mindestens eine solche Angabe vorhanden ist.
    """
    sid = student.student_id
    return (
        student.diagnostic != DiagnosticProfile()
        or student.permanently_absent
        or any(sid in session.entries for session in plan.documentation.sessions)
        or bool(plan.documentation.grades.get(sid))
    )


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
        first_name: Neuer Vorname (über ``normalize_name_part``).
        last_name: Neuer Nachname (über ``normalize_name_part``).

    Returns:
        Neuer Plan mit aktualisiertem Namen.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan
    student.first_name_official = normalize_name_part(first_name)
    student.last_name = normalize_name_part(last_name)
    return next_plan


def set_nickname(plan: SeatingPlan, student_id: StudentId, nickname: str) -> SeatingPlan:
    """Setzt den Spitznamen eines Schülers (leerer String löscht ihn wieder).

    Args:
        plan: Ausgangsplan.
        student_id: ID des Schülers.
        nickname: Neuer Spitzname (über ``normalize_name_part``).

    Returns:
        Neuer Plan mit aktualisiertem Spitznamen.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan
    student.nickname = normalize_name_part(nickname)
    return next_plan


def set_permanently_absent(plan: SeatingPlan, student_id: StudentId, absent: bool) -> SeatingPlan:
    """Markiert eine Person als dauerhaft abwesend oder hebt die Markierung auf.

    Nur benannte Personen lassen sich markieren (ein leerer Tisch kann nicht
    abwesend sein); Aufheben geht immer. Folgen der Markierung regelt
    ``core/domain/permanent_absence.py``.

    Args:
        plan: Ausgangsplan.
        student_id: ID der Person.
        absent: ``True`` markiert, ``False`` hebt auf.

    Returns:
        Neuer Plan (unverändert, wenn die Person fehlt oder unbenannt ist).
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None or (absent and not student.is_named()):
        return next_plan
    student.permanently_absent = absent
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
