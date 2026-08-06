"""Deserialisierung eines JSON-Dicts in einen SeatingPlan.

Alle Eingabedaten aus JSON werden misstrauisch behandelt: Typfehler,
fehlende Schlüssel und ungültige Werte werden abgefangen und durch
Standardwerte ersetzt oder führen zu einem ``ValueError``.
"""

from __future__ import annotations

import uuid

from app.core.domain.models import Desk, DocumentationEntry, GradeColumnDefinition, SeatingPlan
from app.core.domain.table_groups import normalize_tablegroups_in_place


def _coerce_int(raw_value: object, default: int) -> int:
    """Konvertiert *raw_value* sicher in int; bei Fehler wird *default* zurückgegeben.

    Args:
        raw_value: Roher, beliebig typisierter Eingabewert.
        default: Rückgabewert, falls die Konvertierung fehlschlägt.
    """
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def _coerce_float(raw_value: object, default: float) -> float:
    """Konvertiert *raw_value* sicher in float; bei Fehler wird *default* zurückgegeben.

    Args:
        raw_value: Roher, beliebig typisierter Eingabewert.
        default: Rückgabewert, falls die Konvertierung fehlschlägt.
    """
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def _deserialize_desk(item: dict, documentation_dates: list[str]) -> Desk:
    """Deserialisiert einen einzelnen Tisch aus einem JSON-Dict.

    Neu entdeckte Dokumentationsdaten (die bisher nicht in *documentation_dates*
    stehen) werden direkt in die übergebene Liste eingetragen.

    Args:
        item: Roh-Dict eines Tisches aus der JSON-Datei.
        documentation_dates: Mutable Liste globaler Dokumentationsdaten; wird
            bei Bedarf erweitert.

    Returns:
        Fertig deserialisiertes ``Desk``-Objekt.

    Raises:
        ValueError: Wenn Typ oder Koordinaten fehlen/ungültig sind.
    """
    x = int(item.get("x"))
    y = int(item.get("y"))
    desk_type = str(item.get("type"))
    if desk_type not in {"teacher", "student"}:
        raise ValueError("desk type must be teacher or student")

    # --- Tisch-eigene Symbole (z.B. "Laptop") ---
    symbols_raw = item.get("symbols") or {}
    desk_symbols: dict[str, int] = {}
    if isinstance(symbols_raw, list):
        # Legacy: ["Laptop", "Tablet"] → {"Laptop": 1, "Tablet": 1}
        for raw_symbol in symbols_raw:
            name = str(raw_symbol).strip()
            if name:
                desk_symbols[name] = 1
    elif isinstance(symbols_raw, dict):
        for raw_symbol, raw_count in symbols_raw.items():
            name = str(raw_symbol).strip()
            if not name:
                continue
            try:
                parsed = int(raw_count)
            except (TypeError, ValueError):
                continue
            if 1 <= parsed <= 3:
                desk_symbols[name] = parsed
    else:
        raise ValueError("symbols must be a list or object")

    # --- Farbmarker ---
    color_markers_raw = item.get("color_markers") or []
    color_markers: list[str] = []
    if isinstance(color_markers_raw, list):
        for raw_color in color_markers_raw:
            color_key = str(raw_color).strip()
            if color_key and color_key not in color_markers:
                color_markers.append(color_key)
    elif isinstance(color_markers_raw, str):
        color_key = color_markers_raw.strip()
        if color_key:
            color_markers.append(color_key)
    else:
        raise ValueError("color_markers must be a list or string")

    # --- Dokumentationseinträge ---
    documentation_entries: dict[str, DocumentationEntry] = {}
    doc_entries_raw = item.get("documentation_entries")
    if isinstance(doc_entries_raw, dict):
        for raw_date, raw_entry in doc_entries_raw.items():
            date_key = str(raw_date).strip()
            if not date_key or not isinstance(raw_entry, dict):
                continue

            entry_symbols: dict[str, int] = {}
            entry_symbols_raw = raw_entry.get("symbols")
            if isinstance(entry_symbols_raw, dict):
                for raw_sym, raw_count in entry_symbols_raw.items():
                    sym_name = str(raw_sym).strip()
                    if not sym_name:
                        continue
                    try:
                        parsed_count = int(raw_count)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= parsed_count <= 3:
                        entry_symbols[sym_name] = parsed_count

            entry_grades: dict[str, float] = {}
            entry_grades_raw = raw_entry.get("grades")
            if isinstance(entry_grades_raw, dict):
                for raw_col_id, raw_grade in entry_grades_raw.items():
                    col_id = str(raw_col_id).strip()
                    if not col_id:
                        continue
                    try:
                        parsed_grade = float(raw_grade)
                    except (TypeError, ValueError):
                        continue
                    entry_grades[col_id] = parsed_grade

            note = str(raw_entry.get("note") or "").strip()
            entry = DocumentationEntry(symbols=entry_symbols, grades=entry_grades, note=note)
            if entry.has_content():
                documentation_entries[date_key] = entry
                if date_key not in documentation_dates:
                    documentation_dates.append(date_key)

    return Desk(
        x=x,
        y=y,
        desk_type=desk_type,
        student_name=str(item.get("name") or "").strip(),
        student_last_name=str(item.get("last_name") or "").strip(),
        symbols=desk_symbols,
        color_markers=color_markers,
        tablegroup_number=_coerce_int(item.get("tablegroup_number", 0), 0),
        tablegroup_shift_x=_coerce_float(item.get("tablegroup_shift_x", 0.0), 0.0),
        tablegroup_shift_y=_coerce_float(item.get("tablegroup_shift_y", 0.0), 0.0),
        tablegroup_rotation=_coerce_float(item.get("tablegroup_rotation", 0.0), 0.0),
        documentation_entries=documentation_entries,
    )


def deserialize_plan(payload: dict) -> SeatingPlan:
    """Deserialisiert ein JSON-Dict in einen vollständigen ``SeatingPlan``.

    Args:
        payload: JSON-Payload der Plandatei.

    Returns:
        Vollständig deserialisierter und normalisierter ``SeatingPlan``.

    Raises:
        ValueError: Bei strukturellen Fehlern (fehlende Tische, mehrere
            Lehrertische, Lehrertisch nicht auf (0, 0)).
    """
    version = int(payload.get("version", 1))
    plan_id = str(payload.get("plan_id") or uuid.uuid4().hex)
    name = str(payload.get("name") or "Unbenannter Sitzplan")

    doc_payload = payload.get("documentation") if isinstance(payload.get("documentation"), dict) else {}
    dates_raw = doc_payload.get("dates") if isinstance(doc_payload, dict) else []
    documentation_dates: list[str] = []
    if isinstance(dates_raw, list):
        for raw_date in dates_raw:
            date_key = str(raw_date).strip()
            if date_key and date_key not in documentation_dates:
                documentation_dates.append(date_key)

    grade_columns_raw = doc_payload.get("grade_columns") if isinstance(doc_payload, dict) else []
    grade_columns: list[GradeColumnDefinition] = []
    if isinstance(grade_columns_raw, list):
        for raw_col in grade_columns_raw:
            if not isinstance(raw_col, dict):
                continue
            col_id = str(raw_col.get("id") or "").strip()
            category = str(raw_col.get("category") or "").strip().lower()
            title = str(raw_col.get("title") or "").strip()
            if not col_id or category not in {"schriftlich", "sonstig"}:
                continue
            if any(existing.column_id == col_id for existing in grade_columns):
                continue
            grade_columns.append(
                GradeColumnDefinition(
                    column_id=col_id,
                    category=category,  # type: ignore[arg-type]
                    title=title or col_id,
                )
            )

    grade_weighting = doc_payload.get("grade_weighting") if isinstance(doc_payload, dict) else {}
    if not isinstance(grade_weighting, dict):
        grade_weighting = {}
    written_weight = _coerce_int(grade_weighting.get("written_percent", 50), 50)
    sonstige_weight = _coerce_int(grade_weighting.get("sonstige_percent", 50), 50)
    if written_weight + sonstige_weight <= 0:
        written_weight, sonstige_weight = 50, 50

    color_meanings_raw = payload.get("color_meanings") or {}
    color_meanings: dict[str, str] = {}
    if isinstance(color_meanings_raw, dict):
        for raw_key, raw_meaning in color_meanings_raw.items():
            key = str(raw_key).strip()
            meaning = str(raw_meaning).strip()
            if key and meaning:
                color_meanings[key] = meaning

    raw_desks = payload.get("desks")
    if not isinstance(raw_desks, list):
        raise ValueError("desks must be a list")

    desks: list[Desk] = []
    for item in raw_desks:
        if not isinstance(item, dict):
            raise ValueError("desk entry must be an object")
        desks.append(_deserialize_desk(item, documentation_dates))

    teacher_count = sum(1 for desk in desks if desk.desk_type == "teacher")
    if teacher_count != 1:
        raise ValueError("plan must contain exactly one teacher desk")
    if not any(desk.x == 0 and desk.y == 0 and desk.desk_type == "teacher" for desk in desks):
        raise ValueError("teacher desk must be at (0, 0)")

    used_colors = {
        color_key
        for desk in desks
        if desk.desk_type == "student"
        for color_key in desk.color_markers
    }
    normalized_color_meanings = {k: v for k, v in color_meanings.items() if k in used_colors}

    plan = SeatingPlan(
        version=max(version, 3),
        plan_id=plan_id,
        name=name,
        desks=desks,
        color_meanings=normalized_color_meanings,
        documentation_dates=sorted(set(documentation_dates)),
        grade_columns=grade_columns,
        written_weight_percent=written_weight,
        sonstige_weight_percent=sonstige_weight,
    )
    normalize_tablegroups_in_place(plan)
    return plan
