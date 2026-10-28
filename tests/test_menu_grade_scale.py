"""Headless-Tests für das Notenskala-Untermenü im Datei-Menü (ohne Tk-Fenster)."""

from pathlib import Path

import pytest

import app.adapters.gui._mixin_menu as menu_module
from app.adapters.gui._mixin_menu import MenuMixin
from app.core.domain.grade_scale import SCALE_POINTS_0_15, SCALE_SCHOOL_1_6
from app.core.domain.models_v4 import Session, SessionEntry
from app.core.intents.grade_intents import SetGradeScaleIntent
from tests.conftest import make_plan, make_student


class _Var:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class _Controller:
    def __init__(self):
        self.intents = []

    def dispatch(self, intent):
        self.intents.append(intent)


class _Window(MenuMixin):
    def __init__(self, plan):
        self.current_plan = plan
        self.current_plan_path = Path("test.json") if plan else None
        self._controller = _Controller()
        self.status_var = _Var()


def _plan_with_grade():
    student = make_student()
    plan = make_plan(students=[student])
    plan.documentation.sessions.append(
        Session(date="2025-09-01", entries={student.student_id: SessionEntry(grades={"c1": 3.2})})
    )
    return plan


@pytest.fixture
def answers(monkeypatch):
    """Ersetzt die Rückfrage durch eine Liste vorbereiteter Antworten und protokolliert Aufrufe."""
    calls: list[str] = []
    replies: list[bool] = []

    def fake_askyesno(_title, message, **_kwargs):
        calls.append(message)
        return replies.pop(0)

    monkeypatch.setattr(menu_module.messagebox, "askyesno", fake_askyesno)
    return calls, replies


def test_submenu_marks_current_scale():
    window = _Window(make_plan())
    item = window._grade_scale_menu_item()
    assert item.type == "submenu"
    checked = {child.label: child.checked for child in item.items}
    assert checked == {"Schulnoten (1–6)": True, "Punkte (0–15)": False}


def test_without_plan_only_disabled_hint():
    assert _Window(None)._grade_scale_menu_item().type == "disabled"


def test_switch_without_grades_needs_no_confirmation(answers):
    calls, _ = answers
    window = _Window(make_plan())
    window._set_grade_scale(SCALE_POINTS_0_15)
    assert calls == []
    assert window._controller.intents == [SetGradeScaleIntent(scale_id=SCALE_POINTS_0_15)]


def test_switch_with_grades_warns_and_respects_no(answers):
    calls, replies = answers
    replies.append(False)
    window = _Window(_plan_with_grade())
    window._set_grade_scale(SCALE_POINTS_0_15)
    assert len(calls) == 1 and "1 Noten" in calls[0]
    assert window._controller.intents == []


def test_switch_with_grades_dispatches_after_yes(answers):
    _, replies = answers
    replies.append(True)
    window = _Window(_plan_with_grade())
    window._set_grade_scale(SCALE_POINTS_0_15)
    assert window._controller.intents == [SetGradeScaleIntent(scale_id=SCALE_POINTS_0_15)]


def test_same_scale_does_nothing(answers):
    calls, _ = answers
    window = _Window(_plan_with_grade())
    window._set_grade_scale(SCALE_SCHOOL_1_6)
    assert calls == [] and window._controller.intents == []
