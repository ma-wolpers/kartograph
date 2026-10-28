"""Usecases für Noten-Operationen (Spalten, Einzelnoten, Gewichtung, Anzeige).

Noten werden über ``column_id`` (Spalte) und ``StudentId`` (Schüler) adressiert,
nicht mehr über (x, y)-Koordinaten. Sessions übernehmen die Rolle der alten
``documentation_entries``-Dicts.
"""

from __future__ import annotations

import uuid
from copy import deepcopy

from app.core.domain.grade_scale import scale_for
from app.core.domain.models_v4 import GradeCategory, GradeColumn, GradeWeighting, SeatingPlan
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

    ``grade=None`` entfernt die Note (``0`` ist bei Punkten ein gültiger Wert).
    Werte werden auf den Bereich der planweiten Notenskala geclampt
    (``plan.documentation.grade_scale``) — als letzte Sicherung, die GUI
    lehnt ungültige Eingaben bereits vorher ab. Die Session wird bei Bedarf angelegt.

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
        entry.grades[clean_col] = scale_for(next_plan.documentation.grade_scale).clamp(grade)

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
    lists = _value_lists_for_student(plan, student_id)
    return _overall_display(
        lists["schriftlich"], lists["sonstig"], plan.documentation.weighting, allow_provisional
    )


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

    return _subtotal_display(_value_lists_for_student(plan, student_id)[clean_cat])


def _value_lists_for_student(
    plan: SeatingPlan, student_id: StudentId
) -> dict[GradeCategory, list[float]]:
    """Sammelt alle Notenwerte eines Schülers je Kategorie.

    Einzelschüler-Gegenstück zu :func:`collect_grade_value_lists_by_student`;
    scannt nur den Eintrag dieses Schülers pro Session. Die Reihenfolge der
    Werte ist irrelevant (nur Summe/Anzahl zählen), daher kein ``sorted()``.

    Args:
        plan: Plan, aus dem gelesen wird.
        student_id: ID des Schülers.

    Returns:
        Dict mit beiden Kategorien als Schlüssel (ggf. leere Listen).
    """
    cat_by_col = {col.column_id: col.category for col in plan.documentation.grade_columns}
    lists: dict[GradeCategory, list[float]] = {"schriftlich": [], "sonstig": []}
    for session in plan.documentation.sessions:
        entry = session.entry_for(student_id)
        if entry is None:
            continue
        for col_id, grade_val in entry.grades.items():
            cat = cat_by_col.get(col_id)
            if cat in lists:
                lists[cat].append(float(grade_val))
    return lists


def _overall_display(
    written_vals: list[float],
    sonstige_vals: list[float],
    weighting: GradeWeighting,
    allow_provisional: bool,
) -> str:
    """Formatiert die Gesamtnote aus den Wertelisten beider Kategorien (SSOT der Formel).

    Beide Kategorie-Schnitte werden zuerst auf ganze Zahlen gerundet und
    dann gewichtet (``"3.67"``). Liegt nur eine Kategorie vor, entsteht eine
    vorläufige Note in Klammern (``"(3)"``) bzw. ``""`` ohne *allow_provisional*.
    Die Formel ist skalenneutral und gilt für Schulnoten wie Punkte.

    Args:
        written_vals: Alle schriftlichen Werte.
        sonstige_vals: Alle sonstigen Werte.
        weighting: Gewichtung des Plans; Summe 0 wird als 100 behandelt.
        allow_provisional: Vorläufige Noten in Klammern zurückgeben.
    """
    if not written_vals and not sonstige_vals:
        return ""
    if written_vals and sonstige_vals:
        w = _round_half_up_to_int(sum(written_vals) / len(written_vals))
        s = _round_half_up_to_int(sum(sonstige_vals) / len(sonstige_vals))
        total = weighting.written_percent + weighting.sonstige_percent
        if total <= 0:
            total = 100
        overall = (w * weighting.written_percent + s * weighting.sonstige_percent) / total
        return f"{_round_half_up_to_two_decimals(overall):.2f}"
    if not allow_provisional:
        return ""
    partial = written_vals or sonstige_vals
    return f"({_round_half_up_to_int(sum(partial) / len(partial))})"


def _subtotal_display(values: list[float]) -> str:
    """Formatiert den auf eine ganze Zahl gerundeten Schnitt einer Kategorie (``""`` ohne Werte).

    Args:
        values: Alle Werte einer Kategorie für einen Schüler.
    """
    return str(_round_half_up_to_int(sum(values) / len(values))) if values else ""


def compute_latest_grades_by_student(
    plan: SeatingPlan,
) -> dict[StudentId, dict[str, float]]:
    """Berechnet für alle Schüler gleichzeitig die zuletzt eingetragene Note je Spalte.

    Iteriert alle Sessions genau einmal in Datumsreihenfolge (statt, wie ein
    naiver pro-Schüler-x-Spalte-Aufruf es täte, für jede (Schüler, Spalte)-
    Kombination erneut zu sortieren und zu scannen). Spätere Sessions
    überschreiben frühere Werte für dieselbe (Schüler, Spalte)-Kombination,
    sodass am Ende automatisch der jeweils neueste Wert übrig bleibt.

    Args:
        plan: Plan, aus dem gelesen wird.

    Returns:
        Dict von StudentId → (Dict von column_id → neueste Note). Schüler/Spalten
        ohne Eintrag fehlen im Ergebnis (kein leerer Eintrag).
    """
    latest: dict[StudentId, dict[str, float]] = {}
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        for student_id, entry in session.entries.items():
            if not entry.grades:
                continue
            per_student = latest.setdefault(student_id, {})
            for col_id, grade_val in entry.grades.items():
                per_student[col_id] = float(grade_val)
    return latest


def collect_grade_value_lists_by_student(
    plan: SeatingPlan,
) -> dict[StudentId, dict[GradeCategory, list[float]]]:
    """Sammelt für alle Schüler gleichzeitig alle Notenwerte je Kategorie (ein Durchlauf).

    Gemeinsame Grundlage für :func:`compute_grade_display_by_student` und
    :func:`compute_grade_subtotal_display_by_student`. Wird ein Aufrufer
    (wie die Doku-Tabelle) mehrere dieser Funktionen für denselben Plan
    hintereinander aufrufen, sollte er dieses Ergebnis einmal berechnen und
    per ``value_lists=`` an alle weiterreichen — sonst scannt jeder einzelne
    Aufruf alle Sessions erneut, obwohl das Ergebnis identisch wäre.

    Args:
        plan: Plan, aus dem gelesen wird.

    Returns:
        Dict von StudentId → (Dict von Kategorie → Liste aller Notenwerte).
        Reihenfolge der Werte innerhalb einer Liste ist beliebig (Summe/
        Durchschnitt sind ordnungsunabhängig).
    """
    cat_by_col: dict[str, str] = {
        col.column_id: col.category for col in plan.documentation.grade_columns
    }
    result: dict[StudentId, dict[GradeCategory, list[float]]] = {}
    for session in plan.documentation.sessions:
        for student_id, entry in session.entries.items():
            if not entry.grades:
                continue
            for col_id, grade_val in entry.grades.items():
                cat = cat_by_col.get(col_id)
                if cat not in ("schriftlich", "sonstig"):
                    continue
                per_student = result.setdefault(student_id, {"schriftlich": [], "sonstig": []})
                per_student[cat].append(float(grade_val))
    return result


def compute_grade_display_by_student(
    plan: SeatingPlan,
    allow_provisional: bool = True,
    *,
    value_lists: dict[StudentId, dict[GradeCategory, list[float]]] | None = None,
) -> dict[StudentId, str]:
    """Wie :func:`compute_grade_display`, aber für alle benannten Schüler in einem Durchlauf.

    Args:
        plan: Plan, aus dem gelesen wird.
        allow_provisional: Vorläufige Noten in Klammern zurückgeben.
        value_lists: Optional vorberechnetes Ergebnis von
            :func:`collect_grade_value_lists_by_student`, um einen erneuten
            Sessions-Scan zu vermeiden, wenn der Aufrufer ohnehin auch
            :func:`compute_grade_subtotal_display_by_student` für denselben
            Plan aufruft (siehe dortige Docstring).

    Returns:
        Dict von StudentId → formatierter Notenstring (auch ``""`` als Wert
        für Schüler ohne Note, damit Aufrufer nicht zwischen "fehlt im Dict"
        und "keine Note" unterscheiden müssen).
    """
    value_lists = value_lists if value_lists is not None else collect_grade_value_lists_by_student(plan)
    weighting = plan.documentation.weighting
    results: dict[StudentId, str] = {}
    for student in plan.classroom.students:
        if not student.is_named():
            continue
        lists = value_lists.get(student.student_id)
        results[student.student_id] = _overall_display(
            lists["schriftlich"] if lists else [],
            lists["sonstig"] if lists else [],
            weighting,
            allow_provisional,
        )
    return results


def compute_grade_subtotal_display_by_student(
    plan: SeatingPlan,
    category: str,
    *,
    value_lists: dict[StudentId, dict[GradeCategory, list[float]]] | None = None,
) -> dict[StudentId, str]:
    """Wie :func:`compute_grade_subtotal_display`, aber für alle benannten Schüler in einem Durchlauf.

    Args:
        plan: Plan, aus dem gelesen wird.
        category: ``"schriftlich"`` oder ``"sonstig"``.
        value_lists: Optional vorberechnetes Ergebnis von
            :func:`collect_grade_value_lists_by_student` (siehe dortige
            Docstring) — vermeidet einen erneuten Sessions-Scan, wenn diese
            Funktion mehrfach (z. B. für beide Kategorien) oder zusammen mit
            :func:`compute_grade_display_by_student` für denselben Plan
            aufgerufen wird.

    Returns:
        Dict von StudentId → formatierter Durchschnitt (auch ``""`` als Wert
        für Schüler ohne passende Note).
    """
    clean_cat = str(category or "").strip().lower()
    results: dict[StudentId, str] = {}
    if clean_cat not in {"schriftlich", "sonstig"}:
        for student in plan.classroom.students:
            if student.is_named():
                results[student.student_id] = ""
        return results

    if value_lists is not None:
        resolved_lists = value_lists
    else:
        has_columns = any(col.category == clean_cat for col in plan.documentation.grade_columns)
        resolved_lists = collect_grade_value_lists_by_student(plan) if has_columns else {}
    value_lists = resolved_lists
    for student in plan.classroom.students:
        if not student.is_named():
            continue
        lists = value_lists.get(student.student_id)
        results[student.student_id] = _subtotal_display(lists[clean_cat] if lists else [])
    return results
