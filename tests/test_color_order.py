"""Tests für die gemeinsamen Paletten-Ableitungen in ``app/core/domain/color_order.py``."""

from __future__ import annotations

from app.adapters.gui.main_window_constants import COLOR_MARKER_PALETTE
from app.core.domain.color_order import (
    FALLBACK_COLOR_HEX,
    order_color_keys,
    palette_by_key,
    palette_color,
    palette_order,
    palette_shortcut_by_key,
)

PALETTE = [
    ("1", "gelb", "Gelb", "#111111"),
    ("2", "orange", "Orange", "#222222"),
    ("3", "rot", "Rot", "#333333"),
]


def test_palette_order_follows_palette_numbering() -> None:
    """Die Reihenfolge entspricht der Palette (= Nummerierung 1, 2, 3)."""
    assert palette_order(PALETTE) == ["gelb", "orange", "rot"]


def test_palette_order_and_lookup_accept_none() -> None:
    """``None`` (Renderer ohne Palette) verhält sich wie eine leere Palette."""
    assert palette_order(None) == []
    assert palette_by_key(None) == {}


def test_palette_by_key_maps_label_and_hex() -> None:
    """Der Lookup liefert ``(label, hex)`` je Farbschlüssel."""
    assert palette_by_key(PALETTE)["rot"] == ("Rot", "#333333")


def test_palette_shortcut_by_key_maps_color_number() -> None:
    """Der Kürzel-Lookup liefert die Farbnummer je Farbschlüssel."""
    assert palette_shortcut_by_key(PALETTE) == {"gelb": "1", "orange": "2", "rot": "3"}
    assert palette_shortcut_by_key(None) == {}


def test_order_color_keys_sorts_by_palette_and_dedupes() -> None:
    """Tags werden nach Palette sortiert, Duplikate entfernt."""
    assert order_color_keys(["rot", "gelb", "rot"], palette_order(PALETTE)) == ["gelb", "rot"]


def test_order_color_keys_appends_unknown_keys_in_input_order() -> None:
    """Unbekannte Schlüssel gehen nicht verloren, sondern kommen hinten in Eingangsreihenfolge."""
    result = order_color_keys(["zz", "orange", "aa"], palette_order(PALETTE))
    assert result == ["orange", "zz", "aa"]


def test_real_palette_is_numbered_one_to_nine() -> None:
    """Die echte Palette ist der Nummerierung 1..9 nach geordnet (Grundlage für "Farbe 1 innen")."""
    assert [key for key, _color_key, _label, _hex in COLOR_MARKER_PALETTE] == [str(n) for n in range(1, 10)]


def test_palette_color_resolves_known_and_falls_back_for_unknown_keys() -> None:
    """Bekannte Schlüssel liefern Label/Hex, unbekannte ihren Schlüssel und die Ersatzfarbe."""
    lookup = palette_by_key(PALETTE)
    assert palette_color(lookup, "gelb") == ("Gelb", "#111111")
    assert palette_color(lookup, "blau") == ("blau", FALLBACK_COLOR_HEX)
