"""Tests für die PDF-Ansichten (``app/core/domain/pdf_view_mode.py``)."""

from __future__ import annotations

import pytest

from app.core.domain.pdf_view_mode import BOTH_ON_ONE_PAGE, PDF_VIEW_MODES, is_pdf_view_mode, orientations_for
from app.core.domain.seat_orientation import ORIENTATION_MODES, TEACHER_BOTTOM, TEACHER_TOP, orientation_label


def test_pdf_view_modes_extend_the_orientation_modes() -> None:
    """Einzelansichten mit identischen Labels zuerst, danach nur die Doppelansicht."""
    assert PDF_VIEW_MODES[: len(ORIENTATION_MODES)] == ORIENTATION_MODES
    assert [key for key, _label in PDF_VIEW_MODES[len(ORIENTATION_MODES):]] == [BOTH_ON_ONE_PAGE]


def test_known_and_unknown_modes() -> None:
    assert all(is_pdf_view_mode(key) for key, _label in PDF_VIEW_MODES)
    assert not is_pdf_view_mode("sideways")


def test_orientations_per_page() -> None:
    assert orientations_for(TEACHER_TOP) == (TEACHER_TOP,)
    assert orientations_for(BOTH_ON_ONE_PAGE) == (TEACHER_BOTTOM, TEACHER_TOP)
    with pytest.raises(ValueError):
        orientations_for("sideways")


def test_orientation_label_comes_from_the_orientation_modes() -> None:
    assert orientation_label(TEACHER_BOTTOM) == dict(ORIENTATION_MODES)[TEACHER_BOTTOM]
    with pytest.raises(ValueError):
        orientation_label("sideways")
