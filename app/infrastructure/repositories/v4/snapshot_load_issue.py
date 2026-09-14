"""Strukturierter Fehlertransport für die Snapshot-Deserialisierung.

Bewusst getrennt vom Domainmodell: ``SeatingSnapshot``
(``app/core/domain/models_v4.py``) enthält ausschließlich fachliche Daten,
keine Lade-/UI-Fehlerinformation. ``SnapshotLoadIssue`` ist reine
Infrastruktur-/Feedback-Information, wird nicht persistiert und entsteht nur
für ``seats``-Einträge innerhalb eines ansonsten gültigen Snapshots -- alle
anderen fehlerhaften Rohdaten werden (wie im übrigen Deserializer üblich)
still repariert/verworfen, s. ``deserializer_v4.py::_deserialize_snapshots``
für die vollständige Abgrenzung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SnapshotLoadIssueReason = Literal["invalid_student_id", "invalid_seat"]


@dataclass(frozen=True)
class SnapshotLoadIssue:
    """Eine bei der Snapshot-Deserialisierung übersprungene/reparierte Rohdaten-Stelle.

    Entsteht ausschließlich für einzelne ``seats``-Einträge eines ansonsten
    gültigen Snapshots -- nicht für snapshot-weite strukturelle Probleme
    (fehlende/doppelte ``snapshot_id``: ganzer Eintrag still verworfen, wie
    bei Sessions/Notenspalten) oder für Felder mit sinnvollem Default (Name,
    Datum, Lehrertisch: still repariert, wie überall sonst im Deserializer).
    """

    snapshot_id: str
    reason: SnapshotLoadIssueReason
    detail: str
