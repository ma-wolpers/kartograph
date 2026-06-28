"""Usecases für Noten-Operationen (Spalten, Einzelnoten, Gewichtung, Anzeige).

Noten werden über ``column_id`` (Spalte) und ``StudentId`` (Schüler) adressiert,
nicht mehr über (x, y)-Koordinaten. Sessions übernehmen die Rolle der alten
``documentation_entries``-Dicts.
"""

from __future__ import annotations

import uuid
from copy import deepcopy

from app.core.domain.models_v4 import GradeColumn, GradeWeighting, SeatingPlan
from app.core.domain.student_id import StudentId
from app.core.usecases.v4._shared import (
    _normalize_doc_date,
    _round_half_up_to_int,
    _round_half_up_to_two_decimals,
)
from app.core.usecases.v4.session_usecases import ensure_session


def add_grade_column(
    plan: SeatingPlan, category: str, title: str
) -> tuple[SeatingPlan, str]:
    """Legt eine neue Notenspalte an.

    Ungültige Kategorien werden still ignoriert; ``column_id`` ist dann leer.

    Args:
        plan: Ausgangsplan.
        category: ``"schriftlich"`` oder ``"sonstig"``.
        title: Anzeigetitel; leer ergibt einen Standardtitel.

    Returns:
        Tupel aus (neuer Plan, neuer column_id).
    """
    clean_cat = str(category or "").strip().lower()
    if clean_cat not in {"schriftlich", "sonstig"}:
        return deepcopy(plan), ""

    clean_title = (
        str(title or "").strip()
        or f"{clean_cat.title()} {len(plan.documentation.grade_columns) + 1}"
    )
    next_plan = deepcopy(plan)
    column_id = uuid.uuid4().hex[:8]
    next_plan.documentation.grade_columns.append(
        GradeColumn(
            column_id=column_id,
            category=clean_cat,  # type: ignore[arg-type]
            title=clean_title,
        )
    )
    return next_plan, column_id


def record_grade(
    plan: SeatingPlan,
    student_id: StudentId,
    date: str | None,
    column_id: str,
    grade: float | None,
) -> SeatingPlan:
    """Setzt oder löscht eine Note für einen Schüler an einem Datum.

    ``grade=None`` entfernt die Note. Gültige Noten werden auf [1.0, 6.0] geclampt.
    Die Session wird bei Bedarf angelegt.

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        date: Datum im Format YYYY-MM-DD (None = heute).
        column_id: ID der Notenspalte.
        grade: Neue Note oder None zum Löschen.

    Returns:
        Neuer Plan mit der aktualisierten Note.
    """
    clean_col = str(column_id or "").strip()
    if not clean_col:
        return deepcopy(plan)
    if plan.documentation.column_by_id(clean_col) is None:
        return deepcopy(plan)

    next_plan = ensure_session(plan, date)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None or not student.is_named():
        return next_plan

    date_key = _normalize_doc_date(date)
    session = next_plan.documentation.session_for_date(date_key)
    if session is None:
        return next_plan

    entry = session.ensure_entry(student_id)
    if grade is None:
        entry.grades.pop(clean_col, None)
    else:
        entry.grades[clean_col] = max(1.0, min(6.0, float(grade)))

    if not entry.has_content():
        session.entries.pop(student_id, None)

    return next_plan


def set_grade_weighting(
    plan: SeatingPlan, written_percent: int, sonstige_percent: int
) -> SeatingPlan:
    """Legt die Gewichtung schriftlicher vs. sonstiger Noten fest.

    Negative Werte werden auf 0 geclampt; sind beide 0, wird 50/50 verwendet.

    Args:
        plan: Ausgangsplan.
        written_percent: Anteil der schriftlichen Note (0–100).
        sonstige_percent: Anteil der sonstigen Note (0–100).

    Returns:
        Neuer Plan mit der aktualisierten Gewichtung.
    """
    next_plan = deepcopy(plan)
    wp = max(0, int(written_percent))
    sp = max(0, int(sonstige_percent))
    if wp + sp <= 0:
        wp, sp = 50, 50
    next_plan.documentation.weighting = GradeWeighting(
        written_percent=wp, sonstige_percent=sp
    )
    return next_plan


def compute_grade_display(
    plan: SeatingPlan,
    student_id: StudentId,
    allow_provisional: bool = True,
) -> str:
    """Berechnet die Gesamtnoten-Anzeige für einen Schüler.

    Liegen sowohl schriftliche als auch sonstige Noten vor, wird die gewichtete
    Gesamtnote als ``"3.67"`` formatiert. Bei nur einer Kategorie und
    *allow_provisional=True* erscheint ein Klammerausdruck wie ``"(3)"``.

    Args:
        plan: Plan, aus dem gelesen wird.
        student_id: ID des Schülers.
        allow_provisional: Vorläufige Noten in Klammern zurückgeben.

    Returns:
        Formatierter Notenstring oder ``""``.
    """
    student = plan.classroom.student_by_id(student_id)
    if student is None or not student.is_named():
        return ""

    cat_by_col: dict[str, str] = {
        col.column_id: col.category
        for col in plan.documentation.grade_columns
    }
    written_vals: list[float] = []
    sonstige_vals: list[float] = []

    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        entry = session.entry_for(student_id)
        if entry is None:
            continue
        for col_id, grade_val in entry.grades.items():
            cat = cat_by_col.get(col_id)
            if cat == "schriftlich":
                written_vals.append(float(grade_val))
            elif cat == "sonstig":
                sonstige_vals.append(float(grade_val))

    if not written_vals and not sonstige_vals:
        return ""

    written_avg = sum(written_vals) / len(written_vals) if written_vals else None
    sonstige_avg = sum(sonstige_vals) / len(sonstige_vals) if sonstige_vals else None

    if written_avg is not None and sonstige_avg is not None:
        w = _round_half_up_to_int(written_avg)
        s = _round_half_up_to_int(sonstige_avg)
        weighting = plan.documentation.weighting
        total = weighting.written_percent + weighting.sonstige_percent
        if total <= 0:
            total = 100
        overall = (w * weighting.written_percent + s * weighting.sonstige_percent) / total
        return f"{_round_half_up_to_two_decimals(overall):.2f}"

    if not allow_provisional:
        return ""

    partial = written_avg if written_avg is not None else sonstige_avg
    assert partial is not None
    return f"({_round_half_up_to_int(partial)})"


def compute_grade_subtotal_display(
    plan: SeatingPlan, student_id: StudentId, category: str
) -> str:
    """Berechnet den Durchschnitt einer Notenkategorie für einen Schüler.

    Args:
        plan: Plan, aus dem gelesen wird.
        student_id: ID des Schülers.
        category: ``"schriftlich"`` oder ``"sonstig"``.

    Returns:
        Gerundeter Durchschnitt als String (z.B. ``"3"``), oder ``""``.
    """
    student = plan.classroom.student_by_id(student_id)
    if student is None or not student.is_named():
        return ""

    clean_cat = str(category or "").strip().lower()
    if clean_cat not in {"schriftlich", "sonstig"}:
        return ""

    valid_cols = {
        col.column_id
        for col in plan.documentation.grade_columns
        if col.category == clean_cat
    }
    if not valid_cols:
        return ""

    values: list[float] = []
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        entry = session.entry_for(student_id)
        if entry is None:
            continue
        for col_id, grade_val in entry.grades.items():
            if col_id in valid_cols:
                values.append(float(grade_val))

    return str(_round_half_up_to_int(sum(values) / len(values))) if values else ""
