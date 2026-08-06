from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId
from app.core.intents.base import Intent


@dataclass(frozen=True)
class ToggleDiagnosticSymbolIntent(Intent):
    """Schaltet ein Diagnose-Symbol im Schülerprofil um (unabhängig von der Dokumentations-Historie)."""

    student_id: StudentId
    symbol: str


@dataclass(frozen=True)
class RecordDocumentationSymbolIntent(Intent):
    """Trägt für einen Schüler an *date* die Stärke *strength* von *symbol* ein (0 = löschen)."""

    student_id: StudentId
    date: str
    symbol: str
    strength: int  # 0 = löschen
