"""Seitenaufteilung des PDF-Exports: eine Ansicht quer oder beide Ansichten hochkant.

Schreibt echte PDFs in ``tmp_path`` (synthetischer Plan) und zeichnet die Tisch-
Aufrufe des Renderers mit, um Kopienzahl, Lage auf der Seite und Seitengröße zu
prüfen. Benötigt reportlab.
"""

from __future__ import annotations

import re

import pytest

from app.core.domain.pdf_view_mode import BOTH_ON_ONE_PAGE
from app.core.domain.seat_orientation import TEACHER_BOTTOM
from app.infrastructure.exporters.pdf_exporter import PdfSeatingPlanExporter
from tests.conftest import make_plan, make_student

pytest.importorskip("reportlab")


@pytest.fixture
def plan():
    return make_plan(students=[make_student(x=1, y=0), make_student(x=2, y=2, first_name="Ben")])


@pytest.fixture
def exporter_and_calls(monkeypatch):
    exporter = PdfSeatingPlanExporter(symbol_definitions=[])
    calls: list[tuple[tuple[float, float], bool]] = []
    original = exporter._desk_renderer.render_desk

    def spy(c, colors, pdfmetrics, seat, polygon, center, *args):
        calls.append((center, seat.is_teacher))
        return original(c, colors, pdfmetrics, seat, polygon, center, *args)

    monkeypatch.setattr(exporter._desk_renderer, "render_desk", spy)
    return exporter, calls


def _media_box(path) -> tuple[float, float]:
    match = re.search(rb"/MediaBox \[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", path.read_bytes())
    assert match
    return float(match.group(1)), float(match.group(2))


def test_single_view_is_one_landscape_copy(tmp_path, plan, exporter_and_calls):
    exporter, calls = exporter_and_calls
    out = tmp_path / "single.pdf"
    exporter.export_plan(plan, out, TEACHER_BOTTOM)

    width, height = _media_box(out)
    assert width > height
    assert len(calls) == 3  # Lehrertisch + zwei Schülertische


def test_both_views_are_two_copies_on_a_portrait_page(tmp_path, plan, exporter_and_calls):
    exporter, calls = exporter_and_calls
    out = tmp_path / "both.pdf"
    exporter.export_plan(plan, out, BOTH_ON_ONE_PAGE)

    width, height = _media_box(out)
    assert height > width
    assert len(calls) == 6
    upper, lower = calls[:3], calls[3:]
    assert all(center[1] > height / 2 for center, _teacher in upper)
    assert all(center[1] < height / 2 for center, _teacher in lower)


def test_both_views_put_the_teacher_desk_at_opposite_ends(tmp_path, plan, exporter_and_calls):
    """Obere Kopie ungedreht wie im Editor (dort steht der Lehrertisch in Zeile 0, also oben),
    untere Kopie um 180° gedreht -- der Lehrertisch landet am anderen Ende."""
    exporter, calls = exporter_and_calls
    exporter.export_plan(plan, tmp_path / "both.pdf", BOTH_ON_ONE_PAGE)

    def teacher_rank(copy):
        teacher_y = next(center[1] for center, teacher in copy if teacher)
        ys = [center[1] for center, _teacher in copy]
        return "top" if teacher_y >= max(ys) else "bottom" if teacher_y <= min(ys) else "middle"

    assert teacher_rank(calls[:3]) == "top"
    assert teacher_rank(calls[3:]) == "bottom"


def test_unknown_view_is_rejected(tmp_path, plan, exporter_and_calls):
    exporter, _calls = exporter_and_calls
    with pytest.raises(ValueError):
        exporter.export_plan(plan, tmp_path / "x.pdf", "sideways")
