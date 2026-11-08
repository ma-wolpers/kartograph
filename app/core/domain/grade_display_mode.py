"""Notenanzeige im PDF-Export (SSOT): Schlüssel, Dialog-Labels und ihre Bedeutung.

Einzige Quelle für
- die Modus-Schlüssel ``none``/``final_only``/``include_provisional`` samt
  Dialog-Labels in Anzeigereihenfolge (der PDF-Dialog baut seine Auswahl daraus),
- die Prüfung eines Modus (``is_grade_display_mode``, genutzt vom Exporter),
- die Bedeutung eines Modus für die Notenberechnung (``provisional_policy``,
  genutzt vom Tisch-Renderer).

Gleiches Muster wie ``seat_orientation.ORIENTATION_MODES``. Vorher standen die
Werte als ``Literal`` und als Prüf-Menge im Exporter, als if/elif-Kette im
Renderer und als Radiobutton-Werte im Dialog.
"""

from __future__ import annotations

from typing import Literal

GRADE_MODE_NONE = "none"
GRADE_MODE_FINAL_ONLY = "final_only"
GRADE_MODE_INCLUDE_PROVISIONAL = "include_provisional"

GradeDisplayMode = Literal["none", "final_only", "include_provisional"]

GRADE_DISPLAY_MODES: tuple[tuple[GradeDisplayMode, str], ...] = (
    (GRADE_MODE_NONE, "Keine Noten (Standard)"),
    (GRADE_MODE_FINAL_ONLY, "Nur fertige Gesamtnote"),
    (GRADE_MODE_INCLUDE_PROVISIONAL, "Gesamtnote inkl. Klammernoten"),
)
"""Erlaubte Modi mit ihren Dialog-Labels, in Anzeigereihenfolge."""

DEFAULT_GRADE_DISPLAY_MODE: GradeDisplayMode = GRADE_MODE_NONE


def is_grade_display_mode(mode: object) -> bool:
    """Prüft, ob *mode* ein bekannter Notenanzeige-Modus ist.

    Args:
        mode: Zu prüfender Wert.
    """
    return any(key == mode for key, _label in GRADE_DISPLAY_MODES)


def provisional_policy(mode: GradeDisplayMode) -> bool | None:
    """Was *mode* für die Gesamtnoten-Berechnung bedeutet.

    Args:
        mode: Notenanzeige-Modus.

    Returns:
        ``None`` = keine Note zeigen, sonst der Wert für
        ``compute_grade_display(..., allow_provisional=…)``.
    """
    if mode == GRADE_MODE_NONE:
        return None
    return mode == GRADE_MODE_INCLUDE_PROVISIONAL
