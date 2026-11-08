"""Texte der Doku-Tabelle (Tk-frei): Zusammenfassung mit Abgabenbilanz und Spaltenköpfe mit Faktor."""

from __future__ import annotations

import pytest

from app.adapters.gui._mixin_docs_view import DocsViewMixin
from app.adapters.gui.docs_table_model import DocColumnAxis, grade_column_key
from app.core.domain.models_v4 import GradeColumn
from app.core.domain.submission_status import SubmissionStatus
from tests.conftest import make_plan

NAMES = {
    SubmissionStatus.COMPLETE: "Abgabe vollständig",
    SubmissionStatus.PARTIAL: "Abgabe lückenhaft",
    SubmissionStatus.MISSING: "Nicht abgegeben",
}
GLYPHS = {"Abgabe vollständig": "✓", "Abgabe lückenhaft": "◐", "Nicht abgegeben": "X", "Beteiligung": "B"}


class _Host(DocsViewMixin):
    """Nur das, was die Zellformatierung braucht: Glyphen aus einem festen Katalog."""

    def _symbol_glyph(self, symbol_name: str) -> str:
        return GLYPHS[symbol_name]


def test_submission_symbols_are_counted_not_shown_as_latest():
    latest = {"Beteiligung": 2, "Nicht abgegeben": 1}
    counts = {SubmissionStatus.MISSING: 3, SubmissionStatus.COMPLETE: 5, SubmissionStatus.PARTIAL: 1}
    assert _Host()._documentation_summary_cell_text(latest, counts, NAMES) == "BB ✓5 ◐1 X3"


def test_zero_statuses_are_omitted_and_one_keeps_its_number():
    assert _Host()._documentation_summary_cell_text({}, {SubmissionStatus.MISSING: 1}, NAMES) == "X1"


def test_without_any_submission_only_latest_symbols():
    assert _Host()._documentation_summary_cell_text({"Beteiligung": 1}, {}, NAMES) == "B"


def test_without_resolvable_names_cell_stays_as_before():
    latest = {"Beteiligung": 1, "Nicht abgegeben": 1}
    assert _Host()._documentation_summary_cell_text(latest, {}, None) == "B X"


class _LabelHost(DocsViewMixin):
    """Plan mit drei sonstigen Spalten (Faktor 2, 1 und 0.5) und den passenden festen Spalten."""

    def __init__(self) -> None:
        self.current_plan = make_plan()
        self.current_plan.documentation.grade_columns = [
            GradeColumn("ref", "sonstig", "Referat", weight=2.0),
            GradeColumn("heft", "sonstig", "Heft"),
            GradeColumn("test", "sonstig", "Test", weight=0.5),
        ]
        self._doc_dates = []
        keys = ["summary", *(grade_column_key(c) for c in ("ref", "heft", "test")), "sonstige_total", "overall"]
        self._doc_axis = DocColumnAxis((), keys)


@pytest.mark.parametrize(
    ("key", "label"),
    [
        (grade_column_key("ref"), "Referat ×2"),
        (grade_column_key("heft"), "Heft"),
        (grade_column_key("test"), "Test ×0.5"),
        ("sonstige_total", "Sonstig gesamt"),
        ("written_total", "Schriftlich gesamt"),
        ("summary", "Zusammenfassung"),
        ("overall", "Gesamtnote"),
    ],
)
def test_column_labels(key, label):
    assert _LabelHost()._doc_column_label(key) == label
