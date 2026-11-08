from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.models_v4 import DEFAULT_COLUMN_WEIGHT
from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class AddGradeColumnIntent(Intent):
    """Legt eine neue Notenspalte (*category* aus ``GRADE_CATEGORIES``) mit *title* und Faktor *weight* an."""

    category: str  # eine von GRADE_CATEGORIES
    title: str
    weight: float = DEFAULT_COLUMN_WEIGHT


@dataclass(frozen=True)
class DeleteGradeColumnIntent(Intent):
    """Löscht die Notenspalte *column_id* inkl. aller darin erfassten Noten."""

    column_id: str


@dataclass(frozen=True)
class RecordGradeIntent(Intent):
    """Trägt für einen Schüler in Spalte *column_id* den Wert *grade* ein (None = löschen).

    ``None`` statt ``0.0`` als Lösch-Signal, weil 0 Punkte ein gültiger Wert ist.
    """

    student_id: StudentId
    column_id: str
    grade: float | None  # None = löschen


@dataclass(frozen=True)
class ResolveGradeConflictsIntent(Intent):
    """Legt für alte Mehrfachnoten die gültige Note fest (*choices*: Schüler, Spalte, Note)."""

    choices: tuple[tuple[StudentId, str, float], ...]


@dataclass(frozen=True)
class UpdateGradeWeightingIntent(Intent):
    """Setzt Kategorie-Prozente (schriftlich/sonstig) und Spaltenfaktoren in einem Undo-Schritt.

    *column_weights* enthält ``(column_id, Faktor)``-Paare; nicht genannte
    Spalten behalten ihren Faktor.
    """

    written_percent: int
    sonstige_percent: int
    column_weights: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class SetGradeScaleIntent(Intent):
    """Stellt die planweite Notenskala auf *scale_id* um und rechnet alle Werte um.

    Die Rückfrage bei vorhandenen Noten erfolgt vorher in der GUI; der
    Intent selbst konvertiert immer.
    """

    scale_id: str
