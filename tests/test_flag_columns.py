"""Tests für Ja/Nein-Spalten (``core/domain/flag_columns``) und ihre Unsichtbarkeit auf dem Sitzplan."""

from __future__ import annotations

from app.core.domain.color_order import order_color_keys
from app.core.domain.flag_columns import (
    flag_column_keys,
    free_color_keys,
    is_colorless_flag,
    new_colorless_key,
)

ORDER = ["gelb", "orange", "rot"]


def test_new_colorless_key_is_unique_and_recognised():
    key = new_colorless_key(["gelb"])
    assert is_colorless_flag(key) and len(key) == len("flag_") + 8
    assert not is_colorless_flag("gelb")


def test_free_colors_follow_palette_order():
    assert free_color_keys(ORDER, ["rot", "flag_1"]) == ["gelb", "orange"]
    assert free_color_keys(ORDER, ORDER) == []


def test_flag_column_order_colors_then_foreign_then_colorless():
    in_use = ["flag_b", "rot", "blau", "gelb", "flag_a", "rot"]
    assert flag_column_keys(ORDER, in_use) == ["gelb", "rot", "blau", "flag_b", "flag_a"]


def test_colorless_marks_never_reach_seat_plan_renderers():
    assert order_color_keys(["flag_x", "rot", "blau", "gelb"], ORDER) == ["gelb", "rot", "blau"]
