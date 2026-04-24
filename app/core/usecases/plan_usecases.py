from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import Desk, SeatingPlan
from app.core.domain.table_groups import normalize_tablegroups_in_place


def create_student_desk(plan: SeatingPlan, x: int, y: int) -> SeatingPlan:
    next_plan = deepcopy(plan)
    existing = next_plan.desk_at(x, y)
    if existing and existing.desk_type == "teacher":
        return next_plan
    if existing and existing.desk_type == "student":
        return next_plan
    next_plan.desks.append(Desk(x=x, y=y, desk_type="student"))
    normalize_tablegroups_in_place(next_plan)
    return next_plan


def delete_desk(plan: SeatingPlan, x: int, y: int) -> SeatingPlan:
    next_plan = deepcopy(plan)
    existing = next_plan.desk_at(x, y)
    if not existing:
        return next_plan
    if existing.desk_type == "teacher":
        return next_plan
    next_plan.without_desk_at(x, y)
    normalize_tablegroups_in_place(next_plan)
    return next_plan


def update_student_name(plan: SeatingPlan, x: int, y: int, name: str) -> SeatingPlan:
    next_plan = deepcopy(plan)
    desk = next_plan.desk_at(x, y)
    if not desk or desk.desk_type != "student":
        return next_plan
    desk.student_name = name.strip()
    return next_plan


def toggle_symbol(plan: SeatingPlan, x: int, y: int, symbol: str) -> SeatingPlan:
    next_plan = deepcopy(plan)
    desk = next_plan.desk_at(x, y)
    if not desk or desk.desk_type != "student":
        return next_plan
    current_count = int(desk.symbols.get(symbol, 0))
    next_count = (current_count + 1) % 4
    if next_count == 0:
        desk.symbols.pop(symbol, None)
    else:
        desk.symbols[symbol] = next_count
    return next_plan


def is_color_used(plan: SeatingPlan, color_key: str) -> bool:
    for desk in plan.desks:
        if desk.desk_type != "student":
            continue
        if color_key in desk.color_markers:
            return True
    return False


def set_color_meaning(plan: SeatingPlan, color_key: str, meaning: str) -> SeatingPlan:
    next_plan = deepcopy(plan)
    clean = meaning.strip()
    if clean:
        next_plan.color_meanings[color_key] = clean
    else:
        next_plan.color_meanings.pop(color_key, None)
    return next_plan


def cleanup_unused_color_meanings(plan: SeatingPlan) -> SeatingPlan:
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


def set_teacher_desk(plan: SeatingPlan, new_teacher_x: int, new_teacher_y: int) -> SeatingPlan:
    next_plan = deepcopy(plan)
    transformed_students: dict[tuple[int, int], Desk] = {}

    for desk in next_plan.desks:
        if desk.x == new_teacher_x and desk.y == new_teacher_y:
            continue
        if desk.desk_type == "teacher":
            continue
        nx = desk.x - new_teacher_x
        ny = desk.y - new_teacher_y
        transformed_students[(nx, ny)] = Desk(
            x=nx,
            y=ny,
            desk_type="student",
            student_name=desk.student_name,
            symbols=dict(desk.symbols),
            color_markers=list(desk.color_markers),
            tablegroup_number=desk.tablegroup_number,
            tablegroup_shift_x=desk.tablegroup_shift_x,
            tablegroup_shift_y=desk.tablegroup_shift_y,
            tablegroup_rotation=desk.tablegroup_rotation,
        )

    next_plan.desks = [Desk(x=0, y=0, desk_type="teacher")]
    next_plan.desks.extend(transformed_students.values())
    normalize_tablegroups_in_place(next_plan)
    return next_plan
