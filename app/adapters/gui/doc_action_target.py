"""Ziel einer Doku-Aktion: für wen und an welchem Datum sie wirkt.

Doku-Aktionen (Doku- und Diagnosesymbole, Mitarbeit-Bewertung) schreiben
einen Tageseintrag eines Schülers. Wer und welches Datum das ist, bestimmt
ausschließlich ``SelectionMixin._doc_action_target()`` aus der aktiven
Oberfläche; die Aktionen selbst bekommen nur noch dieses fertige Ziel.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.student_id import StudentId


@dataclass(frozen=True)
class DocActionTarget:
    """Schüler und Datum, auf die eine Doku-Aktion wirkt.

    Attributes:
        student_id: Benannter Schüler, dessen Tageseintrag geändert wird.
        date: ISO-Datum (YYYY-MM-DD) des Tageseintrags.
    """

    student_id: StudentId
    date: str
