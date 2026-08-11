"""B6 — Tests für Handler-Isolation und Controller-Integration.

Abdeckung:
  - Handler-Funktionen direkt aufgerufen (kein GUI, kein Tkinter)
  - KartographAppController: dispatch → state-Update → Callback
"""

from __future__ import annotations

import dataclasses
import tempfile
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from app.application.app_controller import KartographAppController
from app.application.app_state import AppState, EditorSurface, InteractionMode
from app.application.handler_context import HandlerContext
from app.application.handlers.accommodation_handlers import handle_set_accommodations
from app.application.handlers.edit_handlers import (
    handle_copy_selection,
    handle_cut_selection,
    handle_paste_selection,
    handle_redo,
    handle_undo,
)
from app.application.handlers.grade_handlers import handle_add_grade_column, handle_delete_grade_column
from app.application.handlers.navigation_handlers import (
    handle_clear_selection,
    handle_move_selection,
    handle_select_cell,
)
from app.application.handlers.plan_handlers import (
    handle_create_plan,
    handle_delete_plan,
    handle_duplicate_plan,
    handle_open_plan,
)
from app.application.handlers.session_handlers import (
    handle_add_session,
    handle_go_to_today,
    handle_navigate_session,
)
from app.application.handlers.student_handlers import (
    handle_create_student,
    handle_delete_student,
    handle_rename_student,
)
from app.application.handlers.view_handlers import (
    handle_open_settings,
    handle_reset_view,
    handle_update_settings,
    handle_zoom_in,
    handle_zoom_out,
)
from app.core.domain.models_v4 import Session, SessionEntry
from app.core.domain.plan_history import PlanHistory
from app.core.domain.plan_selection import RectSelection
from app.core.domain.settings import KartographSettings
from app.core.domain.student_id import StudentId
from app.core.intents.accommodation_intents import SetAccommodationsIntent
from app.core.intents.edit_intents import (
    CopySelectionIntent,
    CutSelectionIntent,
    PasteSelectionIntent,
    RedoIntent,
    UndoIntent,
)
from app.core.intents.grade_intents import AddGradeColumnIntent, DeleteGradeColumnIntent
from app.core.intents.navigation_intents import (
    ClearSelectionIntent,
    MoveSelectionIntent,
    SelectCellIntent,
)
from app.core.intents.plan_intents import (
    CreatePlanIntent,
    DeletePlanIntent,
    DuplicatePlanIntent,
    OpenPlanIntent,
)
from app.core.intents.session_intents import AddSessionIntent, GoToTodayIntent, NavigateSessionIntent
from app.core.intents.student_intents import (
    CreateStudentIntent,
    DeleteStudentIntent,
    RenameStudentIntent,
)
from app.core.intents.view_intents import (
    OpenSettingsIntent,
    ResetViewIntent,
    SetEditorSurfaceIntent,
    UpdateSettingsIntent,
    ZoomInIntent,
    ZoomOutIntent,
)
from tests.conftest import make_plan, make_student


# ---------------------------------------------------------------------------
# Fake-Infrastruktur (kein I/O, kein Tkinter)
# ---------------------------------------------------------------------------

class FakePlanRepository:
    """In-Memory-Repository für Tests."""

    def __init__(self, plans: dict[Path, object] | None = None) -> None:
        from app.core.domain.models_v4 import Classroom, PlanMeta, SeatingPlan, TeacherSeat
        self._plans: dict[Path, object] = plans or {}
        self._SeatingPlan = SeatingPlan
        self._PlanMeta = PlanMeta
        self._Classroom = Classroom
        self._TeacherSeat = TeacherSeat

    def list_plans(self, plans_dir: Path) -> list[tuple[Path, object]]:
        return list(self._plans.items())

    def load_plan(self, plan_path: Path) -> object:
        if plan_path not in self._plans:
            raise FileNotFoundError(f"Plan nicht gefunden: {plan_path}")
        return self._plans[plan_path]

    def save_plan(self, plan: object, plan_path: Path) -> None:
        self._plans[plan_path] = plan

    def create_new_plan(
        self, plans_dir: Path, plan_name: str, overwrite: bool = False
    ) -> tuple[Path, object]:
        name = plan_name.strip() or "Neuer Sitzplan"
        path = plans_dir / f"{name}.json"
        plan = self._SeatingPlan(
            format_version=4,
            plan_id="fakeid",
            meta=self._PlanMeta(name=name),
            classroom=self._Classroom(teacher_seat=self._TeacherSeat(x=0, y=0)),
        )
        self._plans[path] = plan
        return path, plan

    def rename_plan(
        self, source_path: Path, new_name: str, overwrite: bool = False
    ) -> tuple[Path, object]:
        plan = self._plans.pop(source_path)
        plan.meta.name = new_name
        new_path = source_path.with_name(f"{new_name}.json")
        self._plans[new_path] = plan
        return new_path, plan

    def delete_plan(self, plan_path: Path) -> None:
        self._plans.pop(plan_path, None)

    def duplicate_plan(
        self, source_path: Path, target_name: str, overwrite: bool = False
    ) -> tuple[Path, object]:
        target_path = source_path.with_name(f"{target_name}.json")
        if target_path != source_path and target_path in self._plans and not overwrite:
            raise FileExistsError(f"Plandatei existiert bereits: {target_path.name}")
        clone = deepcopy(self._plans[source_path])
        clone.meta.name = target_name
        self._plans[target_path] = clone
        return target_path, clone

    def plan_name_taken(self, source_path: Path, name: str) -> bool:
        target_path = source_path.with_name(f"{name}.json")
        return target_path != source_path and target_path in self._plans


class FakeSettingsRepository:
    """In-Memory-Settings-Repository für Tests (persistiert tatsächlich)."""

    def __init__(self, initial: dict | None = None) -> None:
        self._payload: dict = dict(initial or {})

    def load_settings(self) -> dict:
        return dict(self._payload)

    def save_settings(self, payload: dict) -> None:
        self._payload = dict(payload)


PLANS_DIR = Path("/fake/plans")
# Echtes temporäres Verzeichnis (nicht "/fake/..."), da load_symbol_definitions()
# beim Controller-Start tatsächlich Dateien liest/anlegt.
SYMBOLS_PATH = Path(tempfile.mkdtemp()) / "symbols.json"


def make_ctx(plans: dict | None = None) -> HandlerContext:
    return HandlerContext(
        plan_repository=FakePlanRepository(plans),
        settings_repository=FakeSettingsRepository(),
        history=PlanHistory(),
        default_plans_dir=PLANS_DIR,
    )


def make_state_with_plan(plan=None, path: Path | None = None) -> AppState:
    p = plan or make_plan()
    pt = path or PLANS_DIR / "test.json"
    return AppState(
        current_plan=p,
        current_plan_path=pt,
        interaction_mode=InteractionMode.GRID,
    )


# ---------------------------------------------------------------------------
# Handler-Isolation: Plan-Handler
# ---------------------------------------------------------------------------

class TestHandlePlanHandlers:
    def test_open_plan_sets_current_plan(self):
        plan = make_plan(name="Klasse 5a")
        path = PLANS_DIR / "klasse5a.json"
        ctx = make_ctx({path: plan})
        state = AppState()

        result = handle_open_plan(OpenPlanIntent(plan_path=path), state, ctx)

        assert result.current_plan is plan
        assert result.current_plan_path == path

    def test_open_plan_sets_interaction_mode_to_grid(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})

        result = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)

        assert result.interaction_mode == InteractionMode.GRID

    def test_open_plan_resets_undo_redo(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})

        result = handle_open_plan(OpenPlanIntent(plan_path=path), AppState(), ctx)

        assert result.can_undo is False
        assert result.can_redo is False

    def test_open_plan_with_missing_file_returns_error_status(self):
        ctx = make_ctx()
        missing = PLANS_DIR / "missing.json"

        result = handle_open_plan(OpenPlanIntent(plan_path=missing), AppState(), ctx)

        assert result.current_plan is None
        assert "missing" in result.status_message.lower() or result.status_message != ""

    def test_create_plan_returns_new_plan(self):
        ctx = make_ctx()

        result = handle_create_plan(CreatePlanIntent(name="Neue Klasse"), AppState(), ctx)

        assert result.current_plan is not None
        assert result.current_plan.meta.name == "Neue Klasse"

    def test_create_plan_sets_grid_mode(self):
        ctx = make_ctx()

        result = handle_create_plan(CreatePlanIntent(name="X"), AppState(), ctx)

        assert result.interaction_mode == InteractionMode.GRID

    def test_delete_open_plan_clears_current_plan(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_delete_plan(DeletePlanIntent(plan_path=path), state, ctx)

        assert result.current_plan is None
        assert result.current_plan_path is None
        assert result.interaction_mode == InteractionMode.LIST

    def test_delete_other_plan_keeps_current_plan(self):
        plan = make_plan()
        current_path = PLANS_DIR / "current.json"
        other_path = PLANS_DIR / "other.json"
        ctx = make_ctx({current_path: plan, other_path: make_plan()})
        state = make_state_with_plan(plan, current_path)

        result = handle_delete_plan(DeletePlanIntent(plan_path=other_path), state, ctx)

        assert result.current_plan is plan

    def test_duplicate_plan_creates_copy_with_chosen_name(self):
        plan = make_plan(name="Klasse 5a")
        path = PLANS_DIR / "klasse5a.json"
        ctx = make_ctx({path: plan})

        result = handle_duplicate_plan(
            DuplicatePlanIntent(plan_path=path, new_name="Klasse 5a Kopie"), AppState(), ctx
        )

        new_path = PLANS_DIR / "Klasse 5a Kopie.json"
        assert ctx.plan_repository._plans[new_path].meta.name == "Klasse 5a Kopie"
        assert any(entry.path == new_path for entry in result.plan_list)

    def test_duplicate_plan_with_name_conflict_returns_error_status(self):
        plan = make_plan()
        path = PLANS_DIR / "klasse5a.json"
        conflict_path = PLANS_DIR / "Kopie.json"
        ctx = make_ctx({path: plan, conflict_path: make_plan(name="Kopie")})

        result = handle_duplicate_plan(
            DuplicatePlanIntent(plan_path=path, new_name="Kopie"), AppState(), ctx
        )

        assert result.status_message != ""
        assert "fehler" in result.status_message.lower()

    def test_duplicate_plan_with_overwrite_replaces_conflicting_file(self):
        plan = make_plan(name="Original")
        path = PLANS_DIR / "klasse5a.json"
        conflict_path = PLANS_DIR / "Kopie.json"
        ctx = make_ctx({path: plan, conflict_path: make_plan(name="Kopie")})

        result = handle_duplicate_plan(
            DuplicatePlanIntent(plan_path=path, new_name="Kopie", overwrite=True), AppState(), ctx
        )

        assert ctx.plan_repository._plans[conflict_path].meta.name == "Kopie"
        assert result.status_message == "Plan dupliziert: Kopie"


# ---------------------------------------------------------------------------
# Handler-Isolation: Student-Handler
# ---------------------------------------------------------------------------

class TestHandleStudentHandlers:
    def test_create_student_adds_student_to_plan(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_create_student(CreateStudentIntent(x=2, y=1), state, ctx)

        assert result.current_plan.student_at(2, 1) is not None

    def test_create_student_sets_name_edit_mode(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_create_student(CreateStudentIntent(x=2, y=1), state, ctx)

        assert result.interaction_mode == InteractionMode.NAME_EDIT

    def test_create_student_no_effect_without_plan(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_create_student(CreateStudentIntent(x=1, y=0), state, ctx)

        assert result is state

    def test_delete_student_removes_from_plan(self):
        student = make_student(x=1, y=0)
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_delete_student(DeleteStudentIntent(student_id=student.student_id), state, ctx)

        assert result.current_plan.student_by_id(student.student_id) is None

    def test_rename_student_updates_names(self):
        student = make_student(first_name="", last_name="")
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_rename_student(
            RenameStudentIntent(student_id=student.student_id, first_name="Max", last_name="Muster"),
            state,
            ctx,
        )

        s = result.current_plan.student_by_id(student.student_id)
        assert s.first_name == "Max"
        assert s.last_name == "Muster"

    def test_rename_student_sets_grid_mode(self):
        student = make_student()
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = AppState(
            current_plan=plan,
            current_plan_path=path,
            interaction_mode=InteractionMode.NAME_EDIT,
        )

        result = handle_rename_student(
            RenameStudentIntent(student_id=student.student_id, first_name="X", last_name="Y"),
            state,
            ctx,
        )

        assert result.interaction_mode == InteractionMode.GRID


# ---------------------------------------------------------------------------
# Handler-Isolation: Clipboard-Handler (T4 — Copy/Cut/Paste)
# ---------------------------------------------------------------------------

class TestHandleClipboardHandlers:
    def test_copy_selection_fills_clipboard_without_changing_plan(self):
        student = make_student(x=1, y=0)
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_copy_selection(CopySelectionIntent(cells=((1, 0),)), state, ctx)

        assert result.current_plan is plan
        assert ctx.clipboard.has_content() is True
        assert "1" in result.status_message

    def test_copy_selection_without_plan_is_noop(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_copy_selection(CopySelectionIntent(cells=((1, 0),)), state, ctx)

        assert result is state
        assert ctx.clipboard.has_content() is False

    def test_cut_selection_does_not_remove_student_yet(self):
        student = make_student(x=1, y=0)
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_cut_selection(CutSelectionIntent(cells=((1, 0),)), state, ctx)

        assert result.current_plan.student_by_id(student.student_id) is not None
        assert ctx.clipboard.has_content() is True

    def test_paste_after_cut_moves_student_and_saves(self):
        student = make_student(x=1, y=0)
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)
        state = handle_cut_selection(CutSelectionIntent(cells=((1, 0),)), state, ctx)

        result = handle_paste_selection(PasteSelectionIntent(target_x=3, target_y=0), state, ctx)

        assert result.current_plan.student_at(1, 0) is None
        moved = result.current_plan.student_at(3, 0)
        assert moved is not None
        assert moved.student_id == student.student_id
        assert ctx.plan_repository.load_plan(path).student_at(3, 0) is not None

    def test_paste_after_copy_creates_new_id(self):
        student = make_student(x=1, y=0)
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)
        state = handle_copy_selection(CopySelectionIntent(cells=((1, 0),)), state, ctx)

        result = handle_paste_selection(PasteSelectionIntent(target_x=3, target_y=0), state, ctx)

        clone = result.current_plan.student_at(3, 0)
        assert clone is not None
        assert clone.student_id != student.student_id
        assert result.current_plan.student_at(1, 0) is not None

    def test_paste_with_empty_clipboard_returns_status_message(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_paste_selection(PasteSelectionIntent(target_x=1, target_y=0), state, ctx)

        assert result.current_plan is plan
        assert result.status_message != ""

    def test_paste_blocked_by_teacher_seat_reports_status_without_saving(self):
        student = make_student(x=1, y=0)
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)
        state = handle_copy_selection(CopySelectionIntent(cells=((1, 0),)), state, ctx)

        result = handle_paste_selection(PasteSelectionIntent(target_x=0, target_y=0), state, ctx)

        assert result.current_plan is plan
        assert "Lehrertisch" in result.status_message


# ---------------------------------------------------------------------------
# Handler-Isolation: Noten-Handler (T6 — Notenspalte löschen)
# ---------------------------------------------------------------------------

class TestHandleGradeColumnHandlers:
    def test_add_grade_column_appends_column(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_add_grade_column(
            AddGradeColumnIntent(category="schriftlich", title="Mathearbeit 1"), state, ctx
        )

        assert len(result.current_plan.documentation.grade_columns) == 1
        assert result.current_plan.documentation.grade_columns[0].title == "Mathearbeit 1"

    def test_delete_grade_column_removes_column(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)
        state = handle_add_grade_column(
            AddGradeColumnIntent(category="schriftlich", title="Mathearbeit 1"), state, ctx
        )
        column_id = state.current_plan.documentation.grade_columns[0].column_id

        result = handle_delete_grade_column(DeleteGradeColumnIntent(column_id=column_id), state, ctx)

        assert result.current_plan.documentation.grade_columns == []

    def test_delete_grade_column_purges_recorded_grades_from_sessions(self):
        student = make_student(x=1, y=0)
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)
        state = handle_add_grade_column(
            AddGradeColumnIntent(category="schriftlich", title="Mathearbeit 1"), state, ctx
        )
        column_id = state.current_plan.documentation.grade_columns[0].column_id
        state.current_plan.documentation.sessions.append(
            Session(date="2025-09-01", entries={student.student_id: SessionEntry(grades={column_id: 2.0})})
        )

        result = handle_delete_grade_column(DeleteGradeColumnIntent(column_id=column_id), state, ctx)

        session = result.current_plan.documentation.session_for_date("2025-09-01")
        assert column_id not in session.entry_for(student.student_id).grades

    def test_delete_grade_column_clears_selected_column_in_state(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)
        state = handle_add_grade_column(
            AddGradeColumnIntent(category="schriftlich", title="Mathearbeit 1"), state, ctx
        )
        column_id = state.current_plan.documentation.grade_columns[0].column_id
        state = dataclasses.replace(state, doc_selected_column_id=column_id)

        result = handle_delete_grade_column(DeleteGradeColumnIntent(column_id=column_id), state, ctx)

        assert result.doc_selected_column_id is None

    def test_delete_grade_column_without_plan_is_noop(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_delete_grade_column(DeleteGradeColumnIntent(column_id="missing"), state, ctx)

        assert result is state


# ---------------------------------------------------------------------------
# Handler-Isolation: Accommodation-Handler
# ---------------------------------------------------------------------------

class TestHandleAccommodationHandlers:
    def test_set_accommodations_updates_student(self):
        student = make_student()
        plan = make_plan(students=[student])
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_set_accommodations(
            SetAccommodationsIntent(student_id=student.student_id, accommodations=["Zeitzuschlag 25 %"]),
            state,
            ctx,
        )

        s = result.current_plan.student_by_id(student.student_id)
        assert s.diagnostic.accommodations == ["Zeitzuschlag 25 %"]

    def test_set_accommodations_without_plan_is_noop(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_set_accommodations(
            SetAccommodationsIntent(student_id=StudentId.new(), accommodations=["X"]),
            state,
            ctx,
        )

        assert result is state


# ---------------------------------------------------------------------------
# Handler-Isolation: View/Settings-Handler
# ---------------------------------------------------------------------------

class TestHandleViewHandlers:
    def test_open_settings_loads_from_repository(self):
        ctx = make_ctx()
        ctx.settings_repository = FakeSettingsRepository({"canvas_radius": 12, "theme": "porcelain"})

        result = handle_open_settings(OpenSettingsIntent(), AppState(), ctx)

        assert result.settings.canvas_radius == 12
        assert result.settings.theme == "porcelain"

    def test_update_settings_persists_and_updates_state(self):
        ctx = make_ctx()
        new_settings = KartographSettings(canvas_radius=7)

        result = handle_update_settings(UpdateSettingsIntent(settings=new_settings), AppState(), ctx)

        assert result.settings.canvas_radius == 7
        assert ctx.settings_repository.load_settings()["canvas_radius"] == 7


# ---------------------------------------------------------------------------
# Handler-Isolation: Viewport-Handler (Zoom/Reset)
# ---------------------------------------------------------------------------

class TestHandleViewportHandlers:
    def test_zoom_in_increases_cell_size(self):
        ctx = make_ctx()
        state = AppState(cell_size=92)

        result = handle_zoom_in(ZoomInIntent(), state, ctx)

        assert result.cell_size == 100

    def test_zoom_in_clamps_at_max(self):
        ctx = make_ctx()
        state = AppState(cell_size=160)

        result = handle_zoom_in(ZoomInIntent(), state, ctx)

        assert result.cell_size == 160

    def test_zoom_out_decreases_cell_size(self):
        ctx = make_ctx()
        state = AppState(cell_size=92)

        result = handle_zoom_out(ZoomOutIntent(), state, ctx)

        assert result.cell_size == 84

    def test_zoom_out_clamps_at_min(self):
        ctx = make_ctx()
        state = AppState(cell_size=44)

        result = handle_zoom_out(ZoomOutIntent(), state, ctx)

        assert result.cell_size == 44

    def test_reset_view_restores_default_cell_size(self):
        ctx = make_ctx()
        state = AppState(cell_size=160)

        result = handle_reset_view(ResetViewIntent(), state, ctx)

        assert result.cell_size == 92


# ---------------------------------------------------------------------------
# Handler-Isolation: Session-Handler (Datum anlegen/navigieren)
# ---------------------------------------------------------------------------

class TestHandleSessionHandlers:
    def test_add_session_creates_session_for_date(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx = make_ctx({path: plan})
        state = make_state_with_plan(plan, path)

        result = handle_add_session(AddSessionIntent(date="2025-09-01"), state, ctx)

        assert result.current_plan.documentation.session_for_date("2025-09-01") is not None
        assert result.doc_selected_date == "2025-09-01"

    def test_add_session_without_plan_is_noop(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_add_session(AddSessionIntent(date="2025-09-01"), state, ctx)

        assert result is state

    def test_navigate_session_next_moves_to_later_date(self):
        plan = make_plan()
        plan.documentation.sessions = [Session(date="2025-09-01"), Session(date="2025-09-03")]
        ctx = make_ctx()
        state = make_state_with_plan(plan)
        state = dataclasses.replace(state, doc_selected_date="2025-09-01")

        result = handle_navigate_session(NavigateSessionIntent(direction="next"), state, ctx)

        assert result.doc_selected_date == "2025-09-03"

    def test_navigate_session_prev_moves_to_earlier_date(self):
        plan = make_plan()
        plan.documentation.sessions = [Session(date="2025-09-01"), Session(date="2025-09-03")]
        ctx = make_ctx()
        state = make_state_with_plan(plan)
        state = dataclasses.replace(state, doc_selected_date="2025-09-03")

        result = handle_navigate_session(NavigateSessionIntent(direction="prev"), state, ctx)

        assert result.doc_selected_date == "2025-09-01"

    def test_navigate_session_includes_virtual_today_date(self):
        """Heute ist immer navigierbar, auch ohne gespeicherte Session (s. GUI-_doc_dates)."""
        plan = make_plan()
        plan.documentation.sessions = [Session(date="2025-09-01"), Session(date="2025-09-03")]
        ctx = make_ctx()
        state = make_state_with_plan(plan)
        state = dataclasses.replace(state, doc_selected_date="2025-09-03")

        result = handle_navigate_session(NavigateSessionIntent(direction="next"), state, ctx)

        today = date.today().isoformat()
        expected = "2025-09-03" if today <= "2025-09-03" else today
        assert result.doc_selected_date == expected

    def test_navigate_session_without_plan_is_noop(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_navigate_session(NavigateSessionIntent(direction="next"), state, ctx)

        assert result is state

    def test_go_to_today_sets_todays_date(self):
        plan = make_plan()
        ctx = make_ctx()
        state = make_state_with_plan(plan)

        result = handle_go_to_today(GoToTodayIntent(), state, ctx)

        assert result.doc_selected_date == date.today().isoformat()


# ---------------------------------------------------------------------------
# Handler-Isolation: Navigation-Handler
# ---------------------------------------------------------------------------

class TestHandleNavigationHandlers:
    def test_select_cell_updates_selection(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_select_cell(SelectCellIntent(x=3, y=2), state, ctx)

        assert result.selection.anchor_x == 3
        assert result.selection.anchor_y == 2

    def test_select_cell_sets_grid_mode(self):
        ctx = make_ctx()
        result = handle_select_cell(SelectCellIntent(x=1, y=1), AppState(), ctx)
        assert result.interaction_mode == InteractionMode.GRID

    def test_move_selection_shifts_focus(self):
        ctx = make_ctx()
        state = AppState(selection=RectSelection(2, 3))

        result = handle_move_selection(MoveSelectionIntent(dx=1, dy=-1), state, ctx)

        assert result.selection.focus_x == 3
        assert result.selection.focus_y == 2

    def test_clear_selection_sets_list_mode(self):
        ctx = make_ctx()
        state = AppState(interaction_mode=InteractionMode.GRID)

        result = handle_clear_selection(ClearSelectionIntent(), state, ctx)

        assert result.interaction_mode == InteractionMode.LIST


# ---------------------------------------------------------------------------
# Handler-Isolation: Undo/Redo
# ---------------------------------------------------------------------------

class TestHandleUndoRedo:
    def _state_after_change(self, ctx: HandlerContext) -> AppState:
        """Hilfsmethode: Erzeugt State mit einem Plan und einem History-Eintrag."""
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctx.plan_repository.save_plan(plan, path)
        ctx.history.reset(plan)
        student = make_student(x=1, y=0)
        plan_v2 = make_plan(students=[student])
        ctx.history.record(plan_v2, "student.create")
        return AppState(current_plan=plan_v2, current_plan_path=path)

    def test_undo_restores_previous_plan(self):
        ctx = make_ctx()
        state = self._state_after_change(ctx)

        result = handle_undo(UndoIntent(), state, ctx)

        assert result.current_plan.student_at(1, 0) is None

    def test_undo_updates_can_undo_flag(self):
        ctx = make_ctx()
        state = self._state_after_change(ctx)

        result = handle_undo(UndoIntent(), state, ctx)

        assert result.can_undo is False

    def test_undo_enables_redo(self):
        ctx = make_ctx()
        state = self._state_after_change(ctx)

        result = handle_undo(UndoIntent(), state, ctx)

        assert result.can_redo is True

    def test_redo_reapplies_undone_change(self):
        ctx = make_ctx()
        state = self._state_after_change(ctx)
        after_undo = handle_undo(UndoIntent(), state, ctx)

        result = handle_redo(RedoIntent(), after_undo, ctx)

        assert result.current_plan.student_at(1, 0) is not None

    def test_undo_without_history_returns_message(self):
        ctx = make_ctx()
        plan = make_plan()
        ctx.history.reset(plan)
        path = PLANS_DIR / "test.json"
        ctx.plan_repository.save_plan(plan, path)
        state = AppState(current_plan=plan, current_plan_path=path)

        result = handle_undo(UndoIntent(), state, ctx)

        assert result.status_message != ""

    def test_undo_without_plan_returns_unchanged_state(self):
        ctx = make_ctx()
        state = AppState()

        result = handle_undo(UndoIntent(), state, ctx)

        assert result is state


# ---------------------------------------------------------------------------
# Controller-Integration
# ---------------------------------------------------------------------------

class TestKartographAppController:
    def _make_controller(
        self,
        plans: dict | None = None,
    ) -> tuple[KartographAppController, list[AppState]]:
        received: list[AppState] = []
        ctrl = KartographAppController(
            plan_repository=FakePlanRepository(plans),
            settings_repository=FakeSettingsRepository(),
            default_plans_dir=PLANS_DIR,
            symbols_path=SYMBOLS_PATH,
            on_state_changed=received.append,
        )
        return ctrl, received

    # --- Initialzustand -------------------------------------------------------

    def test_initial_state_has_no_plan(self):
        ctrl, _ = self._make_controller()
        assert ctrl.state.current_plan is None

    def test_initial_interaction_mode_is_list(self):
        ctrl, _ = self._make_controller()
        assert ctrl.state.interaction_mode == InteractionMode.LIST

    # --- Alle Intent-Typen registriert ----------------------------------------

    def test_all_intents_from_package_are_registered(self):
        import app.core.intents as pkg

        ctrl, _ = self._make_controller()
        registered = set(ctrl._registry.registered_types())

        for name in pkg.__all__:
            cls = getattr(pkg, name)
            if isinstance(cls, type) and issubclass(cls, pkg.Intent) and cls is not pkg.Intent:
                assert cls in registered, f"{name} ist nicht im Controller registriert"

    # --- dispatch → state + Callback ------------------------------------------

    def test_dispatch_open_plan_sets_current_plan(self):
        plan = make_plan(name="Klasse 6b")
        path = PLANS_DIR / "klasse6b.json"
        ctrl, _ = self._make_controller({path: plan})

        ctrl.dispatch(OpenPlanIntent(plan_path=path))

        assert ctrl.state.current_plan is plan

    def test_dispatch_open_plan_triggers_callback(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctrl, received = self._make_controller({path: plan})

        ctrl.dispatch(OpenPlanIntent(plan_path=path))

        assert len(received) == 1
        assert received[0].current_plan is plan

    def test_dispatch_unknown_intent_does_not_call_callback(self):
        from app.core.intents.base import Intent
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class UnknownIntent(Intent):
            pass

        ctrl, received = self._make_controller()

        ctrl.dispatch(UnknownIntent())

        assert received == []

    def test_dispatch_create_plan_sets_plan_in_state(self):
        ctrl, _ = self._make_controller()

        ctrl.dispatch(CreatePlanIntent(name="Neue Klasse"))

        assert ctrl.state.current_plan is not None
        assert ctrl.state.current_plan.meta.name == "Neue Klasse"

    def test_dispatch_create_student_after_open(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctrl, _ = self._make_controller({path: plan})
        ctrl.dispatch(OpenPlanIntent(plan_path=path))

        ctrl.dispatch(CreateStudentIntent(x=2, y=1))

        assert ctrl.state.current_plan.student_at(2, 1) is not None

    def test_dispatch_select_cell_updates_state(self):
        ctrl, _ = self._make_controller()

        ctrl.dispatch(SelectCellIntent(x=4, y=2))

        assert ctrl.state.selection.anchor_x == 4
        assert ctrl.state.selection.anchor_y == 2

    def test_dispatch_set_editor_surface_to_documentation(self):
        ctrl, _ = self._make_controller()

        ctrl.dispatch(SetEditorSurfaceIntent(surface="documentation"))

        assert ctrl.state.editor_surface == EditorSurface.DOCUMENTATION

    # --- Undo/Redo via Controller ---------------------------------------------

    def test_undo_redo_roundtrip_via_controller(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctrl, _ = self._make_controller({path: plan})
        ctrl.dispatch(OpenPlanIntent(plan_path=path))

        ctrl.dispatch(CreateStudentIntent(x=1, y=0))
        assert ctrl.state.current_plan.student_at(1, 0) is not None
        assert ctrl.state.can_undo is True

        ctrl.dispatch(UndoIntent())
        assert ctrl.state.current_plan.student_at(1, 0) is None
        assert ctrl.state.can_redo is True

        ctrl.dispatch(RedoIntent())
        assert ctrl.state.current_plan.student_at(1, 0) is not None

    # --- Callback-Fehlertoleranz ----------------------------------------------

    def test_callback_exception_does_not_crash_controller(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"

        def bad_callback(s: AppState) -> None:
            raise RuntimeError("GUI crashed")

        ctrl = KartographAppController(
            plan_repository=FakePlanRepository({path: plan}),
            settings_repository=FakeSettingsRepository(),
            default_plans_dir=PLANS_DIR,
            symbols_path=SYMBOLS_PATH,
            on_state_changed=bad_callback,
        )

        ctrl.dispatch(OpenPlanIntent(plan_path=path))  # darf nicht werfen

        assert ctrl.state.current_plan is plan
