from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class SetNotesIntent(Intent):
    """Ersetzt die Liste der Notizen eines Schülers vollständig."""

    student_id: StudentId
    notes: list[str]


@dataclass(frozen=True)
class AddNoteColumnIntent(Intent):
    """Legt eine eigene Notizspalte an (*kind* aus ``NOTE_VALUE_KINDS``)."""

    title: str
    kind: str


@dataclass(frozen=True)
class DeleteNoteColumnIntent(Intent):
    """Löscht eine eigene Notizspalte samt Werten."""

    column_id: str


@dataclass(frozen=True)
class SetNoteValueIntent(Intent):
    """Setzt den Wert einer Person in einer Notizspalte (leer = löschen)."""

    student_id: StudentId
    column_id: str
    text: str
