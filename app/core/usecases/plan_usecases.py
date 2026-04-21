from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import Desk, SeatingPlan


def create_student_desk(plan: SeatingPlan, x: int, y: int) -> SeatingPlan:
    next_plan = deepcopy(plan)
    existing = next_plan.desk_at(x, y)
    if existing and existing.desk_type == "teacher":
        return next_plan
    if existing and existing.desk_type == "student":
        return next_plan
    next_plan.desks.append(Desk(x=x, y=y, desk_type="student"))
    return next_plan


def delete_desk(plan: SeatingPlan, x: int, y: int) -> SeatingPlan:
    next_plan = deepcopy(plan)
    existing = next_plan.desk_at(x, y)
    if not existing:
        return next_plan
    if existing.desk_type == "teacher":
        return next_plan
    next_plan.without_desk_at(x, y)
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
    if symbol in desk.symbols:
        desk.symbols = [value for value in desk.symbols if value != symbol]
    else:
        desk.symbols.append(symbol)
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
            symbols=list(desk.symbols),
        )

    next_plan.desks = [Desk(x=0, y=0, desk_type="teacher")]
    next_plan.desks.extend(transformed_students.values())
    return next_plan
