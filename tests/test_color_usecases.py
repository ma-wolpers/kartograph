"""Tests für v4 color_usecases (Farbpunkt-Bedeutungen in der Palette).

Abgesichert sind Lesen/Setzen der Bedeutung, die Übergangsregel "eine Spalte
verschwindet nur mit ihrer letzten Markierung" (über die echten Handler),
Ja/Nein-Spalten anlegen/löschen, sowie das Dateiformat (nur
``meaning``, alte ``label``/``hex``-Felder werden ignoriert). Nur synthetische Daten.
"""

from __future__ import annotations

from copy import deepcopy

from app.application.app_state import AppState
from app.application.handlers.color_handlers import handle_add_flag_column, handle_delete_flag_column, handle_toggle_color
from app.application.handlers.plan_handlers import handle_open_plan
from app.core.domain.models_v4 import PaletteEntry
from app.core.intents.color_intents import AddFlagColumnIntent, DeleteFlagColumnIntent, ToggleColorIntent
from app.core.intents.plan_intents import OpenPlanIntent
from app.core.usecases.v4.color_usecases import (
    add_flag_column,
    drop_abandoned_palette_entries,
    palette_meaning,
    set_palette_meaning,
)
from app.infrastructure.repositories.v4.deserializer_v4 import deserialize_plan
from app.infrastructure.repositories.v4.serializer_v4 import serialize_plan
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR, FakePlanRepository
from tests.test_plan_save_debounce import _make_ctx


def _plan_with_yellow(*, carriers: int = 1):
    """Plan, in dem *carriers* Schüler Gelb tragen und Gelb "Förderbedarf" bedeutet.

    Returns:
        ``(plan, students)``.
    """
    students = [make_student(x=i, y=0, first_name=f"S{i}") for i in range(carriers)]
    for student in students:
        student.diagnostic.color_tags = ["gelb"]
    plan = make_plan(students=students)
    plan.color_palette["gelb"] = PaletteEntry(meaning="Förderbedarf")
    return plan, students


class TestSetPaletteMeaning:
    def test_creates_missing_entry(self):
        # Regression: ohne Palette-Eintrag ging die abgefragte Bedeutung verloren.
        result = set_palette_meaning(make_plan(), "gelb", "  Förderbedarf  ")
        assert result.color_palette["gelb"] == PaletteEntry(meaning="Förderbedarf")

    def test_updates_existing_entry(self):
        plan, _students = _plan_with_yellow()
        result = set_palette_meaning(plan, "gelb", "Neu")
        assert palette_meaning(result, "gelb") == "Neu"

    def test_does_not_mutate_input(self):
        plan = make_plan()
        set_palette_meaning(plan, "gelb", "Förderbedarf")
        assert plan.color_palette == {}


class TestPaletteMeaning:
    def test_missing_entry_is_empty(self):
        assert palette_meaning(make_plan(), "gelb") == ""

    def test_whitespace_only_is_empty(self):
        plan = make_plan()
        plan.color_palette["gelb"] = PaletteEntry(meaning="   ")
        assert palette_meaning(plan, "gelb") == ""

    def test_returns_trimmed_meaning(self):
        plan = make_plan()
        plan.color_palette["gelb"] = PaletteEntry(meaning=" Förderbedarf ")
        assert palette_meaning(plan, "gelb") == "Förderbedarf"


class TestAbandonedPaletteEntries:
    """Übergangsregel: Eine Spalte verschwindet nur, wenn ihre letzte Markierung entfernt wird."""

    def test_only_entries_whose_last_carrier_left_are_dropped(self):
        previous, (student,) = _plan_with_yellow()
        previous.color_palette["rot"] = PaletteEntry(meaning="niemand trägt das")
        plan = deepcopy(previous)
        plan.classroom.students[0].diagnostic.color_tags = []
        drop_abandoned_palette_entries(previous, plan)
        assert set(plan.color_palette) == {"rot"}

    def test_without_previous_nothing_is_dropped(self):
        plan, _students = _plan_with_yellow()
        plan.color_palette["rot"] = PaletteEntry(meaning="leer")
        drop_abandoned_palette_entries(None, plan)
        assert set(plan.color_palette) == {"gelb", "rot"}

    def test_removing_color_from_last_carrier_discards_meaning(self):
        plan, (student,) = _plan_with_yellow(carriers=1)
        state = AppState(current_plan=plan, current_plan_path=PLANS_DIR / "x.json")

        new_state = handle_toggle_color(
            ToggleColorIntent(student_id=student.student_id, color_key="gelb"), state, _make_ctx()
        )

        assert new_state.current_plan.color_palette == {}

    def test_removing_color_from_one_of_two_carriers_keeps_meaning(self):
        plan, (first, _second) = _plan_with_yellow(carriers=2)
        state = AppState(current_plan=plan, current_plan_path=PLANS_DIR / "x.json")

        new_state = handle_toggle_color(
            ToggleColorIntent(student_id=first.student_id, color_key="gelb"), state, _make_ctx()
        )

        assert palette_meaning(new_state.current_plan, "gelb") == "Förderbedarf"

    def test_opening_a_file_keeps_empty_columns(self):
        plan, _students = _plan_with_yellow()
        plan.color_palette["rot"] = PaletteEntry(meaning="noch leer")
        path = PLANS_DIR / "empty_column.json"
        ctx = _make_ctx(FakePlanRepository(plans={path: deserialize_plan(serialize_plan(plan))}))

        new_state = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)

        assert set(new_state.current_plan.color_palette) == {"gelb", "rot"}


class TestFlagColumns:
    """Ja/Nein-Spalten = Paletteneinträge; leer angelegt bleiben sie, bis die letzte Markierung geht."""

    def _state(self, plan):
        return AppState(current_plan=plan, current_plan_path=PLANS_DIR / "x.json")

    def test_new_empty_column_survives_other_edits(self):
        plan, (student,) = _plan_with_yellow()
        ctx = _make_ctx()
        state = handle_add_flag_column(AddFlagColumnIntent(title=" Material da ", color_key="rot"), self._state(plan), ctx)
        assert state.current_plan.color_palette["rot"] == PaletteEntry(meaning="Material da")
        state = handle_toggle_color(ToggleColorIntent(student_id=student.student_id, color_key="gelb"), state, ctx)
        assert set(state.current_plan.color_palette) == {"rot"}

    def test_column_disappears_when_its_last_mark_is_removed(self):
        plan, (student,) = _plan_with_yellow()
        ctx = _make_ctx()
        state = handle_add_flag_column(AddFlagColumnIntent(title="Material da", color_key=None), self._state(plan), ctx)
        (key,) = [k for k in state.current_plan.color_palette if k != "gelb"]
        assert key.startswith("flag_")
        toggle = ToggleColorIntent(student_id=student.student_id, color_key=key)
        state = handle_toggle_color(toggle, state, ctx)
        assert key in state.current_plan.student_by_id(student.student_id).diagnostic.color_tags
        state = handle_toggle_color(toggle, state, ctx)
        assert key not in state.current_plan.color_palette

    def test_taken_color_is_rejected(self):
        plan, _students = _plan_with_yellow()
        state = handle_add_flag_column(AddFlagColumnIntent(title="x", color_key="gelb"), self._state(plan), _make_ctx())
        assert state.current_plan.color_palette["gelb"].meaning == "Förderbedarf"
        assert "vergeben" in state.status_message

    def test_delete_removes_marks_and_entry(self):
        plan, students = _plan_with_yellow(carriers=2)
        state = handle_delete_flag_column(DeleteFlagColumnIntent(key="gelb"), self._state(plan), _make_ctx())
        assert "gelb" not in state.current_plan.color_palette
        assert all(not s.diagnostic.color_tags for s in state.current_plan.classroom.students)

    def test_add_flag_column_usecase_returns_the_key(self):
        next_plan, key = add_flag_column(make_plan(), "Brille", "blau")
        assert key == "blau" and next_plan.color_palette == {"blau": PaletteEntry(meaning="Brille")}


class TestPaletteFileFormat:
    def test_serializes_meaning_only(self):
        plan, _students = _plan_with_yellow()
        assert serialize_plan(plan)["color_palette"] == {"gelb": {"meaning": "Förderbedarf"}}

    def test_legacy_label_and_hex_are_ignored(self):
        payload = serialize_plan(make_plan())
        payload["color_palette"] = {"gelb": {"label": "Gelb", "hex": "#f4d35e", "meaning": "Förderbedarf"}}
        assert deserialize_plan(payload).color_palette == {"gelb": PaletteEntry(meaning="Förderbedarf")}
