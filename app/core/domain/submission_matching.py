"""Ordnet Unterordner einer Abgabe-ZIP den Schüler:innen eines Plans zu (rein, Tk-frei).

Ordnernamen haben die Form "Vorname [Zweitnamen …] Nachname". Ein Ordner
passt zu einer Person, wenn sein **erstes Wort** dem ersten Wort ihres
offiziellen Vornamens (oder ihres Spitznamens) entspricht und die Wörter
ihres **Nachnamens am Ende** stehen; Zweitnamen dazwischen sind erlaubt.
Verglichen wird normalisiert (s. :func:`normalize_name`), reine Zahlen-
Wörter (Export-IDs) werden ignoriert. Alles, was nicht eindeutig ist, landet
im Ergebnis als mehrdeutig/unbekannt und wird im Zuordnungsdialog geklärt —
es wird nie geraten.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Protocol

from app.core.domain.student_id import StudentId

# Vor der Akzent-Entfernung, damit "Müller" und "Mueller" gleich werden.
_TRANSLITERATION = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_SEPARATORS = re.compile(r"[\s\-_.,;]+")


class _Student(Protocol):
    """Was der Abgleich von einem Schüler braucht."""

    student_id: StudentId
    first_name_official: str
    last_name: str
    nickname: str

    def is_named(self) -> bool:
        """Ob die Person einen Namen hat (leere Tische zählen nicht)."""
        ...


@dataclass(frozen=True)
class MatchResult:
    """Ergebnis des Abgleichs.

    Attributes:
        matched: Ordner → eindeutig zugeordnete Person.
        ambiguous: Ordner → mögliche Personen (mehrere Treffer, oder dieselbe
            Person passt zu mehreren Ordnern).
        unknown: Ordner ohne passende Person.
        without_folder: Benannte Personen ohne zugeordneten Ordner.
    """

    matched: dict[str, StudentId]
    ambiguous: dict[str, tuple[StudentId, ...]]
    unknown: tuple[str, ...]
    without_folder: tuple[StudentId, ...]


def normalize_name(text: str) -> tuple[str, ...]:
    """Zerlegt *text* in normalisierte Wörter.

    Klein, ä/ö/ü/ß ausgeschrieben, übrige Akzente entfernt, Bindestrich,
    Unterstrich, Punkt, Komma als Trenner, reine Ziffernfolgen verworfen.

    Args:
        text: Ordner- oder Personenname.

    Examples:
        ``"Anna-Lena Müller_123"`` → ``("anna", "lena", "mueller")``;
        ``"José Núñez"`` → ``("jose", "nunez")``.
    """
    lowered = text.casefold().translate(_TRANSLITERATION)
    plain = "".join(c for c in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(c))
    return tuple(word for word in _SEPARATORS.split(plain) if word and not word.isdigit())


def _folder_fits(folder: tuple[str, ...], student: _Student) -> bool:
    """Prüft die Regel "erstes Wort = Vorname, Nachname am Ende" für einen Ordner.

    Args:
        folder: Normalisierte Wörter des Ordnernamens.
        student: Zu prüfende Person.
    """
    last = normalize_name(student.last_name)
    if not last or len(folder) <= len(last) or folder[-len(last):] != last:
        return False
    first_words = {words[0] for words in (normalize_name(student.first_name_official), normalize_name(student.nickname)) if words}
    return folder[0] in first_words


def match_submission_folders(folders: Iterable[str], students: Iterable[_Student]) -> MatchResult:
    """Ordnet *folders* den benannten *students* zu.

    Passt ein Ordner zu genau einer Person und diese Person zu keinem
    anderen Ordner, ist er eindeutig zugeordnet. Sonst wird er als
    mehrdeutig (mit Kandidaten) oder unbekannt gemeldet.

    Args:
        folders: Unterordnernamen der ZIP.
        students: Schüler:innen des Plans (unbenannte werden ignoriert).

    Returns:
        Das :class:`MatchResult`.
    """
    named = [s for s in students if s.is_named()]
    candidates: dict[str, tuple[StudentId, ...]] = {}
    unknown: list[str] = []
    for folder in folders:
        words = normalize_name(folder)
        hits = tuple(s.student_id for s in named if _folder_fits(words, s))
        if hits:
            candidates[folder] = hits
        else:
            unknown.append(folder)

    single_hit_counts = Counter(hits[0] for hits in candidates.values() if len(hits) == 1)
    duplicated = {sid for sid, count in single_hit_counts.items() if count > 1}
    matched = {f: h[0] for f, h in candidates.items() if len(h) == 1 and h[0] not in duplicated}
    ambiguous = {f: h for f, h in candidates.items() if f not in matched}
    assigned = set(matched.values())
    without = tuple(s.student_id for s in named if s.student_id not in assigned)
    return MatchResult(matched=matched, ambiguous=ambiguous, unknown=tuple(unknown), without_folder=without)
