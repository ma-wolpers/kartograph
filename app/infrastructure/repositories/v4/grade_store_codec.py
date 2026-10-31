"""Noten lesen und schreiben -- inklusive Übernahme des alten Formats (Noten in den Tageseinträgen).

Früher lagen Noten je Datum in ``sessions[].entries[].grades``; eine Spalte
konnte dadurch mehrere Noten derselben Person enthalten. Jetzt gilt: eine Note
je Person und Spalte (``documentation.grades``). Beim Lesen wird das alte Format
übernommen: Gibt es genau eine Altnote, ist sie die Note. Gibt es mehrere, gilt
vorläufig die neueste (das zeigte die Zelle schon vorher), und alle bleiben als
``GradeConflict`` erhalten, bis die Nutzerin entscheidet -- es geht nichts verloren.
Altnoten unbekannter Spalten/Schüler wurden nirgends angezeigt und entfallen.
"""

from __future__ import annotations

from typing import Iterable

from app.core.domain.models_v4 import DocumentationBlock, GradeConflict
from app.core.domain.student_id import StudentId


def has_legacy_session_grades(payload: dict) -> bool:
    """Prüft, ob eine Plandatei noch Noten in Tageseinträgen enthält (altes Format).

    Args:
        payload: Roh-Dict der Plandatei.
    """
    documentation = payload.get("documentation") or {}
    return any(
        isinstance(entry, dict) and entry.get("grades")
        for session in documentation.get("sessions") or [] if isinstance(session, dict)
        for entry in (session.get("entries") or {}).values()
    )


def read_grade_store(
    raw_doc: dict, column_ids: Iterable[str], student_ids: Iterable[StudentId]
) -> tuple[dict[StudentId, dict[str, float]], list[GradeConflict]]:
    """Liest Noten und offene Konflikte; übernimmt dabei Altnoten aus den Tageseinträgen.

    Args:
        raw_doc: Roh-Dict des ``documentation``-Feldes.
        column_ids: Bekannte Notenspalten.
        student_ids: Bekannte Schüler.

    Returns:
        ``(Noten je Schüler und Spalte, offene Konflikte)``.
    """
    known_columns, known_students = set(column_ids), set(student_ids)
    grades: dict[StudentId, dict[str, float]] = {}
    for sid, column_id, value in _stored_grades(raw_doc.get("grades") or {}):
        if sid in known_students and column_id in known_columns:
            grades.setdefault(sid, {})[column_id] = value
    conflicts = [
        conflict for conflict in _stored_conflicts(raw_doc.get("grade_conflicts") or [])
        if conflict.student_id in known_students and conflict.column_id in known_columns
    ]
    for (sid, column_id), candidates in _legacy_candidates(raw_doc.get("sessions") or []).items():
        if sid not in known_students or column_id not in known_columns or column_id in grades.get(sid, {}):
            continue
        grades.setdefault(sid, {})[column_id] = candidates[-1][1]
        if len(candidates) > 1:
            conflicts.append(GradeConflict(sid, column_id, tuple(candidates)))
    return grades, conflicts


def serialize_grade_store(doc: DocumentationBlock) -> dict:
    """Wandelt Noten und offene Konflikte in die JSON-Felder von ``documentation`` um.

    Args:
        doc: Dokumentationsblock.
    """
    return {
        "grades": {
            str(sid): {column_id: float(value) for column_id, value in columns.items()}
            for sid, columns in doc.grades.items()
        },
        "grade_conflicts": [
            {
                "student_id": str(conflict.student_id),
                "column_id": conflict.column_id,
                "candidates": [{"date": date, "value": value} for date, value in conflict.candidates],
            }
            for conflict in doc.grade_conflicts
        ],
    }


def _student_id_or_none(raw: object) -> StudentId | None:
    """Liest eine Schüler-ID; ungültige Werte ergeben ``None``.

    Args:
        raw: Rohwert aus der Datei.
    """
    try:
        return StudentId.of(str(raw).strip())
    except ValueError:
        return None


def _grade_or_none(raw: object) -> float | None:
    """Liest einen Notenwert; ungültige Werte ergeben ``None``.

    Args:
        raw: Rohwert aus der Datei.
    """
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _stored_grades(raw: dict) -> Iterable[tuple[StudentId, str, float]]:
    """Liefert die gültigen Einträge des Feldes ``documentation.grades``.

    Args:
        raw: Roh-Dict Schüler-ID → (Spalte → Wert).
    """
    for raw_sid, columns in raw.items():
        sid = _student_id_or_none(raw_sid)
        if sid is None or not isinstance(columns, dict):
            continue
        for column_id, raw_value in columns.items():
            value = _grade_or_none(raw_value)
            if value is not None:
                yield sid, str(column_id).strip(), value


def _stored_conflicts(raw: list) -> Iterable[GradeConflict]:
    """Liefert die gültigen Einträge des Feldes ``documentation.grade_conflicts``.

    Args:
        raw: Roh-Liste der Konflikte.
    """
    for item in raw:
        if not isinstance(item, dict):
            continue
        sid = _student_id_or_none(item.get("student_id"))
        candidates = tuple(
            (str(candidate.get("date") or ""), value)
            for candidate in item.get("candidates") or [] if isinstance(candidate, dict)
            if (value := _grade_or_none(candidate.get("value"))) is not None
        )
        if sid is not None and len(candidates) > 1:
            yield GradeConflict(sid, str(item.get("column_id") or "").strip(), candidates)


def _legacy_candidates(raw_sessions: list) -> dict[tuple[StudentId, str], list[tuple[str, float]]]:
    """Sammelt Altnoten je Schüler und Spalte, aufsteigend nach Datum.

    Args:
        raw_sessions: Roh-Liste des ``sessions``-Feldes (doppelte Daten zählen
            wie beim Lesen der Sessions nur beim ersten Vorkommen).
    """
    result: dict[tuple[StudentId, str], list[tuple[str, float]]] = {}
    seen_dates: set[str] = set()
    dated = [s for s in raw_sessions if isinstance(s, dict) and str(s.get("date") or "").strip()]
    for session in sorted(dated, key=lambda s: str(s["date"]).strip()):
        date = str(session["date"]).strip()
        if date in seen_dates:
            continue
        seen_dates.add(date)
        for raw_sid, entry in (session.get("entries") or {}).items():
            sid = _student_id_or_none(raw_sid)
            if sid is None or not isinstance(entry, dict):
                continue
            for column_id, raw_value in (entry.get("grades") or {}).items():
                value = _grade_or_none(raw_value)
                if value is not None:
                    result.setdefault((sid, str(column_id).strip()), []).append((date, value))
    return result
