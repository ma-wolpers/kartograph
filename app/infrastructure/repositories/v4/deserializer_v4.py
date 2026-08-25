"""Deserialisierung eines JSON-Dicts (Format v4) in ein SeatingPlan-Objekt.

Alle Eingaben werden misstrauisch behandelt: fehlende Schlüssel, falsche
Typen und ungültige Werte werden abgefangen und durch Standardwerte ersetzt
oder führen zu einem ``ValueError`` mit aussagekräftiger Meldung.
"""

from __future__ import annotations

import uuid

from app.core.domain.models_v4 import (
    Classroom,
    CustomSymbolDefinition,
    DiagnosticProfile,
    DocumentationBlock,
    GradeColumn,
    GradeWeighting,
    GroupSeat,
    PaletteEntry,
    PlanMeta,
    SeatingPlan,
    Seat,
    Session,
    SessionEntry,
    Student,
    TableGroup,
    TeacherSeat,
)
from app.core.domain.student_id import StudentId


# ---------------------------------------------------------------------------
# Öffentliche API
# ---------------------------------------------------------------------------

def deserialize_plan(payload: dict) -> SeatingPlan:
    """Deserialisiert ein v4-JSON-Dict in einen ``SeatingPlan``.

    Args:
        payload: Geparster JSON-Inhalt der Plandatei.

    Returns:
        Vollständig deserialisierter Sitzplan.

    Raises:
        ValueError: Bei strukturellen Fehlern (fehlendes Pflichtfeld, falscher Typ).
    """
    format_version = _coerce_int(payload.get("format_version"), 4)
    plan_id = str(payload.get("plan_id") or uuid.uuid4().hex)

    meta = _deserialize_meta(payload.get("meta") or {})
    classroom = _deserialize_classroom(payload.get("classroom") or {})
    tablegroups = _deserialize_tablegroups(payload.get("tablegroups") or [])
    color_palette = _deserialize_color_palette(payload.get("color_palette") or {})
    custom_symbols = _deserialize_custom_symbols(payload.get("custom_symbols") or {})
    documentation = _deserialize_documentation(payload.get("documentation") or {})

    return SeatingPlan(
        format_version=format_version,
        plan_id=plan_id,
        meta=meta,
        classroom=classroom,
        tablegroups=tablegroups,
        color_palette=color_palette,
        custom_symbols=custom_symbols,
        documentation=documentation,
    )


# ---------------------------------------------------------------------------
# Metadaten
# ---------------------------------------------------------------------------

def _deserialize_meta(raw: dict) -> PlanMeta:
    """Liest die Plan-Metadaten aus *raw*; fehlende Felder werden zu leeren Strings.

    Args:
        raw: Roh-Dict des ``meta``-Feldes aus der Plandatei.
    """
    return PlanMeta(
        name=str(raw.get("name") or "Unbenannter Sitzplan").strip(),
        school_year=str(raw.get("school_year") or "").strip(),
        created_at=str(raw.get("created_at") or "").strip(),
        last_modified=str(raw.get("last_modified") or "").strip(),
    )


# ---------------------------------------------------------------------------
# Klassenraum
# ---------------------------------------------------------------------------

def _deserialize_classroom(raw: dict) -> Classroom:
    """Liest Lehrertisch und Schülerliste aus *raw*.

    Args:
        raw: Roh-Dict des ``classroom``-Feldes aus der Plandatei.

    Raises:
        ValueError: Wenn ``teacher_seat`` kein Objekt oder ``students``
            keine Liste ist.
    """
    raw_ts = raw.get("teacher_seat")
    if not isinstance(raw_ts, dict):
        raise ValueError("classroom.teacher_seat muss ein Objekt sein")
    teacher_seat = TeacherSeat(
        x=_coerce_int(raw_ts.get("x"), 0),
        y=_coerce_int(raw_ts.get("y"), 0),
    )
    raw_students = raw.get("students") or []
    if not isinstance(raw_students, list):
        raise ValueError("classroom.students muss eine Liste sein")
    students = [_deserialize_student(item) for item in raw_students if isinstance(item, dict)]
    return Classroom(teacher_seat=teacher_seat, students=students)


def _deserialize_student(raw: dict) -> Student:
    """Liest einen Schüler aus *raw*; vergibt bei fehlender/ungültiger ID eine frische ``StudentId``.

    Args:
        raw: Roh-Dict eines einzelnen Schülers.
    """
    raw_id = str(raw.get("student_id") or "").strip()
    try:
        student_id = StudentId.of(raw_id) if raw_id else StudentId.new()
    except ValueError:
        student_id = StudentId.new()

    raw_seat = raw.get("seat") or {}
    seat = Seat(
        x=_coerce_int(raw_seat.get("x"), 0),
        y=_coerce_int(raw_seat.get("y"), 0),
    )
    diagnostic = _deserialize_diagnostic(raw.get("diagnostic") or {})
    return Student(
        student_id=student_id,
        first_name_official=str(raw.get("first_name") or "").strip(),
        last_name=str(raw.get("last_name") or "").strip(),
        seat=seat,
        nickname=str(raw.get("nickname") or "").strip(),
        diagnostic=diagnostic,
    )


def _deserialize_diagnostic(raw: dict) -> DiagnosticProfile:
    """Liest Symbole, Farbpunkte und Nachteilsausgleiche eines Schülers aus *raw*.

    Symbolstärken außerhalb von 1..3 werden verworfen statt geklemmt (eine
    fehlerhafte Stärke deutet auf eine korrupte/handgeschriebene Datei hin,
    nicht auf einen gültigen Grenzwert). Farbtags werden dedupliziert,
    Nachteilsausgleiche behalten ihre ursprüngliche Reihenfolge (auch bei
    Duplikaten).

    Args:
        raw: Roh-Dict des ``diagnostic``-Feldes eines Schülers.
    """
    symbols: dict[str, int] = {}
    raw_symbols = raw.get("symbols") or {}
    if isinstance(raw_symbols, dict):
        for name, strength in raw_symbols.items():
            name = str(name).strip()
            if not name:
                continue
            try:
                parsed = int(strength)
            except (TypeError, ValueError):
                continue
            if 1 <= parsed <= 3:
                symbols[name] = parsed

    color_tags: list[str] = []
    raw_tags = raw.get("color_tags") or []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            key = str(tag).strip()
            if key and key not in color_tags:
                color_tags.append(key)

    accommodations: list[str] = []
    raw_accommodations = raw.get("accommodations") or []
    if isinstance(raw_accommodations, list):
        for entry in raw_accommodations:
            text = str(entry).strip()
            if text:
                accommodations.append(text)

    return DiagnosticProfile(symbols=symbols, color_tags=color_tags, accommodations=accommodations)


# ---------------------------------------------------------------------------
# Tischgruppen
# ---------------------------------------------------------------------------

def _deserialize_tablegroups(raw_list: list) -> list[TableGroup]:
    """Liest die Tischgruppen-Liste samt Sitzgeometrie (Versatz/Rotation pro Platz) aus *raw_list*.

    Args:
        raw_list: Roh-Liste des ``tablegroups``-Feldes aus der Plandatei.
    """
    groups: list[TableGroup] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        group_id = _coerce_int(item.get("group_id"), 0)
        raw_seats = item.get("seats") or []
        seats = [
            GroupSeat(
                x=_coerce_int(s.get("x"), 0),
                y=_coerce_int(s.get("y"), 0),
                shift_x=_coerce_float(s.get("shift_x"), 0.0),
                shift_y=_coerce_float(s.get("shift_y"), 0.0),
                rotation=_coerce_float(s.get("rotation"), 0.0),
            )
            for s in raw_seats
            if isinstance(s, dict)
        ]
        groups.append(TableGroup(group_id=group_id, seats=seats))
    return groups


# ---------------------------------------------------------------------------
# Farbpalette
# ---------------------------------------------------------------------------

def _deserialize_color_palette(raw: dict) -> dict[str, PaletteEntry]:
    """Liest die Farbpalette (Label/Hex/Bedeutung pro Farbschlüssel) aus *raw*; überspringt leere Schlüssel.

    Args:
        raw: Roh-Dict des ``color_palette``-Feldes aus der Plandatei.
    """
    palette: dict[str, PaletteEntry] = {}
    for key, entry in raw.items():
        key = str(key).strip()
        if not key or not isinstance(entry, dict):
            continue
        palette[key] = PaletteEntry(
            label=str(entry.get("label") or key).strip(),
            hex=str(entry.get("hex") or "").strip(),
            meaning=str(entry.get("meaning") or "").strip(),
        )
    return palette


# ---------------------------------------------------------------------------
# Eigene Doku-Symbole
# ---------------------------------------------------------------------------

def _deserialize_custom_symbols(raw: dict) -> dict[str, CustomSymbolDefinition]:
    """Liest die eigenen Doku-Symbole (id/glyph/meaning/shortcut) aus *raw*; überspringt leere Schlüssel.

    Bewusst LENIENT beim Shortcut-Feld (nur ``.strip()``, keine Re-Validierung
    gegen ``validate_custom_symbol_shortcut()``) — ein per Hand beschädigter
    Shortcut-Wert führt nicht zum Ladefehler des ganzen Plans, das Symbol
    bleibt sichtbar/editierbar, ist aber über Tastatur schlicht nicht
    erreichbar (der Ctrl+Shift-Handler matcht nur exakt gültige kanonische
    Formen). Gleiche Fehlertoleranz-Philosophie wie
    ``load_symbol_definitions()`` für den globalen Katalog.

    Args:
        raw: Roh-Dict des ``custom_symbols``-Feldes aus der Plandatei.
    """
    result: dict[str, CustomSymbolDefinition] = {}
    for key, entry in raw.items():
        key = str(key).strip()
        if not key or not isinstance(entry, dict):
            continue
        result[key] = CustomSymbolDefinition(
            id=str(entry.get("id") or key).strip(),
            glyph=str(entry.get("glyph") or "").strip(),
            meaning=str(entry.get("meaning") or "").strip(),
            shortcut=str(entry.get("shortcut") or "").strip(),
        )
    return result


# ---------------------------------------------------------------------------
# Dokumentation
# ---------------------------------------------------------------------------

def _deserialize_documentation(raw: dict) -> DocumentationBlock:
    """Liest Notenspalten, Gewichtung und Sessions aus *raw* zu einem ``DocumentationBlock`` zusammen.

    Args:
        raw: Roh-Dict des ``documentation``-Feldes aus der Plandatei.
    """
    grade_columns = _deserialize_grade_columns(raw.get("grade_columns") or [])
    weighting = _deserialize_weighting(raw.get("grade_weighting") or {})
    sessions = _deserialize_sessions(raw.get("sessions") or [])
    return DocumentationBlock(
        grade_columns=grade_columns,
        weighting=weighting,
        sessions=sessions,
    )


def _deserialize_grade_columns(raw_list: list) -> list[GradeColumn]:
    """Liest Notenspalten aus *raw_list*; verwirft Einträge mit fehlender/doppelter ID oder ungültiger Kategorie.

    Args:
        raw_list: Roh-Liste des ``grade_columns``-Feldes aus der Plandatei.
    """
    columns: list[GradeColumn] = []
    seen: set[str] = set()
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        col_id = str(item.get("column_id") or "").strip()
        category = str(item.get("category") or "").strip().lower()
        title = str(item.get("title") or "").strip()
        if not col_id or col_id in seen:
            continue
        if category not in {"schriftlich", "sonstig"}:
            continue
        columns.append(GradeColumn(
            column_id=col_id,
            category=category,  # type: ignore[arg-type]
            title=title or col_id,
            created_at=str(item.get("created_at") or "").strip(),
        ))
        seen.add(col_id)
    return columns


def _deserialize_weighting(raw: dict) -> GradeWeighting:
    """Liest die Notengewichtung aus *raw*; fällt auf 50/50 zurück, wenn beide Anteile zusammen <= 0 wären.

    Args:
        raw: Roh-Dict des ``grade_weighting``-Feldes aus der Plandatei.
    """
    written = _coerce_int(raw.get("written_percent"), 50)
    sonstige = _coerce_int(raw.get("sonstige_percent"), 50)
    if written + sonstige <= 0:
        written, sonstige = 50, 50
    return GradeWeighting(written_percent=written, sonstige_percent=sonstige)


def _deserialize_sessions(raw_list: list) -> list[Session]:
    """Liest die Sessions aus *raw_list*; überspringt Einträge mit fehlendem oder doppeltem Datum.

    Args:
        raw_list: Roh-Liste des ``sessions``-Feldes aus der Plandatei.
    """
    sessions: list[Session] = []
    seen_dates: set[str] = set()
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        date = str(item.get("date") or "").strip()
        if not date or date in seen_dates:
            continue
        entries = _deserialize_entries(item.get("entries") or {})
        sessions.append(Session(date=date, entries=entries))
        seen_dates.add(date)
    return sessions


def _deserialize_entries(raw: dict) -> dict[StudentId, SessionEntry]:
    """Liest die Schüler-Einträge einer Session aus *raw*.

    Verwirft Einträge mit ungültiger ``StudentId`` sowie solche, die nach dem
    Parsen leer sind (``SessionEntry.has_content()`` False) — eine Session
    soll nur tatsächlich dokumentierte Schüler enthalten.

    Args:
        raw: Roh-Dict des ``entries``-Feldes einer Session (StudentId → Eintrag).
    """
    entries: dict[StudentId, SessionEntry] = {}
    for raw_id, raw_entry in raw.items():
        raw_id = str(raw_id).strip()
        if not raw_id or not isinstance(raw_entry, dict):
            continue
        try:
            sid = StudentId.of(raw_id)
        except ValueError:
            continue

        symbols: dict[str, int] = {}
        for name, strength in (raw_entry.get("symbols") or {}).items():
            name = str(name).strip()
            if not name:
                continue
            try:
                parsed = int(strength)
            except (TypeError, ValueError):
                continue
            if 1 <= parsed <= 3:
                symbols[name] = parsed

        grades: dict[str, float] = {}
        for col_id, grade in (raw_entry.get("grades") or {}).items():
            col_id = str(col_id).strip()
            if not col_id:
                continue
            try:
                grades[col_id] = float(grade)
            except (TypeError, ValueError):
                continue

        note = str(raw_entry.get("note") or "").strip()

        raw_participation = raw_entry.get("participation")
        participation = raw_participation if raw_participation in ("+", "o", "-", "☆") else None

        entry = SessionEntry(symbols=symbols, grades=grades, note=note, participation=participation)
        if entry.has_content():
            entries[sid] = entry
    return entries


# ---------------------------------------------------------------------------
# Coerce-Helfer
# ---------------------------------------------------------------------------

def _coerce_int(raw: object, default: int) -> int:
    """Wandelt *raw* in ``int`` um; gibt *default* zurück, wenn das nicht möglich ist.

    Args:
        raw: Roher, beliebig typisierter Eingabewert.
        default: Rückgabewert, falls die Umwandlung fehlschlägt.
    """
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _coerce_float(raw: object, default: float) -> float:
    """Wandelt *raw* in ``float`` um; gibt *default* zurück, wenn das nicht möglich ist.

    Args:
        raw: Roher, beliebig typisierter Eingabewert.
        default: Rückgabewert, falls die Umwandlung fehlschlägt.
    """
    try:
        return float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
