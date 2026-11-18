"""Tests für die gemeinsame Symbol-Reihenfolge und -Stufung (``symbol_legend``, ``symbol_level``)."""

from __future__ import annotations

import pytest

from app.core.domain.symbol_catalog import SymbolDefinition, symbol_level
from app.core.domain.symbol_legend import ordered_symbol_counts, ordered_symbol_keys

CATALOG = ["Beteiligung", "Kooperation", "Abwesend"]


@pytest.mark.parametrize(("raw", "level"), [(-2, 1), (0, 1), (1, 1), (2, 2), (3, 3), (7, 3)])
def test_symbol_level_clamps_to_one_to_three(raw: int, level: int) -> None:
    assert symbol_level(raw) == level


def test_legend_for_count_uses_the_shared_clamp() -> None:
    definition = SymbolDefinition(key="k", name="K", glyph="k", shortcut=None, legend=("eins", "zwei", "drei"))
    assert [definition.legend_for_count(count) for count in (0, 1, 2, 3, 9)] == ["eins", "eins", "zwei", "drei", "drei"]


def test_catalog_keys_first_then_others_case_insensitive() -> None:
    keys = ordered_symbol_keys(CATALOG, ["zebra", "Abwesend", "apfel", "Beteiligung", "Birne"])
    assert keys == ["Beteiligung", "Abwesend", "apfel", "Birne", "zebra"]


def test_counts_skip_zero_and_clamp() -> None:
    counts = ordered_symbol_counts(CATALOG, {"Kooperation": 0, "Beteiligung": 5, "eigen": 2})
    assert counts == [("Beteiligung", 3), ("eigen", 2)]


def test_counts_respect_visible_filter() -> None:
    counts = ordered_symbol_counts(CATALOG, {"Beteiligung": 1, "Kooperation": 2}, visible={"Kooperation"})
    assert counts == [("Kooperation", 2)]
