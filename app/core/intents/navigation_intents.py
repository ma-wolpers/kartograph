from __future__ import annotations

from dataclasses import dataclass

from app.core.intents.base import Intent


@dataclass(frozen=True)
class SelectCellIntent(Intent):
    """Setzt die Auswahl auf eine einzelne Zelle (*x*, *y*); ersetzt eine bestehende Bereichsauswahl."""

    x: int
    y: int


@dataclass(frozen=True)
class MoveSelectionIntent(Intent):
    """Verschiebt die Auswahl relativ um (*dx*, *dy*).

    Bei *expand* = False wird die Auswahl auf eine Einzelzelle an der neuen
    Position kollabiert (Pfeiltasten). Bei *expand* = True bleibt der Anker
    erhalten und nur der Fokus wandert, wodurch sich eine Bereichsauswahl
    aufspannt (Shift+Pfeiltasten, Canvas-Drag).
    """

    dx: int
    dy: int
    expand: bool = False


@dataclass(frozen=True)
class ClearSelectionIntent(Intent):
    """Verlässt die Rasteransicht zurück in die Planliste (Escape aus dem Editor)."""
