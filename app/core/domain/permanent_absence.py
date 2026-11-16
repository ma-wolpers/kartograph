"""Dauerhaft abwesende Personen: die einzige Regelstelle (SSOT).

Eine Person kann dauerhaft abwesend markiert werden (``Student.permanently_absent``,
z. B. langfristig krank, im Ausland). Die Markierung ist umkehrbar und löscht
nichts. Solange sie gesetzt ist, gilt:

* **zählt nicht mit** (``is_active``): Exporte (PDF, Sitzkärtchen, namenfit-CSV,
  Sitzplan-Vorschau) und Sammelaktionen (Abgaben zählen) übergehen die Person;
* **gesperrt** (``accepts_entries``): keine neuen Doku-Einträge, Noten, Mitarbeit,
  Diagnose-Symbole oder Farbpunkte -- Name, Notizen und das Aufheben bleiben möglich;
* **Tisch im Export** (``export_seat_visibility``): Gehört der Tisch zu einer
  Tischgruppe, in der noch ein anderer Tisch gezeigt wird, erscheint er leer
  (Raumbild bleibt stimmig); sonst entfällt er ganz.

Jeder Aufrufer fragt nur diese Funktionen, keiner prüft das Feld selbst. Die
Texte für Menü, Häkchen und Sperrhinweis stehen ebenfalls nur hier.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from app.core.domain.models_v4 import SeatingPlan, Student
from app.core.domain.student_id import StudentId
from app.core.domain.table_groups import SeatGeometryV4

PERMANENT_ABSENCE_LABEL = "Dauerhaft abwesend"
MARK_ABSENT_LABEL = "Als dauerhaft abwesend markieren"
UNMARK_ABSENT_LABEL = "Markierung „dauerhaft abwesend“ aufheben"
LOCKED_MESSAGE = "Dauerhaft abwesend – erst die Markierung aufheben"


def is_active(student: Student) -> bool:
    """Zählt *student* für Exporte und Sammelaktionen mit?

    Args:
        student: Zu prüfende Person (auch ein leerer Tisch).

    Returns:
        ``True`` für benannte, nicht dauerhaft abwesende Personen.
    """
    return student.is_named() and not student.permanently_absent


def accepts_entries(student: Student) -> bool:
    """Darf *student* neue Einträge (Doku, Noten, Mitarbeit, Symbole, Farben) bekommen?

    Args:
        student: Zu prüfende Person.

    Returns:
        ``True`` wie bei ``is_active`` -- gesperrt sind leere Tische und dauerhaft Abwesende.
    """
    return is_active(student)


def active_students(students: Iterable[Student]) -> list[Student]:
    """Die mitzählenden Personen, Reihenfolge erhalten.

    Args:
        students: Alle Schülertische eines Plans.
    """
    return [student for student in students if is_active(student)]


def absent_student_ids(students: Iterable[Student]) -> frozenset[StudentId]:
    """IDs aller benannten, dauerhaft abwesend markierten Personen.

    Args:
        students: Alle Schülertische eines Plans.
    """
    return frozenset(s.student_id for s in students if s.is_named() and s.permanently_absent)


@dataclass(frozen=True)
class ExportSeatVisibility:
    """Wie die Tische dauerhaft Abwesender in Exporten erscheinen.

    Attributes:
        emptied: Tisch erscheint leer (ohne Namen, Noten, Symbole, Farben).
        hidden: Tisch entfällt ganz.
    """

    emptied: frozenset[StudentId]
    hidden: frozenset[StudentId]


def export_seat_visibility(plan: SeatingPlan) -> ExportSeatVisibility:
    """Teilt die Tische dauerhaft Abwesender in "leer zeigen" und "weglassen".

    Ein Tisch erscheint leer, wenn seine Tischgruppe (``plan.tablegroups``, gehalten
    durch die Tischgruppen-Invariante) mindestens einen weiteren Tisch enthält, der
    gezeigt wird -- also einen leeren Tisch oder den einer mitzählenden Person.
    Sonst (Einzeltisch, Gruppe nur aus Abwesenden) entfällt er.

    Args:
        plan: Plan mit aktuellen Tischgruppen.

    Returns:
        Die Aufteilung; Personen ohne Markierung kommen in keiner Menge vor.
    """
    absent = absent_student_ids(plan.classroom.students)
    if not absent:
        return ExportSeatVisibility(frozenset(), frozenset())
    emptied: set[StudentId] = set()
    for group in plan.tablegroups:
        occupants = [plan.student_at(seat.x, seat.y) for seat in group.seats]
        if any(student is None or student.student_id not in absent for student in occupants):
            emptied.update(s.student_id for s in occupants if s is not None and s.student_id in absent)
    return ExportSeatVisibility(frozenset(emptied), frozenset(absent - emptied))


def apply_export_visibility(plan: SeatingPlan, geometries: Iterable[SeatGeometryV4]) -> list[SeatGeometryV4]:
    """Wendet ``export_seat_visibility`` auf Sitzgeometrien an (PDF, Sitzkärtchen, Vorschau).

    Weggelassene Tische fallen heraus; geleerte bleiben als Tisch ohne Person
    (``student=None``) -- jeder Renderer zeichnet sie damit wie einen leeren Tisch.
    Die Tischgruppen-Geometrie (Verschiebung/Drehung) bleibt unberührt, weil sie
    vorher aus dem ganzen Plan berechnet wurde.

    Args:
        plan: Plan, aus dem *geometries* berechnet wurden.
        geometries: Ergebnis von ``build_seat_geometries_v4(plan)``.

    Returns:
        Die zu zeichnenden Geometrien in unveränderter Reihenfolge.
    """
    visibility = export_seat_visibility(plan)
    result: list[SeatGeometryV4] = []
    for geometry in geometries:
        student_id = getattr(geometry.student, "student_id", None)
        if student_id in visibility.hidden:
            continue
        result.append(replace(geometry, student=None) if student_id in visibility.emptied else geometry)
    return result
