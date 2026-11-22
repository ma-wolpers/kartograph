"""Tests für das Lesen und Schreiben von Zellen als Text (``docs_cell_editing``, nur synthetische Daten)."""

from __future__ import annotations

from app.adapters.gui.docs_cell_editing import CellEditTarget, cell_text, commit_cell_text
from app.adapters.gui.docs_table_model import NOTES_KEY, grade_column_key, note_column_key
from app.core.intents.grade_intents import RecordGradeIntent
from app.core.intents.note_intents import SetNotesIntent, SetNoteValueIntent
from app.core.usecases.v4.grade_usecases import add_grade_column
from app.core.usecases.v4.note_usecases import add_note_column
from tests.conftest import make_plan, make_student


def _plan_with_student():
    student = make_student(first_name="Anna", last_name="A")
    student.diagnostic.notes = ["braucht Zeit", "sitzt vorne"]
    return make_plan(students=[student]), student.student_id


def test_general_notes_read_one_note_per_line():
    plan, student_id = _plan_with_student()
    assert cell_text(plan, CellEditTarget(student_id, NOTES_KEY)) == "braucht Zeit\nsitzt vorne"


def test_general_notes_write_one_note_per_line_without_running_input():
    plan, student_id = _plan_with_student()
    commit = commit_cell_text(plan, CellEditTarget(student_id, NOTES_KEY), " a \n\nb\n")
    assert commit.intent == SetNotesIntent(student_id=student_id, notes=["a", "b"])
    assert not commit.intent.running_input
    assert commit_cell_text(plan, CellEditTarget(student_id, NOTES_KEY), "").message == "Notizen gelöscht"


def test_single_line_cells_take_line_breaks_as_spaces():
    plan, student_id = _plan_with_student()
    plan, column_id = add_note_column(plan, "Bemerkung", "text")
    commit = commit_cell_text(plan, CellEditTarget(student_id, note_column_key(column_id)), "zwei\nZeilen\n")
    assert commit.intent == SetNoteValueIntent(student_id=student_id, column_id=column_id, text="zwei Zeilen")


def test_pasted_grade_with_trailing_line_break_is_valid():
    plan, student_id = _plan_with_student()
    plan, column_id = add_grade_column(plan, "schriftlich", "Arbeit")
    commit = commit_cell_text(plan, CellEditTarget(student_id, grade_column_key(column_id)), "2,3\n")
    assert isinstance(commit.intent, RecordGradeIntent)
    assert commit.intent.grade is not None
