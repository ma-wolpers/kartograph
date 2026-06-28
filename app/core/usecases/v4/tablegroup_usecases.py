"""Usecases für Tischgruppen-Operationen (Geometrie, Nummerierung, Validierung).

Im v4-Modell liegt die Geometrie einmalig pro Gruppe in ``TableGroup.seats``,
nicht redundant in jedem Schüler wie in v3 (``Desk.tablegroup_*``-Felder).
"""

from __future__ import annotations

from collections import Counter, deque
from copy import deepcopy
from dataclasses import dataclass

from app.core.domain.models_v4 import GroupSeat, SeatingPlan, TableGroup
from app.core.domain.table_groups import (
    _polygons_overlap,
    _sanitize_rotation,
    _sanitize_shift,
    build_seat_geometries_v4,
)


@dataclass(frozen=True)
class TableGroupSettings:
    group_id: int
    shift_x: float
    shift_y: float
    rotation: float


def _build_seat_components(plan: SeatingPlan) -> list[list[tuple[int, int]]]:
    """Gruppiert alle Schüler-Sitzplätze nach 4-Wege-Rasternachbarschaft.

    Args:
        plan: v4-Sitzplan, dessen Schülerplätze gruppiert werden.
    """
    seats = [(s.seat.x, s.seat.y) for s in plan.classroom.students]
    if not seats:
        return []
    occupied = set(seats)
    visited: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []

    for seat in sorted(seats, key=lambda item: (item[1], item[0])):
        if seat in visited:
            continue
        queue: deque[tuple[int, int]] = deque([seat])
        visited.add(seat)
        component: list[tuple[int, int]] = []
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in visited or (nx, ny) not in occupied:
                    continue
                visited.add((nx, ny))
                queue.append((nx, ny))
        components.append(component)

    components.sort(key=lambda comp: (min(y for _, y in comp), min(x for x, _ in comp)))
    return components


def normalize_tablegroups(plan: SeatingPlan) -> SeatingPlan:
    """Baut ``plan.tablegroups`` aus der physischen Sitznachbarschaft neu auf.

    Komponenten ohne benannten Schüler bilden keine eigene Gruppe. Bestehende
    Gruppennummern und Geometrie-Offsets bleiben erhalten, wo möglich.

    Args:
        plan: Ausgangsplan.

    Returns:
        Neuer Plan mit aktualisierten Tischgruppen.
    """
    next_plan = deepcopy(plan)
    components = _build_seat_components(next_plan)

    seat_lookup = {(s.seat.x, s.seat.y): s for s in next_plan.classroom.students}
    old_group_by_seat: dict[tuple[int, int], int] = {}
    old_geom_by_seat: dict[tuple[int, int], tuple[float, float, float]] = {}
    for group in next_plan.tablegroups:
        for gs in group.seats:
            old_group_by_seat[(gs.x, gs.y)] = group.group_id
            old_geom_by_seat[(gs.x, gs.y)] = (gs.shift_x, gs.shift_y, gs.rotation)

    if not components:
        next_plan.tablegroups = []
        return next_plan

    valid_components = [comp for comp in components if any(seat_lookup[xy].is_named() for xy in comp)]
    if not valid_components:
        next_plan.tablegroups = []
        return next_plan

    def pick_number(component: list[tuple[int, int]]) -> int | None:
        numbers = [old_group_by_seat[xy] for xy in component if old_group_by_seat.get(xy, 0) > 0]
        if not numbers:
            return None
        counts = Counter(numbers)
        number, _ = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        return number

    def pick_geometry(component: list[tuple[int, int]]) -> tuple[float, float, float]:
        named = [xy for xy in component if seat_lookup[xy].is_named()]
        reference = named[0] if named else component[0]
        shift_x, shift_y, rotation = old_geom_by_seat.get(reference, (0.0, 0.0, 0.0))
        return _sanitize_shift(shift_x), _sanitize_shift(shift_y), _sanitize_rotation(rotation)

    max_existing_number = max(
        (number for number in (pick_number(component) for component in valid_components) if number is not None),
        default=0,
    )
    assigned_numbers: set[int] = set()
    next_new_number = max_existing_number + 1
    new_groups: list[TableGroup] = []

    for component in valid_components:
        preferred_number = pick_number(component)
        if preferred_number is None or preferred_number in assigned_numbers:
            number = next_new_number
            next_new_number += 1
        else:
            number = preferred_number

        shift_x, shift_y, rotation = pick_geometry(component)
        seats = [GroupSeat(x=x, y=y, shift_x=shift_x, shift_y=shift_y, rotation=rotation) for x, y in component]
        new_groups.append(TableGroup(group_id=number, seats=seats))
        assigned_numbers.add(number)

    next_plan.tablegroups = new_groups
    return next_plan


def tablegroup_number_at(plan: SeatingPlan, x: int, y: int) -> int | None:
    """Gibt die Tischgruppen-ID an Position (*x*, *y*) zurück, oder ``None``.

    Args:
        plan: v4-Sitzplan, in dem die Position gesucht wird.
        x: X-Rasterkoordinate des Sitzplatzes.
        y: Y-Rasterkoordinate des Sitzplatzes.
    """
    group = plan.tablegroup_for_seat(x, y)
    return group.group_id if group is not None else None


def get_tablegroup_settings(plan: SeatingPlan, group_id: int) -> TableGroupSettings | None:
    """Gibt die Geometrie-Einstellungen einer Tischgruppe zurück, oder ``None``.

    Args:
        plan: v4-Sitzplan, in dem die Tischgruppe gesucht wird.
        group_id: ID der gesuchten Tischgruppe.
    """
    if group_id <= 0:
        return None
    for group in plan.tablegroups:
        if group.group_id != group_id or not group.seats:
            continue
        gs = group.seats[0]
        return TableGroupSettings(
            group_id=group_id,
            shift_x=_sanitize_shift(gs.shift_x),
            shift_y=_sanitize_shift(gs.shift_y),
            rotation=_sanitize_rotation(gs.rotation),
        )
    return None


def set_tablegroup_number_with_cascade(plan: SeatingPlan, source_number: int, target_number: int) -> SeatingPlan:
    """Weist einer Tischgruppe *target_number* zu und kaskadiert Konflikte nach oben.

    Args:
        plan: Ausgangsplan (sollte bereits normalisiert sein).
        source_number: Bisherige Gruppennummer.
        target_number: Gewünschte neue Gruppennummer.

    Returns:
        Neuer Plan mit aktualisierten Gruppennummern.
    """
    if source_number <= 0 or target_number <= 0 or source_number == target_number:
        return deepcopy(plan)

    next_plan = deepcopy(plan)
    groups = next_plan.tablegroups
    ids = [g.group_id for g in groups]
    if source_number not in ids:
        return next_plan

    source_idx = ids.index(source_number)
    occupied: dict[int, int] = {gid: idx for idx, gid in enumerate(ids) if gid > 0}
    if occupied.get(source_number) == source_idx:
        occupied.pop(source_number, None)

    def push_up(number: int) -> None:
        if number not in occupied:
            return
        push_up(number + 1)
        occupied[number + 1] = occupied.pop(number)

    push_up(target_number)
    occupied[target_number] = source_idx

    for number, idx in occupied.items():
        groups[idx].group_id = number
    return next_plan


def set_tablegroup_transforms(
    plan: SeatingPlan,
    group_id: int,
    *,
    shift_x: float | None = None,
    shift_y: float | None = None,
    rotation: float | None = None,
) -> SeatingPlan:
    """Setzt Geometrie-Offsets aller Sitzplätze einer Tischgruppe.

    ``None``-Werte lassen das jeweilige Feld unverändert.

    Args:
        plan: Ausgangsplan, dessen Tischgruppe verändert wird.
        group_id: ID der zu verändernden Tischgruppe.
        shift_x: Neuer X-Versatz; bleibt unverändert, wenn None.
        shift_y: Neuer Y-Versatz; bleibt unverändert, wenn None.
        rotation: Neue Rotation; bleibt unverändert, wenn None.
    """
    next_plan = deepcopy(plan)
    if group_id <= 0:
        return next_plan
    for group in next_plan.tablegroups:
        if group.group_id != group_id:
            continue
        for gs in group.seats:
            if shift_x is not None:
                gs.shift_x = _sanitize_shift(shift_x)
            if shift_y is not None:
                gs.shift_y = _sanitize_shift(shift_y)
            if rotation is not None:
                gs.rotation = _sanitize_rotation(rotation)
    return next_plan


def detect_overlaps_for_tablegroup(plan: SeatingPlan, group_id: int) -> tuple[bool, bool]:
    """Prüft, ob eine Tischgruppe nach ihren Offsets mit Lehrertisch/anderen Plätzen überlappt.

    Args:
        plan: v4-Sitzplan mit allen Sitzplätzen.
        group_id: ID der zu prüfenden Tischgruppe.

    Returns:
        Tupel ``(teacher_overlap, student_overlap)``.
    """
    geometries = build_seat_geometries_v4(plan)
    target_indexes = [idx for idx, g in enumerate(geometries) if not g.is_teacher and g.group_id == group_id]
    if not target_indexes:
        return False, False

    teacher_overlap = False
    student_overlap = False
    seen_pairs: set[tuple[int, int]] = set()

    for target_idx in target_indexes:
        target_poly = geometries[target_idx].polygon
        for other_idx, other in enumerate(geometries):
            if target_idx == other_idx:
                continue
            pair = (min(target_idx, other_idx), max(target_idx, other_idx))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            if not _polygons_overlap(target_poly, other.polygon):
                continue

            if other.is_teacher:
                teacher_overlap = True
            else:
                student_overlap = True

    return teacher_overlap, student_overlap
