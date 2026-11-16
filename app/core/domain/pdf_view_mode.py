"""Ansichten des PDF-Exports: einzige Quelle für Schlüssel, Labels und Kopien je Seite.

Der PDF-Export bietet die beiden Ansichten aus ``seat_orientation.ORIENTATION_MODES``
(eine Kopie auf A4 quer) und zusätzlich ``BOTH_ON_ONE_PAGE``: beide Ansichten
übereinander auf einer A4-Seite hochkant, z. B. eine für das Lehrerpult und eine
für Vertretungslehrkräfte am anderen Ende des Raums. Die Labels der Einzelansichten
stammen nur aus ``ORIENTATION_MODES``; die Reihenfolge der Kopien (oben zuerst)
ist die Reihenfolge dort. Der Sitzplan-Vorschau-Dialog bleibt bei
``ORIENTATION_MODES`` -- eine Doppelansicht gibt es nur auf Papier.
"""

from __future__ import annotations

from app.core.domain.seat_orientation import ORIENTATION_MODES, is_orientation_mode

BOTH_ON_ONE_PAGE = "both_on_one_page"

PDF_VIEW_MODES: tuple[tuple[str, str], ...] = ORIENTATION_MODES + (
    (BOTH_ON_ONE_PAGE, "Beide Ansichten auf einer A4-Seite (hochkant, Lehrertisch unten und oben)"),
)
"""Erlaubte PDF-Ansichten mit ihren Dialog-Labels, in Anzeigereihenfolge."""


def is_pdf_view_mode(mode: str) -> bool:
    """Prüft, ob *mode* eine bekannte PDF-Ansicht ist.

    Args:
        mode: Zu prüfender Schlüssel.
    """
    return any(key == mode for key, _label in PDF_VIEW_MODES)


def orientations_for(mode: str) -> tuple[str, ...]:
    """Ansicht-Schlüssel der Kopien auf der Seite, von oben nach unten.

    Args:
        mode: Bekannte PDF-Ansicht.

    Returns:
        Eine Einzelansicht als 1-Tupel; ``BOTH_ON_ONE_PAGE`` als alle Ansichten
        aus ``ORIENTATION_MODES`` in deren Reihenfolge.

    Raises:
        ValueError: *mode* ist keine bekannte PDF-Ansicht.
    """
    if mode == BOTH_ON_ONE_PAGE:
        return tuple(key for key, _label in ORIENTATION_MODES)
    if is_orientation_mode(mode):
        return (mode,)
    raise ValueError(f"Unbekannte PDF-Ansicht: {mode!r}")
