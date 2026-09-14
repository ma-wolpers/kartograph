"""Usecases für Snapshots: benannte Momentaufnahmen der Tischkoordinaten.

Folgt exakt dem Deepcopy-Muster aus ``accommodation_usecases.py``: jeder
Usecase beginnt mit ``next_plan = deepcopy(plan)`` und mutiert danach
ausschließlich ``next_plan`` -- das eingehende ``plan`` bleibt in jedem Pfad
unangetastet, damit ältere, in ``PlanHistory`` gehaltene Zustände strukturell
isoliert bleiben (keine Referenzmutation möglich).

Kommunizieren ihr Ergebnis über explizite Result-Objekte statt impliziter
Signale (Plan-Identität, Listenlänge, Equality) -- Handler werten
ausschließlich ``result.created``/``result.changed`` aus.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from app.core.domain.models_v4 import Seat, SeatingPlan, SeatingSnapshot
from app.core.domain.snapshot_matching import is_full_match

SNAPSHOT_RESTORE_ROW_GAP = 1  # eine Leerzeile Abstand unterhalb des Snapshot-Bereichs


@dataclass(frozen=True)
class CreateSnapshotResult:
    """Ergebnis von :func:`create_snapshot`."""

    plan: SeatingPlan
    created: bool
    snapshot_id: str | None


@dataclass(frozen=True)
class SnapshotMutationResult:
    """Ergebnis von :func:`delete_snapshot`/:func:`rename_snapshot`/:func:`restore_snapshot`.

    Einheitliches Signal, ob überhaupt etwas geändert wurde (z. B. eine
    unbekannte ``snapshot_id`` -> ``changed=False``, ``plan`` unverändert).
    """

    plan: SeatingPlan
    changed: bool


def create_snapshot(plan: SeatingPlan, name: str) -> CreateSnapshotResult:
    """Legt einen neuen Snapshot aus den aktuellen Tischkoordinaten an.

    Erstellt keinen neuen Snapshot, wenn der aktuelle Zustand bereits einen
    bestehenden Snapshot vollständig entspricht (:func:`is_full_match`) --
    das ist die Duplikat-Sperre aus der Produktentscheidung.

    Args:
        plan: Ausgangsplan.
        name: Anzeigename des neuen Snapshots.
    """
    if any(is_full_match(s, plan) for s in plan.snapshots):
        return CreateSnapshotResult(plan=plan, created=False, snapshot_id=None)

    next_plan = deepcopy(plan)
    now = datetime.now().isoformat()
    snapshot_id = uuid.uuid4().hex
    snapshot = SeatingSnapshot(
        snapshot_id=snapshot_id,
        name=name.strip() or "Unbenannter Snapshot",
        created_at=now,
        last_used_at=now,
        teacher_seat=Seat(x=next_plan.classroom.teacher_seat.x, y=next_plan.classroom.teacher_seat.y),
        seats={s.student_id: Seat(x=s.seat.x, y=s.seat.y) for s in next_plan.classroom.students},
    )
    next_plan.snapshots.append(snapshot)
    return CreateSnapshotResult(plan=next_plan, created=True, snapshot_id=snapshot_id)


def delete_snapshot(plan: SeatingPlan, snapshot_id: str) -> SnapshotMutationResult:
    """Entfernt den Snapshot mit *snapshot_id*; der aktuelle Sitzplan bleibt unverändert.

    Args:
        plan: Ausgangsplan.
        snapshot_id: ID des zu löschenden Snapshots.
    """
    if plan.snapshot_by_id(snapshot_id) is None:
        return SnapshotMutationResult(plan=plan, changed=False)
    next_plan = deepcopy(plan)
    next_plan.snapshots = [s for s in next_plan.snapshots if s.snapshot_id != snapshot_id]
    return SnapshotMutationResult(plan=next_plan, changed=True)


def rename_snapshot(plan: SeatingPlan, snapshot_id: str, new_name: str) -> SnapshotMutationResult:
    """Benennt den Snapshot mit *snapshot_id* um; ändert nur ``name``.

    Args:
        plan: Ausgangsplan.
        snapshot_id: ID des umzubenennenden Snapshots.
        new_name: Neuer Anzeigename.
    """
    if plan.snapshot_by_id(snapshot_id) is None:
        return SnapshotMutationResult(plan=plan, changed=False)
    next_plan = deepcopy(plan)
    snapshot = next_plan.snapshot_by_id(snapshot_id)
    snapshot.name = new_name.strip() or "Unbenannter Snapshot"
    return SnapshotMutationResult(plan=next_plan, changed=True)


def restore_snapshot(plan: SeatingPlan, snapshot_id: str) -> SnapshotMutationResult:
    """Stellt die Tischkoordinaten von Snapshot *snapshot_id* wieder her.

    Setzt den Lehrertisch und die Sitzplätze aller Schüler:innen, die im
    Snapshot vorkommen. Schüler:innen, die im aktuellen Plan existieren, aber
    nicht im Snapshot enthalten sind (z. B. seitdem neu hinzugekommen),
    werden NICHT verworfen, sondern in einer neuen, horizontal zentrierten
    Reihe unterhalb aller Snapshot-Koordinaten platziert (s.
    ``_place_unmatched_students``). Aktualisiert ``last_used_at`` des
    geladenen Snapshots.

    Args:
        plan: Ausgangsplan.
        snapshot_id: ID des wiederherzustellenden Snapshots.
    """
    snapshot = plan.snapshot_by_id(snapshot_id)
    if snapshot is None:
        return SnapshotMutationResult(plan=plan, changed=False)

    next_plan = deepcopy(plan)
    target = next_plan.snapshot_by_id(snapshot_id)
    target.last_used_at = datetime.now().isoformat()

    next_plan.classroom.teacher_seat.x = target.teacher_seat.x
    next_plan.classroom.teacher_seat.y = target.teacher_seat.y
    for student in next_plan.classroom.students:
        seat = target.seats.get(student.student_id)
        if seat is not None:
            student.seat = Seat(x=seat.x, y=seat.y)

    _place_unmatched_students(next_plan, target)
    return SnapshotMutationResult(plan=next_plan, changed=True)


def _place_unmatched_students(next_plan: SeatingPlan, snapshot: SeatingSnapshot) -> None:
    """Platziert Schüler:innen, die nicht im Snapshot enthalten sind, in einer Spare-Row.

    Horizontal um x=0 zentriert, eine Leerzeile (``SNAPSHOT_RESTORE_ROW_GAP``)
    unterhalb aller Snapshot-Koordinaten (Schülerplätze + Lehrertisch). Kein
    Clamping auf den Canvas-Radius -- außerhalb liegende Tische sind ein
    bereits vom bestehenden Code behandelter Fall (``_count_out_of_bounds_desks``).

    Args:
        next_plan: Bereits deepcopy'ter Plan, dessen Schüler mutiert werden.
        snapshot: Snapshot, dessen ``seats`` als "gematcht" gelten.
    """
    matched_ids = snapshot.seats.keys()
    unmatched = [s for s in next_plan.classroom.students if s.student_id not in matched_ids]
    if not unmatched:
        return
    reference_ys = [seat.y for seat in snapshot.seats.values()] + [snapshot.teacher_seat.y]
    row_y = max(reference_ys) + SNAPSHOT_RESTORE_ROW_GAP + 1
    offset = len(unmatched) // 2
    for i, student in enumerate(unmatched):
        student.seat = Seat(x=i - offset, y=row_y)
