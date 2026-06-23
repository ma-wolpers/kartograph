"""Zustandslose Hilfsfunktionen für den PDF-Export.

Enthält Schriftgrößen-Fitting, Symbol-Token-Generierung, Symbol-Listen-
Iteration und Farbmarkierungs-Sortierung. Alle Funktionen sind rein
(keine Seiteneffekte) und können von mehreren Renderern genutzt werden.
"""

from __future__ import annotations

from app.infrastructure.symbol_config_loader import SymbolDefinition


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
    meaning: str,
    count: int,
    symbols_by_meaning: dict[str, SymbolDefinition],
    uses_fallback: bool,
) -> str:
    """Erzeugt das Anzeigetoken für ein Symbol mit gegebener Stärke.

    Args:
        meaning: Symbolbedeutung.
        count: Anzahl/Stärke (1–3).
        symbols_by_meaning: Lookup-Dict der Symboldefinitionen.
        uses_fallback: True, wenn kein Unicode-Zeichensatz verfügbar ist.

    Returns:
        Token-String (Glyphen oder Buchstabe-Kürzel).
    """
    symbol = symbols_by_meaning.get(meaning)
    clamped = max(1, min(3, int(count)))
    if symbol is None:
        return "?" * clamped
    if uses_fallback:
        shortcut = (symbol.shortcut or meaning[:1] or "?").upper()
        return shortcut * clamped
    return symbol.glyph * clamped


def iter_symbol_counts(
    symbol_definitions: list[SymbolDefinition],
    symbols_by_meaning: dict[str, SymbolDefinition],
    symbols: dict[str, int],
    visible_symbols: set[str] | None = None,
) -> list[tuple[str, int]]:
    """Gibt eine geordnete Liste von (Symbolbedeutung, Stärke) zurück.

    Bekannte Symbole erscheinen in Definitionsreihenfolge, unbekannte
    alphabetisch dahinter. Symbole mit Stärke 0 werden ausgelassen.

    Args:
        symbol_definitions: Geordnete Liste aller Symboldefinitionen.
        symbols_by_meaning: Lookup-Dict der Symboldefinitionen.
        symbols: Dict von Symbolbedeutung → Stärke des aktuellen Tisches.
        visible_symbols: Wenn gesetzt, werden nur diese Symbole angezeigt.

    Returns:
        Liste von (Bedeutung, clamped Stärke 1–3).
    """
    entries: list[tuple[str, int]] = []
    for symbol in symbol_definitions:
        if visible_symbols is not None and symbol.meaning not in visible_symbols:
            continue
        count = int(symbols.get(symbol.meaning, 0))
        if count >= 1:
            entries.append((symbol.meaning, min(3, count)))
    for meaning, raw_count in sorted(symbols.items(), key=lambda item: item[0].lower()):
        if meaning in symbols_by_meaning:
            continue
        if visible_symbols is not None and meaning not in visible_symbols:
            continue
        count = int(raw_count)
        if count >= 1:
            entries.append((meaning, min(3, count)))
    return entries


def order_color_keys(color_markers: list[str], color_order: list[str]) -> list[str]:
    """Sortiert Farbmarkierungen gemäß der definierten Palettenreihenfolge.

    Args:
        color_markers: Farbmarker des Tisches (Roh-Reihenfolge).
        color_order: Referenz-Reihenfolge der Farbpalette.

    Returns:
        Sortierte Liste ohne Duplikate.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for color_key in color_order:
        if color_key in color_markers and color_key not in seen:
            ordered.append(color_key)
            seen.add(color_key)
    for color_key in color_markers:
        if color_key not in seen:
            ordered.append(color_key)
            seen.add(color_key)
    return ordered
