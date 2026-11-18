"""Domänenmodell des programmweiten Symbolkatalogs (eingebaute Symbole aus ``config/symbols.json``).

Einzige Definition von :class:`SymbolDefinition`, :data:`SymbolRole` und der
Stärke-Stufung :func:`symbol_level`. Liegt im Kern, damit Domänenlogik
(Legende, Abgaben, Validierung) und Infrastruktur (Loader, PDF) denselben Typ
verwenden, statt ihn über Protocols nachzubauen. Das JSON-Format kennt nur der
Loader in ``app/infrastructure``.

Identität: ``key`` ist der stabile Speicherschlüssel eines Symbols in Plänen
(``DiagnosticProfile.symbols``, ``SessionEntry.symbols``) und Einstellungen
(Raster-Filter). Er entspricht dem historischen ``meaning``-Text und ändert sich
nie; ``name`` ist nur der Anzeigename und darf umbenannt werden, ohne dass
gespeicherte Beobachtungen verwaisen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SymbolRole = Literal["diagnostic", "documentation_only"]
"""``diagnostic``: Stärke 1–3 im Diagnoseprofil; ``documentation_only``: an/aus je Dokumentationstag."""

MAX_SYMBOL_LEVEL = 3


def symbol_level(count: int) -> int:
    """Begrenzt eine gespeicherte Symbolstärke auf die Stufe 1–3 (einzige Stelle dieser Regel).

    Werte unter 1 ergeben 1 (ein gesetztes Symbol zeigt mindestens eine Stufe),
    Werte über 3 ergeben 3. Aufrufer filtern Stärke 0 („nicht gesetzt“) vorher.

    Args:
        count: Rohe Stärke, wie sie im Plan steht.
    """
    return max(1, min(MAX_SYMBOL_LEVEL, int(count)))


@dataclass(frozen=True)
class SymbolDefinition:
    """Ein eingebautes Symbol des programmweiten Katalogs.

    Attributes:
        key: Stabiler Speicherschlüssel (s. Moduldocstring), nie umbenannt.
        name: Anzeigename; anfangs gleich ``key``.
        glyph: Das Zeichen, das im Raster, in der Legende und im PDF erscheint.
        shortcut: Kleinbuchstabe, der Sentinel ``"space"`` oder ``None``.
        legend: Stufentexte ``(eins, zwei, drei)``; ``drei`` ist die höchste Ausprägung.
        role: Diagnose- oder reines Doku-Symbol.
    """

    key: str
    name: str
    glyph: str
    shortcut: str | None
    legend: tuple[str, str, str]
    role: SymbolRole = "diagnostic"

    def legend_for_count(self, count: int) -> str:
        """Gibt den Legendentext für die Stärke *count* zurück (gestuft über :func:`symbol_level`).

        Args:
            count: Symbolstärke, für die der passende Legendentext gesucht wird.
        """
        return self.legend[symbol_level(count) - 1]
