"""Reihenfolge, Stufen und Legendentexte gesetzter Symbole — für Raster, Detailbereich und PDF.

Einzige Stelle, die festlegt, in welcher Reihenfolge die Symbole einer Person
erscheinen, mit welcher Stufe, und welcher Text dazu in der Legende steht.
Format einer Legendenzeile (Entscheidung der Nutzerin 2026-11-18):
``"🎯🎯 Konzentration: Text a, Text b"`` — Glyph so oft wie die Stufe, Name,
dann die Stufentexte aller verknüpften Kompetenzen, mit Komma verbunden.
"""

from __future__ import annotations

from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.core.domain.symbol_catalog import Competence, SymbolDefinition, level_text, symbol_level

OtherSymbolResolver = Callable[[str], tuple[str, str]]
"""Löst einen Schlüssel außerhalb des Katalogs (eigenes/gelöschtes Symbol) zu ``(Glyph, Name)`` auf."""


@dataclass(frozen=True)
class LegendEntry:
    """Eine Legendenzeile: ein gesetztes Symbol mit Stufe und Texten.

    Attributes:
        key: Symbolschlüssel.
        glyph: Anzuzeigendes Zeichen.
        name: Anzeigename.
        level: Stufe 1–3.
        texts: Stufentexte (je verknüpfter Kompetenz bzw. der Häufigkeitstext); leer bei eigenen Symbolen.
    """

    key: str
    glyph: str
    name: str
    level: int
    texts: tuple[str, ...]

    @property
    def text(self) -> str:
        """Die fertige Zeile, z. B. ``"🎯🎯 Konzentration: arbeitet …, findet …"``."""
        head = f"{self.glyph * self.level} {self.name}".strip()
        return f"{head}: {', '.join(self.texts)}" if self.texts else head


def legend_texts(definition: SymbolDefinition, level: int, competences: Mapping[str, Competence]) -> tuple[str, ...]:
    """Gibt die Stufentexte eines Katalogsymbols zur Stufe *level* zurück.

    Diagnosesymbole: je verknüpfter Kompetenz deren Text, in Verknüpfungs-
    reihenfolge; unbekannte IDs werden übersprungen. Doku-Symbole: ihr
    Häufigkeitstext.

    Args:
        definition: Das Katalogsymbol.
        level: Stufe bzw. rohe Stärke (wird auf 1–3 begrenzt).
        competences: Kompetenzen nach ID.
    """
    if definition.role == "diagnostic":
        return tuple(competences[cid].level_text(level) for cid in definition.competence_ids if cid in competences)
    if definition.frequency_legend is None:
        return ()
    return (level_text(definition.frequency_legend, level),)


def build_legend(
    catalog: Sequence[SymbolDefinition],
    competences: Mapping[str, Competence],
    symbols: Mapping[str, int],
    resolve_other: OtherSymbolResolver,
) -> list[LegendEntry]:
    """Baut die Legende für die gesetzten *symbols* einer Person (Detailbereich).

    Args:
        catalog: Programmweiter Katalog in Katalogreihenfolge.
        competences: Kompetenzen nach ID.
        symbols: Schlüssel → gespeicherte Stärke.
        resolve_other: Auflösung für Schlüssel außerhalb des Katalogs.
    """
    by_key = {definition.key: definition for definition in catalog}
    entries: list[LegendEntry] = []
    for key, level in ordered_symbol_counts(list(by_key), symbols):
        definition = by_key.get(key)
        if definition is None:
            glyph, name = resolve_other(key)
            entries.append(LegendEntry(key, glyph, name, level, ()))
            continue
        entries.append(LegendEntry(key, definition.glyph, definition.name, level,
                                   legend_texts(definition, level, competences)))
    return entries


def symbol_summary(definition: SymbolDefinition, competences: Mapping[str, Competence]) -> str:
    """Kurzbeschreibung eines Katalogsymbols für Tooltip und Verwaltungstabelle.

    Diagnosesymbole: ``"Name – Kompetenz 1, Kompetenz 2"``; Doku-Symbole:
    ``"Name – eins / zwei / drei"``.

    Args:
        definition: Das Katalogsymbol.
        competences: Kompetenzen nach ID.
    """
    if definition.role == "diagnostic":
        parts = [competences[cid].name for cid in definition.competence_ids if cid in competences]
        detail = ", ".join(parts)
    else:
        detail = " / ".join(definition.frequency_legend or ())
    return f"{definition.name} – {detail}" if detail else definition.name


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
