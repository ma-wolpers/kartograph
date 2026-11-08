"""Formularlogik des Gewichtungsdialogs (Tk-frei)."""

from __future__ import annotations

import math

import pytest

from app.adapters.gui.grade_weighting_form import complement_percent, evaluate_weighting_form, format_share
from app.core.domain.models_v4 import GradeColumn

COLUMNS = [
    GradeColumn("ka", "schriftlich", "KA 1"),
    GradeColumn("ref", "sonstig", "Referat", weight=2.0),
    GradeColumn("heft", "sonstig", "Heft"),
]


def test_valid_form_yields_intent_values_and_live_shares():
    result = evaluate_weighting_form(COLUMNS, "50", "50", {"ka": "1", "ref": "2", "heft": "1"})
    assert (result.written_percent, result.sonstige_percent) == (50, 50)
    assert result.column_weights == (("ka", 1.0), ("ref", 2.0), ("heft", 1.0))
    assert result.shares["ka"] == 0.5
    assert math.isclose(result.shares["ref"], 1 / 3)


def test_shares_follow_unsaved_input_not_the_stored_weights():
    result = evaluate_weighting_form(COLUMNS, "60", "40", {"ka": "1", "ref": "1", "heft": "1"})
    assert math.isclose(result.shares["ref"], 0.2)


@pytest.mark.parametrize(
    ("written", "sonstige", "factors", "message_part"),
    [
        ("x", "50", {"ka": "1", "ref": "1", "heft": "1"}, "Prozentanteile"),
        ("0", "0", {"ka": "1", "ref": "1", "heft": "1"}, "größer als 0"),
        ("50", "50", {"ka": "1", "ref": "-1", "heft": "1"}, "Referat"),
        ("50", "50", {"ka": "1", "ref": "1"}, "Heft"),
    ],
)
def test_invalid_input_names_the_problem(written, sonstige, factors, message_part):
    with pytest.raises(ValueError, match=message_part):
        evaluate_weighting_form(COLUMNS, written, sonstige, factors)


@pytest.mark.parametrize(("text", "expected"), [("60", "40"), ("0", "100"), ("100", "0"), ("", None), ("150", None)])
def test_complement_percent(text, expected):
    assert complement_percent(text) == expected


def test_format_share():
    assert format_share(0.25) == "25.0 %"
