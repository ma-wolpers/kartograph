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


LevelTexts = tuple[str, str, str]
"""Stufentexte ``(eins, zwei, drei)``; ``drei`` ist immer die höchste Ausprägung."""


def level_text(levels: LevelTexts, count: int) -> str:
    """Gibt den Stufentext zur Stärke *count* zurück (gestuft über :func:`symbol_level`).

    Args:
        levels: Die drei Stufentexte.
        count: Symbolstärke, für die der passende Text gesucht wird.
    """
    return levels[symbol_level(count) - 1]


@dataclass(frozen=True)
class Competence:
    """Eine atomare Kompetenz mit drei Stufentexten (``config/competences.json``).

    Attributes:
        id: Stabile ASCII-ID (``gruppe.teilaspekt``), nie umbenannt.
        name: Anzeigename, z. B. „zur Aufgabe zurückfinden“.
        group: Gruppierung in der Auswahl, z. B. „Konzentration“.
        levels: Stufentexte, Formulierungsregeln in ``docs/SYMBOLE.md``.
    """

    id: str
    name: str
    group: str
    levels: LevelTexts

    def level_text(self, count: int) -> str:
        """Gibt den Text zur Stärke *count* zurück.

        Args:
            count: Symbolstärke (wird auf 1–3 begrenzt).
        """
        return level_text(self.levels, count)


@dataclass(frozen=True)
class SymbolDefinition:
    """Ein eingebautes Symbol des programmweiten Katalogs.

    Diagnosesymbole tragen keine eigenen Stufentexte mehr, sondern verknüpfen
    Kompetenzen (``competence_ids``); nur Doku-Symbole haben Häufigkeitstexte
    (``frequency_legend``, z. B. „einmalig … / mehrfach … / wiederholt …“).

    Attributes:
        key: Stabiler Speicherschlüssel (s. Moduldocstring), nie umbenannt.
        name: Anzeigename; anfangs gleich ``key``.
        glyph: Das Zeichen, das im Raster, in der Legende und im PDF erscheint.
        shortcut: Kleinbuchstabe, der Sentinel ``"space"`` oder ``None``.
        role: Diagnose- oder reines Doku-Symbol.
        active: ``False`` = programmweit deaktiviert (nicht mehr setzbar; vorhandene
            Daten bleiben sichtbar).
        competence_ids: Verknüpfte Kompetenzen in Legendenreihenfolge (nur Diagnose).
        frequency_legend: Häufigkeitstexte (nur Doku-Symbole).
    """

    key: str
    name: str
    glyph: str
    shortcut: str | None
    role: SymbolRole = "diagnostic"
    active: bool = True
    competence_ids: tuple[str, ...] = ()
    frequency_legend: LevelTexts | None = None
