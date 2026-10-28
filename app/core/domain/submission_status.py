"""Abgabestatus einer Person an einem Doku-Tag und seine Doku-Symbole (SSOT).

Genau eines von drei Symbolen beschreibt den Status: ✓ vollständig,
◐ lückenhaft, X nicht bearbeitet bzw. nicht abgegeben (Nichtabgabe und
"nicht bearbeitet" sind bewusst dasselbe Symbol). Identität ist der
**Codepoint**, nicht der Anzeigetext: Der gespeicherte Symbolname
(``meaning``, Schlüssel in ``SessionEntry.symbols``) wird zur Laufzeit aus
dem geladenen Katalog aufgelöst. So bleibt "Abgaben zählen" funktionsfähig,
wenn jemand die Beschriftungen in ``symbols.json`` ändert.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Protocol


class SubmissionStatus(Enum):
    """Bewertung einer Abgabe, Wert = Codepoint des zugehörigen Doku-Symbols."""

    COMPLETE = "2713"   # ✓
    PARTIAL = "25D0"    # ◐
    MISSING = "0058"    # X (nicht abgegeben / nicht bearbeitet)


class _CatalogSymbol(Protocol):
    """Was diese Auflösung von einem Katalogeintrag braucht (Glyph + gespeicherter Name)."""

    glyph: str
    meaning: str


class CatalogSymbolMissing(LookupError):
    """Ein benötigtes Symbol fehlt im Katalog (z. B. bewusst aus ``symbols.json`` gelöscht)."""


ABSENT_CODEPOINT = "2205"  # ∅ Abwesend – für die Wahl "Abwesende ohne Abgabe auch mit X?"


def resolve_symbol_name(catalog: Iterable[_CatalogSymbol], codepoint: str) -> str:
    """Gibt den gespeicherten Symbolnamen des Katalogeintrags mit *codepoint* zurück.

    Args:
        catalog: Geladene Symboldefinitionen (``AppState.symbol_catalog``).
        codepoint: Hex-Codepoint, z. B. ``"2713"``.

    Raises:
        CatalogSymbolMissing: Wenn der Codepoint im Katalog fehlt.
    """
    glyph = chr(int(codepoint, 16))
    for symbol in catalog:
        if symbol.glyph == glyph:
            return symbol.meaning
    raise CatalogSymbolMissing(f"Symbol U+{codepoint} fehlt im Symbolkatalog")


def submission_symbol_names(catalog: Iterable[_CatalogSymbol]) -> dict[SubmissionStatus, str]:
    """Löst die gespeicherten Symbolnamen aller drei Status aus *catalog* auf.

    Args:
        catalog: Geladene Symboldefinitionen.

    Raises:
        CatalogSymbolMissing: Wenn eines der drei Symbole fehlt.
    """
    entries = tuple(catalog)
    return {status: resolve_symbol_name(entries, status.value) for status in SubmissionStatus}
