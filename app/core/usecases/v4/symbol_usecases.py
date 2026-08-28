"""Usecases für Symbol-Operationen (diagnostisch + dokumentationsgebunden).

Diagnostische Symbole (z.B. „Laptop") beschreiben den Schüler dauerhaft.
Dokumentationssymbole (z.B. „Beteiligung") sind sessions-/datumsgebunden.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import SeatingPlan
from app.core.domain.student_id import StudentId
from app.core.usecases.v4._shared import _normalize_doc_date
from app.core.usecases.v4.session_usecases import ensure_session


def toggle_diagnostic_symbol(
    plan: SeatingPlan, student_id: StudentId, symbol: str
) -> SeatingPlan:
    """Wechselt den Zähler eines diagnostischen Symbols zyklisch (0→1→2→3→0).

    Bei Zähler 0 wird der Eintrag entfernt.

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        symbol: Symbolname (z.B. ``"Laptop"``).

    Returns:
        Neuer Plan mit dem aktualisierten Symbolzähler.
    """
    next_plan = deepcopy(plan)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None:
        return next_plan
    current = int(student.diagnostic.symbols.get(symbol, 0))
    next_count = (current + 1) % 4
    if next_count == 0:
        student.diagnostic.symbols.pop(symbol, None)
    else:
        student.diagnostic.symbols[symbol] = next_count
    return next_plan


def record_symbol(
    plan: SeatingPlan,
    student_id: StudentId,
    date: str | None,
    symbol: str,
    strength: int,
) -> SeatingPlan:
    """Setzt oder entfernt ein Dokumentationssymbol für ein bestimmtes Datum.

    Stärke 0 entfernt den Eintrag. Stärken außerhalb von 1–3 werden geclampt.
    Die Session wird bei Bedarf angelegt.

    Args:
        plan: Ausgangsplan.
        student_id: ID des betroffenen Schülers.
        date: Datum im Format YYYY-MM-DD (None = heute).
        symbol: Symbolname.
        strength: Neue Stärke (0 = löschen, 1–3 = setzen).

    Returns:
        Neuer Plan mit dem aktualisierten Dokumentationseintrag.
    """
    clean_symbol = str(symbol or "").strip()
    if not clean_symbol:
        return deepcopy(plan)

    next_plan = ensure_session(plan, date)
    student = next_plan.classroom.student_by_id(student_id)
    if student is None or not student.is_named():
        return next_plan

    date_key = _normalize_doc_date(date)
    session = next_plan.documentation.session_for_date(date_key)
    if session is None:
        return next_plan

    try:
        parsed = int(strength)
    except (TypeError, ValueError):
        parsed = 0

    entry = session.ensure_entry(student_id)
    if parsed <= 0:
        entry.symbols.pop(clean_symbol, None)
    else:
        entry.symbols[clean_symbol] = max(1, min(3, parsed))

    if not entry.has_content():
        session.entries.pop(student_id, None)

    return next_plan


def summarize_latest_symbols(plan: SeatingPlan, student_id: StudentId) -> dict[str, int]:
    """Gibt die jeweils neuesten Symbol-Stärken eines Schülers zurück.

    Iteriert alle Sessions chronologisch; spätere Einträge überschreiben
    frühere Werte für dasselbe Symbol.

    Args:
        plan: Plan, aus dem gelesen wird.
        student_id: ID des Schülers.

    Returns:
        Dict von Symbolname → neueste Stärke (1–3). Leer, wenn keine Einträge.
    """
    student = plan.classroom.student_by_id(student_id)
    if student is None or not student.is_named():
        return {}

    summary: dict[str, int] = {}
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        entry = session.entry_for(student_id)
        if entry is not None:
            summary.update(entry.symbols)
    return summary


def summarize_latest_symbols_by_student(plan: SeatingPlan) -> dict[StudentId, dict[str, int]]:
    """Berechnet für alle Schüler gleichzeitig die jeweils neuesten Symbol-Stärken.

    Iteriert alle Sessions genau einmal in Datumsreihenfolge, statt (wie ein
    naiver pro-Schüler-Aufruf von :func:`summarize_latest_symbols` es täte)
    für jeden Schüler erneut zu sortieren und zu scannen. Für Hot Paths, die
    die Zusammenfassung mehrerer/aller Schüler gleichzeitig brauchen
    (Doku-Tabelle, Raster-Redraw) — Einzelabfragen bleiben bei
    :func:`summarize_latest_symbols`.

    Args:
        plan: Plan, aus dem gelesen wird.

    Returns:
        Dict von StudentId → (Dict von Symbolname → neueste Stärke). Schüler
        ohne jegliche Symbol-Einträge fehlen im Ergebnis.
    """
    summaries: dict[StudentId, dict[str, int]] = {}
    for session in sorted(plan.documentation.sessions, key=lambda s: s.date):
        for student_id, entry in session.entries.items():
            if not entry.symbols:
                continue
            summaries.setdefault(student_id, {}).update(entry.symbols)
    return summaries
