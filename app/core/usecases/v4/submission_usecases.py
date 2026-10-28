"""Usecases für "Abgaben zählen": Abgabestatus pro Person und Doku-Tag setzen.

Alle Schreibzugriffe laufen über ``apply_symbol_strength_in_place`` aus
``symbol_usecases`` (eine Regel für Setzen/Löschen/Aufräumen) auf genau
einer Plankopie pro Aktion. Welche Symbolnamen zu den Status gehören,
bestimmt der Aufrufer über ``submission_symbol_names`` (Codepoint-Auflösung
aus dem Katalog); diese Usecases kennen keinen Anzeigetext.
"""

from __future__ import annotations

from typing import Iterable, Literal, Mapping

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.student_id import StudentId
from app.core.domain.submission_status import SubmissionStatus
from app.core.usecases.v4._shared import _normalize_doc_date
from app.core.usecases.v4.session_usecases import ensure_session
from app.core.usecases.v4.symbol_usecases import apply_symbol_strength_in_place

SubmissionMode = Literal["replace", "complement"]
"""``replace``: alte X/✓/◐ des Tages zuerst entfernen; ``complement``: nur Unbewertete ergänzen."""


def rated_statuses(
    plan: SeatingPlan, date: str, names: Mapping[SubmissionStatus, str]
) -> dict[StudentId, SubmissionStatus]:
    """Gibt den eingetragenen Abgabestatus aller Personen an *date* zurück.

    Grundlage für die Rückfrage "ersetzen/ergänzen", für die Vorbelegung des
    Viewers und für "nur Unbewertete". Hätte eine Person (manuell gesetzt)
    mehrere der drei Symbole, gilt der beste Status.

    Args:
        plan: Plan, aus dem gelesen wird.
        date: Doku-Tag (YYYY-MM-DD).
        names: Status → Symbolname.
    """
    session = plan.documentation.session_for_date(_normalize_doc_date(date))
    if session is None:
        return {}
    result: dict[StudentId, SubmissionStatus] = {}
    for student_id, entry in session.entries.items():
        for status in SubmissionStatus:  # Reihenfolge: vollständig vor lückenhaft vor fehlend
            if entry.symbols.get(names[status]):
                result[student_id] = status
                break
    return result


def set_submission_status(
    plan: SeatingPlan,
    student_id: StudentId,
    date: str,
    status: SubmissionStatus | None,
    names: Mapping[SubmissionStatus, str],
) -> SeatingPlan:
    """Setzt genau einen Abgabestatus (Stärke 1) und entfernt die beiden anderen.

    Args:
        plan: Ausgangsplan.
        student_id: Betroffene Person.
        date: Doku-Tag (YYYY-MM-DD).
        status: Neuer Status; ``None`` entfernt alle drei.
        names: Status → Symbolname.

    Returns:
        Neuer Plan.
    """
    next_plan = ensure_session(plan, date)
    for candidate in SubmissionStatus:
        apply_symbol_strength_in_place(next_plan, student_id, date, names[candidate], 1 if candidate is status else 0)
    return next_plan


def apply_missing_submissions(
    plan: SeatingPlan,
    date: str,
    submitted: Iterable[StudentId],
    names: Mapping[SubmissionStatus, str],
    *,
    absent_symbol: str,
    mark_absent: bool,
    mode: SubmissionMode,
) -> SeatingPlan:
    """Setzt X für alle benannten Personen ohne Abgabe an *date*.

    Args:
        plan: Ausgangsplan.
        date: Doku-Tag (YYYY-MM-DD).
        submitted: Personen mit (zugeordnetem) Abgabeordner.
        names: Status → Symbolname.
        absent_symbol: Gespeicherter Name von ∅ "Abwesend".
        mark_absent: Auch an diesem Tag Abwesende ohne Abgabe mit X markieren.
        mode: ``replace`` entfernt vorher X/✓/◐ aller Personen dieses Tages;
            ``complement`` lässt bereits Bewertete unverändert.

    Returns:
        Neuer Plan (ein Undo-Schritt für den ganzen Lauf).
    """
    next_plan = ensure_session(plan, date)
    session = next_plan.documentation.session_for_date(_normalize_doc_date(date))
    already_rated = set(rated_statuses(next_plan, date, names)) if mode == "complement" else set()
    submitted_ids = set(submitted)
    for student in next_plan.classroom.students:
        if not student.is_named() or student.student_id in already_rated:
            continue
        if mode == "replace":
            for status in SubmissionStatus:
                apply_symbol_strength_in_place(next_plan, student.student_id, date, names[status], 0)
        if student.student_id in submitted_ids:
            continue
        entry = session.entry_for(student.student_id) if session else None
        if not mark_absent and entry is not None and entry.symbols.get(absent_symbol):
            continue
        apply_symbol_strength_in_place(next_plan, student.student_id, date, names[SubmissionStatus.MISSING], 1)
    return next_plan
