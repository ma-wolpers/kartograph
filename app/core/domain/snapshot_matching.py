"""Gleichheits-Prädikate zwischen einem Snapshot und dem aktuellen Sitzplan.

Zwei getrennte, benannte Prädikate statt einer universellen Funktion mit
mehreren Bedeutungen:

- :func:`positions_match` -- Lehrertisch + alle GEMEINSAMEN Schüler:innen
  stimmen überein; unterschiedliche Schüler:innenmengen sind erlaubt.
- :func:`is_full_match` -- zusätzlich exakt gleiche Schüler:innenmenge.
  Basis für "aktuell geladen" und die Duplikat-Sperre beim Erstellen.
"""

from __future__ import annotations

from app.core.domain.models_v4 import SeatingPlan, SeatingSnapshot, Seat
from app.core.domain.student_id import StudentId


def _plan_seats(plan: SeatingPlan) -> dict[StudentId, Seat]:
    """Gibt die aktuellen Sitzplätze aller Schüler:innen des Plans zurück.

    Args:
        plan: Sitzplan, dessen Schülerplätze gelesen werden.
    """
    return {s.student_id: s.seat for s in plan.classroom.students}


def positions_match(snapshot: SeatingSnapshot, plan: SeatingPlan) -> bool:
    """Prüft Positionsgleichheit zwischen *snapshot* und *plan*.

    Lehrertisch muss übereinstimmen; für alle Schüler:innen, die sowohl im
    Snapshot als auch im aktuellen Plan vorkommen, müssen die Koordinaten
    übereinstimmen. Unterschiedliche Schüler:innenmengen sind erlaubt (z. B.
    ein seitdem neu hinzugekommenes Kind bricht den Match nicht). Haben beide
    Zustände zusammen mindestens einen Sitzplatz, aber keine gemeinsame
    Schüler:in, gilt das als keine belegbare Gleichheit.

    Args:
        snapshot: Zu vergleichender Snapshot.
        plan: Aktueller Sitzplan.
    """
    ts_a, ts_b = snapshot.teacher_seat, plan.classroom.teacher_seat
    if (ts_a.x, ts_a.y) != (ts_b.x, ts_b.y):
        return False
    current = _plan_seats(plan)
    common = snapshot.seats.keys() & current.keys()
    if not common and (snapshot.seats or current):
        return False
    return all(
        (snapshot.seats[sid].x, snapshot.seats[sid].y) == (current[sid].x, current[sid].y)
        for sid in common
    )


def is_full_match(snapshot: SeatingSnapshot, plan: SeatingPlan) -> bool:
    """Prüft, ob *snapshot* den aktuellen Zustand von *plan* vollständig beschreibt.

    Positionsgleichheit (s. :func:`positions_match`) UND identische
    Schüler:innenmenge. Grundlage für die "aktuell geladen"-Markierung sowie
    die Duplikat-Sperre beim Erstellen eines neuen Snapshots.

    Args:
        snapshot: Zu vergleichender Snapshot.
        plan: Aktueller Sitzplan.
    """
    if snapshot.seats.keys() != _plan_seats(plan).keys():
        return False
    return positions_match(snapshot, plan)
