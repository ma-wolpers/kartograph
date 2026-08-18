"""Serialisierung eines SeatingPlan (v4) in ein JSON-kompatibles Dict.

Das Ergebnis entspricht dem v4-Schema aus ``docs/architecture-plan-v2.md``.
Einträge ohne Inhalt (leere Session-Entries) werden weggelassen; leere
Sessions werden komplett übersprungen.
"""

from __future__ import annotations

from app.core.domain.models_v4 import SeatingPlan


def serialize_plan(plan: SeatingPlan) -> dict:
    """Wandelt *plan* in ein JSON-kompatibles Dict (Format v4) um.

    Args:
        plan: Zu serialisierender Sitzplan (v4-Domänenmodell).

    Returns:
        Dict, das direkt via ``json.dumps`` gespeichert werden kann.
    """
    return {
        "format_version": 4,
        "plan_id": plan.plan_id,
        "meta": _serialize_meta(plan),
        "classroom": _serialize_classroom(plan),
        "tablegroups": _serialize_tablegroups(plan),
        "color_palette": _serialize_color_palette(plan),
        "documentation": _serialize_documentation(plan),
    }


# ---------------------------------------------------------------------------
# Interne Hilfsfunktionen
# ---------------------------------------------------------------------------

def _serialize_meta(plan: SeatingPlan) -> dict:
    """Wandelt ``plan.meta`` in ein JSON-Dict um.

    Args:
        plan: Sitzplan, dessen Metadaten serialisiert werden.
    """
    return {
        "name": plan.meta.name,
        "school_year": plan.meta.school_year,
        "created_at": plan.meta.created_at,
        "last_modified": plan.meta.last_modified,
    }


def _serialize_classroom(plan: SeatingPlan) -> dict:
    """Wandelt Lehrertisch und alle Schüler von *plan* in ein JSON-Dict um.

    Args:
        plan: Sitzplan, dessen Klassenraum serialisiert wird.
    """
    ts = plan.classroom.teacher_seat
    return {
        "teacher_seat": {"x": ts.x, "y": ts.y},
        "students": [_serialize_student(s) for s in plan.classroom.students],
    }


def _serialize_student(student) -> dict:
    """Wandelt einen einzelnen Schüler samt Diagnoseprofil in ein JSON-Dict um.

    Args:
        student: Zu serialisierender Schüler.
    """
    return {
        "student_id": str(student.student_id),
        "first_name": student.first_name_official,
        "nickname": student.nickname,
        "last_name": student.last_name,
        "seat": {"x": student.seat.x, "y": student.seat.y},
        "diagnostic": {
            "symbols": dict(student.diagnostic.symbols),
            "color_tags": list(student.diagnostic.color_tags),
            "accommodations": list(student.diagnostic.accommodations),
        },
    }


def _serialize_tablegroups(plan: SeatingPlan) -> list:
    """Wandelt alle Tischgruppen samt ihrer Sitz-Geometrie in eine JSON-Liste um.

    Args:
        plan: Sitzplan, dessen Tischgruppen serialisiert werden.
    """
    result = []
    for group in plan.tablegroups:
        result.append({
            "group_id": group.group_id,
            "seats": [
                {
                    "x": seat.x,
                    "y": seat.y,
                    "shift_x": float(seat.shift_x),
                    "shift_y": float(seat.shift_y),
                    "rotation": float(seat.rotation),
                }
                for seat in group.seats
            ],
        })
    return result


def _serialize_color_palette(plan: SeatingPlan) -> dict:
    """Wandelt die Farbpalette von *plan* in ein JSON-Dict um.

    Args:
        plan: Sitzplan, dessen Farbpalette serialisiert wird.
    """
    return {
        key: {"label": entry.label, "hex": entry.hex, "meaning": entry.meaning}
        for key, entry in plan.color_palette.items()
    }


def _serialize_documentation(plan: SeatingPlan) -> dict:
    """Wandelt Notenspalten, Gewichtung und Sessions von *plan* in ein JSON-Dict um.

    Args:
        plan: Sitzplan, dessen Dokumentation serialisiert wird.
    """
    doc = plan.documentation
    return {
        "grade_columns": [
            {
                "column_id": col.column_id,
                "category": col.category,
                "title": col.title,
                "created_at": col.created_at,
            }
            for col in doc.grade_columns
        ],
        "grade_weighting": {
            "written_percent": doc.weighting.written_percent,
            "sonstige_percent": doc.weighting.sonstige_percent,
        },
        "sessions": _serialize_sessions(doc),
    }


def _serialize_sessions(doc) -> list:
    """Wandelt alle Sessions von *doc* in eine JSON-Liste um.

    Symbol-Stärken außerhalb von 1–3 und nicht in Zahlen umwandelbare
    Noten werden verworfen. Leere Einträge (ohne Symbole, Noten, Notiz
    oder Mitarbeit-Bewertung) sowie Sessions ohne verbleibende Einträge
    werden komplett weggelassen, damit die gespeicherte Datei nicht mit
    Leerdaten aufgebläht wird.

    Args:
        doc: Dokumentationsblock, dessen Sessions serialisiert werden.
    """
    result = []
    for session in doc.sessions:
        serialized_entries: dict[str, dict] = {}
        for student_id, entry in session.entries.items():
            if not entry.has_content():
                continue
            entry_symbols: dict[str, int] = {}
            for symbol, strength in entry.symbols.items():
                symbol = str(symbol).strip()
                if not symbol:
                    continue
                try:
                    parsed = int(strength)
                except (TypeError, ValueError):
                    continue
                if 1 <= parsed <= 3:
                    entry_symbols[symbol] = parsed
            entry_grades: dict[str, float] = {}
            for col_id, grade in entry.grades.items():
                col_id = str(col_id).strip()
                if not col_id:
                    continue
                try:
                    entry_grades[col_id] = float(grade)
                except (TypeError, ValueError):
                    continue
            note = entry.note.strip()
            if not entry_symbols and not entry_grades and not note and entry.participation is None:
                continue
            serialized_entries[str(student_id)] = {
                "symbols": entry_symbols,
                "grades":  entry_grades,
                "note":    note,
                "participation": entry.participation,
            }
        if not serialized_entries:
            continue
        result.append({
            "date":    session.date,
            "entries": serialized_entries,
        })
    return result
