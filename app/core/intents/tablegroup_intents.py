from __future__ import annotations

from dataclasses import dataclass

from app.core.intents.base import Intent


@dataclass(frozen=True)
class ApplyTablegroupSettingsIntent(Intent):
    """Übernimmt Nummer und Geometrie für die Tischgruppe an (*x*, *y*), als ein Undo-Schritt.

    Args:
        x: Spalte eines Sitzplatzes der Gruppe.
        y: Zeile eines Sitzplatzes der Gruppe.
        number: Gewünschte Gruppennummer.
        shift_x: Neuer X-Versatz.
        shift_y: Neuer Y-Versatz.
        rotation: Neue Rotation.
        last_changed_field: Zuletzt bearbeitetes Formularfeld; bei einer Überlappung wird es zuerst zurückgesetzt.
    """

    x: int
    y: int
    number: int
    shift_x: float
    shift_y: float
    rotation: float
    last_changed_field: str
