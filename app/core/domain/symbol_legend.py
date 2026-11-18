"""Reihenfolge und Stufen gesetzter Symbole — gemeinsame Grundlage für Raster, Detailbereich und PDF.

Einzige Stelle, die festlegt, in welcher Reihenfolge die Symbole einer Person
erscheinen und mit welcher Stufe. GUI und PDF-Export rufen
:func:`ordered_symbol_counts` auf, statt die Schleife jeweils selbst zu bauen.
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping, Sequence

from app.core.domain.symbol_catalog import symbol_level


def ordered_symbol_keys(catalog_keys: Sequence[str], keys: Iterable[str]) -> list[str]:
    """Ordnet *keys* in Anzeigereihenfolge: Katalogsymbole zuerst, übrige alphabetisch dahinter.

    Die übrigen Schlüssel (eigene oder gelöschte Symbole) werden ohne Beachtung
    der Groß-/Kleinschreibung sortiert.

    Args:
        catalog_keys: Schlüssel des programmweiten Katalogs in Katalogreihenfolge.
        keys: Zu ordnende Schlüssel (z. B. die gesetzten Symbole einer Person).
    """
    present = set(keys)
    known = set(catalog_keys)
    ordered = [key for key in catalog_keys if key in present]
    return ordered + sorted((key for key in present if key not in known), key=str.lower)


def ordered_symbol_counts(
    catalog_keys: Sequence[str],
    symbols: Mapping[str, int],
    visible: Container[str] | None = None,
) -> list[tuple[str, int]]:
    """Gibt die gesetzten Symbole als ``(Schlüssel, Stufe 1–3)`` in Anzeigereihenfolge zurück.

    Reihenfolge nach :func:`ordered_symbol_keys`; Stärke 0 und kleiner wird
    ausgelassen.

    Args:
        catalog_keys: Schlüssel des programmweiten Katalogs in Katalogreihenfolge.
        symbols: Schlüssel → gespeicherte Stärke einer Person oder eines Tages.
        visible: Wenn gesetzt, nur diese Schlüssel (Raster-Filter).
    """
    return [
        (key, symbol_level(symbols[key]))
        for key in ordered_symbol_keys(catalog_keys, symbols)
        if int(symbols[key]) >= 1 and (visible is None or key in visible)
    ]
