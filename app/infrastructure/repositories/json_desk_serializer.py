"""Serialisierung eines SeatingPlan in ein JSON-kompatibles Dict.

Das resultierende Dict enthält nur saubere, validierte Werte und kann
direkt via ``json.dumps`` geschrieben werden. Einträge ohne Inhalt
(leere Symbole, Noten und Notizen) werden weggelassen.
"""

from __future__ import annotations

from app.core.domain.models import DocumentationEntry, SeatingPlan


def serialize_plan(plan: SeatingPlan) -> dict:
    """Wandelt *plan* in ein JSON-kompatibles Dict um.

    Verwendet werden ausschließlich saubere, validierte Werte:
    - Dokumentationseinträge ohne Inhalt werden ausgelassen.
    - Notenspalten mit ungültiger Kategorie oder doppelter ID werden ausgelassen.
    - Gewichtung 0/0 wird auf 50/50 normiert.

    Args:
        plan: Der zu serialisierende Sitzplan.

    Returns:
        Serialisiertes Dict, bereit für ``json.dumps``.
    """
    dates_in_use: set[str] = set()
    serialized_desks = []

    for desk in plan.desks:
        raw_entries = desk.documentation_entries or {}
        serialized_entries: dict[str, dict] = {}

        for raw_date, raw_entry in raw_entries.items():
            date_key = str(raw_date).strip()
            if not date_key:
                continue
            if not isinstance(raw_entry, DocumentationEntry):
                continue

            entry_symbols: dict[str, int] = {}
            for raw_symbol, raw_value in raw_entry.symbols.items():
                symbol = str(raw_symbol).strip()
                if not symbol:
                    continue
                try:
                    parsed_value = int(raw_value)
                except (TypeError, ValueError):
                    continue
                if 1 <= parsed_value <= 3:
                    entry_symbols[symbol] = parsed_value

            entry_grades: dict[str, float] = {}
            for raw_column_id, raw_grade in raw_entry.grades.items():
                column_id = str(raw_column_id).strip()
                if not column_id:
                    continue
                try:
                    parsed_grade = float(raw_grade)
                except (TypeError, ValueError):
                    continue
                entry_grades[column_id] = parsed_grade

            note = raw_entry.note.strip()
            if not entry_symbols and not entry_grades and not note:
                continue

            serialized_entries[date_key] = {
                "symbols": entry_symbols,
                "grades": entry_grades,
                "note": note,
            }
            dates_in_use.add(date_key)

        serialized_desks.append(
            {
                "x": desk.x,
                "y": desk.y,
                "type": desk.desk_type,
                "name": desk.student_name,
                "last_name": desk.student_last_name,
                "symbols": dict(desk.symbols),
                "color_markers": list(desk.color_markers),
                "tablegroup_number": int(desk.tablegroup_number),
                "tablegroup_shift_x": float(desk.tablegroup_shift_x),
                "tablegroup_shift_y": float(desk.tablegroup_shift_y),
                "tablegroup_rotation": float(desk.tablegroup_rotation),
                "documentation_entries": serialized_entries,
            }
        )

    serialized_grade_columns = []
    seen_column_ids: set[str] = set()
    for column in plan.grade_columns:
        column_id = str(column.column_id).strip()
        title = str(column.title).strip()
        category = str(column.category).strip().lower()
        if not column_id or column_id in seen_column_ids:
            continue
        if category not in {"schriftlich", "sonstig"}:
            continue
        serialized_grade_columns.append(
            {
                "id": column_id,
                "category": category,
                "title": title or column_id,
            }
        )
        seen_column_ids.add(column_id)

    try:
        written_weight = int(plan.written_weight_percent)
    except (TypeError, ValueError):
        written_weight = 50
    try:
        sonstige_weight = int(plan.sonstige_weight_percent)
    except (TypeError, ValueError):
        sonstige_weight = 50
    if written_weight + sonstige_weight <= 0:
        written_weight, sonstige_weight = 50, 50

    return {
        "version": max(int(plan.version), 3),
        "plan_id": plan.plan_id,
        "name": plan.name,
        "color_meanings": dict(plan.color_meanings),
        "documentation": {
            "dates": sorted(dates_in_use),
            "grade_columns": serialized_grade_columns,
            "grade_weighting": {
                "written_percent": written_weight,
                "sonstige_percent": sonstige_weight,
            },
        },
        "desks": serialized_desks,
    }
