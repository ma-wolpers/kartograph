"""Tests für Layout und Zeichnen des Gruppenblatts (synthetische Gruppen, keine echten Daten)."""

from __future__ import annotations

import re

import pytest

from app.core.domain.note_groups import GroupBox, GroupSheet
from app.infrastructure.exporters.note_groups_layout import layout_group_boxes
from app.infrastructure.exporters.reportlab_loader import MISSING_REPORTLAB_MESSAGE

A4 = (595.0, 842.0)


def _layout(heights, columns=3, page=A4):
    return layout_group_boxes(heights, page, columns=columns, margin=36, gap=12, first_page_offset=34)


def test_boxes_flow_in_rows_and_the_row_height_is_the_tallest_box():
    (page,) = _layout([60, 100, 80, 40])
    assert [p.index for p in page] == [0, 1, 2, 3]
    assert {p.height for p in page[:3]} == {100}
    assert page[3].left == page[0].left and page[3].top == page[0].top - 100 - 12
    assert page[1].left > page[0].left


def test_a_row_that_does_not_fit_starts_a_new_page_and_no_box_is_split():
    pages = _layout([300] * 9)
    assert len(pages) == 2
    for page in pages:
        assert all(p.top - p.height >= 36 for p in page)
    assert pages[1][0].top == A4[1] - 36


def test_landscape_uses_four_columns():
    (page,) = _layout([50] * 4, columns=4, page=(842.0, 595.0))
    assert len({p.left for p in page}) == 4


def test_no_boxes_no_pages():
    assert _layout([]) == []


class _FakeCanvas:
    """Sammelt gezeichnete Texte und Seitenwechsel (wie in ``test_pdf_exporter_legend.py``)."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.pages = 1

    def setFont(self, _font, _size) -> None:  # noqa: N802 - reportlab API style
        pass

    def drawString(self, _x, _y, text) -> None:  # noqa: N802 - reportlab API style
        self.texts.append(text)

    def setLineWidth(self, _w) -> None:  # noqa: N802 - reportlab API style
        pass

    def roundRect(self, *_args, **_kwargs) -> None:  # noqa: N802 - reportlab API style
        pass

    def line(self, *_args) -> None:
        pass

    def showPage(self) -> None:  # noqa: N802 - reportlab API style
        self.pages += 1


def test_draw_writes_heading_titles_and_names_but_no_title_when_secret():
    pdfmetrics = pytest.importorskip("reportlab.pdfbase.pdfmetrics")
    from app.infrastructure.exporters.note_groups_pdf_exporter import draw_group_sheet

    sheet = GroupSheet("Klasse 7b – Gruppe", (GroupBox("A", ("Ben", "Cem")), GroupBox(None, ("Ida",))))
    c = _FakeCanvas()
    draw_group_sheet(c, pdfmetrics, sheet, A4, "portrait")
    assert c.texts == ["Klasse 7b – Gruppe", "A", "Ben", "Cem", "Ida"]


def test_export_writes_a_pdf_in_the_chosen_orientation(tmp_path):
    pytest.importorskip("reportlab")
    from app.infrastructure.exporters.note_groups_pdf_exporter import export_group_sheet

    sheet = GroupSheet("Klasse 7b", tuple(GroupBox(f"Gruppe {i}", ("Ada", "Ben", "Cem")) for i in range(1, 30)))
    for orientation, wider in (("portrait", False), ("landscape", True)):
        out = tmp_path / f"{orientation}.pdf"
        export_group_sheet(sheet, out, orientation)
        match = re.search(rb"/MediaBox \[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", out.read_bytes())
        assert match and (float(match.group(1)) > float(match.group(2))) is wider
    with pytest.raises(ValueError):
        export_group_sheet(sheet, tmp_path / "x.pdf", "diagonal")


def test_missing_reportlab_message_is_shared():
    assert "reportlab" in MISSING_REPORTLAB_MESSAGE
