"""Tischgruppen-Einstellungen: ein Undo-Schritt je Übernehmen, Überlappungen werden aufgelöst.

Früher schrieb das Overlay am Undo-Verlauf vorbei: Die Einstellung ließ sich nicht
rückgängig machen, und das Undo der nächsten Änderung nahm sie mit zurück.
"""

from __future__ import annotations

import pytest

from app.application.handlers.edit_handlers import handle_undo
from app.application.handlers.symbol_handlers import handle_record_documentation_symbol
from app.application.handlers.tablegroup_handlers import handle_apply_tablegroup_settings
from app.core.domain.models_v4 import TeacherSeat
from app.core.intents.edit_intents import UndoIntent
from app.core.intents.symbol_intents import RecordDocumentationSymbolIntent
from app.core.intents.tablegroup_intents import ApplyTablegroupSettingsIntent
from app.core.usecases.v4.tablegroup_usecases import (
    RESET_ALL_TRANSFORMS,
    apply_normalized_tablegroups,
    apply_tablegroup_settings,
    get_tablegroup_settings,
    tablegroup_number_at,
)
from app.tools.isolated_window import open_isolated_window
from tests.conftest import make_plan, make_student
from tests.test_app_controller import PLANS_DIR, make_ctx, make_state_with_plan

PATH = PLANS_DIR / "test.json"
OVERLAPPING_SHIFT = -0.45  # schiebt den Tisch auf (1, 0) in den Lehrertisch auf (0, 0)


def _plan():
    """Zwei getrennte Tischgruppen, die erste steht direkt neben dem Lehrertisch."""
    plan = make_plan(students=[make_student(x=1, y=0), make_student(x=5, y=0, first_name="Ben")])
    plan.classroom.teacher_seat = TeacherSeat(x=0, y=0)
    apply_normalized_tablegroups(plan)
    return plan


def _settings(plan, x=1, y=0):
    return get_tablegroup_settings(plan, tablegroup_number_at(plan, x, y))


def _apply(plan, *, x=1, number=None, shift_x=0.0, shift_y=0.0, rotation=0.0, last="shift_x"):
    return apply_tablegroup_settings(
        plan,
        x,
        0,
        number=tablegroup_number_at(plan, x, 0) if number is None else number,
        shift_x=shift_x,
        shift_y=shift_y,
        rotation=rotation,
        last_changed_field=last,
    )


class TestApplyTablegroupSettings:
    def test_values_are_set_and_the_input_plan_stays_unchanged(self):
        plan = _plan()
        result = _apply(plan, shift_x=0.2, shift_y=0.1, rotation=15.0)
        settings = _settings(result.plan)
        assert (settings.shift_x, settings.shift_y, settings.rotation, result.reset_field) == (0.2, 0.1, 15.0, None)
        assert _settings(plan).shift_x == 0.0

    def test_position_without_group_changes_nothing(self):
        assert _apply(_plan(), x=9).plan is None

    def test_overlap_resets_the_last_changed_field_first(self):
        result = _apply(_plan(), shift_x=OVERLAPPING_SHIFT, shift_y=0.1)
        settings = _settings(result.plan)
        assert result.reset_field == "shift_x"
        assert (settings.shift_x, settings.shift_y) == (0.0, 0.1)

    def test_overlap_resets_everything_if_the_last_field_does_not_help(self):
        result = _apply(_plan(), shift_x=OVERLAPPING_SHIFT, shift_y=0.1, last="shift_y")
        settings = _settings(result.plan)
        assert result.reset_field == RESET_ALL_TRANSFORMS
        assert (settings.shift_x, settings.shift_y, settings.rotation) == (0.0, 0.0, 0.0)

    def test_new_number_pushes_the_occupying_group_up(self):
        plan = _plan()
        other = tablegroup_number_at(plan, 5, 0)
        result = _apply(plan, number=other)
        assert tablegroup_number_at(result.plan, 1, 0) == other
        assert tablegroup_number_at(result.plan, 5, 0) == other + 1


class TestUndo:
    @pytest.fixture
    def setup(self):
        plan = _plan()
        ctx = make_ctx({PATH: plan})
        ctx.history.reset(plan, PATH)
        return ctx, make_state_with_plan(plan, PATH), plan.classroom.students[0].student_id

    @staticmethod
    def _intent(state, **values):
        fields = {"x": 1, "y": 0, "number": tablegroup_number_at(state.current_plan, 1, 0), "shift_x": 0.0}
        fields |= {"shift_y": 0.0, "rotation": 0.0, "last_changed_field": "shift_x"} | values
        return ApplyTablegroupSettingsIntent(**fields)

    def test_all_values_of_one_apply_are_one_step(self, setup):
        ctx, state, _ = setup
        state = handle_apply_tablegroup_settings(self._intent(state, shift_x=0.2, shift_y=0.1, rotation=15.0), state, ctx)
        assert state.status_message.endswith("gespeichert")

        state = handle_undo(UndoIntent(), state, ctx)

        assert _settings(state.current_plan).shift_x == 0.0
        assert _settings(state.current_plan).rotation == 0.0
        assert not state.can_undo

    def test_undoing_the_next_change_keeps_the_settings(self, setup):
        ctx, state, student_id = setup
        state = handle_apply_tablegroup_settings(self._intent(state, shift_x=0.2), state, ctx)
        state = handle_record_documentation_symbol(
            RecordDocumentationSymbolIntent(student_id=student_id, date="2025-09-01", symbol="Beteiligung", strength=1),
            state,
            ctx,
        )

        state = handle_undo(UndoIntent(), state, ctx)
        assert _settings(state.current_plan).shift_x == 0.2

        state = handle_undo(UndoIntent(), state, ctx)
        assert _settings(state.current_plan).shift_x == 0.0

    def test_two_applies_are_two_steps(self, setup):
        ctx, state, _ = setup
        for shift in (0.1, 0.2):
            state = handle_apply_tablegroup_settings(self._intent(state, shift_x=shift), state, ctx)
        assert _settings(handle_undo(UndoIntent(), state, ctx).current_plan).shift_x == 0.1

    def test_values_and_number_survive_the_normalizing_on_record(self, setup):
        ctx, state, _ = setup
        other = tablegroup_number_at(state.current_plan, 5, 0)
        state = handle_apply_tablegroup_settings(
            self._intent(state, number=other, shift_x=0.2, rotation=15.0), state, ctx
        )
        assert tablegroup_number_at(state.current_plan, 1, 0) == other
        assert (_settings(state.current_plan).shift_x, _settings(state.current_plan).rotation) == (0.2, 15.0)

    def test_position_without_group_records_nothing(self, setup):
        ctx, state, _ = setup
        state = handle_apply_tablegroup_settings(self._intent(state, x=9, number=1), state, ctx)
        assert "Schuelertische" in state.status_message
        assert not ctx.history.can_undo


class TestRealWindow:
    @pytest.fixture
    def window(self, tmp_path):
        app, close = open_isolated_window(tmp_path, _plan())
        app._set_selection_single(1, 0)
        app.open_tablegroup_settings_overlay()
        app.tk_root.update()
        yield app
        close()

    @staticmethod
    def _submit(app, *, shift_x):
        app._tg_shift_x_var.set(f"{shift_x:.2f}")
        app._set_tg_last_changed("shift_x")
        app._apply_tablegroup_overlay_values()
        app.tk_root.update()

    def test_opening_on_a_grouped_desk_fills_the_form(self, window):
        """Früher brach das Öffnen hier ab: ``TableGroupSettings`` hat ``group_id``, nicht ``number``."""
        number = tablegroup_number_at(window.current_plan, 1, 0)
        assert window._tg_number_var.get() == str(number)
        assert window._tg_status_var.get() == f"Aktive Gruppe: TG {number}"

    def test_apply_is_undoable_and_the_form_follows(self, window):
        self._submit(window, shift_x=0.2)
        assert _settings(window.current_plan).shift_x == 0.2
        assert window._tg_status_var.get().endswith("gespeichert")

        window.undo_last_change()
        window.tk_root.update()

        assert _settings(window.current_plan).shift_x == 0.0
        assert window._tg_shift_x_var.get() == "0.00"

    def test_overlap_message_stays_visible(self, window):
        self._submit(window, shift_x=OVERLAPPING_SHIFT)
        assert _settings(window.current_plan).shift_x == 0.0
        assert window._tg_status_var.get() == "Ueberlappung erkannt: x-shift auf 0 gesetzt"

    def test_settings_reach_the_file(self, window):
        self._submit(window, shift_x=0.2)
        window._flush_pending_plan_save()
        saved = window._controller.plan_repository.load_plan(window.current_plan_path)
        assert _settings(saved).shift_x == 0.2
