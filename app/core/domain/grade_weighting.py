"""Gewichtungsregeln der Notenberechnung (SSOT, rein, ohne GUI).

Zwei Ebenen:

1. **Spaltenfaktoren** innerhalb einer Kategorie (``GradeColumn.weight``,
   Standard 1): ``2`` zählt doppelt, ``0.5`` halb, ``0`` gar nicht.
2. **Kategorie-Prozente** schriftlich gegen sonstig (``GradeWeighting``).

Hier liegen alle Regeln dazu genau einmal: Lesen und Bereinigen von
Faktoren, Formatierung, die 50/50-Rückfallregel, die Zuordnung der Prozente
zu den Kategorien, der gewichtete Mittelwert und die nominalen Anteile für
den Gewichtungsdialog. Die Standardwerte stehen als Modell-Defaults in
``models_v4`` (Importrichtung Modell → Regeln, wie bei ``grade_scale``).
Modell, Usecases, Deserializer, Dialog und Spaltenkopf rufen nur diese
Funktionen auf.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from app.core.domain.grade_scale import format_plain_decimal, parse_decimal_input
from app.core.domain.models_v4 import (
    DEFAULT_CATEGORY_PERCENT,
    DEFAULT_COLUMN_WEIGHT,
    GradeCategory,
    GradeColumn,
    GradeWeighting,
)


def normalize_factor(raw: object) -> float:
    """Bereinigt einen gespeicherten oder übergebenen Faktor (misstrauisch, wirft nie).

    Nicht lesbare oder nicht endliche Werte ergeben den Standardfaktor,
    negative Werte werden auf 0 begrenzt.

    Args:
        raw: Beliebiger Rohwert (z. B. aus der Plandatei).

    Examples:
        ``"2" → 2.0``, ``None → 1.0``, ``-3 → 0.0``, ``"nan" → 1.0``.
    """
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_COLUMN_WEIGHT
    if not math.isfinite(value):
        return DEFAULT_COLUMN_WEIGHT
    return max(0.0, value)


def parse_factor(text: str) -> float:
    """Liest einen Faktor aus einer Nutzereingabe (streng, für Dialoge).

    Args:
        text: Rohe Eingabe, Komma oder Punkt (``"0,5"``, ``"2"``).

    Raises:
        ValueError: Leer, keine Zahl, nicht endlich oder negativ.
    """
    value = parse_decimal_input(text)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"Ungültiger Faktor: {text!r}")
    return value


def parse_percent(text: str) -> int:
    """Liest einen Kategorie-Prozentanteil aus einer Nutzereingabe (streng, für Dialoge).

    Args:
        text: Rohe Eingabe, ganze Zahl ≥ 0 (``"60"``).

    Raises:
        ValueError: Leer, keine ganze Zahl oder negativ.
    """
    value = int(str(text).strip())
    if value < 0:
        raise ValueError(f"Ungültiger Prozentanteil: {text!r}")
    return value


def format_factor(value: float) -> str:
    """Formatiert einen Faktor für Spaltenkopf und Dialog (``2.0 → "2"``, ``0.5 → "0.5"``).

    Args:
        value: Faktor.
    """
    return format_plain_decimal(value)


def normalized_category_percents(written_percent: object, sonstige_percent: object) -> tuple[int, int]:
    """Bereinigt die Kategorie-Prozente schriftlich/sonstig (SSOT der 50/50-Regel).

    Nicht lesbare Werte ergeben den Standard, negative werden auf 0 begrenzt.
    Sind danach beide 0, gilt 50/50 -- sonst gäbe es keinen Nenner.

    Args:
        written_percent: Rohanteil schriftlich.
        sonstige_percent: Rohanteil sonstig.

    Returns:
        ``(schriftlich, sonstig)`` mit Summe > 0.
    """
    written = max(0, _coerce_int(written_percent))
    sonstige = max(0, _coerce_int(sonstige_percent))
    if written + sonstige <= 0:
        return DEFAULT_CATEGORY_PERCENT, DEFAULT_CATEGORY_PERCENT
    return written, sonstige


def category_percents(weighting: GradeWeighting) -> dict[GradeCategory, int]:
    """Bereinigte Prozentanteile je Kategorie (einzige Zuordnung Feld → Kategorie).

    Args:
        weighting: Kategorie-Prozente des Plans.

    Returns:
        ``{"schriftlich": …, "sonstig": …}`` mit Summe > 0.
    """
    written, sonstige = normalized_category_percents(weighting.written_percent, weighting.sonstige_percent)
    return {"schriftlich": written, "sonstig": sonstige}


def weighted_mean(pairs: Iterable[tuple[float, float]]) -> float | None:
    """Gewichteter Mittelwert aus ``(Wert, Faktor)``-Paaren.

    Fehlt einer Person eine Note in einer Spalte, steht das Paar einfach
    nicht in *pairs*: Das Gewicht verteilt sich dann auf die vorhandenen Noten.

    Args:
        pairs: ``(Notenwert, Faktor)``.

    Returns:
        Mittelwert oder ``None``, wenn die Faktorsumme 0 ist (keine zählende Note).
    """
    total_weight = 0.0
    total = 0.0
    for value, weight in pairs:
        total_weight += weight
        total += value * weight
    if total_weight <= 0:
        return None
    return total / total_weight


def effective_column_shares(columns: Sequence[GradeColumn], weighting: GradeWeighting) -> dict[str, float]:
    """Nominaler Anteil jeder Spalte an der Gesamtnote (0–1), für die Live-Anzeige im Dialog.

    Annahme: Jede Person hat in jeder Spalte eine Note; die Rundung des
    Kategorie-Schnitts bleibt außen vor. Anteil = Faktor / Faktorsumme der
    Kategorie × Kategorie-Prozent. Spalten einer Kategorie mit Faktorsumme 0
    erhalten 0.

    Args:
        columns: Notenspalten (mit ``category`` und ``weight``).
        weighting: Kategorie-Prozente des Plans.

    Returns:
        ``column_id → Anteil``.
    """
    percents = category_percents(weighting)
    total_percent = sum(percents.values())
    category_share = {category: percent / total_percent for category, percent in percents.items()}
    weight_sums: dict[str, float] = {}
    for column in columns:
        weight_sums[column.category] = weight_sums.get(column.category, 0.0) + column.weight
    shares: dict[str, float] = {}
    for column in columns:
        weight_sum = weight_sums.get(column.category, 0.0)
        share = category_share.get(column.category, 0.0)
        shares[column.column_id] = share * column.weight / weight_sum if weight_sum > 0 else 0.0
    return shares


def _coerce_int(raw: object) -> int:
    """Wandelt *raw* in ``int``; nicht lesbare Werte ergeben den Standard-Prozentanteil.

    Args:
        raw: Beliebiger Rohwert.
    """
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_CATEGORY_PERCENT
