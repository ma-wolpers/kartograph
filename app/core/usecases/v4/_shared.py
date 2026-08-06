"""Interne Hilfsfunktionen für die v4-Usecase-Schicht."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def _today_iso() -> str:
    return date.today().isoformat()


def _normalize_doc_date(value: str | None) -> str:
    clean = str(value or "").strip()
    return clean or _today_iso()


def _round_half_up_to_int(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _round_half_up_to_two_decimals(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
