"""Tests für die Notenanzeige-Modi des PDF-Exports (``grade_display_mode.py``)."""

import pytest

from app.core.domain.grade_display_mode import (
    DEFAULT_GRADE_DISPLAY_MODE,
    GRADE_DISPLAY_MODES,
    GRADE_MODE_FINAL_ONLY,
    GRADE_MODE_INCLUDE_PROVISIONAL,
    GRADE_MODE_NONE,
    is_grade_display_mode,
    provisional_policy,
)


def test_modes_are_unique_and_default_is_listed():
    keys = [key for key, _label in GRADE_DISPLAY_MODES]
    assert len(set(keys)) == len(keys)
    assert DEFAULT_GRADE_DISPLAY_MODE in keys


@pytest.mark.parametrize(("mode", "known"), [(GRADE_MODE_NONE, True), ("quatsch", False), (None, False)])
def test_is_grade_display_mode(mode, known):
    assert is_grade_display_mode(mode) is known


@pytest.mark.parametrize(
    ("mode", "policy"),
    [(GRADE_MODE_NONE, None), (GRADE_MODE_FINAL_ONLY, False), (GRADE_MODE_INCLUDE_PROVISIONAL, True)],
)
def test_provisional_policy(mode, policy):
    assert provisional_policy(mode) is policy
