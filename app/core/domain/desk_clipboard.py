from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import Desk, SeatingPlan


class DeskClipboard:
    def __init__(self):
        self._payload: dict[tuple[int, int], Desk] = {}
        self._width = 0
        self._height = 0

    def has_content(self) -> bool:
        return bool(self._payload)

    def copy_from_plan(self, plan: SeatingPlan, cells: list[tuple[int, int]]) -> int:
        if not cells:
            self._payload = {}
            self._width = 0
            self._height = 0
            return 0

        xs = [x for x, _y in cells]
        ys = [y for _x, y in cells]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        self._payload = {}
        self._width = max_x - min_x + 1
        self._height = max_y - min_y + 1

        for x, y in cells:
            desk = plan.desk_at(x, y)
            if not desk or desk.desk_type != "student":
                continue
            rel = (x - min_x, y - min_y)
            self._payload[rel] = Desk(
                x=rel[0],
                y=rel[1],
                desk_type="student",
                student_name=desk.student_name,
                symbols=dict(desk.symbols),
                tablegroup_number=desk.tablegroup_number,
                tablegroup_shift_x=desk.tablegroup_shift_x,
                tablegroup_shift_y=desk.tablegroup_shift_y,
                tablegroup_rotation=desk.tablegroup_rotation,
            )

        return len(self._payload)

    def cut_from_plan(self, plan: SeatingPlan, cells: list[tuple[int, int]]) -> tuple[SeatingPlan, int, int]:
        copied = self.copy_from_plan(plan, cells)
        next_plan = deepcopy(plan)
        removed = 0
        for x, y in cells:
            desk = next_plan.desk_at(x, y)
            if not desk or desk.desk_type != "student":
                continue
            next_plan.without_desk_at(x, y)
            removed += 1
        return next_plan, copied, removed

    def paste_into_plan(
        self,
        plan: SeatingPlan,
        target_x: int,
        target_y: int,
        min_bound: int,
        max_bound: int,
    ) -> tuple[SeatingPlan, int, bool]:
        next_plan = deepcopy(plan)
        if not self._payload:
            return next_plan, 0, False

        teacher_conflict = False
        pasted_count = 0

        for (dx, dy), source in self._payload.items():
            x = target_x + dx
            y = target_y + dy
            if x < min_bound or x > max_bound or y < min_bound or y > max_bound:
                continue

            existing = next_plan.desk_at(x, y)
            if existing and existing.desk_type == "teacher":
                teacher_conflict = True
                continue
            if existing and existing.desk_type == "student":
                next_plan.without_desk_at(x, y)

            next_plan.desks.append(
                Desk(
                    x=x,
                    y=y,
                    desk_type="student",
                    student_name=source.student_name,
                    symbols=dict(source.symbols),
                    tablegroup_number=source.tablegroup_number,
                    tablegroup_shift_x=source.tablegroup_shift_x,
                    tablegroup_shift_y=source.tablegroup_shift_y,
                    tablegroup_rotation=source.tablegroup_rotation,
                )
            )
            pasted_count += 1

        return next_plan, pasted_count, teacher_conflict
