"""Zustandslose Hilfsfunktionen für den PDF-Export.

Enthält Schriftgrößen-Fitting und Symbol-Token-Generierung; die Reihenfolge
der Symbole liefert ``app/core/domain/symbol_legend.py``. Alle Funktionen sind rein (keine Seiteneffekte) und können von
mehreren Renderern genutzt werden. Die Farbmarkierungs-Sortierung liegt in
``app/core/domain/color_order.py`` (gemeinsam mit Grid und Sitzplan-Vorschau).
"""

from __future__ import annotations

from app.core.domain.symbol_catalog import SymbolDefinition, symbol_level


def fit_single_line_font(
    pdfmetrics,
    font_name: str,
    text: str,
    max_width: float,
    max_height: float,
    min_size: int,
    max_size: int,
) -> int:
    """Bestimmt die größtmögliche Schriftgröße für einzeiligen Text.

    Args:
        pdfmetrics: ReportLab ``pdfmetrics``-Modul.
        font_name: Name des Zeichensatzes.
        text: Anzuzeigender Text.
        max_width: Maximale Breite in Punkten.
        max_height: Maximale Höhe in Punkten.
        min_size: Kleinste erlaubte Schriftgröße.
        max_size: Größte erlaubte Schriftgröße.

    Returns:
        Schriftgröße (int) zwischen *min_size* und *max_size*.
    """
    if not text:
        return min_size
    for size in range(max_size, min_size - 1, -1):
        if pdfmetrics.stringWidth(text, font_name, size) <= max_width and size * 1.15 <= max_height:
            return size
    return min_size


def fit_multi_line_font(
    pdfmetrics,
    font_name: str,
    lines: list[str],
    max_width: float,
    max_height: float,
    min_size: int,
    max_size: int,
) -> tuple[int, float]:
    """Bestimmt Schriftgröße und Zeilenhöhe für mehrzeiligen Text.

    Args:
        pdfmetrics: ReportLab ``pdfmetrics``-Modul.
        font_name: Name des Zeichensatzes.
        lines: Liste von Textzeilen.
        max_width: Maximale Breite in Punkten.
        max_height: Maximale Gesamthöhe in Punkten.
        min_size: Kleinste erlaubte Schriftgröße.
        max_size: Größte erlaubte Schriftgröße.

    Returns:
        Tupel aus (Schriftgröße, Zeilenhöhe in Punkten).
    """
    if not lines:
        return min_size, max(6.0, min_size * 1.1)
    for size in range(max_size, min_size - 1, -1):
        line_height = max(6.0, size * 1.12)
        if line_height * len(lines) > max_height:
            continue
        if not any(pdfmetrics.stringWidth(line, font_name, size) > max_width for line in lines):
            return size, line_height
    return min_size, max(6.0, min_size * 1.1)


def build_symbol_token(
    key: str,
    count: int,
    symbols_by_key: dict[str, SymbolDefinition],
    uses_fallback: bool,
) -> str:
    """Erzeugt das Anzeigetoken für ein Symbol mit gegebener Stärke.

    Args:
        key: Symbolschlüssel (``SymbolDefinition.key``).
        count: Anzahl/Stärke (1–3).
        symbols_by_key: Lookup-Dict der Symboldefinitionen.
        uses_fallback: True, wenn kein Unicode-Zeichensatz verfügbar ist.

    Returns:
        Token-String (Glyphen oder Buchstabe-Kürzel).
    """
    symbol = symbols_by_key.get(key)
    clamped = symbol_level(count)
    if symbol is None:
        return "?" * clamped
    if uses_fallback:
        shortcut = (symbol.shortcut or key[:1] or "?").upper()
        return shortcut * clamped
    return symbol.glyph * clamped
