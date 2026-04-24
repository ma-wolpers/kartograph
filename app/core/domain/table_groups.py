from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from math import cos, radians, sin

from app.core.domain.models import Desk, SeatingPlan

TG_SHIFT_LIMIT = 0.49
TG_ROTATION_LIMIT = 45.0


@dataclass(frozen=True)
class TableGroupSettings:
    number: int
    shift_x: float
    shift_y: float
    rotation: float


@dataclass(frozen=True)
class DeskGeometry:
    desk: Desk
    center_x: float
    center_y: float
    polygon: tuple[tuple[float, float], ...]


def _sanitize_shift(value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(-TG_SHIFT_LIMIT, min(TG_SHIFT_LIMIT, parsed))


def _sanitize_rotation(value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(-TG_ROTATION_LIMIT, min(TG_ROTATION_LIMIT, parsed))


def _component_sort_key(component: list[Desk]) -> tuple[int, int]:
    min_x = min(desk.x for desk in component)
    min_y = min(desk.y for desk in component)
    return min_y, min_x


def build_student_components(plan: SeatingPlan) -> list[list[Desk]]:
    students = [desk for desk in plan.desks if desk.desk_type == "student"]
    if not students:
        return []

    by_coord = {(desk.x, desk.y): desk for desk in students}
    visited: set[tuple[int, int]] = set()
    components: list[list[Desk]] = []

    for desk in sorted(students, key=lambda item: (item.y, item.x)):
        start = (desk.x, desk.y)
        if start in visited:
            continue

        queue: deque[tuple[int, int]] = deque([start])
        visited.add(start)
        component: list[Desk] = []

        while queue:
            x, y = queue.popleft()
            node = by_coord.get((x, y))
            if node is None:
                continue
            component.append(node)

            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in visited:
                    continue
                if (nx, ny) not in by_coord:
                    continue
                visited.add((nx, ny))
                queue.append((nx, ny))

        components.append(component)

    components.sort(key=_component_sort_key)
    return components


def _pick_component_number(component: list[Desk]) -> int | None:
    numbers = [int(desk.tablegroup_number) for desk in component if int(desk.tablegroup_number) > 0]
    if not numbers:
        return None
    counts = Counter(numbers)
    number, _ = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return number


def _pick_component_shift_x(component: list[Desk]) -> float:
    return _sanitize_shift(component[0].tablegroup_shift_x if component else 0.0)


def _pick_component_shift_y(component: list[Desk]) -> float:
    return _sanitize_shift(component[0].tablegroup_shift_y if component else 0.0)


def _pick_component_rotation(component: list[Desk]) -> float:
    return _sanitize_rotation(component[0].tablegroup_rotation if component else 0.0)


def normalize_tablegroups_in_place(plan: SeatingPlan) -> None:
    components = build_student_components(plan)

    for desk in plan.desks:
        if desk.desk_type == "teacher":
            desk.tablegroup_number = 0
            desk.tablegroup_shift_x = 0.0
            desk.tablegroup_shift_y = 0.0
            desk.tablegroup_rotation = 0.0

    if not components:
        return

    assigned_numbers: set[int] = set()

    for component in components:
        preferred_number = _pick_component_number(component)
        if preferred_number is None or preferred_number in assigned_numbers:
            # Neue oder gesplittete Gruppen erhalten fortlaufend die naechste hoechste Nummer.
            number = (max(assigned_numbers) + 1) if assigned_numbers else 1
        else:
            number = preferred_number

        shift_x = _pick_component_shift_x(component)
        shift_y = _pick_component_shift_y(component)
        rotation = _pick_component_rotation(component)

        for desk in component:
            desk.tablegroup_number = number
            desk.tablegroup_shift_x = shift_x
            desk.tablegroup_shift_y = shift_y
            desk.tablegroup_rotation = rotation

        assigned_numbers.add(number)


def tablegroup_number_at(plan: SeatingPlan, x: int, y: int) -> int | None:
    desk = plan.desk_at(x, y)
    if desk is None or desk.desk_type != "student":
        return None
    number = int(desk.tablegroup_number)
    return number if number > 0 else None


def get_tablegroup_settings(plan: SeatingPlan, number: int) -> TableGroupSettings | None:
    if number <= 0:
        return None
    for desk in plan.desks:
        if desk.desk_type != "student":
            continue
        if int(desk.tablegroup_number) != number:
            continue
        return TableGroupSettings(
            number=number,
            shift_x=_sanitize_shift(desk.tablegroup_shift_x),
            shift_y=_sanitize_shift(desk.tablegroup_shift_y),
            rotation=_sanitize_rotation(desk.tablegroup_rotation),
        )
    return None


def set_tablegroup_number_with_cascade_in_place(plan: SeatingPlan, source_number: int, target_number: int) -> None:
    if source_number <= 0 or target_number <= 0 or source_number == target_number:
        return

    components = build_student_components(plan)
    if not components:
        return

    number_by_component: list[int] = []
    for component in components:
        number = int(component[0].tablegroup_number)
        number_by_component.append(number)

    try:
        source_idx = number_by_component.index(source_number)
    except ValueError:
        return

    occupied: dict[int, int] = {}
    for idx, number in enumerate(number_by_component):
        if number > 0:
            occupied[number] = idx

    old_number = number_by_component[source_idx]
    if occupied.get(old_number) == source_idx:
        occupied.pop(old_number, None)

    def push_up(number: int) -> None:
        if number not in occupied:
            return
        push_up(number + 1)
        occupied[number + 1] = occupied.pop(number)

    push_up(target_number)
    occupied[target_number] = source_idx

    for number, idx in occupied.items():
        for desk in components[idx]:
            desk.tablegroup_number = number


def set_tablegroup_transforms_in_place(
    plan: SeatingPlan,
    number: int,
    *,
    shift_x: float | None = None,
    shift_y: float | None = None,
    rotation: float | None = None,
) -> None:
    if number <= 0:
        return

    for desk in plan.desks:
        if desk.desk_type != "student":
            continue
        if int(desk.tablegroup_number) != number:
            continue
        if shift_x is not None:
            desk.tablegroup_shift_x = _sanitize_shift(shift_x)
        if shift_y is not None:
            desk.tablegroup_shift_y = _sanitize_shift(shift_y)
        if rotation is not None:
            desk.tablegroup_rotation = _sanitize_rotation(rotation)


def _desk_polygon(center_x: float, center_y: float, angle_degrees: float) -> tuple[tuple[float, float], ...]:
    angle = radians(angle_degrees)
    cos_v = cos(angle)
    sin_v = sin(angle)
    half = 0.5
    corners = [(-half, -half), (half, -half), (half, half), (-half, half)]

    points: list[tuple[float, float]] = []
    for dx, dy in corners:
        rx = dx * cos_v - dy * sin_v
        ry = dx * sin_v + dy * cos_v
        points.append((center_x + rx, center_y + ry))
    return tuple(points)


def build_desk_geometries(plan: SeatingPlan) -> list[DeskGeometry]:
    geometries: list[DeskGeometry] = []

    for desk in plan.desks:
        if desk.desk_type == "teacher":
            center_x = float(desk.x) + 0.5
            center_y = float(desk.y) + 0.5
            rotation = 0.0
        else:
            center_x = float(desk.x) + 0.5 + _sanitize_shift(desk.tablegroup_shift_x)
            center_y = float(desk.y) + 0.5 - _sanitize_shift(desk.tablegroup_shift_y)
            rotation = _sanitize_rotation(desk.tablegroup_rotation)

        polygon = _desk_polygon(center_x, center_y, rotation)
        geometries.append(
            DeskGeometry(
                desk=desk,
                center_x=center_x,
                center_y=center_y,
                polygon=polygon,
            )
        )

    return geometries


def _project_polygon(axis_x: float, axis_y: float, polygon: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    values = [point_x * axis_x + point_y * axis_y for point_x, point_y in polygon]
    return min(values), max(values)


def _polygons_overlap(poly_a: tuple[tuple[float, float], ...], poly_b: tuple[tuple[float, float], ...], eps: float = 1e-6) -> bool:
    axes: list[tuple[float, float]] = []
    for polygon in (poly_a, poly_b):
        for idx in range(len(polygon)):
            x1, y1 = polygon[idx]
            x2, y2 = polygon[(idx + 1) % len(polygon)]
            edge_x = x2 - x1
            edge_y = y2 - y1
            axis_x = -edge_y
            axis_y = edge_x
            if abs(axis_x) < eps and abs(axis_y) < eps:
                continue
            axes.append((axis_x, axis_y))

    for axis_x, axis_y in axes:
        min_a, max_a = _project_polygon(axis_x, axis_y, poly_a)
        min_b, max_b = _project_polygon(axis_x, axis_y, poly_b)
        overlap = min(max_a, max_b) - max(min_a, min_b)
        if overlap <= eps:
            return False

    return True


def detect_overlaps_for_tablegroup(plan: SeatingPlan, number: int) -> tuple[bool, bool]:
    geometries = build_desk_geometries(plan)
    target_indexes = [
        idx
        for idx, geometry in enumerate(geometries)
        if geometry.desk.desk_type == "student" and int(geometry.desk.tablegroup_number) == number
    ]
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

            if other.desk.desk_type == "teacher":
                teacher_overlap = True
            else:
                student_overlap = True

    return teacher_overlap, student_overlap


def group_bounds_from_geometries(geometries: list[DeskGeometry], number: int) -> tuple[float, float, float, float] | None:
    points: list[tuple[float, float]] = []
    for geometry in geometries:
        if geometry.desk.desk_type != "student":
            continue
        if int(geometry.desk.tablegroup_number) != number:
            continue
        points.extend(geometry.polygon)

    if not points:
        return None

    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return min_x, min_y, max_x, max_y


def list_tablegroup_numbers(plan: SeatingPlan) -> list[int]:
    numbers = {
        int(desk.tablegroup_number)
        for desk in plan.desks
        if desk.desk_type == "student" and int(desk.tablegroup_number) > 0
    }
    return sorted(numbers)
