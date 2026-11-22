from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class SetNotesIntent(Intent):
    """Ersetzt die Liste der Notizen eines Schülers vollständig.

    Attributes:
        student_id: Betroffene Person.
        notes: Vollständige neue Notizliste.
        running_input: ``True`` nur für laufendes Tippen im Notizfeld der
            Tischdetails -- dann fasst die History aufeinanderfolgende Änderungen
            derselben Person zu einem Undo-Schritt zusammen. Dialog, Einfügen und
            Ausschneiden sind je ein eigener Schritt (Vorgabe ``False``).
    """

    student_id: StudentId
    notes: list[str]
    running_input: bool = False


@dataclass(frozen=True)
class AddNoteColumnIntent(Intent):
    """Legt eine eigene Notizspalte an (*kind* aus ``NOTE_VALUE_KINDS``)."""

    title: str
    kind: str


@dataclass(frozen=True)
class RenameNoteColumnIntent(Intent):
    """Gibt der Notizspalte *column_id* den Titel *title* (leer wird abgelehnt)."""

    column_id: str
    title: str


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
