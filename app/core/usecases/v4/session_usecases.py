"""Usecases für Session-Operationen (Anlegen, Umbenennen).

Sessions ersetzen das frühere ``documentation_dates``-Konzept. Statt einer
globalen Datumsliste gibt es eine geordnete Liste von ``Session``-Objekten,
die alle Einträge für einen Unterrichtstag kapseln.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models_v4 import SeatingPlan, Session, SessionEntry
from app.core.domain.student_id import StudentId
from app.core.usecases.v4._shared import _normalize_doc_date


def ensure_session(plan: SeatingPlan, date: str | None = None) -> SeatingPlan:
    """Stellt sicher, dass eine Session für *date* im Plan vorhanden ist.

    Ist die Session bereits vorhanden, wird der Plan unverändert zurückgegeben.
    Fehlt *date* oder ist None, wird das heutige Datum verwendet.

    Args:
        plan: Ausgangsplan.
        date: Datum im Format YYYY-MM-DD (optional).

    Returns:
        Neuer Plan mit der sichergestellten Session.
    """
    date_key = _normalize_doc_date(date)
    if plan.documentation.session_for_date(date_key) is not None:
        return deepcopy(plan)
    next_plan = deepcopy(plan)
    next_plan.documentation.sessions.append(Session(date=date_key))
    next_plan.documentation.sessions.sort(key=lambda s: s.date)
    return next_plan


def rename_session_date(plan: SeatingPlan, old_date: str, new_date: str) -> SeatingPlan:
    """Benennt eine Session um und migriert alle Einträge auf das neue Datum.

    Existiert unter *new_date* bereits eine Session, werden Symbole, Noten
    und Notizen aus *old_date* zusammengeführt (bestehende Werte bleiben).

    Args:
        plan: Ausgangsplan.
        old_date: Bisheriger Datumstring.
        new_date: Neuer Datumstring; leer/None ergibt das heutige Datum.

    Returns:
        Neuer Plan mit umbenannter Session.
    """
    clean_old = str(old_date or "").strip()
    clean_new = _normalize_doc_date(new_date)
    if not clean_old or clean_old == clean_new:
        return deepcopy(plan)

    next_plan = deepcopy(plan)
    old_session = next_plan.documentation.session_for_date(clean_old)
    if old_session is None:
        return next_plan

    new_session = next_plan.documentation.session_for_date(clean_new)
    if new_session is None:
        old_session.date = clean_new
        next_plan.documentation.sessions.sort(key=lambda s: s.date)
        return next_plan

    # Merge old into existing new
    for student_id, old_entry in old_session.entries.items():
        existing = new_session.entries.get(student_id)
        if existing is None:
            new_session.entries[student_id] = deepcopy(old_entry)
        else:
            existing.symbols.update(old_entry.symbols)
            existing.grades.update(old_entry.grades)
            if old_entry.note.strip() and not existing.note.strip():
                existing.note = old_entry.note.strip()

    next_plan.documentation.sessions = [
        s for s in next_plan.documentation.sessions if s.date != clean_old
    ]
    next_plan.documentation.sessions.sort(key=lambda s: s.date)
    return next_plan
