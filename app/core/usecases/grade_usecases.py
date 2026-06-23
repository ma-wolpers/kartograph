"""Usecases für Noten-Operationen (Spalten, Einzel­noten, Gewichtung, Anzeige).

Noten werden spaltengebunden (``GradeColumnDefinition``) und datumgebunden
(``DocumentationEntry.grades``) gespeichert. Alle Berechnungen erfolgen
auf einer Kopie des Plans (immutable-Update-Muster).
"""

from __future__ import annotations

import uuid
from copy import deepcopy

from app.core.domain.models import DocumentationEntry, GradeCategory, GradeColumnDefinition, SeatingPlan
from app.core.usecases._shared import (
    _normalize_doc_date,
    _round_half_up_to_int,
    _round_half_up_to_two_decimals,
)
from app.core.usecases.date_usecases import ensure_documentation_date


def add_grade_column(plan: SeatingPlan, category: GradeCategory, title: str) -> tuple[SeatingPlan, str]:
    """Legt eine neue Notenspalte an.

    Ungültige Kategorien (weder ``"schriftlich"`` noch ``"sonstig"``)
    werden still ignoriert; es wird ein leerer ``column_id``-String
    zurückgegeben.

    Args:
        plan: Ausgangsplan.
        category: Notentyp – ``"schriftlich"`` oder ``"sonstig"``.
        title: Anzeigetitel der Spalte; leer ergibt einen Standardtitel.

    Returns:
        Tupel aus (neuer Plan, neuer column_id). column_id ist leer bei
        ungültiger Kategorie.
    """
    clean_category = str(category).strip().lower()
    if clean_category not in {"schriftlich", "sonstig"}:
        return deepcopy(plan), ""

    clean_title = (
        str(title or "").strip()
        or f"{clean_category.title()} {len(plan.grade_columns) + 1}"
    )
    next_plan = deepcopy(plan)
    column_id = uuid.uuid4().hex[:8]
    next_plan.grade_columns.append(
        GradeColumnDefinition(
            column_id=column_id,
            category=clean_category,  # type: ignore[arg-type]
            title=clean_title,
        )
    )
    return next_plan, column_id


def set_documentation_grade(
    plan: SeatingPlan,
    x: int,
    y: int,
    column_id: str,
    grade: float | None,
    doc_date: str | None = None,
) -> SeatingPlan:
    """Setzt oder löscht eine Note für eine bestimmte Spalte und ein Datum.

    ``grade=None`` entfernt die Note. Noten werden auf [1.0, 6.0] geclampt.
    Das Datum und der column_id müssen im Plan bekannt sein; sonst wird der
    Plan unverändert zurückgegeben.

    Args:
        plan: Ausgangsplan.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        column_id: ID der Notenspalte.
        grade: Neue Note (1.0–6.0) oder None zum Löschen.
        doc_date: Zieldatum; None ergibt das heutige Datum.

    Returns:
        Neuer Plan mit der aktualisierten Note.
    """
    clean_column_id = str(column_id or "").strip()
    if not clean_column_id:
        return deepcopy(plan)

    if all(item.column_id != clean_column_id for item in plan.grade_columns):
        return deepcopy(plan)

    next_plan = ensure_documentation_date(plan, doc_date)
    desk = next_plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return next_plan

    date_key = _normalize_doc_date(doc_date)
    entry = desk.documentation_entries.get(date_key)
    if entry is None:
        entry = DocumentationEntry()
        desk.documentation_entries[date_key] = entry

    if grade is None:
        entry.grades.pop(clean_column_id, None)
    else:
        entry.grades[clean_column_id] = max(1.0, min(6.0, float(grade)))

    if not entry.has_content():
        desk.documentation_entries.pop(date_key, None)
    return next_plan


def set_grade_weighting(plan: SeatingPlan, written_percent: int, sonstige_percent: int) -> SeatingPlan:
    """Legt die Gewichtung von schriftlichen vs. sonstigen Noten fest.

    Negative Werte werden auf 0 geclampt. Sind beide 0, wird 50/50
    verwendet.

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
    next_plan.written_weight_percent = wp
    next_plan.sonstige_weight_percent = sp
    return next_plan


def compute_grade_display_for_student(
    plan: SeatingPlan,
    x: int,
    y: int,
    allow_provisional: bool = True,
) -> str:
    """Berechnet die Gesamtnoten-Anzeige für einen Schüler.

    Hat der Schüler sowohl schriftliche als auch sonstige Noten, wird die
    gewichtete Gesamtnote als ``"3.67"`` formatiert. Liegt nur eine Kategorie
    vor und *allow_provisional* ist True, erscheint ein Klammerausdruck wie
    ``"(3)"``. Ohne Noten wird ``""`` zurückgegeben.

    Args:
        plan: Plan, aus dem gelesen wird.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        allow_provisional: Gibt vorläufige Noten in Klammern zurück, wenn
            nur eine Kategorie vorhanden ist.

    Returns:
        Formatierter Notenstring oder ``""``.
    """
    desk = plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return ""

    category_by_column: dict[str, str] = {
        col.column_id: col.category for col in plan.grade_columns
    }
    written_values: list[float] = []
    sonstige_values: list[float] = []

    for date_key in sorted(desk.documentation_entries.keys()):
        entry = desk.documentation_entries[date_key]
        for column_id, grade_value in entry.grades.items():
            category = category_by_column.get(column_id)
            if category == "schriftlich":
                written_values.append(float(grade_value))
            elif category == "sonstig":
                sonstige_values.append(float(grade_value))

    if not written_values and not sonstige_values:
        return ""

    written_avg = sum(written_values) / len(written_values) if written_values else None
    sonstige_avg = sum(sonstige_values) / len(sonstige_values) if sonstige_values else None

    if written_avg is not None and sonstige_avg is not None:
        written_rounded = _round_half_up_to_int(written_avg)
        sonstige_rounded = _round_half_up_to_int(sonstige_avg)
        total_weight = int(plan.written_weight_percent) + int(plan.sonstige_weight_percent)
        if total_weight <= 0:
            total_weight = 100
        overall = (
            written_rounded * int(plan.written_weight_percent)
            + sonstige_rounded * int(plan.sonstige_weight_percent)
        ) / total_weight
        return f"{_round_half_up_to_two_decimals(overall):.2f}"

    if not allow_provisional:
        return ""

    partial_value = written_avg if written_avg is not None else sonstige_avg
    assert partial_value is not None
    return f"({_round_half_up_to_int(partial_value)})"


def compute_grade_subtotal_display_for_student(
    plan: SeatingPlan,
    x: int,
    y: int,
    category: GradeCategory,
) -> str:
    """Berechnet den Durchschnitt einer Notenkategorie für einen Schüler.

    Args:
        plan: Plan, aus dem gelesen wird.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        category: ``"schriftlich"`` oder ``"sonstig"``.

    Returns:
        Gerundeter Durchschnitt als String (z.B. ``"3"``), oder ``""``.
    """
    desk = plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return ""

    clean_category = str(category).strip().lower()
    if clean_category not in {"schriftlich", "sonstig"}:
        return ""

    valid_column_ids = {
        item.column_id for item in plan.grade_columns if item.category == clean_category
    }
    if not valid_column_ids:
        return ""

    values: list[float] = []
    for date_key in sorted(desk.documentation_entries.keys()):
        entry = desk.documentation_entries[date_key]
        for column_id, grade_value in entry.grades.items():
            if column_id in valid_column_ids:
                values.append(float(grade_value))

    if not values:
        return ""

    return str(_round_half_up_to_int(sum(values) / len(values)))
