"""Tests für eigene Notizspalten: Zeilentypen, Usecases/Handler und Dateiformat (nur synthetische Daten)."""

from __future__ import annotations

import pytest

from app.application.app_state import AppState
from app.application.handlers.note_handlers import (
    handle_add_note_column,
    handle_delete_note_column,
    handle_set_note_value,
)
from app.core.domain.note_column_kinds import NOTE_VALUE_KINDS, format_date_value, parse_date_input, parse_note_value
from app.core.intents.note_intents import AddNoteColumnIntent, DeleteNoteColumnIntent, SetNoteValueIntent
from app.core.usecases.v4.note_usecases import add_note_column
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR
from tests.test_plan_save_debounce import _make_ctx


class TestKinds:
    @pytest.mark.parametrize(("text", "stored"), [("2,50", "2.5"), (" 3 ", "3"), ("0.25", "0.25")])
    def test_number(self, text, stored):
        assert parse_note_value("number", text) == stored

    @pytest.mark.parametrize(("text", "stored"), [("3.11.2026", "2026-11-03"), ("03.11.26", "2026-11-03"),
                                                   ("2026-11-03", "2026-11-03")])
    def test_date(self, text, stored):
        assert parse_date_input(text) == stored
        assert format_date_value(stored) == "03.11.2026"

    @pytest.mark.parametrize(("kind", "text"), [("number", "abc"), ("date", "31.02.2026"), ("date", "morgen")])
    def test_invalid_input_raises(self, kind, text):
        with pytest.raises(ValueError):
            parse_note_value(kind, text)

    def test_empty_input_means_delete(self):
        assert parse_note_value("number", "  ") == ""

    def test_sort_values_order_numbers_and_dates(self):
        number = NOTE_VALUE_KINDS["number"].sort_value
        assert sorted(["10", "9", "x"], key=number) == ["9", "10", "x"]
        assert NOTE_VALUE_KINDS["date"].sort_value("2026-01-02") < NOTE_VALUE_KINDS["date"].sort_value("2026-11-01")


def _state():
    student = make_student(x=0, y=0, first_name="Ada")
    return AppState(current_plan=make_plan(students=[student]), current_plan_path=PLANS_DIR / "x.json"), student


class TestHandlers:
    def test_add_set_and_delete(self):
        state, student = _state()
        ctx = _make_ctx()
        state = handle_add_note_column(AddNoteColumnIntent(title="", kind="number"), state, ctx)
        (column,) = state.current_plan.note_columns
        assert column.title == "Zahl 1" and column.kind == "number"
        state = handle_set_note_value(SetNoteValueIntent(student.student_id, column.column_id, "2,5"), state, ctx)
        assert state.current_plan.student_by_id(student.student_id).diagnostic.note_values == {column.column_id: "2.5"}
        state = handle_set_note_value(SetNoteValueIntent(student.student_id, column.column_id, ""), state, ctx)
        assert state.current_plan.student_by_id(student.student_id).diagnostic.note_values == {}
        state = handle_set_note_value(SetNoteValueIntent(student.student_id, column.column_id, "4"), state, ctx)
        state = handle_delete_note_column(DeleteNoteColumnIntent(column.column_id), state, ctx)
        assert state.current_plan.note_columns == []
        assert state.current_plan.student_by_id(student.student_id).diagnostic.note_values == {}

    def test_invalid_value_keeps_plan_and_reports(self):
        state, student = _state()
        ctx = _make_ctx()
        state = handle_add_note_column(AddNoteColumnIntent(title="Datum", kind="date"), state, ctx)
        column_id = state.current_plan.note_columns[0].column_id
        new_state = handle_set_note_value(SetNoteValueIntent(student.student_id, column_id, "morgen"), state, ctx)
        assert new_state.current_plan is state.current_plan
        assert "passt nicht" in new_state.status_message

    def test_unknown_kind_is_rejected(self):
        with pytest.raises(ValueError):
            add_note_column(make_plan(), "x", "farbe")


class TestFileFormat:
    def test_roundtrip(self):
        state, student = _state()
        plan, column_id = add_note_column(state.current_plan, "HA", "text")
        plan.classroom.students[0].diagnostic.note_values[column_id] = "vergessen"
        loaded = deserialize_plan(serialize_plan(plan))
        assert loaded.note_columns == plan.note_columns
        assert loaded.classroom.students[0].diagnostic.note_values == {column_id: "vergessen"}

    def test_old_files_and_broken_entries_load(self):
        payload = serialize_plan(make_plan(students=[make_student(x=0, y=0)]))
        payload.pop("note_columns")
        assert deserialize_plan(payload).note_columns == []
        payload["note_columns"] = [{"column_id": "a", "kind": "farbe"}, {"kind": "text"}, {"column_id": "b", "kind": "text"},
                                   {"column_id": "b", "kind": "date"}]
        (column,) = deserialize_plan(payload).note_columns
        assert (column.column_id, column.title, column.kind) == ("b", "b", "text")
