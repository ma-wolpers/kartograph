"""Kartograph Domänenmodelle — Format v4.

Ersetzt langfristig ``models.py`` (v3). Die zentralen Unterschiede:

- ``Student`` besitzt eine stabile :class:`StudentId` — Sitzwechsel
  invalidieren keine Dokumentationsdaten mehr.
- Tischgruppen-Geometrie liegt einmalig in ``TableGroup.seats``,
  nicht redundant in jedem ``Desk``.
- Dokumentation wird als geordnete ``Session``-Liste gespeichert;
  Abfragen über ein Datum erfordern kein vollständiges Desk-Iterieren.
- Farbpalette: ``color_palette[key]`` trägt Label, Hex-Wert *und*
  pädagogische Bedeutung in einem Objekt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.domain.student_id import StudentId

GradeCategory = Literal["schriftlich", "sonstig"]
ParticipationRating = Literal["+", "o", "-"]


# ---------------------------------------------------------------------------
# Plan-Metadaten
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PlanMeta:
    """Beschreibende Metadaten eines Sitzplans (kein Domänenzustand)."""

    name: str
    school_year: str = ""
    created_at: str = ""       # ISO-8601-Datetime, z. B. "2025-08-15T09:00:00"
    last_modified: str = ""    # ISO-8601-Datetime


# ---------------------------------------------------------------------------
# Klassenraum: Lehrertisch + Schüler
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Seat:
    """Rasterkoordinaten eines Sitzplatzes."""

    x: int
    y: int


@dataclass(slots=True)
class TeacherSeat:
    """Fester Lehrertisch — kein Student, kein Tischgruppen-Mitglied."""

    x: int
    y: int


@dataclass(slots=True)
class DiagnosticProfile:
    """Dauerhaft sichtbare Schülermerkmale (Symbole, Farbmarkierungen).

    Diese Daten beschreiben den Schüler unabhängig vom Datum —
    im Gegensatz zu ``SessionEntry``, das tagesaktuelle Beobachtungen hält.
    """

    symbols: dict[str, int] = field(default_factory=dict)
    color_tags: list[str] = field(default_factory=list)
    accommodations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Student:
    """Ein Schüler mit stabiler ID, Sitzplatz und Diagnoseprofil."""

    student_id: StudentId
    first_name_official: str
    last_name: str
    seat: Seat
    nickname: str = ""
    diagnostic: DiagnosticProfile = field(default_factory=DiagnosticProfile)

    @property
    def first_name(self) -> str:
        """Effektiver Vorname für Anzeigezwecke: Spitzname falls gesetzt, sonst der offizielle Vorname.

        Schreibgeschützt (kein Setter) — Umbenennen läuft immer explizit über
        ``first_name_official``. Das erzwingt, dass jeder Code, der ``.first_name``
        liest, automatisch spitznamen-bewusst ist, ohne das wissen zu müssen; nur
        Stellen, die wirklich den offiziellen Vornamen brauchen (Vorname-Editierfeld,
        Umbenennen-Logik, Persistenz), greifen bewusst auf ``first_name_official`` zu.
        """
        nickname = self.nickname.strip()
        return nickname if nickname else self.first_name_official

    def display_name(self) -> str:
        """Gibt „Nachname, Vorname" zurück, oder Koordinaten als Fallback."""
        last = self.last_name.strip()
        first = self.first_name.strip()
        if last and first:
            return f"{last}, {first}"
        return last or first or f"({self.seat.x},{self.seat.y})"

    def is_named(self) -> bool:
        """True, wenn mindestens ein (effektiver) Vorname gesetzt ist."""
        return bool(self.first_name.strip())


@dataclass(slots=True)
class Classroom:
    """Der Klassenraum: Lehrertisch und alle Schülerplätze."""

    teacher_seat: TeacherSeat
    students: list[Student] = field(default_factory=list)

    def student_at(self, x: int, y: int) -> Student | None:
        """Gibt den Schüler an Koordinate (x, y) zurück, oder None.

        Args:
            x: X-Rasterkoordinate des gesuchten Sitzplatzes.
            y: Y-Rasterkoordinate des gesuchten Sitzplatzes.
        """
        for student in self.students:
            if student.seat.x == x and student.seat.y == y:
                return student
        return None

    def student_by_id(self, student_id: StudentId) -> Student | None:
        """Gibt den Schüler mit der angegebenen ID zurück, oder None.

        Args:
            student_id: ID des gesuchten Schülers.
        """
        for student in self.students:
            if student.student_id == student_id:
                return student
        return None


# ---------------------------------------------------------------------------
# Tischgruppen
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GroupSeat:
    """Ein Platz innerhalb einer Tischgruppe mit optionalem Geometrie-Offset."""

    x: int
    y: int
    shift_x: float = 0.0
    shift_y: float = 0.0
    rotation: float = 0.0


@dataclass(slots=True)
class TableGroup:
    """Eine Tischgruppe: Geometrie einmalig pro Gruppe, nicht pro Desk."""

    group_id: int
    seats: list[GroupSeat] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Farbpalette
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PaletteEntry:
    """Ein Farbeintrag mit Label, Hex-Wert und pädagogischer Bedeutung."""

    label: str
    hex: str
    meaning: str = ""


# ---------------------------------------------------------------------------
# Dokumentation: Notenstruktur
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GradeColumn:
    """Definition einer Notenspalte (z. B. „Mathearbeit 1")."""

    column_id: str
    category: GradeCategory
    title: str
    created_at: str = ""   # ISO-8601-Datum der Erstellung


@dataclass(slots=True)
class GradeWeighting:
    """Gewichtung schriftlicher vs. sonstiger Noten in Prozent."""

    written_percent: int = 50
    sonstige_percent: int = 50


# ---------------------------------------------------------------------------
# Dokumentation: Sessions (tagesaktuelle Beobachtungen)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SessionEntry:
    """Beobachtungen eines einzelnen Schülers an einem Unterrichtstag."""

    symbols: dict[str, int] = field(default_factory=dict)
    grades: dict[str, float] = field(default_factory=dict)
    note: str = ""
    participation: ParticipationRating | None = None

    def has_content(self) -> bool:
        """Prüft, ob der Eintrag Symbole, Noten, eine Notiz oder eine Mitarbeit-Bewertung enthält."""
        return bool(self.symbols or self.grades or self.note.strip() or self.participation is not None)


@dataclass(slots=True)
class Session:
    """Alle Beobachtungen einer Klasse an einem Datum.

    ``entries`` ist nach ``StudentId`` indiziert — kein Desk-Lookup nötig.
    """

    date: str                                          # YYYY-MM-DD
    entries: dict[StudentId, SessionEntry] = field(default_factory=dict)

    def entry_for(self, student_id: StudentId) -> SessionEntry | None:
        """Gibt den Eintrag des Schülers mit *student_id* zurück, oder None.

        Args:
            student_id: ID des gesuchten Schülers.
        """
        return self.entries.get(student_id)

    def ensure_entry(self, student_id: StudentId) -> SessionEntry:
        """Gibt den Eintrag zurück; legt ihn an, falls noch nicht vorhanden.

        Args:
            student_id: ID des Schülers, dessen Eintrag geholt oder angelegt wird.
        """
        if student_id not in self.entries:
            self.entries[student_id] = SessionEntry()
        return self.entries[student_id]


@dataclass(slots=True)
class DocumentationBlock:
    """Alle Dokumentationsdaten eines Plans: Spalten, Gewichtung, Sessions."""

    grade_columns: list[GradeColumn] = field(default_factory=list)
    weighting: GradeWeighting = field(default_factory=GradeWeighting)
    sessions: list[Session] = field(default_factory=list)

    def session_for_date(self, date: str) -> Session | None:
        """Gibt die Session zum Datum *date* zurück, oder None.

        Args:
            date: Gesuchtes Datum im Format YYYY-MM-DD.
        """
        for session in self.sessions:
            if session.date == date:
                return session
        return None

    def all_dates(self) -> list[str]:
        """Gibt alle Session-Daten sortiert zurück."""
        return sorted(s.date for s in self.sessions)

    def column_by_id(self, column_id: str) -> GradeColumn | None:
        """Gibt die Notenspalte mit *column_id* zurück, oder None.

        Args:
            column_id: ID der gesuchten Notenspalte.
        """
        for col in self.grade_columns:
            if col.column_id == column_id:
                return col
        return None


# ---------------------------------------------------------------------------
# Aggregat-Root
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SeatingPlan:
    """Aggregat-Root eines Kartograph-Sitzplans (Format v4).

    Alle Mutationen erfolgen über Usecases, die eine neue Instanz
    zurückgeben (immutable-update-Muster). Direkte Zuweisung auf Felder
    dieser Klasse ist nur innerhalb von Usecases erlaubt.
    """

    format_version: int
    plan_id: str
    meta: PlanMeta
    classroom: Classroom
    tablegroups: list[TableGroup] = field(default_factory=list)
    color_palette: dict[str, PaletteEntry] = field(default_factory=dict)
    documentation: DocumentationBlock = field(default_factory=DocumentationBlock)

    # --- Convenience-Shortcuts auf Classroom-Methoden --------------------

    def student_at(self, x: int, y: int) -> Student | None:
        """Gibt den Schüler an Koordinate (x, y) zurück, oder None.

        Args:
            x: X-Rasterkoordinate des gesuchten Sitzplatzes.
            y: Y-Rasterkoordinate des gesuchten Sitzplatzes.
        """
        return self.classroom.student_at(x, y)

    def student_by_id(self, student_id: StudentId) -> Student | None:
        """Gibt den Schüler mit der angegebenen ID zurück, oder None.

        Args:
            student_id: ID des gesuchten Schülers.
        """
        return self.classroom.student_by_id(student_id)

    def tablegroup_for_seat(self, x: int, y: int) -> TableGroup | None:
        """Gibt die Tischgruppe zurück, zu der Platz (x, y) gehört.

        Args:
            x: X-Rasterkoordinate des gesuchten Sitzplatzes.
            y: Y-Rasterkoordinate des gesuchten Sitzplatzes.
        """
        for group in self.tablegroups:
            for seat in group.seats:
                if seat.x == x and seat.y == y:
                    return group
        return None
