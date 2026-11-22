"""Ja/Nein-Spalten der Datenansicht = Farbmarkierungen (SSOT, reines Python).

Entscheidung der Nutzerin (2026-11-17): Eine Ja/Nein-Spalte *ist* eine
Farbspalte. Darum gibt es keinen eigenen Speicher:

- Die Spalte ist ein Eintrag in ``plan.color_palette`` (Schlüssel = Farbe,
  ``PaletteEntry.meaning`` = Spaltentitel).
- Ob eine Person markiert ist, steht wie jede Farbe in
  ``DiagnosticProfile.color_tags``.
- Ist beim Anlegen keine Farbe mehr frei, bekommt die Spalte einen
  **farblosen** Schlüssel ``flag_<8 hex>``. Farblose Markierungen erscheinen
  nur in der Datenansicht: ``color_order.order_color_keys`` -- der gemeinsame
  Eingang aller Sitzplan-Darstellungen (Raster, Legende, PDF, Vorschau) --
  lässt sie weg.

Lebensdauer (ebenfalls Entscheidung der Nutzerin): Eine Spalte verschwindet
nur, wenn die letzte Markierung entfernt wird; eine von Anfang an leere Spalte
bleibt (``color_usecases.drop_abandoned_palette_entries``).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.core.domain.short_id import new_short_id

COLORLESS_PREFIX = "flag_"
FLAG_KIND_LABEL = "Ja/Nein"
"""Beschriftung des Spaltentyps im Dialog "Notizspalte hinzufügen" (neben den Typen aus ``note_column_kinds``)."""
FLAG_MARK = "✓"
"""Wert/Zelltext einer gesetzten Ja/Nein-Markierung (Datenansicht, ``note_groups.note_entries``)."""


def is_colorless_flag(key: str) -> bool:
    """Ist *key* der Schlüssel einer farblosen Ja/Nein-Spalte?

    Args:
        key: Schlüssel aus ``color_palette``/``color_tags``.
    """
    return key.startswith(COLORLESS_PREFIX)


def new_colorless_key(existing: Iterable[str]) -> str:
    """Erzeugt einen neuen, unbenutzten farblosen Schlüssel ``flag_<8 hex>``.

    Args:
        existing: Bereits vergebene Schlüssel (Palette und getragene Markierungen).

    Returns:
        z. B. ``"flag_3fa85f64"``.
    """
    return new_short_id(existing, prefix=COLORLESS_PREFIX)


def free_color_keys(color_order: Sequence[str], in_use: Iterable[str]) -> list[str]:
    """Farben der Palette, die noch keine Spalte haben (weder Eintrag noch Träger).

    Args:
        color_order: Farbschlüssel in Palettenreihenfolge (``palette_order``).
        in_use: Schlüssel der Paletteneinträge und getragenen Markierungen.

    Returns:
        Freie Farben in Palettenreihenfolge; leer, wenn alle vergeben sind.
    """
    used = set(in_use)
    return [key for key in color_order if key not in used]


def flag_column_keys(color_order: Sequence[str], in_use: Iterable[str]) -> list[str]:
    """Reihenfolge der Ja/Nein-Spalten: Farben in Palettenreihenfolge, dann Fremdschlüssel, dann farblose.

    Fremdschlüssel (Farben, die in der Palette nicht vorkommen, z. B. aus einer
    älteren Plandatei) und farblose Spalten behalten ihre Eingangsreihenfolge.

    Args:
        color_order: Farbschlüssel in Palettenreihenfolge.
        in_use: Schlüssel der Paletteneinträge und getragenen Markierungen
            (Eingangsreihenfolge = Anlagereihenfolge).

    Returns:
        Spaltenschlüssel ohne Dubletten.
    """
    keys = list(dict.fromkeys(in_use))
    known = [key for key in color_order if key in keys]
    foreign = [key for key in keys if key not in color_order and not is_colorless_flag(key)]
    colorless = [key for key in keys if is_colorless_flag(key)]
    return known + foreign + colorless
