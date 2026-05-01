from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.domain.models import Desk, DocumentationEntry, GradeCategory, GradeColumnDefinition, SeatingPlan
from app.core.domain.table_groups import normalize_tablegroups_in_place


def _today_iso() -> str:
    return date.today().isoformat()


def _normalize_doc_date(value: str | None) -> str:
    clean = str(value or "").strip()
    return clean or _today_iso()


def _round_half_up_to_int(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_half_up_to_two_decimals(value: float) -> float:
    rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(rounded)


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


def ensure_documentation_date(plan: SeatingPlan, value: str | None = None) -> SeatingPlan:
    next_plan = deepcopy(plan)
    date_key = _normalize_doc_date(value)
    if date_key not in next_plan.documentation_dates:
        next_plan.documentation_dates.append(date_key)
        next_plan.documentation_dates.sort()
    return next_plan


def rename_documentation_date(plan: SeatingPlan, old_date: str, new_date: str) -> SeatingPlan:
    clean_old = str(old_date or "").strip()
    clean_new = _normalize_doc_date(new_date)
    if not clean_old:
        return deepcopy(plan)

    next_plan = deepcopy(plan)
    for desk in next_plan.desks:
        if not desk.is_named_student():
            continue
        old_entry = desk.documentation_entries.get(clean_old)
        if old_entry is None:
            continue
        existing_new = desk.documentation_entries.get(clean_new)
        if existing_new is None:
            desk.documentation_entries[clean_new] = old_entry
        else:
            existing_new.symbols.update(old_entry.symbols)
            existing_new.grades.update(old_entry.grades)
            if old_entry.note.strip() and not existing_new.note.strip():
                existing_new.note = old_entry.note.strip()
        desk.documentation_entries.pop(clean_old, None)

    next_plan.documentation_dates = [date_key for date_key in next_plan.documentation_dates if date_key != clean_old]
    if clean_new not in next_plan.documentation_dates:
        next_plan.documentation_dates.append(clean_new)
    next_plan.documentation_dates.sort()
    return next_plan


def set_documentation_symbol(
    plan: SeatingPlan,
    x: int,
    y: int,
    symbol: str,
    strength: int,
    doc_date: str | None = None,
) -> SeatingPlan:
    clean_symbol = str(symbol or "").strip()
    if not clean_symbol:
        return deepcopy(plan)

    next_plan = ensure_documentation_date(plan, doc_date)
    desk = next_plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return next_plan

    date_key = _normalize_doc_date(doc_date)
    entry = desk.documentation_entries.get(date_key)
    if entry is None:
        entry = DocumentationEntry()
        desk.documentation_entries[date_key] = entry

    try:
        parsed_strength = int(strength)
    except (TypeError, ValueError):
        parsed_strength = 0
    if parsed_strength <= 0:
        entry.symbols.pop(clean_symbol, None)
    else:
        entry.symbols[clean_symbol] = max(1, min(3, parsed_strength))

    if not entry.has_content():
        desk.documentation_entries.pop(date_key, None)
    return next_plan


def add_grade_column(plan: SeatingPlan, category: GradeCategory, title: str) -> tuple[SeatingPlan, str]:
    clean_category = str(category).strip().lower()
    if clean_category not in {"schriftlich", "sonstig"}:
        return deepcopy(plan), ""

    clean_title = str(title or "").strip() or f"{clean_category.title()} {len(plan.grade_columns) + 1}"
    next_plan = deepcopy(plan)
    column_id = uuid.uuid4().hex[:8]
    next_plan.grade_columns.append(
        GradeColumnDefinition(
            column_id=column_id,
            category=clean_category,  # type: ignore[arg-type]
            title=clean_title,
        )
    )
    return next_plan, column_id


def set_documentation_grade(
    plan: SeatingPlan,
    x: int,
    y: int,
    column_id: str,
    grade: float | None,
    doc_date: str | None = None,
) -> SeatingPlan:
    clean_column_id = str(column_id or "").strip()
    if not clean_column_id:
        return deepcopy(plan)

    if all(item.column_id != clean_column_id for item in plan.grade_columns):
        return deepcopy(plan)

    next_plan = ensure_documentation_date(plan, doc_date)
    desk = next_plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return next_plan

    date_key = _normalize_doc_date(doc_date)
    entry = desk.documentation_entries.get(date_key)
    if entry is None:
        entry = DocumentationEntry()
        desk.documentation_entries[date_key] = entry

    if grade is None:
        entry.grades.pop(clean_column_id, None)
    else:
        entry.grades[clean_column_id] = max(1.0, min(6.0, float(grade)))

    if not entry.has_content():
        desk.documentation_entries.pop(date_key, None)
    return next_plan


def set_grade_weighting(plan: SeatingPlan, written_percent: int, sonstige_percent: int) -> SeatingPlan:
    next_plan = deepcopy(plan)
    wp = max(0, int(written_percent))
    sp = max(0, int(sonstige_percent))
    if wp + sp <= 0:
        wp, sp = 50, 50
    next_plan.written_weight_percent = wp
    next_plan.sonstige_weight_percent = sp
    return next_plan


def summarize_latest_symbols_for_student(plan: SeatingPlan, x: int, y: int) -> dict[str, int]:
    desk = plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return {}

    summary: dict[str, int] = {}
    for date_key in sorted(desk.documentation_entries.keys()):
        entry = desk.documentation_entries[date_key]
        for symbol, strength in entry.symbols.items():
            summary[symbol] = strength
    return summary


def compute_grade_display_for_student(plan: SeatingPlan, x: int, y: int) -> str:
    desk = plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return ""

    category_by_column: dict[str, str] = {column.column_id: column.category for column in plan.grade_columns}
    written_values: list[float] = []
    sonstige_values: list[float] = []

    for date_key in sorted(desk.documentation_entries.keys()):
        entry = desk.documentation_entries[date_key]
        for column_id, grade_value in entry.grades.items():
            category = category_by_column.get(column_id)
            if category == "schriftlich":
                written_values.append(float(grade_value))
            elif category == "sonstig":
                sonstige_values.append(float(grade_value))

    if not written_values and not sonstige_values:
        return ""

    written_avg = sum(written_values) / len(written_values) if written_values else None
    sonstige_avg = sum(sonstige_values) / len(sonstige_values) if sonstige_values else None

    if written_avg is not None and sonstige_avg is not None:
        written_rounded = _round_half_up_to_int(written_avg)
        sonstige_rounded = _round_half_up_to_int(sonstige_avg)
        total_weight = int(plan.written_weight_percent) + int(plan.sonstige_weight_percent)
        if total_weight <= 0:
            total_weight = 100
        overall = (
            written_rounded * int(plan.written_weight_percent)
            + sonstige_rounded * int(plan.sonstige_weight_percent)
        ) / total_weight
        return f"{_round_half_up_to_two_decimals(overall):.2f}"

    partial_value = written_avg if written_avg is not None else sonstige_avg
    assert partial_value is not None
    return f"({_round_half_up_to_int(partial_value)})"


def compute_grade_subtotal_display_for_student(plan: SeatingPlan, x: int, y: int, category: GradeCategory) -> str:
    desk = plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return ""

    clean_category = str(category).strip().lower()
    if clean_category not in {"schriftlich", "sonstig"}:
        return ""

    valid_column_ids = {item.column_id for item in plan.grade_columns if item.category == clean_category}
    if not valid_column_ids:
        return ""

    values: list[float] = []
    for date_key in sorted(desk.documentation_entries.keys()):
        entry = desk.documentation_entries[date_key]
        for column_id, grade_value in entry.grades.items():
            if column_id in valid_column_ids:
                values.append(float(grade_value))

    if not values:
        return ""

    avg_value = sum(values) / len(values)
    return str(_round_half_up_to_int(avg_value))


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
            documentation_entries=deepcopy(desk.documentation_entries),
        )

    next_plan.desks = [Desk(x=0, y=0, desk_type="teacher")]
    next_plan.desks.extend(transformed_students.values())
    normalize_tablegroups_in_place(next_plan)
    return next_plan
