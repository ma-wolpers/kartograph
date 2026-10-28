"""Tests für die Notenskalen-Registry und die Umrechnung Schulnoten ↔ Punkte."""

import pytest

from app.core.domain.grade_scale import (
    GRADE_SCALES,
    SCALE_POINTS_0_15,
    SCALE_SCHOOL_1_6,
    convert_value,
    grade_to_points,
    points_to_grade,
    scale_for,
)


ANCHORS = {
    15: 0.7, 14: 1.0, 13: 1.3, 12: 1.7, 11: 2.0, 10: 2.3, 9: 2.7, 8: 3.0,
    7: 3.3, 6: 3.7, 5: 4.0, 4: 4.3, 3: 4.7, 2: 5.0, 1: 5.3, 0: 6.0,
}


class TestRegistry:
    def test_ids_match_korrektor(self):
        assert SCALE_SCHOOL_1_6 == "schulnoten_1_6"
        assert SCALE_POINTS_0_15 == "punktnoten_0_15"

    def test_unknown_id_falls_back_to_school_grades(self):
        assert scale_for(None).scale_id == SCALE_SCHOOL_1_6
        assert scale_for("quatsch").scale_id == SCALE_SCHOOL_1_6

    def test_school_range_allows_one_plus(self):
        school = GRADE_SCALES[SCALE_SCHOOL_1_6]
        assert school.contains(0.7)
        assert not school.contains(0.6)
        assert not school.contains(7)

    def test_points_range(self):
        points = GRADE_SCALES[SCALE_POINTS_0_15]
        assert points.contains(0)
        assert points.contains(15)
        assert not points.contains(16)
        assert points.clamp(-1) == 0.0

    @pytest.mark.parametrize(
        ("scale_id", "value", "expected"),
        [
            (SCALE_SCHOOL_1_6, 2.3, "2.30"),
            (SCALE_POINTS_0_15, 12.0, "12"),
            (SCALE_POINTS_0_15, 7.5, "7.5"),
            (SCALE_POINTS_0_15, 0.0, "0"),
        ],
    )
    def test_format_value(self, scale_id, value, expected):
        assert scale_for(scale_id).format_value(value) == expected


class TestConversion:
    @pytest.mark.parametrize(("points", "grade"), sorted(ANCHORS.items()))
    def test_anchor_table_both_directions(self, points, grade):
        assert points_to_grade(points) == grade
        assert grade_to_points(grade) == points

    @pytest.mark.parametrize(
        ("grade", "points"),
        [
            (3.2, 7.0),     # knapp neben 3.3 → glatt
            (3.15, 7.5),    # Grenzfall genau mittig
            (2.5, 9.5),     # Lücke zwischen 2.3 und 2.7
            (5.65, 0.5),    # große Lücke zwischen 5.3 und 6.0
            (5.44, 1.0),
            (5.86, 0.0),
            (0.85, 14.5),
            (0.5, 15.0),    # unterhalb der Skala begrenzt
            (6.5, 0.0),
        ],
    )
    def test_grade_to_points_examples(self, grade, points):
        assert grade_to_points(grade) == points

    def test_half_points_interpolate(self):
        assert points_to_grade(7.5) == 3.15
        assert points_to_grade(0.5) == 5.65
        assert points_to_grade(14.5) == 0.85

    @pytest.mark.parametrize("half_steps", range(31))
    def test_half_points_roundtrip_lossless(self, half_steps):
        points = half_steps / 2
        assert grade_to_points(points_to_grade(points)) == points

    def test_convert_value_dispatches_by_direction(self):
        assert convert_value(3.2, SCALE_SCHOOL_1_6, SCALE_POINTS_0_15) == 7.0
        assert convert_value(7.5, SCALE_POINTS_0_15, SCALE_SCHOOL_1_6) == 3.15
        assert convert_value(2.3, SCALE_SCHOOL_1_6, SCALE_SCHOOL_1_6) == 2.3
