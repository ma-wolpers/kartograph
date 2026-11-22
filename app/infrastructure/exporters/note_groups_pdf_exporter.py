"""Gruppenblatt als PDF zeichnen ("Gruppen exportieren" in der Datenansicht).

Bekommt das fertige ``GroupSheet`` aus ``core/domain/note_groups`` (wer in
welchem Kästchen steht, Überschriften, Reihenfolge) und zeichnet nur:
Überschrift, gerahmte Kästchen mit fettem Titel (falls vorhanden) und darunter
einen Namen je Zeile. Wo die Kästchen stehen, sagt ``note_groups_layout``; zu
lange Namen und Titel werden über ``pdf_font_utils.fit_single_line_font``
verkleinert. Schriften wie im Sitzplan-PDF (Helvetica).

GRENZE: Helvetica zeichnet keine Emoji oder Sonderzeichen in Notiztexten,
wie im Sitzplan-PDF auch.
"""

from __future__ import annotations

from pathlib import Path

from app.core.domain.note_groups import GroupBox, GroupSheet
from app.infrastructure.exporters.note_groups_layout import COLUMNS_BY_ORIENTATION, layout_group_boxes
from app.infrastructure.exporters.pdf_font_utils import fit_single_line_font
from app.infrastructure.exporters.reportlab_loader import load_reportlab

_FONT = "Helvetica"
_BOLD = "Helvetica-Bold"
_MARGIN = 36.0
_GAP = 12.0
_PADDING = 8.0
_HEADING_SIZE = 16
_HEADING_SPACE = 34.0
_TITLE_SIZE = 12
_TITLE_HEIGHT = 20.0
_NAME_SIZE = 11
_LINE_HEIGHT = 15.0
_MIN_SIZE = 6


def _box_height(box: GroupBox) -> float:
    """Benötigte Höhe eines Kästchens: Titelzeile (falls vorhanden) plus eine Zeile je Name."""
    title = _TITLE_HEIGHT if box.title else 0.0
    return 2 * _PADDING + title + max(1, len(box.names)) * _LINE_HEIGHT


def _draw_fitted(c, pdfmetrics, font: str, text: str, x: float, y: float, max_width: float, max_size: int) -> None:
    """Zeichnet *text* einzeilig, notfalls verkleinert, damit er in *max_width* passt."""
    size = fit_single_line_font(pdfmetrics, font, text, max_width, max_size * 1.4, _MIN_SIZE, max_size)
    c.setFont(font, size)
    c.drawString(x, y, text)


def draw_group_sheet(c, pdfmetrics, sheet: GroupSheet, page_size: tuple[float, float], orientation: str) -> None:
    """Zeichnet *sheet* auf den Canvas *c* (eine oder mehrere Seiten).

    Args:
        c: ReportLab-Canvas (Tests: Fake mit denselben Methoden).
        pdfmetrics: ``reportlab.pdfbase.pdfmetrics`` (Textbreiten).
        sheet: Fertiges Gruppenblatt.
        page_size: ``(Breite, Höhe)`` der Seite.
        orientation: ``"portrait"`` oder ``"landscape"`` (bestimmt die Spaltenzahl).
    """
    page_w, page_h = page_size
    _draw_fitted(c, pdfmetrics, _BOLD, sheet.heading, _MARGIN, page_h - _MARGIN - _HEADING_SIZE,
                 page_w - 2 * _MARGIN, _HEADING_SIZE)
    pages = layout_group_boxes(
        [_box_height(box) for box in sheet.boxes], page_size, columns=COLUMNS_BY_ORIENTATION[orientation],
        margin=_MARGIN, gap=_GAP, first_page_offset=_HEADING_SPACE,
    )
    for page_number, placements in enumerate(pages):
        if page_number:
            c.showPage()
        for place in placements:
            box = sheet.boxes[place.index]
            c.setLineWidth(0.8)
            c.roundRect(place.left, place.top - place.height, place.width, place.height, 4, stroke=1, fill=0)
            text_width = place.width - 2 * _PADDING
            y = place.top - _PADDING - _NAME_SIZE
            if box.title:
                _draw_fitted(c, pdfmetrics, _BOLD, box.title, place.left + _PADDING, y, text_width, _TITLE_SIZE)
                separator = place.top - _PADDING - _TITLE_HEIGHT + 4
                c.line(place.left + _PADDING, separator, place.left + place.width - _PADDING, separator)
                y -= _TITLE_HEIGHT
            for name in box.names:
                _draw_fitted(c, pdfmetrics, _FONT, name, place.left + _PADDING, y, text_width, _NAME_SIZE)
                y -= _LINE_HEIGHT


def export_group_sheet(sheet: GroupSheet, output_path: Path, orientation: str) -> None:
    """Schreibt *sheet* als A4-PDF nach *output_path*.

    Args:
        sheet: Fertiges Gruppenblatt (``note_groups.build_group_sheet``).
        output_path: Zieldatei.
        orientation: ``"portrait"`` (Hochformat) oder ``"landscape"`` (Querformat),
            Schlüssel aus ``page_orientation.PAGE_ORIENTATIONS``.

    Raises:
        RuntimeError: Wenn reportlab nicht installiert ist.
        ValueError: Bei unbekannter Ausrichtung.
    """
    if orientation not in COLUMNS_BY_ORIENTATION:
        raise ValueError(f"Unbekannte Blattausrichtung: {orientation}")
    rl = load_reportlab()
    page_size = rl.landscape(rl.a4) if orientation == "landscape" else rl.a4
    c = rl.canvas.Canvas(str(output_path), pagesize=page_size)
    c.setTitle(sheet.heading)
    draw_group_sheet(c, rl.pdfmetrics, sheet, page_size, orientation)
    c.showPage()
    c.save()
