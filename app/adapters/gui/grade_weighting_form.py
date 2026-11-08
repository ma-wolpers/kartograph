"""Formularlogik des Gewichtungsdialogs (reines Python, kein Tk, separat testbar).

Der Dialog (``_mixin_grade_dialogs.py``) hält nur Widgets und StringVars;
alles, was aus den eingegebenen Texten folgt -- Gültigkeit, Fehlermeldung,
nominale Anteile, die automatische Ergänzung auf 100 % -- steht hier und
nutzt ausschließlich die Regeln aus ``app/core/domain/grade_weighting.py``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.core.domain.grade_weighting import effective_column_shares, parse_factor, parse_percent
from app.core.domain.models_v4 import GradeColumn, GradeWeighting

FULL_PERCENT = 100


@dataclass(frozen=True)
class WeightingFormResult:
    """Gültiger Formularstand: fertig für ``UpdateGradeWeightingIntent`` plus Anteile für die Anzeige.

    Attributes:
        written_percent: Anteil schriftlich.
        sonstige_percent: Anteil sonstig.
        column_weights: ``(column_id, Faktor)`` in Spaltenreihenfolge.
        shares: ``column_id → nominaler Anteil an der Gesamtnote`` (0–1).
    """

    written_percent: int
    sonstige_percent: int
    column_weights: tuple[tuple[str, float], ...]
    shares: dict[str, float]


def evaluate_weighting_form(
    columns: Sequence[GradeColumn], written_text: str, sonstige_text: str, factor_texts: Mapping[str, str]
) -> WeightingFormResult:
    """Prüft alle Eingaben des Gewichtungsdialogs und berechnet die Live-Anteile.

    Args:
        columns: Notenspalten des Plans (Reihenfolge = Anzeige).
        written_text: Eingabe "Schriftlich %".
        sonstige_text: Eingabe "Sonstig %".
        factor_texts: ``column_id → Faktor-Eingabe``.

    Raises:
        ValueError: Mit einer anzeigefertigen Meldung zur ersten ungültigen Eingabe.
    """
    try:
        written = parse_percent(written_text)
        sonstige = parse_percent(sonstige_text)
    except ValueError:
        raise ValueError("Prozentanteile: bitte ganze Zahlen ab 0 eingeben.") from None
    if written + sonstige <= 0:
        raise ValueError("Mindestens ein Prozentanteil muss größer als 0 sein.")
    weights: dict[str, float] = {}
    for column in columns:
        try:
            weights[column.column_id] = parse_factor(factor_texts.get(column.column_id, ""))
        except ValueError:
            raise ValueError(f"Faktor bei „{column.title}“: bitte eine Zahl ab 0 eingeben (z. B. 2 oder 0,5).") from None
    preview = [dataclasses.replace(column, weight=weights[column.column_id]) for column in columns]
    shares = effective_column_shares(preview, GradeWeighting(written, sonstige))
    return WeightingFormResult(written, sonstige, tuple(weights.items()), shares)


def complement_percent(text: str) -> str | None:
    """Ergänzung auf 100 % für das jeweils andere Prozentfeld (``"60" → "40"``).

    Args:
        text: Eingabe in einem der beiden Prozentfelder.

    Returns:
        Text für das andere Feld oder ``None``, wenn die Eingabe (noch) keine
        ganze Zahl zwischen 0 und 100 ist -- dann bleibt das andere Feld unberührt.
    """
    try:
        value = parse_percent(text)
    except ValueError:
        return None
    return str(FULL_PERCENT - value) if value <= FULL_PERCENT else None


def format_share(share: float) -> str:
    """Formatiert einen nominalen Anteil für die Anteilsspalte (``0.25 → "25.0 %"``).

    Args:
        share: Anteil zwischen 0 und 1.
    """
    return f"{share * FULL_PERCENT:.1f} %"
