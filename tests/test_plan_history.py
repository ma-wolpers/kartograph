"""Tests für PlanHistory: Zusammenfassen gleichartiger Schritte und der coalesce-Schalter."""

from pathlib import Path

from app.core.domain.plan_history import PlanHistory
from tests.conftest import make_plan


def _history_with(*names_and_kinds, coalesce=True):
    history = PlanHistory()
    history.reset(make_plan(name="Start"), Path("p.json"))
    for name, kind in names_and_kinds:
        history.record(make_plan(name=name), kind, coalesce=coalesce)
    return history


def test_consecutive_same_kind_is_coalesced_by_default():
    history = _history_with(("A", "type"), ("B", "type"))
    assert history.undo().meta.name == "Start"


def test_coalesce_false_keeps_every_step():
    history = _history_with(("A", "rate"), ("B", "rate"), coalesce=False)
    assert history.undo().meta.name == "A"
    assert history.undo().meta.name == "Start"
