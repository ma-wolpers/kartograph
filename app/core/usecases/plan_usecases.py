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
            tablegroup_number=desk.tablegroup_number,
            tablegroup_shift_x=desk.tablegroup_shift_x,
            tablegroup_shift_y=desk.tablegroup_shift_y,
            tablegroup_rotation=desk.tablegroup_rotation,
        )

    next_plan.desks = [Desk(x=0, y=0, desk_type="teacher")]
    next_plan.desks.extend(transformed_students.values())
    normalize_tablegroups_in_place(next_plan)
    return next_plan
