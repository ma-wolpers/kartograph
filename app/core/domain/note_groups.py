"""Einträge des Notizenbereichs und Gruppenblätter daraus (reines Python, kein Tk, kein ReportLab).

Einzige Regel, was eine Person in einer Spalte des Notizenbereichs stehen hat
(``note_entries``). Die Tabelle der Datenansicht zeigt daraus ihre Zelltexte,
der Gruppen-Export bildet daraus seine Gruppen, damit beide nie auseinanderlaufen:

- allgemeine Notizen: jede gespeicherte Zeile ist ein Eintrag,
- Ja/Nein-Spalte: ein Eintrag ``FLAG_MARK``, wenn die Person markiert ist,
- eigene Notizspalte: der gespeicherte Wert (Anzeige über ``NOTE_VALUE_KINDS``).

``build_group_sheet`` macht daraus das Blatt "Gruppen exportieren"
(Entscheidungen der Nutzerin 2026-11-22): alle Werte der Spalte, exakt
verglichen; Personen ohne Eintrag auf Wunsch als eigenes Kästchen; Namen
alphabetisch; Kästchen-Überschrift in drei Stufen (``GROUP_LABEL_MODES``),
bei den geheimen Stufen gemischt (und zufällig nummeriert), damit weder
Reihenfolge noch Nummer etwas verraten. Dauerhaft Abwesende fehlen wie in
allen Exporten (``active_students``).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.domain.flag_columns import FLAG_MARK
from app.core.domain.models_v4 import SeatingPlan, Student
from app.core.domain.note_column_kinds import NOTE_VALUE_KINDS
from app.core.domain.permanent_absence import active_students
from app.core.domain.student_id import StudentId
from app.core.domain.student_naming import compute_display_names, name_sort_key

NoteSourceKind = Literal["notes", "flag", "column"]
GroupLabelMode = Literal["note", "numbered", "none"]

GROUP_LABEL_MODES: tuple[tuple[GroupLabelMode, str], ...] = (
    ("note", "Notiz anzeigen"),
    ("numbered", "Geheim – zufällig nummeriert"),
    ("none", "Geheim – ohne Überschrift"),
)
"""Stufen der Kästchen-Überschrift als ``(Schlüssel, Beschriftung)`` (direkt für ``RadioGroup``)."""
DEFAULT_GROUP_LABEL_MODE: GroupLabelMode = "note"
WITHOUT_ENTRY_TITLE = "ohne Eintrag"


@dataclass(frozen=True)
class NoteSource:
    """Eine Spalte des Notizenbereichs.

    Attributes:
        kind: ``"notes"`` (allgemeine Notizen), ``"flag"`` (Ja/Nein) oder ``"column"`` (eigene Notizspalte).
        key: Farb-/``flag_…``-Schlüssel bzw. Spalten-ID; leer für die allgemeinen Notizen.
    """

    kind: NoteSourceKind
    key: str = ""


@dataclass(frozen=True)
class GroupBox:
    """Ein Kästchen des Gruppenblatts.

    Attributes:
        title: Überschrift oder ``None`` (Stufe "ohne Überschrift").
        names: Anzeigenamen, alphabetisch.
    """

    title: str | None
    names: tuple[str, ...]


@dataclass(frozen=True)
class GroupSheet:
    """Inhalt des Gruppenblatts, fertig zum Zeichnen.

    Attributes:
        heading: Überschrift des Blatts.
        boxes: Kästchen in Zeichenreihenfolge.
    """

    heading: str
    boxes: tuple[GroupBox, ...]


def note_entries(plan: SeatingPlan, student: Student, source: NoteSource) -> tuple[tuple[str, str], ...]:
    """Einträge von *student* in der Spalte *source* als Paare (gespeicherter Wert, Anzeigetext).

    Args:
        plan: Plan (für Typ und Existenz eigener Notizspalten).
        student: Person.
        source: Spalte des Notizenbereichs.

    Returns:
        Leer, wenn die Person in der Spalte nichts stehen hat.
    """
    diagnostic = student.diagnostic
    if source.kind == "notes":
        return tuple((line, line) for line in diagnostic.notes)
    if source.kind == "flag":
        return ((FLAG_MARK, FLAG_MARK),) if source.key in diagnostic.color_tags else ()
    column = next((c for c in plan.note_columns if c.column_id == source.key), None)
    stored = diagnostic.note_values.get(source.key, "") if column is not None else ""
    return ((stored, NOTE_VALUE_KINDS[column.kind].display(stored)),) if stored else ()


def count_without_entry(plan: SeatingPlan, source: NoteSource) -> int:
    """Zahl der mitzählenden Personen ohne Eintrag in *source* (Dialog fragt nur, wenn > 0).

    Args:
        plan: Plan.
        source: Spalte des Notizenbereichs.
    """
    return sum(1 for s in active_students(plan.classroom.students) if not note_entries(plan, s, source))


def _group_order_key(plan: SeatingPlan, source: NoteSource, stored: str) -> tuple:
    """Reihenfolge der Gruppen bei "Notiz anzeigen": Typregel der Spalte, sonst alphabetisch."""
    column = next((c for c in plan.note_columns if c.column_id == source.key), None) if source.kind == "column" else None
    if column is not None:
        return NOTE_VALUE_KINDS[column.kind].sort_value(stored)
    return (0, stored.casefold())


def build_group_sheet(
    plan: SeatingPlan,
    source: NoteSource,
    *,
    column_title: str,
    label_mode: GroupLabelMode,
    include_without: bool,
    name_format: str,
    disambiguate: bool,
    rng: random.Random,
) -> GroupSheet:
    """Baut das Gruppenblatt der Spalte *source*.

    Args:
        plan: Plan.
        source: Spalte des Notizenbereichs.
        column_title: Spaltentitel wie in der Datenansicht (Ja/Nein: Titel des Kästchens).
        label_mode: Stufe der Kästchen-Überschrift (``GROUP_LABEL_MODES``).
        include_without: Personen ohne Eintrag als eigenes Kästchen aufnehmen.
        name_format: Namensformat der Einstellungen.
        disambiguate: Eindeutigkeits-Modus der Einstellungen.
        rng: Zufallsquelle fürs Mischen der geheimen Stufen (Tests: fester Seed).

    Returns:
        Überschrift und Kästchen in Zeichenreihenfolge.
    """
    students = active_students(plan.classroom.students)
    names = compute_display_names(students, name_format, disambiguate)
    groups: dict[str, tuple[str, list[StudentId]]] = {}
    without: list[StudentId] = []
    for student in students:
        entries = note_entries(plan, student, source)
        if not entries:
            without.append(student.student_id)
        for stored, display in entries:
            title = column_title if source.kind == "flag" else display
            groups.setdefault(stored, (title, []))[1].append(student.student_id)

    def box(title: str, members: Sequence[StudentId]) -> GroupBox:
        return GroupBox(title, tuple(sorted((names[m] for m in members), key=name_sort_key)))

    boxes = [box(*groups[stored]) for stored in sorted(groups, key=lambda s: _group_order_key(plan, source, s))]
    if include_without and without:
        boxes.append(box(WITHOUT_ENTRY_TITLE, without))
    if label_mode == "note":
        return GroupSheet(f"{plan.meta.name} – {column_title}", tuple(boxes))
    rng.shuffle(boxes)
    numbered = label_mode == "numbered"
    return GroupSheet(
        plan.meta.name,
        tuple(GroupBox(f"Gruppe {index}" if numbered else None, b.names) for index, b in enumerate(boxes, start=1)),
    )
