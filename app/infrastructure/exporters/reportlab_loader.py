"""Einzige Lade-Stelle für ReportLab (PDF-Exporte).

ReportLab ist optional und wird erst beim Export geladen; fehlt es, gibt es
überall dieselbe verständliche Meldung. Die Exporter bekommen die Module als
``ReportLab``-Bündel und importieren ReportLab nicht selbst.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MISSING_REPORTLAB_MESSAGE = "PDF-Export benoetigt reportlab (pip install reportlab)."


@dataclass(frozen=True)
class ReportLab:
    """Die von den Exportern genutzten ReportLab-Bausteine.

    Attributes:
        colors: ``reportlab.lib.colors``.
        pdfmetrics: ``reportlab.pdfbase.pdfmetrics``.
        ttfonts: ``reportlab.pdfbase.ttfonts``.
        canvas: ``reportlab.pdfgen.canvas``.
        a4: Seitengröße A4 hochkant ``(Breite, Höhe)`` in Punkten.
        landscape: ``reportlab.lib.pagesizes.landscape`` (dreht eine Seitengröße ins Querformat).
    """

    colors: Any
    pdfmetrics: Any
    ttfonts: Any
    canvas: Any
    a4: tuple[float, float]
    landscape: Any


def load_reportlab() -> ReportLab:
    """Lädt ReportLab.

    Returns:
        Das Bündel der benötigten Module.

    Raises:
        RuntimeError: Wenn reportlab nicht installiert ist.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfbase import pdfmetrics, ttfonts
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError(MISSING_REPORTLAB_MESSAGE) from exc
    return ReportLab(colors, pdfmetrics, ttfonts, canvas, A4, landscape)
