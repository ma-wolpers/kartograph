from __future__ import annotations

import pytest

from app.core.domain.models import Desk, SeatingPlan
from app.core.domain.table_groups import (
    build_desk_geometries,
    normalize_tablegroups_in_place,
    selection_bounds_from_geometries,
    set_tablegroup_transforms_in_place,
    tablegroup_number_at,
)


def _plan_with(desks: list[Desk]) -> SeatingPlan:
    teacher = Desk(x=0, y=0, desk_type="teacher")
    return SeatingPlan(version=2, plan_id="test", name="Test", desks=[teacher, *desks])


def test_empty_desk_can_stay_in_named_tablegroup() -> None:
    plan = _plan_with(
        [
            Desk(
                x=1,
                y=1,
                desk_type="student",
                student_name="Alice",
                tablegroup_number=2,
                tablegroup_shift_x=0.25,
                tablegroup_shift_y=0.1,
                tablegroup_rotation=12.0,
            ),
            Desk(
                x=2,
                y=1,
                desk_type="student",
                student_name="",
                tablegroup_number=2,
                tablegroup_shift_x=-0.3,
                tablegroup_shift_y=-0.2,
                tablegroup_rotation=-20.0,
            ),
        ]
    )

    normalize_tablegroups_in_place(plan)

    named = plan.desk_at(1, 1)
    empty = plan.desk_at(2, 1)
    assert named is not None
    assert empty is not None
    assert int(named.tablegroup_number) == 2
    assert int(empty.tablegroup_number) == 2
    assert empty.tablegroup_shift_x == pytest.approx(named.tablegroup_shift_x)
    assert empty.tablegroup_shift_y == pytest.approx(named.tablegroup_shift_y)
    assert empty.tablegroup_rotation == pytest.approx(named.tablegroup_rotation)


def test_empty_only_component_cannot_form_tablegroup() -> None:
    plan = _plan_with(
        [
            Desk(x=1, y=1, desk_type="student", student_name="", tablegroup_number=7),
            Desk(x=2, y=1, desk_type="student", student_name="", tablegroup_number=7),
        ]
    )

    normalize_tablegroups_in_place(plan)

    first = plan.desk_at(1, 1)
    second = plan.desk_at(2, 1)
    assert first is not None
    assert second is not None
    assert int(first.tablegroup_number) == 0
    assert int(second.tablegroup_number) == 0
    assert first.tablegroup_shift_x == pytest.approx(0.0)
    assert first.tablegroup_shift_y == pytest.approx(0.0)
    assert first.tablegroup_rotation == pytest.approx(0.0)


def test_tablegroup_transforms_apply_to_empty_member() -> None:
    plan = _plan_with(
        [
            Desk(x=1, y=1, desk_type="student", student_name="Alice", tablegroup_number=1),
            Desk(x=2, y=1, desk_type="student", student_name="", tablegroup_number=1),
        ]
    )

    set_tablegroup_transforms_in_place(plan, 1, shift_x=0.4, shift_y=-0.3, rotation=30.0)

    named = plan.desk_at(1, 1)
    empty = plan.desk_at(2, 1)
    assert named is not None
    assert empty is not None
    assert empty.tablegroup_shift_x == pytest.approx(0.4)
    assert empty.tablegroup_shift_y == pytest.approx(-0.3)
    assert empty.tablegroup_rotation == pytest.approx(30.0)


def test_tablegroup_number_at_works_for_empty_student_desk() -> None:
    plan = _plan_with(
        [
            Desk(x=1, y=1, desk_type="student", student_name="", tablegroup_number=3),
        ]
    )

    assert tablegroup_number_at(plan, 1, 1) == 3


def test_selection_bounds_follow_transformed_desk_geometry() -> None:
    plan = _plan_with(
        [
            Desk(
                x=1,
                y=1,
                desk_type="student",
                student_name="Alice",
                tablegroup_number=1,
                tablegroup_shift_x=0.4,
                tablegroup_shift_y=0.2,
                tablegroup_rotation=30.0,
            )
        ]
    )

    geometries = build_desk_geometries(plan)
    bounds = selection_bounds_from_geometries(geometries, {(1, 1)})

    assert bounds is not None
    min_x, min_y, max_x, max_y = bounds
    assert min_x > 1.0
    assert min_y < 1.0
    assert max_x > 2.0
    assert max_y > 1.9


def test_selection_bounds_none_for_non_desk_cells() -> None:
    plan = _plan_with([Desk(x=1, y=1, desk_type="student", student_name="Alice", tablegroup_number=1)])

    geometries = build_desk_geometries(plan)
    bounds = selection_bounds_from_geometries(geometries, {(9, 9)})

    assert bounds is None
