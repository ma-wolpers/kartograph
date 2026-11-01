"""Tests für PlanHistory: Jeder Aufruf ist ein Schritt, außer ausdrücklich gleiche laufende Eingaben."""

from pathlib import Path

from app.core.domain.plan_history import DEFAULT_MAX_UNDO_STEPS, PlanHistory
from tests.conftest import make_plan


def _history_with(*names_and_keys):
    history = PlanHistory()
    history.reset(make_plan(name="Start"), Path("p.json"))
    for name, merge_key in names_and_keys:
        history.record(make_plan(name=name), merge_key=merge_key)
    return history


def test_every_record_is_its_own_step_by_default():
    history = _history_with(("A", None), ("B", None))
    assert history.undo().meta.name == "A"
    assert history.undo().meta.name == "Start"


def test_same_merge_key_overwrites_the_step():
    history = _history_with(("A", "typing"), ("B", "typing"))
    assert history.undo().meta.name == "Start"


def test_different_merge_key_starts_a_new_step():
    history = _history_with(("A", "first"), ("B", "second"))
    assert history.undo().meta.name == "A"


def test_step_in_between_ends_the_merging():
    history = _history_with(("A", "typing"), ("B", None), ("C", "typing"))
    assert history.undo().meta.name == "B"
    assert history.undo().meta.name == "A"


def test_typing_after_undo_does_not_overwrite_the_older_step():
    history = _history_with(("A", "typing"), ("B", None))
    history.undo()
    history.record(make_plan(name="C"), merge_key="typing")
    assert history.undo().meta.name == "A"


def test_typing_after_redo_does_not_overwrite_the_restored_step():
    history = _history_with(("A", "typing"))
    history.undo()
    history.redo()
    history.record(make_plan(name="B"), merge_key="typing")
    assert history.undo().meta.name == "A"


def test_limit_keeps_the_newest_steps():
    history = _history_with(*((f"P{i}", None) for i in range(DEFAULT_MAX_UNDO_STEPS + 5)))
    last = None
    while history.can_undo:
        last = history.undo().meta.name
    assert last == "P4"  # P0 bis P3 sind herausgefallen, P4 ist der älteste erreichbare Stand


def test_can_undo_and_can_redo_follow_the_stacks():
    history = _history_with()
    assert (history.can_undo, history.can_redo) == (False, False)
    history.record(make_plan(name="A"))
    assert (history.can_undo, history.can_redo) == (True, False)
    history.undo()
    assert (history.can_undo, history.can_redo) == (False, True)
