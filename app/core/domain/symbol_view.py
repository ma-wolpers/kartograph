"""Effektive Symbolsicht eines Plans — einzige Quelle für Namen, Kürzel und Rollen in der GUI.

:func:`build_symbol_view` fasst programmweiten Katalog, Kompetenzen und die
eigenen Doku-Symbole des offenen Plans zu einer unveränderlichen
:class:`SymbolView` zusammen. Alle GUI-Lookups (Schlüssel-Listen, Symbol nach
Schlüssel, Doku-Symbole, Buchstabe → Symbol) werden aus genau dieser Sicht
abgeleitet, statt an mehreren Stellen eigene Teilmengen zu bilden.

Kürzelregel (einzige Stelle): ein Buchstabe gehört zuerst einem **aktiven**
eingebauten Symbol, sonst einem eigenen Symbol des Plans; deaktivierte
eingebaute Symbole sind nicht mehr setzbar. Bei doppelt vergebenen eingebauten
Kürzeln gewinnt das erste in Katalogreihenfolge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from app.core.domain.custom_symbol_validation import SPACE_SHORTCUT
from app.core.domain.effective_symbol import EffectiveSymbol, build_effective_documentation_symbols
from app.core.domain.models_v4 import CustomSymbolDefinition, SeatingPlan, SymbolOverride
from app.core.domain.symbol_catalog import Competence, SymbolDefinition


def custom_symbol_for_letter(
    custom_symbols: Mapping[str, CustomSymbolDefinition], letter: str
) -> CustomSymbolDefinition | None:
    """Sucht das eigene Doku-Symbol, dessen Kürzel *letter* ist (Groß-/Kleinschreibung egal).

    Ein historischer Kürzelwert im alten ``"Ctrl+Shift+<Buchstabe>"``-Format
    kann strukturell nie passen — *letter* ist immer ein einzelner Buchstabe.

    Args:
        custom_symbols: Eigene Symbole eines Plans (``SeatingPlan.custom_symbols``).
        letter: Gedrückter Buchstabe.
    """
    target = letter.strip().upper()
    return next((custom for custom in custom_symbols.values() if custom.shortcut == target), None)


def apply_symbol_overrides(
    catalog: Sequence[SymbolDefinition], overrides: Mapping[str, SymbolOverride]
) -> tuple[SymbolDefinition, ...]:
    """Wendet die Plan-Anpassungen auf den programmweiten Katalog an (einzige Stelle).

    Ergebnis sind effektive ``SymbolDefinition``-Objekte: lokaler Name bzw.
    lokale Kompetenzen ersetzen die Programmwerte, alles andere (Schlüssel,
    Zeichen, Kürzel, Aktiv-Zustand) bleibt programmweit. Wer Namen oder
    Kompetenzen anzeigt, liest sie dadurch automatisch richtig.

    Args:
        catalog: Programmweiter Katalog.
        overrides: ``SeatingPlan.symbol_overrides``.
    """
    effective: list[SymbolDefinition] = []
    for definition in catalog:
        override = overrides.get(definition.key)
        if override is not None:
            if override.name is not None:
                definition = replace(definition, name=override.name)
            if override.competence_ids is not None and definition.role == "diagnostic":
                definition = replace(definition, competence_ids=override.competence_ids)
        effective.append(definition)
    return tuple(effective)


@dataclass(frozen=True)
class SymbolView:
    """Unveränderliche Sicht auf alle Symbole, die im offenen Plan gelten.

    Attributes:
        catalog: Effektive Symbole in Katalogreihenfolge (Plan-Anpassungen angewendet),
            inklusive deaktivierter.
        competences: Kompetenzen nach ID.
        documentation_symbols: Doku-Symbole (eingebaute ``documentation_only`` + eigene des Plans).
        custom_symbols: Eigene Symbole des Plans nach ID.
    """

    catalog: tuple[SymbolDefinition, ...]
    competences: Mapping[str, Competence]
    documentation_symbols: tuple[EffectiveSymbol, ...]
    custom_symbols: Mapping[str, CustomSymbolDefinition] = field(default_factory=dict)

    @property
    def keys(self) -> list[str]:
        """Schlüssel aller Katalogsymbole in Katalogreihenfolge."""
        return [definition.key for definition in self.catalog]

    @property
    def diagnostic_keys(self) -> list[str]:
        """Schlüssel der Diagnosesymbole (auch deaktivierter: vorhandene Werte bleiben änderbar)."""
        return [definition.key for definition in self.catalog if definition.role == "diagnostic"]

    @property
    def by_key(self) -> dict[str, SymbolDefinition]:
        """Katalogsymbol nach Schlüssel."""
        return {definition.key: definition for definition in self.catalog}

    @property
    def documentation_by_key(self) -> dict[str, EffectiveSymbol]:
        """Doku-Symbol (eingebaut oder eigen) nach Schlüssel."""
        return {symbol.key: symbol for symbol in self.documentation_symbols}

    @property
    def builtin_shortcuts(self) -> dict[str, str]:
        """Kürzel → Schlüssel der aktiven eingebauten Symbole (erstes gewinnt)."""
        mapping: dict[str, str] = {}
        for definition in self.catalog:
            if definition.active and definition.shortcut and definition.shortcut not in mapping:
                mapping[definition.shortcut] = definition.key
        return mapping

    def symbol_for_shortcut(self, shortcut: str) -> str | None:
        """Löst einen Tastendruck zum Symbolschlüssel auf (Kürzelregel im Moduldocstring).

        Args:
            shortcut: Buchstabe (beliebige Schreibung) oder ``SPACE_SHORTCUT``.
        """
        normalized = shortcut if shortcut == SPACE_SHORTCUT else shortcut.lower()
        builtin = self.builtin_shortcuts.get(normalized)
        if builtin is not None or normalized == SPACE_SHORTCUT:
            return builtin
        custom = custom_symbol_for_letter(self.custom_symbols, normalized)
        return None if custom is None else custom.id


def build_symbol_view(
    catalog: Sequence[SymbolDefinition],
    competences: Sequence[Competence],
    plan: SeatingPlan | None,
) -> SymbolView:
    """Baut die Symbolsicht für *plan* (oder ohne offenen Plan), mit dessen Symbol-Anpassungen.

    Args:
        catalog: Programmweiter Katalog (``AppState.symbol_catalog``).
        competences: Kompetenzen (``AppState.competence_catalog``).
        plan: Offener Plan oder ``None``.
    """
    custom = dict(plan.custom_symbols) if plan is not None else {}
    definitions = apply_symbol_overrides(catalog, plan.symbol_overrides if plan is not None else {})
    return SymbolView(
        catalog=definitions,
        competences={competence.id: competence for competence in competences},
        documentation_symbols=tuple(build_effective_documentation_symbols(definitions, custom)),
        custom_symbols=custom,
    )
