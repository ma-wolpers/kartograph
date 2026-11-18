"""Tests für die gemeinsame Symbol-Reihenfolge und -Stufung (``symbol_legend``, ``symbol_level``)."""

from __future__ import annotations

import pytest

from app.core.domain.symbol_catalog import Competence, SymbolDefinition, symbol_level
from app.core.domain.symbol_legend import (
    LegendEntry,
    build_legend,
    legend_texts,
    ordered_symbol_counts,
    ordered_symbol_keys,
    symbol_summary,
)

CATALOG = ["Beteiligung", "Kooperation", "Abwesend"]


@pytest.mark.parametrize(("raw", "level"), [(-2, 1), (0, 1), (1, 1), (2, 2), (3, 3), (7, 3)])
def test_symbol_level_clamps_to_one_to_three(raw: int, level: int) -> None:
    assert symbol_level(raw) == level


def test_level_text_uses_the_shared_clamp() -> None:
    competence = Competence("k.a", "A", "K", ("eins", "zwei", "drei"))
    assert [competence.level_text(count) for count in (0, 1, 2, 3, 9)] == ["eins", "eins", "zwei", "drei", "drei"]


def test_catalog_keys_first_then_others_case_insensitive() -> None:
    keys = ordered_symbol_keys(CATALOG, ["zebra", "Abwesend", "apfel", "Beteiligung", "Birne"])
    assert keys == ["Beteiligung", "Abwesend", "apfel", "Birne", "zebra"]


def test_counts_skip_zero_and_clamp() -> None:
    counts = ordered_symbol_counts(CATALOG, {"Kooperation": 0, "Beteiligung": 5, "eigen": 2})
    assert counts == [("Beteiligung", 3), ("eigen", 2)]


def test_counts_respect_visible_filter() -> None:
    counts = ordered_symbol_counts(CATALOG, {"Beteiligung": 1, "Kooperation": 2}, visible={"Kooperation"})
    assert counts == [("Kooperation", 2)]


COMPETENCES = {
    "k.arbeiten": Competence("k.arbeiten", "konzentriert arbeiten", "Konzentration", ("arbeitet phasenweise", "arbeitet überwiegend", "bleibt dabei")),
    "k.zurueck": Competence("k.zurueck", "zur Aufgabe zurückfinden", "Konzentration", ("mit Begleitung", "nach Erinnerung", "eigeninitiativ")),
}
DIAGNOSTIC = SymbolDefinition(key="Konzentration", name="Fokus", glyph="🎯", shortcut="z",
                              competence_ids=("k.arbeiten", "fehlt", "k.zurueck"))
ABSENT = SymbolDefinition(key="Abwesend", name="Abwesend", glyph="∅", shortcut="space", role="documentation_only",
                          frequency_legend=("am Termin", "wiederholt", "mehrfach"))


def test_legend_texts_follow_link_order_and_skip_unknown_ids() -> None:
    assert legend_texts(DIAGNOSTIC, 2, COMPETENCES) == ("arbeitet überwiegend", "nach Erinnerung")
    assert legend_texts(ABSENT, 1, COMPETENCES) == ("am Termin",)


def test_build_legend_uses_the_display_name_and_resolver_for_others() -> None:
    entries = build_legend([DIAGNOSTIC, ABSENT], COMPETENCES, {"eigen": 1, "Konzentration": 3},
                           lambda key: ("★", f"Eigenes {key}"))

    assert [entry.text for entry in entries] == [
        "🎯🎯🎯 Fokus: bleibt dabei, eigeninitiativ",
        "★ Eigenes eigen",
    ]


def test_entry_without_texts_shows_only_glyphs_and_name() -> None:
    assert LegendEntry("k", "∅", "Abwesend", 2, ()).text == "∅∅ Abwesend"


def test_symbol_summary_lists_competence_names_or_frequency_levels() -> None:
    assert symbol_summary(DIAGNOSTIC, COMPETENCES) == "Fokus – konzentriert arbeiten, zur Aufgabe zurückfinden"
    assert symbol_summary(ABSENT, COMPETENCES) == "Abwesend – am Termin / wiederholt / mehrfach"
