"""Usecases für Dokumentationsdaten (Anlegen, Umbenennen).

Dokumentationsdaten sind Schlüssel wie ``"2025-03-14"``, unter denen
Beobachtungen pro Schüler gespeichert werden.
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import SeatingPlan
from app.core.usecases._shared import _normalize_doc_date


def ensure_documentation_date(plan: SeatingPlan, value: str | None = None) -> SeatingPlan:
    """Stellt sicher, dass *value* als Dokumentationsdatum im Plan vorhanden ist.

    Ist das Datum bereits eingetragen, wird der Plan unverändert zurückgegeben.
    Fehlt *value* oder ist None, wird das heutige Datum verwendet.

    Args:
        plan: Ausgangsplan.
        value: Datumstring im Format YYYY-MM-DD (optional).

    Returns:
        Neuer Plan mit dem sichergestellten Datum.
    """
    next_plan = deepcopy(plan)
    date_key = _normalize_doc_date(value)
    if date_key not in next_plan.documentation_dates:
        next_plan.documentation_dates.append(date_key)
        next_plan.documentation_dates.sort()
    return next_plan


def rename_documentation_date(plan: SeatingPlan, old_date: str, new_date: str) -> SeatingPlan:
    """Benennt ein Dokumentationsdatum um und migriert alle zugehörigen Einträge.

    Existieren unter *new_date* bereits Einträge, werden Symbole und Noten
    aus *old_date* zusammengeführt (bestehende Werte bleiben erhalten).

    Args:
        plan: Ausgangsplan.
        old_date: Bisheriger Datumstring.
        new_date: Neuer Datumstring; leer/None ergibt das heutige Datum.

    Returns:
        Neuer Plan mit umbenanntem Datum.
    """
    clean_old = str(old_date or "").strip()
    clean_new = _normalize_doc_date(new_date)
    if not clean_old:
        return deepcopy(plan)

    next_plan = deepcopy(plan)
    for desk in next_plan.desks:
        if not desk.is_named_student():
            continue
        old_entry = desk.documentation_entries.get(clean_old)
        if old_entry is None:
            continue
        existing_new = desk.documentation_entries.get(clean_new)
        if existing_new is None:
            desk.documentation_entries[clean_new] = old_entry
        else:
            existing_new.symbols.update(old_entry.symbols)
            existing_new.grades.update(old_entry.grades)
            if old_entry.note.strip() and not existing_new.note.strip():
                existing_new.note = old_entry.note.strip()
        desk.documentation_entries.pop(clean_old, None)

    next_plan.documentation_dates = [d for d in next_plan.documentation_dates if d != clean_old]
    if clean_new not in next_plan.documentation_dates:
        next_plan.documentation_dates.append(clean_new)
    next_plan.documentation_dates.sort()
    return next_plan
