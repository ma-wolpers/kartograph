"""Ableitungen aus der Farbpalette: Reihenfolge, Lookup und Sortierung von Farbschlüsseln.

Die Palette selbst ist genau einmal definiert (``COLOR_MARKER_PALETTE`` in
``app/adapters/gui/main_window_constants.py``) und wird als Liste von
``(shortcut_key, color_key, label, hex)``-Tupeln an alle Verbraucher
weitergereicht (Grid, Details-Panel, PDF-Renderer, Sitzplan-Vorschau). Dieses
Modul enthält die einzigen Funktionen, die aus diesen Tupeln Reihenfolge und
Lookup ableiten. So kennt kein Verbraucher die Tupelstruktur selbst, und es
gibt keine zweite Sortierimplementierung.

Die Palettenreihenfolge ist zugleich die fachliche Nummerierung der Farben
(Tastenkürzel ``1`` … ``9``). "Farbe 1" ist also das erste Palettenelement,
die "höchste Farbe" eines Tisches das letzte in Palettenreihenfolge.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

PaletteEntryTuple = tuple[str, str, str, str]
"""Ein Palettenelement: ``(shortcut_key, color_key, label, hex_color)``."""

FALLBACK_COLOR_HEX = "#999999"
"""Ersatzfarbe für Farbschlüssel ohne (gültigen) Paletteneintrag, z. B. aus älteren Plandateien."""


def palette_order(color_palette: Sequence[PaletteEntryTuple] | None) -> list[str]:
    """Gibt die Farbschlüssel in Palettenreihenfolge (= Nummerierung 1, 2, …) zurück.

    Args:
        color_palette: Palette als Folge von ``(key, color_key, label, hex)``;
            ``None`` wird wie eine leere Palette behandelt (PDF-Renderer ohne
            Palette, z. B. in Tests).

    Returns:
        Liste der ``color_key``-Werte, z. B. ``["gelb", "orange", …]``.
    """
    return [color_key for _key, color_key, _label, _hex in (color_palette or ())]


def palette_by_key(color_palette: Sequence[PaletteEntryTuple] | None) -> dict[str, tuple[str, str]]:
    """Baut den Lookup ``color_key -> (label, hex_color)`` aus der Palette.

    Args:
        color_palette: Palette als Folge von ``(key, color_key, label, hex)``;
            ``None`` ergibt ein leeres Dict.

    Returns:
        Dict, z. B. ``{"gelb": ("Gelb", "#f4d35e"), …}``.
    """
    return {color_key: (label, hex_color) for _key, color_key, label, hex_color in (color_palette or ())}


def palette_color(color_by_key: dict[str, tuple[str, str]], color_key: str) -> tuple[str, str]:
    """Löst *color_key* zu ``(label, hex_color)`` auf, mit Ersatzwerten für unbekannte Schlüssel.

    Einzige Stelle für den Fallback: Ein Farbschlüssel, der nicht in der
    Palette steht (z. B. aus einer älteren Plandatei), wird mit seinem
    Schlüssel als Label und ``FALLBACK_COLOR_HEX`` angezeigt statt verworfen.

    Args:
        color_by_key: Lookup aus ``palette_by_key``.
        color_key: Aufzulösender Farbschlüssel.

    Returns:
        ``(label, hex_color)``, z. B. ``("Gelb", "#f4d35e")`` bzw.
        ``("blau", "#999999")`` für einen unbekannten Schlüssel.
    """
    return color_by_key.get(color_key, (color_key, FALLBACK_COLOR_HEX))


def palette_shortcut_by_key(color_palette: Sequence[PaletteEntryTuple] | None) -> dict[str, str]:
    """Baut den Lookup ``color_key -> Tastenkürzel`` (die Farbnummer, z. B. ``"1"``).

    Args:
        color_palette: Palette als Folge von ``(key, color_key, label, hex)``;
            ``None`` ergibt ein leeres Dict.

    Returns:
        Dict, z. B. ``{"gelb": "1", "orange": "2", …}``.
    """
    return {color_key: key for key, color_key, _label, _hex in (color_palette or ())}


def order_color_keys(color_markers: Iterable[str], color_order: Sequence[str]) -> list[str]:
    """Sortiert Farbschlüssel gemäß Palettenreihenfolge, ohne Duplikate.

    Schlüssel, die in der Palette nicht vorkommen (z. B. aus einer älteren
    Plandatei), werden nicht verworfen, sondern in ihrer Eingangsreihenfolge
    hinten angehängt. So geht beim Anzeigen keine gespeicherte Markierung
    verloren.

    Args:
        color_markers: Farbschlüssel eines Tisches oder Plans (beliebige Reihenfolge).
        color_order: Referenzreihenfolge, typischerweise ``palette_order(palette)``.

    Returns:
        Sortierte Liste, z. B. ``order_color_keys(["rot", "gelb"], ["gelb", "orange", "rot"])
        == ["gelb", "rot"]``.
    """
    markers = list(color_markers)
    ordered: list[str] = []
    seen: set[str] = set()
    for color_key in color_order:
        if color_key in markers and color_key not in seen:
            ordered.append(color_key)
            seen.add(color_key)
    for color_key in markers:
        if color_key not in seen:
            ordered.append(color_key)
            seen.add(color_key)
    return ordered
