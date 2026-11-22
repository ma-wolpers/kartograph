"""Tests für Einträge des Notizenbereichs und das Gruppenblatt (``note_groups``, nur synthetische Daten)."""

from __future__ import annotations

import random

from app.core.domain.flag_columns import FLAG_MARK
from app.core.domain.note_groups import (
    WITHOUT_ENTRY_TITLE,
    GroupBox,
    NoteSource,
    build_group_sheet,
    count_without_entry,
    note_entries,
)
from app.core.usecases.v4.note_usecases import add_note_column, set_note_value
from tests.conftest import make_plan, make_student

FIRST_NAMES = ("Ida", "Ben", "Cem", "Ada", "Emil", "Fynn", "Gül")


def _plan(column_kind="text"):
    """Sieben Personen auf verschiedenen Plätzen und eine eigene Notizspalte."""
    students = [make_student(x=i, first_name=name, last_name=f"L{i}") for i, name in enumerate(FIRST_NAMES)]
    plan, column_id = add_note_column(make_plan(students=students, name="Klasse 7b"), "Gruppe", column_kind)
    return plan, column_id


def _set(plan, column_id, values):
    for student, value in zip(plan.classroom.students, values):
        plan = set_note_value(plan, student.student_id, column_id, value)
    return plan


def _sheet(plan, source, *, mode="note", include_without=True, seed=1, title="Gruppe"):
    return build_group_sheet(
        plan, source, column_title=title, label_mode=mode, include_without=include_without,
        name_format="Vorname", disambiguate=False, rng=random.Random(seed),
    )


def test_text_column_groups_all_values_alphabetically_with_names_sorted():
    plan, column_id = _plan()
    plan = _set(plan, column_id, ["B", "A", "A", "B", "A", "B", ""])
    sheet = _sheet(plan, NoteSource("column", column_id))
    assert sheet.heading == "Klasse 7b – Gruppe"
    assert sheet.boxes == (
        GroupBox("A", ("Ben", "Cem", "Emil")),
        GroupBox("B", ("Ada", "Fynn", "Ida")),
        GroupBox(WITHOUT_ENTRY_TITLE, ("Gül",)),
    )


def test_values_compare_exactly():
    plan, column_id = _plan()
    plan = _set(plan, column_id, ["Gruppe a", "Gruppe A"])
    boxes = _sheet(plan, NoteSource("column", column_id), include_without=False).boxes
    assert sorted(box.title for box in boxes) == ["Gruppe A", "Gruppe a"]


def test_without_entry_box_is_optional_and_counted():
    plan, column_id = _plan()
    plan = _set(plan, column_id, ["A", "A"])
    source = NoteSource("column", column_id)
    assert count_without_entry(plan, source) == 5
    assert [b.title for b in _sheet(plan, source, include_without=False).boxes] == ["A"]


def test_number_and_date_columns_follow_the_type_order():
    plan, column_id = _plan("number")
    plan = _set(plan, column_id, ["10", "2", "2,5"])
    titles = [b.title for b in _sheet(plan, NoteSource("column", column_id), include_without=False).boxes]
    assert titles == ["2", "2.5", "10"]
    plan, column_id = _plan("date")
    plan = _set(plan, column_id, ["1.2.2027", "3.11.2026"])
    titles = [b.title for b in _sheet(plan, NoteSource("column", column_id), include_without=False).boxes]
    assert titles == ["03.11.2026", "01.02.2027"]


def test_general_notes_one_group_per_line_and_a_person_may_be_in_two():
    plan, _ = _plan()
    first, second = plan.classroom.students[:2]
    first.diagnostic.notes = ["Gruppe A", "braucht Zeit"]
    second.diagnostic.notes = ["Gruppe A"]
    sheet = _sheet(plan, NoteSource("notes"), include_without=False, title="Notizen")
    assert sheet.boxes == (GroupBox("braucht Zeit", ("Ida",)), GroupBox("Gruppe A", ("Ben", "Ida")))


def test_flag_column_box_carries_the_column_title():
    plan, _ = _plan()
    plan.classroom.students[0].diagnostic.color_tags = ["rot"]
    source = NoteSource("flag", "rot")
    assert note_entries(plan, plan.classroom.students[0], source) == ((FLAG_MARK, FLAG_MARK),)
    sheet = _sheet(plan, source, title="Material (Rot)")
    assert sheet.boxes[0] == GroupBox("Material (Rot)", ("Ida",))
    assert sheet.boxes[1].title == WITHOUT_ENTRY_TITLE


def test_permanently_absent_people_are_left_out():
    plan, column_id = _plan()
    plan = _set(plan, column_id, ["A", "A"])
    plan.classroom.students[1].permanently_absent = True
    source = NoteSource("column", column_id)
    assert _sheet(plan, source, include_without=False).boxes == (GroupBox("A", ("Ida",)),)
    assert count_without_entry(plan, source) == 5


def test_secret_modes_shuffle_hide_the_column_and_number_one_to_n():
    plan, column_id = _plan()
    plan = _set(plan, column_id, ["A", "B", "C", "D", "E", "F", "G"])
    source = NoteSource("column", column_id)
    numbered = _sheet(plan, source, mode="numbered", seed=3)
    assert numbered.heading == "Klasse 7b"
    assert [b.title for b in numbered.boxes] == [f"Gruppe {i}" for i in range(1, 8)]
    sorted_names = [b.names for b in _sheet(plan, source).boxes]
    assert [b.names for b in numbered.boxes] != sorted_names
    assert sorted(b.names for b in numbered.boxes) == sorted(sorted_names)
    hidden = _sheet(plan, source, mode="none", seed=3)
    assert all(b.title is None for b in hidden.boxes)
    assert [b.names for b in hidden.boxes] == [b.names for b in numbered.boxes]
