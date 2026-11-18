"""Vereinheitlichte, GUI-taugliche Sicht auf Doku-Symbole — eingebaut und eigen.

Reine Projektion, kein Persistenzformat: fasst die dokumentationsbezogenen
eingebauten Symbole (``SymbolDefinition`` mit ``role == "documentation_only"``
aus dem globalen ``config/symbols.json``-Katalog) und die eigenen Symbole
eines Plans (``CustomSymbolDefinition`` aus ``SeatingPlan.custom_symbols``)
zu einer gemeinsamen, schlanken Liste zusammen — ohne die drei Legenden-
stufen der eingebauten Symbole künstlich auf eigene Symbole zu übertragen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from app.core.domain.models_v4 import CustomSymbolDefinition
from app.core.domain.symbol_catalog import SymbolDefinition, SymbolRole

_DELETED_SYMBOL_GLYPH = "❔"
_DELETED_SYMBOL_LABEL = "Gelöschtes Symbol"


@dataclass(frozen=True)
class EffectiveSymbol:
    """GUI-taugliche, vereinheitlichte Sicht auf ein Symbol — eingebaut oder eigen.

    Kein Persistenzformat, nur eine Lese-Projektion. ``legend`` ist nur bei
    eingebauten Symbolen gesetzt (drei Stufentexte); eigene Doku-Symbole
    haben stattdessen ausschließlich ``display_name`` als einzigen
    Bedeutungstext — das ist bewusst kein Ersatz-Dreifach-Text, sondern
    schlicht ``None``.
    """

    key: str
    glyph: str
    display_name: str
    role: SymbolRole
    is_custom: bool
    legend: tuple[str, str, str] | None
    shortcut: str | None


def build_effective_documentation_symbols(
    symbol_definitions: Sequence[SymbolDefinition],
    custom_symbols: Mapping[str, CustomSymbolDefinition],
) -> list[EffectiveSymbol]:
    """Baut die Liste aller *dokumentationsbezogenen* Symbole eines Plans.

    Enthält die eingebauten Symbole mit ``role == "documentation_only"``
    (mit ihren drei Legendenstufen) sowie alle eigenen Symbole des Plans
    (ohne Legendenstufen, ``legend=None``). Diagnostische eingebaute Symbole
    (``role == "diagnostic"``) tauchen hier bewusst nicht auf — sie bleiben
    im unveränderten, bestehenden Diagnose-Pfad (Raster-Einzelbuchstaben-
    Toggle, PDF-Export, Details-Panel-Badge-Leiste), den dieses Feature
    nicht anfasst.

    Reine Funktion ohne Tk-/GUI-Abhängigkeit — direkt unit-testbar, u. a. für
    den Plan-Isolations-Nachweis (zwei verschiedene ``custom_symbols``-Dicts
    liefern unterschiedliche Ergebnislisten, ganz ohne GUI-Zustand).

    Args:
        symbol_definitions: Der globale, app-weite Symbolkatalog (aus
            ``AppState.symbol_catalog``).
        custom_symbols: Die eigenen Symbole des aktuell betrachteten Plans
            (``SeatingPlan.custom_symbols``), leer bei keinem offenen Plan.

    Returns:
        Liste von ``EffectiveSymbol``, eingebaute zuerst (in Katalog-
        Reihenfolge), danach eigene (in Dict-Iterationsreihenfolge).
    """
    result: list[EffectiveSymbol] = [
        EffectiveSymbol(
            key=definition.key,
            glyph=definition.glyph,
            display_name=definition.name,
            role=definition.role,
            is_custom=False,
            legend=definition.frequency_legend,
            shortcut=definition.shortcut,
        )
        for definition in symbol_definitions
        if definition.role == "documentation_only"
    ]
    result.extend(
        EffectiveSymbol(
            key=custom.id,
            glyph=custom.glyph,
            display_name=custom.meaning,
            role="documentation_only",
            is_custom=True,
            legend=None,
            shortcut=custom.shortcut,
        )
        for custom in custom_symbols.values()
    )
    return result


def resolve_symbol_display(key: str, effective_symbols: Sequence[EffectiveSymbol]) -> tuple[str, str]:
    """Löst *key* zu ``(glyph, Anzeigetext)`` auf.

    Fällt auf ``(_DELETED_SYMBOL_GLYPH, _DELETED_SYMBOL_LABEL)`` zurück, wenn
    *key* zu keinem der übergebenen, aktuell bekannten Symbole mehr gehört —
    das ist der einzige Ort, an dem dieser Fallback definiert ist. Tritt auf,
    wenn ein historischer ``SessionEntry``-Eintrag ein inzwischen aus dem
    Katalog gelöschtes eigenes Symbol referenziert (siehe
    ``delete_custom_symbol()`` in ``custom_symbol_usecases.py``, das
    historische Daten bewusst nicht anfasst). Alle Anzeigestellen rufen
    ausschließlich diese Funktion auf, statt eigene ``None``-Behandlung zu
    bauen.

    Args:
        key: ``SessionEntry.symbols``-Schlüssel (eingebauter ``SymbolDefinition.key``
            oder eigene Symbol-ID).
        effective_symbols: Die aktuell gültige Liste, z. B. aus
            ``build_effective_documentation_symbols()``.
    """
    for symbol in effective_symbols:
        if symbol.key == key:
            return symbol.glyph, symbol.display_name
    return _DELETED_SYMBOL_GLYPH, _DELETED_SYMBOL_LABEL
