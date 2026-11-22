from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.domain.models_v4 import SessionEntry
from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class AddSessionIntent(Intent):
    """Stellt sicher, dass für *date* (YYYY-MM-DD) eine Dokumentations-Session existiert."""

    date: str  # YYYY-MM-DD


@dataclass(frozen=True)
class RenameSessionIntent(Intent):
    """Verlegt den Dokumentationstermin *old_date* auf *new_date* (YYYY-MM-DD; Einträge wandern mit)."""

    old_date: str
    new_date: str


@dataclass(frozen=True)
class DeleteSessionIntent(Intent):
    """Löscht den Dokumentationstermin *date* inkl. aller darin erfassten Symbole, Noten und Notizen."""

    date: str


@dataclass(frozen=True)
class NavigateSessionIntent(Intent):
    """Wählt den vorigen/nächsten Dokumentationstermin relativ zum aktuell ausgewählten Datum (*direction*)."""

    direction: Literal["prev", "next"]


@dataclass(frozen=True)
class GoToTodayIntent(Intent):
    """Wählt das heutige Datum als aktuellen Dokumentationstermin."""


@dataclass(frozen=True)
class ClearDocEntryIntent(Intent):
    """Löscht den Dokumentationseintrag (Symbole, Mitarbeit, Notiz) eines Schülers an *date*."""

    student_id: StudentId
    date: str


@dataclass(frozen=True)
class SetDocEntryIntent(Intent):
    """Ersetzt den Dokumentationseintrag einer Person an *date* vollständig (z. B. Einfügen).

    Attributes:
        student_id: Betroffene Person.
        date: Datum (YYYY-MM-DD).
        entry: Neuer Eintrag; der Handler speichert eine Kopie, leer = löschen.
    """

    student_id: StudentId
    date: str
    entry: SessionEntry
