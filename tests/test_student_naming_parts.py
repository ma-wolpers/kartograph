"""Tests für Namensteile und den Zeilenumbruch (compute_display_name_parts, fit_name_to_width).

Die einzeiligen Namen deckt ``test_student_naming.py`` ab; hier geht es um die
Trennung in vorderen/hinteren Teil und den Umbruch für schmale Ansichten
(Sitzplan-Vorschau). Gemessen wird mit einer Attrappe: Breite = Zeichenanzahl.
"""

import pytest

from app.core.domain.student_naming import (
    compute_display_name_parts,
    compute_display_names,
    fit_name_to_width,
    join_name_parts,
)
from tests.conftest import make_student

_FORMATS = ["Vorname", "Vorname N", "Vorname Nachname", "V. Nachname", "Nachname"]
_STUDENTS = [
    make_student(first_name="Anna Lena", last_name="von Berg"),
    make_student(first_name="Paul", last_name="Möller"),
    make_student(first_name="Paul", last_name="Müller"),
    make_student(first_name="Ida", last_name=""),
    make_student(first_name="", last_name="Gold"),
]


def _parts(students, name_format, disambiguate=False):
    result = compute_display_name_parts(students, name_format, disambiguate)
    return [result[s.student_id] for s in students]


@pytest.mark.parametrize("disambiguate", [False, True])
@pytest.mark.parametrize("name_format", _FORMATS)
def test_joined_parts_equal_single_line_names(name_format, disambiguate):
    """Die Teile ergeben zusammengesetzt exakt die bisherigen einzeiligen Namen."""
    parts = compute_display_name_parts(_STUDENTS, name_format, disambiguate)
    names = compute_display_names(_STUDENTS, name_format, disambiguate)
    assert {sid: join_name_parts(p) for sid, p in parts.items()} == names


def test_parts_split_between_first_and_last_name_even_with_spaces():
    """Leerzeichen innerhalb eines Namensteils trennen nicht."""
    assert _parts(_STUDENTS[:1], "Vorname Nachname") == [("Anna Lena", "von Berg")]


def test_disambiguated_last_name_prefix_is_the_back_part():
    assert _parts(_STUDENTS[1:3], "Vorname", disambiguate=True) == [("Paul", "Mö"), ("Paul", "Mü")]


def test_initial_format_puts_initial_in_front():
    assert _parts(_STUDENTS[1:2], "V. Nachname") == [("P.", "Möller")]


class TestFitNameToWidth:
    def test_stays_single_line_when_it_fits(self):
        assert fit_name_to_width(("Paul", "Möller"), max_width=11, measure=len) == "Paul Möller"

    def test_wraps_back_part_when_too_wide(self):
        assert fit_name_to_width(("Anna Lena", "von Berg"), max_width=10, measure=len) == "Anna Lena\nvon Berg"

    def test_single_part_never_wraps(self):
        assert fit_name_to_width(("Maximiliane", ""), max_width=3, measure=len) == "Maximiliane"
