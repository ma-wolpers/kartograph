"""Tests für die Gewichtungsregeln (``app/core/domain/grade_weighting.py``)."""

import math

import pytest

from app.core.domain.grade_weighting import (
    category_percents,
    effective_column_shares,
    format_factor,
    normalize_factor,
    normalized_category_percents,
    parse_factor,
    parse_percent,
    weighted_mean,
)
from app.core.domain.models_v4 import GradeColumn, GradeWeighting


class TestFactors:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("2", 2.0), (0.5, 0.5), (None, 1.0), ("x", 1.0), (-3, 0.0), (float("nan"), 1.0), (float("inf"), 1.0)],
    )
    def test_normalize_factor(self, raw, expected):
        assert normalize_factor(raw) == expected

    @pytest.mark.parametrize(("text", "expected"), [("0,5", 0.5), (" 2 ", 2.0), ("0", 0.0), ("1.25", 1.25)])
    def test_parse_factor_accepts_comma_and_dot(self, text, expected):
        assert parse_factor(text) == expected

    @pytest.mark.parametrize("text", ["", "abc", "-1", "nan", "inf"])
    def test_parse_factor_rejects_invalid(self, text):
        with pytest.raises(ValueError):
            parse_factor(text)

    @pytest.mark.parametrize(("value", "expected"), [(2.0, "2"), (0.5, "0.5"), (0.0, "0"), (1.25, "1.25")])
    def test_format_factor(self, value, expected):
        assert format_factor(value) == expected


class TestParsePercent:
    @pytest.mark.parametrize(("text", "expected"), [("60", 60), (" 0 ", 0), ("100", 100)])
    def test_accepts_non_negative_integers(self, text, expected):
        assert parse_percent(text) == expected

    @pytest.mark.parametrize("text", ["", "abc", "-5", "12.5"])
    def test_rejects_invalid(self, text):
        with pytest.raises(ValueError):
            parse_percent(text)


class TestCategoryPercents:
    @pytest.mark.parametrize(
        ("written", "sonstige", "expected"),
        [(60, 40, (60, 40)), (-10, 50, (0, 50)), (0, 0, (50, 50)), (None, "x", (50, 50)), ("70", 30, (70, 30))],
    )
    def test_normalized_category_percents(self, written, sonstige, expected):
        assert normalized_category_percents(written, sonstige) == expected

    def test_category_percents_maps_fields_to_categories(self):
        assert category_percents(GradeWeighting(70, 30)) == {"schriftlich": 70, "sonstig": 30}
        assert category_percents(GradeWeighting(0, 0)) == {"schriftlich": 50, "sonstig": 50}


class TestWeightedMean:
    def test_weighted(self):
        assert weighted_mean([(1.0, 2.0), (4.0, 1.0)]) == 2.0

    def test_none_without_counting_weight(self):
        assert weighted_mean([]) is None
        assert weighted_mean([(3.0, 0.0)]) is None


class TestEffectiveColumnShares:
    def test_shares_follow_factors_and_category_percents(self):
        columns = [
            GradeColumn("w1", "schriftlich", "KA 1"),
            GradeColumn("w2", "schriftlich", "KA 2"),
            GradeColumn("s1", "sonstig", "Referat", weight=2.0),
            GradeColumn("s2", "sonstig", "Heft"),
            GradeColumn("s3", "sonstig", "Test", weight=0.5),
        ]
        shares = effective_column_shares(columns, GradeWeighting(50, 50))
        assert shares["w1"] == shares["w2"] == 0.25
        assert math.isclose(shares["s1"], 0.5 * 2 / 3.5)
        assert math.isclose(sum(shares.values()), 1.0)

    def test_category_with_zero_factor_sum_gets_no_share(self):
        columns = [GradeColumn("w", "schriftlich", "KA"), GradeColumn("s", "sonstig", "Heft", weight=0.0)]
        shares = effective_column_shares(columns, GradeWeighting(60, 40))
        assert shares == {"w": 0.6, "s": 0.0}
