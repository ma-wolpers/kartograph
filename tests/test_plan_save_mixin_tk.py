"""Tests für die Tk-``after()``-Debounce-Mechanik in ``_mixin_plan_save.py``.

Nutzt einen echten (unsichtbaren) Tk-Root statt eines Mocks, da die zu
testende Logik direkt auf ``self.after()``/``self.after_cancel()`` beruht —
ein Mock würde nur die eigene Erwartung zurückspiegeln, nicht die echte
Tk-Interaktion prüfen. Kein bestehendes Vorbild für Tk-Tests in dieser Suite
(``test_main_window_root_host_str.py`` kommt bewusst ohne echten Root aus),
daher hier bewusst minimal statt eine ganze ``KartographMainWindow`` zu bauen.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from app.adapters.gui._mixin_plan_save import PlanSaveMixin
from tests.conftest import make_plan

# Kurz gehalten, um den echten-Timer-Test schnell zu halten -- die eigentliche
# MIN_SAVE_DELAY-Untergrenze (0.3s) wird an der Settings-Schicht erzwungen
# (KartographSettings.from_dict, _mixin_settings.py), nicht hier im Mixin
# selbst, das nur liest, was self.save_delay gerade enthält.
_TEST_SAVE_DELAY_SECONDS = 0.1


class _FakeRepository:
    def __init__(self, raise_on_call: bool = False) -> None:
        self.calls: list[tuple] = []
        self.raise_on_call = raise_on_call

    def save_plan(self, plan, path) -> None:
        if self.raise_on_call:
            raise RuntimeError("boom")
        self.calls.append((plan, path))


class _FakeController:
    def __init__(self, repo: _FakeRepository) -> None:
        self.plan_repository = repo


class _FakeStatusVar:
    def __init__(self) -> None:
        self.value: str | None = None

    def set(self, value: str) -> None:
        self.value = value


class _PlanSaveTestWindow(tk.Frame, PlanSaveMixin):
    """Minimales Test-Double: echtes Tk-Widget (für after()) + der zu testende Mixin."""

    def __init__(self, root: tk.Tk, repo: _FakeRepository) -> None:
        super().__init__(root)
        self._controller = _FakeController(repo)
        self.status_var = _FakeStatusVar()
        self.save_delay = _TEST_SAVE_DELAY_SECONDS
        self._pending_plan_save: tuple | None = None
        self._plan_save_after_id: str | None = None


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def window(tk_root):
    repo = _FakeRepository()
    win = _PlanSaveTestWindow(tk_root, repo)
    yield win, repo
    win.destroy()


def test_flush_without_pending_schedule_is_noop(window):
    win, repo = window
    win._flush_pending_plan_save()
    assert repo.calls == []


def test_schedule_then_flush_saves_the_plan(window):
    win, repo = window
    plan = make_plan()
    path = Path("/fake/plans/x.json")

    win._schedule_plan_save(plan, path)
    assert repo.calls == []  # noch nicht sofort gespeichert

    win._flush_pending_plan_save()
    assert repo.calls == [(plan, path)]
    assert win._pending_plan_save is None


def test_rescheduling_before_flush_only_saves_the_latest_plan(window):
    win, repo = window
    plan1 = make_plan(name="Erster Stand")
    plan2 = make_plan(name="Zweiter Stand")
    path = Path("/fake/plans/x.json")

    win._schedule_plan_save(plan1, path)
    win._schedule_plan_save(plan2, path)  # simuliert einen zweiten Edit vor Ablauf des Timers
    win._flush_pending_plan_save()

    assert repo.calls == [(plan2, path)]  # nicht 2 Aufrufe, nicht der veraltete plan1


def test_real_timer_fires_and_saves_after_delay(window):
    win, repo = window
    plan = make_plan()
    path = Path("/fake/plans/x.json")

    win._schedule_plan_save(plan, path)
    assert repo.calls == []

    deadline = int(_TEST_SAVE_DELAY_SECONDS * 1000) + 500
    waited = 0
    while not repo.calls and waited < deadline:
        win.update()
        win.after(20)
        win.update()
        waited += 20

    assert repo.calls == [(plan, path)]


def test_save_error_is_caught_and_surfaced_via_status(tk_root):
    repo = _FakeRepository(raise_on_call=True)
    win = _PlanSaveTestWindow(tk_root, repo)
    try:
        plan = make_plan()
        win._schedule_plan_save(plan, Path("/fake/plans/x.json"))

        win._flush_pending_plan_save()  # darf NICHT raisen

        assert win.status_var.value is not None
        assert "fehlgeschlagen" in win.status_var.value.lower()
    finally:
        win.destroy()
