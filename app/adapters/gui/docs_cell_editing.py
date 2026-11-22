"""Was der Inline-Editor der Datenansicht bearbeitet und wie er speichert (reines Python, kein Tk).

Ein Editor für alle bearbeitbaren Zellen (Noten und eigene Notizspalten),
statt einen Noten-Editor zu kopieren. Je Spaltenart steht hier einmal:

- ``initial_edit_text``: womit der Editor ohne getipptes Startzeichen gefüllt wird,
- ``commit_cell_edit``: Eingabe prüfen und den passenden Intent bauen
  (``RecordGradeIntent`` bzw. ``SetNoteValueIntent``) oder den Eingabehinweis liefern.

Das Ziel wird beim Öffnen festgelegt (``CellEditTarget``), nie aus der späteren Auswahl.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.gui.docs_table_model import grade_column_id, note_column_id
from app.core.domain.grade_scale import parse_grade_input, scale_for
from app.core.domain.models_v4 import NoteColumn, SeatingPlan, StudentId
from app.core.domain.note_column_kinds import NOTE_VALUE_KINDS, format_date_value, parse_note_value
from app.core.intents.base import Intent
from app.core.intents.grade_intents import RecordGradeIntent
from app.core.intents.note_intents import SetNoteValueIntent


@dataclass(frozen=True)
class CellEditTarget:
    """Ziel eines Inline-Editors -- festgelegt beim Öffnen.

    Attributes:
        student_id: Person der Zeile.
        column_key: Spaltenschlüssel (``"grade_<id>"`` oder ``"note_<id>"``).
    """

    student_id: StudentId
    column_key: str


@dataclass(frozen=True)
class CellCommit:
    """Ergebnis der Prüfung einer Editor-Eingabe.

    Attributes:
        intent: Auszuführender Intent; ``None`` bei ungültiger Eingabe.
        message: Statusmeldung (gültig) bzw. Eingabehinweis (ungültig).
    """

    intent: Intent | None
    message: str


def _note_column(plan: SeatingPlan, column_key: str) -> NoteColumn | None:
    """Notizspalte zum Spaltenschlüssel, ``None`` wenn es keine (mehr) ist."""
    column_id = note_column_id(column_key)
    return next((c for c in plan.note_columns if c.column_id == column_id), None)


def initial_edit_text(plan: SeatingPlan, target: CellEditTarget) -> str:
    """Bisheriger Wert der Zelle in Eingabeform (leer, wenn es keinen gibt).

    Args:
        plan: Aktueller Plan.
        target: Ziel des Editors.

    Returns:
        z. B. ``"2,3"`` für eine Note oder ``"03.11.2026"`` für ein Datum.
    """
    grade_id = grade_column_id(target.column_key)
    if grade_id is not None:
        doc = plan.documentation
        value = doc.grade_of(target.student_id, grade_id)
        return "" if value is None else scale_for(doc.grade_scale).format_input(value)
    column = _note_column(plan, target.column_key)
    student = plan.classroom.student_by_id(target.student_id)
    if column is None or student is None:
        return ""
    stored = student.diagnostic.note_values.get(column.column_id, "")
    return format_date_value(stored) if stored and column.kind == "date" else stored


def commit_cell_edit(plan: SeatingPlan, target: CellEditTarget, text: str) -> CellCommit:
    """Prüft *text* für *target* und baut den Intent (leere Eingabe löscht den Wert).

    Args:
        plan: Aktueller Plan.
        target: Ziel des Editors.
        text: Eingabe im Editor.

    Returns:
        ``CellCommit`` mit Intent und Statusmeldung bzw. ohne Intent mit Eingabehinweis.
    """
    grade_id = grade_column_id(target.column_key)
    if grade_id is not None:
        scale = scale_for(plan.documentation.grade_scale)
        valid, value = parse_grade_input(text, scale)
        if not valid:
            return CellCommit(None, scale.input_hint)
        intent = RecordGradeIntent(student_id=target.student_id, column_id=grade_id, grade=value)
        return CellCommit(intent, "Note gelöscht" if value is None else "Note aktualisiert")
    column = _note_column(plan, target.column_key)
    if column is None:
        return CellCommit(None, "Diese Spalte gibt es nicht mehr")
    try:
        stored = parse_note_value(column.kind, text)
    except ValueError:
        return CellCommit(None, NOTE_VALUE_KINDS[column.kind].input_hint)
    intent = SetNoteValueIntent(student_id=target.student_id, column_id=column.column_id, text=text)
    return CellCommit(intent, "Notiz gelöscht" if not stored else "Notiz aktualisiert")
