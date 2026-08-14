"""Tests für compute_display_names() (Namensformat + Eindeutigkeits-Modus)."""

from app.core.domain.student_naming import compute_display_names
from tests.conftest import make_student

# Namensvettern-Beispiel aus der Feature-Anfrage: Paul Möller, Paul Müller,
# Peter Müller, Anna Gold, Peter Gold.
_COUSINS = [
    make_student(first_name="Paul", last_name="Möller"),
    make_student(first_name="Paul", last_name="Müller"),
    make_student(first_name="Peter", last_name="Müller"),
    make_student(first_name="Anna", last_name="Gold"),
    make_student(first_name="Peter", last_name="Gold"),
]


def _labels(students, name_format, disambiguate):
    result = compute_display_names(students, name_format, disambiguate)
    return [result[s.student_id] for s in students]


class TestDisambiguateOff:
    """Ohne Kollisions-Modus verhält sich compute_display_names() wie das alte, fixe Format."""

    def test_vorname_nachname(self):
        assert _labels(_COUSINS, "Vorname Nachname", disambiguate=False) == [
            "Paul Möller", "Paul Müller", "Peter Müller", "Anna Gold", "Peter Gold",
        ]

    def test_vorname_always_bare_regardless_of_collisions(self):
        assert _labels(_COUSINS, "Vorname", disambiguate=False) == [
            "Paul", "Paul", "Peter", "Anna", "Peter",
        ]

    def test_vorname_n(self):
        assert _labels(_COUSINS, "Vorname N", disambiguate=False) == [
            "Paul M", "Paul M", "Peter M", "Anna G", "Peter G",
        ]

    def test_v_nachname(self):
        assert _labels(_COUSINS, "V. Nachname", disambiguate=False) == [
            "P. Möller", "P. Müller", "P. Müller", "A. Gold", "P. Gold",
        ]

    def test_nachname(self):
        assert _labels(_COUSINS, "Nachname", disambiguate=False) == [
            "Möller", "Müller", "Müller", "Gold", "Gold",
        ]


class TestDisambiguateOnNamesakeExample:
    """Kollisions-Modus, exakt gegen das vorgegebene Beispiel geprüft."""

    def test_vorname_nachname_already_maximal_unchanged(self):
        assert _labels(_COUSINS, "Vorname Nachname", disambiguate=True) == [
            "Paul Möller", "Paul Müller", "Peter Müller", "Anna Gold", "Peter Gold",
        ]

    def test_vorname(self):
        assert _labels(_COUSINS, "Vorname", disambiguate=True) == [
            "Paul Mö", "Paul Mü", "Peter M", "Anna", "Peter G",
        ]

    def test_vorname_n_matches_vorname(self):
        """Vorname und Vorname N werden im Kollisions-Modus bewusst identisch behandelt."""
        assert _labels(_COUSINS, "Vorname N", disambiguate=True) == _labels(
            _COUSINS, "Vorname", disambiguate=True
        )

    def test_v_nachname(self):
        assert _labels(_COUSINS, "V. Nachname", disambiguate=True) == [
            "P. Möller", "Pa. Müller", "Pe. Müller", "A. Gold", "P. Gold",
        ]

    def test_nachname(self):
        assert _labels(_COUSINS, "Nachname", disambiguate=True) == [
            "Möller", "Pa. Müller", "Pe. Müller", "A. Gold", "P. Gold",
        ]


class TestDisambiguateEdgeCases:
    def test_true_duplicate_does_not_crash_and_terminates(self):
        """Identischer Vor- UND Nachname: Wachstum stoppt, Duplikat bleibt akzeptiert."""
        dup = [make_student(first_name="Paul", last_name="Möller") for _ in range(2)]
        result = compute_display_names(dup, "Vorname", disambiguate=True)
        assert len(result) == 2

    def test_empty_names_do_not_crash(self):
        empty = [make_student(first_name="", last_name="") for _ in range(2)]
        result = compute_display_names(empty, "Vorname", disambiguate=True)
        assert all(label == "" for label in result.values())

    def test_grouping_uses_nickname_not_official_first_name(self):
        """Kollisionserkennung vergleicht den effektiven (Spitz-)Vornamen, nicht first_name_official."""
        students = [
            make_student(first_name="Alexander", last_name="Meyer", nickname="Alex"),
            make_student(first_name="Alex", last_name="Schmidt"),
        ]
        result = compute_display_names(students, "Vorname", disambiguate=True)
        labels = [result[s.student_id] for s in students]
        assert labels == ["Alex M", "Alex S"]

    def test_single_student_stays_bare_first_name(self):
        solo = [make_student(first_name="Anna", last_name="Gold")]
        result = compute_display_names(solo, "Vorname", disambiguate=True)
        assert result[solo[0].student_id] == "Anna"

    def test_unique_last_name_stays_bare_in_nachname_format(self):
        solo = [make_student(first_name="Anna", last_name="Gold")]
        result = compute_display_names(solo, "Nachname", disambiguate=True)
        assert result[solo[0].student_id] == "Gold"
