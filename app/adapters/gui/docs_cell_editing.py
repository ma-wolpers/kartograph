"""Zellen der Datenansicht als Text lesen und schreiben (reines Python, kein Tk).

Eine Regel für alle Zellen mit Textwert (``DocColumnAxis.holds_text``: Noten,
eigene Notizspalten, allgemeine Notizen), statt sie je Weg zu kopieren. Inline-
Editor, Notizdialog, Entf, Ausschneiden und Einfügen nutzen dieselben zwei Funktionen:

- ``cell_text``: der Wert der Zelle in Eingabeform (Editor-Inhalt, Kopiertext),
- ``commit_cell_text``: einen Text prüfen und den passenden Intent bauen
  (``RecordGradeIntent``, ``SetNoteValueIntent`` bzw. ``SetNotesIntent``) oder
  den Eingabehinweis liefern. Leerer Text löscht den Wert.

Einzeilige Zellen nehmen Zeilenumbrüche (z. B. aus eingefügtem Text) als
Leerzeichen; die allgemeinen Notizen speichern eine Notiz je Zeile.

Das Ziel wird beim Öffnen bzw. Auslösen festgelegt (``CellEditTarget``), nie aus
der späteren Auswahl.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.adapters.gui.docs_table_model import NOTES_KEY, grade_column_id, note_column_id
from app.core.domain.grade_scale import parse_grade_input, scale_for
from app.core.domain.models_v4 import NoteColumn, SeatingPlan, StudentId
from app.core.domain.note_column_kinds import NOTE_VALUE_KINDS, format_date_value, parse_note_value
from app.core.domain.student_notes import normalize_note_lines
from app.core.intents.base import Intent
from app.core.intents.grade_intents import RecordGradeIntent
from app.core.intents.note_intents import SetNotesIntent, SetNoteValueIntent


@dataclass(frozen=True)
class CellEditTarget:
    """Zelle, deren Textwert gelesen oder geschrieben wird -- festgelegt beim Auslösen.

    Attributes:
        student_id: Person der Zeile.
        column_key: Spaltenschlüssel (``"grade_<id>"``, ``"note_<id>"`` oder ``NOTES_KEY``).
    """

    student_id: StudentId
    column_key: str


@dataclass(frozen=True)
class CellCommit:
    """Ergebnis der Prüfung eines Textes für eine Zelle.

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


def _single_line(text: str) -> str:
    """Zeilenumbrüche werden zu Leerzeichen, leere Zeilen entfallen (einzeilige Zellen)."""
    return " ".join(line.strip() for line in str(text).splitlines() if line.strip())


def cell_text(plan: SeatingPlan, target: CellEditTarget) -> str:
    """Bisheriger Wert der Zelle in Eingabeform (leer, wenn es keinen gibt).

    Args:
        plan: Aktueller Plan.
        target: Zelle.

    Returns:
        z. B. ``"2,3"`` für eine Note, ``"03.11.2026"`` für ein Datum oder die
        allgemeinen Notizen mit einer Notiz je Zeile.
    """
    grade_id = grade_column_id(target.column_key)
    if grade_id is not None:
        doc = plan.documentation
        value = doc.grade_of(target.student_id, grade_id)
        return "" if value is None else scale_for(doc.grade_scale).format_input(value)
    student = plan.classroom.student_by_id(target.student_id)
    if student is None:
        return ""
    if target.column_key == NOTES_KEY:
        return "\n".join(student.diagnostic.notes)
    column = _note_column(plan, target.column_key)
    if column is None:
        return ""
    stored = student.diagnostic.note_values.get(column.column_id, "")
    return format_date_value(stored) if stored and column.kind == "date" else stored


def commit_cell_text(plan: SeatingPlan, target: CellEditTarget, text: str) -> CellCommit:
    """Prüft *text* für *target* und baut den Intent (leerer Text löscht den Wert).

    Args:
        plan: Aktueller Plan.
        target: Zelle.
        text: Eingabe (Editor, Dialog oder Zwischenablage).

    Returns:
        ``CellCommit`` mit Intent und Statusmeldung bzw. ohne Intent mit Eingabehinweis.
    """
    if target.column_key == NOTES_KEY:
        lines = normalize_note_lines(str(text).splitlines())
        intent = SetNotesIntent(student_id=target.student_id, notes=lines)
        return CellCommit(intent, "Notizen aktualisiert" if lines else "Notizen gelöscht")
    text = _single_line(text)
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
