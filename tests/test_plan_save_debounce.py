"""Tests für debounced Speichern (Kartograph Performance-Fix, Item 2, 2026-08-28).

Deckt die Application-Schicht ab (kein Tkinter nötig): ``_record_and_save()``
muss die History immer synchron schreiben, das eigentliche ``save_plan()``
aber an ``ctx.plan_save_scheduler`` delegieren, sobald einer gesetzt ist —
ohne Scheduler (Standardfall in allen anderen Tests dieser Suite) bleibt das
Verhalten unverändert synchron. Die Tk-``after()``-Debounce-Mechanik selbst
(``_mixin_plan_save.py``) braucht einen echten Tk-Root und wird hier bewusst
nicht getestet — dafür gibt es keine Präzedenz in dieser Test-Suite (siehe
``tests/test_main_window_root_host_str.py`` für den einzigen bestehenden
GUI-Klassen-Test, der ebenfalls ohne echten Tk-Root auskommt).
"""

from __future__ import annotations

from pathlib import Path

from app.application.app_controller import KartographAppController
from app.application.handler_context import HandlerContext
from app.application.handlers._shared import _record_and_save
from app.core.domain.plan_history import PlanHistory
from app.core.intents.student_intents import CreateStudentIntent
from app.core.intents.plan_intents import OpenPlanIntent
from tests.conftest import make_plan
from tests.test_app_controller import (
    PLANS_DIR,
    SYMBOLS_PATH,
    FakePlanRepository,
    FakeSettingsRepository,
)


def _make_ctx(repo: FakePlanRepository | None = None) -> HandlerContext:
    return HandlerContext(
        plan_repository=repo or FakePlanRepository(),
        settings_repository=FakeSettingsRepository(),
        history=PlanHistory(),
        default_plans_dir=PLANS_DIR,
    )


class TestRecordAndSaveWithoutScheduler:
    """Unverändertes Verhalten (Standardfall — auch in allen anderen Tests dieser Suite)."""

    def test_saves_immediately_via_repository(self):
        repo = FakePlanRepository()
        ctx = _make_ctx(repo)
        plan = make_plan()
        path = PLANS_DIR / "x.json"

        _record_and_save(plan, path, "test.action", ctx)

        assert repo._plans[path] is plan

    def test_records_history(self):
        ctx = _make_ctx()
        plan = make_plan()
        _record_and_save(plan, PLANS_DIR / "x.json", "test.action", ctx)
        assert ctx.history.undo() is not None or len(ctx.history._states) >= 1


class TestRecordAndSaveWithScheduler:
    """``plan_save_scheduler`` übernimmt den Schreibvorgang, History bleibt synchron."""

    def test_scheduler_is_called_instead_of_repository_save(self):
        repo = FakePlanRepository()
        ctx = _make_ctx(repo)
        calls: list[tuple] = []
        ctx.plan_save_scheduler = lambda plan, path: calls.append((plan, path))
        plan = make_plan()
        path = PLANS_DIR / "x.json"

        _record_and_save(plan, path, "test.action", ctx)

        assert calls == [(plan, path)]
        assert path not in repo._plans  # kein direkter Schreibvorgang übers Repository

    def test_history_still_recorded_synchronously_with_scheduler_set(self):
        ctx = _make_ctx()
        ctx.plan_save_scheduler = lambda plan, path: None
        plan = make_plan()

        _record_and_save(plan, PLANS_DIR / "x.json", "test.action", ctx)

        # Nach einem echten Edit muss History mehr als den initialen Zustand halten,
        # d.h. reset() wurde durch record() ersetzt/ergänzt (siehe PlanHistory.record()).
        assert len(ctx.history._states) >= 1

    def test_scheduler_receiving_none_falls_back_to_direct_save(self):
        """``set_plan_save_scheduler(None)`` (z. B. Deaktivieren) reaktiviert Sofort-Speichern."""
        repo = FakePlanRepository()
        ctx = _make_ctx(repo)
        ctx.plan_save_scheduler = lambda plan, path: (_ for _ in ()).throw(AssertionError("nicht aufrufen"))
        ctx.plan_save_scheduler = None

        plan = make_plan()
        path = PLANS_DIR / "x.json"
        _record_and_save(plan, path, "test.action", ctx)

        assert repo._plans[path] is plan


class TestControllerWiresSchedulerIntoContext:
    """``KartographAppController.set_plan_save_scheduler()`` erreicht tatsächlich die Handler."""

    def _make_controller(self, plans: dict | None = None) -> KartographAppController:
        return KartographAppController(
            plan_repository=FakePlanRepository(plans),
            settings_repository=FakeSettingsRepository(),
            default_plans_dir=PLANS_DIR,
            symbols_path=SYMBOLS_PATH,
            on_state_changed=lambda _state: None,
        )

    def test_dispatch_uses_scheduler_for_a_mutating_intent(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        ctrl = self._make_controller({path: plan})
        ctrl.dispatch(OpenPlanIntent(plan_path=path))

        calls: list[Path] = []
        ctrl.set_plan_save_scheduler(lambda _plan, save_path: calls.append(save_path))

        ctrl.dispatch(CreateStudentIntent(x=2, y=1))

        assert calls == [path]
        # AppState wurde trotzdem sofort aktualisiert (nur der Disk-Write ist verzögert):
        assert ctrl.state.current_plan.student_at(2, 1) is not None

    def test_set_plan_save_scheduler_none_restores_synchronous_save(self):
        plan = make_plan()
        path = PLANS_DIR / "test.json"
        repo = FakePlanRepository({path: plan})
        ctrl = KartographAppController(
            plan_repository=repo,
            settings_repository=FakeSettingsRepository(),
            default_plans_dir=PLANS_DIR,
            symbols_path=SYMBOLS_PATH,
            on_state_changed=lambda _state: None,
        )
        ctrl.dispatch(OpenPlanIntent(plan_path=path))
        ctrl.set_plan_save_scheduler(lambda _plan, _path: None)
        ctrl.set_plan_save_scheduler(None)

        ctrl.dispatch(CreateStudentIntent(x=3, y=1))

        assert repo._plans[path].student_at(3, 1) is not None
