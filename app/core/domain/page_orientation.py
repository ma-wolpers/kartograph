"""Blattausrichtung von Exporten (Papierlage, nicht die Sitzplan-Ansicht aus ``pdf_view_mode``).

``(Schlüssel, Beschriftung)``-Paare im Stil von ``PDF_VIEW_MODES``, direkt für
eine bw-gui ``RadioGroup``; die Exporter bilden den Schlüssel auf ihr Papierformat ab.
"""

from __future__ import annotations

from typing import Literal

PageOrientation = Literal["portrait", "landscape"]

PAGE_ORIENTATIONS: tuple[tuple[PageOrientation, str], ...] = (
    ("portrait", "Hochformat"),
    ("landscape", "Querformat"),
)
DEFAULT_PAGE_ORIENTATION: PageOrientation = "portrait"
