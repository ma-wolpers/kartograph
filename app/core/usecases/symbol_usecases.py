"""Usecases für Symbol-Operationen auf Schülertischen.

Unterschieden werden *diagnostische* Symbole (direkt am Tisch, z.B. „Laptop")
und *Dokumentationssymbole* (datumgebunden, z.B. „Abwesend").
"""

from __future__ import annotations

from copy import deepcopy

from app.core.domain.models import DocumentationEntry, SeatingPlan
from app.core.usecases._shared import _normalize_doc_date
from app.core.usecases.date_usecases import ensure_documentation_date


def toggle_symbol(plan: SeatingPlan, x: int, y: int, symbol: str) -> SeatingPlan:
    """Wechselt den Zähler eines diagnostischen Symbols am Tisch (x, y).

    Der Zähler läuft zyklisch 0 → 1 → 2 → 3 → 0. Bei 0 wird der Eintrag entfernt.

    Args:
        plan: Ausgangsplan.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        symbol: Name des Symbols (z.B. ``"Laptop"``).

    Returns:
        Neuer Plan mit dem aktualisierten Symbolzähler.
    """
    next_plan = deepcopy(plan)
    desk = next_plan.desk_at(x, y)
    if not desk or desk.desk_type != "student":
        return next_plan
    current_count = int(desk.symbols.get(symbol, 0))
    next_count = (current_count + 1) % 4
    if next_count == 0:
        desk.symbols.pop(symbol, None)
    else:
        desk.symbols[symbol] = next_count
    return next_plan


def set_documentation_symbol(
    plan: SeatingPlan,
    x: int,
    y: int,
    symbol: str,
    strength: int,
    doc_date: str | None = None,
) -> SeatingPlan:
    """Setzt die Stärke eines Dokumentationssymbols für ein bestimmtes Datum.

    Stärke 0 entfernt den Eintrag. Stärken außerhalb von 1–3 werden
    auf diesen Bereich geclampt. Das Datum wird bei Bedarf im Plan angelegt.

    Args:
        plan: Ausgangsplan.
        x: Spalte des Tisches.
        y: Zeile des Tisches.
        symbol: Symbolname.
        strength: Neue Stärke (0 = entfernen, 1–3 = setzen).
        doc_date: Zieldatum; None ergibt das heutige Datum.

    Returns:
        Neuer Plan mit dem aktualisierten Dokumentationseintrag.
    """
    clean_symbol = str(symbol or "").strip()
    if not clean_symbol:
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

    try:
        parsed_strength = int(strength)
    except (TypeError, ValueError):
        parsed_strength = 0
    if parsed_strength <= 0:
        entry.symbols.pop(clean_symbol, None)
    else:
        entry.symbols[clean_symbol] = max(1, min(3, parsed_strength))

    if not entry.has_content():
        desk.documentation_entries.pop(date_key, None)
    return next_plan


def summarize_latest_symbols_for_student(plan: SeatingPlan, x: int, y: int) -> dict[str, int]:
    """Gibt die jeweils neuesten Symbolstärken eines Schülers zurück.

    Iteriert alle Dokumentationsdaten chronologisch; spätere Einträge
    überschreiben frühere Werte für dasselbe Symbol.

    Args:
        plan: Plan, aus dem gelesen wird.
        x: Spalte des Tisches.
        y: Zeile des Tisches.

    Returns:
        Dict von Symbolname → neueste Stärke (1–3). Leer, wenn keine
        Einträge vorliegen oder der Schüler keinen Namen hat.
    """
    desk = plan.desk_at(x, y)
    if not desk or not desk.is_named_student():
        return {}

    summary: dict[str, int] = {}
    for date_key in sorted(desk.documentation_entries.keys()):
        entry = desk.documentation_entries[date_key]
        for symbol, strength in entry.symbols.items():
            summary[symbol] = strength
    return summary
