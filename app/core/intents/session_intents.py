from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class AddSessionIntent(Intent):
    """Stellt sicher, dass für *date* (YYYY-MM-DD) eine Dokumentations-Session existiert."""

    date: str  # YYYY-MM-DD


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
    """Löscht den Dokumentationseintrag (Symbole, Noten, Notiz) eines Schülers an *date*."""

    student_id: StudentId
    date: str
