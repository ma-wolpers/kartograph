"""Usecases für Notizen an Schülern (``DiagnosticProfile.notes``) und eigene Notizspalten.

Eigene Notizspalten (``SeatingPlan.note_columns``, Werte in
``DiagnosticProfile.note_values``) haben Titel und Zeilentyp; die Typregeln
stehen in ``app/core/domain/note_column_kinds.py``.

Notizen sind freie Textzeilen (z. B. Absprachen oder "Zeitzuschlag 25 %"),
analog zu ``color_tags`` als einfache Liste statt strukturierter Daten. Die
Normalisierung steht einmalig in ``app/core/domain/student_notes.py``.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import NoteColumn, SeatingPlan
from app.core.domain.note_column_kinds import NOTE_VALUE_KINDS, parse_note_value
from app.core.domain.permanent_absence import accepts_notes
from app.core.domain.short_id import new_short_id
from app.core.domain.student_id import StudentId
from app.core.domain.student_notes import normalize_note_lines
from app.core.usecases.v4._shared import _today_iso


def set_notes(
    plan: SeatingPlan, student_id: StudentId, notes: list[str]
) -> SeatingPlan:
    """Ersetzt die Liste der Notizen eines Schülers vollständig.

    Normalisiert über ``normalize_note_lines`` (getrimmt, Leerzeilen verworfen,
    Reihenfolge bleibt erhalten).

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        notes: Neue, vollständige Liste der Notizen.

    Returns:
        Neuer Plan mit aktualisierten Notizen.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None or not accepts_notes(student):  # Notizen nur für Schüler:innen
        return next_plan
    student.diagnostic.notes = normalize_note_lines(notes)
    return next_plan


def add_note_column(plan: SeatingPlan, title: str, kind: str) -> tuple[SeatingPlan, str]:
    """Legt eine eigene Notizspalte an (hinten, ohne Werte).

    Args:
        plan: Ausgangsplan.
        title: Spaltentitel; leer ergibt "<Typ> N" (z. B. "Zahl 2").
        kind: Typschlüssel aus ``NOTE_VALUE_KINDS``.

    Returns:
        ``(neuer Plan, column_id)``.

    Raises:
        ValueError: Unbekannter Typ.
    """
    if kind not in NOTE_VALUE_KINDS:
        raise ValueError(f"Unbekannter Spaltentyp {kind!r}")
    clean_title = str(title or "").strip() or f"{NOTE_VALUE_KINDS[kind].label} {len(plan.note_columns) + 1}"
    next_plan = deepcopy(plan)
    column_id = new_short_id(c.column_id for c in plan.note_columns)
    next_plan.note_columns.append(NoteColumn(column_id, clean_title, kind, _today_iso()))  # type: ignore[arg-type]
    return next_plan, column_id


def delete_note_column(plan: SeatingPlan, column_id: str) -> SeatingPlan:
    """Löscht eine Notizspalte samt den Werten aller Personen.

    Args:
        plan: Ausgangsplan.
        column_id: ID der Spalte.

    Returns:
        Neuer Plan ohne die Spalte.
    """
    next_plan = deepcopy(plan)
    next_plan.note_columns = [c for c in next_plan.note_columns if c.column_id != column_id]
    for student in next_plan.classroom.students:
        student.diagnostic.note_values.pop(column_id, None)
    return next_plan


def set_note_value(plan: SeatingPlan, student_id: StudentId, column_id: str, text: str) -> SeatingPlan:
    """Setzt (oder löscht bei leerer Eingabe) den Wert einer Person in einer Notizspalte.

    Wie die allgemeinen Notizen nur für Schüler:innen (``accepts_notes``;
    dauerhaft Abwesende behalten Notizen). Eingelesen wird über den Typ der
    Spalte (``note_column_kinds.parse_note_value``).

    Args:
        plan: Ausgangsplan.
        student_id: Person.
        column_id: Notizspalte.
        text: Rohe Eingabe.

    Returns:
        Neuer Plan (unverändert bei unbekannter Spalte/Person).

    Raises:
        ValueError: Ungültige Eingabe für den Spaltentyp.
    """
    column = next((c for c in plan.note_columns if c.column_id == column_id), None)
    if column is None:
        return deepcopy(plan)
    stored = parse_note_value(column.kind, text)
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None or not accepts_notes(student):
        return next_plan
    if stored:
        student.diagnostic.note_values[column_id] = stored
    else:
        student.diagnostic.note_values.pop(column_id, None)
    return next_plan
