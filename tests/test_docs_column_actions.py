"""Tests für die eine Regel der Spaltenknöpfe: was hinzufügen/umbenennen/löschen für die Auswahl bedeutet."""

from __future__ import annotations

import pytest

from app.adapters.gui.docs_column_actions import action_label, can_run, column_target
from app.adapters.gui.docs_table_model import (
    NACHNAME_KEY,
    NOTES_KEY,
    OVERALL_KEY,
    SUMMARY_KEY,
    DocColumnAxis,
    grade_column_key,
    note_column_key,
    notes_area_kind,
)
from app.core.domain.data_view_areas import DataArea

_NOTE = note_column_key("n1")
_GRADE = grade_column_key("g1")


@pytest.fixture
def axis() -> DocColumnAxis:
    """Achse mit allen Spaltenarten (Doku + Notizen sichtbar; Noten separat)."""
    return DocColumnAxis(
        ["date_0"],
        [SUMMARY_KEY, _GRADE, OVERALL_KEY],
        [(NOTES_KEY, "notes"), ("mark_rot", "flag"), (_NOTE, notes_area_kind("number"))],
        (DataArea.DOKU, DataArea.NOTIZEN),
    )


@pytest.mark.parametrize(
    ("key", "area", "kind"),
    [("date_0", DataArea.DOKU, "date"), ("mark_rot", DataArea.NOTIZEN, "flag"), (_NOTE, DataArea.NOTIZEN, "note"),
     (NOTES_KEY, DataArea.NOTIZEN, None)],
)
def test_target_per_column(axis, key, area, kind):
    target = column_target(axis, key)
    assert (target.area, target.kind) == (area, kind)


def test_grade_area_columns():
    axis = DocColumnAxis([], [SUMMARY_KEY, _GRADE, OVERALL_KEY], (), (DataArea.NOTEN,))
    assert column_target(axis, _GRADE).kind == "grade"
    assert column_target(axis, OVERALL_KEY).kind is None
    assert action_label("add", column_target(axis, SUMMARY_KEY)) == "Notenspalte hinzufügen"


def test_names_grey_out_everything(axis):
    target = column_target(axis, NACHNAME_KEY)
    assert target is None
    assert not any(can_run(action, target) for action in ("add", "rename", "delete"))
    assert "wähle eine Zelle in Doku, Notizen oder Noten" in action_label("delete", target)


def test_general_notes_allow_adding_but_not_renaming(axis):
    target = column_target(axis, NOTES_KEY)
    assert can_run("add", target) and not can_run("rename", target) and not can_run("delete", target)
    assert action_label("rename", target).endswith("nicht umbenennen")


def test_labels_say_what_happens(axis):
    assert action_label("add", column_target(axis, "date_0")) == "Datum hinzufügen"
    assert action_label("rename", column_target(axis, "date_0")) == "Datum ändern"
    assert action_label("rename", column_target(axis, "mark_rot")).startswith("Ja/Nein-Spalte umbenennen")
    assert action_label("delete", column_target(axis, _NOTE)) == "Notizspalte samt Werten löschen"


@pytest.mark.parametrize(("key", "enabled"), [(NOTES_KEY, True), ("mark_rot", True), (_NOTE, True), ("date_0", False),
                                              (NACHNAME_KEY, False)])
def test_groups_only_in_the_notes_area(axis, key, enabled):
    target = column_target(axis, key)
    assert can_run("groups", target) is enabled
    assert ("Notizenbereich" in action_label("groups", target)) is not enabled
