"""Tests für die Raster-Symbolfilter-Regel (Ausblendliste statt Sichtbar-Liste)."""

from __future__ import annotations

from app.core.domain.grid_symbol_filter import hidden_from_selection, visible_grid_symbols

REFERENCE = ["Beteiligung", "Konzentration", "Abwesend"]


def test_new_symbols_stay_visible_after_the_filter_was_saved() -> None:
    hidden = hidden_from_selection(REFERENCE, ["Beteiligung", "Abwesend"])
    later_reference = [*REFERENCE, "Motivation", "eigenes-symbol"]

    assert hidden == ("Konzentration",)
    assert visible_grid_symbols(later_reference, hidden) == {"Beteiligung", "Abwesend", "Motivation", "eigenes-symbol"}


def test_nothing_selected_means_show_all() -> None:
    assert hidden_from_selection(REFERENCE, []) == ()
    assert visible_grid_symbols(REFERENCE, ()) == set(REFERENCE)


def test_never_saved_shows_all() -> None:
    assert visible_grid_symbols(REFERENCE, None) == set(REFERENCE)


def test_legacy_visible_list_still_applies_until_saved_again() -> None:
    assert visible_grid_symbols(REFERENCE, None, ("Beteiligung", "unbekannt")) == {"Beteiligung"}
    assert visible_grid_symbols(REFERENCE, None, ("unbekannt",)) == set(REFERENCE)


def test_new_format_wins_over_legacy_list() -> None:
    assert visible_grid_symbols(REFERENCE, ("Abwesend",), ("Beteiligung",)) == {"Beteiligung", "Konzentration"}
