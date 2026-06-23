"""Interne Hilfsfunktionen für die Usecase-Schicht.

Dieses Modul ist privat; außerhalb von ``app.core.usecases`` sollte
nichts daraus importiert werden.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def _today_iso() -> str:
    """Gibt das heutige Datum als ISO-8601-String zurück (YYYY-MM-DD)."""
    return date.today().isoformat()


def _normalize_doc_date(value: str | None) -> str:
    """Bereinigt einen Dokumentationsdatumsstring.

    Gibt *value* getrimmt zurück, oder das heutige Datum wenn *value*
    leer oder None ist.
    """
    clean = str(value or "").strip()
    return clean or _today_iso()


def _round_half_up_to_int(value: float) -> int:
    """Rundet *value* kaufmännisch auf eine ganze Zahl."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_half_up_to_two_decimals(value: float) -> float:
    """Rundet *value* kaufmännisch auf zwei Nachkommastellen."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
