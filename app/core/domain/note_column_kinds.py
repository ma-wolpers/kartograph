"""Zeilentypen eigener Notizspalten (SSOT, reines Python).

Eine eigene Notizspalte hat einen Titel und einen Typ (Wunsch der Nutzerin
2026-11-17: "Text, Zahl, Datum, ..."). Je Typ steht hier einmal: Beschriftung,
Einlesen einer Eingabe in die gespeicherte Form, Anzeige und Sortierwert.
"Ja/Nein" ist bewusst *kein* Typ dieser Registry: Ja/Nein-Spalten sind
Farbspalten (``flag_columns``) und speichern in ``color_tags``.

Gespeichert wird ein kanonischer Text je Person und Spalte
(``DiagnosticProfile.note_values``): Text getrimmt, Zahl wie
``format_plain_decimal`` (Punkt, ohne überflüssige Nullen), Datum ISO
``JJJJ-MM-TT``. Eine leere Eingabe löscht den Wert.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.core.domain.grade_scale import format_plain_decimal, parse_decimal_input

NoteValueKind = Literal["text", "number", "date"]

_GERMAN_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})$")


def parse_date_input(text: str) -> str:
    """Liest ein Datum aus einer Nutzereingabe und gibt es als ISO ``JJJJ-MM-TT`` zurück.

    Akzeptiert ``TT.MM.JJJJ``, ``T.M.JJJJ``, ``TT.MM.JJ`` (→ 20JJ) und ISO ``JJJJ-MM-TT``.

    Args:
        text: Rohe Eingabe, z. B. ``"3.11.2026"``.

    Raises:
        ValueError: Kein gültiges Datum.

    Examples:
        ``"03.11.26" → "2026-11-03"``, ``"2026-11-03" → "2026-11-03"``.
    """
    raw = str(text).strip()
    match = _GERMAN_DATE.match(raw)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return date(year + 2000 if year < 100 else year, month, day).isoformat()
    return date.fromisoformat(raw).isoformat()


def format_date_value(stored: str) -> str:
    """Zeigt ein gespeichertes ISO-Datum als ``TT.MM.JJJJ`` (Unlesbares unverändert).

    Args:
        stored: Gespeicherter Wert, z. B. ``"2026-11-03"``.
    """
    try:
        return date.fromisoformat(stored).strftime("%d.%m.%Y")
    except ValueError:
        return stored


def _number_sort(stored: str) -> tuple:
    """Sortierwert einer Zahl: Zahlen vor Unlesbarem (``(0, wert)`` bzw. ``(1, text)``)."""
    try:
        return (0, parse_decimal_input(stored))
    except ValueError:
        return (1, stored.lower())


@dataclass(frozen=True)
class NoteKindSpec:
    """Ein Zeilentyp.

    Attributes:
        key: Gespeicherter Typschlüssel (``"text"``, ``"number"``, ``"date"``).
        label: Beschriftung im Dialog.
        parse: Eingabe → gespeicherte Form (wirft ``ValueError`` bei ungültiger Eingabe).
        display: gespeicherte Form → Zelltext.
        sort_value: gespeicherte Form → vergleichbares Tupel (leere Zellen sortiert
            die Tabelle selbst ans Ende, s. ``docs_table_model``).
    """

    key: NoteValueKind
    label: str
    parse: Callable[[str], str]
    display: Callable[[str], str]
    sort_value: Callable[[str], tuple]


NOTE_VALUE_KINDS: dict[str, NoteKindSpec] = {
    "text": NoteKindSpec("text", "Text", lambda text: str(text).strip(), lambda stored: stored,
                         lambda stored: (0, stored.lower())),
    "number": NoteKindSpec("number", "Zahl", lambda text: format_plain_decimal(parse_decimal_input(text)),
                           lambda stored: stored, _number_sort),
    "date": NoteKindSpec("date", "Datum", parse_date_input, format_date_value, lambda stored: (0, stored)),
}
"""Alle Zeilentypen in Dialogreihenfolge; einzige Quelle für Typschlüssel und -beschriftungen."""


def parse_note_value(kind: str, text: str) -> str:
    """Liest *text* für eine Spalte vom Typ *kind*; leere Eingabe ergibt ``""`` (= Wert löschen).

    Args:
        kind: Typschlüssel aus ``NOTE_VALUE_KINDS``.
        text: Rohe Eingabe.

    Raises:
        ValueError: Ungültige Eingabe für den Typ (z. B. "abc" in einer Zahlspalte).
    """
    if not str(text).strip():
        return ""
    return NOTE_VALUE_KINDS[kind].parse(text)
