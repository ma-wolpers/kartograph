"""JSON-Form der eigenen Notizspalten (``SeatingPlan.note_columns``) und ihrer Werte.

Additiv im Format v4 (kein Versionssprung)::

    "note_columns": [{"column_id": "3fa85f64", "title": "Hausaufgaben", "kind": "number", "created_at": "…"}]
    "diagnostic": {..., "note_values": {"3fa85f64": "4"}}

Lesen ist tolerant: Spalten ohne ID, mit doppelter ID oder unbekanntem Typ
entfallen (wie ``_deserialize_grade_columns``), Werte werden als Text gelesen.
GRENZE: Werte zu einer Spalten-ID, die es nicht (mehr) gibt (nur nach Bearbeiten
der Datei von Hand möglich), bleiben gespeichert, werden aber nirgends angezeigt.
"""

from __future__ import annotations

from app.core.domain.models_v4 import NoteColumn
from app.core.domain.note_column_kinds import NOTE_VALUE_KINDS


def serialize_note_columns(columns: list[NoteColumn]) -> list[dict]:
    """Schreibt die Notizspalten in Anzeigereihenfolge.

    Args:
        columns: Spalten des Plans.
    """
    return [
        {"column_id": c.column_id, "title": c.title, "kind": c.kind, "created_at": c.created_at}
        for c in columns
    ]


def deserialize_note_columns(raw: object) -> list[NoteColumn]:
    """Liest die Notizspalten tolerant (fehlend oder kaputt = keine).

    Args:
        raw: Rohwert des Feldes ``note_columns``.
    """
    columns: list[NoteColumn] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        column_id = str(item.get("column_id") or "").strip()
        kind = str(item.get("kind") or "").strip()
        if not column_id or column_id in seen or kind not in NOTE_VALUE_KINDS:
            continue
        seen.add(column_id)
        title = str(item.get("title") or "").strip() or column_id
        columns.append(NoteColumn(column_id, title, kind, str(item.get("created_at") or "").strip()))  # type: ignore[arg-type]
    return columns


def deserialize_note_values(raw: object) -> dict[str, str]:
    """Liest die Werte einer Person (Spalten-ID → gespeicherte Form); leere Werte entfallen.

    Args:
        raw: Rohwert von ``diagnostic.note_values``.
    """
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if str(key).strip() and str(value).strip()}
