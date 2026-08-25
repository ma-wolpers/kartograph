"""Tests für die EffectiveSymbol-Projektion (eingebaute + eigene Doku-Symbole)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.effective_symbol import build_effective_documentation_symbols, resolve_symbol_display
from app.core.domain.models_v4 import CustomSymbolDefinition


@dataclass(frozen=True)
class _FakeSymbolDefinition:
    """Minimaler Stand-in für SymbolDefinition -- erfuellt _SymbolDefinitionLike
    strukturell, ohne von app.infrastructure abhaengen zu muessen."""

    meaning: str
    glyph: str
    role: str
    legend_one: str = "eins"
    legend_two: str = "zwei"
    legend_three: str = "drei"


def _custom(id_: str, glyph: str, meaning: str, shortcut: str = "Ctrl+Shift+K") -> CustomSymbolDefinition:
    return CustomSymbolDefinition(id=id_, glyph=glyph, meaning=meaning, shortcut=shortcut)


class TestBuildEffectiveDocumentationSymbols:
    def test_documentation_only_builtin_is_included_with_legend(self):
        defs = [_FakeSymbolDefinition(meaning="Abwesend", glyph="∅", role="documentation_only")]

        result = build_effective_documentation_symbols(defs, {})

        assert len(result) == 1
        symbol = result[0]
        assert symbol.key == "Abwesend"
        assert symbol.display_name == "Abwesend"
        assert symbol.is_custom is False
        assert symbol.legend == ("eins", "zwei", "drei")

    def test_diagnostic_builtin_is_excluded(self):
        defs = [_FakeSymbolDefinition(meaning="Beteiligung", glyph="b", role="diagnostic")]

        result = build_effective_documentation_symbols(defs, {})

        assert result == []

    def test_custom_symbol_is_included_without_legend(self):
        custom = _custom("abc123", "☕", "Kaffee vergessen")

        result = build_effective_documentation_symbols([], {custom.id: custom})

        assert len(result) == 1
        symbol = result[0]
        assert symbol.key == "abc123"
        assert symbol.glyph == "☕"
        assert symbol.display_name == "Kaffee vergessen"
        assert symbol.is_custom is True
        assert symbol.legend is None

    def test_builtin_and_custom_symbols_are_combined(self):
        defs = [_FakeSymbolDefinition(meaning="Abwesend", glyph="∅", role="documentation_only")]
        custom = _custom("abc123", "☕", "Kaffee vergessen")

        result = build_effective_documentation_symbols(defs, {custom.id: custom})

        assert {s.key for s in result} == {"Abwesend", "abc123"}

    def test_two_different_custom_symbol_maps_produce_different_results(self):
        """Grundlage fuer den Plan-Isolations-Nachweis: keinerlei geteilter
        Zustand zwischen zwei Aufrufen mit unterschiedlichen custom_symbols."""
        custom_a = _custom("id-a", "☕", "Kaffee vergessen")
        custom_b = _custom("id-b", "💻", "Laptop vergessen")

        result_a = build_effective_documentation_symbols([], {custom_a.id: custom_a})
        result_b = build_effective_documentation_symbols([], {custom_b.id: custom_b})

        assert [s.key for s in result_a] == ["id-a"]
        assert [s.key for s in result_b] == ["id-b"]


class TestResolveSymbolDisplay:
    def test_known_key_resolves_to_glyph_and_display_name(self):
        custom = _custom("abc123", "☕", "Kaffee vergessen")
        effective = build_effective_documentation_symbols([], {custom.id: custom})

        assert resolve_symbol_display("abc123", effective) == ("☕", "Kaffee vergessen")

    def test_unknown_key_falls_back_to_deleted_symbol_placeholder(self):
        assert resolve_symbol_display("no-such-key", []) == ("❔", "Gelöschtes Symbol")
