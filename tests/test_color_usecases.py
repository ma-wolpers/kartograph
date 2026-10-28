"""Tests für v4 color_usecases (Farbpunkt-Bedeutungen in der Palette).

Abgesichert sind Lesen/Setzen der Bedeutung, die Invariante "die Palette
enthält nur getragene Farben" beim Übernehmen eines Planzustands (über den
echten Toggle-Handler) und beim Öffnen, sowie das Dateiformat (nur
``meaning``, alte ``label``/``hex``-Felder werden ignoriert). Nur synthetische Daten.
"""

from __future__ import annotations

from app.application.app_state import AppState
from app.application.handlers.color_handlers import handle_toggle_color
from app.application.handlers.plan_handlers import handle_open_plan
from app.core.domain.models_v4 import PaletteEntry
from app.core.intents.color_intents import ToggleColorIntent
from app.core.intents.plan_intents import OpenPlanIntent
from app.core.usecases.v4.color_usecases import drop_unused_palette_entries, palette_meaning, set_palette_meaning
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


class TestUnusedPaletteInvariant:
    def test_drop_keeps_only_carried_colors(self):
        plan, _students = _plan_with_yellow()
        plan.color_palette["rot"] = PaletteEntry(meaning="niemand trägt das")
        drop_unused_palette_entries(plan)
        assert set(plan.color_palette) == {"gelb"}

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

    def test_opening_a_file_drops_orphaned_meanings(self):
        plan, _students = _plan_with_yellow()
        plan.color_palette["rot"] = PaletteEntry(meaning="verwaist")
        path = PLANS_DIR / "orphan.json"
        ctx = _make_ctx(FakePlanRepository(plans={path: deserialize_plan(serialize_plan(plan))}))

        new_state = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)

        assert set(new_state.current_plan.color_palette) == {"gelb"}


class TestPaletteFileFormat:
    def test_serializes_meaning_only(self):
        plan, _students = _plan_with_yellow()
        assert serialize_plan(plan)["color_palette"] == {"gelb": {"meaning": "Förderbedarf"}}

    def test_legacy_label_and_hex_are_ignored(self):
        payload = serialize_plan(make_plan())
        payload["color_palette"] = {"gelb": {"label": "Gelb", "hex": "#f4d35e", "meaning": "Förderbedarf"}}
        assert deserialize_plan(payload).color_palette == {"gelb": PaletteEntry(meaning="Förderbedarf")}
