"""Tests für die ←/→-Navigation der Dokutabelle über die logische Spaltenachse (ohne Tk).

Prüft Zielspalte und Ziel-Pane von ``resolve_horizontal_target``, inkl. der
einzigen zustandsabhängigen Sonderregel (erste RIGHT-Spalte + ← → aktueller
Datumsanker, nicht das letzte Datum).
"""

from __future__ import annotations

import pytest

from app.adapters.gui._mixin_docs_nav import DocsNavMixin
from app.adapters.gui.docs_table_model import DocColumnAxis, DocsPane
from app.adapters.gui.docs_table_rules import resolve_horizontal_target

DATES = tuple(f"date_{i}" for i in range(10))
FIXED = ("summary", "grade_a", "grade_b", "overall")


@pytest.fixture
def axis() -> DocColumnAxis:
    return DocColumnAxis(DATES, FIXED)


def _step(axis, key, delta, anchor=0):
    target = resolve_horizontal_target(axis, key, anchor, delta)
    return target, (axis.pane_of(target) if target is not None else None)


class TestCrossPaneTransitions:
    def test_names_to_main_and_back(self, axis):
        assert _step(axis, "nachname", 1) == ("vorname", DocsPane.NAMES)
        assert _step(axis, "vorname", 1) == ("date_0", DocsPane.MAIN)
        assert _step(axis, "date_0", -1) == ("vorname", DocsPane.NAMES)
        assert _step(axis, "vorname", -1) == ("nachname", DocsPane.NAMES)

    def test_main_to_right(self, axis):
        assert _step(axis, "date_9", 1, anchor=9) == ("grade_a", DocsPane.RIGHT)

    def test_edges(self, axis):
        assert _step(axis, "nachname", -1) == (None, None)
        assert _step(axis, "overall", 1) == (None, None)

    def test_within_right_pane(self, axis):
        assert _step(axis, "grade_a", 1) == ("grade_b", DocsPane.RIGHT)
        assert _step(axis, "grade_b", -1) == ("grade_a", DocsPane.RIGHT)


class TestDateAnchorReturn:
    """← von der ersten RIGHT-Spalte springt zum aktuellen Datumsanker, nicht zu date_last."""

    @pytest.mark.parametrize("anchor", [7, 2])
    def test_left_from_first_fixed_column_returns_to_anchor(self, axis, anchor):
        assert _step(axis, "grade_a", -1, anchor=anchor) == (f"date_{anchor}", DocsPane.MAIN)

    def test_anchor_is_clamped(self, axis):
        assert _step(axis, "grade_a", -1, anchor=42) == ("date_9", DocsPane.MAIN)

    def test_without_dates_falls_back_to_structure(self):
        axis = DocColumnAxis((), FIXED)
        assert _step(axis, "grade_a", -1) == ("vorname", DocsPane.NAMES)


class _ClampHost(DocsNavMixin):
    """Tk-freies Double: nur die Zustandsfelder, die Clamp/aktive Spalte brauchen."""

    def __init__(self, axis: DocColumnAxis, nondate: str | None, anchor: int) -> None:
        self._doc_axis = axis
        self._doc_selected_nondate_column_id = nondate
        self._doc_selected_date_index = anchor


class TestVanishedActiveColumn:
    """Nach einem Rebuild ist die aktive Spalte gültig oder fällt deterministisch zurück."""

    def test_vanished_grade_column_falls_back_to_clamped_anchor(self):
        host = _ClampHost(DocColumnAxis(DATES[:6], ("summary", "grade_0", "grade_1", "grade_2", "overall")), "grade_4", 3)
        host._clamp_doc_column_selection_after_rebuild(6)
        assert host._doc_selected_nondate_column_id is None
        assert host._doc_active_column_key() == "date_3"

    def test_vanished_date_is_clamped(self):
        host = _ClampHost(DocColumnAxis(DATES[:6], FIXED), None, 8)
        host._clamp_doc_column_selection_after_rebuild(6)
        assert host._doc_active_column_key() == "date_5"

    @pytest.mark.parametrize("key", ["vorname", "nachname", "grade_b"])
    def test_existing_nondate_column_stays(self, key):
        host = _ClampHost(DocColumnAxis(DATES, FIXED), key, 2)
        host._clamp_doc_column_selection_after_rebuild(len(DATES))
        assert host._doc_active_column_key() == key
        assert host._doc_selected_date_index == 2
